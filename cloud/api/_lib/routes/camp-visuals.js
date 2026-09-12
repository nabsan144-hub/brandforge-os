import {createHash} from 'node:crypto';
import {loadStoredFiles,stageAssetBundle} from '../assets.js';
import {admin,authUser,json} from '../sb.js';
import {serve} from '../serve.js';
import {UUID,readJson,HttpError,dbCheck} from '../http.js';
import {rateLimit} from '../limit.js';
import {correctionFields,redrawVectors,correctionLayout,normalizeCorrectionLayout} from '../vector-corrections.js';
import {assertCampaignPayload} from '../payload.js';
async function handle(req,ctx){
 if(req.method!=='POST')return json({error:'Method not allowed'},405);
 const user=await authUser(req);if(!user)return json({error:'Not signed in'},401);
 try{
  const id=ctx?.params?.id||new URL(req.url).pathname.split('/').at(-2);
  if(!UUID.test(id||''))throw new HttpError(404,'Campaign not found');
  const b=await readJson(req,750000);
  if(Object.keys(b).some(k=>!['revision','request_id','visual_fields','visual_layout'].includes(k))||!UUID.test(b.request_id||'')||!Number.isInteger(b.revision)||b.revision<1)throw new HttpError(400,'Include the expected version, request ID and supported visual fields only.');
  const fields=correctionFields(b.visual_fields),sb=admin();
  const c=dbCheck(await sb.from('campaigns').select('*').eq('id',id).eq('user_id',user.id).maybeSingle());if(!c)throw new HttpError(404,'Campaign not found');
  const layout=correctionLayout(b.visual_layout||{},c),changeHash=createHash('sha256').update(JSON.stringify({fields,layout})).digest('hex');
  const prior=dbCheck(await sb.from('campaign_visual_versions').select('campaign_id,source_revision,result_revision,payload').eq('user_id',user.id).eq('request_id',b.request_id).maybeSingle());
  if(prior){
   if(prior.campaign_id!==id||prior.source_revision!==b.revision||(prior.payload.change_hash?prior.payload.change_hash!==changeHash:Object.keys(layout).length>0)||Object.entries(fields).some(([k,v])=>prior.payload.fields[k]!==v))throw new HttpError(409,'This request ID belongs to different corrections.','IDEMPOTENCY_CONFLICT');
   return json({ok:true,id,revision:prior.result_revision,replayed:true});
  }
  if(process.env.VECTOR_CORRECTIONS_ENABLED!=='true')throw new HttpError(503,'Saved visual corrections are not enabled on this deployment. Your files are unchanged.','VISUAL_CORRECTIONS_DISABLED');
  if(c.revision!==b.revision)throw new HttpError(409,'A newer version exists. Reload before correcting visuals.','REVISION_CONFLICT');
  if(!await rateLimit('visual-correction',user.id,60,3600))throw new HttpError(429,'Visual correction safety limit reached. Retry later.');
  const original=await loadStoredFiles(sb,user.id,c);
  let payload=redrawVectors({...c,asset_bundle_id:null,files:original.files},fields,await normalizeCorrectionLayout(layout));
  payload.change_hash=changeHash;payload.status=c.visual_status;
  if(original.bucket){const staged=await stageAssetBundle(sb,{uid:user.id,sourceCampaignId:id,sourceRevision:c.revision,files:payload.files,bucket:original.bucket});payload={...payload,files:staged.files,bundle_id:staged.id,status:c.visual_status};}
  assertCampaignPayload(payload);
  assertCampaignPayload({...c,visual_recipe:payload.recipe,files:payload.files,visual_fields:fields,visual_field_report:payload.report});
  const result=dbCheck(await sb.rpc('save_vector_correction',{p_uid:user.id,p_id:id,p_revision:b.revision,p_request:b.request_id,p_payload:payload}));
  if(!result.ok)throw new HttpError(result.code==='NOT_FOUND'?404:409,'Corrections were not saved. Reload and review the current version.',result.code);
  return json(result);
 }catch(e){return json({error:e.status?e.message:'The correction save could not be confirmed. Retry the same correction request before editing again.',code:e.code},e.status||503);}
}
const h=serve(handle);export default h;export const POST=h;
