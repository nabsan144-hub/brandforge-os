import {it,expect,vi,beforeAll,afterAll,beforeEach} from 'vitest';
import {randomBytes} from 'node:crypto';
vi.mock('../api/_lib/sb.js',()=>({authUser:vi.fn(),admin:vi.fn(),json:(b,s=200)=>new Response(JSON.stringify(b),{status:s,headers:{'Content-Type':'application/json'}})}));
vi.mock('../api/_lib/limit.js',()=>({rateLimit:vi.fn(async()=>true)}));
vi.mock('../api/_lib/keys.js',()=>({resolveCampaignKeys:vi.fn(async()=>({key_source:'offline'}))}));
vi.mock('../api/_lib/engine.js',async()=>({...await vi.importActual('../api/_lib/engine.js'),runCampaign:vi.fn()}));
import {admin,authUser} from '../api/_lib/sb.js';
import {runCampaign} from '../api/_lib/engine.js';
import create from '../api/_lib/routes/campaigns.js';
import detail from '../api/_lib/routes/camp-id.js';
import accountExport from '../api/_lib/routes/me-export.js';
import {database,request} from './helpers/db.js';
let sb,user;
beforeAll(async()=>{sb=await database();admin.mockReturnValue(sb);},30000);
afterAll(async()=>{await sb.close();});
beforeEach(async()=>{user=await sb.user();authUser.mockResolvedValue(user);sb.calls.length=0;});
it('oversized complete pack fails before save, without consuming allowance',async()=>{
 runCampaign.mockResolvedValue({provider:'offline',files:[{name:'hero.svg',content:'a'.repeat(3_010_000)}]});
 const response=await create(request('/campaigns','POST',{product_name:'Coffee',provider:'offline'}));
 expect(response.status).toBe(413);expect(await response.json()).toMatchObject({code:'CAMPAIGN_PAYLOAD_LIMIT',retry_with_new_request:true});
 expect(sb.calls.some(c=>c.rpc==='complete_generation')).toBe(false);
 expect((await sb.rpc('generation_totals',{p_uid:user.id})).data).toMatchObject({campaigns_lifetime:0,reserved:0});
 expect((await sb.from('campaigns').select('*').eq('user_id',user.id)).data).toHaveLength(0);
});
it('an oversized legacy row returns a bounded error only to its owner',async()=>{
 const old=(await sb.from('campaigns').insert({user_id:user.id,name:'Legacy',product:'Coffee',files:[{name:'old.svg',content:'x'.repeat(4_100_000)}]}).select('id').single()).data;
 const r=await detail(request('/campaigns/'+old.id));expect(r.status).toBe(413);expect(await r.json()).toMatchObject({code:'LEGACY_PAYLOAD_LIMIT'});
 authUser.mockResolvedValue(await sb.user());expect((await detail(request('/campaigns/'+old.id))).status).toBe(404);
 expect((await sb.from('campaigns').select('id').eq('id',old.id)).data).toHaveLength(1);
});
it('large high-entropy legacy account exports fail with a controlled support path',async()=>{
 const content=randomBytes(4_200_000).toString('base64');
 await sb.from('campaigns').insert({user_id:user.id,name:'Legacy high entropy',product:'Coffee',files:[{name:'old.svg',content}]});
 const r=await accountExport(request('/me/export'));expect(r.status).toBe(413);
 expect(await r.json()).toMatchObject({code:'EXPORT_PAYLOAD_LIMIT'});
 expect((await sb.from('campaigns').select('id').eq('user_id',user.id)).data).toHaveLength(1);
});
