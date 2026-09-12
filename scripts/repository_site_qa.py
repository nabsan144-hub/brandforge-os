"""All source sales pages, real Chromium rendering/CSP; external APIs mocked.
Hosting redirect behavior is tested separately with the Python static adapter.
"""
import asyncio, json, mimetypes, os
from pathlib import Path
from urllib.parse import urlparse
from playwright.async_api import async_playwright
ROOT=Path(__file__).resolve().parents[1];SITE=ROOT/'sales';OUT=Path(os.environ.get('BRANDFORGE_QA_DIR',str(ROOT/'qa-results/repository-site')));OUT.mkdir(parents=True,exist_ok=True)
ORIGIN='https://sales.example.test';AXE=(SITE/'node_modules/axe-core/axe.min.js').read_text()
HEADERS={h['key']:h['value'] for rule in json.loads((SITE/'vercel.json').read_text())['headers'] if rule['source']=='/(.*)' for h in rule['headers']}
async def main():
 results=[]
 async with async_playwright() as p:
  browser=await getattr(p,os.environ.get('BF_BROWSER','chromium')).launch(args=['--no-sandbox'] if os.environ.get('BF_BROWSER','chromium')=='chromium' else [])
  for theme in ['light','dark']:
   for width in [390,1440]:
    context=await browser.new_context(viewport={'width':width,'height':900},reduced_motion='reduce');await context.add_init_script(f"localStorage.setItem('brandforge-theme','{theme}')")
    async def route(r):
     u=urlparse(r.request.url)
     if u.path=='/api/capabilities':return await r.fulfill(json={'schema':1,'generation_paused':False,'cloud':{'checkout_enabled':False},'desktop':{'checkout_enabled':False},'imagery':{'configured':False,'scope':'hero_only','resized_banners':'vector_only'}},headers={'Access-Control-Allow-Origin':ORIGIN})
     if u.hostname!=urlparse(ORIGIN).hostname:return await r.abort()
     path=u.path.lstrip('/') or 'index.html'
     if not Path(path).suffix:path+='.html'
     f=SITE/path
     if f.is_file():return await r.fulfill(body=f.read_bytes(),headers=HEADERS,content_type=mimetypes.guess_type(str(f))[0] or 'application/octet-stream')
     return await r.fulfill(status=404,body='Not found')
    await context.route('**/*',route)
    for file in sorted(SITE.glob(os.environ.get('BF_QA_PAGES','*.html'))):
     page=await context.new_page();errors=[];page.on('pageerror',lambda e:errors.append(str(e)))
     await page.goto(ORIGIN+('/' if file.stem=='index' else '/'+file.stem),wait_until='networkidle')
     await page.evaluate("()=>document.querySelectorAll('[data-rv]').forEach(x=>x.classList.add('in','is-visible','revealed'))")
     await page.evaluate(AXE)
     violations=await page.evaluate("async()=> (await axe.run()).violations.map(v=>({id:v.id,nodes:v.nodes.map(n=>({target:n.target,summary:n.failureSummary}))}))")
     overflow=await page.evaluate('document.documentElement.scrollWidth>innerWidth')
     if file.stem in ['index','pricing','docs']:await page.screenshot(path=str(OUT/f'{file.stem}-{theme}-{width}.png'))
     results.append({'page':file.name,'theme':theme,'width':width,'axe':violations,'overflow':overflow,'page_errors':errors})
     await page.close()
    await context.close()
  await browser.close()
 (OUT/'results.json').write_text(json.dumps(results,indent=2))
 failures=[r for r in results if r['axe'] or r['overflow'] or r['page_errors']]
 print(json.dumps({'views':len(results),'failures':failures},indent=2));assert not failures
asyncio.run(main())
