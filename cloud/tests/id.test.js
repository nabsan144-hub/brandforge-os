import {describe,it,expect,vi,beforeAll,afterAll,beforeEach} from 'vitest';
import {randomUUID} from 'node:crypto';
vi.mock('../api/_lib/sb.js',()=>({authUser:vi.fn(),admin:vi.fn(),json:(b,s=200)=>new Response(JSON.stringify(b),{status:s})}));
vi.mock('../api/_lib/limit.js',()=>({rateLimit:vi.fn(async()=>true)}));
import {admin,authUser} from '../api/_lib/sb.js';
import handler from '../api/_lib/routes/camp-id.js';
import {database,request} from './helpers/db.js';
let sb,user,id;
beforeAll(async()=>{sb=await database();admin.mockReturnValue(sb);},30000);afterAll(()=>sb.close());
beforeEach(async()=>{user=await sb.user();authUser.mockResolvedValue(user);id=randomUUID();await sb.db.query("insert into campaigns(id,user_id,name,product,copy) values($1,$2,'Example','Coffee','Original copy')",[id,user.id]);sb.calls.length=0;});
describe('campaign ownership, editing and non-refunding deletion',()=>{
 it('requires auth and handles relative URLs/context IDs',async()=>{authUser.mockResolvedValue(null);expect((await handler(request('/campaigns/'+id))).status).toBe(401);authUser.mockResolvedValue(user);expect((await(await handler({url:'/api/campaigns/'+randomUUID()},{params:{id}})).json()).id).toBe(id);});
 it('denies foreign reads/edits and supports only documented methods',async()=>{authUser.mockResolvedValue(await sb.user());expect((await handler(request('/campaigns/'+id))).status).toBe(404);expect((await handler(request('/campaigns/'+id,'PATCH',{revision:1,copy:'Attack'}))).status).toBe(404);authUser.mockResolvedValue(user);expect((await handler(request('/campaigns/'+id,'POST',{}))).status).toBe(405);});
 it('deletes content idempotently, never invoking a refund RPC',async()=>{for(let i=0;i<2;i++)expect((await handler(request('/campaigns/'+id,'DELETE'))).status).toBe(200);expect((await handler(request('/campaigns/'+randomUUID(),'DELETE'))).status).toBe(200);expect(sb.calls.some(c=>c.rpc)).toBe(false);});
 it('cannot delete a foreign campaign',async()=>{authUser.mockResolvedValue(await sb.user());expect((await handler(request('/campaigns/'+id,'DELETE'))).status).toBe(200);expect((await sb.db.query('select id from campaigns where id=$1',[id])).rows).toHaveLength(1);});
 it('saves a revision, detects a conflict, and restores without losing history',async()=>{
  expect((await handler(request('/campaigns/'+id,'PATCH',{revision:1,copy:'Edited copy'}))).status).toBe(200);
  expect((await handler(request('/campaigns/'+id,'PATCH',{revision:1,copy:'Lost edit'}))).status).toBe(409);
  const d=await(await handler(request('/campaigns/'+id,'GET',undefined,{'X-Brandforge-Review':'visual-review-v1'}))).json();expect(d.copy).toBe('Edited copy');expect(d.revisions).toHaveLength(1);
  expect((await handler(request('/campaigns/'+id,'PATCH',{revision:2,restore_revision:1}))).status).toBe(200);
  expect((await(await handler(request('/campaigns/'+id,'GET',undefined,{'X-Brandforge-Review':'visual-review-v1'}))).json()).copy).toBe('Original copy');
 });
 it('rejects oversized edits without modifying the document',async()=>{expect((await handler(request('/campaigns/'+id,'PATCH',{revision:1,copy:'a'.repeat(20001)}))).status).toBe(400);expect((await(await handler(request('/campaigns/'+id,'GET',undefined,{'X-Brandforge-Review':'visual-review-v1'}))).json()).revision).toBe(1);});
});
