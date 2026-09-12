import {it,expect,vi,beforeAll,afterAll,beforeEach} from 'vitest';
import {gunzipSync} from 'node:zlib';
vi.mock('../api/_lib/sb.js',()=>({authUser:vi.fn(),admin:vi.fn(),json:(b,s=200)=>new Response(JSON.stringify(b),{status:s})}));
vi.mock('../api/_lib/limit.js',()=>({rateLimit:vi.fn(async()=>true)}));
import {admin,authUser} from '../api/_lib/sb.js';
import route from '../api/_lib/routes/camp-id.js';
import exportRoute from '../api/_lib/routes/me-export.js';
import {database,request} from './helpers/db.js';
import {needsVisualReview,assertVisualReview,visualReviewNote} from '../public/visual-review.js';
let sb,user,id;const headers={'X-Brandforge-Review':'visual-review-v1'};
const files=[{name:'hero.svg',content:'<svg>Original price</svg>'}];
beforeAll(async()=>{sb=await database();admin.mockReturnValue(sb);},30000);
afterAll(()=>sb.close());
beforeEach(async()=>{user=await sb.user();authUser.mockResolvedValue(user);id=(await sb.from('campaigns').insert({user_id:user.id,name:'Coffee',product:'Coffee',copy:'Original price',files}).select('id').single()).data.id;});
const patch=body=>route(request('/campaigns/'+id,'PATCH',body,headers));
const get=async()=>{const r=await route(request('/campaigns/'+id,'GET',undefined,headers));expect(r.status).toBe(200);return r.json();};
it('copy edits mark visuals stale without changing their bytes or consuming allowance',async()=>{
 expect((await patch({revision:1,copy:'New price'})).status).toBe(200);
 const row=await get();expect(row).toMatchObject({revision:2,visual_review_state:'review_required',files,copy:'New price'});expect(needsVisualReview(row)).toBe(true);expect(()=>assertVisualReview(row)).toThrow(/Review/);
 expect((await sb.rpc('generation_totals',{p_uid:user.id})).data).toMatchObject({campaigns_lifetime:0,reserved:0});
});
it.each([{name:'Renamed'},{strategy:'New strategy'},{seo:'New SEO'},{copy:'Original price'}])('non-copy/no-op changes do not newly mark generated visuals stale: %j',async fields=>{
 expect((await patch({revision:1,...fields})).status).toBe(200);expect((await get()).visual_review_state).toBe('unchanged');
});
it('acknowledgment is revision-bound and idempotent, not a file update or certification',async()=>{
 await patch({revision:1,copy:'Changed'});expect((await patch({revision:1,acknowledge_visuals:true})).status).toBe(409);
 expect((await patch({revision:2,acknowledge_visuals:true})).status).toBe(200);const row=await get();
 expect(row).toMatchObject({revision:2,visual_review_state:'review_required',visual_review_ack_revision:2,files});expect(row.visual_review_ack_at).toBeTruthy();expect(needsVisualReview(row)).toBe(false);expect(()=>assertVisualReview(row)).not.toThrow();expect(visualReviewNote(row)).toContain('NOT been redrawn');
 expect(await(await patch({revision:2,acknowledge_visuals:true})).json()).toMatchObject({replayed:true});expect((await get()).visual_review_ack_at).toBe(row.visual_review_ack_at);
 expect(row.revisions).toHaveLength(1);
});
it('any subsequent text version invalidates the prior acknowledgment',async()=>{
 await patch({revision:1,copy:'Changed'});await patch({revision:2,acknowledge_visuals:true});await patch({revision:2,strategy:'Edited strategy'});
 expect(await get()).toMatchObject({revision:3,visual_review_ack_revision:null,visual_review_ack_at:null});expect(needsVisualReview(await get())).toBe(true);
});
it('restore creates a new review-required version; it cannot revive an old approval',async()=>{
 await patch({revision:1,copy:'Changed'});await patch({revision:2,acknowledge_visuals:true});await patch({revision:2,copy:'Changed again'});
 await patch({revision:3,restore_revision:2});const restored=await get();expect(restored).toMatchObject({copy:'Changed',revision:4,visual_review_ack_revision:null,files});expect(needsVisualReview(restored)).toBe(true);
 await patch({revision:4,restore_revision:1});expect(needsVisualReview(await get())).toBe(true);
});
it('acknowledgment cannot be mixed with an edit or performed by another account',async()=>{
 expect((await patch({revision:1,copy:'Other',acknowledge_visuals:true})).status).toBe(400);
 authUser.mockResolvedValue(await sb.user());expect((await patch({revision:1,acknowledge_visuals:true})).status).toBe(404);
 authUser.mockResolvedValue(user);expect((await get()).visual_review_ack_revision).toBeNull();
});
it('old clients cannot fetch stale or acknowledged-stale inline detail without a reload',async()=>{
 await patch({revision:1,copy:'Changed'});
 expect((await route(request('/campaigns/'+id))).status).toBe(409);
 await patch({revision:2,acknowledge_visuals:true});expect((await route(request('/campaigns/'+id))).status).toBe(409);
 expect((await get()).copy).toBe('Changed');
});
it('historical unknown records require review rather than being silently certified',async()=>{
 await sb.from('campaigns').update({visual_review_state:'unknown'}).eq('id',id);
 expect(needsVisualReview(await get())).toBe(true);expect(visualReviewNote(await get())).toContain('unknown');
 await patch({revision:1,acknowledge_visuals:true});expect(needsVisualReview(await get())).toBe(false);
});
it('data portability preserves unreviewed files with a clear archive warning, not forced approval',async()=>{
 await patch({revision:1,copy:'Changed'});expect((await exportRoute(request('/me/export'))).status).toBe(409);
 const r=await exportRoute(request('/me/export','GET',undefined,headers));expect(r.status).toBe(200);
 const data=JSON.parse(gunzipSync(Buffer.from(await r.arrayBuffer())).toString());expect(data.visual_review_required).toEqual([{id,revision:2}]);expect(data.archive_notice).toContain('not a publish-ready');expect(data.data.campaigns[0]).toMatchObject({files,visual_review_ack_revision:null});
});
it('request fields cannot forge a review or clear staleness',async()=>{
 await patch({revision:1,copy:'Changed',visual_review_state:'unchanged',visual_review_ack_revision:2});
 expect(await get()).toMatchObject({visual_review_state:'review_required',visual_review_ack_revision:null});
});
it('missing metadata or stale/missing acknowledgment timestamps fail export review checks',()=>{
 for(const row of [{},{revision:2,visual_review_state:'review_required',visual_review_ack_revision:1,visual_review_ack_at:'now'},{revision:2,visual_review_ack_revision:2}])expect(()=>assertVisualReview(row)).toThrow();
});
it('browser roles cannot acknowledge directly through the database',async()=>{
 const r=await sb.db.query("select has_function_privilege('authenticated','acknowledge_visual_review(uuid,uuid,integer)','EXECUTE') allowed");expect(r.rows[0].allowed).toBe(false);
});

it('database review and edit reject a missing expected revision',async()=>{
 expect((await sb.rpc('acknowledge_visual_review',{p_uid:user.id,p_id:id,p_revision:null})).data.code).toBe('REVISION_CONFLICT');
 expect((await sb.rpc('edit_campaign',{p_uid:user.id,p_id:id,p_revision:null,p_changes:{copy:'Wrong'}})).data.code).toBe('REVISION_CONFLICT');
 expect((await get()).revision).toBe(1);
});
