import {admin,json} from '../sb.js';
import {serve} from '../serve.js';
import {readJson,dbCheck,HttpError} from '../http.js';
import {deliverDesktopOrder} from '../fulfillment.js';
import {rateLimit} from '../limit.js';
import {clientIp} from './campaigns.js';
async function handle(req){
 if(req.method!=='POST')return json({error:'Method not allowed'},405);
 try{
  const b=await readJson(req),email=String(b.email||'').toLowerCase().trim();
  if(!await rateLimit('desktop-resend-ip',clientIp(req),5,3600)||!await rateLimit('desktop-resend-email',email,3,86400))throw new HttpError(429,'Please wait before requesting another link.');
  if(/^txn_[a-z\d]{26}$/.test(b.order_id||'')){
   const sb=admin(),order=dbCheck(await sb.from('desktop_orders').select('transaction_id,email,status').eq('transaction_id',b.order_id).maybeSingle());
   if(order?.email===email&&order.status==='paid'){
    dbCheck(await sb.rpc('request_desktop_redelivery',{p_id:order.transaction_id}));
    try{await deliverDesktopOrder(sb,order.transaction_id);}catch{/* durable retry queue; never reveal order existence */}
   }
  }
  return json({ok:true,message:'If this is a matching paid order, a link will be sent to its purchase email. Links are reissued at most once per day.'});
 }catch(e){return json({error:e.status?e.message:'Please try later.'},e.status||503);}
}
const h=serve(handle);export default h;export const POST=h;
