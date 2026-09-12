// Public release configuration, not an uptime check or permission to charge.
// Expected closed checkout is a successful capability response, not a 503.
import {json} from '../sb.js';
import {serve} from '../serve.js';
import {billingReadiness,env,publicCors} from '../commerce.js';
import {visualConfig} from '../visual-plan.js';
export function publicCapabilities(){
 const cloud=billingReadiness('cloud'),desktop=billingReadiness('desktop'),visual=visualConfig();
 const costPrefix='AI_VISUALS_'+String(visual.provider||'').toUpperCase();
 const estimate=Number(env(costPrefix+'_MAX_USD_PER_IMAGE'));
 const images=visual.enabled&&env(costPrefix+'_COST_MODEL')===visual.model&&Number.isFinite(estimate)&&estimate>0;
 return {schema:1,free:{lifetime_campaigns:3,card_required:false,visuals:'watermarked_vectors'},
  cloud:{checkout_enabled:cloud.enabled&&cloud.mode==='production'},
  desktop:{checkout_enabled:desktop.enabled&&desktop.mode==='production'},
  imagery:{configured:images,scope:process.env.AI_CAMPAIGN_ENABLED==='true'?'campaign_formats':'hero_only',resized_banners:process.env.AI_CAMPAIGN_ENABLED==='true'?'three_ai_formats':'vector_only',requires_paid_plan:true,requires_opt_in:true},
  generation_paused:env('GENERATION_PAUSED')==='true'};
}
async function handle(req){
 if(req.method==='OPTIONS')return publicCors(req,new Response(null,{status:204}));
 if(req.method&&req.method!=='GET')return publicCors(req,json({error:'Method not allowed'},405));
 try{return publicCors(req,json(publicCapabilities()));}
 catch{return publicCors(req,json({error:'Availability could not be verified.'},503));}
}
const h=serve(handle);export default h;export const GET=h;export const OPTIONS=h;
