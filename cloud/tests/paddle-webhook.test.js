import {describe,it,expect,vi,beforeAll,afterAll,beforeEach,afterEach} from 'vitest';
import {createHmac,randomUUID} from 'node:crypto';
vi.mock('../api/_lib/sb.js',()=>({authUser:vi.fn(),admin:vi.fn(),json:(b,s=200)=>new Response(JSON.stringify(b),{status:s})}));
import {admin} from '../api/_lib/sb.js';
import handler,{verify} from '../api/_lib/routes/paddle-webhook.js';
import {desktopDownload} from '../api/_lib/fulfillment.js';
import {seal,checkoutProof} from '../api/_lib/commerce.js';
import {database} from './helpers/db.js';
import {configure,paddleServer,ids,knownSubscription} from './helpers/paddle.js';
let sb,state;
beforeAll(async()=>{sb=await database();admin.mockReturnValue(sb);},30000);afterAll(()=>sb.close());
beforeEach(async()=>{await sb.db.exec('truncate auth.users cascade;truncate desktop_orders,paddle_events,payment_adjustments');configure();state=paddleServer();});
afterEach(()=>{vi.unstubAllEnvs();vi.unstubAllGlobals();});
function event(type,data){return {event_id:'evt_'+randomUUID().replaceAll('-','').slice(0,26),event_type:type,occurred_at:new Date().toISOString(),data};}
function req(p,secret=process.env.PADDLE_WEBHOOK_SECRET,time=Math.floor(Date.now()/1000)){
 const raw=JSON.stringify(p),sig=createHmac('sha256',secret).update(time+':'+raw).digest('hex');return new Request('https://app.example.test/api/paddle-webhook',{method:'POST',headers:{'paddle-signature':`ts=${time};h1=${sig}`},body:raw});
}
function guest(){
 state.customers.set(ids.customer,{id:ids.customer,email:'guest@example.test'});
 return {id:'txn_'+ '7'.repeat(26),status:'completed',customer_id:ids.customer,items:[{price:{id:ids.owner},quantity:1}],currency_code:'USD',details:{totals:{total:'19900'}}};
}
describe('verified payment events and durable fulfillment',()=>{
 it('verifies raw Unicode, refuses changed/expired signatures and permits secret rotation',async()=>{
  const p=event('customer.updated',{id:ids.customer,name:'ایپکس کافی'});expect((await handler(req(p,'bad-secret'))).status).toBe(401);expect((await handler(req(p,undefined,Math.floor(Date.now()/1000)-600))).status).toBe(401);
  vi.stubEnv('PADDLE_WEBHOOK_SECRET_PREVIOUS','previous-secret');expect((await handler(req(p,'previous-secret'))).status).toBe(200);expect(verify('x','ts=1;h1=garbage','secret')).toBe(false);
 });
 it('fulfills a guest order without a Cloud account and deduplicates events/orders/emails',async()=>{
  const d=guest(),p=event('transaction.completed',d);expect((await handler(req(p))).status).toBe(200);expect((await handler(req(p))).status).toBe(200);expect((await handler(req(event('transaction.completed',d)))).status).toBe(200);
  expect(state.emails).toHaveLength(1);expect(state.emails[0].body.to).toEqual(['guest@example.test']);expect(state.emails[0].body.text).toContain('/desktop-download#token=');
  expect((await sb.db.query('select count(*)::int n from desktop_orders')).rows[0].n).toBe(1);expect((await sb.db.query('select count(*)::int n from profiles')).rows[0].n).toBe(0);
 });
 it('persists the order when email fails and safely retries delivery',async()=>{
  const p=event('transaction.completed',guest());state.emailFailure=true;expect((await handler(req(p))).status).toBe(503);
  const first=(await sb.db.query('select * from desktop_orders')).rows[0];expect(first.delivered_at).toBe(null);expect(first.delivery_error).toBeTruthy();
  state.emailFailure=false;expect((await handler(req(p))).status).toBe(200);expect(state.emails).toHaveLength(0);
  await sb.db.query("update desktop_orders set delivery_next_attempt_at=now()-interval '1 second'");
  const {deliverDesktopOrder}=await import('../api/_lib/fulfillment.js');await deliverDesktopOrder(sb,first.transaction_id);expect(state.emails).toHaveLength(1);expect((await sb.db.query('select delivery_nonce from desktop_orders')).rows[0].delivery_nonce).toBe(first.delivery_nonce);
 });
 it('grants/revokes download access only from approved order state',async()=>{
  const d=guest();await handler(req(event('transaction.completed',d)));const order=(await sb.db.query('select * from desktop_orders')).rows[0];
  const token=seal({purpose:'desktop-download',id:d.id,nonce:order.delivery_nonce,exp:Date.now()+60000},'DESKTOP_DOWNLOAD_SECRET');expect(await desktopDownload(sb,token)).toContain('https://storage.example.test');
  const adjustment={id:'adj_'+ '5'.repeat(26),transaction_id:d.id,type:'full',action:'refund',status:'pending_approval',totals:{total:'19900'}};
  expect((await handler(req(event('adjustment.created',adjustment)))).status).toBe(200);expect(await desktopDownload(sb,token)).toContain('https://storage.example.test');
  const approved=event('adjustment.updated',{...adjustment,status:'approved'});approved.occurred_at=new Date(Date.now()+1000).toISOString();expect((await handler(req(approved))).status).toBe(200);await expect(desktopDownload(sb,token)).rejects.toMatchObject({status:403});
 });
 it('does not let a Desktop purchase overwrite an active Cloud subscription',async()=>{const user=await sb.user();await knownSubscription(sb,state,user,{price:ids.agency});const d=guest();state.customers.set(ids.customer,{id:ids.customer,email:user.email});await handler(req(event('transaction.completed',d)));expect((await sb.db.query('select plan from profiles where id=$1',[user.id])).rows[0].plan).toBe('agency');});
 it('binds a Cloud entitlement to the ORIGINAL authorized transaction, never custom user_id/email',async()=>{
  const user=await sb.user(),intent=(await sb.rpc('begin_checkout',{p_uid:user.id,p_plan:'pro',p_interval:'month'})).data;
  const tx='txn_'+ '8'.repeat(26),s={id:ids.subscription,customer_id:ids.customer,status:'active',items:[{price:{id:ids.pro},quantity:1}],updated_at:new Date().toISOString(),custom_data:{bf_proof:checkoutProof(user.id,intent.id)}};
  await sb.db.query("update checkout_intents set transaction_id=$1,state='open' where id=$2",[tx,intent.id]);state.subscriptions.set(s.id,s);state.transactions.set(tx,{id:tx,status:'completed',subscription_id:s.id,customer_id:ids.customer,custom_data:{bf_intent:intent.id}});
  expect((await handler(req(event('subscription.activated',s)))).status).toBe(200);expect((await sb.db.query('select plan from profiles where id=$1',[user.id])).rows[0].plan).toBe('pro');
  const other=await sb.user(),forged={...s,id:'sub_'+ '9'.repeat(26),custom_data:{user_id:other.id,email:other.email}};state.subscriptions.set(forged.id,forged);expect((await handler(req(event('subscription.activated',forged)))).status).toBe(503);expect((await sb.db.query('select plan from profiles where id=$1',[other.id])).rows[0].plan).toBe('free');
 });
 it('reconciles canonical cancellation even when an old active event is delivered late',async()=>{const user=await sb.user(),s=await knownSubscription(sb,state,user);const stale={...s,status:'active'};s.status='canceled';s.updated_at=new Date(Date.now()+1000).toISOString();expect((await handler(req(event('subscription.activated',stale)))).status).toBe(200);expect((await sb.db.query('select plan from profiles where id=$1',[user.id])).rows[0].plan).toBe('free');});
 it('keeps an unsuccessful event retryable after a database failure',async()=>{sb.failNextRpc('record_desktop_order');const p=event('transaction.completed',guest());expect((await handler(req(p))).status).toBe(503);expect((await handler(req(p))).status).toBe(200);expect(state.emails).toHaveLength(1);});
});
