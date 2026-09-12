import {loadStoredFiles,stageAssetBundle} from '../assets.js';
import {createHash} from 'node:crypto';
import {admin,authUser,json} from '../sb.js';
import {serve} from '../serve.js';
import {readJson,UUID,dbCheck,HttpError} from '../http.js';
import {rateLimit} from '../limit.js';
import {resolveVisualPlan} from '../visual-plan.js';
import {reserveOperatorBudget} from '../cost.js';
import {generateScene} from '../visuals_ai.js';
import {bannerSvg} from '../visuals.js';
import {assertCampaignPayload} from '../payload.js';
async function handle(req,ctx){
 const user=await authUser(req);if(!user)return json({error:'Not signed in'},401);
 let job=null;const sb=admin({signal:AbortSignal.timeout(52000)});
 try{
  const id=ctx?.params?.id;if(!UUID.test(id||''))throw new HttpError(404,'Campaign not found');
  if(req.method==='GET')return json({jobs:dbCheck(await sb.from('campaign_image_jobs').select('id,source_revision,result_revision,status,failure_code,expires_at,created_at').eq('campaign_id',id).eq('user_id',user.id).order('created_at',{ascending:false}).limit(10))});
  if(req.method!=='POST')throw new HttpError(405,'Method not allowed');
  const b=await readJson(req,3000);
  if(!UUID.test(b.request_id||'')||!Number.isInteger(b.revision)||b.consent!==true||typeof b.provider!=='string')throw new HttpError(400,'Confirm image-provider sharing and the current version.');
  if(!await rateLimit('image-recovery',user.id,15,3600))throw new HttpError(429,'Recovery safety limit reached');
  const hash=createHash('sha256').update(JSON.stringify({id,revision:b.revision,provider:b.provider,consent:true})).digest('hex');
  // A successful lost response remains replayable after provider configuration changes.
  const prior=dbCheck(await sb.from('campaign_image_jobs').select('campaign_id,request_hash,status,result_revision,expires_at').eq('user_id',user.id).eq('request_id',b.request_id).maybeSingle());
  if(prior){if(prior.request_hash!==hash||prior.campaign_id!==id)throw new HttpError(409,'Request ID belongs to a different recovery.','REQUEST_CONFLICT');if(prior.status==='completed')return json({ok:true,id,revision:prior.result_revision,replayed:true});throw new HttpError(409,prior.status==='running'&&Date.parse(prior.expires_at)>Date.now()?'Recovery is still running. Check recovery status.':'Previous recovery did not complete. Start a new recovery request after checking history.',prior.status==='running'&&Date.parse(prior.expires_at)>Date.now()?'RUNNING':'PREVIOUS_FAILED');}
  if(process.env.IMAGE_RECOVERY_ENABLED!=='true'||process.env.GENERATION_PAUSED==='true')throw new HttpError(503,'Image-only recovery is not enabled. Your current pack is unchanged.','RECOVERY_DISABLED');
  const c=dbCheck(await sb.from('campaigns').select('*').eq('id',id).eq('user_id',user.id).maybeSingle());if(!c)throw new HttpError(404,'Campaign not found');
  if(!Array.isArray(c.files)||!c.files.some(f=>f.name==='hero_banner.svg')||!c.visual_recipe?.common||!c.visual_fields)throw new HttpError(409,'This saved pack does not have a supported recovery recipe.','RECOVERY_UNSUPPORTED');
  const original=await loadStoredFiles(sb,user.id,c);
  const visualPlan=resolveVisualPlan({provider:'auto',visuals_ai:true,visual_provider:b.provider});
  if(!visualPlan.enabled)throw new HttpError(503,'Image provider unavailable.','VISUALS_UNAVAILABLE');
  const claim=dbCheck(await sb.rpc('claim_image_recovery',{p_uid:user.id,p_id:id,p_revision:b.revision,p_request:b.request_id,p_hash:hash}));
  if(!claim.ok)throw new HttpError(409,'Recovery not started: '+claim.code,claim.code);
  job=claim.job_id;
  await reserveOperatorBudget(sb,job,{key_source:'offline'},visualPlan);
  const common=c.visual_recipe.common;
  // Explicit whitelist, never the stored brief, photo, logo, copy or keys.
  const input={product:c.product,industry:c.industry,audience:c.audience,tone:c.brief?.tone||'',primary:common.primary,secondary:common.secondary};
  const g=await generateScene(input,{key:visualPlan.key,provider:visualPlan.provider,model:visualPlan.model,timeoutMs:25000});
  const status={mode:'ai',state:'generated',provider:g.provider,model:g.model,generated_at:new Date().toISOString(),scope:'hero_only'};
  const files=original.files.map(f=>f.name==='hero_banner.svg'?{name:f.name,content:bannerSvg({...common,...c.visual_fields,width:1200,height:630,explicitVisualFields:true,scene:`data:${g.mime};base64,${g.data}`})}:f.name==='brand_guidelines.md'?{...f,content:f.content+`\n\nRecovered hero artwork: ${g.provider} / ${g.model}, ${status.generated_at}. Resized banners remain unchanged. Review input, likeness, trademark and advertising rights. No exclusivity or commercial-rights guarantee.\n`}:f);
  let payload={files,recipe:{...c.visual_recipe,schema:2,scene_sha256:createHash('sha256').update(`data:${g.mime};base64,${g.data}`).digest('hex')},fields:c.visual_fields,report:c.visual_field_report,status};
  if(original.bucket){const staged=await stageAssetBundle(sb,{uid:user.id,sourceCampaignId:id,sourceRevision:c.revision,files,bucket:original.bucket});payload={...payload,files:staged.files,bundle_id:staged.id};}
  assertCampaignPayload(payload);assertCampaignPayload({...c,files:payload.files,visual_status:status});
  const saved=dbCheck(await sb.rpc('finish_image_recovery',{p_uid:user.id,p_job:job,p_payload:payload}));if(!saved.ok)throw new HttpError(409,'The campaign changed or the recovery expired; current files were not replaced.',saved.code);
  job=null;return json({...saved,notice:'Hero recovered. Copy and resized banners were not regenerated. No campaign allowance consumed. Review the new version before exporting.'});
 }catch(e){
  if(job)try{dbCheck(await admin().from('campaign_image_jobs').update({status:'failed',failure_code:e.code||'RECOVERY_FAILED'}).eq('id',job).eq('user_id',user.id).eq('status','running'));}catch{ /* lease expires; a completed save is never marked failed */ }
  return json({error:e.status?e.message:'Image recovery could not be confirmed. Check status, then retry the unchanged request.',code:e.code||'RECOVERY_FAILED'},e.status||503);
 }
}
export default serve(handle);
