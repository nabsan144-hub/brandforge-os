import {productPhotoDimensions} from './image-dimensions.js';
// SVG is accepted only as a flattened reference, never inserted as live DOM.
export async function prepareReference(file){
 if(file.size>3000000)throw Error('Reference exceeds 3 MB. Export a smaller PNG first.');
 let blob=file;
 if(file.type==='image/svg+xml'||file.name?.toLowerCase().endsWith('.svg')){
  const source=await file.text();if(/<!\s*(?:DOCTYPE|ENTITY)/i.test(source))throw Error('SVG document types and entities are not imported.');
  const parsed=new DOMParser().parseFromString(source,'image/svg+xml'),root=parsed.documentElement;
  if(parsed.querySelector('parsererror')||root.localName!=='svg'||root.namespaceURI!=='http://www.w3.org/2000/svg'||parsed.querySelector('script,foreignObject,iframe,object,embed,style')||parsed.querySelectorAll('*').length>10000)throw Error('Unsupported or active SVG. Export a trusted PNG instead.');
  if([...parsed.childNodes].some(n=>n.nodeType===7))throw Error('SVG processing instructions are not imported.');
  for(const filter of parsed.querySelectorAll('filter'))filter.remove();
  const allowed=new Set('svg g defs path rect circle ellipse line polyline polygon text tspan title desc metadata lineargradient radialgradient stop clippath mask pattern symbol use image'.split(' '));
  let images=0;
  for(const el of parsed.querySelectorAll('*')){
   if(el.namespaceURI!==root.namespaceURI||!allowed.has(el.localName.toLowerCase()))throw Error('Only static SVG artwork is imported; export other content as PNG.');
   for(const attr of [...el.attributes]){
    if(/^on/i.test(attr.localName)||attr.localName==='style'||attr.localName==='base')throw Error('Active SVG attributes are not imported.');
    if(['fill','stroke','clip-path','mask','cursor','marker-start','marker-end','marker-mid'].includes(attr.localName)&&attr.value.includes('\\'))throw Error('Escaped SVG resource expressions are not imported.');
    if(attr.localName==='filter'){el.removeAttributeNode(attr);continue;}
    if(['href','src'].includes(attr.localName)&&!attr.value.startsWith('#')){
     if(el.localName!=='image'||!/^data:image\/(png|jpeg);base64,[A-Za-z0-9+/=]+$/.test(attr.value)||++images>8)throw Error('External SVG resources are not imported.');
     const bytes=Uint8Array.from(atob(attr.value.split(',')[1]),c=>c.charCodeAt(0));productPhotoDimensions(bytes);
    }
    if(/url\s*\(/i.test(attr.value)&&!/^[a-z-]*\(?\s*#[-a-zA-Z0-9_]+\)?$/.test(attr.value)&&!/^url\(#[a-zA-Z0-9_-]+\)$/.test(attr.value))throw Error('External CSS resources are not imported.');
   }
  }
  let expanded=0;const inspect=(el,depth=0,stack=new Set())=>{if(++expanded>50000||depth>64||stack.has(el))throw Error('SVG reference expansion is too complex.');const next=new Set(stack);next.add(el);if(el.localName==='use'){const href=el.getAttribute('href')||el.getAttributeNS('http://www.w3.org/1999/xlink','href')||'';const target=parsed.getElementById(href.slice(1));if(!target)throw Error('Unresolved SVG reference.');inspect(target,depth+1,next);}for(const child of el.children)inspect(child,depth+1,next);};inspect(root);
  const vb=(root.getAttribute('viewBox')||'').trim().split(/[ ,]+/).map(Number),w=Number(root.getAttribute('width'))||vb[2],h=Number(root.getAttribute('height'))||vb[3];
  if(!Number.isFinite(w)||!Number.isFinite(h)||w<=0||h<=0||w>5000||h>5000)throw Error('Unsupported SVG dimensions.');
  if(!root.getAttribute('viewBox'))root.setAttribute('viewBox',`0 0 ${w} ${h}`);
  const scale=Math.min(1,1200/w,1200/h);root.setAttribute('width',String(Math.round(w*scale)));root.setAttribute('height',String(Math.round(h*scale)));
  blob=new Blob([new XMLSerializer().serializeToString(root)],{type:'image/svg+xml'});
 }else{
  if(!['image/png','image/jpeg'].includes(file.type))throw Error('Choose PNG, JPEG or a static SVG.');
  productPhotoDimensions(await file.arrayBuffer());
 }
 let url;
 try{url=URL.createObjectURL(blob);const image=new Image();await new Promise((ok,no)=>{const timer=setTimeout(()=>no(Error('Image decoding timed out')),10000);image.onload=()=>{clearTimeout(timer);ok();};image.onerror=()=>{clearTimeout(timer);no(Error('Reference could not be decoded'));};image.src=url;});
  if(image.naturalWidth*image.naturalHeight>4000000)throw Error('Decoded image exceeds 4 MP.');
  for(const max of [1200,900,600,400]){const c=document.createElement('canvas'),scale=Math.min(1,max/image.naturalWidth,max/image.naturalHeight);c.width=Math.max(1,Math.round(image.naturalWidth*scale));c.height=Math.max(1,Math.round(image.naturalHeight*scale));c.getContext('2d').drawImage(image,0,0,c.width,c.height);const src=c.toDataURL('image/png');c.width=c.height=0;if(src.length<=450000)return src;}
  throw Error('Reference is too complex to fit the editable document limit.');
 }finally{if(url)URL.revokeObjectURL(url);}
}
