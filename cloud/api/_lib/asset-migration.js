import {writeFile} from 'node:fs/promises';
import {dbCheck,HttpError} from './http.js';
import {encodeAssetBundle,privateBucket,stageAssetBundle} from './assets.js';
export async function migrateInlineCampaign(sb,{uid,campaignId,bucket,apply=false}){
 const row=dbCheck(await sb.from('campaigns').select('*').eq('id',campaignId).eq('user_id',uid).maybeSingle());
 if(!row)throw new HttpError(404,'Campaign not found.');
 if(row.visual_version_id)throw new HttpError(409,'Versioned vector corrections must stay inline until visual-history storage migration is supported.');
 if(row.asset_bundle_id)return {ok:true,already_private:true,campaign_id:row.id};
 const pack=encodeAssetBundle(row.files);
 const summary={campaign_id:row.id,revision:row.revision,files:pack.manifest.length,bytes:pack.data.length,sha256:pack.sha256};
 if(!apply)return {...summary,dry_run:true};
 await privateBucket(sb,bucket);
 const bundle=await stageAssetBundle(sb,{uid,sourceCampaignId:row.id,sourceRevision:row.revision,files:row.files,bucket});
 const result=dbCheck(await sb.rpc('attach_migrated_asset_bundle',{p_uid:uid,p_campaign:row.id,p_revision:row.revision,p_bundle:bundle.id}));
 return {...summary,...result,dry_run:false};
}

// CLI-only fallback for old inline rows that exceed Vercel or bundle caps.
export async function recoverInlineCampaign(sb,{uid,campaignId,path}){
 const row=dbCheck(await sb.from('campaigns').select('*').eq('id',campaignId).eq('user_id',uid).maybeSingle());
 if(!row)throw new HttpError(404,'Campaign not found.');
 if(row.asset_bundle_id)throw new HttpError(409,'Use the authenticated workspace export for private campaigns.');
 const revisions=dbCheck(await sb.from('campaign_revisions').select('*').eq('campaign_id',row.id).eq('user_id',uid))||[];
 const visual_versions=dbCheck(await sb.from('campaign_visual_versions').select('*').eq('campaign_id',row.id).eq('user_id',uid))||[];
 const data=JSON.stringify({schema:2,campaign:row,revisions,visual_versions},null,2);
 await writeFile(path,data,{mode:0o600,flag:'wx'});
 return {ok:true,bytes:Buffer.byteLength(data)};
}
