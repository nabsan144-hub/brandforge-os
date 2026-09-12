import {requireVisualReviewClient} from './visual-review.js';
// Private immutable file bundles. No customer content travels through a large
// Vercel response: only metadata and owner-authorized, short-lived signed URLs.
import {randomUUID,createHash} from 'node:crypto';
import {HttpError,dbCheck} from './http.js';
export const MAX_ASSET_BUNDLE_BYTES=20_000_000;
export const MAX_ASSET_FILE_BYTES=8_000_000;
export const ASSET_CLIENT='asset-bundle-v1';
export const storageEnabled=()=>process.env.CAMPAIGN_ASSETS_ENABLED==='true';
export function requireAssetClient(req){
 if(req.headers?.get?.('x-brandforge-client')!==ASSET_CLIENT)throw new HttpError(409,'Reload BrandForge to use the updated private-file viewer and exports.','CLIENT_UPDATE_REQUIRED');
}
export async function privateBucket(sb,bucket){
 if(!/^[a-zA-Z0-9_-]{1,100}$/.test(bucket||''))throw new HttpError(503,'Private campaign storage needs configuration.','ASSET_STORAGE_UNAVAILABLE');
 const meta=dbCheck(await sb.storage.getBucket(bucket),'Private campaign storage is unavailable.');
 if(!meta || meta.public!==false)throw new HttpError(503,'Campaign storage must be private.','ASSET_BUCKET_PUBLIC');
 return bucket;
}
export async function prepareAssetStorage(sb,req){
 if(!storageEnabled())return null;
 requireAssetClient(req);
 return privateBucket(sb,process.env.CAMPAIGN_ASSET_BUCKET);
}
const digest=bytes=>createHash('sha256').update(bytes).digest('hex');
export function encodeAssetBundle(files){
 if(!Array.isArray(files)||!files.length||files.length>64)throw new HttpError(413,'Unsupported file bundle.','ASSET_BUNDLE_LIMIT');
 const seen=new Set(),manifest=[];
 for(const file of files){
  if(!file || !/^[\p{L}\p{N}][\p{L}\p{N}._-]{0,119}$/u.test(file.name||'')||seen.has(file.name)||typeof file.content!=='string'||(file.encoding!==undefined&&file.encoding!=='base64'))throw new HttpError(413,'Invalid generated file bundle.','ASSET_BUNDLE_INVALID');
  seen.add(file.name);
  if(file.encoding==='base64'&&(!/^[A-Za-z0-9+/]*={0,2}$/.test(file.content)||file.content.length%4))throw new HttpError(413,'Invalid generated file encoding.','ASSET_BUNDLE_INVALID');
  const bytes=Buffer.from(file.content,file.encoding==='base64'?'base64':'utf8');
  if(bytes.length>MAX_ASSET_FILE_BYTES)throw new HttpError(413,'A generated file exceeds the supported size.','ASSET_FILE_LIMIT');
  manifest.push({name:file.name,encoding:file.encoding||'utf8',bytes:bytes.length,sha256:digest(bytes),storage:'bundle'});
 }
 const data=Buffer.from(JSON.stringify({schema:1,files}));
 if(data.length>MAX_ASSET_BUNDLE_BYTES)throw new HttpError(413,'The campaign files exceed the supported bundle size.','ASSET_BUNDLE_LIMIT');
 return {data,manifest,sha256:digest(data)};
}
export async function stageAssetBundle(sb,{uid,generationId=null,sourceCampaignId=null,sourceRevision=null,files,bucket}){
 const pack=encodeAssetBundle(files),id=randomUUID(),path=`campaigns/${id}.json`;
 // Durable row BEFORE upload: failed/uncertain uploads are later collected.
 dbCheck(await sb.from('campaign_asset_bundles').insert({id,user_id:uid,generation_id:generationId,source_campaign_id:sourceCampaignId,source_revision:sourceRevision,bucket,object_path:path,bytes:pack.data.length,sha256:pack.sha256,file_manifest:pack.manifest}),'Could not reserve private file storage.');
 dbCheck(await sb.storage.from(bucket).upload(path,pack.data,{contentType:'application/json',cacheControl:'0',upsert:false}),'Private file upload failed. No campaign allowance was consumed.');
 dbCheck(await sb.from('campaign_asset_bundles').update({uploaded_at:new Date().toISOString()}).eq('id',id),'Could not confirm private file upload.');
 return {id,files:pack.manifest};
}
export async function externalizeCampaign(sb,uid,generationId,campaign,bucket){
 if(!bucket)return campaign;
 const bundle=await stageAssetBundle(sb,{uid,generationId,files:campaign.files,bucket});
 return {...campaign,files:bundle.files,asset_bundle_id:bundle.id};
}
export async function authorizeBundle(sb,uid,campaignId,req,expected={}){
 const campaign=dbCheck(await sb.from('campaigns').select('id,revision,asset_bundle_id,visual_review_state,visual_version_id').eq('id',campaignId).eq('user_id',uid).maybeSingle());
 if(expected.revision!==undefined&&(campaign?.revision!==expected.revision||campaign?.asset_bundle_id!==expected.bundle))throw new HttpError(404,'This shared version is no longer available.');
 if(campaign)requireVisualReviewClient(req,campaign);
 if(!campaign?.asset_bundle_id)throw new HttpError(404,'Private files not found.');
 const row=dbCheck(await sb.from('campaign_asset_bundles').select('*').eq('id',campaign.asset_bundle_id).eq('campaign_id',campaignId).eq('user_id',uid).eq('state','attached').maybeSingle());
 if(!row)throw new HttpError(404,'Private files not found.');
 // Recheck frozen bucket privacy, including after environment changes.
 await privateBucket(sb,row.bucket);
 const result=dbCheck(await sb.storage.from(row.bucket).createSignedUrl(row.object_path,60),'Private files are temporarily unavailable.');
 const url=new URL(result?.signedUrl||'');
 const expectedOrigin=new URL(process.env.SUPABASE_URL);
 if(url.protocol!=='https:'||url.origin!==expectedOrigin.origin||url.username||url.password)throw new HttpError(503,'Invalid storage download origin.','ASSET_STORAGE_UNAVAILABLE');
 return {url:url.href,expires_in:60,bytes:row.bytes,sha256:row.sha256,schema:1};
}
export async function collectAssetGarbage(sb){
 const rows=dbCheck(await sb.rpc('claim_campaign_asset_cleanup',{p_limit:25}))||[];
 const groups=new Map();for(const row of rows){if(!groups.has(row.bucket))groups.set(row.bucket,[]);groups.get(row.bucket).push(row);}
 let removed=0,failed=0;
 for(const [bucket,items] of groups){
  try{
   if(items.some(x=>!/^campaigns\/[0-9a-f-]{36}\.json$/.test(x.object_path)))throw new Error('Unexpected object path');
   // Deletion is allowed even if a historical bucket has become public.
   dbCheck(await sb.storage.from(bucket).remove(items.map(x=>x.object_path)));
   for(const item of items){
    dbCheck(await sb.from('campaign_asset_bundles').delete().eq('id',item.id).eq('state','deleting').eq('cleanup_token',item.cleanup_token));removed++;
   }
  }catch{failed+=items.length;} // durable lease expires; next maintenance retries
 }
 return {claimed:rows.length,removed,failed,batch_full:rows.length===25};
}

// Server-side hydration for no-provider corrections. Bound before decoding and
// verify both immutable bundle bytes and individual file manifests.
export async function loadStoredFiles(sb,uid,campaign){
 if(!campaign.asset_bundle_id)return {files:campaign.files,bucket:null};
 const row=dbCheck(await sb.from('campaign_asset_bundles').select('*').eq('id',campaign.asset_bundle_id).eq('campaign_id',campaign.id).eq('user_id',uid).eq('state','attached').maybeSingle());
 if(!row)throw new HttpError(404,'Original private files are unavailable.');
 await privateBucket(sb,row.bucket);
 const blob=dbCheck(await sb.storage.from(row.bucket).download(row.object_path));
 if(!blob||blob.size!==row.bytes||blob.size>MAX_ASSET_BUNDLE_BYTES)throw new HttpError(409,'Private file size verification failed.');
 const bytes=Buffer.from(await blob.arrayBuffer());if(digest(bytes)!==row.sha256)throw new HttpError(409,'Private file checksum verification failed.');
 let data;try{data=JSON.parse(bytes.toString('utf8'));}catch{throw new HttpError(409,'Invalid private bundle.');}
 if(data.schema!==1)throw new HttpError(409,'Unsupported private bundle.');
 const checked=encodeAssetBundle(data.files),manifests=[row.file_manifest,campaign.files];
 for(const manifest of manifests)if(!Array.isArray(manifest)||manifest.length!==checked.manifest.length||checked.manifest.some((f,i)=>['name','encoding','bytes','sha256','storage'].some(k=>f[k]!==manifest[i][k])))throw new HttpError(409,'Private file manifest verification failed.');
 return {files:data.files,bucket:row.bucket};
}
