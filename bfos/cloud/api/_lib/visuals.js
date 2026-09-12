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
// ---- Bold creative composition (v1.9 premium agency redesign) --------------
// Language derived from modern ad-creative direction: a calm branded field
// with soft radial washes and a board frame, one confident overline headline
// with a brand underline, ONE structured benefits area (icon rail, outlined
// info card or elevated solid panel — four layout personalities from the
// brief hash), an offer chip and a glass CTA pill. All geometry is procedural
// and deterministic from the brief; text stays exact outlined vector text
// from the copy stage and only the customer's own colours, words, benefits,
// offer and approved logo are used. style:'essential' keeps the calm classic
// composition; 'bold' is the default for new packs (engine level).
const h32=s=>{let x=5381;for(const c of String(s||''))x=(x*33^c.codePointAt(0))>>>0;return x;};
const STAR_PATH='M0 -1 L.22 -.22 1 0 .22 .22 0 1 -.22 .22 -1 0 -.22 -.22 Z';
const sparkAt=(cx,cy,r,fill,op)=>`<path d="${STAR_PATH}" transform="translate(${n(cx)} ${n(cy)}) rotate(${n((cx+cy)%36-18)}) scale(${n(r)})" fill="${fill}" fill-opacity="${n(op)}"/>`;
const PICTOS=[
 c=>`<path d="${STAR_PATH}" transform="scale(11)" fill="${c}"/>`,
 c=>`<path d="M2.2 -11 L-6.5 2.4 h5.1 L-1.8 11 L8.5 -3.2 h-5.1 Z" fill="${c}"/>`,
 c=>`<path d="M-9 .5 L-3 6.5 L9 -6.5" fill="none" stroke="${c}" stroke-width="3.4" stroke-linecap="round" stroke-linejoin="round"/>`,
 c=>`<path d="M0 -11 L8 -8 V.5 C8 6.2 4.4 9.4 0 11 C-4.4 9.4 -8 6.2 -8 .5 V-8 Z" fill="${c}"/>`,
 c=>`<path d="M-8 9 C-8 -2 -2 -9 9 -9 C9 2 2 9 -8 9 Z" fill="${c}"/>`,
 c=>`<g fill="${c}" stroke="${c}"><circle r="4.2" stroke="none"/><path d="M0 -11 v3 M0 8 v3 M-11 0 h3 M8 0 h3 M-7.8 -7.8 l2.1 2.1 M5.7 5.7 l2.1 2.1 M7.8 -7.8 L5.7 -5.7 M-5.7 5.7 l-2.1 2.1" fill="none" stroke-width="2.2" stroke-linecap="round"/></g>`
];
function boldBody({w,h,p,inner,head,sub,label,list,offerTxt,primary,secondary,fg,watermark,rtlTop,logo,cta,layout}){
 // ----- Premium agency-ad composition (owner standard review, 2026-09-11) ---
 // Calm field, one confident headline with a brand underline, ONE structured
 // benefits area and a clean CTA row. No rotated paint band, no blob storm,
 // no star-sticker sprinkles. Four deterministic layout personalities (hash
 // of the brief) so different businesses get visibly different designs; exact
 // outlined text is never modified, only laid out.
 const H=h32(label+'|'+head+'|'+list.join('|')+'|'+(offerTxt||''))||1;
 const wide=layout==='horizontal'&&w>=760;
 const varN=wide?H%4:H%3;
 const inkPri=ink(primary);
 const oTxt=offerTxt?(/^[\x00-\x7F]*$/.test(offerTxt)?offerTxt.toUpperCase():offerTxt):'';
 const wmk=watermark?Math.max(14,h*.03):0;
 const initials=label.split(/\s+/).map(x=>[...x][0]).filter(c=>c&&/\p{L}/u.test(c)).slice(0,2).join('')||'\u2726';
 const padX=wide?p+w*.01:p+w*.028,contX=padX,contW=w-2*padX;
 const tileS=Math.min(Math.max(28,h*.075),54,contW*.45);
 const rtlA=rtlTop?'right':'left';
 const L=rtlTop?contX+contW:contX,R=rtlTop?contX:contX+contW;
 let out='';
 // 1. Soft seeded atmosphere in opposing corners — radial-gradient washes
 // with a soft falloff (premium print-ad haze), radii capped by the SHORT
 // canvas side so tall formats stay balanced, plus a fine inset board frame.
 const ws=H%2?1:-1,mm=Math.min(w,h),wop=ink(secondary)==='#FFFFFF';
 out+=`<defs><radialGradient id="bfW1"><stop offset="0%" stop-color="${primary}" stop-opacity="${wop?'.26':'.17'}"/><stop offset="100%" stop-color="${primary}" stop-opacity="0"/></radialGradient><radialGradient id="bfW2"><stop offset="0%" stop-color="${primary}" stop-opacity="${wop?'.14':'.09'}"/><stop offset="100%" stop-color="${primary}" stop-opacity="0"/></radialGradient></defs>`
    +`<ellipse cx="${n(R-ws*(rtlTop?-1:1)*w*.03)}" cy="${n(h*.1)}" rx="${n(mm*(.34+(H%5)*.012))}" ry="${n(mm*.44)}" fill="url(#bfW1)"/>`
    +`<ellipse cx="${n(L+ws*(rtlTop?-1:1)*w*.02)}" cy="${n(h*.95)}" rx="${n(mm*.3)}" ry="${n(mm*.4)}" fill="url(#bfW2)"/>`
    +`<rect x="${n(p*.6)}" y="${n(p*.6)}" width="${n(w-p*1.2)}" height="${n(h-p*1.2)}" rx="${n(p*.55)}" fill="none" stroke="${fg}" stroke-opacity=".06" stroke-width="1.4"/>`;
 // 2. Header: badge/logo at the reading edge, brand label beside it.
 const bx=rtlTop?Math.max(p*.6,R-tileS):L;
 if(logo){const lw=Math.min(tileS*1.9,contW*.3);out+=image(logo,bx,p,lw,tileS);}
 else out+=`<rect x="${n(bx)}" y="${n(p)}" width="${n(tileS)}" height="${n(tileS)}" rx="${n(tileS*.26)}" fill="${primary}"/>`
  +textBox(initials,[bx,p+tileS*.09,tileS,tileS*.84],tileS*.44,inkPri,1,'center');
 const lblW=contW*.44,lblX=rtlTop?bx-p*.55-lblW:bx+tileS*.7+p*.5;
 out+=textBox(label,[Math.max(rtlTop?p:lblX,rtlTop?p:lblX),p+tileS*.1,lblW,tileS*.8],Math.min(22,w*.05,Math.max(1,h*.058)),fg,1,rtlA);
 // 3. Offer chip at the far edge (outline stamp — never fights the badge).
 if(oTxt){
  const chipW=Math.min(contW*.3,260),chipH=Math.max(26,h*.05);
  const cx0=rtlTop?contX:contX+contW-chipW;
  out+=`<rect x="${n(cx0)}" y="${n(p+tileS*.14)}" width="${n(chipW)}" height="${n(chipH)}" rx="${n(chipH/2)}" fill="${primary}" fill-opacity="${ink(fg)==='#FFFFFF'?'.15':'.1'}" stroke="${primary}" stroke-opacity=".5"/>`
     +textBox(oTxt,[cx0+8,p+tileS*.14+3,chipW-16,chipH-6],Math.min(16,w*.034,Math.max(1,h*.038)),primary,1,'center');
 }
 const headY=p+tileS+Math.max(14,h*.034);
 const barW=Math.max(90,contW*.24);
 // Benefit pictograms: seeded pick per benefit, salted by row index AND
 // deduped within the banner so two benefits never share one mark.
 const usedPicts=new Set();
 const pict=(b,i)=>{let k=(h32(String(b))+i*2)%PICTOS.length;while(usedPicts.has(k))k=(k+1)%PICTOS.length;usedPicts.add(k);return PICTOS[k];};
 const iconAt=(cx,cy,r,b,i)=>`<g transform="translate(${n(cx)} ${n(cy)}) scale(${n(r/11)})">${pict(b,i)(primary)}</g>`;
 const dot=(cx,cy,c)=>`<circle cx="${n(cx)}" cy="${n(cy)}" r="${n(Math.max(2.6,h*.006))}" fill="${c||primary}"/>`;
 const ctaPill=(x,y,ph,pw)=>{
  out+=`<ellipse cx="${n(x+pw/2)}" cy="${n(y+ph*.75)}" rx="${n(pw*.56)}" ry="${n(ph*.95)}" fill="${primary}" fill-opacity=".18"/>`
     +`<rect x="${n(x)}" y="${n(y)}" width="${n(pw)}" height="${n(ph)}" rx="${n(ph/2)}" fill="${primary}"/>`
     +`<rect x="${n(x+ph*.3)}" y="${n(y+ph*.09)}" width="${n(pw-ph*.6)}" height="${n(ph*.11)}" rx="${n(ph*.055)}" fill="${inkPri}" fill-opacity=".22"/>`
     +textBox(cta,[x+10,y+5,pw-20,ph-10],Math.min(22,w*.047),inkPri,1,'center');};
 const wmkRow=(ax,aw2,color)=>{if(watermark)out+=textBox('BrandForge \u00b7 Preview',[ax,h-p-wmk+2,aw2,wmk-2],Math.min(12,w*.035),color);};
 // Utility: headline + underline + sub block, reading-side aligned.
 const copyBlock=(bx0,bw2,tH2)=>{
  out+=textBox(head,[bx0,headY,bw2,tH2],Math.min(88,Math.max(1,w*.078),Math.max(1,h*.165)),fg,2,rtlA);
  const by2=headY+tH2+Math.max(10,h*.018);
  out+=`<rect x="${n(rtlTop?bx0+bw2-barW:bx0)}" y="${n(by2)}" width="${n(barW)}" height="${n(Math.max(4,h*.008))}" rx="${n(Math.max(2,h*.004))}" fill="${primary}"/>`;
  let y2=by2+Math.max(10,h*.02);
  if(sub){out+=textBox(sub,[bx0,y2,bw2,h*.052],Math.min(22,w*.042),fg,1,rtlA);y2+=h*.052+Math.max(8,h*.014);}
  return y2;};
 if(!wide){
  // ---- Personality A (square / tall / narrow): stacked composition ----
  const pillH=Math.max(34,Math.min(64,h*.1)),pillW=Math.min(contW*.6,Math.max(150,w*.42));
  const pillY=h-p-wmk-pillH;
  const y2=copyBlock(contX,contW,Math.min(h*.3,(pillY-Math.max(10,h*.02)-headY)*.55));
  // Rail is centred in the zone between copy and CTA — on tall formats this
  // avoids a dead band under the benefits row.
  const avail=Math.max(0,pillY-Math.max(10,h*.014)-y2-Math.max(6,h*.012));
  const railTop=y2+Math.max(6,h*.012)+avail*.17,railH=avail*.66;
  if(list.length&&railH>h*.1){
   const m=list.length,cw=contW/m,iR=Math.min(railH*.2,cw*.16,Math.max(1,h*.055));
   list.forEach((b,i)=>{
    const cx=contX+cw*((rtlTop?m-1-i:i)+.5);
    out+=`<circle cx="${n(cx)}" cy="${n(railTop+iR)}" r="${n(iR*1.34)}" fill="${primary}" fill-opacity="${ink(fg)==='#FFFFFF'?'.13':'.09'}"/>`;
    out+=iconAt(cx,railTop+iR,iR*1.02,b,i);
    if(i>0)out+=`<rect x="${n(contX+cw*(rtlTop?m-i:i))}" y="${n(railTop+railH*.16)}" width="1.2" height="${n(Math.max(1,railH*.68))}" fill="${fg}" fill-opacity=".13"/>`;
    out+=textBox(b,[cx-cw*.44,railTop+iR*2.34,cw*.88,Math.max(14,railH-iR*2.34-4)],Math.min(18,w*.038),fg,3,'center');
   });
  }
  ctaPill(rtlTop?R:R-pillW,pillY,pillH,pillW);wmkRow(contX,contW,fg);
  return out;
 }
 if(varN===1){
  // ---- Personality B (wide): info card on the far side --------------------
  const cardW=Math.min(contW*.33,370),gap2=Math.max(22,w*.026);
  const cardX=rtlTop?contX:contX+contW-cardW,bw2=contW-cardW-gap2,bx0=rtlTop?cardX+cardW+gap2:contX;
  const y2=copyBlock(bx0,bw2,h*.36);
  const cTop=headY,cBot=h-p-wmk-Math.max(26,h*.048);
  out+=`<rect x="${n(cardX)}" y="${n(cTop+Math.max(7,h*.012))}" width="${n(cardW)}" height="${n(cBot-cTop)}" rx="${n(Math.max(14,w*.016))}" fill="#000000" fill-opacity="${wop?'.16':'.08'}"/>`
     +`<rect x="${n(cardX)}" y="${n(cTop)}" width="${n(cardW)}" height="${n(cBot-cTop)}" rx="${n(Math.max(14,w*.016))}" fill="${primary}" fill-opacity="${ink(fg)==='#FFFFFF'?'.085':'.055'}" stroke="${primary}" stroke-opacity=".42"/>`;
  if(list.length){
   const inP=Math.max(12,w*.013),rowH=(cBot-cTop-2*inP)/list.length;
   list.forEach((b,i)=>{
    const ry=cTop+inP+i*rowH,rC=Math.min(rowH*.3,17);
    const icx=rtlTop?cardX+cardW-inP-rC:cardX+inP+rC;
    out+=iconAt(icx,ry+rowH*.5,rC,b,i);
    const tOff=rtlTop?cardX+inP:cardX+inP+rC*2.4;
    out+=textBox(b,[tOff,ry,cardW-2*inP-rC*2.4,rowH],Math.min(17,w*.036),fg,2,rtlA);
    if(i<list.length-1)out+=`<rect x="${n(cardX+inP)}" y="${n(ry+rowH)}" width="${n(cardW-2*inP)}" height="1" fill="${fg}" fill-opacity=".12"/>`;
   });
  }else out+=textBox(sub||label,[cardX+12,cTop+12,cardW-24,cBot-cTop-24],Math.min(18,w*.04),fg,2,'center');
  const pillH=Math.max(34,Math.min(60,h*.1)),pillW=Math.min(bw2*.66,Math.max(150,w*.33));
  ctaPill(bx0,h-p-wmk-pillH,pillH,pillW);wmkRow(cardX,cardW,fg);
  return out;
 }
 if(varN===2||varN===3){
  // ---- Personality C/D (wide): solid primary panel, benefits in inverse ink
  const panelW=contW*.42,gap2=Math.max(24,w*.028);
  const flip=varN===3,panX=(rtlTop?!flip:flip)?contX:contX+contW-panelW;
  const panTop=headY-tileS*.32,panBot=h-p-wmk-4;
  // Elevation shadow under the solid panel — quiet, like a dropped card.
  out+=`<rect x="${n(panX)}" y="${n(panTop+Math.max(8,h*.014))}" width="${n(panelW)}" height="${n(panBot-panTop)}" rx="${n(Math.max(14,w*.018))}" fill="#000000" fill-opacity="${wop?'.24':'.13'}"/>`
     +`<rect x="${n(panX)}" y="${n(panTop)}" width="${n(panelW)}" height="${n(panBot-panTop)}" rx="${n(Math.max(14,w*.018))}" fill="${primary}"/>`;
  const bw2=contW-panelW-gap2,bx0=(rtlTop?!flip:flip)?contX+panelW+gap2:contX;
  copyBlock(bx0,bw2,h*.38);
  if(list.length){
   const inP=Math.max(14,w*.016),rowH=(panBot-panTop-2*inP)/list.length;
   list.forEach((b,i)=>{
    const ry=panTop+inP+i*rowH;
    const dx=rtlTop?panX+panelW-inP-8:panX+inP;
    out+=dot(dx,ry+rowH*.5,inkPri);
    // RTL text starts at the panel's inner reading edge and must END before
    // the dot zone; LTR text must START after it.
    const tX=rtlTop?panX+inP:panX+inP+16;
    out+=textBox(b,[tX,ry,panelW-2*inP-16,rowH],Math.min(19,w*.039),inkPri,2,rtlA);
   });
  }else out+=textBox(sub||label,[panX+16,panTop+16,panelW-32,panBot-panTop-32],Math.min(19,w*.042),inkPri,2,'center');
  const pillH=Math.max(34,Math.min(58,h*.095)),pillW=Math.min(bw2*.7,Math.max(150,w*.3));
  ctaPill(bx0,h-p-wmk-pillH,pillH,pillW);wmkRow(panX+12,panelW-24,inkPri);
  return out;
 }
 // ---- Personality A-wide ---------------------------------------------------
 const pillH=Math.max(34,Math.min(62,h*.1)),pillW=Math.min(contW*.5,Math.max(150,w*.38));
 const pillY=h-p-wmk-pillH;
 const y2=copyBlock(contX,contW,Math.min(h*.3,(pillY-Math.max(12,h*.02)-headY)*.6));
 const railTop=y2+Math.max(8,h*.014),railH=pillY-Math.max(8,h*.012)-railTop;
 if(list.length&&railH>h*.1){
  const m=list.length,cw=contW/m;
  list.forEach((b,i)=>{
   const cx=contX+cw*((rtlTop?m-1-i:i)+.5);
   const iR=Math.min(railH*.26,cw*.14,Math.max(1,h*.05));
   if(i>0)out+=`<rect x="${n(contX+cw*(rtlTop?m-i:i))}" y="${n(railTop+railH*.2)}" width="1.2" height="${n(Math.max(1,railH*.6))}" fill="${fg}" fill-opacity=".13"/>`;
   out+=iconAt(cx,railTop+iR,iR,b,i);
   out+=textBox(b,[cx-cw*.44,railTop+iR*2.2,cw*.88,Math.max(14,railH-iR*2.2-4)],Math.min(17,w*.037),fg,2,'center');
  });
 }
 ctaPill(rtlTop?R:R-pillW,pillY,pillH,pillW);wmkRow(contX,contW,fg);
 return out;
}

export function bannerSvg({product,subtitle='',audience='',benefits=[],primary='#E8B54A',secondary='#0F172A',cta='Learn more',logo='',watermark=false,width=1200,height=630,headline='',subheadline='',scene='',style='essential',offer=''}){
 const w=Math.max(50,Math.min(5000,Math.round(width))),h=Math.max(50,Math.min(5000,Math.round(height))),p=Math.max(6,Math.min(64,Math.min(w,h)*.065));
 primary=safeHex(primary);secondary=safeHex(secondary,'#0F172A');logo=safeLogo(logo);
 const fg=ink(secondary),label=product||'Your brand';let svg=`<rect width="${w}" height="${h}" fill="${secondary}"/><path d="M0 0H${w}" stroke="${primary}" stroke-width="${Math.max(3,h*.006)}"/>`,layout;
 // Layered brand depth: two soft radial glows in the brand accent, a diagonal
 // sheen and a fine deterministic grain. All procedural — no external assets,
 // so offline rendering and browser PNG export keep working unchanged.
 const bfDefs=`<defs>
  <radialGradient id="bfA" cx="82%" cy="18%" r="75%"><stop offset="0%" stop-color="${primary}" stop-opacity=".30"/><stop offset="55%" stop-color="${primary}" stop-opacity=".08"/><stop offset="100%" stop-color="${primary}" stop-opacity="0"/></radialGradient>
  <radialGradient id="bfB" cx="8%" cy="95%" r="80%"><stop offset="0%" stop-color="${primary}" stop-opacity=".16"/><stop offset="60%" stop-color="${primary}" stop-opacity=".04"/><stop offset="100%" stop-color="${primary}" stop-opacity="0"/></radialGradient>
  <linearGradient id="bfS" x1="0" y1="0" x2="1" y2="1"><stop offset="0%" stop-color="${fg}" stop-opacity=".05"/><stop offset="45%" stop-color="${fg}" stop-opacity="0"/></linearGradient>
  <filter id="bfG" x="0" y="0" width="100%" height="100%"><feTurbulence type="fractalNoise" baseFrequency=".8" numOctaves="2" stitchTiles="stitch" result="n"/><feColorMatrix in="n" type="matrix" values="0 0 0 0 1  0 0 0 0 1  0 0 0 0 1  0 0 0 .04 0"/></filter>
 </defs>`;
 const glows=bfDefs+`<rect width="${w}" height="${h}" fill="url(#bfA)"/><rect width="${w}" height="${h}" fill="url(#bfB)"/><rect width="${w}" height="${h}" fill="url(#bfS)"/><rect width="${w}" height="${h}" filter="url(#bfG)" opacity=".55"/>`;
 if(w<180&&h<120){layout='micro';svg+=glows;const initials=label.split(/\s+/).map(x=>x[0]).slice(0,2).join('');svg+=logo?image(logo,p,p,w-2*p,h-2*p):textBox(initials,[p,p,w-2*p,h-2*p],Math.min(w,h)*.5,fg,1,'center');}
 else if(h<120&&w>h*2){
  layout='strip';svg+=glows;const logoW=logo?h-2*p:0,bw=Math.min(145,w*.27),x=p+(logo?logoW+p:0),available=w-x-bw-3*p;
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
  const list=benefits.map(x=>String(x||'').trim()).filter(Boolean).slice(0,3);
  if(!scene&&style==='bold'){
   svg+=bfDefs+boldBody({w,h,p,inner,head,sub,label,list,offerTxt:String(offer||'').trim(),primary,secondary,fg,watermark,rtlTop,logo,cta,layout})
      +`<rect width="${w}" height="${h}" filter="url(#bfG)" opacity=".45"/>`;
  }else{
  if(scene){svg+=glows;
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
  }else{svg+=glows;
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
