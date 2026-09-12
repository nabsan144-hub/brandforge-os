// Entire published page set: canonical URLs, metadata, IDs, local links/assets.
const fs=require('fs'),path=require('path'),assert=require('node:assert/strict');
const {JSDOM}=require('jsdom');
const root=path.join(__dirname,'..'),pages=fs.readdirSync(root).filter(n=>n.endsWith('.html'));
const docs=new Map(pages.map(p=>[p,new JSDOM(fs.readFileSync(path.join(root,p),'utf8')).window.document]));
const problems=[];
for(const [name,d]of docs){
 const check=(ok,why)=>{if(!ok)problems.push(name+': '+why);};
 check(d.documentElement.lang==='en','missing language');check(d.title.length>5,'missing title');check(d.querySelector('meta[name="description"]')?.content.length>20,'missing description');
 check(d.querySelectorAll('h1').length===1,'expected one h1');
 const ids=[...d.querySelectorAll('[id]')].map(e=>e.id);check(new Set(ids).size===ids.length,'duplicate IDs');
 if(name!=='404.html'){
  const canonical=d.querySelector('link[rel="canonical"]')?.href;check(canonical==='https://www.brandforge-os.com/'+(name==='index.html'?'':name.slice(0,-5)),'noncanonical URL');
 }
 for(const el of d.querySelectorAll('[src],a[href],link[href],video[poster]')){
  const raw=el.getAttribute('src')||el.getAttribute('href')||el.getAttribute('poster');
  if(!raw||/^(https?:|mailto:|tel:|data:|blob:)/.test(raw))continue;
  const u=new URL(raw,'https://local.test/'+(name==='index.html'?'':name.slice(0,-5)));
  let target=decodeURIComponent(u.pathname).replace(/^\//,'');
  if(!target)target='index.html';else if(target==='tour')target='assets/product-demo/tour.html';else if(!path.extname(target))target+='.html';
  check(fs.existsSync(path.join(root,target)),'missing local target '+raw);
  if(el.tagName==='A'&&u.hash&&docs.has(target))check(!!docs.get(target).getElementById(decodeURIComponent(u.hash.slice(1))),'missing fragment '+raw);
  if(el.tagName==='A'&&/\.html(?:[?#]|$)/.test(raw)&&!raw.startsWith('assets/'))check(false,'public page link contains .html: '+raw);
 }
 for(const img of d.images)check(img.hasAttribute('alt'),'image lacks alt');
}
assert.deepEqual(problems,[]);console.log(`Site integrity: ${pages.length} pages; canonical URLs, metadata, IDs, links/assets passed.`);
