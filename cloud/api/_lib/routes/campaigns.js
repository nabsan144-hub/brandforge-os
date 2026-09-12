import {validateReferenceImages} from '../visuals_ai.js';
import {COMPOSITION_STYLES,chooseComposition} from '../composition-vector.js';
import {photoInput,normalizeProductPhoto} from '../product-photo.js';
import {prepareAssetStorage,externalizeCampaign} from '../assets.js';
import { admin, authUser, json } from '../sb.js';
import { PLANS, runCampaign, AD_SIZES } from '../engine.js';
import { resolveCampaignKeys } from '../keys.js';
import { pickLang } from '../i18n.js';
import { rateLimit } from '../limit.js';
import { serve,requestStartedAt } from '../serve.js';
import { readJson, clean, safeHex, safeLogo, safeUrl, UUID, HttpError, dbCheck } from '../http.js';
import {validateVisualText} from '../visuals.js';
import {reserveOperatorBudget} from '../cost.js';
import {resolveVisualPlan} from '../visual-plan.js';
import {assertCampaignPayload} from '../payload.js';
import { randomUUID, createHash } from 'node:crypto';

export function clientIp(req) {
 const get=n=>req.headers?.get?.(n)||'';
 // Requires a trusted proxy that overwrites/appends its client address.
 // Never use the attacker-controlled first forwarded-for hop.
 return (get('x-vercel-forwarded-for') || get('x-real-ip') || get('x-forwarded-for')).split(',').pop()?.trim() || 'unknown';
}
export function campaignInput(body, plan) {
 if(body.style==='auto-v1')body={...body,style:chooseComposition(body)};
 for(const [field,max] of Object.entries({product_name:80,industry:80,audience:120,benefits:500,name:80,offer:200,cta:40,url:500,tone:120,proof:500,avoided:500,visual_model:128})){
  if(body[field]!==undefined && (typeof body[field]!=='string'||body[field].length>max)) throw new HttpError(400,`${field} must be text of at most ${max} characters.`);
 }
 if(body.visuals_ai!==undefined && typeof body.visuals_ai!=='boolean')throw new HttpError(400,'Image consent must be true or false.');
 if(body.visual_provider!==undefined && !['gemini','openai','xai',''].includes(body.visual_provider))throw new HttpError(400,'Choose a supported image provider.');
 if(body.artwork_mode!==undefined&&!['campaign','legacy'].includes(body.artwork_mode))throw new HttpError(400,'Choose a supported artwork mode.');
 if(body.reference_consent!==undefined&&typeof body.reference_consent!=='boolean')throw new HttpError(400,'Reference consent must be a boolean.');
 if(body.artwork_mode==='campaign'&&body.visuals_ai!==true)throw new HttpError(400,'AI campaign mode requires explicit image-generation consent.');
 if(body.artwork_mode==='campaign'&&(body.product_image||body.logo)&&body.reference_consent!==true)throw new HttpError(400,'Confirm sharing the supplied images with the selected provider.','VISUAL_REFERENCE_CONSENT_REQUIRED');
 const product_image=photoInput(body);
 if(body.style==='product-v1'&&!product_image)throw new HttpError(400,'Product-first needs your approved product photograph.');
 if(body.style==='offer-v1'&&!String(body.offer||'').trim())throw new HttpError(400,'Offer-first needs an offer and its important conditions.');
 if(body.style==='evidence-v1'&&!String(body.proof||'').trim())throw new HttpError(400,'Evidence-first needs supplied proof you are authorized to use.');
 const sizes=[];
 if(body.custom_sizes!==undefined && !Array.isArray(body.custom_sizes)) throw new HttpError(400,'Custom sizes must be a list.');
 if((body.custom_sizes||[]).length>plan.custom_presets) throw new HttpError(400,`This plan allows ${plan.custom_presets} selected sizes per run.`);
 for(const x of body.custom_sizes||[]) {
  if(!x || typeof x!=='object') throw new HttpError(400,'Invalid banner size.');
  const preset=String(x.preset||'');
  if(AD_SIZES[preset]) sizes.push({preset,width:AD_SIZES[preset][0],height:AD_SIZES[preset][1]});
  else if(plan.custom_any && Number.isInteger(x.width) && Number.isInteger(x.height) && x.width>=50 && x.width<=5000 && x.height>=50 && x.height<=5000) sizes.push({preset:'',width:x.width,height:x.height});
  else throw new HttpError(400,'Choose a listed preset, or use Agency for custom dimensions (50–5000 pixels).');
 }
 if(product_image&&sizes.length>3)throw new HttpError(400,'Product photos support up to three selected sizes plus the hero. Choose fewer formats.');
 if(!sizes.length) for(const preset of (product_image?['instagram_square','fb_story','fb_feed']:Object.keys(AD_SIZES)).slice(0,product_image?Math.min(3,plan.custom_presets):plan.custom_presets)) sizes.push({preset,width:AD_SIZES[preset][0],height:AD_SIZES[preset][1]});
 if(body.artwork_mode==='campaign'){
  if(body.generate_new_logo===true||(body.custom_sizes||[]).length)throw new HttpError(400,'AI campaigns include hero, square and story artwork. Separate logo concepts and additional sizes use Basic layouts.');
  if(plan.watermark)throw new HttpError(403,'AI campaign artwork is available on configured paid plans.','PAID_PLAN_REQUIRED');
  if(body.provider==='offline')throw new HttpError(400,'No-AI mode cannot request AI campaign artwork.');
  sizes.splice(0,sizes.length,{preset:'instagram_square',width:1080,height:1080},{preset:'fb_story',width:1080,height:1920});
 }
 const input={
  ...(body.artwork_mode==='campaign'?{artwork_mode:'campaign',reference_consent:body.reference_consent===true}:{}),
  visual_requested:body.visuals_ai===true,visuals_ai:body.visuals_ai===true && !plan.watermark && body.provider!=='offline',visual_provider:body.visual_provider||'',...(body.visual_model?{visual_model:body.visual_model}:{}),
  product:clean(body.product_name,80),industry:clean(body.industry,80)||'General',audience:clean(body.audience,120)||'your customers',
  benefits:clean(body.benefits,500)||'quality, clear information',lang:pickLang(body.lang),primary:safeHex(body.primary_color),secondary:safeHex(body.secondary_color,'#0F172A'),
  custom_sizes:sizes,custom_presets:plan.custom_presets,custom_any:plan.custom_any,watermark:plan.watermark,
  offer:clean(body.offer,200),cta:clean(body.cta,40),url:safeUrl(body.url),tone:clean(body.tone,120),proof:clean(body.proof,500),avoided:clean(body.avoided,500),
  logo:safeLogo(body.logo),generate_new_logo:body.generate_new_logo===true,provider:body.provider||'auto',brand_id:UUID.test(body.brand_id||'')?body.brand_id:null,style:['essential','editorial-v1',...COMPOSITION_STYLES].includes(body.style)?body.style:'bold',
 };
 if(!['auto','offline','groq','gemini'].includes(input.provider)) throw new HttpError(400,'Choose a supported provider.');
 if(body.style!==undefined&&!['bold','essential','editorial-v1',...COMPOSITION_STYLES].includes(body.style)) throw new HttpError(400,'Choose a supported visual style.');
 if(!input.product) throw new HttpError(400,'Enter a product or brand name.');
 if(product_image)Object.assign(input,{product_image,product_image_rights:true});
 return input;
}
async function handle(req) {
 const deadline=requestStartedAt(req)+55000,signal=AbortSignal.any([req.signal,AbortSignal.timeout(Math.max(1,deadline-Date.now()))].filter(Boolean));
 const user=await authUser(req,{signal});
 if(!user) return json({error:'Not signed in'},401);
 const sb=admin({signal});
 let reservation=null;
 try {
  if(req.method==='GET') {
   const q=new URL(req.url,'https://brandforge.local').searchParams;
   const page=Math.max(0,Math.min(100000,Number.parseInt(q.get('page')||'0',10)||0)),size=20;
   const search=clean(q.get('q'),80).replace(/[%_\\]/g,'');
   let query=sb.from('campaigns').select('id,name,product,provider,research_live,created_at,revision,stage_status',{count:'exact'}).eq('user_id',user.id);
   if(search) query=query.ilike('name',`%${search}%`);
   const r=await query.order('created_at',{ascending:false}).order('id',{ascending:false}).range(page*size,page*size+size-1);
   return json({campaigns:dbCheck(r)||[],page,page_size:size,total:r.count||0,has_more:(page+1)*size<(r.count||0)});
  }
  if(req.method!=='POST') return json({error:'Method not allowed'},405);
  const body=await readJson(req,750000,{signal});
  const profile=dbCheck(await sb.from('profiles').select('plan,plan_status,deletion_pending').eq('id',user.id).single(),'Could not load your plan.');
  if(profile?.deletion_pending) throw new HttpError(409,'Account deletion is pending. Retry deletion from Settings.');
  if(profile?.plan_status==='past_due') throw new HttpError(402,'Update your payment method before generating. Your existing work remains available.','PAYMENT_PAST_DUE');
  const plan=PLANS[profile?.plan]||PLANS.free;
  const input=campaignInput(body,plan);
  if(input.product_image){
   if(!await rateLimit('product-photo',user.id,30,3600,{signal}))throw new HttpError(429,'Product photo processing limit reached. Retry later.');
   input.product_image=await normalizeProductPhoto(input.product_image);
  }
  if(input.artwork_mode==='campaign')await validateReferenceImages([input.product_image,input.logo].filter(Boolean));
  else validateVisualText(input);
  if(input.brand_id){const own=dbCheck(await sb.from('brand_profiles').select('id').eq('id',input.brand_id).eq('user_id',user.id).maybeSingle());if(!own)throw new HttpError(400,'Choose a saved brand from your own workspace.');}
  const name=clean(body.name,80)||`${input.product} Campaign`;
  const id=req.headers?.get?.('idempotency-key')||body.request_id||randomUUID();
  if(!UUID.test(id)) throw new HttpError(400,'Request ID must be a UUID.');
  const hash=createHash('sha256').update(JSON.stringify({input,name})).digest('hex');
  // Authenticated users are limited individually. No 30/day office-wide cap.
  // These count attempts, including failures; the ledger counts consumed runs.
  if(!await rateLimit('gen-attempt',user.id,100,86400,{signal})) throw new HttpError(429,'Daily attempt limit reached. Try tomorrow.','LIMIT_ATTEMPTS');
  const reserve=dbCheck(await sb.rpc('reserve_generation',{p_uid:user.id,p_id:id,p_hash:hash,p_lifetime_limit:plan.lifetime,p_monthly_limit:plan.monthly,p_daily_limit:plan.daily,p_concurrency:plan.concurrency}));
  if(!reserve?.ok) {
   if(reserve?.code==='ALREADY_COMPLETED') return reserve.campaign_id?json({id:reserve.campaign_id,replayed:true}):json({error:'This request completed, but its campaign was deleted.',code:'CAMPAIGN_DELETED'},410);
   const messages={LIMIT_LIFETIME:'Your 3 lifetime campaigns have been used. Deleting content does not reset usage.',LIMIT_MONTHLY:`Monthly allowance reached (${plan.monthly}).`,LIMIT_DAILY:`Daily safety limit reached (${plan.daily}).`,LIMIT_CONCURRENT:'A generation is already running. Wait for it to finish.',ALREADY_FAILED:'The previous request failed without consuming an allowance. Click Create again to start a new request.',ALREADY_RESERVED:'This request is still running. Check History before trying again.',IDEMPOTENCY_CONFLICT:'This request ID belongs to a different brief.'};
   throw new HttpError(['LIMIT_LIFETIME','LIMIT_MONTHLY'].includes(reserve?.code)?403:reserve?.code?.startsWith('LIMIT_')?429:409,messages[reserve?.code]||'Generation could not be reserved.',reserve?.code||'RESERVATION_FAILED');
  }
  reservation=id;
  if(process.env.GENERATION_PAUSED==='true') throw new HttpError(503,'Generation is temporarily paused by the operator. No allowance was consumed.','GENERATION_PAUSED');
  const budget=Math.max(1,Math.min(10000,Number(process.env.GENERATION_DAILY_BUDGET)||500));
  if(!await rateLimit('gen-global','deployment',budget,86400,{signal})) throw new HttpError(503,'The service daily capacity has been reached. No allowance was consumed.','CAPACITY_REACHED');
  // Replay a completed request before checking current provider configuration.
  // Existing results remain recoverable after an operator provider change.
  const assetBucket=await prepareAssetStorage(sb,req);
  const visualPlan=resolveVisualPlan(input);
  const keys=await resolveCampaignKeys(sb,user.id,input.provider);
  await reserveOperatorBudget(sb,id,keys,visualPlan);
  const onProgress=async(p_stage,p_state)=>{try{await admin({signal:AbortSignal.any([signal,AbortSignal.timeout(1200)])}).rpc('set_generation_progress',{p_uid:user.id,p_id:id,p_stage,p_state});}catch{/* Progress failure does not release or duplicate this request. */}};
  const result=await runCampaign(input,{...keys,visualPlan,productPhoto:input.product_image,onProgress,deadline,signal});
  if(!Array.isArray(result?.files) || !result.files.length) throw new Error('Invalid engine result');
  let campaign={...result,name,product:input.product,industry:input.industry,audience:input.audience,benefits:input.benefits,lang:input.lang,brief:input,stage_status:result.stage_status||{},key_source:keys.key_source};
  campaign=await externalizeCampaign(sb,user.id,id,campaign,assetBucket);
  assertCampaignPayload(campaign); // bound inline packs or externalized metadata BEFORE quota is committed
  const saved=dbCheck(await sb.rpc('complete_generation',{p_uid:user.id,p_id:id,p_campaign:campaign}),'Your save could not be confirmed. Retry this exact request; do not start another.');
  reservation=null;
  return json({...saved,provider:result.provider,stage_status:result.stage_status,visual_status:result.visual_status,request_id:id});
 } catch(e) {
  let released=false;
  if(reservation) {
   // If completion committed but its response was lost, this cannot refund it:
   // fail_generation changes ONLY this user's still-reserved record.
   try { released=dbCheck(await admin({signal:AbortSignal.timeout(1800)}).rpc('fail_generation',{p_uid:user.id,p_id:reservation,p_code:e.code||'GENERATION_FAILED'}))===true; } catch { console.error('generation reservation cleanup unavailable'); }
  }
  return json({error:e.status?e.message:'Generation could not be completed. Check History before retrying.',code:e.code||'GENERATION_FAILED',retry_with_new_request:released},e.status||503);
 }
}
const h=serve(handle);export default h;export const GET=h;export const POST=h;
