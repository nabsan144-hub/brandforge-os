import {requireVisualReviewClient,needsVisualReview} from '../visual-review.js';
import {requireAssetClient} from '../assets.js';
// Paged portability: no silent Supabase 1000-row truncation or Vercel 4.5MB
// response overflow. Each page includes <=1 full campaign and <=1 brand.
// Key material, signed download links and capability tokens are NEVER exported.
import {admin,authUser,json} from '../sb.js';
import {serve} from '../serve.js';
import {gzipSync} from 'node:zlib';
import {dbCheck,HttpError} from '../http.js';
import {MAX_FUNCTION_BODY_BYTES} from '../payload.js';
async function handle(req){
 if(req.method&&req.method!=='GET')return json({error:'Method not allowed'},405);
 const user=await authUser(req);if(!user)return json({error:'Not signed in'},401);
 const sb=admin();
 try{
  const q=new URL(req.url,'https://brandforge.local').searchParams,page=Math.max(0,Math.min(100000,Number.parseInt(q.get('page')||'0',10)||0));
  if(q.get('kind')==='canvas'){
   const pageData=dbCheck(await sb.rpc('export_canvas_page',{p_uid:user.id,p_page:page}));
   const payload={schema:2,page,kind:'canvas',...pageData,next_kind:pageData.has_more?'canvas':null,note:'Editable canvas sources and retained versions. Account IDs/approval state are not portable editor grants.'};
   return new Response(gzipSync(JSON.stringify(payload)),{headers:{'Content-Type':'application/json','Content-Encoding':'gzip','Cache-Control':'no-store'}});
  }
  const hasCanvas=(dbCheck(await sb.from('canvas_projects').select('id').eq('user_id',user.id).limit(1))||[]).length>0;
  if(hasCanvas&&req.headers.get('x-brandforge-canvas')!=='canvas-v1')throw new HttpError(409,'Reload the workspace before exporting; this account includes editable canvas projects.','CANVAS_EXPORT_CLIENT_REQUIRED');
  const definitions=[['campaign_image_jobs','id,campaign_id,source_revision,result_revision,status,failure_code,expires_at,created_at',30],['campaign_transfers','id,name,pack,created_at',1],['campaign_review_links','id,campaign_id,revision,expires_at,revoked_at,status,comments,created_at',10],['campaigns','*',1],['brand_profiles','*',1],['generation_usage','id,campaign_id,status,units,yyyymm,created_at,completed_at,provider,failure_code',100],['product_feedback','*',100],['billing_subscriptions','id,plan,status,billing_interval,occurred_at',100],['campaign_revisions','*',10],['campaign_visual_versions','*',1]];
  const results=await Promise.all(definitions.map(async([table,cols,size])=>{
   const order=table==='billing_subscriptions'?'occurred_at':'created_at';
   const r=await sb.from(table).select(cols,{count:'exact'}).eq('user_id',user.id).order(order,{ascending:true}).order(table==='campaign_revisions'?'campaign_id':'id',{ascending:true}).range(page*size,page*size+size-1);
   return {table,data:dbCheck(r)||[],has_more:(page+1)*size<(r.count||0),total:r.count||0};
  }));
  const exportCampaigns=results.find(r=>r.table==='campaigns').data;
  for(const c of exportCampaigns)requireVisualReviewClient(req,c);
  const visual_review_required=exportCampaigns.filter(needsVisualReview).map(c=>({id:c.id,revision:c.revision}));
  if(results.find(r=>r.table==='campaigns').data.some(c=>c.asset_bundle_id))requireAssetClient(req);
  const profile=page===0?dbCheck(await sb.from('profiles').select('*').eq('id',user.id).single()):undefined;
  const payload={schema:2,page,visual_review_required,archive_notice:'Account archive, not a publish-ready campaign pack. Visual review state is included; copy edits do not redraw visuals.',export_date:new Date().toISOString(),user:page===0?{id:user.id,email:user.email,profile}:undefined,data:Object.fromEntries(results.map(r=>[r.table,r.data])),totals:Object.fromEntries(results.map(r=>[r.table,r.total])),has_more:results.some(r=>r.has_more),next_page:results.some(r=>r.has_more)?page+1:null,note:'Repeat with next_page until has_more is false. BYOK secrets are intentionally excluded. Paddle invoices are available in Manage billing.'};
  if(!payload.has_more&&hasCanvas){payload.has_more=true;payload.next_page=0;payload.next_kind='canvas';}else payload.next_kind='account';
  const compressed=gzipSync(JSON.stringify(payload));
  if(compressed.byteLength>MAX_FUNCTION_BODY_BYTES)throw new HttpError(413,'This export page needs an offline support export. Your saved content has not changed.','EXPORT_PAYLOAD_LIMIT');
  return new Response(compressed,{headers:{'Content-Type':'application/json','Content-Encoding':'gzip','Cache-Control':'no-store'}});
 }catch(e){return json({error:e.status?e.message:'Could not export account data.',code:e.code},e.status||503);}
}
const h=serve(handle);export default h;export const GET=h;
