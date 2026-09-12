import {admin,authUser,json} from '../sb.js';
import {PLANS} from '../engine.js';
import {serve} from '../serve.js';
import {dbCheck,readJson,HttpError} from '../http.js';
import {deleteAccount} from '../account-deletion.js';
async function handle(req){
 const user=await authUser(req);if(!user)return json({error:'Not signed in'},401);
 const sb=admin();
 try{
  if(req.method==='DELETE'){
   const body=await readJson(req);
   if(body.confirm!=='DELETE AND CANCEL BILLING')throw new HttpError(400,'Confirm deletion and immediate cancellation of Cloud billing. Export your work first.');
   return json(await deleteAccount(sb,user));
  }
  if(req.method&&req.method!=='GET')return json({error:'Method not allowed'},405);
  const [p,u]=await Promise.all([sb.from('profiles').select('plan,plan_status,deletion_pending').eq('id',user.id).single(),sb.rpc('generation_totals',{p_uid:user.id})]);
  const profile=dbCheck(p),usage=dbCheck(u);const plan=PLANS[profile?.plan]?profile.plan:'free';
  return json({email:user.email,plan,plan_status:profile?.plan_status,deletion_pending:!!profile?.deletion_pending,limits:PLANS[plan],usage});
 }catch(e){return json({error:e.status?e.message:'Could not complete your account request.',code:e.code},e.status||503);}
}
const h=serve(handle);export default h;export const GET=h;export const DELETE=h;
