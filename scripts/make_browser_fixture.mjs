// Synthetic fixture data only; not a live account, payment or provider sample.
import {runCampaign,PLANS,AD_SIZES} from '../cloud/api/_lib/engine.js';
import {publicPlans} from '../cloud/api/_lib/plans.js';
import {mkdirSync,writeFileSync} from 'node:fs';
const destination=process.argv[2]||'qa-results';mkdirSync(destination,{recursive:true});
const brief={product:'Apex Coffee',industry:'Specialty Coffee',audience:'Busy professionals',benefits:'Fresh-roasted beans, clear origin details',lang:'en',custom_any:true,custom_presets:21,custom_sizes:[{preset:'leaderboard'},{preset:'mobile_banner'}]};
const r=await runCampaign(brief);
const campaign={...r,id:'00000000-0000-4000-8000-000000000002',name:'Reviewed coffee campaign',product:brief.product,brief,revision:1,revisions:[],lang:'en',created_at:'2026-09-05T00:00:00Z'};
writeFileSync(destination+'/cloud-fixture.json',JSON.stringify({campaign,limits:PLANS,sizes:AD_SIZES,plans:publicPlans()}));
