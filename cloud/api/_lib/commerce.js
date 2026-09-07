// Paddle Billing (v2), never Classic fulfillment. No browser chooses a raw
// Cloud price or customer ID. Monetary changes are server-authorized.
import { createHmac, timingSafeEqual, randomUUID } from 'node:crypto';
import { HttpError, dbCheck, UUID } from './http.js';
export const env = name => String(process.env[name] || '').trim();
export const validPrice = x => /^pri_[a-z\d]{26}$/.test(String(x));
export function catalog() {
 const rows=[['pro','month','PADDLE_PRICE_PRO'],['pro','year','PADDLE_PRICE_PRO_YEARLY'],['agency','month','PADDLE_PRICE_AGENCY'],['owner','once','PADDLE_PRICE_DESKTOP_OWNER'],['agency_source','once','PADDLE_PRICE_DESKTOP_AGENCY_SOURCE']];
 const seen=new Set();
 return rows.map(([plan,interval,key])=>{
  const price=env(key); if(price && (!validPrice(price)||seen.has(price))) throw new HttpError(503,'Billing price configuration needs review.');
  if(price) seen.add(price);return {plan,interval,price,key};
 });
}
export function billingReadiness(kind='cloud') {
 const required=['PADDLE_API_KEY','PADDLE_CLIENT_TOKEN','PADDLE_WEBHOOK_SECRET','SUPABASE_URL','SUPABASE_SERVICE_ROLE_KEY','BILLING_ACTION_SECRET'];
 if(kind==='desktop') required.push('DESKTOP_DOWNLOAD_SECRET','DESKTOP_STORAGE_BUCKET','DESKTOP_OWNER_PATH','DESKTOP_AGENCY_SOURCE_PATH','RESEND_API_KEY','DELIVERY_FROM_EMAIL','BRANDFORGE_APP_URL','DESKTOP_RELEASE_SHA256_OWNER','DESKTOP_RELEASE_SHA256_AGENCY_SOURCE');
 if(kind==='cloud') for(const provider of ['GROQ','GEMINI']) if(env(provider+'_API_KEY')) required.push(provider+'_INPUT_USD_PER_MTOK',provider+'_OUTPUT_USD_PER_MTOK');
 const missing=required.filter(x=>!env(x) || /YOUR_|CHANGE_ME|REPLACE_ME/.test(env(x)));
 if(kind==='desktop'){
  if(env('DESKTOP_DOWNLOAD_SECRET').length<32)missing.push('DESKTOP_DOWNLOAD_SECRET (32+ characters)');
  for(const n of ['DESKTOP_RELEASE_SHA256_OWNER','DESKTOP_RELEASE_SHA256_AGENCY_SOURCE'])if(!/^[a-f0-9]{64}$/i.test(env(n)))missing.push(n+' (SHA-256)');
  for(const n of ['DESKTOP_OWNER_PATH','DESKTOP_AGENCY_SOURCE_PATH'])if(!/^[a-z0-9._/-]+\.zip$/i.test(env(n))||env(n).includes('..')||env(n).startsWith('/'))missing.push(n+' (private object path)');
  try{if(new URL(env('BRANDFORGE_APP_URL')).protocol!=='https:')missing.push('BRANDFORGE_APP_URL HTTPS');}catch{missing.push('BRANDFORGE_APP_URL HTTPS');}
 }
 if(env('BILLING_ACTION_SECRET').length<32) missing.push('BILLING_ACTION_SECRET (32+ characters)');
 const mode=env('PADDLE_ENV')||'sandbox';
 if(!['sandbox','production'].includes(mode)) missing.push('PADDLE_ENV');
 if(!(mode==='sandbox'?/^test_/:/^live_/).test(env('PADDLE_CLIENT_TOKEN'))) missing.push('matching client token environment');
 try { for(const c of catalog().filter(c=>kind==='desktop'?c.interval==='once':c.interval!=='once')) if(!c.price) missing.push(c.key); } catch { missing.push('unique valid price IDs'); }
 if(kind==='cloud' && !env('GROQ_API_KEY') && !env('GEMINI_API_KEY')) missing.push('operator text provider key');
 const flag=kind==='desktop'?'DESKTOP_CHECKOUT_ENABLED':'CLOUD_CHECKOUT_ENABLED';
 if(env(flag)!=='true') missing.push(flag);
 if(mode==='production' && env('BILLING_RELEASE_VERIFIED')!=='true') missing.push('BILLING_RELEASE_VERIFIED');
 if(mode==='sandbox' && env('BILLING_SANDBOX_TESTING')!=='true' && env('BILLING_RELEASE_VERIFIED')!=='true') missing.push('BILLING_SANDBOX_TESTING');
 return {enabled:missing.length===0,mode,missing:[...new Set(missing)]};
}
export function requireCheckout(kind='cloud') { const r=billingReadiness(kind);if(!r.enabled) throw new HttpError(503,'Paid checkout is not open yet. This request did not start a payment.','CHECKOUT_DISABLED');return r; }
export async function paddle(path,body,method=body?'POST':'GET') {
 if(!env('PADDLE_API_KEY')) throw new HttpError(503,'Billing is unavailable. No billing operation was confirmed.','BILLING_UNAVAILABLE');
 const base=env('PADDLE_ENV')==='production'?'https://api.paddle.com':'https://sandbox-api.paddle.com';
 let res;
 try {res=await fetch(base+path,{method,headers:{Authorization:`Bearer ${env('PADDLE_API_KEY')}`,'Content-Type':'application/json'},...(body?{body:JSON.stringify(body)}:{}),signal:AbortSignal.timeout(15000)});} catch {throw new HttpError(503,'Billing provider did not confirm the operation. Check Billing before retrying.','BILLING_UNCERTAIN');}
 let payload;try{payload=await res.json();}catch{throw new HttpError(503,'Invalid billing provider response.','BILLING_UNCERTAIN');}
 if(!res.ok || payload.error) throw new HttpError(res.status===409?409:502,'The billing provider could not complete this operation. Try the customer portal or contact support.','PADDLE_'+(payload.error?.code||res.status));
 return payload;
}
export async function listPaddle(path) {
 let data=[],next=path;
 for(let i=0;i<30;i++) {
  const r=await paddle(next);if(!Array.isArray(r.data)) throw new HttpError(503,'Billing reconciliation failed.');data.push(...r.data);
  if(!r.meta?.pagination?.has_more) return data;
  const u=new URL(r.meta.pagination.next);
  // Do not send a provider credential to a supplied pagination origin.
  if(!['api.paddle.com','sandbox-api.paddle.com'].includes(u.hostname)) throw new HttpError(503,'Invalid billing pagination.');
  next=u.pathname+u.search;
 }
 throw new HttpError(503,'Billing reconciliation exceeded the safe page limit. Contact support.');
}
export async function profileFor(sb,uid) {return dbCheck(await sb.from('profiles').select('*').eq('id',uid).single(),'Could not read your billing account.');}
export async function withBillingLock(sb,uid,fn) {
 const id=randomUUID();
 if(!dbCheck(await sb.rpc('begin_billing_operation',{p_uid:uid,p_id:id}))) throw new HttpError(409,'Another billing operation is in progress. Wait, then refresh.','BILLING_BUSY');
 try{return await fn();}finally{dbCheck(await sb.from('billing_operations').delete().eq('user_id',uid).eq('operation_id',id),'Billing lock cleanup failed. Wait five minutes before retrying.');}
}
export async function ensureCustomer(sb,user,profile) {
 if(profile.paddle_customer_id) {await requireCustomerOwnership(sb,user.id,profile.paddle_customer_id);return profile.paddle_customer_id;}
 if(!user.email_confirmed_at) throw new HttpError(403,'Confirm your email before starting paid checkout.');
 const matches=await listPaddle('/customers?email='+encodeURIComponent(user.email));
 if(matches.length>1) throw new HttpError(409,'Multiple billing customers need reconciliation. Contact support.');
 let customer=matches[0];
 if(customer && !dbCheck(await sb.rpc('claim_billing_customer',{p_uid:user.id,p_customer:customer.id}))) customer=null;
 if(!customer) customer=(await paddle('/customers',{email:user.email})).data;
 if(!/^ctm_[a-z\d]{26}$/.test(customer?.id)) throw new HttpError(503,'Could not confirm billing customer.');
 await requireCustomerOwnership(sb,user.id,customer.id);
 dbCheck(await sb.from('profiles').update({paddle_customer_id:customer.id}).eq('id',user.id));
 return customer.id;
}
export async function reconcileSubscriptions(sb,userId,profile) {
 const rows=dbCheck(await sb.from('billing_subscriptions').select('*').eq('user_id',userId))||[];
 const customers=new Set(rows.map(s=>s.customer_id));if(profile.paddle_customer_id) customers.add(profile.paddle_customer_id);
 const all=new Map();
 for(const id of customers) for(const s of await listPaddle('/subscriptions?customer_id='+encodeURIComponent(id)+'&per_page=200')) all.set(s.id,s);
 if(profile.paddle_subscription_id&&!all.has(profile.paddle_subscription_id)) {const s=(await paddle('/subscriptions/'+encodeURIComponent(profile.paddle_subscription_id))).data;if(s) all.set(s.id,s);else throw new HttpError(503,'Could not reconcile the current subscription.');}
 for(const row of rows) if(!all.has(row.id)) {const s=(await paddle('/subscriptions/'+encodeURIComponent(row.id))).data;if(!s) throw new HttpError(503,'Could not reconcile a subscription.');all.set(s.id,s);}
 const owned=[];
 for(const s of all.values()){
  const owner=await accountForSubscription(sb,s);
  if(owner===userId){await syncSubscription(sb,userId,s);owned.push(s);}
  else if(owner) throw new HttpError(409,'A billing customer is shared with another identity; support must reconcile it.');
  else if(billable(s) && s.items?.some(i=>catalog().some(p=>p.interval!=='once'&&p.price===(i.price?.id||i.price_id)))) throw new HttpError(409,'An unbound Cloud subscription needs support reconciliation.');
 }
 return owned;
}
export const billable = s => ['active','trialing','past_due','paused'].includes(s.status);
export function seal(payload,secretName='BILLING_ACTION_SECRET') {
 const secret=env(secretName);if(secret.length<32) throw new HttpError(503,'Billing signing configuration is incomplete.');
 const raw=Buffer.from(JSON.stringify(payload)).toString('base64url');
 return raw+'.'+createHmac('sha256',secret).update(raw).digest('base64url');
}
export function unseal(token,secretName='BILLING_ACTION_SECRET') {
 try {const [raw,sig,...rest]=String(token).split('.');if(rest.length||!raw||!sig||env(secretName).length<32) return null;
 const a=Buffer.from(sig,'base64url'),b=createHmac('sha256',env(secretName)).update(raw).digest();if(a.length!==b.length||!timingSafeEqual(a,b)) return null;
 const p=JSON.parse(Buffer.from(raw,'base64url'));if(p.exp && Date.now()>p.exp) return null;return p;}catch{return null;}
}
export function checkoutProof(uid,intent) {return seal({purpose:'cloud-checkout',uid,intent});}
export async function accountForSubscription(sb,data) {
 const old=dbCheck(await sb.from('billing_subscriptions').select('user_id').eq('id',data.id).maybeSingle());
 if(old?.user_id) return old.user_id;
 const proof=unseal(data.custom_data?.bf_proof);
 if(!proof || proof.purpose!=='cloud-checkout'||!UUID.test(proof.uid)||!UUID.test(proof.intent)) return null;
 const intent=dbCheck(await sb.from('checkout_intents').select('user_id,transaction_id').eq('id',proof.intent).maybeSingle());
 if(intent?.user_id!==proof.uid || !intent.transaction_id) return null;
 const original=(await paddle('/transactions/'+encodeURIComponent(intent.transaction_id))).data;
 return original?.subscription_id===data.id && original.customer_id===data.customer_id && original.status==='completed' && original.custom_data?.bf_intent===proof.intent ? proof.uid : null;
}
export async function syncSubscription(sb,uid,s,at=s.updated_at||new Date().toISOString()) {
 const match=catalog().find(p=>p.interval!=='once'&&p.price && s.items?.length===1 && (s.items[0].price?.id||s.items[0].price_id)===p.price && Number(s.items[0].quantity||1)===1);
 if(!match) throw new HttpError(503,'Unrecognized subscription price. Billing requires reconciliation.');
 dbCheck(await sb.rpc('apply_subscription',{p_uid:uid,p_id:s.id,p_customer:s.customer_id,p_plan:match.plan,p_status:s.status,p_price:match.price,p_interval:match.interval,p_at:at}));
}
export function publicCors(req,response) {
 const origin=req.headers?.get?.('origin');
 const allowed=[env('BRANDFORGE_MARKETING_URL'),env('BRANDFORGE_APP_URL')].filter(Boolean).map(x=>{try{return new URL(x).origin;}catch{return '';}});
 if(origin && allowed.includes(origin)) {
  response.headers.set('Access-Control-Allow-Origin',origin);response.headers.set('Vary','Origin');
  response.headers.set('Access-Control-Allow-Methods','GET, POST, OPTIONS');response.headers.set('Access-Control-Allow-Headers','Content-Type');
 }
 return response;
}

export async function verifyCatalogPrice(choice){
 const expected={pro:{month:4900,year:49000},agency:{month:9900},owner:{once:19900},agency_source:{once:49900}};
 const p=(await paddle('/prices/'+encodeURIComponent(choice.price))).data;
 const cycle=p?.billing_cycle;
 if(!p||p.status!=='active'||p.unit_price?.currency_code!=='USD'||Number(p.unit_price.amount)!==expected[choice.plan]?.[choice.interval]||
    (choice.interval==='once'?cycle!==null:cycle?.interval!==choice.interval||cycle?.frequency!==1)||p.trial_period){
  throw new HttpError(503,'The configured price does not match the published product. Checkout is stopped for review.','CATALOG_MISMATCH');
 }
 return p;
}

export async function requireCustomerOwnership(sb,uid,customer){
 if(!dbCheck(await sb.rpc('claim_billing_customer',{p_uid:uid,p_customer:customer}))) throw new HttpError(409,'This billing customer belongs to a different or deleted identity. Contact support; email alone cannot transfer billing access.','CUSTOMER_BINDING_CONFLICT');
}

export async function reconcileCheckoutIntent(sb,uid,row){
 if(row.transaction_id)return row;
 const profile=await profileFor(sb,uid);if(!profile.paddle_customer_id)throw new HttpError(409,'Checkout customer is not known. Support must reconcile this attempt.');
 const transactions=await listPaddle('/transactions?customer_id='+encodeURIComponent(profile.paddle_customer_id)+'&per_page=100');
 const matches=transactions.filter(t=>{const p=unseal(t.custom_data?.bf_proof);return t.custom_data?.bf_intent===row.id&&p?.purpose==='cloud-checkout'&&p.uid===uid&&p.intent===row.id;});
 if(matches.length!==1)throw new HttpError(409,'The earlier checkout cannot be confirmed uniquely. No replacement checkout was created. Contact support with the attempt ID '+row.id+'.','CHECKOUT_UNCERTAIN');
 const transaction=matches[0];
 dbCheck(await sb.from('checkout_intents').update({transaction_id:transaction.id,state:['canceled','completed'].includes(transaction.status)?transaction.status:'open'}).eq('id',row.id).eq('user_id',uid));
 return {...row,transaction_id:transaction.id};
}
