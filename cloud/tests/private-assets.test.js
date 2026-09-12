import {it,expect,vi,beforeAll,afterAll,beforeEach,afterEach} from 'vitest';
import {randomUUID} from 'node:crypto';
import {gunzipSync} from 'node:zlib';
vi.mock('../api/_lib/sb.js',()=>({authUser:vi.fn(),admin:vi.fn(),json:(b,s=200)=>new Response(JSON.stringify(b),{status:s,headers:{'Content-Type':'application/json','Cache-Control':'no-store'}})}));
vi.mock('../api/_lib/limit.js',()=>({rateLimit:vi.fn(async()=>true)}));
vi.mock('../api/_lib/keys.js',()=>({resolveCampaignKeys:vi.fn(async()=>({key_source:'offline'}))}));
vi.mock('../api/_lib/engine.js',async()=>({...await vi.importActual('../api/_lib/engine.js'),runCampaign:vi.fn()}));
import {admin,authUser} from '../api/_lib/sb.js';
import {runCampaign} from '../api/_lib/engine.js';
import create from '../api/_lib/routes/campaigns.js';
import detail from '../api/_lib/routes/camp-id.js';
import download from '../api/_lib/routes/camp-assets.js';
import accountExport from '../api/_lib/routes/me-export.js';
import {database,request} from './helpers/db.js';
import {encodeAssetBundle,collectAssetGarbage,stageAssetBundle} from '../api/_lib/assets.js';
import {migrateInlineCampaign,recoverInlineCampaign} from '../api/_lib/asset-migration.js';
import {mkdtemp,readFile,stat,rm} from 'node:fs/promises';
import {tmpdir} from 'node:os';
import {join} from 'node:path';
import {hydrateCampaign,hydrateAccountExport} from '../public/private-assets.js';
let sb,user,objects,storage,failUpload,failRemove,isPublic;
const headers={'X-Brandforge-Client':'asset-bundle-v1','X-Brandforge-Review':'visual-review-v1'};
const files=[{name:'hero.svg',content:'<svg xmlns="http://www.w3.org/2000/svg"/>'},{name:'logo.png',content:'aGk=',encoding:'base64'}];
beforeAll(async()=>{sb=await database();admin.mockReturnValue(sb);},30000);
afterAll(async()=>{await sb.close();});
beforeEach(async()=>{
 vi.stubEnv('CAMPAIGN_ASSETS_ENABLED','true');vi.stubEnv('CAMPAIGN_ASSET_BUCKET','private-assets');vi.stubEnv('SUPABASE_URL','https://storage.example.test');
 user=await sb.user();authUser.mockResolvedValue(user);objects=new Map();failUpload=false;failRemove=false;isPublic=false;
 storage={upload:vi.fn(async(path,data)=>{if(failUpload)return {error:{code:'UPLOAD_FAILED'}};objects.set(path,Buffer.from(data));return {data:{path}};}),remove:vi.fn(async paths=>{if(failRemove)return {error:{code:'DELETE_FAILED'}};for(const p of paths)objects.delete(p);return {data:paths};}),createSignedUrl:vi.fn(async path=>({data:{signedUrl:'https://storage.example.test/'+path+'?token=private'}}))};
 sb.storage={getBucket:vi.fn(async()=>({data:{public:isPublic}})),from:()=>storage};runCampaign.mockReset();runCampaign.mockResolvedValue({provider:'offline',files});
});
afterEach(()=>vi.unstubAllEnvs());
const generate=async(id=randomUUID(),h=headers)=>{const r=await create(request('/campaigns','POST',{product_name:'Coffee',provider:'offline'}, {...h,'idempotency-key':id}));return {status:r.status,...await r.json()};};
const row=async id=>(await sb.from('campaigns').select('*').eq('id',id).single()).data;
const totals=async()=>(await sb.rpc('generation_totals',{p_uid:user.id})).data;
const fetchStored=async url=>new Response(objects.get(new URL(url).pathname.slice(1)));
const authorize=async path=>{const r=await download(request(path,'GET',undefined,headers));if(!r.ok)throw new Error('Download unauthorized');return r.json();};
it('stores immutable bytes privately, attaches atomically, and replays without another upload',async()=>{
 const requestId=randomUUID(),saved=await generate(requestId);expect(saved.status).toBe(200);
 const campaign=await row(saved.id);expect(campaign.asset_bundle_id).toBeTruthy();expect(campaign.files[0]).not.toHaveProperty('content');
 expect((await totals()).campaigns_lifetime).toBe(1);
 const hydrated=await hydrateCampaign(campaign,authorize,process.env.SUPABASE_URL,fetchStored);expect(hydrated.files).toEqual(files);
 const replay=await generate(requestId);expect(replay).toMatchObject({id:saved.id,replayed:true});expect(storage.upload).toHaveBeenCalledTimes(1);
 expect(await collectAssetGarbage(sb)).toMatchObject({claimed:0});
});
it('a >3MB pack saves as bounded metadata, but per-file and bundle caps still apply',async()=>{
 runCampaign.mockResolvedValue({provider:'offline',files:[{name:'large.svg',content:'x'.repeat(3_100_000)}]});
 const saved=await generate();expect(saved.status).toBe(200);expect(JSON.stringify(await row(saved.id)).length).toBeLessThan(10000);
 expect(()=>encodeAssetBundle([{name:'big.svg',content:'x'.repeat(8_000_001)}])).toThrow(/size/);
 expect(()=>encodeAssetBundle([0,1,2].map(i=>({name:`f${i}`,content:'x'.repeat(7_000_000)})))).toThrow(/bundle size/);
});
it.each(['public','missing','client'])('%s storage preflight fails before engine execution or consumed allowance',async mode=>{
 if(mode==='public')isPublic=true;if(mode==='missing')vi.stubEnv('CAMPAIGN_ASSET_BUCKET','');
 expect((await generate(randomUUID(),mode==='client'?{}:headers)).status).toBe(mode==='client'?409:503);
 expect(runCampaign).not.toHaveBeenCalled();expect(await totals()).toMatchObject({campaigns_lifetime:0,reserved:0});
});
it('upload failure retains cleanup record but no campaign or allowance',async()=>{
 failUpload=true;expect((await generate()).status).toBe(503);expect(await totals()).toMatchObject({campaigns_lifetime:0,reserved:0});
 const pending=(await sb.from('campaign_asset_bundles').select('*').eq('user_id',user.id)).data;expect(pending).toHaveLength(1);expect(pending[0].uploaded_at).toBeNull();
 await sb.db.query("update campaign_asset_bundles set created_at=now()-interval '25 hours' where id=$1",[pending[0].id]);
 expect(await collectAssetGarbage(sb)).toMatchObject({removed:1});
});
it('failed save is collectible; a lost completion response never refunds or deletes attached files',async()=>{
 sb.failNextRpc('complete_generation');expect((await generate()).status).toBe(503);expect((await totals()).campaigns_lifetime).toBe(0);
 sb.failNextRpc('complete_generation',true);const id=randomUUID();expect((await generate(id)).status).toBe(503);expect((await totals()).campaigns_lifetime).toBe(1);
 const replay=await generate(id);expect(replay.replayed).toBe(true);
 await sb.db.query("update campaign_asset_bundles set created_at=now()-interval '25 hours' where user_id=$1",[user.id]);
 expect(await collectAssetGarbage(sb)).toMatchObject({removed:1});expect((await row(replay.id)).asset_bundle_id).toBeTruthy();expect(objects.size).toBe(1);
});
it('owner-only signed delivery, no-store and stale-client detail/export rejection',async()=>{
 const saved=await generate();const r=await download(request('/campaigns/'+saved.id+'/assets','GET',undefined,headers));expect(r.status).toBe(200);expect(r.headers.get('cache-control')).toBe('no-store');expect(storage.createSignedUrl).toHaveBeenCalledWith(expect.any(String),60);
 expect((await detail(request('/campaigns/'+saved.id))).status).toBe(409);expect((await accountExport(request('/me/export'))).status).toBe(409);
 authUser.mockResolvedValue(await sb.user());expect((await download(request('/campaigns/'+saved.id+'/assets','GET',undefined,headers))).status).toBe(404);expect(storage.createSignedUrl).toHaveBeenCalledTimes(1);
});
it('privacy changes fail closed, while the kill switch does not disable existing downloads',async()=>{
 const saved=await generate();vi.stubEnv('CAMPAIGN_ASSETS_ENABLED','false');expect((await authorize('/campaigns/'+saved.id+'/assets')).url).toContain('https:');
 isPublic=true;expect((await download(request('/campaigns/'+saved.id+'/assets','GET',undefined,headers))).status).toBe(503);
});
it.each(['campaign','account'])('%s deletion survives cascades and failed cleanup leases',async kind=>{
 const saved=await generate();
 if(kind==='campaign')expect((await detail(request('/campaigns/'+saved.id,'DELETE'))).status).toBe(200);
 else expect((await sb.auth.admin.deleteUser(user.id)).error).toBeNull();
 failRemove=true;expect(await collectAssetGarbage(sb)).toMatchObject({claimed:1,failed:1});expect(await collectAssetGarbage(sb)).toMatchObject({claimed:0});
 await sb.db.query("update campaign_asset_bundles set cleanup_until=now()-interval '1 minute' where state='deleting'");failRemove=false;
 expect(await collectAssetGarbage(sb)).toMatchObject({removed:1});expect(objects.size).toBe(0);
});
it('portable account export hydrates all files and never includes signed links',async()=>{
 await generate();const r=await accountExport(request('/me/export','GET',undefined,headers));expect(r.status).toBe(200);
 const payload=JSON.parse(gunzipSync(Buffer.from(await r.arrayBuffer())).toString());
 const portable=await hydrateAccountExport(payload,authorize,process.env.SUPABASE_URL,fetchStored);
 expect(portable.data.campaigns[0].files).toEqual(files);expect(JSON.stringify(portable)).not.toContain('token=');expect(portable.files_included).toBe(true);
});
it('migration dry run is read-only; conversion preserves content and revision conflicts do not overwrite edits',async()=>{
 const old=(await sb.from('campaigns').insert({user_id:user.id,name:'Old',product:'Coffee',files}).select('*').single()).data;
 expect(await migrateInlineCampaign(sb,{uid:user.id,campaignId:old.id})).toMatchObject({dry_run:true});expect(storage.upload).not.toHaveBeenCalled();
 const original=storage.upload.getMockImplementation();storage.upload.mockImplementationOnce(async(...args)=>{await sb.rpc('edit_campaign',{p_uid:user.id,p_id:old.id,p_revision:1,p_changes:{copy:'new copy'}});return original(...args);});
 expect(await migrateInlineCampaign(sb,{uid:user.id,campaignId:old.id,bucket:'private-assets',apply:true})).toMatchObject({ok:false,code:'REVISION_CONFLICT'});
 expect(await row(old.id)).toMatchObject({files,copy:'new copy',asset_bundle_id:null,revision:2});
 expect(await migrateInlineCampaign(sb,{uid:user.id,campaignId:old.id,bucket:'private-assets',apply:true})).toMatchObject({ok:true});
 const hydrated=await hydrateCampaign(await row(old.id),authorize,process.env.SUPABASE_URL,fetchStored);expect(hydrated).toMatchObject({files,revision:2,copy:'new copy'});expect((await totals()).campaigns_lifetime).toBe(0);
});
it('cleanup-claimed pending files cannot be attached, nor can a different owner claim them',async()=>{
 const old=(await sb.from('campaigns').insert({user_id:user.id,name:'Old',product:'Coffee',files}).select('*').single()).data;
 const bundle=await stageAssetBundle(sb,{uid:user.id,sourceCampaignId:old.id,sourceRevision:1,files,bucket:'private-assets'});
 const args={p_uid:user.id,p_campaign:old.id,p_revision:1,p_bundle:bundle.id};
 expect((await sb.rpc('attach_migrated_asset_bundle',{...args,p_uid:(await sb.user()).id})).data.ok).toBe(false);
 await sb.db.query("update campaign_asset_bundles set created_at=now()-interval '25 hours' where id=$1",[bundle.id]);
 await sb.rpc('claim_campaign_asset_cleanup');expect((await sb.rpc('attach_migrated_asset_bundle',args)).error).toBeTruthy();expect((await row(old.id)).files).toEqual(files);
});
it('browser refuses substituted origins, corrupt/truncated/oversized bytes and mismatched manifests',async()=>{
 const saved=await generate(),campaign=await row(saved.id),auth=await authorize('/campaigns/'+saved.id+'/assets');
 const mock=vi.fn(fetchStored);
 await expect(hydrateCampaign(campaign,async()=>({...auth,url:'https://evil.test/data'}),process.env.SUPABASE_URL,mock)).rejects.toThrow(/verification/);expect(mock).not.toHaveBeenCalled();
 for(const data of ['bad','x'.repeat(auth.bytes+1)])await expect(hydrateCampaign(campaign,async()=>auth,process.env.SUPABASE_URL,async()=>new Response(data))).rejects.toThrow(/verification/);
 const corrupt=Buffer.from(objects.values().next().value);corrupt[0]=32;
 await expect(hydrateCampaign(campaign,async()=>auth,process.env.SUPABASE_URL,async()=>new Response(corrupt))).rejects.toThrow(/verification/);
 await expect(hydrateCampaign({...campaign,files:campaign.files.map(f=>({...f,sha256:'0'.repeat(64)}))},async()=>auth,process.env.SUPABASE_URL,fetchStored)).rejects.toThrow(/verification/);
 await hydrateCampaign(campaign,async()=>auth,process.env.SUPABASE_URL,mock);expect(mock.mock.calls[0][1]).toMatchObject({credentials:'omit',redirect:'error',referrerPolicy:'no-referrer'});
});
it('browser roles cannot access bundle rows or cleanup/migration RPCs',async()=>{
 const r=await sb.db.query("select has_table_privilege('authenticated','campaign_asset_bundles','SELECT') a,has_function_privilege('anon','claim_campaign_asset_cleanup(integer)','EXECUTE') b,has_function_privilege('authenticated','attach_migrated_asset_bundle(uuid,uuid,integer,uuid)','EXECUTE') c");
 expect(r.rows[0]).toEqual({a:false,b:false,c:false});
});
it('completion rejects mismatched generation, owner, unconfirmed upload and altered manifest without consuming quota',async()=>{
 const id=randomUUID();expect((await sb.rpc('reserve_generation',{p_uid:user.id,p_id:id,p_hash:'a'.repeat(64),p_lifetime_limit:3,p_monthly_limit:null,p_daily_limit:3,p_concurrency:1})).data.ok).toBe(true);
 const bundle=await stageAssetBundle(sb,{uid:user.id,generationId:randomUUID(),files,bucket:'private-assets'});
 const args={p_uid:user.id,p_id:id,p_campaign:{product:'Coffee',files:bundle.files,asset_bundle_id:bundle.id}};
 expect((await sb.rpc('complete_generation',args)).error).toBeTruthy();
 const other=await sb.user();await sb.from('campaign_asset_bundles').update({generation_id:id,user_id:other.id}).eq('id',bundle.id);
 expect((await sb.rpc('complete_generation',args)).error).toBeTruthy();
 await sb.from('campaign_asset_bundles').update({user_id:user.id,uploaded_at:null}).eq('id',bundle.id);
 expect((await sb.rpc('complete_generation',args)).error).toBeTruthy();
 await sb.from('campaign_asset_bundles').update({uploaded_at:new Date().toISOString()}).eq('id',bundle.id);
 expect((await sb.rpc('complete_generation',{...args,p_campaign:{...args.p_campaign,files:[]}})).error).toBeTruthy();
 expect(await totals()).toMatchObject({campaigns_lifetime:0,reserved:1});
 expect((await sb.rpc('complete_generation',args)).error).toBeNull();expect((await totals()).campaigns_lifetime).toBe(1);
});
it('pending cleanup does not steal a fresh upload and expired lease tokens cannot delete a newly claimed record',async()=>{
 const bundle=await stageAssetBundle(sb,{uid:user.id,files,bucket:'private-assets'});
 expect((await sb.rpc('claim_campaign_asset_cleanup')).data).toEqual([]);
 await sb.db.query("update campaign_asset_bundles set created_at=now()-interval '25 hours' where id=$1",[bundle.id]);
 const first=(await sb.rpc('claim_campaign_asset_cleanup')).data[0];
 await sb.db.query("update campaign_asset_bundles set cleanup_until=now()-interval '1 minute' where id=$1",[bundle.id]);
 const second=(await sb.rpc('claim_campaign_asset_cleanup')).data[0];expect(first.cleanup_token).not.toBe(second.cleanup_token);
 await sb.from('campaign_asset_bundles').delete().eq('id',bundle.id).eq('cleanup_token',first.cleanup_token);
 expect((await sb.from('campaign_asset_bundles').select('id').eq('id',bundle.id)).data).toHaveLength(1);
});
it('operator recovery writes oversized legacy bytes privately without mutation or overwriting a backup',async()=>{
 const oldFiles=[{name:'oversized.svg',content:'x'.repeat(8_100_000)}];
 const old=(await sb.from('campaigns').insert({user_id:user.id,name:'Legacy',product:'Coffee',files:oldFiles}).select('id').single()).data;
 const directory=await mkdtemp(join(tmpdir(),'bf-recovery-')),path=join(directory,'recovery.json');
 try{
  await expect(migrateInlineCampaign(sb,{uid:user.id,campaignId:old.id})).rejects.toThrow(/size/);
  await expect(recoverInlineCampaign(sb,{uid:(await sb.user()).id,campaignId:old.id,path})).rejects.toThrow(/not found/);
  await recoverInlineCampaign(sb,{uid:user.id,campaignId:old.id,path});
  expect(JSON.parse(await readFile(path,'utf8')).campaign.files).toEqual(oldFiles);expect((await stat(path)).mode&0o777).toBe(0o600);
  await expect(recoverInlineCampaign(sb,{uid:user.id,campaignId:old.id,path})).rejects.toThrow();
  expect((await row(old.id)).files).toEqual(oldFiles);expect(storage.upload).not.toHaveBeenCalled();
 }finally{await rm(directory,{recursive:true,force:true});}
});
