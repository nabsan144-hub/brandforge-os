import {vectorQuality,QUALITY_NOTICE} from '/vector-quality.js';
import {assertVisualReview,visualReviewNote} from '/visual-review.js';
// Self-hosted export tools. No CDN or document upload is needed for export.
import {zipSync,strToU8} from '/vendor/fflate.mjs';
export function fileBytes(file){if(typeof file?.content!=='string')throw new Error('Private files are not loaded. Reload the campaign before exporting.');return file.encoding==='base64'?Uint8Array.from(atob(file.content),c=>c.charCodeAt(0)):strToU8(file.content||'');}
export function saveBlob(blob,name){
 const url=URL.createObjectURL(blob),a=document.createElement('a');a.href=url;a.download=name;document.body.append(a);a.click();a.remove();setTimeout(()=>URL.revokeObjectURL(url),10000);
}
const leaf=name=>String(name).split(/[\\/]/).pop().replace(/[^\p{L}\p{N}._-]/gu,'_').replace(/^\.+/,'').slice(0,120)||'file';
export async function rasterize(file,type='image/png'){
 const bytes=fileBytes(file),url=URL.createObjectURL(new Blob([bytes],{type:'image/svg+xml'}));
 const img=new Image();let canvas;
 try{
  await new Promise((resolve,reject)=>{img.onload=resolve;img.onerror=()=>reject(new Error('This visual could not be rasterized. Download the SVG source instead.'));img.src=url;});
  const w=img.naturalWidth,h=img.naturalHeight;if(!w||!h||w>5000||h>5000)throw new Error('Raster dimensions must be between 50 and 5000 pixels.');
  canvas=document.createElement('canvas');canvas.width=w;canvas.height=h;const ctx=canvas.getContext('2d');if(!ctx)throw new Error('Canvas is unavailable.');
  if(type==='image/jpeg'){ctx.fillStyle='#ffffff';ctx.fillRect(0,0,w,h);}ctx.drawImage(img,0,0);
  const blob=await new Promise(resolve=>canvas.toBlob(resolve,type,.93));if(!blob)throw new Error('Raster export failed.');return blob;
 }finally{URL.revokeObjectURL(url);if(canvas){canvas.width=0;canvas.height=0;}}
}
export async function campaignZip(campaign,onProgress=()=>{},includePng=true){
 assertVisualReview(campaign);
 const files={},warnings=[],{files:visuals=[],...metadata}=campaign;
 const quality=vectorQuality(visuals);
 if(quality.length)files['VISUAL-QUALITY.json']=strToU8(JSON.stringify({schema:1,notice:QUALITY_NOTICE,formats:quality},null,2));
 files['COPY-VISUAL-REVIEW.txt']=strToU8(visualReviewNote(campaign)+'\n');
 if(campaign.visual_fields)files['VISUAL-FIELDS.json']=strToU8(JSON.stringify({fields:campaign.visual_fields,format_report:campaign.visual_field_report||[],notice:'Canonical inputs for the saved banners, not an automatic rewrite of the separate campaign copy. Destination is metadata only. Included does not certify legibility; preview all formats.'},null,2));
 files['campaign.json']=strToU8(JSON.stringify(metadata,null,2));
 for(const section of ['strategy','copy','seo'])files[section+'.md']=strToU8(campaign[section]||'');
 files['REVIEW-BEFORE-PUBLISHING.txt']=strToU8('This is a draft, not legal/platform approval. Verify claims, proof, rights, prices, offers, consent and destination links. SVG text is outlined for portable script shaping; text files remain editable. Editing copy does not automatically change a visual. Logo concepts are templates, not trademark clearance. Free-plan generated visuals carry visible BrandForge attribution; uploaded customer logos are unchanged. Visible attribution is not tamper-proof.\n');
 for(let i=0;i<visuals.length;i++){
  const f=visuals[i],name=leaf(f.name);files['visuals/'+name]=fileBytes(f);onProgress(`Preparing ${i+1}/${visuals.length}: ${name}`);
  if(includePng&&name.endsWith('.svg')){try{files['visuals/'+name.replace(/\.svg$/,'.png')]=new Uint8Array(await (await rasterize(f)).arrayBuffer());}catch(e){warnings.push(name+': '+e.message);}}
  await new Promise(r=>setTimeout(r,0));
 }
 if(warnings.length)files['EXPORT-WARNINGS.txt']=strToU8(warnings.join('\n'));
 const manifest=[];
 for(const [name,data] of Object.entries(files)){
  const digest=await crypto.subtle.digest('SHA-256',data);manifest.push({name,bytes:data.length,sha256:Array.from(new Uint8Array(digest),x=>x.toString(16).padStart(2,'0')).join('')});
 }
 files['manifest.json']=strToU8(JSON.stringify({schema:1,campaign:campaign.id,revision:campaign.revision,files:manifest},null,2));
 const bytes=zipSync(files,{level:6});return {blob:new Blob([bytes],{type:'application/zip'}),warnings,name:leaf(campaign.name||'campaign')+'.zip'};
}
export async function normalizedLogo(file){
 if(!['image/png','image/jpeg','image/webp'].includes(file.type)||file.size>5000000)throw new Error('Choose a PNG, JPEG or WebP under 5 MB.');
 logoDimensions(await file.arrayBuffer());
 const url=URL.createObjectURL(file),img=new Image();
 try{
  await new Promise((ok,no)=>{img.onload=ok;img.onerror=()=>no(new Error('That image could not be decoded.'));img.src=url;});
  for(const max of [256,192,128,96]){
   const scale=Math.min(1,max/img.width,max/img.height),c=document.createElement('canvas');c.width=Math.max(1,Math.round(img.width*scale));c.height=Math.max(1,Math.round(img.height*scale));c.getContext('2d').drawImage(img,0,0,c.width,c.height);const data=c.toDataURL('image/png');c.width=0;c.height=0;if(atob(data.split(',')[1]).length<=64000)return data;
  }
  throw new Error('This image is too detailed for a small brand logo. Use a simpler logo.');
 }finally{URL.revokeObjectURL(url);}
}


// Inspect bounded raster headers before asking the browser to decode a logo.
export function logoDimensions(bytes){
 const b=new Uint8Array(bytes),v=new DataView(b.buffer,b.byteOffset,b.byteLength);
 if(b.length<12||String.fromCharCode(...b.slice(0,4))!=='RIFF'||String.fromCharCode(...b.slice(8,12))!=='WEBP')return productPhotoDimensions(bytes);
 let width=0,height=0;const kind=String.fromCharCode(...b.slice(12,16));
 if(b.length>=30&&kind==='VP8X'){
  if(b[20]&2)throw new Error('Choose a static logo, not an animation.');
  width=1+b[24]+(b[25]<<8)+(b[26]<<16);height=1+b[27]+(b[28]<<8)+(b[29]<<16);
 }else if(b.length>=25&&kind==='VP8L'&&b[20]===47){const bits=v.getUint32(21,true);width=1+(bits&16383);height=1+((bits>>>14)&16383);}
 else if(b.length>=30&&kind==='VP8 '&&b[23]===157&&b[24]===1&&b[25]===42){width=v.getUint16(26,true)&16383;height=v.getUint16(28,true)&16383;}
 if(!width||!height||width*height>4_000_000)throw new Error('Use a complete static logo with at most 4 million pixels.');
 return {width,height};
}

// Read dimensions before browser decoding: avoid allocating a decompression bomb.
export function productPhotoDimensions(bytes){
 const b=new Uint8Array(bytes),v=new DataView(b.buffer,b.byteOffset,b.byteLength);let width=0,height=0;
 if(b.length>=24&&b.slice(0,8).every((x,i)=>x===[137,80,78,71,13,10,26,10][i])){width=v.getUint32(16);height=v.getUint32(20);}
 else if(b[0]===255&&b[1]===216){
  let i=2;
  while(i+4<b.length){
   if(b[i++]!==255)break;while(b[i]===255)i++;const marker=b[i++];
   if(marker===217||marker===218)break;
   const length=v.getUint16(i);if(length<2||i+length>b.length)break;
   if([192,193,194].includes(marker)&&length>=8){height=v.getUint16(i+3);width=v.getUint16(i+5);break;}i+=length;
  }
 }
 if(!width||!height||width*height>4_000_000)throw new Error('Use a complete PNG or JPEG with at most 4 million pixels.');
 return {width,height};
}
export async function normalizedProductPhoto(file){
 if(!['image/png','image/jpeg'].includes(file.type)||file.size>5_000_000)throw new Error('Choose a PNG or JPEG under 5 MB.');
 productPhotoDimensions(await file.arrayBuffer());
 const url=URL.createObjectURL(file),img=new Image();
 try{
  await new Promise((ok,no)=>{img.onload=ok;img.onerror=()=>no(new Error('The product photograph could not be decoded.'));img.src=url;});
  if(img.naturalWidth*img.naturalHeight>4_000_000)throw new Error('The decoded photograph exceeds the pixel limit.');
  for(const max of [1024,800,640,480]){
   const scale=Math.min(1,max/img.naturalWidth,max/img.naturalHeight),canvas=document.createElement('canvas');canvas.width=Math.max(1,Math.round(img.naturalWidth*scale));canvas.height=Math.max(1,Math.round(img.naturalHeight*scale));
   const ctx=canvas.getContext('2d');if(!ctx)throw new Error('Canvas is unavailable.');ctx.fillStyle='#ffffff';ctx.fillRect(0,0,canvas.width,canvas.height);ctx.drawImage(img,0,0,canvas.width,canvas.height);
   const data=canvas.toDataURL('image/jpeg',.8);canvas.width=0;canvas.height=0;if(atob(data.split(',')[1]).length<=120000)return data;
  }
  throw new Error('This photograph is too detailed. Choose a smaller image.');
 }finally{URL.revokeObjectURL(url);}
}
