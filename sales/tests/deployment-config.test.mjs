import assert from 'node:assert/strict';
import {mkdtempSync,mkdirSync,copyFileSync,writeFileSync,readFileSync,rmSync} from 'node:fs';
import {tmpdir} from 'node:os';
import {join} from 'node:path';
import {spawnSync} from 'node:child_process';
const tmp=mkdtempSync(join(tmpdir(),'bf-site-build-'));
try{
 mkdirSync(join(tmp,'assets/product-demo'),{recursive:true});
 copyFileSync(new URL('../build.mjs',import.meta.url),join(tmp,'build.mjs'));
 writeFileSync(join(tmp,'index.html'),'<a href="https://app.brandforge-os.com/signup">Try</a><link rel="canonical" href="https://www.brandforge-os.com/">');
 writeFileSync(join(tmp,'assets/config.js'),"desktop_checkout_enabled: false; hosted_url: 'https://app.brandforge-os.com'");
 writeFileSync(join(tmp,'assets/product-demo/tour.html'),'<p>Tour</p>');
 const env={...process.env,BRANDFORGE_APP_URL:'https://app-staging.example.test',BRANDFORGE_MARKETING_URL:'https://sales-staging.example.test',VERCEL_ENV:'preview',DESKTOP_CHECKOUT_ENABLED:'false',BILLING_RELEASE_VERIFIED:'false'};
 assert.equal(spawnSync(process.execPath,['build.mjs'],{cwd:tmp,env}).status,0);
 const html=readFileSync(join(tmp,'public/index.html'),'utf8');assert.ok(html.includes('https://app-staging.example.test/signup'));assert.ok(html.includes('https://sales-staging.example.test/'));assert.ok(!html.includes('brandforge-os.com'));
 assert.match(readFileSync(join(tmp,'public/robots.txt'),'utf8'),/Disallow: \//);
 for(const bad of ['javascript:alert(1)','https://user:password@example.test','https://example.test/path','https://example.test/?key=secret'])assert.notEqual(spawnSync(process.execPath,['build.mjs'],{cwd:tmp,env:{...env,BRANDFORGE_APP_URL:bad}}).status,0);
 console.log('Deployment origins: isolated links, preview robots and invalid URL rejection passed.');
}finally{rmSync(tmp,{recursive:true,force:true});}
