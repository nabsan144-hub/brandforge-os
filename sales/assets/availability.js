/* One release-state reader for badges, Cloud CTAs and Desktop buttons.
   Public flags/tokens/prices alone NEVER prove checkout is open. */
(function(){
 var state=null,serial=0;
 var cfg=function(){return window.BRANDFORGE_LAUNCH||{};};
 function base(){return String(cfg().hosted_url||'').replace(/\/+$/,'');}
 function desktopOpen(){return cfg().desktop_checkout_enabled===true&&state?.desktop.checkout_enabled===true;}
 function setText(selector,text){document.querySelectorAll(selector).forEach(function(el){el.textContent=text;});}
 function render(){
  var cloud=state?.cloud.checkout_enabled===true,desktop=desktopOpen();
  var paidText=state?(cloud?'Paid Cloud checkout enabled':'Paid Cloud checkout not open'):'Paid Cloud availability unverified';
  var deskText=desktop?'Desktop checkout enabled':!state&&cfg().desktop_checkout_enabled===true?'Desktop availability unverified — join waitlist':'Desktop waitlist — purchases not open';
  setText('[data-release-summary]','Free Cloud: 3 lifetime campaigns, no card. '+paidText+'. '+deskText+'.');
  setText('[data-desktop-status]',deskText);
  setText('#launch-badge',paidText+' · '+deskText);
  setText('#launch-note',desktop?'Desktop is a separate one-time purchase. Payment and file delivery are verified by the server.':'Desktop is waitlist-only on this site. Listed prices apply at launch; joining the waitlist does not start a payment.');
  setText('[data-image-status]',state?.imagery.configured&&state.imagery.scope==='campaign_formats'?'Three-format AI campaigns are configured for opted-in Pro/Agency use. Provider, budget and content-review checks still apply.':state?.imagery.configured?'Optional AI hero artwork is configured for opted-in Pro/Agency campaigns; provider and budget checks still apply. Resized banners remain vector-only.':'Cloud uses vector visuals by default. Optional AI hero artwork is not currently confirmed available. Resized banners remain vector-only.');
  setText('[data-generation-status]',state?.generation_paused?'New campaign generation is temporarily paused. Existing work remains available.':'');
  document.querySelectorAll('[data-cloud-cta]').forEach(function(a){
   var plan=a.dataset.cloudCta==='review-agency'?'agency':'pro',annual=a.dataset.cloudCta==='review-pro-year';
   a.textContent=cloud?(annual?'Review Pro annual — $490/year':'Review '+(plan==='pro'?'Pro':'Agency')+' monthly'):'Start free — no card';
   a.href=base()+'/signup'+(cloud?'?plan='+plan+'&interval='+(annual?'year':'month'):'');
  });
  document.querySelectorAll('[data-cta-tier]').forEach(function(el){
   var price=el.getAttribute('data-cta-price')||'';
   el.textContent=desktop?'Buy once — $'+price:'Join the waitlist — $'+price+' at launch';
  });
  // Keep the waitlist reachable even when enabled: no paid tier is inferred
  // from public price IDs, and interested visitors need not start checkout.
  window.dispatchEvent(new CustomEvent('brandforge:availability'));
 }
 function valid(d){return d?.schema===1&&typeof d.cloud?.checkout_enabled==='boolean'&&typeof d.desktop?.checkout_enabled==='boolean'&&typeof d.imagery?.configured==='boolean'&&((d.imagery.scope==='hero_only'&&d.imagery.resized_banners==='vector_only')||(d.imagery.scope==='campaign_formats'&&d.imagery.resized_banners==='three_ai_formats'))&&typeof d.generation_paused==='boolean';}
 async function refresh(){
  var id=++serial,controller=new AbortController(),timer=setTimeout(function(){controller.abort();},4000);
  try{
   var url=new URL(base());if(url.protocol!=='https:'||url.username||url.password)throw new Error('Invalid service');
   var r=await fetch(url.origin+'/api/capabilities',{cache:'no-store',credentials:'omit',signal:controller.signal});
   if(!r.ok)throw new Error('Unavailable');var data=await r.json();if(!valid(data))throw new Error('Invalid capability response');
   if(id===serial){state=data;render();}
  }catch{if(id===serial){state=null;render();}}
  finally{clearTimeout(timer);}
  return state;
 }
 window.BRANDFORGE_AVAILABILITY={refresh:refresh,render:render,desktopOpen:desktopOpen,getState:function(){return state;}};
 function boot(){render();refresh();}
 if(document.readyState==='loading')document.addEventListener('DOMContentLoaded',boot);else boot();
})();
