import {admin,authUser,json} from '../sb.js';
import {serve} from '../serve.js';
import {UUID,dbCheck} from '../http.js';
import {rateLimit} from '../limit.js';
async function handle(req){
 if(req.method!=='GET')return json({error:'Method not allowed'},405);
 const user=await authUser(req);if(!user)return json({error:'Not authorized'},401);
 const id=new URL(req.url).searchParams.get('request_id')||'';if(!UUID.test(id))return json({error:'Request ID must be a UUID'},400);
 try{
  if(!await rateLimit('progress',user.id,180,60))return json({error:'Progress polling limit reached'},429);
  const row=dbCheck(await admin().from('generation_usage').select('id,status,campaign_id,progress,failure_code').eq('id',id).eq('user_id',user.id).maybeSingle());
  if(!row)return json({error:'Request not found'},404);
  return json({request_id:row.id,status:row.status,campaign_id:row.campaign_id,stages:row.progress||{},failure_code:row.failure_code||null});
 }catch{return json({error:'Progress temporarily unavailable; generation may still be running'},503);}
}
const handler=serve(handle);export default handler;export const GET=handler;
