// Paged portability: no silent Supabase 1000-row truncation or Vercel 4.5MB
// response overflow. Each page includes <=1 full campaign and <=1 brand.
// Key material, signed download links and capability tokens are NEVER exported.
import {admin,authUser,json} from '../sb.js';
import {serve} from '../serve.js';
import {gzipSync} from 'node:zlib';
import {dbCheck} from '../http.js';
async function handle(req){
 if(req.method&&req.method!=='GET')return json({error:'Method not allowed'},405);
 const user=await authUser(req);if(!user)return json({error:'Not signed in'},401);
 const sb=admin();
 try{
  const q=new URL(req.url,'https://brandforge.local').searchParams,page=Math.max(0,Math.min(100000,Number.parseInt(q.get('page')||'0',10)||0));
  const definitions=[['campaigns','*',1],['brand_profiles','*',1],['generation_usage','id,campaign_id,status,units,yyyymm,created_at,completed_at,provider,failure_code',100],['product_feedback','*',100],['billing_subscriptions','id,plan,status,billing_interval,occurred_at',100],['campaign_revisions','*',10]];
  const results=await Promise.all(definitions.map(async([table,cols,size])=>{
   const order=table==='billing_subscriptions'?'occurred_at':'created_at';
   const r=await sb.from(table).select(cols,{count:'exact'}).eq('user_id',user.id).order(order,{ascending:true}).order(table==='campaign_revisions'?'campaign_id':'id',{ascending:true}).range(page*size,page*size+size-1);
   return {table,data:dbCheck(r)||[],has_more:(page+1)*size<(r.count||0),total:r.count||0};
  }));
  const profile=page===0?dbCheck(await sb.from('profiles').select('*').eq('id',user.id).single()):undefined;
  const payload={schema:2,page,export_date:new Date().toISOString(),user:page===0?{id:user.id,email:user.email,profile}:undefined,data:Object.fromEntries(results.map(r=>[r.table,r.data])),totals:Object.fromEntries(results.map(r=>[r.table,r.total])),has_more:results.some(r=>r.has_more),next_page:results.some(r=>r.has_more)?page+1:null,note:'Repeat with next_page until has_more is false. BYOK secrets are intentionally excluded. Paddle invoices are available in Manage billing.'};
  return new Response(gzipSync(JSON.stringify(payload)),{headers:{'Content-Type':'application/json','Content-Encoding':'gzip','Cache-Control':'no-store'}});
 }catch(e){return json({error:e.status?e.message:'Could not export account data.'},e.status||503);}
}
const h=serve(handle);export default h;export const GET=h;
