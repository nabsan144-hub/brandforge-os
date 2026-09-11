import {fileBytes,saveBlob,rasterize,campaignZip,normalizedLogo} from '/workspace-tools.js';
// Supabase config — Vercel env vars are injected at build time via window env,
// or paste your project values here for local runs.
// supabase-js is VENDORED (cloud/public/vendor/supabase.mjs) instead of loaded
// from a third-party CDN, so the login page cannot break if that CDN is
// unreachable. The vendor bundle also pairs with a tightened CSP.
import { createClient } from "/vendor/supabase.mjs";
// Top-level fetch MUST be resilient: a 404 or non-JSON /api/config response
// used to throw at import time and leave a blank page with no explanation.
async function startWorkspace(){
let __cfg = null;
try {
  const __r = await fetch("/api/config", { cache: "no-store" });
  if (__r.ok) __cfg = await __r.json();
} catch (e) { __cfg = null; }
// Domain-agnostic: store marketing URL from config for pricing links
window.__bfMarketingUrl = (__cfg && __cfg.marketingUrl) ? __cfg.marketingUrl.replace(/\/+$/, '') : 'https://brandforge-os.com';
function updatePricingLinks(){
  var marketing = window.__bfMarketingUrl || 'https://brandforge-os.com';
  // If marketingUrl is same as app origin or empty, try to use relative sales path if exists, else keep marketing
  // For true domain-agnostic: if on a preview host and marketing is default prod, use current origin + /pricing.html? No, pricing is sales site, not cloud.
  // So keep marketingUrl as is — operator sets BRANDFORGE_MARKETING_URL to any domain (preview host, custom, etc)
  document.querySelectorAll('[data-pricing-link]').forEach(function(a){
    try {
      // If marketingUrl is set to any domain (including a preview host), use it
      if (marketing && marketing.indexOf('YOUR')===-1) {
        // Marketing site serves clean URLs (Vercel cleanUrls) — /pricing, not /pricing.html.
        a.setAttribute('href', marketing + '/pricing');
      }
    } catch(e) {}
  });
}

if (!__cfg || !__cfg.supabaseUrl || !__cfg.supabaseAnonKey) {
  document.body.innerHTML = '<div style="padding:40px;font-family:system-ui;color:#F8FAFC;max-width:560px;margin:auto;text-align:center"><h2 style="margin-bottom:8px">BrandForge Cloud — temporarily unavailable</h2><p style="color:#94A3B8;line-height:1.6">Please try again later or contact support@brandforge-os.com. No payment was started.</p></div>';
  return; // friendly unavailable screen; no unhandled module rejection
}
const sb = createClient(__cfg.supabaseUrl, __cfg.supabaseAnonKey);
// Initialize marketing URL from config (domain-agnostic)
window.__bfMarketingUrl = (__cfg.marketingUrl || 'https://brandforge-os.com').replace(/\/+$/, '');
setTimeout(updatePricingLinks, 100);

const $ = (id) => document.getElementById(id);
let mode = "login";
let currentSession = null;
let sessionLoaded = false;
// P0.2 — route the right auth tab from the URL so marketing "Start free"
// lands on the signup form (never the dead sign-in default), and so Enter
// submits the auth form. Mirrors hosted/web behavior.
function setAuthMode(next) {
  mode = (next === "signup" || next === "forgot") ? next : "login";
  const t = next === "signup" ? $("tab-signup") : next === "forgot" ? $("tab-forgot") : $("tab-login");
  ["tab-login", "tab-signup", "tab-forgot"].forEach((id) => { const el = $(id); if (el) el.classList.toggle("on", id === (t && t.id)); });
  const pw = $("auth-pass-wrap"); if (pw) pw.classList.toggle("hidden", mode === "forgot");
  setPass2Visible(mode === "signup");
  setPassAutocomplete(mode === "signup" ? "new-password" : "current-password");
  updatePassHint();
  const go = $("auth-go"); if (go) go.textContent = mode === "signup" ? "Start free" : mode === "forgot" ? "Send reset link" : "Sign in";
  const rw = $("resend-wrap"); if (rw) rw.style.display = "none";
}
function authModeFromLocation() {
  const p = location.pathname.replace(/\/+$/, "");
  if (/\/signup$/.test(p)) return "signup";
  if (/\/forgot(-password)?$/.test(p) || /\/reset$/.test(p)) return "forgot";
  if (/\/login$/.test(p)) return "login";
  const q = new URLSearchParams(location.search).get("tab");
  return q === "signup" || q === "login" || q === "forgot" ? q : "login";
}
const _authForm = $("auth-form");
if (_authForm) _authForm.addEventListener("submit", (e) => { e.preventDefault(); const b = $("auth-go"); if (b) b.click(); });
// Supabase refreshes an access token in the background. Keep the request helper
// on the refreshed token instead of letting one-hour JWT expiry silently turn
// every dashboard poll into a 401.
sb.auth.onAuthStateChange((event, nextSession) => {
  const priorUser=currentSession?.user?.id;
  currentSession = nextSession || null;
  if(event==='SIGNED_OUT'||(event==='SIGNED_IN'&&priorUser&&priorUser!==nextSession?.user?.id)){
    location.replace(event==='SIGNED_OUT'?'/login':'/app');
    return;
  }
  sessionLoaded = true;
  if (event === "SIGNED_OUT") {
    $("nav-logout")?.classList.add("hidden");
  }
  if (event === "PASSWORD_RECOVERY") {
    // User arrived from a Supabase recovery email — show the
    // set-new-password screen instead of the dashboard. (bug §2.1)
    passwordRecoveryPending = true;
    show("reset");
    $("nav-logout")?.classList.add("hidden");
    history.replaceState(null, "", "/");
  }
});

let passwordRecoveryPending = false;

function show(view) {
  $("view-auth").classList.toggle("hidden", view !== "auth");
  $("view-app").classList.toggle("hidden", !["app", "billing"].includes(view));
  $("view-app").classList.toggle("billing-mode", view === "billing");
  $("view-billing").classList.toggle("hidden", view !== "billing");
  const reset = $("view-reset");
  if (reset) reset.classList.toggle("hidden", view !== "reset");
}

async function session() {
  if (sessionLoaded) return currentSession;
  const { data } = await sb.auth.getSession();
  currentSession = data.session || null;
  sessionLoaded = true;
  return currentSession;
}

async function api(path, opts = {}) {
  const s = await session();
  const r = await fetch("/api" + path, {
    ...opts,
    headers: { "Content-Type": "application/json", Authorization: `Bearer ${s?.access_token || ""}`, ...(opts.headers || {}) },
  });
  return r;
}

async function boot() {
  // Recovery flow takes precedence — never override the set-password screen
  if (passwordRecoveryPending) { show("reset"); return; }
  const s = await session();
  if (passwordRecoveryPending) { show("reset"); return; }
  if (!s) { show("auth"); setAuthMode(authModeFromLocation()); return; }
  show("app");
  $("nav-logout").classList.remove("hidden");
  const r = await api("/me").catch(() => null);
  if (!r || !r.ok) {
    // Expired/invalid session: sign out locally and show the auth screen
    // instead of rendering a broken workspace with "FREE" placeholders.
    if (r?.status === 401) {
      await sb.auth.signOut(); $('nav-logout').classList.add('hidden'); show('auth');
    } else {
      $('app-usage').textContent='Your account is temporarily unavailable. Your sign-in has been kept; reload to retry.';
    }
    return;
  }
  const me = await r.json();
  window.__bfMe = me;
  $("nav-plan").textContent = (me.plan || "free").toUpperCase();
  // Plan-aware banner-size UI: preset quota per plan (Free 1 · Pro 10 ·
  // Agency 21), arbitrary custom size fields only where the plan allows.
  try {
    const L = me.limits || {};
    const quota = (typeof L.custom_presets === "number") ? L.custom_presets : 21;
    const allowAny = !!L.custom_any;
    const sel = $("c-preset"), lbl = $("c-sizes-label"), customWrap = $("c-custom-wrap");
    if (lbl) lbl.textContent = `Banner sizes — your plan includes up to ${quota} preset${quota === 1 ? "" : "s"} per run${allowAny ? " + arbitrary custom sizes" : ""}`;
    if (sel && __cfg && __cfg.adSizes) {
      const keys = Object.keys(__cfg.adSizes);
      const autoN = Math.min(quota, keys.length);
      // Touch-friendly chip/checkbox picker — replaces the native multi-select,
      // which needs Ctrl/Cmd and is unusable on phones (audit §2.4). Empty
      // selection = Auto (full plan set); quota cap is enforced like before.
      sel.classList.add("chip-grid");
      sel.innerHTML = "";
      const makeChip = (text, value) => {
        const lab = document.createElement("label");
        lab.className = "chip";
        const box = document.createElement("input");
        box.type = "checkbox"; box.value = value;
        const span = document.createElement("span"); span.textContent = text;
        lab.appendChild(box); lab.appendChild(span);
        sel.appendChild(lab);
        return box;
      };
      makeChip(`Auto — ${autoN} preset${autoN === 1 ? "" : "s"} from my plan`, "");
      keys.forEach((k) => {
        const [w, h, label] = __cfg.adSizes[k];
        makeChip(`${label} — ${w}×${h}`, k);
      });
      const boxes = () => [...sel.querySelectorAll("input[type=checkbox]")];
      const updatePresetUI = () => {
        const all = boxes();
        let realPicked = all.filter((b) => b.checked && b.value);
        // Cap at plan quota (newest picks win).
        if (realPicked.length > quota) realPicked.slice(0, realPicked.length - quota).forEach((b) => { b.checked = false; });
        const now = all.filter((b) => b.checked && b.value);
        const autoBox = all.find((b) => b.value === "");
        // "Auto" (full set) and specific sizes are mutually exclusive.
        if (autoBox) {
          if (autoBox.checked && now.length > 0) autoBox.checked = false;
          autoBox.disabled = now.length > 0;
        }
        all.forEach((b) => { const lab = b.closest("label"); if (lab) lab.classList.toggle("on", b.checked && !!b.value); });
        if (lbl) {
          lbl.textContent = now.length
            ? `Banner sizes — ${now.length}/${quota} selected (empty = Auto full set)`
            : `Banner sizes — your plan includes up to ${quota} preset${quota === 1 ? "" : "s"} per run${allowAny ? " + arbitrary custom sizes" : ""}`;
        }
      };
      boxes().forEach((b) => { b.addEventListener("change", updatePresetUI); });
      updatePresetUI();
    }
    if (customWrap) customWrap.classList.toggle("hidden", !allowAny);
  } catch {}
  // customData.user_id for Paddle checkout must be the Supabase account id.
  // (me.js doesn't return it, and there is no `user` variable here — using the
  // session object which always carries the auth user.)
  window.__bfUserId = (s && s.user && s.user.id) || me.id || "";
  const L = me.limits || {}, U = me.usage || {};
  $("app-usage").textContent = L.lifetime != null
    ? `Free plan — ${U.campaigns_lifetime}/${L.lifetime} campaigns used · watermarked`
    : `${me.plan} — ${U.campaigns_this_month}${L.monthly ? "/" + L.monthly : ""} campaigns this month`;
  try { const saved = localStorage.getItem("brandforge-lang"); if (saved && $("c-lang")) $("c-lang").value = saved; } catch {}
  await loadCampaigns();
  loadKeys();
  await loadBrands();
  updatePricingLinks();
  if(autoShowPlan){autoShowPlan=false;show("billing");await loadBilling();}
  // Campaign deep-link (bug §2.2 + §6.3): /app/c/<id> opens that campaign —
  // the WhatsApp-delivery link shares exactly this URL shape, and refreshing
  // with a campaign open restores it instead of losing your place.
  const m = location.pathname.match(/^\/app\/c\/([A-Za-z0-9_-]+)\/?$/);
  if (m) openCampaign(decodeURIComponent(m[1]), { replace: true });
}

async function refreshAccountSummary() {
  const r = await api("/me").catch(() => null);
  if (!r || !r.ok) return;
  const me = await r.json().catch(() => null);
  if (!me) return;
  window.__bfMe = me;
  $('c-custom-wrap').classList.toggle('hidden',!me.limits?.custom_any);
  $("nav-plan").textContent = (me.plan || "free").toUpperCase();
  const L = me.limits || {}, U = me.usage || {};
  $("app-usage").textContent = L.lifetime != null
    ? `Free plan — ${U.campaigns_lifetime}/${L.lifetime} campaigns used · watermarked`
    : `${me.plan} — ${U.campaigns_this_month}${L.monthly ? "/" + L.monthly : ""} campaigns this month`;
}

let historyPage=0,historySearch='',historyRequest=0;
async function requestJSON(path,opts={}){const r=await api(path,opts);const d=await r.json().catch(()=>({}));if(!r.ok)throw Object.assign(new Error(d.error||'Request could not be completed.'),{code:d.code,status:r.status,retryWithNewRequest:d.retry_with_new_request});return d;}
async function loadCampaigns(){
 const request=++historyRequest;
 try{const d=await requestJSON(`/campaigns?page=${historyPage}&q=${encodeURIComponent(historySearch)}`);if(request!==historyRequest)return;
  $('camp-list').innerHTML=(d.campaigns||[]).map(c=>`<button type="button" class="row" data-id="${esc(c.id)}"><span style="flex:1;min-width:0"><b>${esc(c.name)}</b><br><span class="help">${esc(c.product)} · ${esc((c.created_at||'').slice(0,10))}</span></span><span class="badge">${esc(c.provider==='mixed'?'Mixed':c.provider==='offline'?'Draft':(c.provider==='groq'||c.provider==='gemini')?'AI':c.provider)}</span></button>`).join('')||'<p class="help">No matching campaigns. Start with a specific brief.</p>';
  $('camp-list').querySelectorAll('[data-id]').forEach(b=>b.onclick=()=>openCampaign(b.dataset.id));
  $('history-page').textContent=`Page ${historyPage+1} · ${d.total||0} campaign${d.total===1?'':'s'}`;$('history-prev').disabled=historyPage===0;$('history-next').disabled=!d.has_more;
 }catch(e){$('camp-list').innerHTML=`<p class="err">${esc(e.message)}</p>`;}
}
$('history-search').onsubmit=e=>{e.preventDefault();historySearch=$('history-query').value.trim();historyPage=0;loadCampaigns();};
$('history-prev').onclick=()=>{if(historyPage){historyPage--;loadCampaigns();}};
$('history-next').onclick=()=>{historyPage++;loadCampaigns();};

let activeSection='strategy',editing=false;
function renderTab(section){
 if(!current)return;
 if(editing&&!confirm('Discard unsaved section edits?'))return;
 editing=false;activeSection=section;revokeBlobs();const el=$('d-body');el.innerHTML='';
 const textSection=['strategy','copy','seo'].includes(section);
 $('d-edit').disabled=!textSection;$('d-copy').disabled=!textSection;
 document.querySelectorAll('#detail .tabs button').forEach(b=>{b.classList.toggle('on',b.dataset.t===section);b.setAttribute('aria-pressed',String(b.dataset.t===section));});
 if(textSection){const pre=document.createElement('pre');pre.textContent=current[section]||'—';pre.tabIndex=0;pre.dir=current.lang==='ur'?'rtl':'auto';pre.setAttribute('aria-label',section+' draft');el.append(pre);return;}
 for(const f of current.files||[]){
  const row=document.createElement('div');row.className='action-row';const label=document.createElement('span');label.className='help';label.textContent=f.name;row.append(label);
  const dl=document.createElement('button');dl.className='btn ghost';dl.textContent='Download source';dl.onclick=()=>downloadFile(f);row.append(dl);
  if(f.name.endsWith('.svg'))for(const [title,mime,ext] of [['PNG','image/png','.png'],['JPEG','image/jpeg','.jpg']]){
   const button=document.createElement('button');button.className='btn ghost';button.textContent=title;button.onclick=async()=>{button.disabled=true;try{saveBlob(await rasterize(f,mime),f.name.replace(/\.svg$/,ext));}catch(e){$('d-action-msg').textContent=e.message;}finally{button.disabled=false;}};row.append(button);
  }
  el.append(row);
  if(/\.(svg|png|jpe?g)$/.test(f.name)){
   const img=document.createElement('img');img.className='file';img.alt=f.name;img.loading='lazy';const url=URL.createObjectURL(new Blob([fileBytes(f)],{type:f.name.endsWith('.svg')?'image/svg+xml':f.name.endsWith('.png')?'image/png':'image/jpeg'}));blobUrls.push(url);img.src=url;el.append(img);
  }
 }
}
function downloadFile(f){const type=f.name.endsWith('.svg')?'image/svg+xml':f.name.endsWith('.png')?'image/png':'text/plain;charset=utf-8';saveBlob(new Blob([fileBytes(f)],{type}),f.name.split('/').pop());}
function detailEnhancements(){
 if(!current)return;editing=false;
 const statuses=Object.entries(current.stage_status||{}).map(([k,s])=>`${k}: ${s.state}${s.provider?' ('+(s.provider==='offline'?'draft':'AI')+')':''}${s.reason?' — '+s.reason.replaceAll('_',' ').toLowerCase():''}`);
 $('d-stage-status').textContent=`Version ${current.revision||1}. ${statuses.join(' · ')}. Drafts require review; no live SEO score or platform approval.`;
 $('d-revisions').innerHTML='<option value="">Select a version</option>'+(current.revisions||[]).map(r=>`<option value="${r.revision}">Version ${r.revision} · ${esc(r.created_at.slice(0,10))}</option>`).join('');
 $('d-action-msg').textContent='';
}
$('d-copy').onclick=async()=>{if(!current)return;try{await navigator.clipboard.writeText(current[activeSection]||'');$('d-action-msg').textContent='Section copied.';}catch{$('d-action-msg').textContent='Clipboard access was blocked. Select and copy the text manually.';}};
$('d-edit').onclick=()=>{
 if(!current||activeSection==='files')return;editing=true;const section=activeSection,version=current.revision||1,el=$('d-body');el.innerHTML='';
 const label=document.createElement('label');label.htmlFor='section-editor';label.textContent='Edit '+section;const input=document.createElement('textarea');input.id='section-editor';input.maxLength=20000;input.value=current[section]||'';input.dir=current.lang==='ur'?'rtl':'auto';
 const notice=document.createElement('p');notice.className='help';notice.textContent='Saves a new text version. Visuals are unchanged; use Reuse brief to generate new visuals (one campaign).';
 const save=document.createElement('button');save.className='btn gold';save.textContent='Save new version';save.onclick=async()=>{save.disabled=true;try{await requestJSON('/campaigns/'+current.id,{method:'PATCH',body:JSON.stringify({revision:version,[section]:input.value})});editing=false;await openCampaign(current.id,{replace:true});renderTab(section);$('d-action-msg').textContent='Saved. Previous versions can be restored below.';}catch(e){$('d-action-msg').textContent=e.message;save.disabled=false;}};
 const cancel=document.createElement('button');cancel.className='btn ghost';cancel.textContent='Discard edits';cancel.onclick=()=>{editing=false;renderTab(section);};el.append(label,input,notice,save,cancel);input.focus();
};
$('d-restore').onclick=async()=>{if(!current||!$('d-revisions').value)return;if(!confirm('Restore this saved text as a new version? Visuals stay unchanged.'))return;try{await requestJSON('/campaigns/'+current.id,{method:'PATCH',body:JSON.stringify({revision:current.revision,restore_revision:Number($('d-revisions').value)})});await openCampaign(current.id,{replace:true});$('d-action-msg').textContent='Version restored.';}catch(e){$('d-action-msg').textContent=e.message;}};
$('d-zip').onclick=async()=>{if(!current)return;if(editing){$('d-action-msg').textContent='Save or discard your section edits before exporting.';return;}const button=$('d-zip'),campaign=current;button.disabled=true;try{const result=await campaignZip(campaign,m=>$('d-action-msg').textContent=m);saveBlob(result.blob,result.name);$('d-action-msg').textContent=result.warnings.length?`Source pack downloaded; ${result.warnings.length} raster conversions failed. See EXPORT-WARNINGS.txt.`:'Pack downloaded: copy, SVG/PNG visuals, review notes and SHA-256 manifest.';}catch(e){$('d-action-msg').textContent=e.message;}finally{button.disabled=false;}};

let brandLogo='',selectedBrand='';
const fieldMap={product_name:'c-product',industry:'c-ind',audience:'c-aud',benefits:'c-ben',offer:'c-offer',cta:'c-cta',url:'c-url',tone:'c-tone',proof:'c-proof',avoided:'c-avoided',primary_color:'c-primary',secondary_color:'c-secondary',lang:'c-lang'};
function briefFields(){return {...Object.fromEntries(Object.entries(fieldMap).map(([key,id])=>[key,$(id).value])),logo:brandLogo,brand_id:selectedBrand||null,provider:$('c-provider').value,generate_new_logo:$('c-new-logo').checked};}
function setBrief(data){
 selectedBrand=data.brand_id||'';
 if(![...$('c-brand').options].some(o=>o.value===selectedBrand))selectedBrand='';
 $('c-brand').value=selectedBrand;$('brand-delete').classList.toggle('hidden',!selectedBrand);
 const normalized={...data,product_name:data.product_name||data.product||'',primary_color:data.primary_color||data.primary||'#E8B54A',secondary_color:data.secondary_color||data.secondary||'#0F172A',lang:data.lang||'en'};
 for(const [key,id]of Object.entries(fieldMap))$(id).value=normalized[key]||'';
 brandLogo=data.logo||'';showLogo();
}
function showLogo(){$('logo-preview').classList.toggle('hidden',!brandLogo);$('logo-clear').classList.toggle('hidden',!brandLogo);if(brandLogo)$('logo-preview').src=brandLogo;else $('logo-preview').removeAttribute('src');}
async function loadBrands(){try{const {brands}=await requestJSON('/brands');$('c-brand').innerHTML='<option value="">New / unsaved brand</option>'+brands.map(b=>`<option value="${esc(b.id)}">${esc(b.name)}</option>`).join('');$('c-brand').value=selectedBrand;$('brand-delete').classList.toggle('hidden',!selectedBrand);}catch(e){$('brand-msg').textContent=e.message;}}
$('c-brand').onchange=async()=>{selectedBrand=$('c-brand').value;$('brand-delete').classList.toggle('hidden',!selectedBrand);if(!selectedBrand){setBrief({});return;}try{const b=await requestJSON('/brands?id='+encodeURIComponent(selectedBrand));setBrief({...b.data,brand_id:b.id});$('brand-msg').textContent='Brand loaded. Set the campaign-specific offer, then generate.';}catch(e){$('brand-msg').textContent=e.message;}};
$('brand-save').onclick=async()=>{const b=$('brand-save');b.disabled=true;try{const d=await requestJSON('/brands',{method:'POST',body:JSON.stringify({...briefFields(),id:selectedBrand||null,name:$('c-product').value})});selectedBrand=d.id;await loadBrands();$('brand-msg').textContent='Brand saved. Stored only in your account.';}catch(e){$('brand-msg').textContent=e.message;}finally{b.disabled=false;}};
$('brand-delete').onclick=async()=>{if(!selectedBrand||!confirm('Remove this saved brand? Existing campaigns are kept.'))return;try{await requestJSON('/brands',{method:'DELETE',body:JSON.stringify({id:selectedBrand})});selectedBrand='';await loadBrands();$('brand-msg').textContent='Saved brand removed.';}catch(e){$('brand-msg').textContent=e.message;}};
$('c-logo').onchange=async()=>{try{const file=$('c-logo').files?.[0];if(file){brandLogo=await normalizedLogo(file);showLogo();$('brand-msg').textContent='Logo prepared locally. Save brand or generate to upload it.';}}catch(e){$('brand-msg').textContent=e.message;}};
$('logo-clear').onclick=()=>{brandLogo='';$('c-logo').value='';showLogo();};
$('d-duplicate').onclick=()=>{if(!current)return;setBrief(current.brief||current);$('c-name').value=current.name+' — new draft';show('app');$('c-product').focus();$('c-product').scrollIntoView({block:'center'});$('run-msg').textContent='Brief reused. Review the fields; generating a new pack uses one campaign.';};
let pendingGeneration=null;
$('c-go').onclick=async(event)=>{
 event.preventDefault();const button=$('c-go'),msg=$('run-msg');button.disabled=true;button.textContent='Generating…';msg.textContent='';
 try{
  const sizes=[...$('c-preset').querySelectorAll('input:checked')].filter(b=>b.value).map(b=>({preset:b.value}));
  const w=Number($('c-cw').value),h=Number($('c-ch').value);if(window.__bfMe?.limits?.custom_any&&(w||h))sizes.push({width:w,height:h});
  const payload={...briefFields(),name:$('c-name').value,custom_sizes:sizes,style:$('c-style').value},signature=JSON.stringify(payload);
  if(!pendingGeneration||pendingGeneration.signature!==signature)pendingGeneration={signature,id:crypto.randomUUID()};
  const data=await requestJSON('/campaigns',{method:'POST',headers:{'Idempotency-Key':pendingGeneration.id},body:signature});pendingGeneration=null;
  msg.className='ok';msg.textContent=data.replayed?'Existing completed request found; opening its pack.':`Pack saved — ${data.provider&&data.provider!=='offline'?'AI draft':'draft'}. Review all sections before publishing.`;
  historyPage=0;await Promise.all([loadCampaigns(),refreshAccountSummary()]);if(data.id)await openCampaign(data.id);
 }catch(e){msg.className='err';msg.textContent=e.message;
  // An exhausted allowance is the highest-intent upgrade moment: offer the
  // plan review immediately instead of a dead-end error line.
  if(['LIMIT_LIFETIME','LIMIT_MONTHLY'].includes(e.code)){const cta=document.createElement('button');cta.type='button';cta.className='btn gold';cta.style.marginLeft='10px';cta.textContent='Review paid plans →';cta.onclick=()=>$('nav-billing').click();msg.append(' ');msg.append(cta);}
  if(e.retryWithNewRequest||['ALREADY_FAILED','CAMPAIGN_DELETED','IDEMPOTENCY_CONFLICT'].includes(e.code))pendingGeneration=null;}
 finally{button.disabled=false;button.textContent='Create My Campaign →';}
};
$('feedback-send').onclick=async()=>{const b=$('feedback-send');b.disabled=true;try{await requestJSON('/feedback',{method:'POST',body:JSON.stringify({campaign_id:current?.id,usable:$('feedback-usable').value==='yes',minutes_saved:$('feedback-minutes').value?Number($('feedback-minutes').value):null,note:$('feedback-note').value})});$('feedback-msg').textContent='Thank you. Your feedback went straight to the team.';}catch(e){$('feedback-msg').textContent=e.message;}finally{b.disabled=false;}};
let exportPage=0;
$('account-export').onclick=async()=>{
 const b=$('account-export');b.disabled=true;
 try{const r=await api('/me/export?page='+exportPage);if(!r.ok)throw new Error((await r.json()).error||'Export failed');const d=await r.json();saveBlob(new Blob([JSON.stringify(d,null,2)],{type:'application/json'}),`brandforge-account-part-${exportPage+1}.json`);
  exportPage=d.next_page??0;b.textContent=d.has_more?'Download next data part':'Export account data';$('account-export-msg').textContent=d.has_more?`Part ${d.page+1} downloaded. More data remains; click again for the next part. Files are included. Secrets are excluded.`:'All account data parts downloaded. Paddle invoices are available in Manage billing.';
 }catch(e){$('account-export-msg').textContent=e.message;}finally{b.disabled=false;}
};


function esc(s) { return String(s ?? "").replace(/[&<>"]/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c])); }

let current = null;
let openRequest = 0;
async function openCampaign(id, opts = {}) {
  if(editing&&!confirm("Discard unsaved section edits?"))return;
  editing=false;
  const requestId = ++openRequest;
  current = null;
  const rf = await api("/campaigns/" + encodeURIComponent(id)).catch(() => null);
  if (requestId !== openRequest) return;
  const loaded = rf && rf.ok ? await rf.json() : null;
  if(requestId !== openRequest) return;
  current = loaded;
  if (!current) { if (location.pathname.startsWith("/app/c/")) history.replaceState(null, "", "/"); return; }
  // Reflect the open campaign in the URL so it is shareable/bookmarkable and
  // survives refresh; use replace() when arriving from a deep link so the
  // back button does not re-trigger the same open.
  const url = "/app/c/" + encodeURIComponent(current.id);
  if (location.pathname !== url) {
    if (opts.replace) history.replaceState({ cid: current.id }, "", url);
    else history.pushState({ cid: current.id }, "", url);
  } else {
    history.replaceState({ cid: current.id }, "", url);
  }
  $("detail").classList.remove("hidden");
  $("d-name").textContent = current.name;
  // WhatsApp delivery is a storefront-promised Agency feature (pricing.html:
  // "Optional WhatsApp workspace reminders"). Only show it to Agency-tier plans;
  // the server enforces the same gate. (`window.__bfMe?.plan` is set in boot().)
  const deliveryTier = String(window.__bfMe?.plan || "").toLowerCase() === "agency" && !!__cfg.whatsappEnabled;
  $("d-deliver").style.display = deliveryTier ? "inline-flex" : "none";
  // The phone field is part of the WhatsApp-delivery control, so only show it
  // to tiers that can actually send (hiding it avoided a confusing lone field
  // for Free/Pro users whose button was already hidden).
  $("d-phone").style.display = deliveryTier ? "inline-block" : "none";
  $("d-phone-label").style.display = deliveryTier ? "block" : "none";
  if (!deliveryTier) $("d-deliver-msg").textContent = "WhatsApp workspace reminders are on Agency.";
  else $("d-deliver-msg").textContent = "Personal reminder link — requires your Cloud login, not a public client share.";
  try { if (localStorage.getItem("brandforge-phone")) $("d-phone").value = localStorage.getItem("brandforge-phone"); } catch {}
  $("d-provider").textContent = current.provider === "groq" ? "AI (Groq)" : current.provider === "gemini" ? "AI (Gemini)" : current.provider === "mixed" ? "Mixed — review stage status" : "Draft pack (offline)";
  $("d-back").onclick = () => { if(editing&&!confirm("Discard unsaved section edits?"))return;editing=false;revokeBlobs(); openRequest += 1; current = null; $("detail").classList.add("hidden"); history.pushState({}, "", "/"); };
  // P0.5 — delete the campaign (owner-scoped server route) and refresh the list.
  const delBtn = $("d-delete");
  if (delBtn) delBtn.onclick = async () => {
    if (!current) return;
    if (!confirm("Delete this campaign and its saved versions? This cannot be undone. Completed generation usage is not refunded.")) return;
    delBtn.disabled = true; delBtn.textContent = "Deleting…";
    try {
      const r = await api("/campaigns/" + encodeURIComponent(current.id), { method: "DELETE" }).catch(() => null);
      if (!r || !r.ok) { delBtn.disabled = false; delBtn.textContent = "Delete"; alert("Could not delete campaign."); return; }
      revokeBlobs(); openRequest += 1; current = null; $("detail").classList.add("hidden"); history.pushState({}, "", "/");
      await loadCampaigns();
      await refreshAccountSummary();
    } catch { delBtn.disabled = false; delBtn.textContent = "Delete"; alert("Could not delete campaign."); }
  };
  detailEnhancements();
  renderTab("strategy");
  document.querySelectorAll("#detail .tabs button").forEach((b) => {
    b.onclick = () => { document.querySelectorAll("#detail .tabs button").forEach((x) => x.classList.remove("on")); b.classList.add("on"); renderTab(b.dataset.t); };
  });
  $("detail").scrollIntoView({ behavior: matchMedia("(prefers-reduced-motion: reduce)").matches ? "auto" : "smooth", block:"start" });
}

// Blob URLs created for stored-SVG previews must be tracked and revoked or
// every "Files" tab render leaks one object URL per SVG. (The declarations
// were dropped in an earlier toolbar refactor — clicking Files threw
// ReferenceError on revokeBlobs until this fix.)
const blobUrls = [];
function revokeBlobs() {
  while (blobUrls.length) {
    try { URL.revokeObjectURL(blobUrls.pop()); } catch {}
  }
}

// ---- auth handlers ----
// Map common Supabase auth errors to clear, human copy (audit §2.6). Returns
// a friendly string, or null to fall back to the raw provider message.
function friendlyAuthError(msg) {
  const m = String(msg || "").toLowerCase();
  if (/invalid login credentials|invalid email or password/i.test(m)) return "We couldn't match that email and password. Try again, or use Reset to set a new password.";
  if (/email not confirmed/i.test(m)) return "That email isn't confirmed yet — check your inbox for the confirmation link, or use the Resend button below.";
  if (/user already registered/i.test(m)) return "An account already exists for that email. Go to Sign in, or use Reset if you forgot your password.";
  if (/rate limit|too many|throttl/i.test(m)) return "Too many attempts from this device — wait a moment and try again.";
  if (/password should be at least/i.test(m)) return "Password must be at least 8 characters.";
  return null;
}
// Inline password feedback as the user types (audit §2.5).
function updatePassHint() {
  const hint = $("auth-pass-hint");
  if (!hint) return;
  const v = ($("auth-pass") && $("auth-pass").value) || "";
  const v2 = ($("auth-pass2") && $("auth-pass2").value) || "";
  if (!v) { hint.textContent = "At least 8 characters."; return; }
  if (v.length < 8) { hint.textContent = `${v.length}/8 characters — keep going.`; return; }
  if (mode === "signup" && v2 && v2 !== v) { hint.textContent = "Your passwords don't match yet."; return; }
  hint.textContent = "Looks good — 8+ characters" + (mode === "signup" ? " and both fields match." : ".");
}
function setPassAutocomplete(ac) { const p = $("auth-pass"); if (p) p.autocomplete = ac; }
function setPass2Visible(visible) { const w = $("auth-pass2-wrap"); const p2 = $("auth-pass2"); if (w) w.classList.toggle("hidden", !visible); if (p2 && !visible) p2.value = ""; }
$("tab-login").onclick = () => { $("resend-wrap").style.display = "none"; mode = "login"; $("tab-login").classList.add("on"); $("tab-signup").classList.remove("on"); $("tab-forgot").classList.remove("on"); $("auth-pass-wrap").classList.remove("hidden"); setPass2Visible(false); setPassAutocomplete("current-password"); updatePassHint(); $("auth-go").textContent = "Sign in"; };
$("tab-signup").onclick = () => { $("resend-wrap").style.display = "none"; mode = "signup"; $("tab-signup").classList.add("on"); $("tab-login").classList.remove("on"); $("tab-forgot").classList.remove("on"); $("auth-pass-wrap").classList.remove("hidden"); setPass2Visible(true); setPassAutocomplete("new-password"); updatePassHint(); $("auth-go").textContent = "Start free"; };
$("tab-forgot").onclick = () => { $("resend-wrap").style.display = "none"; mode = "forgot"; $("tab-forgot").classList.add("on"); $("tab-login").classList.remove("on"); $("tab-signup").classList.remove("on"); $("auth-pass-wrap").classList.add("hidden"); setPass2Visible(false); setPassAutocomplete("current-password"); updatePassHint(); $("auth-go").textContent = "Send reset link"; };
const _passEl = $("auth-pass"); if (_passEl) _passEl.addEventListener("input", updatePassHint);
const _pass2El = $("auth-pass2"); if (_pass2El) _pass2El.addEventListener("input", updatePassHint);
// ---- optional Cloudflare Turnstile (SEC-2) ----
// Strictly opt-in: only when the operator sets CAPTCHA_SITE_KEY (served via
// /api/config). With no key this is a no-op — signup/login behave exactly as
// before, no third-party script loads, no challenge is enforced. When a key is
// present, we load Turnstile, render an implicit widget in the auth form, and
// pass the resulting token to Supabase Auth (which requires the matching
// provider secret to be enabled on the project).
function loadTurnstile() {
  return new Promise((resolve) => {
    if (window.turnstile) return resolve(window.turnstile);
    const s = document.createElement("script");
    s.src = "https://challenges.cloudflare.com/turnstile/v0/api.js?render=explicit";
    s.async = true;
    s.onload = () => resolve(window.turnstile || null);
    s.onerror = () => resolve(null);
    document.head.appendChild(s);
  });
}
async function getCaptchaToken() {
  const key = __cfg && __cfg.captchaSiteKey;
  if (!key) return null;
  const ts = await loadTurnstile();
  if (!ts) return null; // provider unreachable -> caller fails closed when a key is configured
  return new Promise((resolve) => {
    let target = document.getElementById("bf-captcha");
    if (!target) {
      target = document.createElement("div");
      target.id = "bf-captcha";
      target.style.cssText = "margin:10px 0";
      const form = $("auth-form");
      if (!form) { resolve(null); return; }
      form.appendChild(target);
    }
    ts.render(target, {
      sitekey: key,
      callback: (token) => resolve(token),
      "expired-callback": () => resolve(null),
      "error-callback": () => resolve(null),
    });
  });
}
$("auth-go").onclick = async () => {
  const email = $("auth-email").value.trim(), password = $("auth-pass").value;
  const msg = $("auth-msg");
  const button = $("auth-go");
  msg.innerHTML = "";
  $("resend-wrap").style.display = "none";
  button.disabled = true;
  try {
    if (mode === "forgot") {
      if (!email) { msg.innerHTML = `<div class="err">Please enter your email</div>`; button.disabled = false; return; }
      const result = await sb.auth.resetPasswordForEmail(email, { redirectTo: window.location.origin });
      if (result.error) {
        const friendly = friendlyAuthError(result.error.message);
        msg.innerHTML = `<div class="err">${friendly ? esc(friendly) : esc(result.error.message)}</div>`;
      } else {
        msg.innerHTML = `<div class="ok">Password reset link sent to your inbox.</div>`;
      }
      return;
    }
    // Client-side min-length (bug §2.4): placeholder promises "Min 8
    // characters", so enforce it inline instead of surfacing a generic
    // provider error after a round trip.
    if (mode === "signup" && password.length < 8) {
      msg.innerHTML = `<div class="err">Password must be at least 8 characters.</div>`;
      return;
    }
    // Confirm-password on signup (audit §2.3): catch a typo here rather than
    // discovering it at first login. Mirrors the reset screen's existing check.
    if (mode === "signup" && $("auth-pass2").value !== password) {
      msg.innerHTML = `<div class="err">Passwords don't match.</div>`;
      return;
    }
    // Optional bot challenge (SEC-2). No-op unless CAPTCHA_SITE_KEY is set.
    const captchaToken = await getCaptchaToken();
    // Fail CLOSED when a key is configured but the challenge could not load or
    // complete (blocked third-party script, error callback, widget tear-down).
    // Previously this quietly continued without a token, so anyone blocking the
    // provider domain bypassed the gate entirely.
    if (__cfg && __cfg.captchaSiteKey && !captchaToken) {
      msg.innerHTML = `<div class="err">Security check could not finish — allow challenges.cloudflare.com if you run a script blocker, then try again.</div>`;
      return;
    }
    const authOptions = captchaToken ? { captchaToken } : {};
    const result = mode === "signup"
      // Email-confirmation redirect must go to *this* app's origin, not
      // Supabase's default Site URL (which defaulted to http://localhost:3000
      // and produced a dead confirmation link). Mirrors resetPasswordForEmail
      // below. The SPA (createClient default detectSessionInUrl) parses the
      // returned #access_token hash back into a session automatically.
      ? await sb.auth.signUp({ email, password, options: { emailRedirectTo: authRedirect(), ...authOptions } })
      : await sb.auth.signInWithPassword({ email, password, ...(authOptions.captchaToken ? { options: authOptions } : {}) });
    if (result.error) {
      const friendly = friendlyAuthError(result.error.message);
      msg.innerHTML = `<div class="err">${friendly ? esc(friendly) : esc(result.error.message)}</div>`;
      // §6.4: unconfirmed account hits "Email not confirmed" on login —
      // offer a resend right where the user is stuck.
      if (/not confirmed/i.test(result.error.message || "")) $("resend-wrap").style.display = "block";
      return;
    }
    if (mode === "signup") {
      // If email confirmation is enabled there is no session yet; state that
      // explicitly instead of claiming the account is already signed in.
      const needsConfirm = !(result.data && result.data.session);
      msg.innerHTML = needsConfirm
        ? `<div class="ok">Account created — check your inbox to confirm your email, then sign in.</div>`
        : `<div class="ok">Account created — you're signed in.</div>`;
      if (needsConfirm) $("resend-wrap").style.display = "block";
    }
    await boot();
  } catch (error) {
    msg.innerHTML = `<div class="err">${esc(error.message || "Could not reach the account service")}</div>`;
  } finally {
    button.disabled = false;
  }
};

// Password-reset landing view (bug §2.1): shown when Supabase fires
// PASSWORD_RECOVERY after the user clicks the recovery email link.
$("reset-go").onclick = async () => {
  const msg = $("reset-msg");
  const p1 = $("reset-pass").value, p2 = $("reset-pass2").value;
  msg.innerHTML = "";
  if (p1.length < 8) { msg.innerHTML = `<div class="err">Password must be at least 8 characters.</div>`; return; }
  if (p1 !== p2) { msg.innerHTML = `<div class="err">Passwords don't match.</div>`; return; }
  const btn = $("reset-go");
  btn.disabled = true;
  try {
    const { error } = await sb.auth.updateUser({ password: p1 });
    if (error) {
      const friendly = friendlyAuthError(error.message);
      msg.innerHTML = `<div class="err">${friendly ? esc(friendly) : esc(error.message)}</div>`;
      return;
    }
    msg.innerHTML = `<div class="ok">Password updated — opening your workspace…</div>`;
    $("reset-pass").value = ""; $("reset-pass2").value = "";
    passwordRecoveryPending = false;
    setTimeout(() => boot(), 600);
  } catch (error) {
    msg.innerHTML = `<div class="err">${esc(error.message || "Could not update password")}</div>`;
  } finally {
    btn.disabled = false;
  }
};
$("nav-logout").onclick = async () => { await sb.auth.signOut(); location.reload(); };

// Account deletion (GDPR / privacy-policy promise). DELETE /api/me removes the
// auth user; the database cascades to campaigns, keys, usage and delivery log.
$("d-account-delete").onclick = async (e) => {
  const btn = e.currentTarget;
  if (!confirm("Cancel all Cloud billing immediately AND permanently delete your workspace and keys? Export your data first. Cancellation is not a refund; legally required payment records remain. If billing cannot be reconciled, deletion stops and you can retry.")) return;
  const phrase = window.prompt("Type DELETE to confirm permanent account deletion:");
  if (phrase !== "DELETE") return;
  btn.disabled = true; btn.textContent = "Deleting…";
  try {
    const r = await api("/me", { method: "DELETE", body: JSON.stringify({confirm:"DELETE AND CANCEL BILLING"}) });
    if (r && r.ok) {
      await sb.auth.signOut();
      location.reload();
      return;
    }
    const d = await r.json().catch(() => ({}));
    alert(d.error || "Could not delete your account.");
    btn.disabled = false; btn.textContent = "Delete account …";
  } catch (error) {
    alert(String(error?.message || error));
    btn.disabled = false; btn.textContent = "Delete account …";
  }
};

$("auth-resend").onclick = async () => {
  const email = $("auth-email").value.trim();
  const msg = $("auth-msg");
  if (!email) { msg.innerHTML = `<div class="err">Please enter your email</div>`; return; }
  const btn = $("auth-resend");
  btn.disabled = true;
  try {
    const { error } = await sb.auth.resend({ type: "signup", email, options: {emailRedirectTo: authRedirect()} });
    msg.innerHTML = error
      ? `<div class="err">${esc(error.message)}</div>`
      : `<div class="ok">Confirmation email re-sent — check your inbox (and spam folder).</div>`;
  } catch (error) {
    msg.innerHTML = `<div class="err">${esc(error.message || "Could not resend confirmation")}</div>`;
  } finally {
    btn.disabled = false;
  }
};

/* ===== BYOK keys (Stage 1) ===== */
async function loadKeys() {
  const card = $("keys-card");
  const r = await api("/me/keys").catch(() => null);
  if (!r || r.status === 404) { card.classList.add("hidden"); return; }
  card.classList.remove("hidden");
  if (!r.ok) return;
  const d = await r.json();
  const keys = d.keys || [];
  const provider = $("key-provider").value;
  const saved = keys.find((key) => key.provider === provider);
  const status = $("key-status");
  const removeBtn = $("key-remove");
  if (saved) {
    status.textContent = `✓ ${saved.provider}: ${saved.key_prefix}`;
    removeBtn.style.display = "inline-flex";
    $("key-input").placeholder = "Leave blank to keep your saved key";
  } else {
    status.textContent = keys.length
      ? `No ${provider} key saved (${keys.length} provider key${keys.length === 1 ? "" : "s"} on file).`
      : "No key saved — campaigns use the server's key or the offline engine.";
    removeBtn.style.display = "none";
    $("key-input").placeholder = "Paste a provider key";
  }
}
$("key-provider").addEventListener("change", loadKeys);
$("key-save").onclick = async () => {
  const msg = $("keys-msg");
  msg.innerHTML = "";
  const apiKey = $("key-input").value.trim();
  if (!apiKey) { await loadKeys(); return; }
  const provider = $("key-provider").value;
  const btn = $("key-save");
  btn.disabled = true; btn.textContent = "Validating…";
  try {
    const r = await api("/me/keys", {
      method: "PUT",
      body: JSON.stringify({ provider, api_key: apiKey }),
    });
    const d = await r.json().catch(() => ({}));
    if (!r.ok) {
      msg.innerHTML = `<div class="err">${esc(d.error || "Could not save key")}</div>`;
      return;
    }
    $("key-input").value = "";
    msg.innerHTML = `<div class="ok">${esc(d.provider)} key saved (${esc(d.key_prefix)}).</div>`;
    await loadKeys();
  } catch (error) {
    msg.innerHTML = `<div class="err">${esc(error.message || "Could not save key")}</div>`;
  } finally {
    btn.disabled = false;
    btn.textContent = "Save key";
  }
};
$("key-remove").onclick = async () => {
  const provider = $("key-provider").value;
  const msg = $("keys-msg");
  try {
    const r = await api("/me/keys?provider=" + encodeURIComponent(provider), { method: "DELETE" });
    const d = await r.json().catch(() => ({}));
    if (!r.ok) throw new Error(d.error || "Could not remove key");
    msg.innerHTML = `<div class="ok">${esc(provider)} key removed.</div>`;
    await loadKeys();
  } catch (error) {
    msg.innerHTML = `<div class="err">${esc(error.message || "Could not remove key")}</div>`;
  }
};

$("d-deliver").onclick = async () => {
  const msg = $("d-deliver-msg");
  msg.textContent = "";
  if (!current) return;
  const phone = $("d-phone").value.trim();
  if (!phone) { msg.textContent = "Enter your WhatsApp number (E.164, e.g. +923001234567)."; return; }
  try { localStorage.setItem("brandforge-phone", phone); } catch {}
  const btn = $("d-deliver");
  btn.disabled = true; btn.textContent = "Sending…";
  try {
    const r = await api("/campaigns/" + encodeURIComponent(current.id) + "/deliver", {
      method: "POST",
      body: JSON.stringify({ phone }),
    });
    const d = await r.json().catch(() => ({}));
    msg.textContent = r.ok ? "✓ Workspace reminder sent to " + phone : (d.error || "Delivery failed");
    msg.style.color = r.ok ? "#10B981" : "#F87171";
  } catch (error) {
    msg.textContent = error.message || "Delivery service unavailable";
    msg.style.color = "#F87171";
  } finally {
    btn.disabled = false; btn.textContent = "Send workspace reminder";
  }
};

$("nav-billing").onclick = async () => {
  // Guests shouldn't land on a broken billing view (api() 401s -> "Could not load
  // plans"). Route them to sign-up instead so "Upgrade" always makes sense.
  const s = await session();
  if (!s) { setAuthMode("signup"); show("auth"); const m = $("auth-msg"); if (m) m.innerHTML = "<div class='ok'>Sign in to manage your plan — or create a free account.</div>"; return; }
  show("billing"); loadBilling();
};
$("bill-back").onclick = () => boot();

// ---- theme toggle (audit §4.4): light/dark parity with the marketing site ----
const THEME_KEY = "brandforge-theme";
// Site-wide cookie (Domain=.brandforge-os.com) so a theme chosen on the marketing site
// (www) also applies on the app subdomain, and vice-versa. localStorage alone would be
// origin-scoped, so www<->app would never agree. (fix: app reverted to dark after the
// user set light on www.)
function themeCookieSet(t) {
  try { document.cookie = "brandforge-theme=" + t + ";Path=/;Domain=.brandforge-os.com;Max-Age=" + (365 * 24 * 60 * 60); } catch {}
}
function applyTheme(theme) {
  const dark = theme !== "light";
  document.documentElement.setAttribute("data-theme", dark ? "" : "light");
  const btn = $("nav-theme");
  if (btn) { btn.textContent = dark ? "☀" : "☾"; btn.setAttribute("aria-pressed", String(!dark)); }
}
function initTheme() {
  let t = null;
  try { const m = document.cookie.match(/(?:^|;\s*)brandforge-theme=([^;]+)/); if (m) t = decodeURIComponent(m[1]); } catch {}
  if (!t) { try { t = localStorage.getItem(THEME_KEY); } catch {} }
  // Default DARK to match the marketing site, which is dark-first; light is the
  // visitor's explicit opt-in (cookie/localStorage), shared across www and app.
  applyTheme(t === "light" ? "light" : "dark");
}
(function () {
  const btn = $("nav-theme");
  if (!btn) return;
  btn.onclick = () => {
    const isLightNow = document.documentElement.getAttribute("data-theme") === "light";
    const next = isLightNow ? "dark" : "light";
    try { localStorage.setItem(THEME_KEY, next); } catch {}
    themeCookieSet(next);
    applyTheme(next);
  };
  initTheme();
})();

let billingBusy=false,billingData=null,paddleLoading=null;
const intentParams=new URLSearchParams(location.search);
function validIntent(value){return value&&['pro','agency'].includes(value.plan)&&['month','year'].includes(value.interval)&&!(value.plan==='agency'&&value.interval==='year')?value:null;}
let planIntent=validIntent({plan:intentParams.get('plan'),interval:intentParams.get('interval')||'month'});
try{if(planIntent)localStorage.setItem('brandforge-plan-intent',JSON.stringify(planIntent));else planIntent=validIntent(JSON.parse(localStorage.getItem('brandforge-plan-intent')||'null'));}catch{}
let autoShowPlan=!!planIntent;
function authRedirect(){const u=new URL('/',location.origin);if(planIntent){u.searchParams.set('plan',planIntent.plan);u.searchParams.set('interval',planIntent.interval);}return u.href;}
async function loadBilling(){
 const list=$('bill-plans');list.innerHTML='<p class="help">Loading billing…</p>';
 try{
  const d=await requestJSON('/billing/status');billingData=d;$('bill-interval').disabled=billingBusy;$('bill-current').textContent=`Current: ${d.plan.toUpperCase()} · ${d.plan_status}`;
  $('bill-portal').classList.toggle('hidden',!d.portal_available);$('bill-cancel-pending').classList.toggle('hidden',!d.pending_checkout);
  if(planIntent)$('bill-interval').value=planIntent.interval;
  const annual=$('bill-interval').value==='year';
  list.innerHTML=d.plans.map(p=>{
   const selectedInterval=p.id==='pro'&&annual?'year':'month';
   const same=p.id===d.plan&&(p.id==='free'||d.subscriptions?.some(s=>s.plan===p.id&&s.billing_interval===selectedInterval&&['active','trialing','past_due'].includes(s.status)));
   const price=p.id==='pro'&&annual?'$490/year':p.price_label;
   return `<section class="card"><h3>${esc(p.name)}</h3><p style="font-size:23px;font-weight:700;margin:10px 0">${esc(price)}</p><p class="help">${esc(p.tagline)}</p><ul style="padding-left:18px;font-size:12px;line-height:1.9">${p.features.map(f=>`<li>${esc(f)}</li>`).join('')}</ul><button class="btn ${same?'ghost':'gold'} bill-pay" data-plan="${p.id}" style="margin-top:14px" ${same||p.id==='free'||!d.checkout_enabled||billingBusy?'disabled':''}>${same?'Current plan':p.id==='free'?'Cancel renewal in portal':!d.checkout_enabled?'Paid checkout not open':d.has_subscription?'Preview change':'Review checkout'}</button></section>`;
  }).join('');
  list.querySelectorAll('[data-plan]').forEach(b=>b.onclick=()=>openCheckout(b.dataset.plan,d));
  if(!d.checkout_enabled)$('bill-msg').innerHTML='<p class="ok">Paid plans are not open yet. You can use the Free allowance and keep or export your existing work.</p>';
  else if(planIntent)$('bill-msg').textContent=`Selected from pricing: ${planIntent.plan.toUpperCase()}, ${planIntent.interval==='year'?'$490 billed each year':'monthly'}. Review before confirming; selecting a plan does not authorize payment.`;
 }catch(e){list.innerHTML='';
  // A route/deploy hiccup (e.g. platform 404) must not read as lost work.
  $('bill-msg').textContent=e.status===404
   ?'Plan management is temporarily unavailable while we finish an update. Your campaigns and exports are unaffected — please check back shortly.'
   :e.message;}
}
$('bill-interval').onchange=()=>{planIntent={plan:'pro',interval:$('bill-interval').value};try{localStorage.setItem('brandforge-plan-intent',JSON.stringify(planIntent));}catch{}loadBilling();};
async function paddleClient(){
 if(paddleLoading)return paddleLoading;
 paddleLoading=(async()=>{
  const r=await fetch('/api/billing/paddle-client-token');const config=await r.json();if(!r.ok||!config.token)throw new Error(config.error||'Checkout is disabled.');
  if(!window.Paddle)await new Promise((resolve,reject)=>{const s=document.createElement('script');s.src='https://cdn.paddle.com/paddle/v2/paddle.js';s.onload=resolve;s.onerror=()=>reject(new Error('Payment provider could not load. No new payment was submitted.'));document.head.append(s);});
  if(!window.__bfPaddleInit){
   if(config.environment==='sandbox')window.Paddle.Environment.set('sandbox');
   window.Paddle.Initialize({token:config.token,eventCallback:ev=>{
    if(ev.name==='checkout.closed'){billingBusy=false;loadBilling();}
    if(ev.name==='checkout.completed'){
     billingBusy=false;planIntent=null;try{localStorage.removeItem('brandforge-plan-intent');}catch{}
     $('bill-msg').textContent='Payment submitted. Waiting for server confirmation — do not pay again.';
     let attempts=0;const check=async()=>{await refreshAccountSummary();await loadBilling();if(window.__bfMe?.plan==='free'&&++attempts<10)setTimeout(check,2000);};setTimeout(check,1500);
    }
   }});window.__bfPaddleInit=true;
  }
  return window.Paddle;
 })().catch(e=>{paddleLoading=null;throw e;});return paddleLoading;
}
function money(t,currency){const value=t?.grand_total??t?.total??t?.balance;if(value===undefined||value===null)return 'No immediate amount reported';try{return new Intl.NumberFormat(undefined,{style:'currency',currency:currency||'USD'}).format(Number(value)/100);}catch{return String(value)+' minor units';}}
async function openCheckout(planId,bill){
 if(billingBusy||!bill.checkout_enabled)return;billingBusy=true;$('bill-interval').disabled=true;$('bill-msg').textContent='Preparing a server-authorized billing review…';document.querySelectorAll('.bill-pay').forEach(b=>b.disabled=true);
 const interval=planId==='pro'?$('bill-interval').value:'month';
 try{
  if(bill.has_subscription){
   const d=await requestJSON('/billing/change',{method:'POST',body:JSON.stringify({plan:planId,interval})});const box=$('bill-preview');box.classList.remove('hidden');
   box.innerHTML=`<h3>Review your plan change</h3><p>Switch to ${esc(planId.toUpperCase())} · ${interval==='year'?'$490/year':planId==='pro'?'$49/month':'$99/month'}.</p><p>Prorated amount now: <strong>${esc(d.preview.immediate?money(d.preview.immediate,d.preview.currency):'No immediate charge')}</strong></p><p>Next transaction estimate: ${esc(d.preview.next?money(d.preview.next,d.preview.currency):'See the renewal in your billing portal')}</p><p class="help">${esc(d.notice)} Taxes and account credits are calculated by Paddle. This updates the existing subscription.</p><div class="action-row"><button id="confirm-plan-change" class="btn gold">Confirm change and prorated charge</button><button id="cancel-plan-change" class="btn ghost">Keep current plan</button></div>`;
   $('confirm-plan-change').onclick=async()=>{const button=$('confirm-plan-change');button.disabled=true;try{await requestJSON('/billing/change',{method:'POST',body:JSON.stringify({plan:planId,interval,confirmation:d.confirmation})});box.classList.add('hidden');planIntent=null;try{localStorage.removeItem('brandforge-plan-intent');}catch{}await refreshAccountSummary();$('bill-msg').textContent='Existing subscription updated. No second subscription was created.';}catch(e){$('bill-msg').textContent=e.message;}finally{billingBusy=false;await loadBilling();}};
   $('cancel-plan-change').onclick=()=>{box.classList.add('hidden');billingBusy=false;loadBilling();};box.scrollIntoView({block:'center'});$('confirm-plan-change').focus();
  }else{
   const client=await paddleClient();
   const d=await requestJSON('/billing/checkout',{method:'POST',body:JSON.stringify({plan:planId,interval})});
   client.Checkout.open({transactionId:d.transaction_id,settings:{displayMode:'overlay',theme:document.documentElement.dataset.theme==='light'?'light':'dark',locale:'en'}});
   $('bill-msg').textContent='Review the full charge and renewal terms in Paddle before paying.';
  }
 }catch(e){billingBusy=false;await loadBilling();$('bill-msg').textContent=e.message;}
}
$('bill-portal').onclick=async()=>{const b=$('bill-portal'),tab=window.open('about:blank','_blank');if(tab)tab.opener=null;b.disabled=true;try{const d=await requestJSON('/billing/portal',{method:'POST',body:'{}'});if(tab)tab.location.href=d.url;else location.assign(d.url);}catch(e){if(tab)tab.close();$('bill-msg').textContent=e.message;}finally{b.disabled=false;}};
$('bill-cancel-pending').onclick=async()=>{if(!confirm('Close the pending unpaid checkout? This does not refund payments or cancel an active subscription.'))return;try{await requestJSON('/billing/cancel-pending',{method:'POST',body:'{}'});$('bill-msg').textContent='Pending checkout reconciled.';await loadBilling();}catch(e){$('bill-msg').textContent=e.message;}};


// Browser back/forward across campaign deep-links: re-render to match the URL.
window.addEventListener("popstate", () => {
  const m = location.pathname.match(/^\/app\/c\/([A-Za-z0-9_-]+)\/?$/);
  if (m) {
    if (currentSession) openCampaign(decodeURIComponent(m[1]), { replace: true });
  } else {
    revokeBlobs();
    openRequest += 1;
    current = null;
    $("detail").classList.add("hidden");
  }
});

boot();

$('bill-reconcile').onclick=async()=>{try{await requestJSON('/billing/reconcile',{method:'POST',body:'{}'});await refreshAccountSummary();await loadBilling();$('bill-msg').textContent='Billing reconciled.';}catch(e){$('bill-msg').textContent=e.message;}};

$('d-rename').onclick=async()=>{
 if(!current||editing){$('d-action-msg').textContent='Save or discard section edits before renaming.';return;}
 const name=prompt('Campaign name (up to 80 characters):',current.name);if(name===null)return;
 if(!name.trim()||name.length>80){$('d-action-msg').textContent='Use a name from 1 to 80 characters.';return;}
 try{await requestJSON('/campaigns/'+current.id,{method:'PATCH',body:JSON.stringify({revision:current.revision,name:name.trim()})});await openCampaign(current.id,{replace:true});await loadCampaigns();}catch(e){$('d-action-msg').textContent=e.message;}
};

}
startWorkspace().catch(()=>{document.body.innerHTML='<main style="max-width:600px;margin:60px auto;padding:24px;font-family:system-ui"><h1>Workspace temporarily unavailable</h1><p>Reload to try again, or contact support@brandforge-os.com. No payment was started.</p></main>';});
