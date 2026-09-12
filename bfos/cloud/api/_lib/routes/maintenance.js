// Invoke from a scheduled job with Authorization: Bearer CRON_SECRET.
// Safe to retry. Never exposes subscriber data in its summary.
import {admin,json} from '../sb.js';
import {serve} from '../serve.js';
import {deliverDesktopOrder} from '../fulfillment.js';
import {env} from '../commerce.js';
import {dbCheck} from '../http.js';
import {timingSafeEqual} from 'node:crypto';
async function handle(req){
 const expected=Buffer.from('Bearer '+env('CRON_SECRET')),actual=Buffer.from(req.headers?.get?.('authorization')||'');
 if(env('CRON_SECRET').length<32||actual.length!==expected.length||!timingSafeEqual(actual,expected))return json({error:'Not authorized'},401);
 try{
  const sb=admin(),rows=dbCheck(await sb.from('desktop_orders').select('transaction_id').eq('status','paid').is('delivered_at',null).lte('delivery_next_attempt_at',new Date().toISOString()).order('delivery_attempts',{ascending:true}).order('created_at',{ascending:true}).limit(3))||[];
  let sent=0,failed=0;
  await Promise.all(rows.map(async row=>{try{if(await deliverDesktopOrder(sb,row.transaction_id))sent++;}catch{failed++;}}));
  const rate_rows_collected=dbCheck(await sb.rpc('bf_rate_limit_gc'));
  dbCheck(await sb.rpc('expire_generation_reservations'));
  const events=await sb.from('paddle_events').select('event_id',{head:true,count:'exact'}).eq('status','failed');dbCheck(events);
  const health=dbCheck(await sb.rpc('generation_health'));
  const alerts=[];
  if(failed)alerts.push('Desktop delivery retries are failing');
  if(events.count)alerts.push('Payment events need reconciliation');
  if(health.failed_today>=5)alerts.push('Generation failures exceed five today');
  if(health.average_duration_ms>30000)alerts.push('Average generation latency exceeds 30 seconds');
  if(Number(health.reserved_operator_budget_usd)>=Number(env('MAX_PROVIDER_DAILY_USD')||10)*.8)alerts.push('80% of the configured provider budget is reserved');
  let alert_delivery='not needed';
  if(alerts.length){
   alert_delivery='not configured';
   if(env('OPS_ALERT_WEBHOOK_URL').startsWith('https://')){
    try{const r=await fetch(env('OPS_ALERT_WEBHOOK_URL'),{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({text:'BrandForge Cloud: '+alerts.join('; ')}),signal:AbortSignal.timeout(5000)});alert_delivery=r.ok?'sent':'failed';}catch{alert_delivery='failed';}
   }
  }
  return json({sent,rate_rows_collected,delivery_pending:failed,webhook_events_needing_review:events.count||0,health,alerts,alert_delivery});
 }catch{return json({error:'Maintenance could not complete. Check the deployment.'},503);}
}
const h=serve(handle);export default h;export const GET=h;export const POST=h;
