import {admin,json} from '../sb.js';
import {createHmac,timingSafeEqual} from 'node:crypto';
import {serve} from '../serve.js';
import {dbCheck,HttpError,readBody} from '../http.js';
import {catalog,accountForSubscription,syncSubscription,paddle,billable,unseal} from '../commerce.js';
import {recordDesktopTransaction,deliverDesktopOrder} from '../fulfillment.js';
export function verify(raw,header,secret,tolerance=300){
 if(!header||!secret)return false;
 const entries=String(header).split(';').map(x=>x.trim().split('='));
 const ts=entries.filter(x=>x[0]==='ts');const signatures=entries.filter(x=>x[0]==='h1').map(x=>x[1]);
 if(ts.length!==1||!/^\d+$/.test(ts[0][1])||Math.abs(Date.now()/1000-Number(ts[0][1]))>tolerance)return false;
 const expected=createHmac('sha256',secret).update(`${ts[0][1]}:${raw}`).digest();
 return signatures.some(s=>/^[a-f\d]{64}$/i.test(s||'')&&timingSafeEqual(Buffer.from(s,'hex'),expected));
}
// Export retained for configuration tests; Desktop maps to orders, not plans.
export function priceToPlan(){try{return Object.fromEntries(catalog().filter(x=>x.price).map(x=>[x.price,x.plan]));}catch{return {};}}
async function applySubscription(sb,s,at){
 const uid=await accountForSubscription(sb,s);
 const proof=unseal(s.custom_data?.bf_proof);
 if(!uid){
  const old=dbCheck(await sb.from('billing_subscriptions').select('id,user_id').eq('id',s.id).maybeSingle());
  if(proof?.purpose==='cloud-checkout'||old){
   const userId=proof?.uid;
   const profile=userId?dbCheck(await sb.from('profiles').select('id,deletion_pending').eq('id',userId).maybeSingle()):null;
   if(profile)throw new HttpError(503,'Checkout ownership is awaiting reconciliation.');
   // A paid event arriving AFTER account erasure must not restart renewals.
   if(billable(s))await paddle('/subscriptions/'+s.id+'/cancel',{effective_from:'immediately'});
   if(old)dbCheck(await sb.from('billing_subscriptions').update({status:'canceled',updated_at:new Date().toISOString()}).eq('id',s.id));
   return 'orphan subscription canceled; review any final payment for refund';
  }
  throw new HttpError(503,'No server-authorized checkout or known subscription.');
 }
 const profile=dbCheck(await sb.from('profiles').select('deletion_pending').eq('id',uid).maybeSingle());
 if(!profile || profile.deletion_pending){
  const canceled=billable(s)?(await paddle('/subscriptions/'+s.id+'/cancel',{effective_from:'immediately'})).data:s;
  if(profile)await syncSubscription(sb,uid,canceled,canceled.updated_at||at);
  return 'canceled during account deletion';
 }
 await syncSubscription(sb,uid,s,at);return 'subscription reconciled';
}
async function handle(req){
 if(req.method&&req.method!=='POST')return json({error:'Method not allowed'},405);
 const secrets=[process.env.PADDLE_WEBHOOK_SECRET,process.env.PADDLE_WEBHOOK_SECRET_PREVIOUS].filter(Boolean);
 if(!secrets.length)return json({error:'Webhook not configured'},503);
 if(Number(req.headers?.get?.('content-length'))>1000000)return json({error:'Webhook too large'},413);
 let raw;try{raw=await readBody(req,1000000);}catch(e){return json({error:'Webhook too large or unreadable'},e.status||400);}
 if(!secrets.some(s=>verify(raw,req.headers?.get?.('paddle-signature'),s)))return json({error:'Invalid webhook signature'},401);
 let p;try{p=JSON.parse(raw);}catch{return json({error:'Invalid JSON'},400);}
 if(!p||typeof p!=='object'||Array.isArray(p)||!/^evt_[a-z\d]{26}$/.test(p.event_id||'')||!Number.isFinite(Date.parse(p.occurred_at)))return json({error:'Invalid webhook envelope'},400);
 const sb=admin();let claimed=false;
 try{
  const state=dbCheck(await sb.rpc('claim_paddle_event',{p_id:p.event_id}));
  if(state==='completed')return json({ok:true,note:'duplicate event ignored'});
  if(state!=='claimed')throw new HttpError(503,'This event is already processing; retry later.');
  claimed=true;const d=p.data||{};let note='ignored';
  dbCheck(await sb.from('paddle_events').update({event_type:p.event_type,entity_id:String(d.id||'').slice(0,80)}).eq('event_id',p.event_id));
  if(p.event_type==='transaction.completed'){
   if(await recordDesktopTransaction(sb,d,p.occurred_at)){await deliverDesktopOrder(sb,d.id);note='desktop order recorded';}
   else if(d.subscription_id){
    const s=(await paddle('/subscriptions/'+encodeURIComponent(d.subscription_id))).data;
    if(!s)throw new HttpError(503,'Subscription not available yet.');
    if(!s.custom_data)s.custom_data=d.custom_data;
    note=await applySubscription(sb,s,s.updated_at||p.occurred_at);
   }
  }else if(p.event_type.startsWith('subscription.')){
   // Pull canonical state: a delayed activation cannot roll back a later cancel.
   const s=(await paddle('/subscriptions/'+encodeURIComponent(d.id))).data;
   if(!s)throw new HttpError(503,'Subscription reconciliation failed.');
   note=await applySubscription(sb,s,s.updated_at||p.occurred_at);
  }else if(['adjustment.created','adjustment.updated'].includes(p.event_type)){
   dbCheck(await sb.rpc('apply_payment_adjustment',{p_data:{id:d.id,transaction_id:d.transaction_id,action:d.action,status:d.status,type:d.type,amount_total:Number(d.totals?.total||0),occurred_at:p.occurred_at}}));note='adjustment recorded';
  }
  dbCheck(await sb.from('paddle_events').update({status:'completed',lease_until:null,last_error:null}).eq('event_id',p.event_id));
  return json({ok:true,note});
 }catch(e){
  if(claimed)await sb.from('paddle_events').update({status:'failed',lease_until:null,last_error:e.code||'PROCESSING_FAILED'}).eq('event_id',p.event_id);
  // No raw payloads, customer emails, keys or signed links in application logs.
  console.error('Paddle processing needs retry',p.event_id,e.code||'PROCESSING_FAILED');
  return json({error:'Could not process webhook; retry is safe.'},503);
 }
}
const h=serve(handle);export default h;export const POST=h;
