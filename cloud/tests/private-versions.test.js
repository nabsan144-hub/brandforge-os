import {it,expect,vi,beforeAll,afterAll,beforeEach,afterEach} from 'vitest';
import {randomUUID} from 'node:crypto';
import sharp from 'sharp';
vi.mock('../api/_lib/sb.js',()=>({admin:vi.fn(),authUser:vi.fn(),json:(b,s=200)=>new Response(JSON.stringify(b),{status:s})}));
vi.mock('../api/_lib/limit.js',()=>({rateLimit:vi.fn(async()=>true)}));
vi.mock('../api/_lib/visuals_ai.js',async original=>({...await original(),generateScene:vi.fn()}));
import {admin,authUser} from '../api/_lib/sb.js';
import {generateScene} from '../api/_lib/visuals_ai.js';
import {runCampaign} from '../api/_lib/engine.js';
import {stageAssetBundle,loadStoredFiles} from '../api/_lib/assets.js';
import {redrawVectors} from '../api/_lib/vector-corrections.js';
import correct from '../api/_lib/routes/camp-visuals.js';
import recover from '../api/_lib/routes/image-recovery.js';
import {database,request} from './helpers/db.js';
let sb,user,id,oldBundle,original,blobs;
const row=async()=> (await sb.from('campaigns').select('*').eq('id',id).single()).data;
beforeAll(async()=>{sb=await database();admin.mockReturnValue(sb);},30000);afterAll(()=>sb.close());
beforeEach(async()=>{vi.stubEnv('VECTOR_CORRECTIONS_ENABLED','true');blobs=new Map();sb.storage={getBucket:async()=>({data:{public:false},error:null}),from:()=>({upload:async(path,data)=>{blobs.set(path,Buffer.from(data));return {data:{},error:null};},download:async path=>({data:new Blob([blobs.get(path)||'corrupt']),error:null})})};user=await sb.user('pro');authUser.mockResolvedValue(user);id=randomUUID();const p=await runCampaign({product:'Coffee',provider:'offline',style:'product-v1',product_image:'data:image/jpeg;base64,'+(await sharp({create:{width:120,height:100,channels:3,background:'#b7352e'}}).jpeg().toBuffer()).toString('base64'),product_image_rights:true,benefits:'Whole beans',offer:'Rs 100',cta:'View'});original=p.files;await sb.from('campaigns').insert({id,user_id:user.id,name:'Private',product:'Coffee',provider:'offline',files:p.files,visual_recipe:p.visual_recipe,visual_fields:p.visual_fields,visual_status:{mode:'svg',state:'fallback'},visual_review_state:'unchanged'});oldBundle=(await stageAssetBundle(sb,{uid:user.id,sourceCampaignId:id,sourceRevision:1,files:p.files,bucket:'private'})).id;expect((await sb.rpc('attach_migrated_asset_bundle',{p_uid:user.id,p_campaign:id,p_revision:1,p_bundle:oldBundle})).data.ok).toBe(true);});afterEach(()=>vi.unstubAllEnvs());
it('corrects private vectors, retains old immutable sources and restores exact bytes',async()=>{
 const c=await row(),b={revision:1,request_id:randomUUID(),visual_fields:{...c.visual_fields,headline:'Revised headline'}};
 const r=await correct(request('/campaigns/'+id+'/visuals','POST',b),{params:{id}});expect(r.status).toBe(200);expect((await correct(request('/campaigns/'+id+'/visuals','POST',b),{params:{id}})).status).toBe(200);
 const changed=await row();expect(changed.asset_bundle_id).not.toBe(oldBundle);expect(changed.files.every(f=>f.storage==='bundle')).toBe(true);expect((await loadStoredFiles(sb,user.id,changed)).files[0].content).toContain('Revised headline');
 expect((await sb.rpc('claim_campaign_asset_cleanup',{p_limit:25})).data).toHaveLength(0);
 expect((await sb.rpc('restore_vector_revision',{p_uid:user.id,p_id:id,p_revision:2,p_restore:1})).data.ok).toBe(true);const restored=await row();expect(restored.asset_bundle_id).toBe(oldBundle);expect((await loadStoredFiles(sb,user.id,restored)).files).toEqual(original);
});
it('rejects corrupt original bytes before rendering or replacing stored files',async()=>{
 for(const path of blobs.keys())blobs.set(path,Buffer.from('bad'));
 const c=await row();const r=await correct(request('/campaigns/'+id+'/visuals','POST',{revision:1,request_id:randomUUID(),visual_fields:c.visual_fields}),{params:{id}});expect(r.status).toBe(409);expect((await row()).revision).toBe(1);
});
it('recovers a private image fallback and can restore its original private vector version',async()=>{
 for(const [k,v]of Object.entries({IMAGE_RECOVERY_ENABLED:'true',AI_VISUALS_ENABLED:'true',AI_VISUALS_PROVIDER:'openai',AI_VISUAL_MODEL:'gpt-image-1',AI_VISUALS_OPENAI_KEY:'fixture',AI_VISUALS_OPENAI_COST_MODEL:'gpt-image-1',AI_VISUALS_OPENAI_MAX_USD_PER_IMAGE:'0.1',MAX_PROVIDER_DAILY_USD:'100'}))vi.stubEnv(k,v);
 generateScene.mockResolvedValue({data:(await sharp({create:{width:200,height:100,channels:3,background:'#653f2a'}}).jpeg().toBuffer()).toString('base64'),mime:'image/jpeg',model:'gpt-image-1',provider:'openai'});
 const r=await recover(request('/x','POST',{request_id:randomUUID(),revision:1,provider:'openai',consent:true}),{params:{id}});expect(r.status).toBe(200);expect((await row()).asset_bundle_id).not.toBe(oldBundle);
 const recovered=await row(),providerCalls=generateScene.mock.calls.length;
 const corrected=await correct(request('/x','POST',{revision:2,request_id:randomUUID(),visual_fields:{...recovered.visual_fields,headline:'Recovered and edited'}}),{params:{id}});expect(corrected.status).toBe(200);expect(generateScene.mock.calls.length).toBe(providerCalls);expect((await row()).visual_recipe.scene_sha256).toBe(recovered.visual_recipe.scene_sha256);
 expect((await sb.rpc('restore_vector_revision',{p_uid:user.id,p_id:id,p_revision:3,p_restore:1})).data.ok).toBe(true);expect((await loadStoredFiles(sb,user.id,await row())).files).toEqual(original);
});
it('prunes only unreferenced private history and queues it for cleanup',async()=>{
 for(let n=1;n<=12;n++){const c=await row();const r=await correct(request('/x','POST',{revision:c.revision,request_id:randomUUID(),visual_fields:{...c.visual_fields,headline:'Version '+n}}),{params:{id}});expect(r.status).toBe(200);}
 const garbage=(await sb.rpc('claim_campaign_asset_cleanup',{p_limit:25})).data;expect(garbage.length).toBeGreaterThan(0);const current=await row();expect(garbage.some(b=>b.id===current.asset_bundle_id)).toBe(false);
});

it('replaces a photo, edits benefits, selects crop and preserves attribution with idempotent restore',async()=>{
 const c=await row(),photo='data:image/jpeg;base64,'+(await sharp({create:{width:140,height:110,channels:3,background:'#246aac'}}).jpeg().toBuffer()).toString('base64');
 const body={revision:1,request_id:randomUUID(),visual_fields:{...c.visual_fields,benefits:'New benefit; Honest benefit',proof:'Owner supplied'},visual_layout:{logo_position:'right',photo_fit:'crop',product_image:photo,product_image_rights:true}};
 let r=await correct(request('/x','POST',body),{params:{id}});expect(r.status).toBe(200);const changed=await row();expect(changed.visual_recipe.common.photo_fit).toBe('crop');expect(changed.visual_recipe.common.benefits).toEqual(['New benefit','Honest benefit']);expect(changed.visual_recipe.common.watermark).toBe(c.visual_recipe.common.watermark);
 const files=(await loadStoredFiles(sb,user.id,changed)).files;expect(files.find(f=>f.name==='hero_banner.svg').content).toContain('xMidYMid slice');expect(files.find(f=>f.name==='approved_product_photo.jpg').content).not.toBe(original.find(f=>f.name==='approved_product_photo.jpg').content);
 r=await correct(request('/x','POST',body),{params:{id}});expect((await r.json()).replayed).toBe(true);
 r=await correct(request('/x','POST',{...body,visual_layout:{...body.visual_layout,photo_fit:'contain'}}),{params:{id}});expect(r.status).toBe(409);
 expect((await sb.rpc('restore_vector_revision',{p_uid:user.id,p_id:id,p_revision:2,p_restore:1})).data.ok).toBe(true);expect((await loadStoredFiles(sb,user.id,await row())).files).toEqual(original);expect((await row()).visual_recipe).toEqual(c.visual_recipe);
});
it('refuses unknown layout properties and unconsented replacement photos',async()=>{
 const c=await row();for(const layout of [{watermark:false},{logo_position:'outside'},{product_image:c.visual_recipe.common.product_image,product_image_rights:false}]){const r=await correct(request('/x','POST',{revision:1,request_id:randomUUID(),visual_fields:c.visual_fields,visual_layout:layout}),{params:{id}});expect(r.status).toBe(400);}expect((await row()).revision).toBe(1);
});
it('replaces an approved logo and crop anchor privately without losing exact restore',async()=>{
 const c=await row(),logo='data:image/png;base64,'+(await sharp({create:{width:64,height:40,channels:4,background:{r:10,g:100,b:60,alpha:.7}}}).png().toBuffer()).toString('base64');
 const body={revision:1,request_id:randomUUID(),visual_fields:c.visual_fields,visual_layout:{logo,logo_rights:true,photo_fit:'crop',photo_anchor:'bottom-right'}};
 const calls=generateScene.mock.calls.length;
 let r=await correct(request('/x','POST',body),{params:{id}});expect(r.status).toBe(200);expect(generateScene.mock.calls.length).toBe(calls);
 const changed=await row(),files=(await loadStoredFiles(sb,user.id,changed)).files;
 const source=files.find(f=>f.name==='approved_logo.png');expect(source.encoding).toBe('base64');expect(changed.visual_recipe.common.logo).toBe('data:image/png;base64,'+source.content);
 const hero=files.find(f=>f.name==='hero_banner.svg').content;expect(hero).toContain(changed.visual_recipe.common.logo);expect(hero).toContain('xMaxYMax slice');
 expect(files.filter(f=>f.name==='approved_logo.png')).toHaveLength(1);
 r=await correct(request('/x','POST',body),{params:{id}});expect((await r.json()).replayed).toBe(true);
 r=await correct(request('/x','POST',{...body,visual_layout:{...body.visual_layout,photo_anchor:'top'}}),{params:{id}});expect(r.status).toBe(409);
 expect((await sb.rpc('restore_vector_revision',{p_uid:user.id,p_id:id,p_revision:2,p_restore:1})).data.ok).toBe(true);
 expect((await loadStoredFiles(sb,user.id,await row())).files).toEqual(original);expect((await row()).visual_recipe).toEqual(c.visual_recipe);
});
it('rejects missing logo rights, malformed PNG and injectable anchors without saving',async()=>{
 const c=await row();for(const layout of [{logo:'bad',logo_rights:false},{logo:'data:image/png;base64,YWJj',logo_rights:true},{photo_anchor:'center" onload="alert(1)'},{photo_anchor:null}]){
  const r=await correct(request('/x','POST',{revision:1,request_id:randomUUID(),visual_fields:c.visual_fields,visual_layout:layout}),{params:{id}});expect(r.status).toBe(400);
 }expect((await row()).revision).toBe(1);
});
it('edits a new AI hero overlay without changing scene bytes or calling a provider, then restores',async()=>{
 const sceneData=(await sharp({create:{width:400,height:200,channels:3,background:'#a9462b'}}).jpeg().toBuffer()).toString('base64');
 generateScene.mockResolvedValue({data:sceneData,mime:'image/jpeg',provider:'openai',model:'fixture'});
 const p=await runCampaign({product:'Scene coffee',benefits:'Fresh beans',provider:'groq',style:'bold',watermark:true},{visualPlan:{enabled:true,key:'fixture',provider:'openai',model:'fixture'}});
 expect(p.visual_recipe.schema).toBe(2);
 const sceneId=randomUUID();await sb.from('campaigns').insert({id:sceneId,user_id:user.id,name:'Scene',product:'Scene coffee',provider:'offline',files:p.files,visual_recipe:p.visual_recipe,visual_fields:p.visual_fields,visual_status:p.visual_status,visual_review_state:'unchanged'});
 const before=generateScene.mock.calls.length;
 const body={revision:1,request_id:randomUUID(),visual_fields:{...p.visual_fields,headline:'A new headline'}};
 const r=await correct(request('/x','POST',body),{params:{id:sceneId}});expect(r.status).toBe(200);
 const c=(await sb.from('campaigns').select('*').eq('id',sceneId).single()).data;
 expect(c.files[0].content).toContain('data:image/jpeg;base64,'+sceneData);
 const corrupt=structuredClone(c);corrupt.files[0].content=corrupt.files[0].content.replace(sceneData,sceneData.slice(0,-4)+'AAAA');expect(()=>redrawVectors(corrupt,c.visual_fields)).toThrow(/scene failed verification/);expect(c.files[0].content).toContain('A new headline');expect(c.files[0].content).toContain('data-watermark="brandforge"');expect(c.visual_status).toEqual(p.visual_status);expect(generateScene.mock.calls.length).toBe(before);
 expect((await sb.rpc('restore_vector_revision',{p_uid:user.id,p_id:sceneId,p_revision:2,p_restore:1})).data.ok).toBe(true);
 const restored=(await sb.from('campaigns').select('*').eq('id',sceneId).single()).data;expect(restored.files).toEqual(p.files);
});
