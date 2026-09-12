import {HttpError,dbCheck} from './http.js';
// Three requests, <=1800 output tokens each, bounded UTF-8 prompts. 60k tokens
// is a deliberately conservative upper reservation, NOT measured usage.
export const MAX_RUN_TOKEN_RESERVATION=60000;
export async function reserveOperatorBudget(sb,id,keys){
 if(keys.key_source!=='operator')return;
 const provider=keys.groqKey?'GROQ':'GEMINI';
 const names=[provider+'_INPUT_USD_PER_MTOK',provider+'_OUTPUT_USD_PER_MTOK'];
 const rates=names.map(n=>!String(process.env[n]??'').trim()?NaN:Number(process.env[n]));
 const daily=Number(process.env.MAX_PROVIDER_DAILY_USD||10);
 if(rates.some(x=>!Number.isFinite(x)||x<0)||!Number.isFinite(daily)||daily<=0)throw new HttpError(503,'Operator provider pricing and daily budget need configuration. No provider request was started.','COST_GUARD_UNCONFIGURED');
 const upper=Math.ceil(MAX_RUN_TOKEN_RESERVATION*Math.max(...rates)/1000000*1e6)/1e6;
 if(!Number.isFinite(upper))throw new HttpError(503,'Provider pricing is outside the supported range.','COST_GUARD_UNCONFIGURED');
 if(!dbCheck(await sb.rpc('reserve_operator_cost',{p_id:id,p_upper:upper,p_daily:daily})))throw new HttpError(503,'The configured daily provider budget has been reserved. Try after the UTC reset. No campaign allowance was consumed.','COST_BUDGET_REACHED');
}
