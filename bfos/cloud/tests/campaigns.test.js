import {describe,it,expect,vi,beforeAll,afterAll,beforeEach} from 'vitest';
import {randomUUID} from 'node:crypto';
vi.mock('../api/_lib/sb.js',()=>({authUser:vi.fn(),admin:vi.fn(),json:(b,s=200)=>new Response(JSON.stringify(b),{status:s,headers:{'Content-Type':'application/json'}})}));
vi.mock('../api/_lib/limit.js',()=>({rateLimit:vi.fn(async()=>true)}));
vi.mock('../api/_lib/keys.js',()=>({resolveCampaignKeys:vi.fn(async()=>({key_source:'offline'}))}));
import {admin,authUser} from '../api/_lib/sb.js';
import {rateLimit} from '../api/_lib/limit.js';
import handler from '../api/_lib/routes/campaigns.js';
import {database,request} from './helpers/db.js';
let sb,user;
const brief={product_name:'Apex Coffee',industry:'Specialty Coffee',audience:'Busy professionals',benefits:'Organic beans; same-day delivery',provider:'offline'};
beforeAll(async()=>{sb=await database();admin.mockReturnValue(sb);},30000);
afterAll(()=>sb.close());
beforeEach(async()=>{user=await sb.user();authUser.mockResolvedValue(user);rateLimit.mockResolvedValue(true);sb.calls.length=0;delete process.env.GENERATION_PAUSED;});
describe('campaign API against actual migration RPCs',()=>{
 it('requires auth and permits only collection methods',async()=>{authUser.mockResolvedValue(null);expect((await handler(request('/campaigns'))).status).toBe(401);authUser.mockResolvedValue(user);expect((await handler(request('/campaigns','PUT',{}))).status).toBe(405);});
 it('creates a complete pack and returns an object-shaped paged list',async()=>{
  const r=await handler(request('/campaigns','POST',brief));expect(r.status).toBe(200);const made=await r.json();expect(made.id).toMatch(/-/);
  const list=await(await handler(request('/campaigns'))).json();expect(list.campaigns).toHaveLength(1);expect(list.total).toBe(1);expect(list.has_more).toBe(false);
  expect((await sb.db.query('select status from generation_usage where user_id=$1',[user.id])).rows[0].status).toBe('completed');
 });
 it('replays the same request without generating another pack',async()=>{
  const key=randomUUID(),first=await(await handler(request('/campaigns','POST',brief,{'Idempotency-Key':key}))).json();
  const second=await(await handler(request('/campaigns','POST',brief,{'Idempotency-Key':key}))).json();expect(second).toMatchObject({id:first.id,replayed:true});
  expect((await sb.db.query('select count(*)::int n from campaigns where user_id=$1',[user.id])).rows[0].n).toBe(1);
 });
 it('does not refund a commit after a lost save response; retry returns its pack',async()=>{
  sb.failNextRpc('complete_generation',true);const key=randomUUID();
  expect((await handler(request('/campaigns','POST',brief,{'Idempotency-Key':key}))).status).toBe(503);
  const retry=await(await handler(request('/campaigns','POST',brief,{'Idempotency-Key':key}))).json();expect(retry.replayed).toBe(true);
  expect((await sb.rpc('generation_totals',{p_uid:user.id})).data.campaigns_lifetime).toBe(1);
 });
 it('makes an actual failed save refundable, but the failed request ID cannot run twice',async()=>{
  sb.failNextRpc('complete_generation');const key=randomUUID();expect((await handler(request('/campaigns','POST',brief,{'Idempotency-Key':key}))).status).toBe(503);
  expect((await sb.rpc('generation_totals',{p_uid:user.id})).data.campaigns_lifetime).toBe(0);
  expect((await(await handler(request('/campaigns','POST',brief,{'Idempotency-Key':key}))).json()).code).toBe('ALREADY_FAILED');
  expect((await handler(request('/campaigns','POST',brief))).status).toBe(200);
 });
 it('fails closed on reservation, limiter and circuit-breaker outages',async()=>{
  sb.failNextRpc('reserve_generation');expect((await handler(request('/campaigns','POST',brief))).status).toBe(503);
  rateLimit.mockRejectedValueOnce(Object.assign(new Error('Protection unavailable'),{status:503}));expect((await handler(request('/campaigns','POST',brief))).status).toBe(503);
  process.env.GENERATION_PAUSED='true';expect((await handler(request('/campaigns','POST',brief))).status).toBe(503);
  expect((await sb.rpc('generation_totals',{p_uid:user.id})).data.campaigns_lifetime).toBe(0);
 });
 it('denies a fourth Free run and cannot bypass it by deleting results',async()=>{
  for(let i=0;i<3;i++)expect((await handler(request('/campaigns','POST',brief))).status).toBe(200);
  await sb.db.query('delete from campaigns where user_id=$1',[user.id]);
  const r=await handler(request('/campaigns','POST',brief));expect(r.status).toBe(403);expect((await r.json()).code).toBe('LIMIT_LIFETIME');
 });
 it('rejects bad size/brief/logo/idempotency input rather than silently dropping it',async()=>{
  for(const body of [{...brief,custom_sizes:[{width:300,height:250}]},{...brief,product_name:'x'.repeat(81)},{...brief,custom_sizes:[{preset:'not-a-preset'}]},{...brief,logo:'data:image/svg+xml,<script/>'},{...brief,request_id:'not-uuid'}])expect((await handler(request('/campaigns','POST',body))).status).toBe(400);
 });
 it('honors Agency arbitrary dimensions and does not invent a desktop mirror entitlement',async()=>{
  await sb.db.query("update profiles set plan='agency' where id=$1",[user.id]);const r=await handler(request('/campaigns','POST',{...brief,custom_sizes:[{width:600,height:400}]}));expect(r.status).toBe(200);
  const {id}=await r.json(),c=(await sb.db.query('select files from campaigns where id=$1',[id])).rows[0];expect(c.files.some(f=>f.name==='banner_600x400.svg'&&f.content.includes('width="600" height="400"'))).toBe(true);
 });
 it('does not spend provider capacity for a past-due or deleting account',async()=>{
  await sb.db.query("update profiles set plan='pro',plan_status='past_due' where id=$1",[user.id]);expect((await handler(request('/campaigns','POST',brief))).status).toBe(402);
  await sb.db.query("update profiles set plan_status='active',deletion_pending=true where id=$1",[user.id]);expect((await handler(request('/campaigns','POST',brief))).status).toBe(409);
 });
 it('retrieves more than 50 campaigns, searches and never lists a foreign owner',async()=>{
  for(let i=0;i<55;i++)await sb.db.query('insert into campaigns(user_id,name,product) values($1,$2,$3)',[user.id,'Seed '+String(i).padStart(2,'0'),'Coffee']);
  const other=await sb.user();await sb.db.query("insert into campaigns(user_id,name,product) values($1,'FOREIGN','Secret')",[other.id]);
  const p2=await(await handler(request('/campaigns?page=2'))).json();expect(p2.campaigns).toHaveLength(15);expect(p2.total).toBe(55);expect(p2.has_more).toBe(false);
  const found=await(await handler(request('/campaigns?q=Seed%2000'))).json();expect(found.campaigns).toHaveLength(1);expect(found.campaigns[0].name).toBe('Seed 00');
 });
});
