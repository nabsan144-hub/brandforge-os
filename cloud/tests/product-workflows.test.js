import {it,expect,vi,beforeAll,afterAll,beforeEach,afterEach} from 'vitest';
import sharp from 'sharp';
import {randomUUID} from 'node:crypto';
vi.mock('../api/_lib/sb.js',()=>({authUser:vi.fn(),admin:vi.fn(),json:(b,s=200)=>new Response(JSON.stringify(b),{status:s})}));
vi.mock('../api/_lib/limit.js',()=>({rateLimit:vi.fn(async()=>true)}));
vi.mock('../api/_lib/keys.js',()=>({resolveCampaignKeys:vi.fn(async()=>({key_source:'offline'}))}));
import {authUser,admin} from '../api/_lib/sb.js';
import {rateLimit} from '../api/_lib/limit.js';
import create,{campaignInput} from '../api/_lib/routes/campaigns.js';
import preview from '../api/_lib/routes/campaign-preview.js';
import {runCampaign,PLANS,AD_SIZES} from '../api/_lib/engine.js';
import {bannerSvg} from '../api/_lib/visuals.js';
import {COMPOSITION_STYLES} from '../api/_lib/composition-vector.js';
import {redrawVectors} from '../api/_lib/vector-corrections.js';
import {vectorQuality} from '../public/vector-quality.js';
import {database,request} from './helpers/db.js';
let sb,user,photo;
const base={product_name:'Northline Coffee',industry:'Coffee',audience:'Coffee for home',benefits:'Whole beans; Small batches',offer:'250 g / Rs 1450',cta:'View the roasts',style:'product-v1',provider:'offline',product_image_rights:true};
beforeAll(async()=>{photo='data:image/jpeg;base64,'+(await sharp({create:{width:300,height:180,channels:3,background:'#ae542a'}}).jpeg().toBuffer()).toString('base64');sb=await database();admin.mockReturnValue(sb);},30000);
afterAll(()=>sb.close());
beforeEach(async()=>{user=await sb.user();authUser.mockResolvedValue(user);rateLimit.mockResolvedValue(true);vi.stubGlobal('fetch',vi.fn(()=>{throw new Error('No network allowed');}));});
afterEach(()=>{vi.unstubAllGlobals();vi.unstubAllEnvs();});
it('requires rights and rejects a remote photo, mixed AI request or excessive formats before charging',async()=>{
 for(const extra of [{product_image_rights:false},{product_image:'https://example.test/photo.jpg'},{visuals_ai:true},{style:'bold'}]){
  expect((await create(request('/campaigns','POST',{...base,product_image:photo,...extra}))).status).toBe(400);
 }
 expect(()=>campaignInput({...base,product_image:photo,custom_sizes:Object.keys(AD_SIZES).slice(0,4).map(preset=>({preset}))},PLANS.pro)).toThrow(/three/);
 expect((await sb.rpc('generation_totals',{p_uid:user.id})).data.campaigns_lifetime).toBe(0);expect(fetch).not.toHaveBeenCalled();
});
it('validates complete raster bytes before creating a generation reservation',async()=>{
 const result=await create(request('/campaigns','POST',{...base,product_image:'data:image/jpeg;base64,AAAA'}));expect(result.status).toBe(400);
 expect((await sb.rpc('generation_totals',{p_uid:user.id})).data.reserved).toBe(0);
});
it('previews real templates with no quota, campaigns or provider work, even when AI is requested',async()=>{
 const result=await preview(request('/campaign-preview','POST',{...base,product_image:photo,provider:'gemini',visuals_ai:true}));expect(result.status).toBe(200);
 const data=await result.json();expect(data.preview).toBe(true);expect(data.files.length).toBe(2);expect(data.files.every(f=>f.content.includes('xMidYMid meet'))).toBe(true);
 expect((await sb.rpc('generation_totals',{p_uid:user.id})).data).toMatchObject({campaigns_lifetime:0,reserved:0});expect((await sb.db.query('select count(*)::int n from campaigns where user_id=$1',[user.id])).rows[0].n).toBe(0);expect(fetch).not.toHaveBeenCalled();
});
it('guards preview authentication, method, rate limit and deletion',async()=>{
 authUser.mockResolvedValue(null);expect((await preview(request('/campaign-preview','POST',{}))).status).toBe(401);authUser.mockResolvedValue(user);
 expect((await preview(request('/campaign-preview'))).status).toBe(405);rateLimit.mockResolvedValue(false);expect((await preview(request('/campaign-preview','POST',{}))).status).toBe(429);
 rateLimit.mockResolvedValue(true);await sb.from('profiles').update({deletion_pending:true}).eq('id',user.id);expect((await preview(request('/campaign-preview','POST',{}))).status).toBe(409);
});
it('saves supplied imagery and replays once with fixed attribution',async()=>{
 const key=randomUUID(),body={...base,product_image:photo};const response=await create(request('/campaigns','POST',body,{'Idempotency-Key':key}));expect(response.status).toBe(200);
 const id=(await response.json()).id,row=(await sb.from('campaigns').select('*').eq('id',id).single()).data;
 expect(row.visual_status).toMatchObject({mode:'uploaded',state:'supplied',provider:null});expect(row.visual_recipe.common.product_image).toMatch(/^data:image\/jpeg/);
 expect(row.files.some(f=>f.name==='approved_product_photo.jpg')).toBe(true);for(const f of row.files.filter(f=>f.name.endsWith('.svg')))expect(f.content).toContain('data-watermark="brandforge"');
 expect(await(await create(request('/campaigns','POST',body,{'Idempotency-Key':key}))).json()).toMatchObject({id,replayed:true});expect((await sb.rpc('generation_totals',{p_uid:user.id})).data.campaigns_lifetime).toBe(1);expect(fetch).not.toHaveBeenCalled();
 const fields={headline:'Fresh coffee',subheadline:'',offer:'500 g / Rs 2700',cta:'Choose a roast',destination:''},changed=redrawVectors(row,fields);
 expect(changed.files.find(f=>f.name==='approved_product_photo.jpg')).toEqual(row.files.find(f=>f.name==='approved_product_photo.jpg'));expect(changed.files[0].content).toContain('500 g / Rs 2700');expect(changed.recipe.common.product_image).toBe(row.visual_recipe.common.product_image);
});
it.each(COMPOSITION_STYLES)('%s emits bounded geometry and explicit diagnostics across every preset',style=>{
 for(const [width,height]of Object.values(AD_SIZES)){
  const svg=bannerSvg({product:'Coffee',headline:'Fresh coffee',benefits:['Small batches','Whole beans'],offer:'Rs 250',cta:'View roasts',proof:'Roasted in small batches',product_image:photo,style,width,height,watermark:true});
  const report=vectorQuality([{name:'hero_banner.svg',content:svg}]);expect(report[0].renderer).toBe(style);expect(svg).toContain('data-watermark="brandforge"');
  for(const m of svg.matchAll(/data-box="([^"]+)"/g)){const [x,y,w,h]=m[1].split(',').map(Number);expect([x,y,w,h].every(Number.isFinite)).toBe(true);expect(x).toBeGreaterThanOrEqual(-.01);expect(y).toBeGreaterThanOrEqual(-.01);expect(x+w).toBeLessThanOrEqual(width+.1);expect(y+h).toBeLessThanOrEqual(height+.1);}
 }
});
it('does not invent proof or silently print a fraction of a long price condition',()=>{
 expect(()=>campaignInput({product_name:'Coffee',style:'evidence-v1'},PLANS.free)).toThrow(/proof/);expect(()=>campaignInput({product_name:'Coffee',style:'offer-v1'},PLANS.free)).toThrow(/offer/);
 const svg=bannerSvg({product:'Coffee',style:'offer-v1',offer:'For eligible members only '.repeat(30),width:320,height:50,watermark:true});
 expect(vectorQuality([{name:'banner.svg',content:svg}])[0].fields.find(f=>f.field==='offer').status).toBe('omitted_unfit');expect(svg).not.toContain('For eligible');
});
it('keeps supplied photos out of every text provider request',async()=>{
 const calls=[];vi.stubGlobal('fetch',vi.fn(async(u,o)=>{calls.push(o.body);return {ok:false,status:400};}));
 await runCampaign({product:'Coffee',product_image:photo,provider:'groq',style:'product-v1',benefits:'Fresh beans'},{groqKey:'fixture'});
 expect(calls).toHaveLength(3);expect(calls.every(s=>!s.includes('base64')&&!s.includes(photo))).toBe(true);
});
it('resolves opt-in automatic composition without changing the legacy default',()=>{
 expect(campaignInput({product_name:'Brand'},PLANS.free).style).toBe('bold');
 for(const [extra,style] of [[{product_image:photo,product_image_rights:true},'product-v1'],[{proof:'Supplied proof'},'evidence-v1'],[{offer:'Rs 100'},'offer-v1'],[{benefits:'Small group'},'service-v1'],[{},'editorial-v1']])expect(campaignInput({product_name:'Brand',style:'auto-v1',...extra},PLANS.free).style).toBe(style);
});
