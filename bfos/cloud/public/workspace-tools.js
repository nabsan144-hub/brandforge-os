// Self-hosted export tools. No CDN or document upload is needed for export.
import {zipSync,strToU8} from '/vendor/fflate.mjs';
export function fileBytes(file){return file.encoding==='base64'?Uint8Array.from(atob(file.content),c=>c.charCodeAt(0)):strToU8(file.content||'');}
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
 const files={},warnings=[],{files:visuals=[],...metadata}=campaign;
 files['campaign.json']=strToU8(JSON.stringify(metadata,null,2));
 for(const section of ['strategy','copy','seo'])files[section+'.md']=strToU8(campaign[section]||'');
 files['REVIEW-BEFORE-PUBLISHING.txt']=strToU8('This is a draft, not legal/platform approval. Verify claims, proof, rights, prices, offers, consent and destination links. SVG text is outlined for portable script shaping; text files remain editable. Editing copy does not automatically change a visual. Logo concepts are templates, not trademark clearance.\n');
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
 const url=URL.createObjectURL(file),img=new Image();
 try{
  await new Promise((ok,no)=>{img.onload=ok;img.onerror=()=>no(new Error('That image could not be decoded.'));img.src=url;});
  for(const max of [256,192,128,96]){
   const scale=Math.min(1,max/img.width,max/img.height),c=document.createElement('canvas');c.width=Math.max(1,Math.round(img.width*scale));c.height=Math.max(1,Math.round(img.height*scale));c.getContext('2d').drawImage(img,0,0,c.width,c.height);const data=c.toDataURL('image/png');c.width=0;c.height=0;if(atob(data.split(',')[1]).length<=64000)return data;
  }
  throw new Error('This image is too detailed for a small brand logo. Use a simpler logo.');
 }finally{URL.revokeObjectURL(url);}
}
