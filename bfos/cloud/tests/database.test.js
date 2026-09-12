import {describe,it,expect,beforeAll,afterAll} from 'vitest';
import {PGlite} from '@electric-sql/pglite';
import {readFileSync,readdirSync} from 'node:fs';
import {randomUUID} from 'node:crypto';
const directory=new URL('../../supabase/migrations/',import.meta.url);
const migrations=readdirSync(directory).filter(x=>x.endsWith('.sql')).sort();
const bootstrap=`create schema auth;create table auth.users(id uuid primary key,email text);create function auth.uid() returns uuid language sql stable as $$select nullif(current_setting('request.jwt.claim.sub',true),'')::uuid$$;create role anon;create role authenticated;create role service_role bypassrls;grant usage on schema public to anon,authenticated,service_role;`;
const sql=f=>readFileSync(new URL(f,directory),'utf8').replace('create extension if not exists pgcrypto;','');
let db;
async function user(){const id=randomUUID();await db.query('insert into auth.users values($1,$2)',[id,id+'@example.test']);return id;}
async function rpc(name,values=[]){const r=await db.query(`select public.${name}(${values.map((_,i)=>'$'+(i+1)).join(',')}) as result`,values.map(v=>v&&typeof v==='object'?JSON.stringify(v):v));return r.rows[0].result;}
const hash='a'.repeat(64),campaign={name:'Test',product:'Coffee',industry:'Food',audience:'People',benefits:'Fresh beans',strategy:'Draft strategy',copy:'Draft copy',seo:'Not measured',files:[{name:'hero.svg',content:'<svg/>'}],stage_status:{copy:{state:'template'}}};
async function complete(uid,limits=[3,null,200,2]){const id=randomUUID();expect((await rpc('reserve_generation',[uid,id,hash,...limits])).ok).toBe(true);return {id,campaign:await rpc('complete_generation',[uid,id,campaign])};}
beforeAll(async()=>{db=new PGlite();await db.exec(bootstrap);for(const m of migrations)await db.exec(sql(m));},30000);
afterAll(async()=>db.close());
describe('actual PostgreSQL migrations and money/data boundaries',()=>{
 it('all current migrations also match the combined schema',()=>{expect(readFileSync(new URL('../schema.sql',import.meta.url),'utf8')).toBe('-- GENERATED from supabase/migrations. Run: node cloud/scripts/sync-schema.mjs\n\n'+migrations.map(m=>readFileSync(new URL(m,directory),'utf8')).join('\n\n'));});
 it('allows real Free, Pro and Agency reserve+complete as service role',async()=>{
  for(const limits of [[3,null,3,1],[null,50,20,2],[null,300,50,2]]){const uid=await user();await db.exec('set role service_role');try{await complete(uid,limits);}finally{await db.exec('reset role');}}
 });
 it('completed usage survives deletion and refuses the fourth Free provider reservation',async()=>{
  const uid=await user();for(let i=0;i<3;i++){const c=await complete(uid);await db.query('delete from campaigns where id=$1',[c.campaign.id]);}
  expect(await rpc('generation_totals',[uid])).toMatchObject({campaigns_lifetime:3});
  expect(await rpc('reserve_generation',[uid,randomUUID(),hash,3,null,200,2])).toMatchObject({ok:false,code:'LIMIT_LIFETIME'});
 });
 it('blocks the 51st Pro reservation before work',async()=>{
  const uid=await user();for(let i=0;i<50;i++)await complete(uid,[null,50,200,2]);
  expect(await rpc('reserve_generation',[uid,randomUUID(),hash,null,50,200,2])).toMatchObject({ok:false,code:'LIMIT_MONTHLY'});
 });
 it('keeps monthly and daily UTC windows separate from lifetime usage',async()=>{
  const uid=await user();const old=await complete(uid,[null,1,200,2]);
  await db.query("update generation_usage set yyyymm=to_char(now()-interval '1 month','YYYYMM'),created_at=now()-interval '1 month' where id=$1",[old.id]);
  expect((await rpc('reserve_generation',[uid,randomUUID(),hash,null,1,200,2])).ok).toBe(true);
  expect((await rpc('generation_totals',[uid])).campaigns_lifetime).toBe(1);
 });
 it('idempotent completion creates only one campaign and cannot be refunded',async()=>{
  const uid=await user(),c=await complete(uid);
  expect(await rpc('complete_generation',[uid,c.id,campaign])).toMatchObject({id:c.campaign.id,replayed:true});
  expect(await rpc('fail_generation',[uid,c.id,'FAKE_FAILURE'])).toBe(false);
  expect((await db.query('select count(*)::int n from campaigns where user_id=$1',[uid])).rows[0].n).toBe(1);
 });
 it('refuses a reused ID with another body or another user',async()=>{
  const uid=await user(),other=await user(),c=await complete(uid);
  expect((await rpc('reserve_generation',[uid,c.id,'b'.repeat(64),3,null,200,2])).code).toBe('IDEMPOTENCY_CONFLICT');
  expect((await rpc('reserve_generation',[other,c.id,hash,3,null,200,2])).code).toBe('IDEMPOTENCY_CONFLICT');
 });
 it('failed work releases only its own reservation, idempotently',async()=>{
  const uid=await user(),other=await user(),id=randomUUID();await rpc('reserve_generation',[uid,id,hash,3,null,200,1]);
  expect(await rpc('fail_generation',[other,id,'BAD'])).toBe(false);
  expect(await rpc('fail_generation',[uid,id,'FAILED'])).toBe(true);expect(await rpc('fail_generation',[uid,id,'FAILED'])).toBe(false);
  expect((await rpc('reserve_generation',[uid,randomUUID(),hash,3,null,200,1])).ok).toBe(true);
 });
 it('expires abandoned work and enforces the in-flight ceiling',async()=>{
  const uid=await user(),id=randomUUID();await rpc('reserve_generation',[uid,id,hash,3,null,200,1]);
  expect((await rpc('reserve_generation',[uid,randomUUID(),hash,3,null,200,1])).code).toBe('LIMIT_CONCURRENT');
  await db.query("update generation_usage set expires_at=now()-interval '1 second' where id=$1",[id]);
  expect((await rpc('reserve_generation',[uid,randomUUID(),hash,3,null,200,1])).ok).toBe(true);
  await expect(rpc('complete_generation',[uid,id,campaign])).rejects.toThrow();
 });
 it('rolls back invalid campaign completion without consuming the reservation',async()=>{
  const uid=await user(),id=randomUUID();await rpc('reserve_generation',[uid,id,hash,3,null,200,1]);
  await expect(rpc('complete_generation',[uid,id,{...campaign,product:null}])).rejects.toThrow();
  expect((await rpc('generation_totals',[uid])).campaigns_lifetime).toBe(0);
 });
 it('denies all browser operations on the waitlist, keys, usage and billing tables',async()=>{
  for(const role of ['anon','authenticated'])for(const table of ['waitlist','user_api_keys','generation_usage','desktop_orders','billing_subscriptions','checkout_intents','operator_cost_reservations']){
   const r=await db.query(`select relrowsecurity from pg_class where oid=$1::regclass`,['public.'+table]);expect(r.rows[0].relrowsecurity).toBe(true);
   for(const perm of ['SELECT','INSERT','UPDATE','DELETE'])expect((await db.query('select has_table_privilege($1,$2,$3) allowed',[role,'public.'+table,perm])).rows[0].allowed).toBe(false);
  }
  await db.exec("set role service_role;insert into public.waitlist(email) values('synthetic@example.test');reset role;");
 });
 it('does not expose quota/commerce RPCs to browser roles',async()=>{
  const r=await db.query("select p.oid::regprocedure::text name,has_function_privilege('authenticated',p.oid,'EXECUTE') allowed from pg_proc p join pg_namespace n on n.oid=p.pronamespace where n.nspname='public' and p.proname in ('reserve_generation','complete_generation','apply_subscription','record_desktop_order','reserve_operator_cost')");
  expect(r.rows).toHaveLength(5);expect(r.rows.every(x=>!x.allowed)).toBe(true);
  expect((await db.query("select to_regprocedure('public.release_campaign_slot(uuid,text)') old")).rows[0].old).toBe(null);
 });
 it('blocks competing checkout intentions, even after nominal expiry',async()=>{
  const uid=await user();const first=await rpc('begin_checkout',[uid,'pro','month']);expect(first.ok).toBe(true);
  await db.query("update checkout_intents set state='open',transaction_id='txn_test',expires_at=now()-interval '1 hour' where id=$1",[first.id]);
  expect((await rpc('begin_checkout',[uid,'agency','month'])).code).toBe('CHECKOUT_ALREADY_OPEN');
  expect(await rpc('begin_checkout',[uid,'pro','month'])).toMatchObject({code:'CHECKOUT_PENDING',transaction_id:'txn_test'});
 });
 it('orders subscription events atomically and retains all subscriptions for reconciliation',async()=>{
  const uid=await user(),at=new Date(),old=new Date(at-60000),sub='sub_'+randomUUID();
  expect(await rpc('apply_subscription',[uid,sub,'ctm_test','pro','active','pri_test','month',at.toISOString()])).toBe(true);
  expect(await rpc('apply_subscription',[uid,sub,'ctm_test','pro','canceled','pri_test','month',old.toISOString()])).toBe(false);
  expect((await db.query('select plan from profiles where id=$1',[uid])).rows[0].plan).toBe('pro');
  await rpc('apply_subscription',[uid,sub+'2','ctm_test','agency','active','pri_other','month',at.toISOString()]);
  expect((await db.query('select count(*)::int n from billing_subscriptions where user_id=$1',[uid])).rows[0].n).toBe(2);
  expect((await rpc('begin_checkout',[uid,'pro','year'])).code).toBe('SUBSCRIPTION_EXISTS');
 });
 it('guest desktop fulfillment is separate from Cloud and idempotent',async()=>{
  const uid=await user(),tx='txn_'+randomUUID();const order={transaction_id:tx,customer_id:'ctm_test',email:uid+'@example.test',tier:'owner',amount_total:19900,currency:'USD',release_path:'releases/owner.zip',occurred_at:new Date().toISOString()};
  await rpc('record_desktop_order',[order]);await rpc('record_desktop_order',[order]);
  expect((await db.query('select count(*)::int n from desktop_orders where transaction_id=$1',[tx])).rows[0].n).toBe(1);
  expect((await db.query('select plan from profiles where id=$1',[uid])).rows[0].plan).toBe('free');
  expect(await rpc('claim_desktop_delivery',[tx])).toBe(true);expect(await rpc('claim_desktop_delivery',[tx])).toBe(false);
 });
 it('full/cumulative refunds, delayed purchases and dispute reversals are auditable',async()=>{
  const tx='txn_'+randomUUID(),time=new Date();
  const adjustment={id:'adj_'+randomUUID(),transaction_id:tx,action:'refund',status:'approved',type:'partial',amount_total:10000,occurred_at:time.toISOString()};
  await rpc('apply_payment_adjustment',[adjustment]);
  await rpc('record_desktop_order',[{transaction_id:tx,customer_id:'ctm_guest',email:'guest@example.test',tier:'owner',amount_total:19900,currency:'USD',release_path:'owner.zip',occurred_at:new Date(time-60000).toISOString()}]);
  expect((await db.query('select status from desktop_orders where transaction_id=$1',[tx])).rows[0].status).toBe('paid');
  await rpc('apply_payment_adjustment',[{...adjustment,id:adjustment.id+'b',amount_total:9900}]);
  expect((await db.query('select status from desktop_orders where transaction_id=$1',[tx])).rows[0].status).toBe('refunded');
  expect(await rpc('claim_desktop_delivery',[tx])).toBe(false);
  const tx2=tx+'2';await rpc('apply_payment_adjustment',[{...adjustment,id:adjustment.id+'c',transaction_id:tx2,action:'chargeback'}]);
  expect(await rpc('desktop_order_state',[tx2,19900])).toBe('disputed');
  await rpc('apply_payment_adjustment',[{...adjustment,id:adjustment.id+'d',transaction_id:tx2,action:'chargeback_reverse',occurred_at:new Date(+time+1000).toISOString()}]);
  expect(await rpc('desktop_order_state',[tx2,19900])).toBe('paid');
 });
 it('failed/expired webhook leases can resume; completed events cannot double-process',async()=>{
  const event='evt_'+randomUUID();expect(await rpc('claim_paddle_event',[event])).toBe('claimed');expect(await rpc('claim_paddle_event',[event])).toBe('processing');
  await db.query("update paddle_events set lease_until=now()-interval '1 second' where event_id=$1",[event]);expect(await rpc('claim_paddle_event',[event])).toBe('claimed');
  await db.query("update paddle_events set status='completed' where event_id=$1",[event]);expect(await rpc('claim_paddle_event',[event])).toBe('completed');
 });
 it('copy revisions use compare-and-swap and cannot edit another owner’s campaign',async()=>{
  const uid=await user(),c=await complete(uid),other=await user();
  expect(await rpc('edit_campaign',[other,c.campaign.id,1,{copy:'bad'}])).toMatchObject({code:'NOT_FOUND'});
  expect(await rpc('edit_campaign',[uid,c.campaign.id,1,{copy:'Edited copy'}])).toMatchObject({ok:true,revision:2});
  expect(await rpc('edit_campaign',[uid,c.campaign.id,1,{copy:'Lost update'}])).toMatchObject({code:'REVISION_CONFLICT'});
  expect((await db.query('select snapshot from campaign_revisions where campaign_id=$1',[c.campaign.id])).rows[0].snapshot.copy).toBe('Draft copy');
 });
 it('the global cost guard serializes finite upper-bound credit reservations',async()=>{
  await db.exec('truncate operator_cost_reservations');
  const outcomes=await Promise.all(Array.from({length:20},()=>rpc('reserve_operator_cost',[randomUUID(),1,10])));
  expect(outcomes.filter(Boolean)).toHaveLength(10);expect((await rpc('generation_health')).reserved_operator_budget_usd).toBe(10);
 });

});
