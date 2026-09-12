import {describe,it,expect,vi,afterEach} from 'vitest';
import {imageAdapter,imageProviderKey,imageProviderModel,resolveImageExecution,publicImageAdapters} from '../api/_lib/image-providers.js';
import {generateScene} from '../api/_lib/visuals_ai.js';
afterEach(()=>{vi.unstubAllEnvs();vi.unstubAllGlobals();});
describe('provider-independent image adapter boundary',()=>{
 it.each(['typo','__proto__','constructor','https://example.com/api'])('rejects unregistered provider %s',provider=>{
  expect(()=>imageAdapter(provider)).toThrow(expect.objectContaining({code:'VISUAL_PROVIDER_UNSUPPORTED'}));
 });
 it('never takes a Gemini key/model for an explicitly selected OpenAI request',()=>{
  vi.stubEnv('AI_VISUALS_PROVIDER','gemini');vi.stubEnv('GEMINI_API_KEY','gemini-private-fixture');vi.stubEnv('AI_VISUAL_MODEL','gemini-custom');
  vi.stubEnv('OPENAI_API_KEY','');vi.stubEnv('AI_VISUALS_OPENAI_KEY','');
  expect(imageProviderKey('openai')).toBe('');expect(imageProviderModel('openai')).toBe('gpt-image-2.5-sunburst');
  expect(()=>resolveImageExecution({provider:'openai'})).toThrow(expect.objectContaining({code:'VISUAL_KEY_REQUIRED'}));
 });
 it('explicit empty credentials do not fall back to environment credentials',()=>{
  vi.stubEnv('AI_VISUALS_OPENAI_KEY','private-fixture');
  expect(()=>resolveImageExecution({provider:'openai',key:''})).toThrow(expect.objectContaining({code:'VISUAL_KEY_REQUIRED'}));
 });
 it('preserves explicit execution snapshot after environment changes',()=>{
  const selected=resolveImageExecution({provider:'openai',model:'gpt-image-1',key:'snapshot-fixture'});
  vi.stubEnv('AI_VISUALS_PROVIDER','gemini');vi.stubEnv('AI_VISUAL_MODEL','different');
  expect(resolveImageExecution(selected)).toEqual(selected);expect(Object.isFrozen(selected)).toBe(true);
 });
 it.each(['panorama','unsupported'])('rejects unsupported format %s rather than returning landscape',format=>{
  expect(()=>resolveImageExecution({provider:'openai',key:'fixture',format})).toThrow(expect.objectContaining({code:'VISUAL_CAPABILITY_UNSUPPORTED'}));
 });
 it('does not pretend that reference-image support is implemented',()=>{
  expect(()=>resolveImageExecution({provider:'xai',key:'fixture',referenceImages:['private-reference']})).toThrow(expect.objectContaining({code:'VISUAL_CAPABILITY_UNSUPPORTED'}));
 });
 it('public capabilities contain no key or environment names and cannot mutate registry',()=>{
  const data=publicImageAdapters();expect(data.map(a=>a.id)).toEqual(['gemini','openai','xai']);
  expect(JSON.stringify(data)).not.toMatch(/keyNames|API_KEY/);data[0].formats.push('portrait');
  expect(imageAdapter('gemini').formats).toEqual(['landscape','square','story']);
 });
 it.each(['../models/test','model?key=secret','model/other',''])('rejects unsafe model %s before network',async model=>{
  const fetch=vi.fn();vi.stubGlobal('fetch',fetch);
  await expect(generateScene({product:'Fixture'},{provider:'gemini',key:'fixture',model})).rejects.toMatchObject({code:'VISUAL_MODEL_UNSUPPORTED'});
  expect(fetch).not.toHaveBeenCalled();
 });
});
