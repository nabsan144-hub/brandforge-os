import {describe,it,expect,vi,afterEach} from 'vitest';
import sharp from 'sharp';
import {campaignInput} from '../api/_lib/routes/campaigns.js';
import {runCampaign,PLANS} from '../api/_lib/engine.js';
import {resolveVisualPlan} from '../api/_lib/visual-plan.js';
import {reserveOperatorBudget} from '../api/_lib/cost.js';
import {assertCampaignPayload} from '../api/_lib/payload.js';
import {validateDocument} from '../public/canvas/model.js';
import {generateScene} from '../api/_lib/visuals_ai.js';
const brief={product_name:'Fixture Kitchen',industry:'Food',benefits:'Crispy chicken',offer:'Lunch menu',cta:'View menu',visuals_ai:true,visual_provider:'gemini',artwork_mode:'campaign',provider:'auto'};
function enable(provider='gemini'){
 vi.stubEnv('AI_CAMPAIGN_ENABLED','true');vi.stubEnv('AI_VISUALS_ENABLED','true');vi.stubEnv('AI_VISUALS_PROVIDER',provider);vi.stubEnv('AI_VISUAL_MODEL',provider==='gemini'?'gemini-3-pro-image':'gpt-image-2.5-sunburst');
 vi.stubEnv('AI_VISUALS_KEY','gemini-private-fixture');vi.stubEnv('AI_VISUALS_OPENAI_KEY','openai-private-fixture');
 vi.stubEnv('AI_VISUALS_'+provider.toUpperCase()+'_COST_MODEL',provider==='gemini'?'gemini-3-pro-image':'gpt-image-2.5-sunburst');vi.stubEnv('AI_VISUALS_'+provider.toUpperCase()+'_MAX_USD_PER_IMAGE','.25');vi.stubEnv('MAX_PROVIDER_DAILY_USD','10');
}
afterEach(()=>{vi.unstubAllEnvs();vi.unstubAllGlobals();});
async function png(){return (await sharp({create:{width:120,height:80,channels:3,background:'#cc4411'}}).png().toBuffer()).toString('base64');}
describe('AI-first campaign execution',()=>{
 it('generates three distinct requests and exports real portable canvases, not basic variants',async()=>{
  enable();const data=await png();const calls=[];
  vi.stubGlobal('fetch',vi.fn(async(url,options)=>{calls.push(JSON.parse(options.body));return {ok:true,json:async()=>({candidates:[{content:{parts:[{inlineData:{mimeType:'image/png',data}}]}}]})};}));
  const input=campaignInput(brief,PLANS.pro);const r=await runCampaign(input,{key_source:'offline'});
  expect(calls).toHaveLength(3);expect(calls.map(x=>x.generationConfig.imageConfig.aspectRatio).sort()).toEqual(['16:9','1:1','9:16']);
  expect(r.visual_status).toMatchObject({scope:'campaign_formats',formats:3,state:'generated'});
  expect(r.visual_recipe.schema).toBe(3);expect(r.files.filter(f=>f.name.endsWith('.svg'))).toHaveLength(3);
  for(const f of r.files.filter(f=>f.name.startsWith('canvas_'))){const d=validateDocument(JSON.parse(f.content));expect(d.layers[0].type).toBe('image');}
  expect(JSON.stringify(r)).not.toContain('private-fixture');assertCampaignPayload(r);
 });
 it('reserves three model-bound image upper costs before execution',async()=>{
  enable();const rpc=vi.fn(async()=>({data:true}));await reserveOperatorBudget({rpc},'request',{key_source:'offline'},resolveVisualPlan(campaignInput(brief,PLANS.pro)));
  expect(rpc).toHaveBeenCalledWith('reserve_operator_cost',{p_id:'request',p_upper:.75,p_daily:10});
 });
 it('image failure rejects the campaign, never returns a successful vector substitution',async()=>{
  enable();vi.stubGlobal('fetch',vi.fn(async()=>({ok:false,status:503})));
  await expect(runCampaign(campaignInput(brief,PLANS.pro),{key_source:'offline'})).rejects.toMatchObject({code:'VISUAL_PROVIDER_ERROR'});
 });
 it('no-AI and free plans cannot initiate AI campaign calls',()=>{
  expect(()=>campaignInput({...brief,provider:'offline'},PLANS.pro)).toThrow();expect(()=>campaignInput(brief,PLANS.free)).toThrow();
 });
 it('new campaign mode requires separate operator enablement',()=>{
  enable();vi.stubEnv('AI_CAMPAIGN_ENABLED','false');expect(()=>resolveVisualPlan(campaignInput(brief,PLANS.pro))).toThrow(expect.objectContaining({code:'AI_CAMPAIGN_UNAVAILABLE'}));
 });
 it('consented product photos are accepted in AI campaign mode without a basic Product-first style',async()=>{
  const product_image='data:image/jpeg;base64,'+(await sharp({create:{width:100,height:100,channels:3,background:'#112233'}}).jpeg().toBuffer()).toString('base64');
  const input=campaignInput({...brief,style:'bold',product_image,product_image_rights:true,reference_consent:true},PLANS.pro);expect(input.product_image).toBe(product_image);
 });
 it('malformed references are rejected before any provider fetch',async()=>{
  const spy=vi.fn();vi.stubGlobal('fetch',spy);
  await expect(generateScene({product:'Fixture'},{provider:'gemini',key:'fixture',model:'gemini-3-pro-image',referenceImages:['data:image/png;base64,aW52YWxpZA==']})).rejects.toMatchObject({code:'VISUAL_BAD_REQUEST'});expect(spy).not.toHaveBeenCalled();
 });
 it('changed model consent is not accepted',()=>{enable();expect(()=>resolveVisualPlan({...campaignInput(brief,PLANS.pro),visual_model:'old-model'})).toThrow(expect.objectContaining({code:'VISUAL_CONSENT_REQUIRED'}));});
 it('references require explicit consent even with image-generation consent',async()=>{
  const product_image='data:image/jpeg;base64,'+(await sharp({create:{width:100,height:100,channels:3,background:'#112233'}}).jpeg().toBuffer()).toString('base64');
  expect(()=>campaignInput({...brief,product_image,product_image_rights:true},PLANS.pro)).toThrow(expect.objectContaining({code:'VISUAL_REFERENCE_CONSENT_REQUIRED'}));
 });
 it('Gemini references use inline image parts and selected aspect',async()=>{
  enable();const data=await png();let sent;
  vi.stubGlobal('fetch',vi.fn(async(url,options)=>{sent=JSON.parse(options.body);return {ok:true,json:async()=>({candidates:[{content:{parts:[{inlineData:{mimeType:'image/png',data}}]}}]})};}));
  await generateScene({product:'Fixture',artwork_mode:'campaign'},{provider:'gemini',key:'fixture',model:'gemini-3-pro-image',format:'story',referenceImages:['data:image/png;base64,'+data]});
  expect(sent.contents[0].parts).toHaveLength(2);expect(sent.generationConfig.imageConfig.aspectRatio).toBe('9:16');
 });
 it('OpenAI references use edits multipart, not the generation JSON endpoint',async()=>{
  enable('openai');const data=await png();let sent;
  vi.stubGlobal('fetch',vi.fn(async(url,options)=>{sent={url,options};return {ok:true,json:async()=>({data:[{b64_json:data}]})};}));
  await generateScene({product:'Fixture',artwork_mode:'campaign'},{provider:'openai',key:'fixture',model:'gpt-image-2.5-sunburst',format:'square',referenceImages:['data:image/png;base64,'+data]});
  expect(sent.url).toBe('https://api.openai.com/v1/images/edits');expect(sent.options.body).toBeInstanceOf(FormData);expect(sent.options.body.getAll('image[]')).toHaveLength(1);expect(sent.options.headers['Content-Type']).toBeUndefined();
 });
});
