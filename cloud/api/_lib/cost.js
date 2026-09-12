import {HttpError,dbCheck} from './http.js';
// Conservative token reservation, including bounded retries; not measured spend.
export const MAX_RUN_TOKEN_RESERVATION=60000;
const configError=()=>new HttpError(503,'Operator provider pricing and daily budget need configuration. No provider request was started.','COST_GUARD_UNCONFIGURED');
const rate=name=>!String(process.env[name]??'').trim()?NaN:Number(process.env[name]);

// ONE database reservation covers all operator-funded work in a campaign.
// Image costs are charged to the operator even with personal/offline text keys.
// Reservations are not refunded after provider failures or uncertain saves.
export async function reserveOperatorBudget(sb,id,keys,visualPlan={enabled:false}){
 let textUpper=0,imageUpper=0;
 if(keys.key_source==='operator'){
  const provider=keys.groqKey?'GROQ':'GEMINI';
  const rates=[rate(provider+'_INPUT_USD_PER_MTOK'),rate(provider+'_OUTPUT_USD_PER_MTOK')];
  if(rates.some(x=>!Number.isFinite(x)||x<0))throw configError();
  textUpper=MAX_RUN_TOKEN_RESERVATION*Math.max(...rates)/1000000;
 }
 if(visualPlan.enabled){
  const provider=String(visualPlan.provider||'').toUpperCase();
  if(!['GEMINI','OPENAI','XAI'].includes(provider))throw configError();
  // Bind the configured upper bound to a provider AND model. Switching models
  // requires a deliberate pricing review instead of reusing a stale estimate.
  if(process.env['AI_VISUALS_'+provider+'_COST_MODEL']!==visualPlan.model)throw configError();
  const count=visualPlan.image_count??1;
  if(!Number.isInteger(count)||count<1||count>3)throw configError();
  imageUpper=count*rate('AI_VISUALS_'+provider+'_MAX_USD_PER_IMAGE');
  if(!Number.isFinite(imageUpper)||imageUpper<=0)throw configError();
 }
 if(keys.key_source!=='operator'&&!visualPlan.enabled)return;
 const daily=rate('MAX_PROVIDER_DAILY_USD');
 const ceiling=Number.isNaN(daily)&&process.env.MAX_PROVIDER_DAILY_USD===undefined?10:daily;
 const upper=Math.ceil((textUpper+imageUpper)*1e6)/1e6;
 if(!Number.isFinite(upper)||!Number.isFinite(ceiling)||ceiling<=0||ceiling>100000)throw configError();
 if(!dbCheck(await sb.rpc('reserve_operator_cost',{p_id:id,p_upper:upper,p_daily:ceiling})))throw new HttpError(503,'The configured daily provider budget has been reserved. Try after the UTC reset. No campaign allowance was consumed.','COST_BUDGET_REACHED');
 return {upper_usd:upper,text_upper_usd:textUpper,image_upper_usd:imageUpper};
}
