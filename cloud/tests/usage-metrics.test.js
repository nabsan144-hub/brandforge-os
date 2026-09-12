import {it,expect,vi,beforeAll,afterAll,beforeEach,afterEach} from 'vitest';
import {randomUUID} from 'node:crypto';
import {JSDOM} from 'jsdom';
vi.mock('../api/_lib/sb.js',()=>({admin:vi.fn(),json:(b,s=200)=>new Response(JSON.stringify(b),{status:s})}));
vi.mock('../api/_lib/limit.js',()=>({rateLimit:vi.fn(async()=>true)}));
import {admin} from '../api/_lib/sb.js';
import handler from '../api/_lib/routes/usage-metrics.js';
import {createUsageMetrics} from '../public/usage-metrics.js';
import {database,request} from './helpers/db.js';
let sb;beforeAll(async()=>{sb=await database();admin.mockReturnValue(sb);},30000);afterAll(()=>sb.close());
beforeEach(()=>{vi.stubEnv('USAGE_METRICS_ENABLED','true');vi.stubEnv('USAGE_METRICS_SECRET','m'.repeat(40));vi.stubEnv('BRANDFORGE_APP_URL','https://app.example.test');});afterEach(()=>{vi.unstubAllEnvs();vi.unstubAllGlobals();});
const post=b=>handler(request('/usage-metrics','POST',b,{Origin:'https://app.example.test'}));
const body=()=>({id:randomUUID(),session:randomUUID(),consent:true,event:'visit',surface:'cloud'});
it('requires explicit consent, approved origin and a strict no-content event schema',async()=>{expect((await post({...body(),consent:false})).status).toBe(400);expect((await post({...body(),copy:'private draft'})).status).toBe(400);expect((await handler(request('/usage-metrics','POST',body(),{Origin:'https://evil.test'}))).status).toBe(403);vi.stubEnv('USAGE_METRICS_ENABLED','false');expect((await post(body())).status).toBe(503);});
it('deduplicates event retries and per-day event types without storing raw browser identifiers',async()=>{const b=body();expect((await post(b)).status).toBe(200);expect((await post(b)).status).toBe(200);expect((await post({...b,id:randomUUID()})).status).toBe(200);const rows=(await sb.db.query('select * from usage_events')).rows;expect(rows).toHaveLength(1);expect(JSON.stringify(rows)).not.toContain(b.session);expect(rows[0].actor_hash).toMatch(/^[a-f0-9]{64}$/);const sum=(await sb.rpc('usage_event_summary')).data;expect(sum.client_reported).toBe(true);expect(sum.event_counts[0].count).toBe(1);});
it('garbage collection removes expired events',async()=>{await sb.db.query("update usage_events set created_at=now()-interval '31 days'");expect((await sb.rpc('gc_usage_events')).data).toBe(1);});
it('browser sends nothing before consent or after revocation, and includes no text fields',async()=>{
 const dom=new JSDOM('<div id="host"></div>',{url:'https://app.example.test'});vi.stubGlobal('document',dom.window.document);vi.stubGlobal('localStorage',dom.window.localStorage);vi.stubGlobal('fetch',vi.fn(async()=>({ok:true})));
 const metric=createUsageMetrics({enabled:true,endpoint:'/api/usage-metrics',surface:'cloud',host:document.getElementById('host')});await metric.event('campaign_saved');expect(fetch).not.toHaveBeenCalled();expect(localStorage.length).toBe(0);
 const box=document.querySelector('input');box.checked=true;box.dispatchEvent(new dom.window.Event('change'));await vi.waitFor(()=>expect(fetch).toHaveBeenCalledTimes(1));await metric.event('campaign_saved');expect(fetch).toHaveBeenCalledTimes(2);const b=JSON.parse(fetch.mock.calls[1][1].body);expect(Object.keys(b).sort()).toEqual(['consent','event','id','session','surface']);box.checked=false;box.dispatchEvent(new dom.window.Event('change'));await metric.event('pack_exported');expect(fetch).toHaveBeenCalledTimes(2);expect(localStorage.length).toBe(0);dom.window.close();
});
it('revocation aborts pending traffic and a stale failure cannot rewrite a new consent session',async()=>{
 const dom=new JSDOM('<div id="host"></div>',{url:'https://app.example.test'});vi.stubGlobal('document',dom.window.document);vi.stubGlobal('localStorage',dom.window.localStorage);let finish;
 vi.stubGlobal('fetch',vi.fn().mockImplementationOnce(()=>new Promise(r=>{finish=r;})).mockResolvedValue({ok:true}));
 createUsageMetrics({enabled:true,endpoint:'/api/usage-metrics',surface:'cloud',host:document.getElementById('host')});const box=document.querySelector('input');
 box.checked=true;box.dispatchEvent(new dom.window.Event('change'));const signal=fetch.mock.calls[0][1].signal;
 box.checked=false;box.dispatchEvent(new dom.window.Event('change'));expect(signal.aborted).toBe(true);expect(localStorage.length).toBe(0);
 box.checked=true;box.dispatchEvent(new dom.window.Event('change'));const saved=localStorage.getItem('bf-optional-metrics-v1');finish({ok:false});await new Promise(r=>setTimeout(r,0));expect(localStorage.getItem('bf-optional-metrics-v1')).toBe(saved);dom.window.close();
});
