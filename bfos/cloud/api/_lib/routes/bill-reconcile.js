import {admin,authUser,json} from '../sb.js';
import {serve} from '../serve.js';
import {dbCheck} from '../http.js';
import {withBillingLock,reconcileCheckoutIntent,profileFor,reconcileSubscriptions} from '../commerce.js';
async function handle(req){
 if(req.method!=='POST')return json({error:'Method not allowed'},405);
 const user=await authUser(req);if(!user)return json({error:'Not signed in'},401);
 try{const sb=admin();const result=await withBillingLock(sb,user.id,async()=>{
  const rows=dbCheck(await sb.from('checkout_intents').select('*').eq('user_id',user.id).in('state',['creating','uncertain','open']))||[];
  for(const row of rows)await reconcileCheckoutIntent(sb,user.id,row);
  await reconcileSubscriptions(sb,user.id,await profileFor(sb,user.id));return {ok:true};
 });return json(result);}catch(e){return json({error:e.status?e.message:'Could not reconcile checkout. No new checkout was created.'},e.status||503);}
}
const h=serve(handle);export default h;export const POST=h;
