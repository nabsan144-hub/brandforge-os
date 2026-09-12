import {it,expect,vi,beforeAll,afterAll,beforeEach,afterEach} from 'vitest';
import {randomUUID} from 'node:crypto';
import sharp from 'sharp';
vi.mock('../api/_lib/sb.js',()=>({admin:vi.fn(),authUser:vi.fn(),json:(b,s=200)=>new Response(JSON.stringify(b),{status:s})}));
vi.mock('../api/_lib/limit.js',()=>({rateLimit:vi.fn(async()=>true)}));
vi.mock('../api/_lib/visuals_ai.js',async original=>({...await original(),generateScene:vi.fn()}));
import {admin,authUser} from '../api/_lib/sb.js';
import {generateScene} from '../api/_lib/visuals_ai.js';
import {runCampaign} from '../api/_lib/engine.js';
import handler from '../api/_lib/routes/image-recovery.js';
import {database,request} from './helpers/db.js';
let sb,user,id,original,scene;
const call=(body)=>handler(request('/campaigns/'+id+'/image-recovery','POST',body),{params:{id}});
const body=()=>({request_id:randomUUID(),revision:1,provider:'openai',consent:true});
beforeAll(async()=>{sb=await database();admin.mockReturnValue(sb);scene={data:(await sharp({create:{width:300,height:180,channels:3,background:'#73451a'}}).jpeg().toBuffer()).toString('base64'),mime:'image/jpeg',provider:'openai',model:'gpt-image-1'};},30000);afterAll(()=>sb.close());
beforeEach(async()=>{for(const [k,v]of Object.entries({IMAGE_RECOVERY_ENABLED:'true',AI_VISUALS_ENABLED:'true',AI_VISUALS_PROVIDER:'openai',AI_VISUAL_MODEL:'gpt-image-1',AI_VISUALS_OPENAI_KEY:'fixture',AI_VISUALS_OPENAI_COST_MODEL:'gpt-image-1',AI_VISUALS_OPENAI_MAX_USD_PER_IMAGE:'0.1',MAX_PROVIDER_DAILY_USD:'100'}))vi.stubEnv(k,v);user=await sb.user('pro');authUser.mockResolvedValue(user);id=randomUUID();const p=await runCampaign({product:'Coffee',provider:'offline',style:'service-v1',benefits:'Small batches',offer:'250g Rs 1450',cta:'View roasts'});original=p.files;await sb.from('campaigns').insert({id,user_id:user.id,name:'Recovery',product:'Coffee',industry:'Coffee',audience:'Adults',provider:'offline',copy:'UNCHANGED COPY',files:p.files,visual_recipe:p.visual_recipe,visual_fields:p.visual_fields,visual_status:{mode:'svg',state:'fallback'},visual_review_state:'unchanged',brief:{tone:'minimal',product_image:'PRIVATE PHOTO'}});generateScene.mockReset();generateScene.mockResolvedValue(scene);});
afterEach(()=>vi.unstubAllEnvs());
it('recovers only hero, reserves image spend, preserves copy/other files and replays without spending twice',async()=>{
 const b=body(),r=await call(b);expect(r.status).toBe(200);expect((await call(b)).status).toBe(200);expect(generateScene).toHaveBeenCalledTimes(1);
 const c=(await sb.from('campaigns').select('*').eq('id',id).single()).data;expect(c.copy).toBe('UNCHANGED COPY');expect(c.revision).toBe(2);expect(c.visual_status).toMatchObject({mode:'ai',provider:'openai'});expect(c.files[0].content).toContain('data:image/jpeg');
 for(const f of original.filter(f=>!['hero_banner.svg','brand_guidelines.md'].includes(f.name)))expect(c.files.find(x=>x.name===f.name)).toEqual(f);
 expect(JSON.stringify(generateScene.mock.calls[0][0])).not.toContain('PRIVATE PHOTO');expect((await sb.rpc('generation_totals',{p_uid:user.id})).data.campaigns_lifetime).toBe(0);
 expect((await sb.db.query('select count(*)::int n from operator_cost_reservations where id in (select id from campaign_image_jobs where campaign_id=$1)',[id])).rows[0].n).toBe(1);
 const restored=(await sb.rpc('restore_vector_revision',{p_uid:user.id,p_id:id,p_revision:2,p_restore:1})).data;expect(restored.ok).toBe(true);expect((await sb.from('campaigns').select('files,visual_status').eq('id',id).single()).data).toMatchObject({files:original,visual_status:{state:'fallback'}});
});
it('blocks missing consent, wrong owner, free plans, changed providers and private packs before model work',async()=>{
 expect((await call({...body(),consent:false})).status).toBe(400);expect((await call({...body(),provider:'gemini'})).status).toBe(409);
 authUser.mockResolvedValue(await sb.user('pro'));expect((await call(body())).status).toBe(404);authUser.mockResolvedValue(user);await sb.from('profiles').update({plan:'free'}).eq('id',user.id);expect((await call(body())).status).toBe(409);expect(generateScene).not.toHaveBeenCalled();
});
it('provider failure keeps files and paid allowance unchanged but retains the conservative spend reservation',async()=>{
 generateScene.mockRejectedValue(Object.assign(new Error('provider down'),{code:'VISUAL_PROVIDER_ERROR'}));const b=body();expect((await call(b)).status).toBe(503);expect((await call(b)).status).toBe(409);expect(generateScene).toHaveBeenCalledTimes(1);const c=(await sb.from('campaigns').select('files,revision').eq('id',id).single()).data;expect(c).toEqual({files:original,revision:1});
 expect((await sb.from('campaign_image_jobs').select('status').eq('campaign_id',id).single()).data.status).toBe('failed');
});
it('rejects conflicting concurrent changes after rendering and cannot overwrite a newer revision',async()=>{
 generateScene.mockImplementation(async()=>{await sb.from('campaigns').update({revision:2,copy:'NEWER COPY'}).eq('id',id);return scene;});expect((await call(body())).status).toBe(409);const c=(await sb.from('campaigns').select('files,copy').eq('id',id).single()).data;expect(c).toEqual({files:original,copy:'NEWER COPY'});
});
it('lost final response replays the committed save without another image or refunded budget',async()=>{
 sb.failNextRpc('finish_image_recovery',true);const b=body();expect((await call(b)).status).toBe(503);expect((await call(b)).status).toBe(200);expect(generateScene).toHaveBeenCalledTimes(1);
});
it('bounds daily retries and does not start a second image while a lease is active',async()=>{
 generateScene.mockRejectedValue(new Error('failed'));
 for(let i=0;i<3;i++)expect((await call(body())).status).toBe(503);
 const r=await call(body());expect(r.status).toBe(409);expect((await r.json()).code).toBe('DAILY_RECOVERY_LIMIT');expect(generateScene).toHaveBeenCalledTimes(3);
});
