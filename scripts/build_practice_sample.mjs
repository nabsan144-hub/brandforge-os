// Reproducible, pre-rendered demonstration. No account, quota or provider calls.
import {runCampaign} from '../cloud/api/_lib/engine.js';
import {writeFileSync,mkdirSync} from 'node:fs';
import {createHash} from 'node:crypto';
const originalFetch=globalThis.fetch;
globalThis.fetch=()=>{throw new Error('Practice build must never access providers');};
const input={product:'Northline Coffee',industry:'Specialty Coffee',audience:'People choosing coffee for home',benefits:'Whole beans or ground; Choose your roast',offer:'250 g · Rs 1,450',cta:'Explore the roasts',primary:'#BB4A2B',secondary:'#F8F1E5',provider:'offline',lang:'en',style:'editorial-v1',watermark:true,custom_presets:3,custom_sizes:[{preset:'instagram_square'},{preset:'fb_story'},{preset:'fb_feed'}],generate_new_logo:false};
const root=new URL('../cloud/public/assets/practice/',import.meta.url);mkdirSync(root,{recursive:true});
const manifest={schema:1,notice:'Fictional, pre-rendered offline demonstration. No provider calls or account allowance. Three selected sizes are shown for comparison, not a statement of Free-plan entitlement. Human proofreading is required. Revisions shown are separately rendered example briefs, not an AI image correction.',files:[]};
try {
 for(const [name,offer]of [['original',input.offer],['revised','500 g · Rs 2,700']]){
  const brief={...input,offer},pack=await runCampaign(brief);
  const sample={...pack,id:'practice-'+name,name:'Northline-practice-'+name,product:brief.product,brief,revision:1,visual_review_state:'unchanged',created_at:'2026-09-11T00:00:00Z',sample_notice:manifest.notice};
  const bytes=JSON.stringify(sample);writeFileSync(new URL(name+'.json',root),bytes);
  manifest.files.push({name:name+'.json',sha256:createHash('sha256').update(bytes).digest('hex'),bytes:Buffer.byteLength(bytes)});
 }
 writeFileSync(new URL('manifest.json',root),JSON.stringify(manifest,null,2)+'\n');
} finally {globalThis.fetch=originalFetch;}
