import {it,expect,vi,beforeAll,afterAll,beforeEach,afterEach} from 'vitest';
import {randomUUID} from 'node:crypto';
import {gunzipSync} from 'node:zlib';
vi.mock('../api/_lib/sb.js',()=>({authUser:vi.fn(),admin:vi.fn(),json:(b,s=200)=>new Response(JSON.stringify(b),{status:s})}));
vi.mock('../api/_lib/limit.js',()=>({rateLimit:vi.fn(async()=>true)}));
import {admin,authUser} from '../api/_lib/sb.js';
import {runCampaign} from '../api/_lib/engine.js';
import {redrawVectors,correctionFields} from '../api/_lib/vector-corrections.js';
import correct from '../api/_lib/routes/camp-visuals.js';
import detail from '../api/_lib/routes/camp-id.js';
import archive from '../api/_lib/routes/me-export.js';
import {migrateInlineCampaign} from '../api/_lib/asset-migration.js';
import {database,request} from './helpers/db.js';
import {needsVisualReview,visualReviewNote} from '../public/visual-review.js';
let sb,user,campaign,original;
const fields={headline:'Fresh coffee today',subheadline:'Roasted for you',offer:'Rs 250 today',cta:'Shop today',destination:'https://example.test/coffee'};
const headers={'X-Brandforge-Review':'visual-review-v1','X-Brandforge-Visuals':'vector-corrections-v1'};
beforeAll(async()=>{sb=await database();admin.mockReturnValue(sb);original=await runCampaign({product:'Coffee',benefits:'Fresh beans, Clear origins',watermark:true,provider:'offline',style:'bold',custom_presets:1,custom_sizes:[{preset:'mobile_banner'}]});},30000);
afterAll(()=>sb.close());
beforeEach(async()=>{
 vi.stubEnv('VECTOR_CORRECTIONS_ENABLED','true');
 user=await sb.user();authUser.mockResolvedValue(user);
 const id=randomUUID();expect((await sb.rpc('reserve_generation',{p_uid:user.id,p_id:id,p_hash:'a'.repeat(64),p_lifetime_limit:3,p_monthly_limit:null,p_daily_limit:3,p_concurrency:1})).data.ok).toBe(true);
 const saved=await sb.rpc('complete_generation',{p_uid:user.id,p_id:id,p_campaign:{...original,product:'Coffee',name:'Coffee'}});expect(saved.error).toBeNull();campaign=saved.data.id;
 vi.stubGlobal('fetch',vi.fn(async()=>{throw new Error('Corrections must not call a provider');}));
});
afterEach(()=>{vi.unstubAllGlobals();vi.unstubAllEnvs();});
const get=async()=>(await sb.from('campaigns').select('*').eq('id',campaign).single()).data;
const save=(revision=1,request_id=randomUUID(),visual_fields=fields)=>correct(request('/campaigns/'+campaign+'/visuals','POST',{revision,request_id,visual_fields},headers));
const versions=async()=>(await sb.from('campaign_visual_versions').select('*').eq('campaign_id',campaign)).data;
it('persists recipes at generation and redraws vectors without provider calls or quota changes',async()=>{
 const before=await get();expect(before.visual_recipe.schema).toBe(1);expect((await save()).status).toBe(200);
 const after=await get();expect(after).toMatchObject({revision:2,visual_fields:fields,copy:before.copy,visual_review_state:'review_required'});expect(after.files[0].content).not.toBe(before.files[0].content);
 expect(after.files[0].content).toContain('Fresh coffee today');expect(after.files[0].content).toContain('RS 250 TODAY');
 expect(after.files.filter(f=>!f.name.startsWith('banner_')&&f.name!=='hero_banner.svg')).toEqual(before.files.filter(f=>!f.name.startsWith('banner_')&&f.name!=='hero_banner.svg'));
 for(const file of after.files.filter(f=>f.name.endsWith('.svg')))expect(file.content).toContain('data-watermark="brandforge"');
 expect(needsVisualReview(after)).toBe(true);expect(visualReviewNote(after)).not.toContain('NOT been redrawn');expect(fetch).not.toHaveBeenCalled();
 expect((await sb.rpc('generation_totals',{p_uid:user.id})).data).toMatchObject({campaigns_lifetime:1,reserved:0});expect(await versions()).toHaveLength(2);
});
it('reports omitted small-format headline/offer and metadata-only destinations',async()=>{
 await save();const row=await get();const strip=row.visual_field_report.find(f=>f.name==='banner_mobile_banner.svg');expect(strip.fields).toMatchObject({headline:'omitted',offer:'omitted',destination:'metadata_only'});
});
it('clearing a subheadline does not restore an old benefit as a fallback',async()=>{
 const data=redrawVectors(await get(),{...fields,subheadline:''});expect((data.files[0].content.match(/data-text="Clear origins"/g)||[]).length).toBe(1); // still present in the unchanged benefits list, not duplicated as the subhead
});
it('does not allow request data to change watermark, dimensions or recipe',async()=>{
 const r=await correct(request('/campaigns/'+campaign+'/visuals','POST',{revision:1,request_id:randomUUID(),visual_fields:fields,watermark:false},headers));expect(r.status).toBe(400);
 expect(()=>correctionFields({...fields,width:5000})).toThrow();expect((await get()).revision).toBe(1);
});
it('preserves paid attribution behavior independently of a later plan change',async()=>{
 const paid=await runCampaign({product:'Paid Coffee',benefits:'Coffee',provider:'offline',watermark:false,style:'bold'});
 const data=redrawVectors({...paid},fields);expect(data.files[0].content).not.toContain('data-watermark="brandforge"');
});
it.each(['legacy','private','ai'])('refuses %s data without overwriting artwork',async mode=>{
 const row=await get();if(mode==='legacy')row.visual_recipe=null;if(mode==='private')row.asset_bundle_id=randomUUID();if(mode==='ai')row.visual_status={mode:'ai'};
 expect(()=>redrawVectors(row,fields)).toThrow(/supported saved rendering recipe/);expect(row.files).toEqual(original.files);
});
it('owner and optimistic revision checks prevent cross-account or stale writes',async()=>{
 authUser.mockResolvedValue(await sb.user());expect((await save()).status).toBe(404);authUser.mockResolvedValue(user);
 expect((await save(2)).status).toBe(409);expect((await get()).revision).toBe(1);expect(await versions()).toHaveLength(0);
});
it('retries a lost committed response without another revision and rejects key reuse',async()=>{
 const key=randomUUID();sb.failNextRpc('save_vector_correction',true);expect((await save(1,key)).status).toBe(503);expect((await get()).revision).toBe(2);
 expect(await(await save(1,key)).json()).toMatchObject({replayed:true,revision:2});expect(await versions()).toHaveLength(2);
 expect((await save(1,key,{...fields,cta:'Other'})).status).toBe(409);
});
it('uncommitted save failure leaves current files and version history untouched',async()=>{
 sb.failNextRpc('save_vector_correction');expect((await save()).status).toBe(503);expect((await get()).files).toEqual(original.files);expect(await versions()).toHaveLength(0);
});
it('restores exact earlier visual bytes and text, then can restore the correction again',async()=>{
 await detail(request('/campaigns/'+campaign,'PATCH',{revision:1,copy:'Text before redraw'},headers));
 await save(2);const corrected=await get();expect(corrected.revision).toBe(3);
 await detail(request('/campaigns/'+campaign,'PATCH',{revision:3,acknowledge_visuals:true},headers));
 const restored=await detail(request('/campaigns/'+campaign,'PATCH',{revision:3,restore_revision:1},headers));expect(restored.status).toBe(200);
 expect(await get()).toMatchObject({files:original.files,copy:original.copy,revision:4,visual_review_ack_revision:null});
 expect((await detail(request('/campaigns/'+campaign,'PATCH',{revision:4,restore_revision:3},headers))).status).toBe(200);
 expect(await get()).toMatchObject({files:corrected.files,visual_fields:fields,copy:'Text before redraw',revision:5});
});
it('retains only file sets referenced by current or last ten text versions',async()=>{
 await save();for(let revision=2;revision<14;revision++)expect((await detail(request('/campaigns/'+campaign,'PATCH',{revision,copy:'Copy '+revision},headers))).status).toBe(200);
 expect(await versions()).toHaveLength(1);
 const snaps=(await sb.from('campaign_revisions').select('*').eq('campaign_id',campaign)).data;expect(snaps).toHaveLength(10);
});
it.each(['campaign','account'])('%s deletion cascades visual versions without refunding usage',async kind=>{
 await save();if(kind==='campaign')expect((await detail(request('/campaigns/'+campaign,'DELETE'))).status).toBe(200);else expect((await sb.auth.admin.deleteUser(user.id)).error).toBeNull();
 expect(await versions()).toHaveLength(0);
 if(kind==='campaign')expect((await sb.rpc('generation_totals',{p_uid:user.id})).data.campaigns_lifetime).toBe(1);
});
it('account archive pages include original and corrected visual versions',async()=>{
 await save();let all=[];for(let page=0;page<3;page++){
  const r=await archive(request('/me/export?page='+page,'GET',undefined,headers));expect(r.status).toBe(200);const data=JSON.parse(gunzipSync(Buffer.from(await r.arrayBuffer())).toString());all.push(...data.data.campaign_visual_versions);
 }
 expect(all).toHaveLength(2);expect(all.some(v=>v.payload.files[0].content===original.files[0].content)).toBe(true);
});
it('old review-only clients must reload for corrected campaigns and private conversion is blocked',async()=>{
 await save();expect((await detail(request('/campaigns/'+campaign,'GET',undefined,{'X-Brandforge-Review':'visual-review-v1'}))).status).toBe(409);
 await expect(migrateInlineCampaign(sb,{uid:user.id,campaignId:campaign})).rejects.toThrow(/stay inline/);
});
it('validates URLs, unsupported text, empty required fields and current role grants',async()=>{
 for(const value of [{...fields,destination:'javascript:alert(1)'},{...fields,headline:''},{...fields,headline:'x'.repeat(161)}])expect(()=>correctionFields(value)).toThrow();
 const r=await sb.db.query("select has_table_privilege('authenticated','campaign_visual_versions','SELECT') a,has_function_privilege('authenticated','save_vector_correction(uuid,uuid,integer,uuid,jsonb)','EXECUTE') b");expect(r.rows[0]).toEqual({a:false,b:false});
});

it('the rollout flag blocks new saves but preserves committed-request replay',async()=>{
 const key=randomUUID();expect((await save(1,key)).status).toBe(200);vi.stubEnv('VECTOR_CORRECTIONS_ENABLED','false');
 expect((await save(2)).status).toBe(503);expect(await(await save(1,key)).json()).toMatchObject({replayed:true});expect((await get()).revision).toBe(2);
});

it('outdated clients cannot acknowledge or restore a managed visual set',async()=>{
 await save();const old={'X-Brandforge-Review':'visual-review-v1'};
 for(const action of [{acknowledge_visuals:true},{restore_revision:1}])expect((await detail(request('/campaigns/'+campaign,'PATCH',{revision:2,...action},old))).status).toBe(409);
 expect((await get()).revision).toBe(2);expect((await get()).visual_review_ack_revision).toBeNull();
});
it('oversized replacement packs fail before saving any visual revision',async()=>{
 const row=await get();await sb.from('campaigns').update({files:[...row.files,{name:'extra.svg',content:'x'.repeat(3_000_000)}]}).eq('id',campaign);
 expect((await save()).status).toBe(413);expect((await get()).revision).toBe(1);expect(await versions()).toHaveLength(0);
});

it('replay after later edits does not overwrite the newer campaign',async()=>{
 const key=randomUUID();await save(1,key);await detail(request('/campaigns/'+campaign,'PATCH',{revision:2,copy:'Later copy'},headers));
 expect(await(await save(1,key)).json()).toMatchObject({replayed:true,revision:2});expect(await get()).toMatchObject({revision:3,copy:'Later copy'});
});
it('saves and restores an editorial recipe and its exact original visual bytes',async()=>{
 const candidate=await runCampaign({product:'Coffee',benefits:'Fresh beans, Clear origins',provider:'offline',watermark:true,style:'editorial-v1',custom_presets:1,custom_sizes:[{preset:'mobile_banner'}]});
 const id=randomUUID();await sb.rpc('reserve_generation',{p_uid:user.id,p_id:id,p_hash:'b'.repeat(64),p_lifetime_limit:3,p_monthly_limit:null,p_daily_limit:3,p_concurrency:1});
 const saved=await sb.rpc('complete_generation',{p_uid:user.id,p_id:id,p_campaign:{...candidate,product:'Coffee',name:'Editorial'}});expect(saved.error).toBeNull();campaign=saved.data.id;
 expect((await get()).visual_recipe.common.style).toBe('editorial-v1');expect((await save()).status).toBe(200);
 expect((await get()).files[0].content.includes('data-renderer="editorial-v1"')).toBe(true);
 const restored=await detail(request('/campaigns/'+campaign,'PATCH',{revision:2,restore_revision:1},headers));expect(restored.status).toBe(200);
 expect((await get()).files).toEqual(candidate.files);expect((await get()).visual_recipe).toEqual(candidate.visual_recipe);expect(fetch).not.toHaveBeenCalled();
});
