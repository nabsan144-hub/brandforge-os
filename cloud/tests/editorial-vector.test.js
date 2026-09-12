import {it,expect,vi,afterEach} from 'vitest';
import {PNG} from 'pngjs';
import {bannerSvg} from '../api/_lib/visuals.js';
import {runCampaign,AD_SIZES,PLANS} from '../api/_lib/engine.js';
import {campaignInput} from '../api/_lib/routes/campaigns.js';
import {redrawVectors,correctionFields} from '../api/_lib/vector-corrections.js';
import {vectorQuality,qualityIssues} from '../public/vector-quality.js';
import {readFileSync} from 'node:fs';import {createHash} from 'node:crypto';
const hash=s=>createHash('sha256').update(s).digest('hex');
const brief={product:'Northline Coffee',headline:'A better morning, brewed.',subheadline:'Coffee roasted in small batches',benefits:['Whole beans or ground','Choose your roast'],offer:'250 g · Rs 1,450',cta:'Explore the roasts',primary:'#BB4A2B',secondary:'#F8F1E5',style:'editorial-v1',explicitVisualFields:true};
const render=(extra={})=>bannerSvg({...brief,...extra});
const report=svg=>vectorQuality([{name:'hero_banner.svg',content:svg}])[0];
afterEach(()=>vi.unstubAllGlobals());
it('preserves all 20 pre-change legacy golden outputs byte-for-byte',()=>{
 const fixture=JSON.parse(readFileSync(new URL('./fixtures/legacy-vector-hashes.json',import.meta.url)));
 for(const c of fixture.cases)expect(hash(bannerSvg(c.options))).toBe(c.sha256);
});
it('exposes editorial only as an explicit accepted style and leaves default bold',()=>{
 expect(campaignInput({product_name:'Coffee',style:'editorial-v1'},PLANS.free).style).toBe('editorial-v1');
 expect(campaignInput({product_name:'Coffee'},PLANS.free).style).toBe('bold');
 expect(()=>campaignInput({product_name:'Coffee',style:'editorial-v2'},PLANS.free)).toThrow(/style/);
});
it.each(Object.entries(AD_SIZES))('bounds outlined geometry for preset %s',(_,dims)=>{
 for(const watermark of [true,false]){
  const [width,height]=dims,svg=render({width,height,watermark});
  expect(svg.includes('data-renderer="editorial-v1"')).toBe(true);
  for(const m of svg.matchAll(/data-box="([^"]+)"/g)){
   const [x,y,w,h]=m[1].split(',').map(Number);expect(x).toBeGreaterThanOrEqual(-.01);expect(y).toBeGreaterThanOrEqual(-.01);expect(x+w).toBeLessThanOrEqual(width+.01);expect(y+h).toBeLessThanOrEqual(height+.01);
  }
  expect(svg.includes('data-watermark="brandforge"')).toBe(watermark);
 }
});
it('uses plain actions and no decorative benefit icons, glows or glass',()=>{
 const svg=render();for(const bad of ['<ellipse','<filter','<radialGradient','<linearGradient','data-icon'])expect(svg.includes(bad)).toBe(false);
 expect(report(svg).fields.every(f=>['included','empty'].includes(f.status))).toBe(true);
});
it('keeps requested offer spelling and does not upper-case it',()=>{
 const svg=render({offer:'From Rs 250 — terms apply'});expect(svg.includes('data-text="From Rs 250 — terms apply"')).toBe(true);
});
it('rejects unfit offer text wholly rather than printing a partial price or ellipsis',()=>{
 const offer='Rs 1,450 only for eligible orders with exclusions and delivery fees '.repeat(5),svg=render({width:300,height:250,offer});
 expect(report(svg).fields.find(f=>f.field==='offer').status).toBe('omitted_unfit');
 expect(svg.includes('data-text="'+offer)).toBe(false);expect(svg.includes('aria-label="Rs 1,450')).toBe(false);
 expect(qualityIssues([report(svg)]).some(s=>s.includes('offer does not fit'))).toBe(true);
});
it('reports intentional strip omissions and micro logo substitution separately',()=>{
 const strip=report(render({width:320,height:50}));expect(strip.fields.find(f=>f.field==='offer').status).toBe('omitted_format');
 expect(strip.fields.find(f=>f.field==='headline').status).toBe('omitted_format');
 const logo='data:image/png;base64,'+PNG.sync.write(new PNG({width:2,height:2})).toString('base64');
 const micro=render({width:50,height:50,logo});expect(report(micro).fields.find(f=>f.field==='brand').status).toBe('logo');expect(micro.includes(logo)).toBe(true);
});
it('does not repeat a benefit already printed as headline or subheadline',()=>{
 const svg=render({headline:'Whole beans or ground',subheadline:'Choose your roast'}),r=report(svg);
 expect(r.fields.filter(f=>f.status==='repeated_in_heading')).toHaveLength(2);
 expect(Array.from(svg.matchAll(/aria-label="([^"]+)" data-text="Whole beans or ground"/g),m=>m[1]).join(' ')).toBe('Whole beans or ground');
 const micro=report(render({width:50,height:50,headline:'Whole beans or ground'}));expect(micro.fields.some(f=>f.status==='repeated_in_heading')).toBe(false);
});
it.each(['آپ کی صبح، آپ کی چائے','आपकी रोज़ की देखभाल'])('outlines supported script without foreign fonts: %s',headline=>{
 const svg=render({headline});expect(report(svg).fields.find(f=>f.field==='headline').status).toBe('included');expect(svg.includes('<text')).toBe(false);expect(svg.includes('<path')).toBe(true);
});
it('keeps minimum included type sizes at declared preview widths',()=>{
 for(const [width,height]of [[1200,630],[1080,1080],[1080,1920],[300,250]]){
  const scale=Math.min(1,(width/height>=1.65?600:360)/width);
  for(const f of report(render({width,height})).fields.filter(f=>f.status==='included'))expect(f.font_size).toBeGreaterThanOrEqual((f.field==='headline'?18:12)/scale-.01);
 }
});
it('engine saves the versioned recipe and corrections preserve it without providers or logo changes',async()=>{
 const fetch=vi.fn(()=>{throw new Error('No network expected')});vi.stubGlobal('fetch',fetch);
 const r=await runCampaign({...brief,benefits:brief.benefits.join(';'),provider:'offline',watermark:true,custom_presets:1,custom_sizes:[{preset:'mobile_banner'}]});
 expect(r.visual_recipe.common.style).toBe('editorial-v1');
 const fields=correctionFields({headline:'New morning roast',subheadline:'',offer:'Rs 250 today',cta:'Order today',destination:''});
 const changed=redrawVectors(r,fields);expect(changed.recipe).toEqual(r.visual_recipe);expect(fetch).not.toHaveBeenCalled();
 for(const f of r.files.filter(f=>!f.name.startsWith('banner_')&&f.name!=='hero_banner.svg'))expect(changed.files.find(x=>x.name===f.name)).toEqual(f);
 expect(changed.report[1].fields.offer).toBe('omitted');
 expect(changed.files[0].content.includes('data-renderer="editorial-v1"')).toBe(true);expect(changed.files[0].content.includes('data-watermark="brandforge"')).toBe(true);
});
it('does not change the AI scene renderer and ignores old files in quality diagnostics',()=>{
 const scene='data:image/png;base64,AAAA',options={...brief,scene};
 expect(hash(bannerSvg(options))).toBe(hash(bannerSvg({...options,style:'essential'})));
 expect(vectorQuality([{name:'x.svg',content:bannerSvg({...brief,style:'bold'})}])).toEqual([]);
});
it('escapes hostile text and emits plain diagnostic values only',()=>{
 const svg=render({headline:'<script>alert(1)</script>'});expect(svg.includes('<script>')).toBe(false);
 expect(report(svg).fields.every(f=>/^[a-z0-9_]+$/.test(f.field))).toBe(true);
});

it('reports unsupported decorative characters instead of silently dropping a glyph',()=>{
 const r=report(render({offer:'Rs 250 🦄 today'}));expect(r.fields.find(f=>f.field==='offer').status).toBe('omitted_unsupported');expect(qualityIssues([r]).some(x=>x.includes('unavailable in the bundled fonts'))).toBe(true);
});
it('reports benefits beyond the three-item layout limit',()=>{
 const r=report(render({benefits:['One','Two','Three','Four']}));expect(r.fields.find(f=>f.field==='benefit_4').status).toBe('omitted_format');
});

it('allocates enough action height for an ordinary two-line 300px CTA',()=>{expect(report(render({width:300,height:250,watermark:true})).fields.find(f=>f.field==='cta').status).toBe('included');});
