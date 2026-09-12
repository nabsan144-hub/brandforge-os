// Synthetic OFFLINE output. No real account, model request, or provider key.
import {bannerSvg,logoSvg,watermarkFooter} from '../cloud/api/_lib/visuals.js';
import {mkdirSync,writeFileSync} from 'node:fs';
const dest=process.argv[2]||'qa-results/watermark';mkdirSync(dest,{recursive:true});
const brief={product:'Northline Coffee',benefits:['Fresh-roasted beans','Clear origin details'],cta:'Explore the coffee',primary:'#E8B54A',secondary:'#0F172A',style:'bold'};
const entries=[];
for(const [name,width,height] of [['hero',1200,630],['story',1080,1920],['strip',320,50],['micro',50,50]]){
 for(const free of [true,false])entries.push({name:`${free?'free':'paid'}-${name}.svg`,content:bannerSvg({...brief,width,height,watermark:free}),free,width,height,footer:free?watermarkFooter(width,height).height:0});
}
entries.push({name:'free-logo.svg',content:logoSvg({brand:'Northline Coffee',watermark:true}),free:true,width:1024,height:1024,footer:watermarkFooter(1024,1024).height});
writeFileSync(dest+'/fixtures.json',JSON.stringify(entries));
const cards=entries.filter(f=>f.name.includes('hero')||f.name.includes('strip')).map(f=>`<article><h2>${f.free?'Free — visible attribution':'Paid — no added attribution'}</h2><p>${f.width} × ${f.height}</p>${f.content}</article>`).join('');
writeFileSync(dest+'/Watermark-Preview.html',`<!doctype html><html lang="en"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>BrandForge watermark preview</title><style>body{margin:0;padding:36px;font:16px system-ui;background:#f4f6f8;color:#172b40}main{max-width:1240px;margin:auto}h1{font-size:32px}p{line-height:1.6;color:#52637a}.grid{display:grid;grid-template-columns:1fr 1fr;gap:24px}article{background:white;border:1px solid #d8dfe6;border-radius:16px;padding:20px}article svg{display:block;max-width:100%;height:auto}h2{font-size:18px}@media(max-width:700px){body{padding:18px}.grid{grid-template-columns:1fr}}</style><main><h1>Made with BrandForge</h1><p>Free-plan watermark implementation preview. Real offline renderer output for a fictional coffee brand. This demonstrates attribution placement, not the later campaign-layout redesign. Paid examples represent newly generated paid-plan assets; upgrading does not automatically rewrite old Free campaigns.</p><div class="grid">${cards}</div><p>The footer is part of the SVG and is carried into PNG/JPEG/ZIP exports. Compact formats use “BrandForge” or “BF”. Uploaded customer logos are not modified. This is visible attribution, not tamper-proof or invisible forensic watermarking.</p></main></html>`);
