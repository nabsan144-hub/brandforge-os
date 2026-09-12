try{document.documentElement.dataset.theme=localStorage.getItem('brandforge-theme')||localStorage.getItem('vg-theme')||(matchMedia('(prefers-color-scheme:light)').matches?'light':'dark');}catch{}
import {newDocument,validateDocument,renderDocument,LIMIT} from './model.js';
const $=id=>document.getElementById(id),clone=x=>structuredClone(x);
let d=newDocument(),selected=null,id=null,revision=0,headers={},history=[],future=[],pending=null,busy=false,epoch=0,connected=false,attributionRequired=null;
const msg=t=>$('status').textContent=t;
const layer=()=>d.layers.find(l=>l.id===selected);
function remember(){$('reviewed').checked=false;history.push(clone(d));if(history.length>30)history.shift();future=[];pending=null;}
function change(fn){if(busy)return;let before=clone(d);try{commitInputs();before=clone(d);fn();validateDocument(d);$('reviewed').checked=false;history.push(before);if(history.length>30)history.shift();future=[];pending=null;draw();}catch(e){d=before;msg(e.message);}}
function commitInputs(){
 const next=clone(d);next.name=$('name').value;next.width=Number($('width').value);next.height=Number($('height').value);next.background=$('background').value;next.watermark=attributionRequired!==false||$('attribution').checked;
 for(const key of ['strategy','copy','seo'])next.sections[key]=$(key).value;
 const l=next.layers.find(x=>x.id===selected);
 if(l)for(const input of $('properties').elements){if(!input.name)continue;const key=input.name;l[key]=key==='bold'?input.checked:typeof l[key]==='number'?Number(input.value):input.value;}
 validateDocument(next);if(JSON.stringify(next)!==JSON.stringify(d)){remember();d=next;}draw();
}
function draw(){
 $('attribution').checked=attributionRequired!==false||d.watermark;$('name').value=d.name;$('width').value=d.width;$('height').value=d.height;$('background').value=d.background;
 for(const k of ['strategy','copy','seo'])$(k).value=d.sections[k];
 $('stage').classList.toggle('zoomed',$('zoom').value!=='fit');$('stage').style.width=$('zoom').value==='fit'?'100%':(d.width*Number($('zoom').value)/100)+'px';
 $('stage').innerHTML=renderDocument({...d,watermark:attributionRequired!==false||d.watermark});
 const active=layer();if(active){const rect=document.createElementNS('http://www.w3.org/2000/svg','rect');for(const key of ['x','y','width','height'])rect.setAttribute(key,active[key]);rect.setAttribute('fill','none');rect.setAttribute('stroke','#9360ed');rect.setAttribute('stroke-width','3');rect.setAttribute('stroke-dasharray','7 5');rect.setAttribute('data-selection','true');rect.setAttribute('transform',`rotate(${active.rotation} ${active.x+active.width/2} ${active.y+active.height/2})`);$('stage').firstElementChild.append(rect);}
$('layers').replaceChildren();
 for(const l of d.layers){const li=document.createElement('li'),b=document.createElement('button');b.textContent=l.type+(l.type==='text'?' · '+l.text.slice(0,25):'');b.setAttribute('aria-pressed',String(l.id===selected));b.onclick=()=>{try{commitInputs();selected=l.id;draw();}catch(e){msg(e.message);}};li.append(b);$('layers').append(li);}
 const form=$('properties');form.replaceChildren();const l=layer();if(!l){form.textContent='Select a layer to edit.';setBusy(busy);return;}
 const fields=['x','y','width','height','rotation','opacity','fill',...(l.type==='text'?['text','fontSize','font','bold','align','direction']:l.type==='image'?['fit','anchor']:[])];
 for(const key of fields){const label=document.createElement('label');label.textContent=key;const choices={font:['sans-serif','serif','monospace'],align:['left','center','right'],direction:['ltr','rtl'],fit:['contain','crop'],anchor:['xMinYMin','xMidYMin','xMaxYMin','xMinYMid','xMidYMid','xMaxYMid','xMinYMax','xMidYMax','xMaxYMax']}[key];const input=choices?document.createElement('select'):key==='text'?document.createElement('textarea'):document.createElement('input');if(choices)for(const value of choices)input.append(new Option(value,value));input.name=key;input.id='prop-'+key;label.htmlFor=input.id;input.value=String(l[key]);if(typeof l[key]==='number'){input.type='number';input.step='any';}if(key==='fill')input.type='color';if(key==='bold'){input.type='checkbox';input.checked=l.bold;}form.append(label,input);}
 const apply=document.createElement('button');apply.textContent='Apply layer';form.append(apply);
 form.onsubmit=e=>{e.preventDefault();try{commitInputs();}catch(error){msg(error.message);}};setBusy(busy);
}
async function api(method='GET',body,path=''){const r=await fetch('/api/canvas'+path,{method,headers:{...headers,'Content-Type':'application/json'},...(body?{body:JSON.stringify(body)}:{}),cache:'no-store',signal:AbortSignal.timeout(30000)});const b=await r.json();if(!r.ok)throw Error(b.error||b.detail||'Canvas operation failed');return b;}
function setBusy(value){busy=value;for(const el of document.querySelectorAll('button,input,textarea,select'))el.disabled=value;$('attribution').disabled=value||attributionRequired!==false;}
async function refresh(){const b=await api();attributionRequired=b.attribution_required!==false;draw();$('projects').replaceChildren(new Option('Choose…',''));for(const row of b.projects)$('projects').append(new Option(row.name+' · v'+row.revision,row.id));$('projects').value=id||'';}
function load(b){d=validateDocument(b.document);id=b.id;revision=b.revision;history=[];future=[];pending=null;selected=null;$('reviewed').checked=false;$('versions').replaceChildren(new Option('Choose…',''));for(const v of b.versions||[])$('versions').append(new Option('Version '+v,String(v)));draw();msg('Opened version '+revision+'. Editing never calls an AI provider.');}
$('zoom').onchange=()=>{try{commitInputs();}catch(e){msg(e.message);}};
$('new').onclick=()=>{if(!confirm('Start a new canvas? Export or save existing edits first.'))return;epoch++;$('reviewed').checked=false;$('consent').checked=false;$('projects').value='';d=newDocument();id=null;revision=0;selected=null;history=[];future=[];pending=null;$('versions').replaceChildren(new Option('Choose…',''));draw();};
$('refresh').onclick=async()=>{try{commitInputs();setBusy(true);await refresh();}catch(e){msg(e.message);}finally{setBusy(false);}};
$('projects').onchange=async()=>{if(!$('projects').value)return;if(!confirm('Open saved project and discard unsaved changes?')){$('projects').value=id||'';return;}const seq=++epoch;setBusy(true);try{const b=await api('GET',null,'?id='+encodeURIComponent($('projects').value));if(seq===epoch)load(b);}catch(e){msg(e.message);}finally{if(seq===epoch)setBusy(false);}};
$('save').onclick=async()=>{if(!connected){msg('Not connected. Export editable JSON to keep your work.');return;}if(!$('consent').checked){msg('Confirm permission to store this content.');return;}try{commitInputs();const fingerprint=JSON.stringify({id,revision,document:d});if(pending?.fingerprint!==fingerprint)pending={fingerprint,request_id:crypto.randomUUID()};setBusy(true);const b=await api('POST',{id,revision,document:d,consent:true,request_id:pending.request_id});load(b);await refresh();msg('Saved version '+revision+'. No campaign allowance used.');}catch(e){msg(e.message+' Your local work remains. Retry unchanged after an uncertain response.');}finally{setBusy(false);}};
$('restore').onclick=async()=>{const v=Number($('versions').value);if(!id||!v||!confirm('Restore this saved version? Current saved work remains in history; unsaved edits are discarded.'))return;try{setBusy(true);load(await api('POST',{id,revision,restore:v,request_id:crypto.randomUUID(),consent:true}));await refresh();}catch(e){msg(e.message);}finally{setBusy(false);}};
$('delete').onclick=async()=>{if(!id||!confirm('Delete this saved project and its history? Downloaded copies are not recalled.'))return;try{commitInputs();setBusy(true);await api('DELETE',null,'?id='+id);id=null;revision=0;pending=null;await refresh();msg('Deleted saved project. Local canvas remains available to export.');}catch(e){msg(e.message);}finally{setBusy(false);}};
$('undo').onclick=()=>{if(history.length){future.push(clone(d));d=history.pop();pending=null;$('reviewed').checked=false;draw();}};$('redo').onclick=()=>{if(future.length){history.push(clone(d));d=future.pop();pending=null;$('reviewed').checked=false;draw();}};
$('apply-document').onclick=()=>change(()=>{d.name=$('name').value;d.width=Number($('width').value);d.height=Number($('height').value);d.background=$('background').value;});
$('apply-sections').onclick=()=>change(()=>{for(const k of ['strategy','copy','seo'])d.sections[k]=$(k).value;});
for(const b of document.querySelectorAll('[data-add]'))b.onclick=()=>change(()=>{const type=b.dataset.add,l={id:crypto.randomUUID(),type,x:0,y:0,width:Math.min(300,d.width),height:Math.min(120,d.height),rotation:0,opacity:1,fill:'#142339',...(type==='text'?{text:'Edit this text',fontSize:Math.min(32,d.height/2),font:'sans-serif',bold:false,align:'left',direction:'ltr'}:{})};d.layers.push(l);selected=l.id;});
$('remove').onclick=()=>change(()=>{d.layers=d.layers.filter(l=>l.id!==selected);selected=null;});
$('duplicate').onclick=()=>change(()=>{if(layer()){const l=clone(layer());l.id=crypto.randomUUID();d.layers.push(l);selected=l.id;}});
for(const [key,delta]of [['back',-1],['front',1]])$(key).onclick=()=>change(()=>{const i=d.layers.findIndex(l=>l.id===selected),j=i+delta;if(i>=0&&j>=0&&j<d.layers.length)[d.layers[i],d.layers[j]]=[d.layers[j],d.layers[i]];});
$('image').onchange=async()=>{
 const file=$('image').files?.[0];if(!file)return;if(!$('image-rights').checked){msg('Confirm rights before preparing an image.');$('image').value='';return;}
 if(!['image/png','image/jpeg','image/svg+xml'].includes(file.type)||file.size>3000000){msg('Use PNG/JPEG/static SVG under 3 MB.');return;}
 const seq=++epoch;setBusy(true);let url;
 try{
  const {prepareReference}=await import('./import-image.js');const src=await prepareReference(file);
  if(seq!==epoch)return;if(src.length>450000)throw Error('Image remains too large. Choose a simpler image.');
  setBusy(false);change(()=>{if($('replace-image').checked){if(layer()?.type!=='image')throw Error('Select an image layer to replace.');layer().src=src;}else{const l={id:crypto.randomUUID(),type:'image',src,fit:'contain',anchor:'xMidYMid',x:0,y:0,width:Math.min(400,d.width),height:Math.min(300,d.height),rotation:0,fill:'#ffffff',opacity:1};d.layers.push(l);selected=l.id;}});$('image-rights').checked=false;
 }catch(e){msg(e.message);}finally{if(url)URL.revokeObjectURL(url);$('image').value='';setBusy(false);}
};
$('import').onchange=async()=>{const f=$('import').files?.[0];if(!f)return;const seq=++epoch;setBusy(true);try{if(f.size>LIMIT)throw Error('Editable JSON exceeds 1 MB.');const doc=validateDocument(JSON.parse(await f.text()));if(seq!==epoch)return;if(!confirm('Open imported editable source? Export unsaved edits first. This does not restore account IDs or approvals.'))return;d=doc;id=null;revision=0;history=[];future=[];pending=null;selected=null;$('reviewed').checked=false;$('consent').checked=false;draw();$('projects').value='';$('versions').replaceChildren(new Option('Choose…',''));msg('Imported locally, not uploaded. Save with permission or edit/export without a connection.');}catch(e){msg(e.message);}finally{if(seq===epoch)setBusy(false);}};
function download(blob,name){const url=URL.createObjectURL(blob),a=document.createElement('a');a.href=url;a.download=name;document.body.append(a);a.click();a.remove();setTimeout(()=>URL.revokeObjectURL(url),5000);}
$('export-json').onclick=()=>{try{commitInputs();download(new Blob([JSON.stringify(d)],{type:'application/json'}),'brandforge-editable.json');}catch(e){msg(e.message);}};
$('export-svg').onclick=()=>{try{commitInputs();if(!$('reviewed').checked)throw Error('Review the output at full size before exporting artwork.');download(new Blob([renderDocument(d)],{type:'image/svg+xml'}),'canvas.svg');}catch(e){msg(e.message);}};
$('export-png').onclick=async()=>{let url;try{commitInputs();if(!$('reviewed').checked){msg('Review the output at full size before exporting artwork.');return;}setBusy(true);url=URL.createObjectURL(new Blob([renderDocument(d)],{type:'image/svg+xml'}));const image=new Image();await new Promise((ok,no)=>{image.onload=ok;image.onerror=no;image.src=url;});const c=document.createElement('canvas'),scale=Math.min(1,2000/d.width,2000/d.height);c.width=Math.round(d.width*scale);c.height=Math.round(d.height*scale);c.getContext('2d').drawImage(image,0,0,c.width,c.height);const blob=await new Promise(ok=>c.toBlob(ok,'image/png'));if(!blob)throw Error('PNG encoding failed');download(blob,'canvas.png');msg('PNG exported at '+c.width+' × '+c.height+'. SVG retains document dimensions.');c.width=c.height=0;}catch{msg('PNG export failed; editable JSON and SVG remain available.');}finally{if(url)URL.revokeObjectURL(url);setBusy(false);}};
let drag=null;
$('stage').onpointerdown=e=>{if(!layer()||busy)return;const box=$('stage').getBoundingClientRect();drag={x:e.clientX,y:e.clientY,l:clone(layer()),sx:d.width/box.width,sy:d.height/box.height};$('stage').setPointerCapture(e.pointerId);};
$('stage').onpointermove=e=>{if(!drag)return;const rect=$('stage').querySelector('[data-selection]'),l=drag.l;if(rect){rect.setAttribute('x',Math.max(0,Math.min(d.width-l.width,l.x+(e.clientX-drag.x)*drag.sx)));rect.setAttribute('y',Math.max(0,Math.min(d.height-l.height,l.y+(e.clientY-drag.y)*drag.sy)));rect.setAttribute('transform',`rotate(${l.rotation} ${Number(rect.getAttribute('x'))+l.width/2} ${Number(rect.getAttribute('y'))+l.height/2})`);}};
$('stage').onpointerup=e=>{if(!drag)return;const initial=drag;drag=null;change(()=>{const l=layer();l.x=Math.max(0,Math.min(d.width-l.width,initial.l.x+(e.clientX-initial.x)*initial.sx));l.y=Math.max(0,Math.min(d.height-l.height,initial.l.y+(e.clientY-initial.y)*initial.sy));});};
$('stage').onpointercancel=()=>{drag=null;draw();};
$('stage').onkeydown=e=>{const move={ArrowLeft:[-1,0],ArrowRight:[1,0],ArrowUp:[0,-1],ArrowDown:[0,1]}[e.key];if(!move||!layer())return;e.preventDefault();change(()=>{const l=layer(),step=e.shiftKey?10:1;l.x=Math.max(0,Math.min(d.width-l.width,l.x+move[0]*step));l.y=Math.max(0,Math.min(d.height-l.height,l.y+move[1]*step));});};
try{const handoff=sessionStorage.getItem('bf-canvas-handoff');if(handoff){d=validateDocument(JSON.parse(handoff));sessionStorage.removeItem('bf-canvas-handoff');msg('Separate editable copy prepared; original files are unchanged.');}}catch(e){msg(e.message);}
if(matchMedia('(max-width:750px)').matches)$('file-actions').open=false;
draw();setBusy(true);
try{
 const r=await fetch('/api/session',{cache:'no-store',signal:AbortSignal.timeout(5000)});if(r.ok){const s=await r.json();if(s.capability)headers={'X-BrandForge-Token':s.capability};else throw Error('Not Desktop');}else throw Error('Not Desktop');
 connected=true;
}catch{
 try{const r=await fetch('/api/config',{cache:'no-store',signal:AbortSignal.timeout(5000)}),c=await r.json();const {createClient}=await import('/vendor/supabase.mjs'),sb=createClient(c.supabaseUrl,c.supabaseAnonKey),{data}=await sb.auth.getSession();if(!data.session)throw Error('Sign in through the workspace to save.');headers={Authorization:'Bearer '+data.session.access_token};connected=true;const owner=data.session.user?.id;sb.auth.onAuthStateChange?.((_event,session)=>{if(!session||session.user?.id!==owner){connected=false;headers={};msg('The sign-in changed. Save is disabled; keep authorized local work as editable JSON and reload to reconnect.');}else{headers={Authorization:'Bearer '+session.access_token};connected=true;}});}catch(e){msg(e.message+' Local editing and JSON export still work.');}
}
if(connected)try{await refresh();msg('Ready. Saving is private; editable JSON transfers between Cloud and Desktop.');}catch(e){msg(e.message+' Local editing/export still work.');}

setBusy(false);
