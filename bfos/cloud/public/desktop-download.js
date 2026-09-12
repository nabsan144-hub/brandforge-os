(async()=>{
 const params=new URLSearchParams(location.hash.slice(1) || location.search);
 const token=params.get('token');
 history.replaceState(null,'',location.pathname);
 const label=document.getElementById('download-status');
 if(!token){label.textContent='Open the complete private link from your purchase email, or request a new one.';return;}
 try{const response=await fetch('/api/desktop/download',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({token})});const data=await response.json();if(!response.ok)throw new Error(data.error||'Download unavailable.');if(new URL(data.url).protocol!=='https:')throw new Error('Invalid download destination.');label.textContent='Order verified. Starting the download…';location.assign(data.url);}catch(e){label.textContent=e.message;}
})();
