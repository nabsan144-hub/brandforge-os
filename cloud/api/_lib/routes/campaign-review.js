import {randomBytes,createHash} from 'node:crypto';
import {admin,authUser,json} from '../sb.js';
import {serve} from '../serve.js';
import {UUID,readJson,clean,HttpError,dbCheck} from '../http.js';
import {boundedJson} from '../payload.js';
import {rateLimit} from '../limit.js';
import {authorizeBundle} from '../assets.js';
const hash=s=>createHash('sha256').update(s).digest('hex');
const enabled=()=>process.env.CLIENT_REVIEW_ENABLED==='true';
async function owner(req,ctx){
 const user=await authUser(req);if(!user)return json({error:'Not signed in'},401);
 try{
  const id=ctx?.params?.id;if(!UUID.test(id||''))throw new HttpError(404,'Campaign not found');
  const sb=admin({signal:AbortSignal.timeout(12000)});
  if(req.method==='GET'){
   const row=dbCheck(await sb.from('campaign_review_links').select('revision,expires_at,revoked_at,status,comments,created_at').eq('campaign_id',id).eq('user_id',user.id).maybeSingle());
   return json({review:row,enabled:enabled()});
  }
  if(!['POST','DELETE'].includes(req.method))throw new HttpError(405,'Method not allowed');
  if(!await rateLimit('review-manage',user.id,30,3600))throw new HttpError(429,'Review link safety limit reached.');
  const b=req.method==='DELETE'?{}:await readJson(req,2000);
  if(req.method==='POST'&&(!enabled()||b.consent!==true))throw new HttpError(409,'Enable client review and confirm that the entire pack may be shared.');
  if(req.method==='POST'&&(!Number.isInteger(b.revision)||![1,7,30].includes(b.days)))throw new HttpError(400,'Choose a current revision and 1, 7 or 30 day expiry.');
  const token=req.method==='POST'?randomBytes(32).toString('hex'):null;
  const result=dbCheck(await sb.rpc('manage_campaign_review',{p_uid:user.id,p_id:id,p_revision:b.revision||0,p_hash:token?hash(token):null,p_days:b.days||1}));
  if(!result.ok)throw new HttpError(result.code==='NOT_FOUND'?404:409,'Review links require the current, reviewed campaign version.',result.code);
  // A fragment is not sent in HTTP requests or referrers. Raw token is shown once.
  return json({...result,...(token?{path:'/review#'+token}:{}),notice:'Anyone with this link can view and save the entire pack, comment and record a decision. Names are self-reported, not verified identities. Editing the campaign invalidates this link; a new link replaces prior responses.'});
 }catch(e){return json({error:e.status?e.message:'Review link operation could not be confirmed.',code:e.code},e.status||503);}
}
async function visitor(req){
 try{
  if(!['GET','POST'].includes(req.method))throw new HttpError(405,'Method not allowed');
  if(!enabled())throw new HttpError(404,'Review is unavailable.');
  const token=(req.headers.get('authorization')||'').replace(/^Bearer /,'');
  if(!/^[a-f0-9]{64}$/.test(token))throw new HttpError(404,'Review unavailable, expired or replaced.');
  const key=hash(token);if(!await rateLimit('review-visit',key,120,3600))throw new HttpError(429,'Review safety limit reached. Retry later.');
  let comment=null;
  if(req.method==='POST'){
   const b=await readJson(req,6000);
   if(!UUID.test(b.request_id||'')||!['comment','approved','changes_requested'].includes(b.decision)||typeof b.name!=='string'||!b.name.trim()||b.name.length>80||typeof b.message!=='string'||b.message.length>1500)throw new HttpError(400,'Supply a name, supported decision and a comment up to 1500 characters.');
   comment={request_id:b.request_id,name:clean(b.name,80),message:clean(b.message,1500),decision:b.decision};
  }
  const sb=admin({signal:AbortSignal.timeout(12000)}),data=dbCheck(await sb.rpc('access_campaign_review',{p_hash:key,p_comment:comment}));
  if(!data.ok)throw new HttpError(404,'Review unavailable, expired, revoked or replaced by a newer campaign version.');
  if(new URL(req.url).searchParams.get('files')==='1'){
   if(req.method!=='GET')throw new HttpError(405,'Method not allowed');
   // Owner ID is fetched only server-side, after scoped token authorization.
   const row=dbCheck(await sb.from('campaign_review_links').select('user_id').eq('token_hash',key).single());
   const internal=new Request(req.url,{headers:{'x-brandforge-client':'asset-bundle-v1','x-brandforge-review':'visual-review-v1','x-brandforge-visuals':'vector-corrections-v1'}});
   return json({...await authorizeBundle(sb,row.user_id,data.campaign.id,internal,{revision:data.campaign.revision,bundle:data.campaign.asset_bundle_id}),storage_origin:new URL(process.env.SUPABASE_URL).origin});
  }
  return boundedJson(data);
 }catch(e){return json({error:e.status?e.message:'Review could not be loaded or response confirmed. Retry the unchanged response.',code:e.code},e.status||503);}
}
export const manageReview=serve(owner);
export default serve(visitor);
