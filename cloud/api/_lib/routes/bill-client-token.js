// Public client token, not an API credential. A token cannot enable checkout
// unless the corresponding server-side release gate is also satisfied.
import {json} from '../sb.js';
import {serve} from '../serve.js';
import {billingReadiness,env,publicCors} from '../commerce.js';
async function handle(req){
 if(req.method==='OPTIONS')return publicCors(req,new Response(null,{status:204}));
 if(req.method&&req.method!=='GET')return json({error:'Method not allowed'},405);
 const cloud=billingReadiness(),desktop=billingReadiness('desktop');
 const r=cloud.enabled||desktop.enabled?json({token:env('PADDLE_CLIENT_TOKEN'),environment:cloud.mode}):json({error:'Paid checkout is not open yet.'},503);
 return publicCors(req,r);
}
const h=serve(handle);export default h;export const GET=h;export const OPTIONS=h;
