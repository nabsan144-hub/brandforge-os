// Operator-only, one explicitly selected owner/campaign. Never run automatically.
// Export recovery writes private customer data: use an encrypted operator disk.
import {createClient} from '@supabase/supabase-js';
import {UUID} from '../api/_lib/http.js';
import {migrateInlineCampaign,recoverInlineCampaign} from '../api/_lib/asset-migration.js';
const args=process.argv.slice(2),take=key=>{const i=args.indexOf(key);return i<0?null:args[i+1];};
try{
 const uid=take('--owner'),campaignId=take('--campaign');
 if(!UUID.test(uid||'')||!UUID.test(campaignId||''))throw new Error('Usage: node cloud/scripts/migrate-private-assets.mjs --owner UUID --campaign UUID [--apply | --recover FILE.json]. Default: read-only dry run. Supply SUPABASE_URL and SUPABASE_SERVICE_ROLE_KEY securely in the environment.');
 if(args.includes('--apply')&&args.includes('--recover'))throw new Error('Recovery and apply are separate operations.');
 const sb=createClient(process.env.SUPABASE_URL,process.env.SUPABASE_SERVICE_ROLE_KEY,{auth:{persistSession:false}});
 if(args.includes('--recover')){
  const path=take('--recover');if(!path||path.startsWith('--'))throw new Error('Recovery requires a new output filename.');
  await recoverInlineCampaign(sb,{uid,campaignId,path});
  console.log('Private recovery file written. Verify its files before any migration.');
 }else{
  console.log(JSON.stringify(await migrateInlineCampaign(sb,{uid,campaignId,bucket:process.env.CAMPAIGN_ASSET_BUCKET,apply:args.includes('--apply')}),null,2));
 }
}catch(e){console.error(e.status?e.message:e.message?.startsWith('Usage:')?e.message:'Operation failed. Check configuration, arguments and database/storage access. No automatic deletion was attempted.');process.exitCode=1;}
