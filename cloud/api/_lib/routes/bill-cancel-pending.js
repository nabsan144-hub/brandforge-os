import {admin,authUser,json} from '../sb.js';
import {serve} from '../serve.js';
import {withBillingLock} from '../commerce.js';
import {closePendingCheckouts} from '../account-deletion.js';
async function handle(req){
 if(req.method!=='POST')return json({error:'Method not allowed'},405);
 const user=await authUser(req);if(!user)return json({error:'Not signed in'},401);
 try{const sb=admin();await withBillingLock(sb,user.id,()=>closePendingCheckouts(sb,user.id));return json({ok:true});}
 catch(e){return json({error:e.status?e.message:'Could not close the pending checkout.'},e.status||503);}
}
const h=serve(handle);export default h;export const POST=h;
