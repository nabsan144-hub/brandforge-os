import {productPhotoDimensions} from './image-dimensions.js';
// Portable editable source. No scripts, HTML, external URLs or account state.
export const LIMIT=1000000;
const enc=new TextEncoder();
const keys=(o,allowed)=>o&&typeof o==='object'&&!Array.isArray(o)&&Object.keys(o).every(k=>allowed.includes(k));
const num=(v,a,b)=>typeof v==='number'&&Number.isFinite(v)&&v>=a&&v<=b;
const color=v=>typeof v==='string'&&/^#[a-f0-9]{6}$/i.test(v);
const text=(v,n)=>typeof v==='string'&&v.length<=n&&!/[\u0000-\u0008\u000b\u000c\u000e-\u001f\ud800-\udfff\ufffe\uffff]/u.test(v);
export function validateDocument(d){
 if(!keys(d,['format','version','name','width','height','background','watermark','sections','layers'])||d.format!=='brandforge-canvas'||d.version!==1||!text(d.name,80)||!d.name.trim()||!Number.isInteger(d.width)||!Number.isInteger(d.height)||!num(d.width,50,5000)||!num(d.height,50,5000)||!color(d.background)||typeof d.watermark!=='boolean'||!keys(d.sections,['strategy','copy','seo'])||!['strategy','copy','seo'].every(k=>text(d.sections[k],20000))||!Array.isArray(d.layers)||d.layers.length>80||enc.encode(JSON.stringify(d)).length>LIMIT)throw Error('Invalid canvas document or capacity exceeded (1 MB / 80 layers).');
 const ids=new Set();let images=0;
 for(const l of d.layers){
  if(!keys(l,['id','type','x','y','width','height','rotation','fill','text','fontSize','font','bold','align','direction','src','fit','anchor','opacity'])||!text(l.id,60)||!/^[-a-z0-9]+$/i.test(l.id)||ids.has(l.id)||!['text','rect','ellipse','image'].includes(l.type)||!num(l.x,0,d.width)||!num(l.y,0,d.height)||!num(l.width,1,d.width)||!num(l.height,1,d.height)||l.x+l.width>d.width+.001||l.y+l.height>d.height+.001||!num(l.rotation,-180,180)||!num(l.opacity,0,1)||!color(l.fill))throw Error('Invalid layer geometry or fields.');
  ids.add(l.id);
  if(l.type==='text'&&(!text(l.text,2000)||!num(l.fontSize,8,300)||!['sans-serif','serif','monospace'].includes(l.font)||typeof l.bold!=='boolean'||!['left','center','right'].includes(l.align)||!['ltr','rtl'].includes(l.direction)))throw Error('Invalid text layer.');
  if(l.type==='image'&&(!text(l.src,450000)||!/^data:image\/(png|jpeg);base64,(?:[A-Za-z0-9+/]{4})*(?:[A-Za-z0-9+/]{2}==|[A-Za-z0-9+/]{3}=)?$/.test(l.src)||!['contain','crop'].includes(l.fit)||!['xMinYMin','xMidYMin','xMaxYMin','xMinYMid','xMidYMid','xMaxYMid','xMinYMax','xMidYMax','xMaxYMax'].includes(l.anchor)||++images>8))throw Error('Invalid image; use a prepared PNG/JPEG (8 images maximum).');
  if(l.type==='image')productPhotoDimensions(Uint8Array.from(atob(l.src.split(',')[1]),c=>c.charCodeAt(0)));
 }
 return d;
}
const esc=v=>String(v).replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&apos;'}[c]));
export function renderDocument(d){
 validateDocument(d);
 let out=`<svg xmlns="http://www.w3.org/2000/svg" width="${d.width}" height="${d.height}" viewBox="0 0 ${d.width} ${d.height}" role="img" aria-label="${esc(d.name)}"><rect width="100%" height="100%" fill="${d.background}"/>`;
 for(const l of d.layers){
  const {x,y,width:w,height:h}=l;
  out+=`<g opacity="${l.opacity}" transform="rotate(${l.rotation} ${x+w/2} ${y+h/2})"><svg x="${x}" y="${y}" width="${w}" height="${h}" overflow="hidden">`;
  if(l.type==='rect')out+=`<rect width="${w}" height="${h}" fill="${l.fill}"/>`;
  if(l.type==='ellipse')out+=`<ellipse cx="${w/2}" cy="${h/2}" rx="${w/2}" ry="${h/2}" fill="${l.fill}"/>`;
  if(l.type==='image')out+=`<image href="${esc(l.src)}" width="${w}" height="${h}" preserveAspectRatio="${l.anchor} ${l.fit==='crop'?'slice':'meet'}"/>`;
  if(l.type==='text'){
   const anchor=l.align==='left'?'start':l.align==='right'?'end':'middle',tx=l.align==='left'?0:l.align==='right'?w:w/2;
   out+=`<text x="${tx}" y="${l.fontSize}" fill="${l.fill}" font-family="${l.font}" font-size="${l.fontSize}" font-weight="${l.bold?'bold':'normal'}" text-anchor="${anchor}" direction="${l.direction}" unicode-bidi="plaintext" xml:space="preserve">`;
   l.text.split('\n').forEach((line,i)=>{out+=`<tspan x="${tx}" dy="${i?l.fontSize*1.2:0}">${esc(line)}</tspan>`;});out+='</text>';
  }
  out+='</svg></g>';
 }
 if(d.watermark){const size=Math.max(8,Math.min(18,d.width/24)),h=size*1.7;out+=`<g data-watermark="brandforge"><rect y="${d.height-h}" width="${d.width}" height="${h}" fill="#102033"/><text x="${d.width/2}" y="${d.height-h/2+size/3}" text-anchor="middle" font-family="sans-serif" font-size="${size}" fill="#ffffff">Made with BrandForge</text></g>`;}
 return out+'</svg>';
}
export function newDocument(name='Untitled canvas'){return {format:'brandforge-canvas',version:1,name,width:1200,height:630,background:'#ffffff',watermark:true,sections:{strategy:'',copy:'',seo:''},layers:[]};}
