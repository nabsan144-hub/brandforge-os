// Billing must be reconciled BEFORE destroying the identity that owns it.
import {dbCheck,HttpError} from './http.js';
import {withBillingLock,profileFor,reconcileSubscriptions,billable,paddle,catalog,syncSubscription,reconcileCheckoutIntent} from './commerce.js';
export async function closePendingCheckouts(sb,uid){
 const rows=dbCheck(await sb.from('checkout_intents').select('*').eq('user_id',uid).in('state',['creating','open','uncertain']))||[];
 for(let row of rows){
  if(!row.transaction_id)row=await reconcileCheckoutIntent(sb,uid,row);
  let t=(await paddle('/transactions/'+encodeURIComponent(row.transaction_id))).data;
  if(!t)throw new HttpError(503,'Could not confirm the pending checkout.');
  if(['draft','ready'].includes(t.status))t=(await paddle('/transactions/'+t.id,{status:'canceled'},'PATCH')).data;
  if(t.status==='paid'||t.status==='billed'||t.status==='past_due')throw new HttpError(409,'A payment is still processing. Try deletion again after Billing updates.');
  if(!['canceled','completed'].includes(t.status))throw new HttpError(503,'Checkout cancellation was not confirmed.');
  if(t.status==='completed'){
   if(!t.subscription_id)throw new HttpError(409,'A completed Cloud checkout is awaiting subscription reconciliation. Contact support.');
   const s=(await paddle('/subscriptions/'+t.subscription_id)).data;
   await syncSubscription(sb,uid,s);
  }
  dbCheck(await sb.from('checkout_intents').update({state:t.status}).eq('id',row.id));
 }
}
export async function deleteAccount(sb,user){
 return withBillingLock(sb,user.id,async()=>{
  const profile=await profileFor(sb,user.id);
  // Remains true after any failure, preventing checkout/generation until the
  // owner retries deletion. Read/export/portal remain available.
  dbCheck(await sb.from('profiles').update({deletion_pending:true}).eq('id',user.id));
  await closePendingCheckouts(sb,user.id);
  let subscriptions=await reconcileSubscriptions(sb,user.id,profile);
  const known=new Set(catalog().filter(x=>x.interval!=='once'&&x.price).map(x=>x.price));
  for(const s of subscriptions.filter(billable)){
   if(!s.items?.length||s.items.some(i=>!known.has(i.price?.id||i.price_id)))throw new HttpError(409,'A subscription has unrecognized products. Support must reconcile it before deletion.');
   const canceled=(await paddle('/subscriptions/'+encodeURIComponent(s.id)+'/cancel',{effective_from:'immediately'})).data;
   if(canceled?.status!=='canceled')throw new HttpError(503,'Cancellation was not confirmed. Your identity has not been deleted.');
   await syncSubscription(sb,user.id,canceled);
  }
  subscriptions=await reconcileSubscriptions(sb,user.id,profile);
  if(subscriptions.some(billable))throw new HttpError(503,'A subscription is still billable. Deletion has been stopped.');
  const result=await sb.auth.admin.deleteUser(user.id);
  dbCheck(result,'Billing is canceled, but data deletion failed. Retry from Settings.');
  return {ok:true,billing_canceled:true,note:'Account data deleted. Legally required transaction records are retained separately. Cancellation is not a refund.'};
 });
}
