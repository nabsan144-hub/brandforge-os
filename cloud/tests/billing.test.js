import {describe,it,expect,vi,beforeAll,afterAll,beforeEach,afterEach} from 'vitest';
vi.mock('../api/_lib/sb.js',()=>({authUser:vi.fn(),admin:vi.fn(),json:(b,s=200)=>new Response(JSON.stringify(b),{status:s})}));
vi.mock('../api/_lib/limit.js',()=>({rateLimit:vi.fn(async()=>true)}));
import {admin,authUser} from '../api/_lib/sb.js';
import status from '../api/_lib/routes/bill-status.js';import token from '../api/_lib/routes/bill-client-token.js';import checkout from '../api/_lib/routes/bill-checkout.js';import change from '../api/_lib/routes/bill-change.js';import portal from '../api/_lib/routes/bill-portal.js';import me from '../api/_lib/routes/me.js';import closeCheckout from '../api/_lib/routes/bill-cancel-pending.js';
import {database,request} from './helpers/db.js';
import {configure,paddleServer,knownSubscription,ids} from './helpers/paddle.js';
let sb,user,state;
beforeAll(async()=>{sb=await database();admin.mockReturnValue(sb);},30000);afterAll(()=>sb.close());
beforeEach(async()=>{await sb.db.exec('truncate auth.users cascade');configure();state=paddleServer();user=await sb.user();authUser.mockResolvedValue(user);});
afterEach(()=>{vi.unstubAllEnvs();vi.unstubAllGlobals();});
describe('server-authorized billing lifecycle with real database state',()=>{
 it('requires auth on account billing; public token stays disabled without release verification',async()=>{authUser.mockResolvedValue(null);expect((await status(request('/billing/status'))).status).toBe(401);vi.stubEnv('BILLING_RELEASE_VERIFIED','false');expect((await token(request('/billing/paddle-client-token'))).status).toBe(503);});
 it('returns clear plan metadata and only opens matching configured environments',async()=>{const d=await(await status(request('/billing/status'))).json();expect(d.plan).toBe('free');expect(d.plans.every(p=>p.name&&p.id)).toBe(true);expect(d.checkout_enabled).toBe(true);expect((await token(request('/billing/paddle-client-token'))).status).toBe(200);vi.stubEnv('PADDLE_ENV','production');expect((await token(request('/billing/paddle-client-token'))).status).toBe(503);});
 it('creates a server-bound annual checkout, reuses it, and never accepts raw client prices',async()=>{
  const r=await checkout(request('/billing/checkout','POST',{plan:'pro',interval:'year',price_id:ids.owner}));expect(r.status).toBe(200);const d=await r.json();
  const t=state.transactions.get(d.transaction_id);expect(t.items).toEqual([{price_id:ids.year,quantity:1}]);expect(t.custom_data.bf_proof).toContain('.');
  const again=await(await checkout(request('/billing/checkout','POST',{plan:'pro',interval:'year'}))).json();expect(again.transaction_id).toBe(d.transaction_id);expect(state.transactions.size).toBe(1);
  expect((await checkout(request('/billing/checkout','POST',{plan:'agency'}))).status).toBe(409);
 });
 it('blocks a wrong amount or disabled release before creating any checkout',async()=>{state.priceMismatch=true;expect((await checkout(request('/billing/checkout','POST',{plan:'pro'}))).status).toBe(503);expect(state.transactions.size).toBe(0);});
 it('requires email verification before first purchase',async()=>{authUser.mockResolvedValue({...user,email_confirmed_at:null});expect((await checkout(request('/billing/checkout','POST',{plan:'pro'}))).status).toBe(403);});
 it('closes a pending unpaid checkout before permitting another choice',async()=>{
  const first=await(await checkout(request('/billing/checkout','POST',{plan:'pro'}))).json();expect((await closeCheckout(request('/billing/cancel-pending','POST',{}))).status).toBe(200);expect(state.transactions.get(first.transaction_id).status).toBe('canceled');expect((await checkout(request('/billing/checkout','POST',{plan:'agency'}))).status).toBe(200);
 });
 it.each([[ids.pro,'agency','month',ids.agency],[ids.agency,'pro','month',ids.pro],[ids.pro,'pro','year',ids.year],[ids.year,'pro','month',ids.pro]])('previews and updates ONE existing subscription (%s → %s/%s)',async(from,plan,interval,to)=>{
  const sub=await knownSubscription(sb,state,user,{price:from});
  expect((await checkout(request('/billing/checkout','POST',{plan,interval}))).status).toBe(409);
  const preview=await change(request('/billing/change','POST',{plan,interval}));expect(preview.status).toBe(200);const d=await preview.json();expect(d.preview.immediate.total).toBe('1500');
  expect((await change(request('/billing/change','POST',{plan,interval,confirmation:d.confirmation}))).status).toBe(200);
  expect(state.subscriptions.get(sub.id).items[0].price.id).toBe(to);expect(state.subscriptions.size).toBe(1);expect(state.transactions.size).toBe(0);
  expect((await change(request('/billing/change','POST',{plan,interval,confirmation:d.confirmation}))).status).toBe(409);
 });
 it('rejects a tampered preview and conflicting multiple subscriptions',async()=>{await knownSubscription(sb,state,user);expect((await change(request('/billing/change','POST',{plan:'agency',confirmation:'fake'}))).status).toBe(409);await knownSubscription(sb,state,user,{id:ids.subscription+'x',price:ids.agency});expect((await change(request('/billing/change','POST',{plan:'agency'}))).status).toBe(409);expect(state.transactions.size).toBe(0);});
 it('creates a fresh authenticated portal link without persisting it',async()=>{await knownSubscription(sb,state,user);const r=await portal(request('/billing/portal','POST',{}));expect(r.status).toBe(200);expect((await r.json()).url).toContain('https://customer-portal.paddle.com/');});
 it.each(['active','past_due','canceled'])('deletes an account only after reconciling a %s subscription',async(status)=>{
  const s=await knownSubscription(sb,state,user,{status});const r=await me(request('/me','DELETE',{confirm:'DELETE AND CANCEL BILLING'}));expect(r.status).toBe(200);expect(state.subscriptions.get(s.id).status).toBe('canceled');expect((await sb.db.query('select id from auth.users where id=$1',[user.id])).rows).toHaveLength(0);
 });
 it('cancels all owned billable subscriptions before deleting identity',async()=>{await knownSubscription(sb,state,user);await knownSubscription(sb,state,user,{id:ids.subscription+'extra',price:ids.agency});expect((await me(request('/me','DELETE',{confirm:'DELETE AND CANCEL BILLING'}))).status).toBe(200);expect([...state.subscriptions.values()].every(s=>s.status==='canceled')).toBe(true);expect(state.calls.filter(c=>c.path.endsWith('/cancel'))).toHaveLength(2);});
 it('preserves identity/data on provider outage or unconfirmed cancellation',async()=>{await knownSubscription(sb,state,user);state.outage=true;expect((await me(request('/me','DELETE',{confirm:'DELETE AND CANCEL BILLING'}))).status).toBe(503);expect((await sb.db.query('select id from auth.users where id=$1',[user.id])).rows).toHaveLength(1);state.outage=false;state.cancelFailure=true;expect((await me(request('/me','DELETE',{confirm:'DELETE AND CANCEL BILLING'}))).status).toBe(502);expect((await sb.db.query('select id from auth.users where id=$1',[user.id])).rows).toHaveLength(1);});
 it('does not grant portal access by email reuse across identities',async()=>{const other=await sb.user();await knownSubscription(sb,state,other);await sb.db.query('update profiles set paddle_customer_id=$1 where id=$2',[ids.customer,user.id]);expect((await portal(request('/billing/portal','POST',{}))).status).toBe(409);expect(state.calls.some(c=>c.path.endsWith('/portal-sessions'))).toBe(false);});
});
