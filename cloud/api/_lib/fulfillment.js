import {dbCheck,HttpError} from './http.js';
import {catalog,paddle,env,seal,unseal} from './commerce.js';
export async function recordDesktopTransaction(sb,data,occurredAt){
 const match=catalog().find(p=>p.interval==='once'&&p.price&&data.items?.length===1&&(data.items[0].price?.id||data.items[0].price_id)===p.price&&Number(data.items[0].quantity||1)===1);
 if(!match){if(data.items?.some(i=>catalog().some(p=>p.interval==='once'&&p.price===(i.price?.id||i.price_id))))throw new HttpError(503,'A desktop cart needs manual reconciliation.','DESKTOP_CART_REVIEW');return false;}
 if(data.status!=='completed'||data.subscription_id)throw new HttpError(400,'Desktop fulfillment requires a completed one-time transaction.');
 const customer=(await paddle('/customers/'+encodeURIComponent(data.customer_id))).data;
 if(!customer?.email || customer.id!==data.customer_id)throw new HttpError(503,'Could not verify the paid customer email.');
 const path=env(match.plan==='owner'?'DESKTOP_OWNER_PATH':'DESKTOP_AGENCY_SOURCE_PATH');
 if(!path || path.includes('..') || !path.endsWith('.zip'))throw new HttpError(503,'Private desktop release is not configured.');
 const checksum=env(match.plan==='owner'?'DESKTOP_RELEASE_SHA256_OWNER':'DESKTOP_RELEASE_SHA256_AGENCY_SOURCE'),bucket=env('DESKTOP_STORAGE_BUCKET');
 if(!/^[a-f0-9]{64}$/i.test(checksum)||!bucket)throw new HttpError(503,'Paid release metadata is incomplete.');
 dbCheck(await sb.rpc('record_desktop_order',{p_data:{transaction_id:data.id,customer_id:data.customer_id,email:customer.email.toLowerCase(),tier:match.plan,amount_total:Number(data.details?.totals?.total||0),currency:data.currency_code||'USD',release_path:path,release_sha256:checksum,release_bucket:bucket,occurred_at:occurredAt}}));
 return true;
}
export async function deliverDesktopOrder(sb,transactionId,{signal}={}){
 if(!dbCheck(await sb.rpc('claim_desktop_delivery',{p_id:transactionId})))return false;
 try{
  const order=dbCheck(await sb.from('desktop_orders').select('*').eq('transaction_id',transactionId).single());
  if(order.status!=='paid')return false;
  const base=env('BRANDFORGE_APP_URL').replace(/\/+$/,'');
  if(!base.startsWith('https://') || !env('RESEND_API_KEY') || !env('DELIVERY_FROM_EMAIL'))throw new Error('Delivery configuration incomplete');
  const token=seal({purpose:'desktop-download',id:order.transaction_id,nonce:order.delivery_nonce,exp:Date.now()+30*86400000},'DESKTOP_DOWNLOAD_SECRET');
  const url=base+'/desktop-download#token='+encodeURIComponent(token);
  const checksum=order.release_sha256;
  if(!order.release_bucket)throw new Error('Order release metadata requires reconciliation');
  if(!/^[a-f0-9]{64}$/i.test(checksum))throw new Error('Release checksum missing');
  // Verify the private release is accessible before sending a dead link.
  dbCheck(await sb.storage.from(order.release_bucket).createSignedUrl(order.release_path,60),'Private release is unavailable.');
  const text=`Thank you for choosing BrandForge OS Desktop ${order.tier==='owner'?'Owner':'Agency + Source'}.\n\nYour order: ${order.transaction_id}\nDownload (valid for 30 days): ${url}\n\nZIP SHA-256: ${checksum}\n\nUnzip the complete folder. On Windows, run SETUP-WINDOWS.bat once while online, then START-HERE.bat to launch. Follow START-HERE.md on macOS/Linux. First-time setup needs an internet connection to install dependencies. After setup, use Offline mode for local generation. Connected providers are optional and may have their own costs.\n\nDesktop is local ownership; it does not include or start a Cloud subscription. Read the included LICENSE for your tier's rights. Keep this email as proof of purchase.\n\nIf a download has expired, use ${base}/download-help or contact support@brandforge-os.com with this order ID. Refunds are reviewed under the published refund policy.\n`;
  const r=await fetch('https://api.resend.com/emails',{method:'POST',headers:{Authorization:`Bearer ${env('RESEND_API_KEY')}`,'Content-Type':'application/json','Idempotency-Key':`desktop/${order.transaction_id}/${order.delivery_nonce}`},body:JSON.stringify({from:env('DELIVERY_FROM_EMAIL'),to:[order.email],subject:'Your BrandForge OS Desktop download',text}),signal:AbortSignal.any([signal,AbortSignal.timeout(15000)].filter(Boolean))});
  if(!r.ok)throw new Error('Delivery provider rejected the email');
  dbCheck(await sb.from('desktop_orders').update({delivered_at:new Date().toISOString(),delivery_error:null,delivery_claimed_until:null}).eq('transaction_id',transactionId).eq('delivery_nonce',order.delivery_nonce));
  return true;
 }catch(e){
  // Durable outbox: webhook retries and the maintenance job can resume this.
  await sb.from('desktop_orders').update({delivery_error:'Delivery failed; inspect provider and private release configuration.',delivery_claimed_until:null}).eq('transaction_id',transactionId);
  throw new HttpError(503,'Desktop delivery is queued for retry.','DELIVERY_PENDING');
 }
}
export async function desktopDownload(sb,token){
 const proof=unseal(token,'DESKTOP_DOWNLOAD_SECRET');
 if(!proof||proof.purpose!=='desktop-download')throw new HttpError(403,'This download link is invalid or expired. Request a new link.');
 const order=dbCheck(await sb.from('desktop_orders').select('status,release_path,release_bucket,release_sha256,delivery_nonce').eq('transaction_id',proof.id).maybeSingle());
 if(!order||order.status!=='paid'||proof.nonce!==order.delivery_nonce)throw new HttpError(403,'This order no longer has an active download link. Contact support if you believe this is an error.');
 if(!order.release_bucket||!/^[a-f0-9]{64}$/i.test(order.release_sha256||''))throw new HttpError(503,'This release requires verification. Contact support with your order ID.');
 const result=dbCheck(await sb.storage.from(order.release_bucket).createSignedUrl(order.release_path,60),'The release is temporarily unavailable.');
 if(!result?.signedUrl)throw new HttpError(503,'Download signing failed.');
 return result.signedUrl;
}

export async function verifyPrivateDesktopRelease(sb){
 const bucket=dbCheck(await sb.storage.getBucket(env('DESKTOP_STORAGE_BUCKET')),'Private release storage is unavailable.');
 if(!bucket || bucket.public!==false)throw new HttpError(503,'Desktop releases must be in a private bucket.','PUBLIC_RELEASE_BUCKET');
 for(const key of ['DESKTOP_OWNER_PATH','DESKTOP_AGENCY_SOURCE_PATH']) dbCheck(await sb.storage.from(env('DESKTOP_STORAGE_BUCKET')).createSignedUrl(env(key),60),'The configured desktop release is missing.');
}
