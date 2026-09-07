import {admin,authUser,json} from '../sb.js';
import {serve} from '../serve.js';
import {readJson,clean,UUID,HttpError,dbCheck} from '../http.js';
import {rateLimit} from '../limit.js';
async function handle(req){
 if(req.method!=='POST')return json({error:'Method not allowed'},405);
 const user=await authUser(req);if(!user)return json({error:'Not signed in'},401);
 try{
  if(!await rateLimit('feedback',user.id,10,86400))throw new HttpError(429,'Feedback limit reached.');
  const b=await readJson(req);if(typeof b.usable!=='boolean')throw new HttpError(400,'Choose whether the pack was usable.');
  const sb=admin();if(b.campaign_id){const own=dbCheck(await sb.from('campaigns').select('id').eq('id',UUID.test(b.campaign_id)?b.campaign_id:'00000000-0000-4000-8000-000000000000').eq('user_id',user.id).maybeSingle());if(!own)throw new HttpError(404,'Campaign not found');}
  dbCheck(await sb.from('product_feedback').insert({user_id:user.id,campaign_id:b.campaign_id||null,usable:b.usable,minutes_saved:Number.isInteger(b.minutes_saved)?Math.max(0,Math.min(600,b.minutes_saved)):null,note:clean(b.note,1000)}));
  return json({ok:true});
 }catch(e){return json({error:e.status?e.message:'Could not save feedback.'},e.status||503);}
}
const h=serve(handle);export default h;export const POST=h;
