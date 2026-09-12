import {it,expect,vi,beforeAll,afterAll,beforeEach,afterEach} from 'vitest';
vi.mock('../api/_lib/sb.js',()=>({admin:vi.fn(),json:(b,s=200)=>new Response(JSON.stringify(b),{status:s})}));
import {admin} from '../api/_lib/sb.js';
import handler from '../api/_lib/routes/ops-status.js';
import {database,request} from './helpers/db.js';
let sb;const secret='s'.repeat(40);
beforeAll(async()=>{sb=await database();admin.mockReturnValue(sb);const user=await sb.user();await sb.from('product_feedback').insert({user_id:user.id,usable:true,minutes_saved:12,note:'PRIVATE CUSTOMER NOTE'});},30000);
afterAll(()=>sb.close());beforeEach(()=>{vi.stubEnv('CRON_SECRET',secret);sb.calls.length=0;});afterEach(()=>vi.unstubAllEnvs());
it('refuses anonymous or incorrect credentials and write methods',async()=>{expect((await handler(request('/ops-status'))).status).toBe(401);expect((await handler(request('/ops-status','POST',{}))).status).toBe(405);expect(sb.calls).toHaveLength(0);});
it('returns bounded aggregate data without customer content or mutation',async()=>{
 const response=await handler(request('/ops-status','GET',undefined,{Authorization:'Bearer '+secret}));expect(response.status).toBe(200);const body=await response.json();
 expect(body).toMatchObject({read_only:true,feedback:{sample_size:1,self_reported_usable:1,self_reported_average_minutes_saved:12}});expect(JSON.stringify(body)).not.toContain('PRIVATE CUSTOMER NOTE');expect(sb.calls.every(c=>!c.op||c.op==='select')).toBe(true);expect(sb.calls.filter(c=>c.rpc).map(c=>c.rpc)).toEqual(['generation_health','usage_event_summary']);expect(admin.mock.calls.at(-1)[0].signal).toBeInstanceOf(AbortSignal);
});
