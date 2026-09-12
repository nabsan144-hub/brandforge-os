// Owner-only READ-ONLY metrics. Unlike maintenance, this never sends mail,
// expires reservations, deletes assets or mutates a customer record.
import {admin,json} from '../sb.js';
import {serve} from '../serve.js';
import {dbCheck} from '../http.js';
import {timingSafeEqual} from 'node:crypto';
async function handle(req){
 if(req.method&&req.method!=='GET')return json({error:'Method not allowed'},405);
 const secret=process.env.CRON_SECRET||'',expected=Buffer.from('Bearer '+secret),actual=Buffer.from(req.headers?.get?.('authorization')||'');
 if(secret.length<32||actual.length!==expected.length||!timingSafeEqual(actual,expected))return json({error:'Not authorized'},401);
 try{
  const deadline=AbortSignal.timeout(10000),signal=req.signal?AbortSignal.any([req.signal,deadline]):deadline,sb=admin({signal});
  const [health,pending,events,assets,feedback,usage]=await Promise.all([
   sb.rpc('generation_health'),
   sb.from('desktop_orders').select('created_at',{count:'exact'}).eq('status','paid').is('delivered_at',null).order('created_at',{ascending:true}).limit(1),
   sb.from('paddle_events').select('event_id',{head:true,count:'exact'}).eq('status','failed'),
   sb.from('campaign_asset_bundles').select('id',{head:true,count:'exact'}).eq('state','deleting'),
   sb.from('product_feedback').select('usable,minutes_saved').gte('created_at',new Date(Date.now()-30*86400000).toISOString()).order('created_at',{ascending:false}).limit(1000),
   sb.rpc('usage_event_summary'),
  ]);
  const h=dbCheck(health),orders=dbCheck(pending),f=dbCheck(feedback);dbCheck(events);dbCheck(assets);
  const timed=f.filter(x=>Number.isFinite(x.minutes_saved));
  return json({schema:1,usage_metrics:dbCheck(usage),read_only:true,observed_at:new Date().toISOString(),generation:h,delivery:{pending:pending.count||0,oldest_seconds:orders[0]?Math.max(0,Math.floor((Date.now()-Date.parse(orders[0].created_at))/1000)):0},failed_webhook_events:events.count||0,pending_asset_deletions:assets.count||0,feedback:{window_days:30,sample_size:f.length,capped:f.length===1000,self_reported_usable:f.filter(x=>x.usable===true).length,self_reported_average_minutes_saved:timed.length?timed.reduce((s,x)=>s+x.minutes_saved,0)/timed.length:null,notice:'Self-selected feedback, not a representative customer benchmark. No prompts, names, emails or notes included.'},limits:'No invoice-based profit, client-side export success, uptime SLA or paid-readiness certification is implied.'});
 }catch{return json({error:'Operational metrics are temporarily unavailable.'},503);}
}
const h=serve(handle);export default h;export const GET=h;
