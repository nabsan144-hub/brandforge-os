import {describe,it,expect,vi,beforeAll,afterAll} from 'vitest';
import {gunzipSync} from 'node:zlib';
vi.mock('../api/_lib/sb.js',()=>({authUser:vi.fn(),admin:vi.fn(),json:(b,s=200)=>new Response(JSON.stringify(b),{status:s})}));
import {admin,authUser} from '../api/_lib/sb.js';
import handler from '../api/_lib/routes/me-export.js';
import {database,request} from './helpers/db.js';
let sb,user;
beforeAll(async()=>{sb=await database();user=await sb.user();admin.mockReturnValue(sb);},30000);afterAll(()=>sb.close());
async function data(page=0){const r=await handler(request('/me/export?page='+page));expect(r.status).toBe(200);return JSON.parse(gunzipSync(Buffer.from(await r.arrayBuffer())).toString());}
describe('paged account portability',()=>{
 it('requires authentication',async()=>{authUser.mockResolvedValue(null);expect((await handler(request('/me/export'))).status).toBe(401);});
 it('exports full records across pages, omits keys and performs no writes',async()=>{
  authUser.mockResolvedValue(user);for(let i=0;i<3;i++)await sb.db.query("insert into campaigns(user_id,name,product,copy) values($1,$2,'Coffee','Complete copy')",[user.id,'Export '+i]);
  const first=await data();expect(first.user.email).toBe(user.email);expect(first.data.campaigns).toHaveLength(1);expect(first.has_more).toBe(true);expect(first.next_page).toBe(1);
  const last=await data(2);expect(last.has_more).toBe(false);expect(last.data.campaigns[0].copy).toBe('Complete copy');
  expect(Object.hasOwn(first.data,'user_api_keys')).toBe(false);expect(sb.calls.every(c=>!c.op||c.op==='select')).toBe(true);
 });
 it('does not export another user’s campaigns',async()=>{const other=await sb.user();authUser.mockResolvedValue(other);expect((await data()).data.campaigns).toHaveLength(0);});
});
