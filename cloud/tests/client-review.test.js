import {it,expect,vi,beforeAll,afterAll,beforeEach,afterEach} from 'vitest';
import {randomUUID,createHash} from 'node:crypto';
vi.mock('../api/_lib/sb.js',()=>({admin:vi.fn(),authUser:vi.fn(),json:(b,s=200)=>new Response(JSON.stringify(b),{status:s})}));
vi.mock('../api/_lib/limit.js',()=>({rateLimit:vi.fn(async()=>true)}));
import {admin,authUser} from '../api/_lib/sb.js';
import {rateLimit} from '../api/_lib/limit.js';
import visitor,{manageReview} from '../api/_lib/routes/campaign-review.js';
import {database,request} from './helpers/db.js';
let sb,user,id;const ctx=()=>({params:{id}});
async function create(){const r=await manageReview(request('/campaigns/'+id+'/review','POST',{revision:1,consent:true,days:7}),ctx());expect(r.status).toBe(200);return (await r.json()).path.split('#')[1];}
const visit=(token,body)=>visitor(request('/review',body?'POST':'GET',body,{Authorization:'Bearer '+token}));
beforeAll(async()=>{sb=await database();admin.mockReturnValue(sb);},30000);afterAll(()=>sb.close());
beforeEach(async()=>{vi.stubEnv('CLIENT_REVIEW_ENABLED','true');rateLimit.mockResolvedValue(true);user=await sb.user();authUser.mockResolvedValue(user);id=randomUUID();await sb.from('campaigns').insert({id,user_id:user.id,name:'Private pack',product:'Coffee',files:[{name:'hero_banner.svg',content:'<svg xmlns="http://www.w3.org/2000/svg"/>'}],copy:'Public to invited reviewers',brief:{secret:'NEVER_SHARE'},provider:'offline',visual_review_state:'unchanged'});});
afterEach(()=>vi.unstubAllEnvs());
it('requires owner authentication, sharing consent and current reviewed version',async()=>{
 authUser.mockResolvedValue(null);expect((await manageReview(request('/campaigns/'+id+'/review'),ctx())).status).toBe(401);authUser.mockResolvedValue(await sb.user());expect((await manageReview(request('/x','POST',{revision:1,days:7,consent:true}),ctx())).status).toBe(404);authUser.mockResolvedValue(user);
 expect((await manageReview(request('/x','POST',{revision:1,days:7}),ctx())).status).toBe(409);
 await sb.from('campaigns').update({visual_review_state:'review_required'}).eq('id',id);expect((await manageReview(request('/x','POST',{revision:1,days:7,consent:true}),ctx())).status).toBe(409);
});
it('stores only a hash and excludes owner identity, prompts and keys from shared content',async()=>{
 const token=await create(),r=await visit(token);expect(r.status).toBe(200);const data=await r.json();expect(data.campaign.copy).toBe('Public to invited reviewers');expect(JSON.stringify(data)).not.toContain('NEVER_SHARE');expect(data.campaign.user_id).toBeUndefined();
 const row=(await sb.from('campaign_review_links').select('*').eq('campaign_id',id).single()).data;expect(row.token_hash).toBe(createHash('sha256').update(token).digest('hex'));expect(JSON.stringify(row)).not.toContain(token);
 expect((await visit('a'.repeat(64))).status).toBe(404);
});
it('comments and decisions are idempotent, bounded and visible to owner only with no workspace mutation',async()=>{
 const token=await create(),body={request_id:randomUUID(),name:'Client',decision:'approved',message:'Use this version'};
 expect((await visit(token,body)).status).toBe(200);expect((await visit(token,body)).status).toBe(200);
 const status=await(await manageReview(request('/x'),ctx())).json();expect(status.review.status).toBe('approved');expect(status.review.comments).toHaveLength(1);
 expect((await visit(token,{...body,message:'Changed under same ID'})).status).toBe(503);
 expect((await visit(token,{...body,request_id:randomUUID(),message:'x'.repeat(1501)})).status).toBe(400);
 const row=(await sb.from('campaigns').select('*').eq('id',id).single()).data;expect(row.revision).toBe(1);expect(row.copy).toBe('Public to invited reviewers');
 authUser.mockResolvedValue(await sb.user());expect((await(await manageReview(request('/x'),ctx())).json()).review).toBeNull();
});
it('revocation, rotation, expiry, campaign changes and account deletion stop access',async()=>{
 const old=await create(),token=await create();expect((await visit(old)).status).toBe(404);
 await manageReview(request('/x','DELETE'),ctx());expect((await visit(token)).status).toBe(404);
 const expired=await create();await sb.from('campaign_review_links').update({expires_at:'2000-01-01T00:00:00Z'}).eq('campaign_id',id);expect((await visit(expired)).status).toBe(404);
 const edited=await create();await sb.from('campaigns').update({revision:2}).eq('id',id);expect((await visit(edited)).status).toBe(404);
 await sb.from('campaigns').update({revision:1}).eq('id',id);const deleting=await create();await sb.from('profiles').update({deletion_pending:true}).eq('id',user.id);expect((await visit(deleting)).status).toBe(404);
});
it('denies direct anonymous/authenticated table access and RPC execution',async()=>{
 for(const role of ['anon','authenticated']){
  expect((await sb.db.query('select has_table_privilege($1,\'public.campaign_review_links\',\'SELECT\') as allowed',[role])).rows[0].allowed).toBe(false);
  expect((await sb.db.query('select has_function_privilege($1,\'public.access_campaign_review(text,jsonb)\',\'EXECUTE\') as allowed',[role])).rows[0].allowed).toBe(false);
 }
});
it('fails closed when disabled or rate limited',async()=>{const token=await create();vi.stubEnv('CLIENT_REVIEW_ENABLED','false');expect((await visit(token)).status).toBe(404);vi.stubEnv('CLIENT_REVIEW_ENABLED','true');rateLimit.mockResolvedValue(false);expect((await visit(token)).status).toBe(429);});
