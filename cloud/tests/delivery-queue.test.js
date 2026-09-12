import {it,expect,vi,afterEach,beforeAll,afterAll} from 'vitest';
import {database} from './helpers/db.js';
import {drainDesktopQueue} from '../api/_lib/delivery-queue.js';
import {deliverDesktopOrder} from '../api/_lib/fulfillment.js';
import {admin} from '../api/_lib/sb.js';
let sb;
beforeAll(async()=>{sb=await database();},30000);afterAll(()=>sb.close());afterEach(()=>{vi.unstubAllGlobals();vi.unstubAllEnvs();});
it('recovers 20 paid orders after a simulated outage, without new orders or duplicate sends',async()=>{
 vi.stubEnv('DESKTOP_DOWNLOAD_SECRET','d'.repeat(40));vi.stubEnv('BRANDFORGE_APP_URL','https://app.example.test');vi.stubEnv('RESEND_API_KEY','fixture');vi.stubEnv('DELIVERY_FROM_EMAIL','test@example.test');
 for(let i=0;i<20;i++)expect((await sb.rpc('record_desktop_order',{p_data:{transaction_id:'txn_queue_'+i,customer_id:'ctm_test',email:'buyer@example.test',tier:'owner',amount_total:19900,currency:'USD',release_path:'owner.zip',release_bucket:'releases',release_sha256:'a'.repeat(64),occurred_at:new Date().toISOString()}})).error).toBeNull();
 sb.storage={from:()=>({createSignedUrl:async()=>({data:{signedUrl:'https://example.test/private'},error:null})})};
 const calls=[];vi.stubGlobal('fetch',vi.fn(async(_,o)=>{calls.push(o.headers['Idempotency-Key']);return {ok:false};}));
 await expect(deliverDesktopOrder(sb,'txn_queue_0')).rejects.toThrow();
 await sb.db.query("update desktop_orders set delivery_next_attempt_at=now()-interval '1 second',delivery_claimed_until=null");
 vi.stubGlobal('fetch',vi.fn(async(_,o)=>{calls.push(o.headers['Idempotency-Key']);return {ok:true};}));
 let clock=Date.now();const options={now:()=>clock,sleep:async ms=>{clock+=ms;}};
 const result=await drainDesktopQueue(sb,options);expect(result).toMatchObject({sent:20,failed:0,attempted:20});expect(new Set(calls).size).toBe(20);
 expect((await drainDesktopQueue(sb,options)).attempted).toBe(0);
 expect((await sb.db.query('select count(*)::int as n from desktop_orders')).rows[0].n).toBe(20);
});
it('leaves orders unclaimed when the attempt budget cannot fit',async()=>{
 const fake={from:()=>({select(){return this;},eq(){return this;},is(){return this;},lte(){return this;},order(){return this;},limit:async()=>({data:[{transaction_id:'x'}]})})};
 const deliver=vi.fn();const r=await drainDesktopQueue(fake,{budgetMs:1,deliver});expect(r.deferred).toBe(1);expect(deliver).not.toHaveBeenCalled();
});
it('forwards a caller abort budget into the real SDK fetch transport',async()=>{
 vi.stubEnv('SUPABASE_URL','https://fixture.supabase.co');vi.stubEnv('SUPABASE_SERVICE_ROLE_KEY','fixture-key');
 const controller=new AbortController();controller.abort();let signal;
 vi.stubGlobal('fetch',vi.fn(async(_,o)=>{signal=o.signal;return new Response('[]',{headers:{'Content-Type':'application/json'}});}));
 await admin({signal:controller.signal}).from('profiles').select('id');expect(signal.aborted).toBe(true);
});

it('stops new attempts and aborts active delivery on the shared request deadline',async()=>{
 const controller=new AbortController();
 const fake={from:()=>({select(){return this;},eq(){return this;},is(){return this;},lte(){return this;},order(){return this;},limit:async()=>({data:[{transaction_id:'a'},{transaction_id:'b'},{transaction_id:'c'}]})})};
 const deliver=vi.fn(async(_sb,_id,{signal})=>{controller.abort();expect(signal.aborted).toBe(true);throw new Error('aborted');});
 const r=await drainDesktopQueue(fake,{signal:controller.signal,deliver,startGapMs:0});
 expect(r).toMatchObject({attempted:2,failed:2,deferred:1});expect(deliver).toHaveBeenCalledTimes(2);
});
