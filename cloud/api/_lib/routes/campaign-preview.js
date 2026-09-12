import {admin,authUser,json} from '../sb.js';
import {serve} from '../serve.js';
import {readJson,dbCheck,HttpError} from '../http.js';
import {rateLimit} from '../limit.js';
import {campaignInput} from './campaigns.js';
import {runCampaign,PLANS} from '../engine.js';
import {validateVisualText} from '../visuals.js';
import {assertCampaignPayload} from '../payload.js';
async function handle(req){
 if(req.method!=='POST')return json({error:'Method not allowed'},405);
 const user=await authUser(req);if(!user)return json({error:'Not signed in'},401);
 try{
  if(!await rateLimit('template-preview',user.id,30,3600))throw new HttpError(429,'Preview safety limit reached. Retry later.');
  const sb=admin(),profile=dbCheck(await sb.from('profiles').select('plan,deletion_pending').eq('id',user.id).single());
  if(profile?.deletion_pending)throw new HttpError(409,'Account deletion is pending.');
  const b=await readJson(req,750000);
  // No credentials resolved, generation ledger touched or provider permitted.
  const input=campaignInput({...b,provider:'offline',visuals_ai:false,visual_provider:''},PLANS[profile?.plan]||PLANS.free);
  validateVisualText(input);
  const result=await runCampaign(input);
  const response={schema:1,preview:true,notice:'Template preview only. No campaign allowance or AI provider used. Connected generation may produce different text. Review every omission before creating a saved campaign.',files:result.files.filter(f=>/^(hero_banner|banner_.*)\.svg$/.test(f.name)),visual_status:result.visual_status};
  assertCampaignPayload(response);return json(response);
 }catch(e){return json({error:e.status?e.message:'Preview could not be prepared. No campaign allowance was used.',code:e.code},e.status||503);}
}
const h=serve(handle);export default h;export const POST=h;
