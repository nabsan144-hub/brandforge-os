import {admin,authUser,json} from '../sb.js';
import {serve} from '../serve.js';
import {profileFor,paddle,requireCustomerOwnership} from '../commerce.js';
import {HttpError} from '../http.js';
import {rateLimit} from '../limit.js';
async function handle(req){
 if(req.method!=='POST')return json({error:'Method not allowed'},405);
 const user=await authUser(req);if(!user)return json({error:'Not signed in'},401);
 try{
  if(!await rateLimit('portal',user.id,30,3600))throw new HttpError(429,'Too many portal requests.');
  const sb=admin(),p=await profileFor(sb,user.id);if(!p.paddle_customer_id)throw new HttpError(404,'No billing customer yet.');
  await requireCustomerOwnership(sb,user.id,p.paddle_customer_id);
  const result=(await paddle('/customers/'+encodeURIComponent(p.paddle_customer_id)+'/portal-sessions',{})).data;
  const url=result?.urls?.general?.overview;
  if(!url||new URL(url).protocol!=='https:'||!/(^|\.)paddle\.com$/.test(new URL(url).hostname))throw new HttpError(503,'Could not create a secure billing portal link.');
  return json({url}); // ephemeral; never save this tokenized URL in the DB
 }catch(e){return json({error:e.status?e.message:'Billing portal is unavailable.'},e.status||503);}
}
const h=serve(handle);export default h;export const POST=h;
