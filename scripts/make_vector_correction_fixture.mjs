import {createRequire} from 'node:module';
const sharp=createRequire(new URL('../cloud/package.json',import.meta.url))('sharp');
import {createHash} from 'node:crypto';
import {bannerSvg} from '../cloud/api/_lib/visuals.js';
import {runCampaign,PLANS,AD_SIZES} from '../cloud/api/_lib/engine.js';
import {redrawVectors,correctionFields,correctionLayout,normalizeCorrectionLayout} from '../cloud/api/_lib/vector-corrections.js';
import {mkdirSync,writeFileSync} from 'node:fs';
const dir=process.argv[2];mkdirSync(dir,{recursive:true});
const brief={product:'Apex Coffee',benefits:'Fresh-roasted beans, Clear origin details',provider:'offline',watermark:true,style:'bold',custom_presets:1,custom_sizes:[{preset:'mobile_banner'}]};
const result=await runCampaign(brief),fields=correctionFields({headline:'Fresh coffee today',subheadline:'Roasted for your morning',offer:'Rs 250 today',cta:'Shop today',destination:'https://example.test/coffee',benefits:result.visual_recipe.common.benefits.join('; '),proof:result.visual_recipe.common.proof||''});
if(process.env.BF_QA_SCENE==='1'){
 const scene='data:image/jpeg;base64,'+(await sharp({create:{width:600,height:300,channels:3,background:'#926848'}}).jpeg().toBuffer()).toString('base64');
 result.visual_recipe={...result.visual_recipe,schema:2,scene_sha256:createHash('sha256').update(scene).digest('hex')};result.visual_status={mode:'ai',state:'generated',provider:'fixture',model:'no-provider-called'};
 result.files[0].content=bannerSvg({...result.visual_recipe.common,...result.visual_fields,scene,width:1200,height:630});
}
const logo=await sharp({create:{width:64,height:40,channels:4,background:{r:24,g:96,b:60,alpha:.8}}}).png().toBuffer();writeFileSync(dir+'/replacement-logo.png',logo);
const before={...result,id:'00000000-0000-4000-8000-000000000002',product:brief.product,name:'Coffee correction QA',brief,revision:1,revisions:[],lang:'en',created_at:'2026-09-11T00:00:00Z'};
const layout=await normalizeCorrectionLayout(correctionLayout({logo:'data:image/png;base64,'+logo.toString('base64'),logo_rights:true},before));
const patch=redrawVectors(before,fields,layout);
const after={...before,visual_recipe:patch.recipe,files:patch.files,visual_fields:fields,visual_field_report:patch.report,visual_version_id:'00000000-0000-4000-8000-000000000003',visual_review_state:'review_required',revision:2,revisions:[{revision:1,created_at:before.created_at}]};
const restored={...before,revision:3,visual_version_id:'00000000-0000-4000-8000-000000000004',visual_review_state:'review_required',revisions:[{revision:2,created_at:before.created_at},{revision:1,created_at:before.created_at}]};
writeFileSync(dir+'/fixtures.json',JSON.stringify({before,after,restored,fields,limits:PLANS.free,sizes:AD_SIZES}));
