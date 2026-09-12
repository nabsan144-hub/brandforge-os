import {it,expect,beforeEach,afterEach,vi} from 'vitest';
import capabilities from '../api/_lib/routes/capabilities.js';
import token from '../api/_lib/routes/bill-client-token.js';
import checkout from '../api/_lib/routes/desk-checkout.js';
import dispatcher from '../api/index.js';
import {configure} from './helpers/paddle.js';
import {request} from './helpers/db.js';
beforeEach(()=>{configure();vi.stubEnv('BRANDFORGE_MARKETING_URL','https://www.example.test');});
afterEach(()=>{vi.unstubAllEnvs();vi.unstubAllGlobals();});
const get=async()=>{const r=await capabilities(request('/capabilities'));expect(r.status).toBe(200);return r.json();};
it('expected closed checkout returns 200, bounded public fields and no-store',async()=>{
 vi.stubEnv('CLOUD_CHECKOUT_ENABLED','false');vi.stubEnv('DESKTOP_CHECKOUT_ENABLED','false');
 const r=await dispatcher(request('/capabilities'));expect(r.status).toBe(200);expect(r.headers.get('cache-control')).toBe('no-store');
 const data=await r.json();expect(data).toMatchObject({free:{lifetime_campaigns:3,card_required:false},cloud:{checkout_enabled:false},desktop:{checkout_enabled:false}});
 expect(JSON.stringify(data)).not.toMatch(/secret|token|pri_|bucket|missing|key/i);expect(JSON.stringify(data).length).toBeLessThan(1000);
 expect((await token(request('/billing/paddle-client-token'))).status).toBe(503);
 expect((await checkout(request('/desktop/checkout','POST',{tier:'owner'}))).status).toBe(503);
});
it('sandbox testing never advertises public paid checkout',async()=>{const d=await get();expect(d.cloud.checkout_enabled).toBe(false);expect(d.desktop.checkout_enabled).toBe(false);});
it.each([['true','false',true,false],['false','true',false,true],['true','true',true,true]])('keeps cloud=%s and desktop=%s independent',async(c,d,ec,ed)=>{
 vi.stubEnv('PADDLE_ENV','production');vi.stubEnv('PADDLE_CLIENT_TOKEN','live_fixture');vi.stubEnv('CLOUD_CHECKOUT_ENABLED',c);vi.stubEnv('DESKTOP_CHECKOUT_ENABLED',d);
 const value=await get();expect(value.cloud.checkout_enabled).toBe(ec);expect(value.desktop.checkout_enabled).toBe(ed);
});
it('incomplete release config and public price IDs never authorize checkout',async()=>{
 vi.stubEnv('PADDLE_ENV','production');vi.stubEnv('PADDLE_CLIENT_TOKEN','live_fixture');vi.stubEnv('BILLING_RELEASE_VERIFIED','false');expect((await get()).desktop.checkout_enabled).toBe(false);
 vi.stubEnv('BILLING_RELEASE_VERIFIED','true');vi.stubEnv('DESKTOP_RELEASE_SHA256_OWNER','');expect((await get()).desktop.checkout_enabled).toBe(false);
});
it('imagery requires the flag, model-bound positive budget and key; its scope stays hero-only',async()=>{
 vi.stubEnv('AI_VISUALS_ENABLED','true');vi.stubEnv('AI_VISUALS_PROVIDER','gemini');vi.stubEnv('AI_VISUALS_KEY','synthetic-private-key');vi.stubEnv('AI_VISUAL_MODEL','fixture-model');
 vi.stubEnv('AI_VISUALS_GEMINI_COST_MODEL','fixture-model');vi.stubEnv('AI_VISUALS_GEMINI_MAX_USD_PER_IMAGE','0.2');
 expect((await get()).imagery).toMatchObject({configured:true,scope:'hero_only',requires_opt_in:true,resized_banners:'vector_only'});
 vi.stubEnv('AI_VISUALS_GEMINI_COST_MODEL','different');expect((await get()).imagery.configured).toBe(false);
 vi.stubEnv('GENERATION_PAUSED','true');expect((await get()).generation_paused).toBe(true);
});
it('CORS only reflects configured origins; preflight works and methods are restricted',async()=>{
 const r=await capabilities(request('/capabilities','GET',undefined,{origin:'https://www.example.test'}));expect(r.headers.get('access-control-allow-origin')).toBe('https://www.example.test');
 const bad=await capabilities(request('/capabilities','GET',undefined,{origin:'https://evil.test'}));expect(bad.headers.has('access-control-allow-origin')).toBe(false);
 expect((await capabilities(request('/capabilities','OPTIONS'))).status).toBe(204);expect((await capabilities(request('/capabilities','POST',{}))).status).toBe(405);
});
