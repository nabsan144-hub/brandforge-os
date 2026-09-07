import {describe,it,expect,vi,beforeAll,afterAll,beforeEach} from 'vitest';
vi.mock('../api/_lib/sb.js',()=>({authUser:vi.fn(),admin:vi.fn(),json:(b,s=200)=>new Response(JSON.stringify(b),{status:s})}));
import {admin,authUser} from '../api/_lib/sb.js';
import handler from '../api/_lib/routes/me.js';
import {database,request} from './helpers/db.js';
let sb,user;
beforeAll(async()=>{sb=await database();admin.mockReturnValue(sb);},30000);afterAll(()=>sb.close());beforeEach(async()=>{user=await sb.user();authUser.mockResolvedValue(user);});
describe('account usage and deletion',()=>{
 it('requires authentication',async()=>{authUser.mockResolvedValue(null);expect((await handler(request('/me'))).status).toBe(401);});
 it('reports immutable usage, not a count of surviving content',async()=>{await sb.db.query("insert into generation_usage(id,user_id,input_hash,status,yyyymm,units) values(gen_random_uuid(),$1,'legacy','completed',to_char(now(),'YYYYMM'),3)",[user.id]);const d=await(await handler(request('/me'))).json();expect(d.usage.campaigns_lifetime).toBe(3);expect(d.plan).toBe('free');});
 it('requires explicit confirmation of immediate billing cancellation',async()=>{expect((await handler(request('/me','DELETE',{}))).status).toBe(400);expect((await sb.db.query('select id from profiles where id=$1',[user.id])).rows).toHaveLength(1);});
 it('deletes a free account with no billing relationship',async()=>{const r=await handler(request('/me','DELETE',{confirm:'DELETE AND CANCEL BILLING'}));expect(r.status).toBe(200);expect((await sb.db.query('select id from auth.users where id=$1',[user.id])).rows).toHaveLength(0);});
 it('does not destroy an identity while billing is uncertain',async()=>{await sb.rpc('begin_checkout',{p_uid:user.id,p_plan:'pro',p_interval:'month'});expect((await handler(request('/me','DELETE',{confirm:'DELETE AND CANCEL BILLING'}))).status).toBe(409);const p=(await sb.db.query('select deletion_pending from profiles where id=$1',[user.id])).rows[0];expect(p.deletion_pending).toBe(true);});
 it('keeps data when billing provider confirmation is unavailable',async()=>{await sb.db.query("update profiles set paddle_customer_id='ctm_00000000000000000000000001' where id=$1",[user.id]);delete process.env.PADDLE_API_KEY;expect((await handler(request('/me','DELETE',{confirm:'DELETE AND CANCEL BILLING'}))).status).toBe(503);expect((await sb.db.query('select id from auth.users where id=$1',[user.id])).rows).toHaveLength(1);});
});
