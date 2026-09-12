import {describe,it,expect,vi,afterEach} from 'vitest';
import {EventEmitter} from 'node:events';
import {PNG} from 'pngjs';
import {safeLogo,readJson,safeUrl} from '../api/_lib/http.js';
import {toWebRequest,writeResponse} from '../api/_lib/serve.js';
import {encryptKey,resolveCampaignKeys} from '../api/_lib/keys.js';
import {bannerSvg,logoSvg,validateVisualText} from '../api/_lib/visuals.js';
import {publicPlans} from '../api/_lib/plans.js';
import {AD_SIZES} from '../api/_lib/engine.js';
afterEach(()=>{vi.unstubAllEnvs();vi.unstubAllGlobals();});
describe('input, transport, provider preference and measured graphics regressions',()=>{
 it('requires a fully decodable bounded PNG, not only a forged PNG header',()=>{
  const png=PNG.sync.write({width:2,height:2,data:Buffer.alloc(16,255)}),uri='data:image/png;base64,'+png.toString('base64');expect(safeLogo(uri)).toBe(uri);
  const truncated=png.subarray(0,33);expect(()=>safeLogo('data:image/png;base64,'+truncated.toString('base64'))).toThrow();
  expect(()=>safeLogo('data:image/svg+xml,<svg/>')).toThrow();expect(()=>safeUrl('javascript:alert(1)')).toThrow();expect(()=>safeUrl('https://user:password@example.test')).toThrow();
 });
 it('only accepts HTTPS destinations and validates every user-visible visual field cleanly',()=>{
  // Ad/landing destinations: plain http and mixed schemes are refused; https survives.
  expect(()=>safeUrl('http://example.test')).toThrow();expect(safeUrl('https://example.test/a?b=1')).toBe('https://example.test/a?b=1');expect(safeUrl('')).toBe('');
  // audience and offer are rendered text too: unsupported scripts must produce a
  // clean 400-class error (not a downstream 503), while marketed scripts pass.
  const unsupported={product:'Apex',benefits:['fresh'],cta:'Learn more',audience:'受众群体',offer:''};
  try{validateVisualText(unsupported);throw new Error('expected rejection');}catch(e){expect(e.status).toBe(400);expect(e.code).toBe('UNSUPPORTED_VISUAL_SCRIPT');}
  try{validateVisualText({product:'Apex',benefits:['fresh'],cta:'Learn more',audience:'Shoppers',offer:'구독자 할인'});throw new Error('expected rejection');}catch(e){expect(e.status).toBe(400);expect(e.code).toBe('UNSUPPORTED_VISUAL_SCRIPT');}
  expect(()=>validateVisualText({product:'Apex Coffee',benefits:['Organic beans'],cta:'Order now',audience:'ایپکس کافی',offer:'अपेक्स कॉफ़ी'})).not.toThrow();
 });
 it('limits streamed request bodies before collecting all bytes',async()=>{
  let canceled=false;const stream=new ReadableStream({start(c){c.enqueue(new Uint8Array(100));c.enqueue(new Uint8Array(100));},cancel(){canceled=true;}});
  const req=new Request('https://example.test',{method:'POST',body:stream,duplex:'half'});
  await expect(readJson(req,120)).rejects.toMatchObject({status:413});expect(canceled).toBe(true);
 });
 it('preserves multibyte raw webhook text and binary responses in the legacy adapter',async()=>{
  const incoming=new EventEmitter();incoming.method='POST';incoming.url='/api/paddle-webhook';incoming.headers={'content-type':'application/json'};
  const text='{"name":"ایپکس"}',data=Buffer.from(text);const reading=toWebRequest(incoming);incoming.emit('data',data.subarray(0,11));incoming.emit('data',data.subarray(11));incoming.emit('end');expect(await(await reading).text()).toBe(text);
  let body;await writeResponse(new Response(Uint8Array.from([0,255,128,1])),{setHeader(){},end(b){body=b;}});expect([...body]).toEqual([0,255,128,1]);
 });
 it('prefers personal Gemini over operator Groq and never switches on key-store failure',async()=>{
  vi.stubEnv('BYOK_ENABLED','1');vi.stubEnv('BRANDFORGE_ENCRYPTION_KEY','a'.repeat(64));vi.stubEnv('GROQ_API_KEY','operator-groq');
  const key=encryptKey('personal-gemini'),sb={from:()=>({select:()=>({eq:async()=>({data:[{provider:'gemini',encrypted_key:key}]})})})};
  expect(await resolveCampaignKeys(sb,'user','auto')).toMatchObject({geminiKey:'personal-gemini',groqKey:'',key_source:'personal'});
  const broken={from:()=>({select:()=>({eq:async()=>({error:{message:'outage'}})})})};await expect(resolveCampaignKeys(broken,'user','auto')).rejects.toThrow();
  expect(await resolveCampaignKeys(broken,'user','offline')).toMatchObject({key_source:'offline'});
 });
 it('does not ignore a corrupt or disabled saved personal key',async()=>{
  vi.stubEnv('BYOK_ENABLED','1');vi.stubEnv('BRANDFORGE_ENCRYPTION_KEY','a'.repeat(64));vi.stubEnv('GROQ_API_KEY','operator');
  const sb={from:()=>({select:()=>({eq:async()=>({data:[{provider:'groq',encrypted_key:'broken'}]})})})};await expect(resolveCampaignKeys(sb,'user','auto')).rejects.toThrow();vi.stubEnv('BYOK_ENABLED','0');await expect(resolveCampaignKeys(sb,'user','auto')).rejects.toThrow();
 });
 it.each(['Apex Coffee','A deliberately very long international brand name for a small canvas','ایپکس کافی','अपेक्स कॉफ़ी','Café Português'])('fits measured text across every preset for %s',brand=>{
  for(const [width,height] of [...Object.values(AD_SIZES).map(x=>x.slice(0,2)),[50,50],[5000,50],[50,5000]]){
   const svg=bannerSvg({product:brand,benefits:['An approved benefit'],width,height});
   for(const match of svg.matchAll(/data-box="([^"]+)"/g)){
    const [x,y,w,h]=match[1].split(',').map(Number);expect(x).toBeGreaterThanOrEqual(-.01);expect(y).toBeGreaterThanOrEqual(-.01);expect(x+w).toBeLessThanOrEqual(width+.01);expect(y+h).toBeLessThanOrEqual(height+.01);
   }
  }
  const paths=['wordmark','lettermark','combination','abstract','pictorial','emblem'].map(style=>[...logoSvg({brand,style}).matchAll(/<(?:path|circle|rect)\b[^>]*>/g)].map(m=>m[0]).join(''));
  expect(new Set(paths).size).toBe(6);
 });
 it('describes the Free plan as hero + 1 preset (engine always emits the hero banner)',()=>{
  const free=publicPlans().find(p=>p.id==='free');expect(free.features.join(' | ')).toContain('Hero + 1 preset per run');expect(free.features.join(' | ')).not.toContain('1 banner preset per run');
 });
});
