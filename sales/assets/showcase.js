/* Local image inspection only. No generation, account, API or upload request. */
(()=>{
 const dialog=document.getElementById('artwork-viewer');
 if(!dialog||typeof dialog.showModal!=='function')return;
 const image=document.getElementById('artwork-full'),title=document.getElementById('artwork-title'),original=document.getElementById('artwork-original');
 let opener=null;
 document.querySelectorAll('a.showcase-open').forEach(link=>link.addEventListener('click',event=>{
  if(event.ctrlKey||event.metaKey||event.shiftKey||event.altKey)return;
  const url=new URL(link.href,location.href);
  if(url.origin!==location.origin||!url.pathname.includes('/assets/showcase/'))return;
  event.preventDefault();opener=link;title.textContent=link.dataset.title||'Campaign artwork';
  image.src=url.href;image.alt=link.querySelector('img')?.alt||title.textContent;original.href=url.href;dialog.showModal();
 }));
 document.getElementById('artwork-close').addEventListener('click',()=>dialog.close());
 dialog.addEventListener('close',()=>{image.removeAttribute('src');opener?.focus();});
})();
