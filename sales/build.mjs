// Publish only customer-facing static files, never tests or operator metadata.
import {readdirSync,statSync,cpSync,rmSync,mkdirSync,readFileSync,writeFileSync} from 'node:fs';
import {join,dirname} from 'node:path';
import {fileURLToPath} from 'node:url';
const root=dirname(fileURLToPath(import.meta.url)),out=join(root,'public');
const rootFiles=new Set(['robots.txt','sitemap.xml','favicon.ico','apple-touch-icon.png','og-image.jpg','_headers','_redirects']);
const privateAssets=new Set(['product-demo/ASSET-NOTICE.md','product-demo/MUSIC-NOTE.txt','product-demo/manifest.json']);
rmSync(out,{recursive:true,force:true});mkdirSync(out,{recursive:true});
for(const name of readdirSync(root)){
 if(name.endsWith('.html')||rootFiles.has(name))cpSync(join(root,name),join(out,name));
}
function assets(relative=''){
 for(const name of readdirSync(join(root,'assets',relative))){
  const rel=join(relative,name),from=join(root,'assets',rel);
  if(privateAssets.has(rel.replaceAll('\\','/'))||name.startsWith('.'))continue;
  if(statSync(from).isDirectory())assets(rel);
  else{const to=join(out,'assets',rel);mkdirSync(dirname(to),{recursive:true});cpSync(from,to);}
 }
}
assets();console.log('Static publication assembled in sales/public (no tests, package files or operator-only media notes).');

// Tour availability is not left to rewrite engines alone. The animated tour
// (assets/product-demo/tour.html, fully self-contained: inline CSS, base64
// fonts/audio, no external refs) is mirrored at the publish root, so clean/pretty
// URLs serve /tour straight from the filesystem on any host (Vercel, Netlify,
// Cloudflare Pages, plain static). The /tour rewrites below are then only a
// fallback, and legacy deep links to the asset path keep working file-directly.
const tourSource=join(root,'assets','product-demo','tour.html');
cpSync(tourSource,join(out,'tour.html'));
console.log('Animated tour mirrored to the publish root as /tour.html (served at /tour).');

// Activation is deployment configuration, not a source-code edit. Both explicit
// operator flags are needed; the backend independently authorizes every payment.
const enabled=process.env.DESKTOP_CHECKOUT_ENABLED==='true'&&process.env.BILLING_RELEASE_VERIFIED==='true';
const config=join(out,'assets/config.js');
writeFileSync(config,readFileSync(config,'utf8').replace(/desktop_checkout_enabled\s*:\s*(true|false)/,'desktop_checkout_enabled: '+enabled));

// Public origins are deployment configuration, never credentials. Override all
// published first-party absolute links/SEO metadata so staging stays isolated.
const publicOrigins=[['BRANDFORGE_APP_URL','https://app.brandforge-os.com'],['BRANDFORGE_MARKETING_URL','https://www.brandforge-os.com']];
for(const [key,oldOrigin]of publicOrigins){
 const raw=process.env[key];if(!raw)continue;
 let url;try{url=new URL(raw);}catch{throw Error(key+' must be an HTTPS origin');}
 if(url.protocol!=='https:'||url.username||url.password||url.search||url.hash||url.pathname!=='/')throw Error(key+' must be an HTTPS origin without credentials, query or path');
 const replacement=url.origin;
 function rewrite(directory){for(const name of readdirSync(directory)){
  const file=join(directory,name);if(statSync(file).isDirectory())rewrite(file);
  else if(/\.(?:html|js|json|xml|txt)$/.test(name))writeFileSync(file,readFileSync(file,'utf8').replaceAll(oldOrigin,replacement));
 }}
 rewrite(out);
}
// Vercel previews are never search-indexing targets. Production canonical URLs
// must only be set to the approved production marketing origin.
if(process.env.VERCEL_ENV==='preview')writeFileSync(join(out,'robots.txt'),'User-agent: *\nDisallow: /\n');
