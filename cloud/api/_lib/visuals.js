// Measured, outlined SVGs. Fonts are licensed OFL assets bundled with the
// server. Outlining keeps exported Arabic/Hindi shaping intact in any viewer,
// without embedding a large font in every file or depending on local fonts.
import * as fontkit from 'fontkit';
import {fileURLToPath} from 'node:url';
import {safeHex,safeLogo,HttpError} from './http.js';
const FONT_NAMES=['NotoSans','NotoNaskhArabic','NotoSansDevanagari'];
let fonts;
const getFonts=()=>fonts||(fonts=FONT_NAMES.map(n=>fontkit.openSync(fileURLToPath(new URL(`../_assets/fonts/${n}-Regular.ttf`,import.meta.url)))));
const esc=s=>String(s??'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&apos;'}[c]));
const n=x=>Number(x.toFixed(8));
function shape(text){
 const fs=getFonts(),groups=[];
 for(const ch of String(text)){
  let face=/\s/.test(ch)&&groups.length?groups.at(-1).face:fs.findIndex(f=>f.hasGlyphForCodePoint(ch.codePointAt(0)));
  if(face<0){if(/[\p{L}\p{N}]/u.test(ch))throw new Error('This text uses a script not supported by the bundled visual fonts.');continue;} // unsupported decorative emoji are omitted
  if(groups.at(-1)?.face===face)groups.at(-1).text+=ch;else groups.push({face,text:ch});
 }
 const rtl=/^[^A-Za-z\u0900-\u097f]*[\u0600-\u06ff]/.test(text);
 if(rtl)groups.reverse();
 let pen=0,minX=0,maxX=0,minY=0,maxY=0;const glyphs=[];
 for(const group of groups){
  const f=fs[group.face],unit=f.unitsPerEm,run=f.layout(group.text,undefined,undefined,undefined,group.face===1?'rtl':'ltr');
  let cursor=0;
  run.glyphs.forEach((g,i)=>{const p=run.positions[i],x=pen+(cursor+p.xOffset)/unit,y=p.yOffset/unit,b=g.bbox;
   glyphs.push({path:g.path.toSVG(),x,y,unit});
   minX=Math.min(minX,x+b.minX/unit);maxX=Math.max(maxX,x+b.maxX/unit);minY=Math.min(minY,y+b.minY/unit);maxY=Math.max(maxY,y+b.maxY/unit);cursor+=p.xAdvance;
  });pen+=cursor/unit;
 }
 return {glyphs,minX,maxX:Math.max(maxX,pen),minY,maxY,width:Math.max(maxX,pen)-minX,height:maxY-minY||1,rtl};
}
const shapeCache=new Map();
function measured(s){if(shapeCache.has(s))return shapeCache.get(s);const v=shape(s);if(shapeCache.size>500)shapeCache.clear();shapeCache.set(s,v);return v;}
function linesFor(text,size,width,maxLines){
 const words=String(text).trim().split(/\s+/),lines=[];let line='';
 for(const word of words){const trial=line?line+' '+word:word;if(line&&measured(trial).width*size>width){lines.push(line);line=word;}else line=trial;}
 if(line)lines.push(line);
 return lines.length<=maxLines?lines:null;
}
function textBox(text,box,size,color,maxLines=1,align='left'){
 const original=String(text||''),[x,y,w,h]=box;if(!original||w<=0||h<=0)return '';
 let chosen=null,fs=size;
 for(fs=size;fs>=8;fs-=0.5){const ls=linesFor(original,fs,w,maxLines);if(!ls)continue;const shapes=ls.map(measured),height=shapes.reduce((a,s)=>a+s.height*fs,0)+Math.max(0,ls.length-1)*fs*.45;
  if(shapes.every(s=>s.width*fs<=w)&&height<=h){chosen={ls,shapes,height};break;}}
 if(!chosen){fs=Math.max(8,Math.min(size,h*.65));let short=original;while(short.length>1&&(measured(short+'…').width*fs>w||measured(short+'…').height*fs>h))short=short.slice(0,-1);const shown=short===original?short:short+'…',s=measured(shown);fs=Math.min(fs,w/s.width,h/s.height);chosen={ls:[shown],shapes:[s],height:s.height*fs};}
 let top=y+(h-chosen.height)/2,svg='';
 chosen.shapes.forEach((s,i)=>{const left=x+(align==='center'?(w-s.width*fs)/2:(align==='right'||s.rtl)?w-s.width*fs:0),baseline=top+s.maxY*fs;
  const paths=s.glyphs.map(g=>`<path d="${g.path}" transform="translate(${n(left+(g.x-s.minX)*fs)} ${n(baseline-g.y*fs)}) scale(${n(fs/g.unit)} ${n(-fs/g.unit)})"/>`).join('');
  svg+=`<g fill="${color}" role="img" aria-label="${esc(chosen.ls[i])}" data-text="${esc(original)}" data-box="${[left,top,s.width*fs,s.height*fs].map(n).join(',')}"><title>${esc(chosen.ls[i])}</title>${paths}</g>`;
  top+=s.height*fs+fs*.45;
 });return svg;
}
function luminance(hex){const a=hex.slice(1).match(/../g).map(x=>parseInt(x,16)/255).map(x=>x<=.04045?x/12.92:((x+.055)/1.055)**2.4);return .2126*a[0]+.7152*a[1]+.0722*a[2];}
function ink(bg){return luminance(bg)>.179?'#000000':'#FFFFFF';}
function frame(w,h,label,content,layout){return `<svg xmlns="http://www.w3.org/2000/svg" width="${w}" height="${h}" viewBox="0 0 ${w} ${h}" role="img" aria-label="${esc(label)}" data-layout="${layout}"><title>${esc(label)}</title><metadata>Outlined text preserves font shaping. Full editable copy is in the campaign text files. Simplified small formats intentionally omit secondary text.</metadata>${content}</svg>`;}
const image=(logo,x,y,w,h)=>logo?`<image href="${esc(logo)}" x="${n(x)}" y="${n(y)}" width="${n(w)}" height="${n(h)}" preserveAspectRatio="xMidYMid meet" aria-label="Approved brand logo"/>`:'';
export function bannerSvg({product,subtitle='',audience='',benefits=[],primary='#E8B54A',secondary='#0F172A',cta='Learn more',logo='',watermark=false,width=1200,height=630,headline='',subheadline='',scene=''}){
 const w=Math.max(50,Math.min(5000,Math.round(width))),h=Math.max(50,Math.min(5000,Math.round(height))),p=Math.max(6,Math.min(64,Math.min(w,h)*.065));
 primary=safeHex(primary);secondary=safeHex(secondary,'#0F172A');logo=safeLogo(logo);
 const fg=ink(secondary),label=product||'Your brand';let svg=`<rect width="${w}" height="${h}" fill="${secondary}"/><path d="M0 0H${w}" stroke="${primary}" stroke-width="${Math.max(3,h*.006)}"/>`,layout;
 // Layered brand depth: two soft radial glows in the brand accent, a diagonal
 // sheen and a fine deterministic grain. All procedural — no external assets,
 // so offline rendering and browser PNG export keep working unchanged.
 const glows=`<defs>
  <radialGradient id="bfA" cx="82%" cy="18%" r="75%"><stop offset="0%" stop-color="${primary}" stop-opacity=".30"/><stop offset="55%" stop-color="${primary}" stop-opacity=".08"/><stop offset="100%" stop-color="${primary}" stop-opacity="0"/></radialGradient>
  <radialGradient id="bfB" cx="8%" cy="95%" r="80%"><stop offset="0%" stop-color="${primary}" stop-opacity=".16"/><stop offset="60%" stop-color="${primary}" stop-opacity=".04"/><stop offset="100%" stop-color="${primary}" stop-opacity="0"/></radialGradient>
  <linearGradient id="bfS" x1="0" y1="0" x2="1" y2="1"><stop offset="0%" stop-color="${fg}" stop-opacity=".05"/><stop offset="45%" stop-color="${fg}" stop-opacity="0"/></linearGradient>
  <filter id="bfG" x="0" y="0" width="100%" height="100%"><feTurbulence type="fractalNoise" baseFrequency=".8" numOctaves="2" stitchTiles="stitch" result="n"/><feColorMatrix in="n" type="matrix" values="0 0 0 0 1  0 0 0 0 1  0 0 0 0 1  0 0 0 .04 0"/></filter>
 </defs>
 <rect width="${w}" height="${h}" fill="url(#bfA)"/><rect width="${w}" height="${h}" fill="url(#bfB)"/><rect width="${w}" height="${h}" fill="url(#bfS)"/><rect width="${w}" height="${h}" filter="url(#bfG)" opacity=".55"/>`;
 svg+=glows;
 if(w<180&&h<120){layout='micro';const initials=label.split(/\s+/).map(x=>x[0]).slice(0,2).join('');svg+=logo?image(logo,p,p,w-2*p,h-2*p):textBox(initials,[p,p,w-2*p,h-2*p],Math.min(w,h)*.5,fg,1,'center');}
 else if(h<120&&w>h*2){
  layout='strip';const logoW=logo?h-2*p:0,bw=Math.min(145,w*.27),x=p+(logo?logoW+p:0),available=w-x-bw-3*p;
  svg+=image(logo,p,p,logoW,logoW)+textBox(label,[x,p,available,h-2*p],Math.min(32,h*.39),fg,2);
  svg+=`<rect x="${w-p-bw}" y="${h*.23}" width="${bw}" height="${h*.54}" rx="${h*.27}" fill="${primary}"/>`+textBox(cta,[w-p-bw+6,h*.23+4,bw-12,h*.54-8],Math.min(16,h*.25),ink(primary),1,'center');
}else{
  // Redesigned composition (owner review, 2026-09-07): one calm accent, no
  // rings/dot-grid/sheen, real headline from the copy stage, clean benefit list.
  layout=h>w*1.4?'vertical':w>h*1.7?'horizontal':'square';
  const inner=w-2*p,headerH=Math.min(64,h*.12),logoW=logo?Math.min(headerH,inner*.25):0;
  const head=(String(headline||'').trim()||String(benefits.find(x=>String(x||'').trim())||'')||label).trim();
  const sub=(String(subheadline||'').trim()||String(benefits.filter(x=>String(x||'').trim())[1]||'')).trim();
  const rtlTop=measured(head||label).rtl;
  if(scene){
   // v1.8 AI artwork: full-bleed scene + a readability scrim on the reading
   // side. Text/logo stay vector-exact; the scene is decorative only.
   const darkScrim=ink(secondary)==='#FFFFFF';
   const c=darkScrim?'7,13,17':'246,244,239';
   svg+=`<image href="${scene}" x="0" y="0" width="${w}" height="${h}" preserveAspectRatio="xMidYMid slice"/>`
     +`<defs><linearGradient id="bfSc" x1="0" y1="0" x2="1" y2="0">`
     +`<stop offset="0%" stop-color="rgb(${c})" stop-opacity="${darkScrim?.94:.9}"/>`
     +`<stop offset="52%" stop-color="rgb(${c})" stop-opacity="${darkScrim?.68:.72}"/>`
     +`<stop offset="92%" stop-color="rgb(${c})" stop-opacity="0"/></linearGradient>`
     +`<linearGradient id="bfScB" x1="0" y1="0" x2="0" y2="1">`
     +`<stop offset="60%" stop-color="rgb(${c})" stop-opacity="0"/>`
     +`<stop offset="100%" stop-color="rgb(${c})" stop-opacity="${darkScrim?.55:.5}"/></linearGradient></defs>`
     +`<rect width="${w}" height="${h}" fill="url(#bfSc)"/><rect width="${w}" height="${h}" fill="url(#bfScB)"/>`;
  }else{
   const arcR=Math.max(w,h)*.78;
   svg+=`<path d="M${n(w)},${n(h)} L${n(w)},${n(h-arcR)} A${n(arcR)} ${n(arcR)} 0 0 0 ${n(w-arcR)},${n(h)} Z" fill="${primary}" fill-opacity="${ink(secondary)==='#FFFFFF'?.07:.11}"/>`;
  }
  const tileS=Math.min(Math.max(30,Math.min(56,h*.08)),inner),fx=rtlTop?w-p-tileS:p;
  let nameX,wordW;
  if(logo){svg+=image(logo,p,p,logoW,headerH);nameX=rtlTop?p:fx;wordW=inner-(logoW+p*.5);}
  else{
   const initials=(label.split(/\s+/).map(x=>[...x][0]).filter(c=>c&&/\p{L}/u.test(c)).slice(0,2).join('')||'✷');
   svg+=`<rect x="${n(fx)}" y="${p}" width="${n(tileS)}" height="${n(tileS)}" rx="${n(tileS*.22)}" fill="${primary}"/>`
      +textBox(initials,[fx,p+tileS*.08,tileS,tileS*.84],tileS*.42,ink(primary),1,'center');
   nameX=rtlTop?p:fx+tileS+p*.5;wordW=w-p-(rtlTop?p:fx+tileS+p*.5);
  }
  svg+=textBox(subtitle||label,[nameX,p+(tileS-tileS*.5)/2,wordW,tileS*.5],Math.min(20,w*.05,h*.055),fg,1,rtlTop?'right':'left');
  svg+=`<rect x="${n(rtlTop?w-p-Math.max(90,w*.11):p)}" y="${n(p+tileS+Math.max(6,h*.012))}" width="${n(Math.max(90,w*.11))}" height="${Math.max(2,h*.005)}" fill="${primary}" fill-opacity=".9"/>`;
  const titleY=p+tileS+Math.max(16,h*.035);
  // CTA top edge mirrors the pill block below so the content area never collides with it.
  const ctaY=h-p-Math.max(30,Math.min(66,h*.112))-Math.max(16,h*.028)-(watermark?Math.max(18,h*.035):0);
  const areaH=Math.max(40,ctaY-Math.max(14,h*.028)-titleY);
  const tH=areaH*.42,sH=areaH*.17,gH=areaH*.04;
  const list=benefits.map(x=>String(x||'').trim()).filter(Boolean).slice(0,3);
  const lstH=Math.max(0,areaH-tH-sH-2*gH),itemH=list.length?lstH/list.length:0;
  svg+=textBox(head,[p,titleY,inner,tH],Math.min(96,w*.105,h*.15),fg,3,rtlTop?'right':'left');
  if(sub)svg+=textBox(sub,[p,titleY+tH+gH,inner,sH],Math.min(24,w*.045),fg,1,rtlTop?'right':'left');
  let ly=titleY+tH+gH+sH+gH;
  list.forEach((b,i)=>{
   const bh2=itemH-(list.length-1>0?gH*.5:0);
   svg+=`<rect x="${n(rtlTop?w-p-Math.max(3,h*.006):p)}" y="${n(ly+bh2*.14)}" width="${Math.max(3,h*.006)}" height="${n(bh2*.72)}" fill="${primary}"/>`
      +textBox(b,[p+(rtlTop?0:Math.max(10,h*.016)),ly,inner-Math.max(10,h*.016),bh2],Math.min(19,w*.04),fg,1,rtlTop?'right':'left');
   ly+=bh2+gH*.5;
  });

  // 6. CTA: elevated accent pill with glow — pinned to the reading-side edge (right for RTL).
  const bw=Math.min(inner*.62,Math.max(100,w*.4)),bh=Math.max(30,Math.min(66,h*.112)),by=h-p-bh-Math.max(16,h*.028)-(watermark?Math.max(18,h*.035):0);
  const cx0=rtlTop?w-p-bw:p;
  svg+=`<ellipse cx="${n(cx0+bw/2)}" cy="${n(by+bh*.72)}" rx="${n(bw*.55)}" ry="${n(bh*.85)}" fill="${primary}" fill-opacity="${scene?.09:.16}"/><rect x="${n(cx0)}" y="${n(by)}" width="${n(bw)}" height="${n(bh)}" rx="${n(bh/2)}" fill="${primary}"/>`+textBox(cta,[cx0+10,by+5,bw-20,bh-10],Math.min(22,w*.048),ink(primary),1,'center');
  if(watermark)svg+=textBox('BrandForge · Preview',[p,h-p-Math.max(12,h*.024),inner,Math.max(12,h*.024)],Math.min(12,w*.04),fg);
 }
 return frame(w,h,label,svg,layout);
}
export function logoSvg({brand,primary='#E8B54A',secondary='#0F172A',style='combination',watermark=false}){
 const pc=safeHex(primary),sc=safeHex(secondary,'#0F172A'),fg=ink(sc),initials=String(brand).split(/\s+/).map(x=>x[0]).slice(0,2).join('');let svg=`<rect width="1024" height="1024" rx="64" fill="${sc}"/>`;
 if(style==='wordmark')svg+=textBox(brand,[80,290,864,440],150,fg,3,'center');
 else if(style==='lettermark')svg+=`<rect x="192" y="192" width="640" height="640" rx="170" fill="${pc}"/>`+textBox(initials,[242,290,540,400],320,ink(pc),1,'center');
 else if(style==='abstract')svg+=`<rect x="300" y="560" width="150" height="290" rx="60" fill="${pc}"/><rect x="500" y="430" width="150" height="420" rx="60" fill="${pc}"/><rect x="700" y="300" width="150" height="550" rx="60" fill="${pc}"/><path d="M300 470 A 620 620 0 0 1 850 470" fill="none" stroke="${pc}" stroke-width="26" stroke-linecap="round"/>`;
 else if(style==='pictorial')svg+=`<path d="M512 232 C 262 316 258 640 512 816 C 766 640 762 316 512 232 Z" fill="${pc}"/><path d="M512 310 L 512 730" stroke="${sc}" stroke-width="24" stroke-linecap="round"/><path d="M430 372 C 486 470 538 570 512 690" fill="none" stroke="${sc}" stroke-width="20" stroke-linecap="round"/>`;
 else if(style==='emblem')svg+=`<circle cx="512" cy="490" r="335" fill="none" stroke="${pc}" stroke-width="22"/><circle cx="512" cy="490" r="290" fill="none" stroke="${pc}" stroke-width="3"/>`+textBox(initials,[295,265,434,250],220,fg,1,'center')+textBox(brand,[235,545,554,140],76,fg,2,'center');
 else svg+=`<circle cx="512" cy="338" r="165" fill="${pc}"/>`+textBox(initials,[385,230,254,210],145,ink(pc),1,'center')+textBox(brand,[80,590,864,190],105,fg,2,'center');
 if(watermark)svg+=textBox('BrandForge · Preview',[130,900,764,44],24,fg,1,'center');
 return frame(1024,1024,brand,svg,'logo-'+style);
}
export {textBox as measuredTextBox};

export function validateVisualText(input){
 const faces=getFonts();
 // audience and offer are rendered or user-visible too; validating them here
 // returns a clean 400 instead of a confusing downstream failure when a user
 // types a script the bundled visual fonts do not support.
 for(const value of [input.product,input.benefits,input.cta,input.audience,input.offer])for(const ch of String(value||'')){
  if(/[\p{L}\p{N}]/u.test(ch)&&!faces.some(f=>f.hasGlyphForCodePoint(ch.codePointAt(0))))throw new HttpError(400,'This brief contains a script that the bundled visual fonts do not support. Use a supported script or an approved logo.','UNSUPPORTED_VISUAL_SCRIPT');
 }
}
