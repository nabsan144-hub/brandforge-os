// Versioned archival transfer, not a native editor or authorization-state import.
export const PORTABLE_NOTICE='Archive transfer only: original files and the three text sections are preserved. Native editor recipes, live providers, IDs, approval state, billing and revision history are not transferred. Imports do not run AI or create a native editable campaign. Treat imported downloads as untrusted files.';
const encoder=new TextEncoder();
export const digest=async bytes=>Array.from(new Uint8Array(await crypto.subtle.digest('SHA-256',bytes)),x=>x.toString(16).padStart(2,'0')).join('');
export function portableBytes(file){if(file.encoding!=='base64'||typeof file.content!=='string'||!/^([A-Za-z0-9+/]{4})*([A-Za-z0-9+/]{2}==|[A-Za-z0-9+/]{3}=)?$/.test(file.content))throw new Error('Invalid file encoding.');return Uint8Array.from(atob(file.content),x=>x.charCodeAt(0));}
export async function validatePortable(pack){
 if(!pack||pack.format!=='brandforge-portable'||pack.version!==1||!['cloud','desktop'].includes(pack.origin)||typeof pack.name!=='string'||!pack.name.trim()||pack.name.length>80||!Array.isArray(pack.files)||pack.files.length>64||!pack.sections||Array.isArray(pack.sections))throw new Error('Unsupported portable pack version or structure.');
 if(encoder.encode(JSON.stringify(pack)).length>3000000)throw new Error('Portable packs are limited to 3 MB. Keep larger files in the original ZIP; no partial import was saved.');
 for(const k of ['strategy','copy','seo'])if(typeof pack.sections[k]!=='string'||pack.sections[k].length>20000)throw new Error('Invalid portable text section.');
 const names=new Set();for(const f of pack.files){
  if(!/^[\p{L}\p{N}][\p{L}\p{N}._-]{0,119}$/u.test(f.name||'')||names.has(f.name)||!/\.(svg|png|jpe?g|webp|pdf|docx|txt|md|csv|json|html)$/i.test(f.name)||!Number.isInteger(f.bytes)||!/^[a-f0-9]{64}$/.test(f.sha256||''))throw new Error('Invalid or duplicate portable filename.');
  names.add(f.name);const bytes=portableBytes(f);if(bytes.length!==f.bytes||await digest(bytes)!==f.sha256)throw new Error('Portable checksum mismatch. Nothing was imported.');
 }
 // Reject hidden authorization/configuration fields instead of forwarding them.
 if(Object.keys(pack).some(k=>!['format','version','origin','name','sections','files','omitted_files'].includes(k))||Object.keys(pack.sections).some(k=>!['strategy','copy','seo'].includes(k))||pack.files.some(f=>Object.keys(f).some(k=>!['name','encoding','content','bytes','sha256'].includes(k))))throw new Error('Unknown fields are not imported.');
 if(pack.omitted_files!==undefined&&(!Array.isArray(pack.omitted_files)||pack.omitted_files.length>128||pack.omitted_files.some(f=>!f||typeof f.name!=='string'||f.name.length>120||typeof f.reason!=='string'||f.reason.length>200||Object.keys(f).some(k=>!['name','reason'].includes(k)))))throw new Error('Invalid omission report');
 return pack;
}
export async function exportPortable(campaign,{core=false}={}){
 const files=[],omitted=[];for(const f of campaign.files||[]){if(core&&f.name!=='hero_banner.svg'){omitted.push({name:f.name,reason:'Core transfer selected; retain the original ZIP for this file.'});continue;}if(typeof f.content!=='string')throw new Error('Load all private files before exporting.');const bytes=f.encoding==='base64'?Uint8Array.from(atob(f.content),x=>x.charCodeAt(0)):encoder.encode(f.content);let s='';for(const b of bytes)s+=String.fromCharCode(b);files.push({name:f.name,encoding:'base64',content:btoa(s),bytes:bytes.length,sha256:await digest(bytes)});}
 return validatePortable({format:'brandforge-portable',version:1,origin:'cloud',name:String(campaign.name||'Campaign').slice(0,80),...(core?{omitted_files:omitted}:{}),sections:Object.fromEntries(['strategy','copy','seo'].map(k=>[k,campaign[k]||''])),files});
}
