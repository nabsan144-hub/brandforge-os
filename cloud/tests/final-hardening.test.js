import {it,expect,vi,afterEach} from 'vitest';
import {readFileSync} from 'node:fs';
import vm from 'node:vm';
import config from '../api/_lib/routes/config.js';
afterEach(()=>{vi.unstubAllEnvs();vi.unstubAllGlobals();});
it.each(['sk-secret-provider-value','x.not-json.signature','sb_secret_value'])('does not reflect an unrecognized public credential: %s',async secret=>{
 vi.stubEnv('SUPABASE_ANON_KEY',secret);const r=await config(new Request('https://example.test/api/config'));expect(r.status).toBe(503);expect(await r.text()).not.toContain(secret);
});
it.each(['sb_publishable_fixture','x.'+Buffer.from(JSON.stringify({role:'anon'})).toString('base64url')+'.signature'])('accepts recognized publishable credentials: %s',async key=>{
 vi.stubEnv('SUPABASE_ANON_KEY',key);const r=await config(new Request('https://example.test/api/config'));expect(r.status).toBe(200);expect((await r.json()).supabaseAnonKey).toBe(key);
});
function downloadHarness(fetch,hash='#token=private-capability'){
 const status={textContent:''},retry={hidden:true,disabled:false,addEventListener:vi.fn((_,fn)=>{retry.click=fn;})};
 const location={hash,search:'',pathname:'/desktop-download',assign:vi.fn()},history={replaceState:vi.fn()};
 const context={URLSearchParams,URL,AbortSignal,TypeError,fetch,location,history,document:{getElementById:id=>id==='download-status'?status:retry}};
 return {done:vm.runInNewContext(readFileSync(new URL('../public/desktop-download.js',import.meta.url),'utf8'),context),status,retry,location,history};
}
it('retries a failed download with the same in-memory token after clearing its URL',async()=>{
 const fetch=vi.fn().mockResolvedValueOnce({ok:false,json:async()=>({error:'Temporary outage'})}).mockResolvedValueOnce({ok:true,json:async()=>({url:'https://example.test/private.zip'})});
 const h=downloadHarness(fetch);await h.done;expect(h.history.replaceState).toHaveBeenCalledWith(null,'','/desktop-download');expect(h.retry.disabled).toBe(false);
 await h.retry.click();expect(fetch).toHaveBeenCalledTimes(2);for(const c of fetch.mock.calls)expect(JSON.parse(c[1].body).token).toBe('private-capability');expect(h.location.assign).toHaveBeenCalledWith('https://example.test/private.zip');
});
it('does not request a download without a capability',async()=>{const fetch=vi.fn(),h=downloadHarness(fetch,'');await h.done;expect(fetch).not.toHaveBeenCalled();expect(h.retry.hidden).toBe(true);});
it.each(['javascript:alert(1)','https://user:password@example.test/file'])('rejects unsafe signed destinations: %s',async url=>{const h=downloadHarness(vi.fn(async()=>({ok:true,json:async()=>({url})})));await h.done;expect(h.location.assign).not.toHaveBeenCalled();expect(h.retry.disabled).toBe(false);});
