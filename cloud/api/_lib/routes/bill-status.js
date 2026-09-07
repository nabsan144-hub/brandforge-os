import {admin,authUser,json} from '../sb.js';
import {serve} from '../serve.js';
import {publicPlans} from '../plans.js';
import {profileFor,billingReadiness} from '../commerce.js';
import {dbCheck} from '../http.js';
async function handle(req){
 if(req.method&&req.method!=='GET')return json({error:'Method not allowed'},405);
 const user=await authUser(req);if(!user)return json({error:'Not signed in'},401);
 try{
  const sb=admin(),profile=await profileFor(sb,user.id),ready=billingReadiness();
  const subscriptions=dbCheck(await sb.from('billing_subscriptions').select('id,plan,status,billing_interval').eq('user_id',user.id))||[];
  const pending=dbCheck(await sb.from('checkout_intents').select('id,plan,billing_interval,state,transaction_id').eq('user_id',user.id).in('state',['open','creating','uncertain']).order('created_at',{ascending:false}).limit(1))||[];
  return json({plan:profile.plan||'free',plan_status:profile.plan_status||'active',subscriptions,has_subscription:subscriptions.some(s=>['active','trialing','past_due','paused'].includes(s.status))||!!profile.paddle_subscription_id,
   portal_available:!!profile.paddle_customer_id,checkout_enabled:ready.enabled,plans:publicPlans(),pending_checkout:pending[0]||null,
   billing_note:'Desktop is a separate one-time local product. It never starts or includes a Cloud subscription.'});
 }catch(e){return json({error:e.status?e.message:'Could not load billing.'},e.status||503);}
}
const h=serve(handle);export default h;export const GET=h;
