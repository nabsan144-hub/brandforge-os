(async()=>{
 const params=new URLSearchParams(location.hash.slice(1) || location.search);
 const token=params.get('token');
 // Keep the capability in this closure only: never localStorage, DOM, logs or
 // a referrer. Clearing the URL must not make an ordinary failed request final.
 history.replaceState(null,'',location.pathname);
 const label=document.getElementById('download-status'),retry=document.getElementById('download-retry');
 if(!token){label.textContent='Open the complete private link from your purchase email, or request a new one.';return;}
 async function download(){
  retry.hidden=false;retry.disabled=true;label.textContent='Checking your private download link…';
  try{
   const response=await fetch('/api/desktop/download',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({token}),signal:AbortSignal.timeout(15000)});
   const data=await response.json();if(!response.ok)throw new Error(data.error||'Download unavailable.');
   const destination=new URL(data.url);if(destination.protocol!=='https:'||destination.username||destination.password)throw new Error('Invalid download destination.');
   label.textContent='Order verified. Starting the download… If it does not start, retry below.';
   location.assign(destination.href);
  }catch(e){label.textContent=e.name==='TimeoutError'||e.name==='AbortError'?'The download check timed out. Retry below; no new purchase is needed.':e instanceof TypeError?'The download could not be reached. Check your connection and retry.':e.message;}
  finally{retry.disabled=false;}
 }
 retry.addEventListener('click',download);
 await download();
})();
