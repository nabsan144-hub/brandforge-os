import {campaignZip,saveBlob,fileBytes} from '/workspace-tools.js';
import {vectorQuality,qualityIssues} from '/vector-quality.js';
const $=id=>document.getElementById(id);
let current=null,url=null,serial=0,manifest=null;
try{document.documentElement.dataset.theme=localStorage.getItem('brandforge-theme')==='dark'?'dark':'light';}catch{}
$('theme').onclick=()=>{const theme=document.documentElement.dataset.theme==='dark'?'light':'dark';document.documentElement.dataset.theme=theme;try{localStorage.setItem('brandforge-theme',theme);}catch{}};
function preview(){
 if(url)URL.revokeObjectURL(url);url=null;
 const f=current?.files?.find(x=>x.name===$('asset').value);if(!f)return;
 url=URL.createObjectURL(new Blob([fileBytes(f)],{type:'image/svg+xml'}));$('preview').src=url;$('preview').alt='Fictional Northline Coffee: '+f.name;$('preview').hidden=false;
 const issues=qualityIssues(vectorQuality([f]));$('fit').textContent=issues.length?'Fit warnings: '+issues.join(' · '):'No omitted-field warnings reported for this format. Check actual-size readability, claims and platform safe areas yourself.';
}
async function load(){
 const request=++serial;if(url)URL.revokeObjectURL(url);url=null;$('copy').textContent='';$('fit').textContent='';$('asset').replaceChildren();$('download').disabled=true;$('asset').disabled=true;current=null;$('preview').hidden=true;$('status').textContent='Loading sample…';
 try{
  if(!manifest){const r=await fetch('/assets/practice/manifest.json',{signal:AbortSignal.timeout(8000)});if(!r.ok)throw new Error();manifest=await r.json();}
  const name=$('version').value+'.json',record=manifest.files.find(x=>x.name===name);if(!record)throw new Error();
  const r=await fetch('/assets/practice/'+name,{signal:AbortSignal.timeout(8000)});if(!r.ok)throw new Error();const bytes=await r.arrayBuffer();
  const hash=Array.from(new Uint8Array(await crypto.subtle.digest('SHA-256',bytes)),x=>x.toString(16).padStart(2,'0')).join('');if(hash!==record.sha256||bytes.byteLength!==record.bytes)throw new Error();
  const pack=JSON.parse(new TextDecoder().decode(bytes));if(request!==serial)return;current=pack;
  $('asset').replaceChildren(...pack.files.filter(f=>f.name.endsWith('.svg')).map(f=>new Option(f.name,f.name)));$('asset').disabled=false;$('copy').textContent=pack.copy;$('download').disabled=false;$('status').textContent='Sample ready. No campaign was created.';preview();
 }catch{if(request===serial)$('status').textContent='Could not verify the sample. Your account and allowance have not changed. Reload to retry.';}
}
$('version').onchange=load;$('asset').onchange=preview;
$('download').onclick=async()=>{if(!current)return;const pack=current;$('download').disabled=true;$('version').disabled=true;try{const result=await campaignZip(pack,text=>$('status').textContent=text);saveBlob(result.blob,result.name);$('status').textContent=result.warnings.length?'Sample downloaded with export warnings; read EXPORT-WARNINGS.txt.':'Sample downloaded. No campaign allowance was used.';}catch{$('status').textContent='Sample export failed. Try again; no campaign allowance was used.';}finally{$('download').disabled=false;$('version').disabled=false;}};
window.addEventListener('pagehide',()=>{if(url)URL.revokeObjectURL(url);});load();
