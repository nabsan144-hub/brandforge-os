import {admin,authUser,json} from '../sb.js';
import {serve} from '../serve.js';
import {UUID,HttpError} from '../http.js';
import {rateLimit} from '../limit.js';
import {requireAssetClient,authorizeBundle} from '../assets.js';
async function handle(req,ctx){
 if(req.method&&req.method!=='GET')return json({error:'Method not allowed'},405);
 const user=await authUser(req);if(!user)return json({error:'Not signed in'},401);
 try{
  const id=ctx?.params?.id||new URL(req.url).pathname.split('/').at(-2);
  if(!UUID.test(id||''))throw new HttpError(404,'Campaign not found');
  requireAssetClient(req);
  if(!await rateLimit('asset-download',user.id,600,3600))throw new HttpError(429,'Download safety limit reached. Retry later.');
  const data=await authorizeBundle(admin(),user.id,id,req);
  return new Response(JSON.stringify(data),{headers:{'Content-Type':'application/json','Cache-Control':'no-store','Referrer-Policy':'no-referrer'}});
 }catch(e){return json({error:e.status?e.message:'Private files could not be loaded.',code:e.code},e.status||503);}
}
const h=serve(handle);export default h;export const GET=h;
