// Preview and update the EXISTING subscription. Never opens a new checkout.
import {admin,authUser,json} from '../sb.js';
import {serve} from '../serve.js';
import {readJson,HttpError,dbCheck} from '../http.js';
import {requireCheckout,verifyCatalogPrice,catalog,withBillingLock,profileFor,reconcileSubscriptions,billable,paddle,seal,unseal,syncSubscription} from '../commerce.js';
import {rateLimit} from '../limit.js';
const totals=t=>t?.details?.totals||t?.totals||null;
async function handle(req){
 if(req.method!=='POST')return json({error:'Method not allowed'},405);
 const user=await authUser(req);if(!user)return json({error:'Not signed in'},401);
 const sb=admin();
 try{
  requireCheckout();const body=await readJson(req);
  if(!await rateLimit('plan-change',user.id,20,3600))throw new HttpError(429,'Too many plan-change requests.');
  const result=await withBillingLock(sb,user.id,async()=>{
   const profile=await profileFor(sb,user.id);if(profile.deletion_pending)throw new HttpError(409,'Account deletion is pending.');
   const active=(await reconcileSubscriptions(sb,user.id,profile)).filter(billable);
   if(active.length!==1)throw new HttpError(409,active.length?'Multiple subscriptions need support review. No additional payment was started.':'No active subscription. Start a new subscription from Billing.');
   const sub=active[0];
   if(sub.status==='past_due'||sub.status==='paused'||sub.scheduled_change)throw new HttpError(409,'Resolve the payment, pause or scheduled cancellation in the portal before changing plans.');
   const choice=catalog().find(c=>c.plan===body.plan&&c.interval===(body.interval||'month')&&c.interval!=='once'&&c.price);
   if(!choice)throw new HttpError(400,'That plan or billing interval is unavailable.');
   await verifyCatalogPrice(choice);
   if(sub.items?.length!==1)throw new HttpError(409,'This subscription has extra items; contact support to change it without removing them.');
   if((sub.items[0].price?.id||sub.items[0].price_id)===choice.price)throw new HttpError(409,'You already have this plan and billing interval.');
   const patch={items:[{price_id:choice.price,quantity:1}],proration_billing_mode:'prorated_immediately',on_payment_failure:'prevent_change'};
   const preview=(await paddle('/subscriptions/'+sub.id+'/preview',patch,'PATCH')).data;
   const summary={currency:preview.currency_code||sub.currency_code,immediate:totals(preview.immediate_transaction),next:totals(preview.next_transaction),recurring:preview.recurring_transaction_details,next_billed_at:preview.next_billed_at};
   const due=summary.immediate?Number(summary.immediate.balance??summary.immediate.grand_total??summary.immediate.total):0;
   if(!Number.isFinite(due) || (preview.immediate_transaction&&!summary.immediate))throw new HttpError(503,'Could not confirm the amount. No plan change was submitted.');
   const usage=dbCheck(await sb.rpc('generation_totals',{p_uid:user.id}));
   const usageNote=` Completed usage carries across plans: ${usage.campaigns_this_month} used this UTC month; ${Math.max(0,(choice.plan==='agency'?300:50)-usage.campaigns_this_month)} remain on the selected plan.`;
   if(!body.confirmation){
    return {preview:summary,confirmation:seal({purpose:'plan-change',uid:user.id,sub:sub.id,price:choice.price,updated:sub.updated_at,max_due:Math.max(0,due),currency:summary.currency,exp:Date.now()+5*60000}),notice:'Paddle will prorate immediately. The final amount can change slightly with elapsed time. A failed payment prevents the plan change.'+usageNote};
   }
   const proof=unseal(body.confirmation);
   if(!proof||proof.purpose!=='plan-change'||proof.uid!==user.id||proof.sub!==sub.id||proof.price!==choice.price||proof.updated!==sub.updated_at)throw new HttpError(409,'Your preview expired or billing changed. Preview again before confirming.');
   if(due>proof.max_due||summary.currency!==proof.currency)throw new HttpError(409,'The prorated amount changed. Preview again before confirming.','AMOUNT_CHANGED');
   const changed=(await paddle('/subscriptions/'+sub.id,patch,'PATCH')).data;
   await syncSubscription(sb,user.id,changed);
   return {ok:true,subscription_id:changed.id,status:changed.status};
  });
  return json(result);
 }catch(e){return json({error:e.status?e.message:'Could not change the subscription.',code:e.code},e.status||503);}
}
const h=serve(handle);export default h;export const POST=h;
