import {createHmac} from 'node:crypto';
import {admin,json} from '../sb.js';
import {serve} from '../serve.js';
import {readJson,UUID,HttpError,dbCheck} from '../http.js';
import {publicCors} from '../commerce.js';
import {clientIp} from './campaigns.js';
import {rateLimit} from '../limit.js';
const EVENTS=['visit','return_visit','signup_started','email_confirmed','campaign_saved','pack_exported','export_failed','billing_active_seen'];
async function handle(req){
 const reply=(b,s=200)=>publicCors(req,json(b,s));
 try{
  const allowed=[process.env.BRANDFORGE_APP_URL,process.env.BRANDFORGE_MARKETING_URL].filter(Boolean).map(x=>new URL(x).origin);
  if(!allowed.includes(req.headers.get('origin')))throw new HttpError(403,'Origin not permitted');
  if(req.method==='OPTIONS')return publicCors(req,new Response(null,{status:204}));
  if(req.method!=='POST')throw new HttpError(405,'Method not allowed');
  if(process.env.USAGE_METRICS_ENABLED!=='true'||(process.env.USAGE_METRICS_SECRET||'').length<32)throw new HttpError(503,'Optional metrics are disabled');
  const b=await readJson(req,1500);if(Object.keys(b).some(k=>!['id','session','event','surface','consent'].includes(k))||b.consent!==true||!UUID.test(b.id||'')||!UUID.test(b.session||'')||!EVENTS.includes(b.event)||!['sales','cloud'].includes(b.surface))throw new HttpError(400,'Only consented, defined event fields are accepted');
  if(!await rateLimit('metrics-ip',clientIp(req),360,3600)||!await rateLimit('metrics-capacity','deployment',5000,86400))throw new HttpError(429,'Metrics capacity reached');
  const actor=createHmac('sha256',process.env.USAGE_METRICS_SECRET).update(b.session+':'+new Date().toISOString().slice(0,10)).digest('hex');
  dbCheck(await admin({signal:AbortSignal.timeout(5000)}).rpc('record_usage_event',{p_id:b.id,p_actor:actor,p_event:b.event,p_surface:b.surface}));
  return reply({ok:true});
 }catch(e){return reply({error:e.status?e.message:'Metrics unavailable'},e.status||503);}
}
export default serve(handle);
