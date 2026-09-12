import {hydrateCampaign} from '/private-assets.js';
import {campaignZip,saveBlob} from '/workspace-tools.js';
const $=id=>document.getElementById(id),token=location.hash.slice(1);
let campaign=null,url=null,pending=null;
async function api(body,files=false){
 const response=await fetch('/api/review'+(files?'?files=1':''),{method:body?'POST':'GET',headers:{Authorization:'Bearer '+token,'Content-Type':'application/json'},...(body?{body:JSON.stringify(body)}:{}),credentials:'omit',cache:'no-store',referrerPolicy:'no-referrer',signal:AbortSignal.timeout(30000)});
 const data=await response.json();if(!response.ok)throw new Error(data.error||'Review unavailable');return data;
}
function visual(){if(url)URL.revokeObjectURL(url);url=null;const file=campaign?.files?.find(f=>f.name===$('format').value);$('visual').hidden=!file;if(!file){$('visual').removeAttribute('src');return;}url=URL.createObjectURL(new Blob([file.content],{type:'image/svg+xml'}));$('visual').src=url;}
function responses(review){$('state').textContent=`Version ${review.revision} · ${review.status.replaceAll('_',' ')} · Expires ${new Date(review.expires_at).toLocaleString()}`;$('comments').replaceChildren();for(const c of review.comments){const box=document.createElement('article'),heading=document.createElement('strong'),p=document.createElement('p');heading.textContent=c.name+' · '+c.decision.replaceAll('_',' ');p.textContent=c.message;box.append(heading,p);$('comments').append(box);}}
async function load(){
 $('pack').hidden=true;campaign=null;visual();$('message').textContent='Loading the shared version…';
 try{
  if(!/^[a-f0-9]{64}$/.test(token))throw new Error('Open the complete private review link supplied by the owner.');
  const data=await api();campaign=data.campaign;
  if(campaign.asset_bundle_id){const descriptor=await api(null,true);campaign=await hydrateCampaign(campaign,async()=>descriptor,descriptor.storage_origin);}
  $('title').textContent=campaign.name;$('text').replaceChildren();for(const key of ['strategy','copy','seo']){const heading=document.createElement('h3'),pre=document.createElement('pre');heading.textContent=key;pre.textContent=campaign[key]||'';$('text').append(heading,pre);}
  $('format').replaceChildren(...campaign.files.filter(f=>/^(hero_banner|banner_.*)\.svg$/.test(f.name)).map(f=>new Option(f.name,f.name)));visual();responses(data.review);$('pack').hidden=false;$('message').textContent='Shared version loaded. Downloads and screenshots cannot be recalled after sharing.';
 }catch(e){campaign=null;visual();$('message').textContent=e.message;}
}
$('format').onchange=visual;$('refresh').onclick=load;
$('reply').onsubmit=async e=>{e.preventDefault();const b=$('send');b.disabled=true;try{const draft={name:$('name').value,message:$('note').value,decision:$('decision').value};if(!pending||JSON.stringify(pending.draft)!==JSON.stringify(draft))pending={draft,request_id:crypto.randomUUID()};const data=await api({...draft,request_id:pending.request_id});responses(data.review);pending=null;$('message').textContent='Response recorded for this version.';}catch(err){$('message').textContent=err.message;}finally{b.disabled=false;}};
$('download').onclick=async()=>{const b=$('download');b.disabled=true;try{await api();const pack=await campaignZip(campaign,t=>$('message').textContent=t);saveBlob(pack.blob,pack.name);$('message').textContent=pack.warnings.length?'Downloaded with export warnings. Read EXPORT-WARNINGS.txt.':'Shared pack downloaded.';}catch(e){$('message').textContent=e.message;}finally{b.disabled=false;}};
window.addEventListener('pagehide',()=>{if(url)URL.revokeObjectURL(url);});load();
