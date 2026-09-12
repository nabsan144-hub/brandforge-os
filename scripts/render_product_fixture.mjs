import {readFileSync} from 'node:fs';
import {campaignInput} from '../cloud/api/_lib/routes/campaigns.js';
import {runCampaign,PLANS} from '../cloud/api/_lib/engine.js';
const {body,plan,preview}=JSON.parse(readFileSync(0,'utf8'));
globalThis.fetch=()=>{throw new Error('Provider access prohibited in fixture');};
try{
 const input=campaignInput(preview?{...body,provider:'offline',visuals_ai:false}:body,PLANS[plan]);
 const result=await runCampaign(input);
 if(preview)result.files=result.files.filter(f=>/^(hero_banner|banner_.*)\.svg$/.test(f.name));
 process.stdout.write(JSON.stringify({ok:true,data:{...result,name:body.name||'Product QA',product:input.product,brief:input,id:'00000000-0000-4000-8000-000000000004',revision:1,revisions:[],created_at:'2026-09-11T00:00:00Z',notice:'Template preview only. No allowance used.'}}));
}catch(e){process.stdout.write(JSON.stringify({ok:false,status:e.status||500,error:e.message}));}
