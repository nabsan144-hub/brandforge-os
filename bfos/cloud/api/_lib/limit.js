// Distributed, fail-CLOSED limiter. A backend outage is a 503, never permission
// to spend unbounded provider credits. No automatic cross-store failover (that
// would double the allowance). The generation ledger is a second backstop.
import { admin } from './sb.js';
import { HttpError } from './http.js';
import { createHash } from 'node:crypto';
const up = () => process.env.RATE_BACKEND === 'upstash';
export const RATE_ENABLED = () => up() ? !!(process.env.UPSTASH_REDIS_REST_URL && process.env.UPSTASH_REDIS_REST_TOKEN) : !!(process.env.SUPABASE_URL && process.env.SUPABASE_SERVICE_ROLE_KEY);
function boolOf(x) {
 if(x===true || x==='true') return true;
 if(x===false || x==='false') return false;
 if(x && typeof x==='object' && Object.keys(x).length===1) return boolOf(Object.values(x)[0]);
 throw new Error('Invalid limiter result');
}
export async function rateLimit(bucket,key,limit,windowSec) {
 if(!RATE_ENABLED()) throw new HttpError(503,'Rate protection is not configured. Please try later.','RATE_UNAVAILABLE');
 // Do not retain raw client IPs or email addresses in rate-limit tables.
 const hash=createHash('sha256').update(String(key)).digest('hex');
 try {
  if(!up()) {
   const {data,error}=await admin().rpc('bf_rate_limit',{bucket,key:hash,lim:limit,win:windowSec});
   if(error) throw error;
   return boolOf(data);
  }
  const script="local n=redis.call('INCR',KEYS[1]); if n==1 then redis.call('EXPIRE',KEYS[1],ARGV[1]) end; return n";
  const r=await fetch(process.env.UPSTASH_REDIS_REST_URL.replace(/\/+$/,''),{
   method:'POST',headers:{Authorization:`Bearer ${process.env.UPSTASH_REDIS_REST_TOKEN}`,'Content-Type':'application/json'},
   body:JSON.stringify(['EVAL',script,1,`bf:${bucket}:${hash}`,String(windowSec)]),signal:AbortSignal.timeout(5000)
  });
  if(!r.ok) throw new Error('Limiter unavailable');
  const value=(await r.json()).result;
  if(!Number.isSafeInteger(value) || value<1) throw new Error('Invalid limiter result');
  return value<=limit;
 } catch {
  throw new HttpError(503,'Rate protection is temporarily unavailable. No generation has started.','RATE_UNAVAILABLE');
 }
}
