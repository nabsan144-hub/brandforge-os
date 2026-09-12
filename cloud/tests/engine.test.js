import {describe,it,expect,vi,afterEach,beforeEach} from 'vitest';
import {PLANS,runCampaign,fallback,completeCopy} from '../api/_lib/engine.js';
const input={product:'Apex Coffee',industry:'Specialty Coffee',audience:'Busy professionals',benefits:'Organic beans; same-day delivery',watermark:false};
afterEach(()=>vi.unstubAllGlobals());
describe('bounded plans and honest generation',()=>{
 it('separates Desktop ownership and caps Cloud capacity',()=>{expect(PLANS.free.lifetime).toBe(3);expect(PLANS.pro.monthly).toBe(50);expect(PLANS.agency.monthly).toBe(300);expect(PLANS.agency.concurrency).toBe(2);expect(PLANS.desktop_solo).toBeUndefined();expect(PLANS.desktop_agency).toBeUndefined();});
 it('returns complete, grounded templates, assets and explicit provenance',async()=>{const r=await runCampaign(input);expect(r.provider).toBe('offline');expect(r.research_live).toBe(false);expect(r.strategy).toContain('No market research');expect(r.seo).toContain('Not measured');expect(r.seo).not.toContain('78/100');expect(completeCopy(r.copy)).toBe(true);expect(r.copy).toContain('Apex Coffee');expect(r.copy).not.toContain('marketing machine');expect(r.copy).not.toContain('Founder,');expect(r.stage_status.copy.state).toBe('template');});
 it('escapes SVG input and visibly labels a Free preview',async()=>{const r=await runCampaign({...input,product:'<img src=x onerror=1>',watermark:true});const svg=r.files[0].content;expect(svg).not.toContain('<img');expect(svg).not.toContain('<script');expect(svg).toContain('Made with BrandForge');});
 it('retains successful provider stages if one request fails',async()=>{
  const prompts=[];
  vi.stubGlobal('fetch',vi.fn(async(url,options)=>{
   const body=JSON.parse(options.body);const text=JSON.stringify(body);
   prompts.push(text);
   if(text.includes('AIDA'))return {ok:false,status:429};
   const content=text.includes('positioning')
    ?'Provider strategy, based on the supplied coffee brief.'
    :'Provider SEO suggestions; no actual URL audit was performed.';
   return {ok:true,json:async()=>({choices:[{message:{content}}],usage:{prompt_tokens:100,completion_tokens:50}})};
  }));
  const r=await runCampaign(input,{groqKey:'fixture',key_source:'personal'});expect(r.provider).toBe('mixed');expect(r.strategy).toContain('Provider strategy');expect(r.stage_status.copy).toMatchObject({state:'fallback',reason:'PROVIDER_RATE_LIMIT'});expect(r.copy).toContain('Welcome Email');expect(r.provider_usage.input_tokens).toBe(200);
  expect(prompts.filter(p=>p.includes('AIDA'))).toHaveLength(3); // 429 + 2 backoff retries
 });
 it('sends explicit Urdu instructions to every task, preserves names, and uses the selected Gemini key',async()=>{
  const prompts=[];vi.stubGlobal('fetch',vi.fn(async(url,options)=>{const b=JSON.parse(options.body);prompts.push({url,body:b,headers:options.headers});const stage=prompts.length===1?'strategy':prompts.length===2?'copy':'seo';return {ok:true,json:async()=>({candidates:[{content:{parts:[{text:fallback(stage,input,'ur')}]}}],usageMetadata:{promptTokenCount:100,candidatesTokenCount:100}})};}));
  const r=await runCampaign({...input,lang:'ur'},{geminiKey:'fixture-gemini',key_source:'personal'});expect(r.provider).toBe('gemini');expect(prompts).toHaveLength(3);for(const p of prompts){expect(p.body.systemInstruction.parts[0].text).toContain('Urdu');expect(p.body.contents[0].parts[0].text).toContain('Apex Coffee');expect(p.headers['x-goog-api-key']).toBe('fixture-gemini');expect(p.body.generationConfig.maxOutputTokens).toBe(1800);}
 });
 it('labels invalid language, incomplete copy and invented SEO scores as fallbacks',async()=>{
  vi.stubGlobal('fetch',vi.fn(async()=>({ok:true,json:async()=>({choices:[{message:{content:'English output that is not the requested Urdu.'}}]})})));
  const r=await runCampaign({...input,lang:'ur'},{groqKey:'fixture'});expect(r.provider).toBe('offline');expect(r.stage_status.copy.reason).toBe('LANGUAGE_CHECK_FAILED');
  let n=0;vi.stubGlobal('fetch',vi.fn(async()=>({ok:true,json:async()=>({choices:[{message:{content:++n===3?'SEO score: 78/100, everything looks great.':'This is a long but incomplete English response.'}}]})})));
  const e=await runCampaign(input,{groqKey:'fixture'});expect(e.stage_status.copy.reason).toBe('STRUCTURE_CHECK_FAILED');expect(e.stage_status.seo.reason).toBe('UNSUPPORTED_SCORE');
 });
 it('backoff retries a 429 and binds the generated headline into every banner',async()=>{
  const copy=`AIDA AD
Headline: Karachi's mornings start with karak
Subheadline: Brewed to order, delivered hot, no queue, no compromises.
Ad body: Short benefit-led lines from the brief only.
PAS POST
Problem: Waiting in traffic ruins the morning.
Agitate: Store tea bags taste flat.
Solution: Real milk and tea leaves brewed to order.
WELCOME EMAIL
Subject: Your first cup of karak
Preheader: Brewed to order and delivered hot.
Body: Order today and taste the difference.
LANDING PAGE HERO
Headline: Karachi's mornings start with karak
Subheadline: Brewed to order, delivered hot, no queue, no compromises.
CTA Button: Order Now`;
  const calls=[];
  vi.stubGlobal('fetch',vi.fn(async(url,options)=>{
   const text=JSON.stringify(JSON.parse(options.body));
   calls.push(text.includes('AIDA')?'copy':text.includes('positioning')?'strategy':'seo');
   if(text.includes('AIDA')&&calls.filter(c=>c==='copy').length===1)return {ok:false,status:429};
   const content=text.includes('positioning')?'Provider strategy, based on the supplied coffee brief.':text.includes('AIDA')?copy:'Provider SEO suggestions; no actual URL audit was performed.';
   return {ok:true,json:async()=>({choices:[{message:{content}}],usage:{prompt_tokens:100,completion_tokens:50}})};
  }));
  const r=await runCampaign({...input,benefits:'Skip the 45-minute queue;Real milk and tea leaves;Brewed to order'},{groqKey:'fixture',key_source:'personal'});
  expect(r.provider).toBe('groq');expect(r.stage_status.copy.state).toBe('generated');
  expect(r.files.filter(f=>f.name.endsWith('.svg')).length).toBeGreaterThanOrEqual(5);
  const hero=r.files[0].content;
  expect(hero).toContain('Karachi&apos;s mornings start with karak');
  expect(hero).toContain('no queue, no compromises');
  expect(calls.filter(c=>c==='copy').length).toBe(2); // 429 once, then backoff success
 });
 describe('v1.8 AI artwork scenes',()=>{
  beforeEach(()=>{process.env.AI_VISUALS_ENABLED='true';});
  const PNG='iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mP8z8BQDwAEhQGAhKmMIQAAAABJRU5ErkJggg==';
  function imageFetch(imageOK){
   const urls=[];
   vi.stubGlobal('fetch',vi.fn(async(url,options)=>{
    const u=String(url);
    if(u.includes('generativelanguage.googleapis.com')){urls.push('gemini');
     if(!imageOK)return {ok:false,status:429};
     return {ok:true,json:async()=>({candidates:[{content:{parts:[{inlineData:{mimeType:'image/png',data:PNG}}]}}]})};}
    if(u.includes('api.openai.com')){urls.push('openai');
     if(!imageOK)return {ok:false,status:429};
     return {ok:true,json:async()=>({data:[{b64_json:PNG}]})};}
    if(u.includes('api.x.ai')){urls.push('xai');
     if(!imageOK)return {ok:false,status:429};
     return {ok:true,json:async()=>({data:[{b64_json:PNG}]})};}
    const text=JSON.stringify(JSON.parse(options.body));
    urls.push('text');
    const content=text.includes('positioning')?'Provider strategy, based on the supplied coffee brief.'
     :text.includes('AIDA')?'AIDA AD\nHeadline: Karachi\'s mornings start with karak\nSubheadline: Brewed to order, delivered hot, no queue, no compromises.\nAd body: Real milk and tea leaves brewed to order.\nPAS POST\nProblem: Waiting in traffic ruins the morning.\nAgitate: Store tea bags taste flat.\nSolution: Brewed to order.\nWELCOME EMAIL\nSubject: Your first cup of karak\nPreheader: Brewed to order.\nBody: Order today.\nLANDING PAGE HERO\nHeadline: Karachi\'s mornings start with karak\nSubheadline: Brewed to order, delivered hot.\nCTA Button: Order Now'
     :'Provider SEO suggestions; no actual URL audit was performed.';
    return {ok:true,json:async()=>({choices:[{message:{content}}],usage:{prompt_tokens:100,completion_tokens:50}})};
   }));
   return urls;
  }
  afterEach(()=>{delete process.env.AI_VISUALS_ENABLED;delete process.env.AI_VISUALS_KEY;delete process.env.AI_VISUALS_OPENAI_KEY;delete process.env.AI_VISUALS_XAI_KEY;delete process.env.AI_VISUALS_PROVIDER;delete process.env.AI_VISUAL_MODEL;});
  it('embeds a Gemini scene into the hero for explicitly opted-in paid packs',async()=>{
   process.env.AI_VISUALS_KEY='fixture';const urls=imageFetch(true);
   const r=await runCampaign({...input,visuals_ai:true,visual_provider:process.env.AI_VISUALS_PROVIDER||'gemini'},{groqKey:'fixture',key_source:'personal'});
   expect(r.visual_status).toMatchObject({mode:'ai',provider:'gemini'});
   expect(urls).toContain('gemini');
   expect(r.files[0].name).toBe('hero_banner.svg');
   expect(r.files[0].content).toContain('data:image/jpeg;base64,');
   expect(r.files[0].content).toContain('<image href=');
   expect(r.files[0].content).toContain('Karachi&apos;s mornings start with karak');
   expect(r.files.every(f=>!f.name.startsWith('logo_')||!f.content.includes('data:image'))).toBe(true);
  });
  it('keeps SVG visuals when the scene provider fails or no key is set',async()=>{
   process.env.AI_VISUALS_KEY='fixture';let urls=imageFetch(false);
   const a=await runCampaign({...input,visuals_ai:true,visual_provider:process.env.AI_VISUALS_PROVIDER||'gemini'},{groqKey:'fixture'});
   expect(a.visual_status).toMatchObject({mode:'svg',reason:'VISUAL_RATE_LIMIT'});
   expect(a.files[0].content).not.toContain('data:image/jpeg;base64,');
   delete process.env.AI_VISUALS_KEY;
   urls=imageFetch(true);
   const b=await runCampaign({...input,visuals_ai:true,visual_provider:process.env.AI_VISUALS_PROVIDER||'gemini'},{groqKey:'fixture'});
   expect(b.visual_status.mode).toBe('svg');
   expect(urls).not.toContain('gemini');
  });
  it('uses the OpenAI lane when the operator selects it',async()=>{
   process.env.AI_VISUALS_PROVIDER='openai';process.env.AI_VISUALS_OPENAI_KEY='sk-fixture';const urls=imageFetch(true);
   const r=await runCampaign({...input,visuals_ai:true,visual_provider:process.env.AI_VISUALS_PROVIDER||'gemini'},{groqKey:'fixture'});
   expect(r.visual_status).toMatchObject({mode:'ai',provider:'openai'});
   expect(urls).toContain('openai');
   expect(r.files[0].content).toContain('data:image/jpeg;base64,');
  });
  it('uses the xAI (Grok Imagine) lane when the operator selects it',async()=>{
   process.env.AI_VISUALS_PROVIDER='xai';process.env.AI_VISUALS_XAI_KEY='xk-fixture';const urls=imageFetch(true);
   const r=await runCampaign({...input,visuals_ai:true,visual_provider:process.env.AI_VISUALS_PROVIDER||'gemini'},{groqKey:'fixture'});
   expect(r.visual_status).toMatchObject({mode:'ai',provider:'xai'});
   expect(urls).toContain('xai');
   expect(r.files[0].content).toContain('data:image/jpeg;base64,');
  });
 });
});
it('does not start provider calls when the end-to-end deadline is exhausted',async()=>{
 const fetch=vi.fn();vi.stubGlobal('fetch',fetch);const r=await runCampaign(input,{groqKey:'fixture',key_source:'personal',deadline:Date.now()-1});expect(fetch).not.toHaveBeenCalled();expect(r.stage_status.copy.reason).toBe('EXECUTION_DEADLINE');expect(r.provider).toBe('offline');
});
