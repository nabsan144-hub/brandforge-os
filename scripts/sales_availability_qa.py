"""Offline Chromium release-label and real rendered contrast regression.
No real checkout, provider, account or deployment traffic is permitted.
"""
import asyncio,json,mimetypes,os
from pathlib import Path
from urllib.parse import urlparse
from playwright.async_api import async_playwright
ROOT=Path(__file__).resolve().parents[1]
OUT=Path(os.environ.get('BRANDFORGE_QA_DIR',str(ROOT/'qa-results/sales-availability')));OUT.mkdir(parents=True,exist_ok=True)
ORIGIN='https://sales.example.test'
AXE=(ROOT/'sales/node_modules/axe-core/axe.min.js').read_text()
HEADERS={h['key']:h['value'] for rule in json.loads((ROOT/'sales/vercel.json').read_text())['headers'] if rule['source']=='/(.*)' for h in rule['headers']}
def caps(cloud=False,desktop=False):return {'schema':1,'cloud':{'checkout_enabled':cloud},'desktop':{'checkout_enabled':desktop},'imagery':{'configured':False,'scope':'hero_only','resized_banners':'vector_only'},'generation_paused':False}
async def main():
 results=[]
 async with async_playwright() as p:
  browser=await p.chromium.launch(args=['--no-sandbox'])
  async def setup(page,state,flag=False):
   errors=[];requests=[];page.on('pageerror',lambda e:errors.append(str(e)))
   async def route(r):
    u=urlparse(r.request.url)
    if u.path=='/api/capabilities':
     requests.append(u.path)
     if state=='offline':return await r.abort()
     if state=='timeout':
      await asyncio.sleep(4.5)
      return await r.fulfill(json=caps(True,True))
     return await r.fulfill(json=state,headers={'Access-Control-Allow-Origin':ORIGIN})
    if u.hostname!=urlparse(ORIGIN).hostname:return await r.abort()
    file=ROOT/'sales'/(u.path.lstrip('/') or 'index.html')
    if file.suffix=='':file=file.with_suffix('.html')
    if not file.is_file():return await r.abort()
    data=file.read_bytes()
    if file.name=='config.js' and flag:data=data.replace(b'desktop_checkout_enabled: false',b'desktop_checkout_enabled: true')
    return await r.fulfill(body=data,headers=HEADERS,content_type=mimetypes.guess_type(str(file))[0] or 'application/octet-stream')
   await page.route('**/*',route)
   return errors,requests
  for name in ['index','pricing']:
   for theme in ['dark','light']:
    for width in [390,1440]:
     page=await browser.new_page(viewport={'width':width,'height':1000},reduced_motion='reduce')
     errors,requests=await setup(page,caps())
     await page.add_init_script(f"localStorage.setItem('brandforge-theme','{theme}')")
     await page.goto(ORIGIN+'/'+name);await page.wait_for_function('window.BRANDFORGE_AVAILABILITY?.getState()!==null')
     # Reveal every collapsed/scroll-triggered section before the contrast scan.
     await page.evaluate("document.querySelectorAll('details').forEach(x=>x.open=true);document.querySelectorAll('[data-rv]').forEach(x=>x.classList.add('in'))")
     await page.evaluate('document.fonts.ready');await page.evaluate(AXE)
     axe=await page.evaluate("async()=>{const r=await axe.run(document,{runOnly:{type:'tag',values:['wcag2a','wcag2aa','wcag21aa']}});return r.violations.map(x=>({id:x.id,nodes:x.nodes.map(n=>({target:n.target,summary:n.failureSummary}))}))}")
     overflow=await page.evaluate('document.documentElement.scrollWidth>innerWidth+1')
     selector='.term-bar > .mono' if name=='index' else '#desktop-alternative-note'
     # Sample actual composited colors, including transparent ancestor surfaces.
     contrast=await page.evaluate(r'''selector=>{
      const el=document.querySelector(selector);if(!el)throw new Error('Missing target');
      const rgb=x=>(x.match(/[\d.]+/g)||[]).map(Number),over=(a,b)=>{const alpha=a[3]??1;return [0,1,2].map(i=>a[i]*alpha+b[i]*(1-alpha))};
      const chain=[];for(let n=el;n;n=n.parentElement)chain.unshift(n);
      let bg=[255,255,255];for(const n of chain)bg=over(rgb(getComputedStyle(n).backgroundColor),bg);
      const fg=over(rgb(getComputedStyle(el).color),bg);
      const lum=c=>c.map(v=>{v/=255;return v<=.04045?v/12.92:((v+.055)/1.055)**2.4}).reduce((sum,v,i)=>sum+v*[.2126,.7152,.0722][i],0);
      const a=lum(fg),b=lum(bg);return {ratio:(Math.max(a,b)+.05)/(Math.min(a,b)+.05),foreground:fg,background:bg,text:el.textContent};
     }''',selector)
     result={'page':name,'theme':theme,'width':width,'contrast':contrast,'axe':axe,'overflow':overflow,'page_errors':errors};results.append(result)
     (OUT/'results.json').write_text(json.dumps(results,indent=2))
     assert not axe,result
     assert not overflow and not errors,result
     assert contrast['ratio']>=4.5,result
     if theme=='light' and width==1440:
      await page.screenshot(path=str(OUT/(name+'-light.png')),full_page=True)
      await page.locator('.term' if name=='index' else '#desktop-alternative-note').screenshot(path=str(OUT/(name+'-contrast.png')))
     await page.close()
  for label,state,flag,cloud,desktop in [('closed',caps(),False,False,False),('cloud-only',caps(True),True,True,False),('desktop-only',caps(False,True),True,False,True),('both',caps(True,True),True,True,True),('public-flag-off',caps(True,True),False,True,False),('offline','offline',True,False,False),('timeout','timeout',True,False,False),('malformed',{'schema':1},True,False,False)]:
   page=await browser.new_page(viewport={'width':1280,'height':900},reduced_motion='reduce');errors,requests=await setup(page,state,flag)
   await page.goto(ORIGIN+'/pricing');await page.wait_for_function('window.BRANDFORGE_AVAILABILITY')
   await page.evaluate('window.BRANDFORGE_AVAILABILITY.refresh()')
   value=await page.evaluate("({summary:document.querySelector('[data-release-summary]').textContent,desktop:[...document.querySelectorAll('[data-cta-tier]')].map(x=>x.textContent),cloud:[...document.querySelectorAll('[data-cloud-cta]')].map(x=>({text:x.textContent,href:x.href})),waitlist:!document.getElementById('waitlist').hidden})")
   assert all(('Buy once' in t)==desktop for t in value['desktop']),value
   assert all(('Review' in x['text'])==cloud for x in value['cloud']),value
   assert all(('plan=' in x['href'])==cloud for x in value['cloud']),value
   assert value['waitlist'] and not errors,value
   results.append({'state':label,'labels':value,'page_errors':errors});await page.close()
  await browser.close()
 (OUT/'results.json').write_text(json.dumps(results,indent=2))
 print(json.dumps({'rendered_views':8,'availability_states':8,'axe_violations':0,'overflow':0,'page_errors':0}))
asyncio.run(main())
