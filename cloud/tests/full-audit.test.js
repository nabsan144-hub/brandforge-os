import {it,expect,vi,afterEach,beforeAll,afterAll} from 'vitest';
import {database} from './helpers/db.js';
import {reserveOperatorBudget} from '../api/_lib/cost.js';
import {resolveGroqKey,encryptKey,resolveCampaignKeys} from '../api/_lib/keys.js';
import {deliverDesktopOrder,desktopDownload} from '../api/_lib/fulfillment.js';
import {seal} from '../api/_lib/commerce.js';
import {serve} from '../api/_lib/serve.js';
import {clean} from '../api/_lib/http.js';
let sb;
beforeAll(async()=>{sb=await database();},30000);
afterAll(async()=>{await sb?.close();});
afterEach(()=>{vi.unstubAllEnvs();vi.unstubAllGlobals();});
it('rejects blank operator prices before any cost reservation',async()=>{
 vi.stubEnv('GROQ_INPUT_USD_PER_MTOK','');vi.stubEnv('GROQ_OUTPUT_USD_PER_MTOK','  ');
 const rpc=vi.fn();await expect(reserveOperatorBudget({rpc},'x',{key_source:'operator',groqKey:'test'})).rejects.toMatchObject({code:'COST_GUARD_UNCONFIGURED'});expect(rpc).not.toHaveBeenCalled();
});
it('fails closed in legacy key helpers but ignores unrelated corruption for an explicit provider',async()=>{
 vi.stubEnv('BYOK_ENABLED','1');vi.stubEnv('GROQ_API_KEY','operator-test-only');vi.stubEnv('BRANDFORGE_ENCRYPTION_KEY','a'.repeat(64));
 const db=data=>({from:()=>({select:()=>({eq:async()=>data})})});
 await expect(resolveGroqKey(db({error:{message:'outage'}}),'x')).rejects.toThrow();
 await expect(resolveGroqKey(db({data:[{provider:'groq',encrypted_key:'broken'}]}),'x')).rejects.toThrow();
 expect(await resolveCampaignKeys(db({data:[{provider:'groq',encrypted_key:encryptKey('personal-key')},{provider:'gemini',encrypted_key:'broken'}]}),'x','groq')).toMatchObject({groqKey:'personal-key'});
});
it('returns bounded errors in the Web runtime as well as the legacy adapter',async()=>{
 const r=await serve(async()=>{throw new Error('private operator token must not escape')})(new Request('https://example.test'));
 expect(r.status).toBe(503);expect(await r.text()).not.toContain('operator token');
});
it('preserves ordinary comparisons while removing markup',()=>{
 expect(clean('Revenue < target; size < 10 g')).toBe('Revenue < target; size < 10 g');
 expect(clean('<script>alert(1)</script>')).not.toContain('<script>');
});
it('freezes the paid release checksum and bucket across configuration changes',async()=>{
 vi.stubEnv('DESKTOP_DOWNLOAD_SECRET','d'.repeat(40));vi.stubEnv('BRANDFORGE_APP_URL','https://app.example.test');vi.stubEnv('RESEND_API_KEY','test');vi.stubEnv('DELIVERY_FROM_EMAIL','test@example.test');vi.stubEnv('DESKTOP_RELEASE_SHA256_OWNER','b'.repeat(64));vi.stubEnv('DESKTOP_STORAGE_BUCKET','new-bucket');
 const tid='txn_'+'q'.repeat(26),oldHash='a'.repeat(64);
 expect((await sb.rpc('record_desktop_order',{p_data:{transaction_id:tid,customer_id:'ctm_test',email:'buyer@example.test',tier:'owner',amount_total:19900,currency:'USD',release_path:'v1/owner.zip',release_bucket:'old-bucket',release_sha256:oldHash,occurred_at:new Date().toISOString()}})).error).toBeNull();
 const buckets=[],oldStorage=sb.storage;
 sb.storage={from:bucket=>({createSignedUrl:async()=>{buckets.push(bucket);return {data:{signedUrl:'https://example.test/private'},error:null};}})};
 let sent;vi.stubGlobal('fetch',vi.fn(async(url,opts)=>{sent=JSON.parse(opts.body);return {ok:true};}));
 try {
  expect(await deliverDesktopOrder(sb,tid)).toBe(true);expect(sent.text).toContain(oldHash);expect(sent.text).not.toContain('b'.repeat(64));expect(buckets).toEqual(['old-bucket']);
  const order=(await sb.from('desktop_orders').select('*').eq('transaction_id',tid).single()).data;
  await desktopDownload(sb,seal({purpose:'desktop-download',id:tid,nonce:order.delivery_nonce,exp:Date.now()+60000},'DESKTOP_DOWNLOAD_SECRET'));expect(buckets.at(-1)).toBe('old-bucket');
 } finally {sb.storage=oldStorage;}
});
it('backs off repeated failed claims without blocking unattempted orders',async()=>{
 const ids=['txn_retry_a','txn_retry_b'];
 for(const id of ids) await sb.rpc('record_desktop_order',{p_data:{transaction_id:id,customer_id:'test',email:'buyer@example.test',tier:'owner',amount_total:19900,currency:'USD',release_path:'owner.zip',occurred_at:new Date().toISOString()}});
 expect((await sb.rpc('claim_desktop_delivery',{p_id:ids[0]})).data).toBe(true);
 await sb.from('desktop_orders').update({delivery_claimed_until:null}).eq('transaction_id',ids[0]);
 expect((await sb.rpc('claim_desktop_delivery',{p_id:ids[0]})).data).toBe(false);expect((await sb.rpc('claim_desktop_delivery',{p_id:ids[1]})).data).toBe(true);
 const row=(await sb.from('desktop_orders').select('*').eq('transaction_id',ids[0]).single()).data;
 expect(row.delivery_attempts).toBe(1);expect(Date.parse(row.delivery_next_attempt_at)).toBeGreaterThan(Date.now());
});
it('does not publish a service credential accidentally entered as the anon key',async()=>{
 const {default:config}=await import('../api/_lib/routes/config.js');
 vi.stubEnv('SUPABASE_ANON_KEY','sb_secret_do-not-publish');
 let r=await config(new Request('https://example.test/api/config'));expect(r.status).toBe(503);expect(await r.text()).not.toContain('sb_secret');
 vi.stubEnv('SUPABASE_ANON_KEY','x.'+Buffer.from(JSON.stringify({role:'service_role'})).toString('base64url')+'.signature');
 r=await config(new Request('https://example.test/api/config'));expect(r.status).toBe(503);
});
