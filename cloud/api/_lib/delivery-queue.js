import {dbCheck} from './http.js';
import {deliverDesktopOrder} from './fulfillment.js';
// Bounded throughput, not a replacement for a frequent monitored scheduler.
// Paid order/nonce claims and backoff remain in the existing SQL transaction.
export async function drainDesktopQueue(sb,{deliver=deliverDesktopOrder,clientForSignal=()=>sb,now=Date.now,sleep=ms=>new Promise(r=>setTimeout(r,ms)),budgetMs=30000,startGapMs=600,signal:parentSignal}={}){
 const started=now(),deadline=started+budgetMs;
 const rows=dbCheck(await sb.from('desktop_orders').select('transaction_id').eq('status','paid').is('delivered_at',null).lte('delivery_next_attempt_at',new Date(now()).toISOString()).order('delivery_attempts',{ascending:true}).order('created_at',{ascending:true}).limit(20))||[];
 let sent=0,failed=0,skipped=0,cursor=0,lastStart=started-startGapMs;
 // Two workers, with serialized start pacing (under two attempts/second).
 // Don't start an order unless its entire 15s attempt budget remains.
 let gate=Promise.resolve();
 async function take(){
  const prior=gate;let release;gate=new Promise(r=>{release=r;});await prior;
  try{
   if(parentSignal?.aborted||cursor>=rows.length)return null;
   const delay=Math.max(0,lastStart+startGapMs-now());
   if(now()+delay+15000>deadline)return null;
   if(delay)await sleep(delay);
   if(parentSignal?.aborted||now()+15000>deadline)return null;
   lastStart=now();return rows[cursor++];
  }finally{release();}
 }
 async function worker(){for(;;){const row=await take();if(!row)return;const attempt=AbortSignal.timeout(15000),signal=parentSignal?AbortSignal.any([parentSignal,attempt]):attempt;
  try{if(await deliver(clientForSignal(signal),row.transaction_id,{signal}))sent++;else skipped++;}catch{failed++;}
 }}
 await Promise.all([worker(),worker()]);
 return {sent,failed,skipped,attempted:cursor,deferred:rows.length-cursor,batch_full:rows.length===20};
}
