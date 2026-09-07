import {verifyPrivateDesktopRelease} from '../fulfillment.js';
import {admin,json} from '../sb.js';
import {serve} from '../serve.js';
import {readJson,HttpError} from '../http.js';
import {requireCheckout,verifyCatalogPrice,catalog,paddle,publicCors} from '../commerce.js';
import {clientIp} from './campaigns.js';
import {rateLimit} from '../limit.js';
async function handle(req){
 if(req.method==='OPTIONS')return publicCors(req,new Response(null,{status:204}));
 let response;
 try{
  if(req.method!=='POST')throw new HttpError(405,'Method not allowed');
  requireCheckout('desktop');const b=await readJson(req);
  const c=catalog().find(x=>x.plan===b.tier&&x.interval==='once'&&x.price);if(!c)throw new HttpError(400,'Unknown desktop edition.');
  if(!await rateLimit('desktop-checkout-ip',clientIp(req),10,3600))throw new HttpError(429,'Too many checkout attempts. Try later.');
  await verifyCatalogPrice(c);
  await verifyPrivateDesktopRelease(admin());
  const t=(await paddle('/transactions',{items:[{price_id:c.price,quantity:1}],collection_mode:'automatic',custom_data:{product:'desktop',edition:c.plan}})).data;
  if(!/^txn_[a-z\d]{26}$/.test(t?.id))throw new HttpError(503,'Checkout was not confirmed.');
  response=json({transaction_id:t.id});
 }catch(e){response=json({error:e.status?e.message:'Checkout is unavailable.',code:e.code},e.status||503);}
 return publicCors(req,response);
}
const h=serve(handle);export default h;export const POST=h;export const OPTIONS=h;
