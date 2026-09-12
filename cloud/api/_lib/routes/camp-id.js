import {requireVisualReviewClient} from '../visual-review.js';
import {requireAssetClient} from '../assets.js';
import {admin,authUser,json} from '../sb.js';
import {serve} from '../serve.js';
import {readJson,clean,dbCheck,HttpError,UUID} from '../http.js';
import {boundedJson} from '../payload.js';
import {rateLimit} from '../limit.js';
async function handle(req,ctx){
 const user=await authUser(req);if(!user)return json({error:'Not signed in'},401);
 const id=ctx?.params?.id||new URL(req.url,'https://brandforge.local').pathname.split('/').pop();
 if(!UUID.test(id||''))return json({error:'Campaign not found'},404);
 const sb=admin();
 try{
  if(!req.method||req.method==='GET'){
   const row=dbCheck(await sb.from('campaigns').select('*').eq('id',id).eq('user_id',user.id).maybeSingle());
   if(!row)throw new HttpError(404,'Campaign not found');
   requireVisualReviewClient(req,row);
   if(row.asset_bundle_id)requireAssetClient(req);
   const revisions=dbCheck(await sb.from('campaign_revisions').select('revision,created_at').eq('campaign_id',id).eq('user_id',user.id).order('revision',{ascending:false}))||[];
   return boundedJson({...row,revisions});
  }
  if(req.method==='DELETE'){
   // FK SET NULL preserves immutable usage; no quota RPC is called.
   dbCheck(await sb.from('campaigns').delete().eq('id',id).eq('user_id',user.id));
   return json({ok:true,note:'Content deleted. Completed generation usage is not refunded.'});
  }
  if(req.method==='PATCH'){
   if(!await rateLimit('campaign-edit',user.id,100,86400))throw new HttpError(429,'Daily edit safety limit reached.');
   const b=await readJson(req,100000),changes={};
   if(!Number.isInteger(b.revision)||b.revision<1)throw new HttpError(400,'Include the version you edited.');
   if(b.acknowledge_visuals===true){
    if(['name','strategy','copy','seo','restore_revision'].some(k=>Object.hasOwn(b,k)))throw new HttpError(400,'Review acknowledgment must be a separate action.');
    const current=dbCheck(await sb.from('campaigns').select('visual_version_id,visual_review_state').eq('id',id).eq('user_id',user.id).maybeSingle());
    if(!current)throw new HttpError(404,'Campaign not found');
    requireVisualReviewClient(req,current);
    const r=dbCheck(await sb.rpc('acknowledge_visual_review',{p_uid:user.id,p_id:id,p_revision:b.revision}));
    if(!r.ok)throw new HttpError(r.code==='NOT_FOUND'?404:409,r.code==='NOT_FOUND'?'Campaign not found':'A newer version was saved. Reload and review it before acknowledging.',r.code);
    return json(r);
   }
   if(b.restore_revision){
    const row=dbCheck(await sb.from('campaign_revisions').select('snapshot').eq('campaign_id',id).eq('user_id',user.id).eq('revision',Number(b.restore_revision)).maybeSingle());
    if(!row)throw new HttpError(404,'That saved revision is no longer available.');
    if(row.snapshot.visual_version_id){
     requireVisualReviewClient(req,row.snapshot);
     const result=dbCheck(await sb.rpc('restore_vector_revision',{p_uid:user.id,p_id:id,p_revision:b.revision,p_restore:Number(b.restore_revision)}));
     if(!result.ok)throw new HttpError(result.code==='NOT_FOUND'?404:409,'This visual version could not be restored. Reload before retrying.',result.code);
     return json(result);
    }
    for(const k of ['name','strategy','copy','seo'])changes[k]=row.snapshot[k]||'';
   }else{
    for(const k of ['name','strategy','copy','seo'])if(Object.hasOwn(b,k)){
     if(typeof b[k]!=='string'||b[k].length>(k==='name'?80:20000))throw new HttpError(400,'Text exceeds the supported edit limit.');
     changes[k]=k==='name'?clean(b[k],80):b[k].replace(/\u0000/g,'');
    }
   }
   if(!Object.keys(changes).length)throw new HttpError(400,'No changes supplied.');
   const r=dbCheck(await sb.rpc('edit_campaign',{p_uid:user.id,p_id:id,p_revision:b.revision,p_changes:changes}));
   if(!r.ok)throw new HttpError(r.code==='NOT_FOUND'?404:409,r.code==='NOT_FOUND'?'Campaign not found':'A newer version was saved. Reload before editing again.',r.code);
   return json(r);
  }
  return json({error:'Method not allowed'},405);
 }catch(e){return json({error:e.status?e.message:'Could not update campaign.',code:e.code},e.status||503);}
}
const h=serve(handle);export default h;export const GET=h;export const DELETE=h;export const PATCH=h;
