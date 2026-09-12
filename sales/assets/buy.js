/* Shared Desktop funnel. A public token/price ID never authorizes a charge.
   Prelaunch goes to the waitlist. Live checkout needs BOTH the public funnel
   flag and the server's verified catalog/fulfillment release gate. */
(function(){
  var busy=false,loading=null;
  var cfg=function(){return window.BRANDFORGE_LAUNCH||{};};
  function waitlist(tier){
    var node=document.getElementById('waitlist');
    if(!node){window.location.href='pricing?tier='+encodeURIComponent(tier||'undecided')+'#waitlist';return;}
    node.scrollIntoView({behavior:window.matchMedia&&matchMedia('(prefers-reduced-motion: reduce)').matches?'auto':'smooth',block:'center'});
    var select=document.getElementById('wl-tier');if(select&&tier)select.value=tier;
    var input=document.getElementById('wl-email');if(input)setTimeout(function(){input.focus();},100);
  }
  function notice(message){
    var node=document.getElementById('checkout-message');
    if(!node){node=document.createElement('div');node.id='checkout-message';node.setAttribute('role','status');node.style.cssText='position:fixed;bottom:20px;left:5%;right:5%;max-width:680px;margin:auto;z-index:100;padding:18px;border-radius:12px;background:#0F172A;color:#F8FAFC;border:1px solid #E8B54A;font-size:14px;line-height:1.6';document.body.appendChild(node);}
    node.textContent=message;
  }
  async function paddle(base){
    if(loading)return loading;
    loading=(async function(){
      var response=await fetch(base+'/api/billing/paddle-client-token');var config=await response.json();
      if(!response.ok||!config.token)throw new Error('Desktop checkout is not open yet.');
      if(!window.Paddle)await new Promise(function(resolve,reject){var script=document.createElement('script');script.src='https://cdn.paddle.com/paddle/v2/paddle.js';script.onload=resolve;script.onerror=function(){reject(new Error('Payment provider could not load.'));};document.head.appendChild(script);});
      if(!window.__bfPaddleInitialized){
        if(config.environment==='sandbox')window.Paddle.Environment.set('sandbox');
        window.Paddle.Initialize({token:config.token,eventCallback:function(event){
          if(event.name==='checkout.closed')busy=false;
          if(event.name==='checkout.completed'){busy=false;notice('Payment submitted. Your desktop download will be emailed after server verification. No Cloud subscription was started. Contact support with the Paddle transaction ID if delivery is delayed.');}
        }});window.__bfPaddleInitialized=true;
      }
      return window.Paddle;
    })().catch(function(error){loading=null;throw error;});return loading;
  }
  window.brandforgeBuy=async function(tier){
    if(!['owner','agency_source'].includes(tier))return;
    if(cfg().desktop_checkout_enabled!==true){waitlist(tier);return;}
    if(busy)return;busy=true;
    try{
      var availability=window.BRANDFORGE_AVAILABILITY;
      if(!availability)throw new Error('Desktop availability could not be verified.');
      await availability.refresh();
      if(!availability.desktopOpen()){busy=false;notice('Desktop checkout is not open or could not be verified. Join the waitlist for updates.');waitlist(tier);return;}
      var base=String(cfg().hosted_url||'').replace(/\/+$/,'');
      if(!/^https:\/\//.test(base))throw new Error('Checkout service is not configured.');
      var client=await paddle(base);
      var response=await fetch(base+'/api/desktop/checkout',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({tier:tier})});
      var result=await response.json();if(!response.ok||!result.transaction_id)throw new Error(result.error||'Checkout is not available.');
      client.Checkout.open({transactionId:result.transaction_id,settings:{displayMode:'overlay',theme:document.documentElement.dataset.theme==='light'?'light':'dark'}});
    }catch(error){busy=false;notice(error.message+' No new payment was submitted by this page.');waitlist(tier);}
  };
  window.joinWaitlist=waitlist;
  // CTA labels follow the same launch state, so a button can never promise
  // checkout for a tier that still routes to the waitlist (and vice versa).
  // Static HTML ships the honest waitlist wording; this upgrades each labelled
  // element to a buy label only when its tier is actually configured for sale.
  function relabel(){window.BRANDFORGE_AVAILABILITY?.render();}
  if(document.readyState==='loading')document.addEventListener('DOMContentLoaded',relabel);else relabel();
  window.refreshDesktopCtas=relabel;
  function intent(){var tier=new URLSearchParams(location.search).get('tier');var select=document.getElementById('wl-tier');if(select&&['owner','agency_source','undecided'].includes(tier))select.value=tier;}
  if(document.readyState==='loading')document.addEventListener('DOMContentLoaded',intent);else intent();
})();
