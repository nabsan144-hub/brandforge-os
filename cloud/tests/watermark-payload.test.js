import {describe,it,expect,vi,afterEach} from 'vitest';
import {bannerSvg,logoSvg,WATERMARK_TEXT,watermarkFooter} from '../api/_lib/visuals.js';
import {runCampaign,AD_SIZES,PLANS} from '../api/_lib/engine.js';
import {campaignInput} from '../api/_lib/routes/campaigns.js';
import {assertCampaignPayload,boundedJson,MAX_CAMPAIGN_JSON_BYTES} from '../api/_lib/payload.js';
import {generateScene,MAX_SOURCE_SCENE_BYTES,MAX_IMAGE_RESPONSE_BYTES} from '../api/_lib/visuals_ai.js';
const brief={product:'Northline Coffee',benefits:['Fresh-roasted beans','Clear origin details'],cta:'Explore the coffee',primary:'#E8B54A',secondary:'#0F172A'};
afterEach(()=>{vi.unstubAllGlobals();vi.unstubAllEnvs();});

describe('visible Free attribution',()=>{
 it.each(['bold','essential'])('marks every advertised size including strip/micro layouts: %s',style=>{
  for(const [width,height] of [...Object.values(AD_SIZES),[50,50]]){
   const svg=bannerSvg({...brief,width,height,watermark:true,style});
   expect(svg).toContain(`width="${width}" height="${height}"`);
   expect(svg.match(/data-watermark="brandforge"/g)).toHaveLength(1);
   expect(svg).toContain(`aria-label="${WATERMARK_TEXT}"`);
   const footer=watermarkFooter(width,height);
   expect(svg).toContain(`y="${height-footer.height}" width="${width}" height="${footer.height}"`);
   expect(svg).toContain(`height="${height-footer.height}" viewBox=`);
   expect(svg.indexOf('data-watermark')).toBeGreaterThan(svg.lastIndexOf('</svg>')-footer.svg.length-10);
  }
 });
 it('renders readable attribution instead of relying on viewer fonts',()=>{
  const footer=watermarkFooter(1200,630).svg;
  expect(footer).toContain('Made with BrandForge');expect(footer).toContain('<path');expect(footer).not.toContain('<text');
  expect(footer).toContain('fill="#101820"');expect(footer).toContain('fill="#FFFFFF"');
 });
 it('uses compact visible text on tiny canvases without losing attribution metadata',()=>{
  expect(watermarkFooter(50,50).svg).toContain('data-text="BF"');
  expect(watermarkFooter(160,600).svg).toContain('data-text="BrandForge"');
 });
 it('marks generated logo concepts, not paid output',()=>{
  for(const style of ['lettermark','wordmark','combination','abstract','pictorial','emblem']){
   expect(logoSvg({brand:'Coffee',style,watermark:true})).toContain('data-watermark="brandforge"');
   expect(logoSvg({brand:'Coffee',style,watermark:false})).not.toContain('data-watermark');
  }
 });
 it.each(['free','pro','agency'])('server plan controls watermark, not the submitted flag: %s',async plan=>{
  const input=campaignInput({product_name:'Coffee',provider:'offline',watermark:plan!=='free'},PLANS[plan]);
  const r=await runCampaign(input);
  for(const file of r.files.filter(f=>f.name.endsWith('.svg')))expect(file.content.includes('data-watermark="brandforge"')).toBe(plan==='free');
 });
});

describe('payload safety containment',()=>{
 it('budgets complete UTF-8 JSON, not characters or decoded image bytes',()=>{
  expect(()=>assertCampaignPayload({files:[{content:'a'.repeat(MAX_CAMPAIGN_JSON_BYTES-100)}]})).not.toThrow();
  expect(()=>assertCampaignPayload({files:[{content:'a'.repeat(MAX_CAMPAIGN_JSON_BYTES)}]})).toThrow(expect.objectContaining({code:'CAMPAIGN_PAYLOAD_LIMIT'}));
  expect(()=>assertCampaignPayload({files:[{content:'ک'.repeat(1_600_000)}]})).toThrow();
 });
 it('returns a controlled legacy error before crossing the function response ceiling',()=>{
  expect(()=>boundedJson({files:[{content:'a'.repeat(4_100_000)}]})).toThrow(expect.objectContaining({code:'LEGACY_PAYLOAD_LIMIT'}));
  expect(boundedJson({files:[]})).toBeInstanceOf(Response);
 });
 it('rejects a decoded scene above the new bound even below the provider response ceiling',async()=>{
  vi.stubGlobal('fetch',vi.fn(async()=>new Response(JSON.stringify({data:[{b64_json:Buffer.alloc(MAX_SOURCE_SCENE_BYTES+1).toString('base64')}]}))));
  await expect(generateScene(brief,{provider:'openai',model:'gpt-image-1',key:'fake'})).rejects.toMatchObject({code:'VISUAL_TOO_LARGE'});
 });
 it('cancels oversized provider streams rather than collecting an unbounded body',async()=>{
  let canceled=false;
  const stream=new ReadableStream({start(c){c.enqueue(new Uint8Array(MAX_IMAGE_RESPONSE_BYTES+1));},cancel(){canceled=true;}});
  vi.stubGlobal('fetch',vi.fn(async()=>new Response(stream)));
  await expect(generateScene(brief,{provider:'openai',model:'gpt-image-1',key:'fake'})).rejects.toMatchObject({code:'VISUAL_TOO_LARGE'});
  expect(canceled).toBe(true);
 });
 it('oversized image responses fall back honestly without embedding the image',async()=>{
  vi.stubEnv('AI_VISUALS_ENABLED','true');vi.stubEnv('AI_VISUALS_PROVIDER','openai');vi.stubEnv('AI_VISUALS_OPENAI_KEY','fake');vi.stubEnv('AI_VISUAL_MODEL','gpt-image-1');
  vi.stubGlobal('fetch',vi.fn(async()=>new Response(JSON.stringify({data:[{b64_json:Buffer.alloc(MAX_SOURCE_SCENE_BYTES+1).toString('base64')}]}))));
  const r=await runCampaign({...brief,visuals_ai:true,visual_provider:'openai'});
  expect(r.visual_status).toMatchObject({mode:'svg',state:'fallback',reason:'VISUAL_TOO_LARGE'});
  expect(r.files[0].content).not.toContain('data:image/');expect(()=>assertCampaignPayload(r)).not.toThrow();
 });
 it.each(['not_base64','',null])('rejects invalid provider image encoding: %s',async data=>{
  vi.stubGlobal('fetch',vi.fn(async()=>new Response(JSON.stringify({data:[{b64_json:data}]}))));
  await expect(generateScene(brief,{provider:'openai',model:'gpt-image-1',key:'fake'})).rejects.toHaveProperty('code');
 });
});
