import {admin,authUser,json} from '../sb.js';
import {serve} from '../serve.js';
import {readJson,dbCheck,HttpError} from '../http.js';
import {requireCheckout,verifyCatalogPrice,catalog,withBillingLock,profileFor,ensureCustomer,reconcileSubscriptions,billable,paddle,checkoutProof} from '../commerce.js';
import {rateLimit} from '../limit.js';
async function handle(req){
 if(req.method!=='POST')return json({error:'Method not allowed'},405);
 const user=await authUser(req);if(!user)return json({error:'Not signed in'},401);
 const sb=admin();
 try{
  requireCheckout();const body=await readJson(req);
  const choice=catalog().find(c=>c.plan===body.plan&&c.interval===(body.interval||'month')&&c.interval!=='once'&&c.price);
  if(!choice)throw new HttpError(400,'That Cloud plan or billing interval is unavailable.');
  await verifyCatalogPrice(choice);
  if(!await rateLimit('checkout',user.id,15,3600))throw new HttpError(429,'Too many checkout requests. Try later.');
  const result=await withBillingLock(sb,user.id,async()=>{
   const profile=await profileFor(sb,user.id);if(profile.deletion_pending)throw new HttpError(409,'Account deletion is pending.');
   const customerId=await ensureCustomer(sb,user,profile);
   const active=(await reconcileSubscriptions(sb,user.id,{...profile,paddle_customer_id:customerId})).filter(billable);
   if(active.length)throw new HttpError(409,'You already have a subscription. Use Change plan or Manage billing, not a new checkout.','SUBSCRIPTION_EXISTS');
   const intent=dbCheck(await sb.rpc('begin_checkout',{p_uid:user.id,p_plan:choice.plan,p_interval:choice.interval}));
   if(!intent.ok){
    if(intent.code==='CHECKOUT_PENDING'&&intent.transaction_id){
     const txn=(await paddle('/transactions/'+encodeURIComponent(intent.transaction_id))).data;
     if(['draft','ready'].includes(txn?.status))return {transaction_id:txn.id,reused:true};
     throw new HttpError(409,'A prior checkout has been paid or closed. Refresh Billing; do not pay again.','CHECKOUT_RECONCILE');
    }
    throw new HttpError(409,'A previous checkout is open or needs reconciliation. Resume or cancel it in Billing before choosing another plan.',intent.code);
   }
   try{
    const txn=(await paddle('/transactions',{items:[{price_id:choice.price,quantity:1}],customer_id:customerId,collection_mode:'automatic',custom_data:{bf_proof:checkoutProof(user.id,intent.id),bf_intent:intent.id}})).data;
    if(!/^txn_[a-z\d]{26}$/.test(txn?.id))throw new HttpError(503,'Checkout was not confirmed.','BILLING_UNCERTAIN');
    dbCheck(await sb.from('checkout_intents').update({transaction_id:txn.id,state:'open'}).eq('id',intent.id));
    return {transaction_id:txn.id};
   }catch(e){
    // Do not create another transaction after an ambiguous provider timeout.
    await sb.from('checkout_intents').update({state:'uncertain'}).eq('id',intent.id);
    throw e;
   }
  });
  return json(result);
 }catch(e){return json({error:e.status?e.message:'Checkout is unavailable.',code:e.code},e.status||503);}
}
const h=serve(handle);export default h;export const POST=h;
