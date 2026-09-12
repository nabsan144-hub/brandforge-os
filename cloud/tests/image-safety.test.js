import {describe,it,expect,vi,afterEach,beforeAll,afterAll} from 'vitest';
import {randomUUID} from 'node:crypto';
import {runCampaign} from '../api/_lib/engine.js';
import {campaignInput} from '../api/_lib/routes/campaigns.js';
import {PLANS} from '../api/_lib/engine.js';
import {resolveVisualPlan,visualConfig} from '../api/_lib/visual-plan.js';
import {reserveOperatorBudget} from '../api/_lib/cost.js';
import {openAIImageBody} from '../api/_lib/visuals_ai.js';
import {database} from './helpers/db.js';

const brief={product_name:'Audit Coffee',industry:'Coffee',audience:'Office workers',benefits:'Fresh beans',provider:'auto',visuals_ai:true,visual_provider:'openai'};
const PNG='iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mP8z8BQDwAEhQGAhKmMIQAAAABJRU5ErkJggg==';
function enable(){
 vi.stubEnv('AI_VISUALS_ENABLED','true');vi.stubEnv('AI_VISUALS_PROVIDER','openai');vi.stubEnv('AI_VISUAL_MODEL','gpt-image-1');
 vi.stubEnv('AI_VISUALS_OPENAI_KEY','fake-private-key');vi.stubEnv('AI_VISUALS_OPENAI_COST_MODEL','gpt-image-1');
 vi.stubEnv('AI_VISUALS_OPENAI_MAX_USD_PER_IMAGE','.20');vi.stubEnv('MAX_PROVIDER_DAILY_USD','10');
}
afterEach(()=>{vi.unstubAllEnvs();vi.unstubAllGlobals();});

describe('explicit provider sharing',()=>{
 it.each(['free','pro','agency'])('no-AI overrides every key and imagery request for %s',async(plan)=>{
  enable();const fetch=vi.fn();vi.stubGlobal('fetch',fetch);
  const input=campaignInput({...brief,provider:'offline'},PLANS[plan]);
  const r=await runCampaign(input,{groqKey:'accidentally-supplied',geminiKey:'accidentally-supplied',key_source:'operator'});
  expect(fetch).not.toHaveBeenCalled();expect(r.provider).toBe('offline');expect(r.visual_status).toMatchObject({state:'not_requested',reason:'NO_AI_MODE'});
 });
 it('a paid plan does not opt in automatically and a free plan cannot opt in',()=>{
  enable();expect(resolveVisualPlan(campaignInput({product_name:'Coffee'},PLANS.pro)).state).toBe('not_requested');
  expect(resolveVisualPlan(campaignInput(brief,PLANS.free)).state).toBe('not_entitled');
 });
 it('requires boolean consent and supported provider values',()=>{
  expect(()=>campaignInput({...brief,visuals_ai:'true'},PLANS.pro)).toThrow();
  expect(()=>campaignInput({...brief,visual_provider:'unapproved'},PLANS.pro)).toThrow();
 });
 it('fails closed when consent is absent or the provider changed',()=>{
  enable();for(const provider of ['', 'gemini'])expect(()=>resolveVisualPlan(campaignInput({...brief,visual_provider:provider},PLANS.pro))).toThrow(expect.objectContaining({code:'VISUAL_CONSENT_REQUIRED'}));
 });
 it('the image kill switch defaults off even with an operator key',()=>{
  enable();vi.stubEnv('AI_VISUALS_ENABLED','');expect(visualConfig().enabled).toBe(false);
  expect(resolveVisualPlan(campaignInput(brief,PLANS.pro))).toMatchObject({enabled:false,state:'not_configured'});
 });
 it('public configuration discloses fields but no provider credential',()=>{
  enable();const cfg=visualConfig();expect(cfg).toMatchObject({enabled:true,provider:'openai',model:'gpt-image-1'});
  expect(JSON.stringify(cfg)).not.toContain('fake-private-key');expect(cfg.fields).toContain('audience');
 });
 it('unknown provider configuration never silently falls back to Gemini',()=>{
  enable();vi.stubEnv('AI_VISUALS_PROVIDER','typo');expect(visualConfig()).toMatchObject({enabled:false,provider:null});
 });
});

describe('combined operator budget',()=>{
 it.each(['personal','offline'])('reserves image spend when text is %s funded',async(key_source)=>{
  enable();const rpc=vi.fn(async()=>({data:true}));const plan=resolveVisualPlan(campaignInput(brief,PLANS.pro));
  await reserveOperatorBudget({rpc},'id',{key_source},plan);
  expect(rpc).toHaveBeenCalledExactlyOnceWith('reserve_operator_cost',{p_id:'id',p_upper:.2,p_daily:10});
 });
 it('uses one atomic reservation for text plus image',async()=>{
  enable();vi.stubEnv('GROQ_INPUT_USD_PER_MTOK','1');vi.stubEnv('GROQ_OUTPUT_USD_PER_MTOK','2');
  const rpc=vi.fn(async()=>({data:true}));await reserveOperatorBudget({rpc},'id',{key_source:'operator',groqKey:'fake'},resolveVisualPlan(campaignInput(brief,PLANS.pro)));
  expect(rpc).toHaveBeenCalledExactlyOnceWith('reserve_operator_cost',{p_id:'id',p_upper:.32,p_daily:10});
 });
 it.each(['','0','-1','NaN','Infinity'])('rejects invalid image upper bound %s before RPC',async(value)=>{
  enable();vi.stubEnv('AI_VISUALS_OPENAI_MAX_USD_PER_IMAGE',value);const rpc=vi.fn();
  await expect(reserveOperatorBudget({rpc},'id',{key_source:'personal'},resolveVisualPlan(campaignInput(brief,PLANS.pro)))).rejects.toMatchObject({code:'COST_GUARD_UNCONFIGURED'});expect(rpc).not.toHaveBeenCalled();
 });
 it('requires a new pricing approval after a model change',async()=>{
  enable();vi.stubEnv('AI_VISUALS_OPENAI_COST_MODEL','different-model');
  await expect(reserveOperatorBudget({rpc:vi.fn()},'id',{key_source:'personal'},resolveVisualPlan(campaignInput(brief,PLANS.pro)))).rejects.toMatchObject({code:'COST_GUARD_UNCONFIGURED'});
 });
 it('honors database budget denial and does not call a provider',async()=>{
  enable();const fetch=vi.fn();vi.stubGlobal('fetch',fetch);
  await expect(reserveOperatorBudget({rpc:async()=>({data:false})},'id',{key_source:'personal'},resolveVisualPlan(campaignInput(brief,PLANS.pro)))).rejects.toMatchObject({code:'COST_BUDGET_REACHED'});expect(fetch).not.toHaveBeenCalled();
 });
});

describe('provider request and export provenance',()=>{
 it('uses the supported GPT image contract and landscape output',()=>{
  expect(openAIImageBody('sample','gpt-image-1')).toEqual({model:'gpt-image-1',prompt:'sample',size:'1536x1024',quality:'high',n:1,output_format:'png'});
  expect(()=>openAIImageBody('sample','dall-e-3')).toThrow();
 });
 it('keeps the resolved provider/model/key stable and exports accurate attribution',async()=>{
  enable();const input=campaignInput(brief,PLANS.pro),plan=resolveVisualPlan(input);let sent;
  vi.stubEnv('AI_VISUALS_PROVIDER','gemini');vi.stubEnv('AI_VISUAL_MODEL','different-model');
  vi.stubGlobal('fetch',vi.fn(async(url,options)=>{sent={url,body:JSON.parse(options.body),headers:options.headers};return {ok:true,json:async()=>({data:[{b64_json:PNG}]})};}));
  const r=await runCampaign(input,{key_source:'offline',visualPlan:plan});
  expect(sent.url).toBe('https://api.openai.com/v1/images/generations');expect(sent.body.model).toBe('gpt-image-1');expect(sent.body).not.toHaveProperty('response_format');
  expect(sent.headers.Authorization).toBe('Bearer fake-private-key');
  expect(r.visual_status).toMatchObject({state:'generated',provider:'openai',model:'gpt-image-1',scope:'hero_only'});
  const guidelines=r.files.find(f=>f.name==='brand_guidelines.md').content;
  expect(guidelines).toContain('provider: openai');expect(guidelines).not.toContain('Google');expect(guidelines).not.toContain('commercial use is allowed');expect(JSON.stringify(r)).not.toContain('fake-private-key');
 });
 it('retains attempted image provider and failure reason after fallback',async()=>{
  enable();vi.stubGlobal('fetch',vi.fn(async()=>({ok:false,status:429})));
  const r=await runCampaign(campaignInput(brief,PLANS.pro));
  expect(r.visual_status).toMatchObject({state:'fallback',provider:'openai',model:'gpt-image-1',reason:'VISUAL_RATE_LIMIT'});
 });
});

describe('actual database persistence and budget ceiling',()=>{
 let sb;
 beforeAll(async()=>{sb=await database();},30000);afterAll(async()=>{await sb?.close();});
 it('persists image status with actual generation RPC and marks historical rows unknown',async()=>{
  const user=await sb.user(),id=randomUUID();
  const old=(await sb.from('campaigns').insert({user_id:user.id,product:'Old',name:'Old'}).select('*').single()).data;
  expect(old.visual_status).toMatchObject({state:'unknown'});
  await sb.rpc('reserve_generation',{p_uid:user.id,p_id:id,p_hash:'a'.repeat(64),p_lifetime_limit:3,p_monthly_limit:null,p_daily_limit:3,p_concurrency:1});
  const visual_status={mode:'svg',state:'fallback',provider:'openai',reason:'VISUAL_RATE_LIMIT'};
  const saved=await sb.rpc('complete_generation',{p_uid:user.id,p_id:id,p_campaign:{product:'Coffee',files:[{name:'hero.svg',content:'<svg/>'}],visual_status}});
  expect(saved.error).toBeNull();const row=(await sb.from('campaigns').select('*').eq('id',saved.data.id).single()).data;
  expect(row.visual_status).toEqual(visual_status);
  const grants=await sb.db.query("select has_function_privilege('authenticated','complete_generation(uuid,uuid,jsonb)','EXECUTE') ok");expect(grants.rows[0].ok).toBe(false);
 });
 it('combined reservations cannot overbook the actual database ceiling',async()=>{
  enable();vi.stubEnv('MAX_PROVIDER_DAILY_USD','.3');
  const plan=resolveVisualPlan(campaignInput(brief,PLANS.pro));
  const attempts=await Promise.allSettled([reserveOperatorBudget(sb,randomUUID(),{key_source:'personal'},plan),reserveOperatorBudget(sb,randomUUID(),{key_source:'personal'},plan)]);
  expect(attempts.filter(x=>x.status==='fulfilled')).toHaveLength(1);
  expect(attempts.find(x=>x.status==='rejected').reason.code).toBe('COST_BUDGET_REACHED');
 });
});
