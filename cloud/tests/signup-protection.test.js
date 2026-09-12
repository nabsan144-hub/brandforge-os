import {it,expect,vi,afterEach} from 'vitest';
import config from '../api/_lib/routes/config.js';
afterEach(()=>vi.unstubAllEnvs());
it('fails closed when CAPTCHA is explicitly required but no public key is configured',async()=>{
 vi.stubEnv('SUPABASE_ANON_KEY','');vi.stubEnv('CAPTCHA_REQUIRED','true');vi.stubEnv('CAPTCHA_SITE_KEY','');
 expect((await config(new Request('https://example.test/api/config'))).status).toBe(503);
 vi.stubEnv('CAPTCHA_SITE_KEY','public-test-key');expect((await config(new Request('https://example.test/api/config'))).status).toBe(200);
});
