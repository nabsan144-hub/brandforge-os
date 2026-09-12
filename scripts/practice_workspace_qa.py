"""Real Chromium practice journey; only static local files are served.
Checks no account/API/provider calls, manifest verification, revision selection,
all previews, ZIP integrity, errors, accessibility and responsive layout.
"""
import asyncio, json, mimetypes, os, zipfile, hashlib
from pathlib import Path
from urllib.parse import urlparse
from playwright.async_api import async_playwright
ROOT=Path(__file__).resolve().parents[1]
OUT=Path(os.environ.get('BRANDFORGE_QA_DIR',str(ROOT/'qa-results/practice')));OUT.mkdir(parents=True,exist_ok=True)
ORIGIN='https://practice.example.test'
AXE=(ROOT/'cloud/node_modules/axe-core/axe.min.js').read_text()
HEADERS={h['key']:h['value'] for rule in json.loads((ROOT/'cloud/vercel.json').read_text())['headers'] if rule['source']=='/(.*)' for h in rule['headers']}
async def main():
 results=[]
 async with async_playwright() as p:
  browser=await p.chromium.launch(args=['--no-sandbox'])
  for theme in ['light','dark']:
   for width in [390,1440]:
    forbidden=[];errors=[];tamper=False
    async def route(r):
     u=urlparse(r.request.url)
     if u.hostname!=urlparse(ORIGIN).hostname or u.path.startswith('/api/') or r.request.method!='GET':
      forbidden.append(r.request.url);return await r.abort()
     f=ROOT/'cloud/public'/('practice.html' if u.path=='/practice' else u.path.lstrip('/'))
     if tamper and u.path.endswith('/revised.json'):return await r.fulfill(body='{}',content_type='application/json')
     if f.is_file():return await r.fulfill(body=f.read_bytes(),content_type=mimetypes.guess_type(str(f))[0] or 'application/octet-stream',headers=HEADERS)
     return await r.fulfill(status=404,body='Not found')
    context=await browser.new_context(viewport={'width':width,'height':1000},reduced_motion='reduce',accept_downloads=True)
    await context.route('**/*',route);await context.add_init_script(f"localStorage.setItem('brandforge-theme','{theme}')")
    page=await context.new_page();page.on('pageerror',lambda e:errors.append(str(e)))
    await page.goto(ORIGIN+'/practice',wait_until='networkidle');await page.wait_for_function("()=>!document.querySelector('#download').disabled")
    for version in ['original','revised']:
     await page.select_option('#version',version);await page.wait_for_function("()=>!document.querySelector('#download').disabled")
     values=await page.locator('#asset option').evaluate_all('(els)=>els.map(x=>x.value)')
     for value in values:
      await page.select_option('#asset',value);await page.wait_for_function("()=>document.querySelector('#preview').complete && document.querySelector('#preview').naturalWidth>0")
     assert ('500 g' if version=='revised' else '250 g') in await page.locator('#copy').inner_text()
     await page.evaluate(AXE);axe=await page.evaluate("async()=> (await axe.run()).violations.map(v=>({id:v.id,nodes:v.nodes.map(n=>n.target)}))")
     overflow=await page.evaluate('document.documentElement.scrollWidth>innerWidth')
     assert not axe and not overflow, (theme,width,axe,overflow)
     async with page.expect_download() as download:
      await page.click('#download')
     path=OUT/f'{theme}-{width}-{version}.zip';await (await download.value).save_as(path)
     with zipfile.ZipFile(path) as z:
      assert z.testzip() is None
      for entry in json.loads(z.read('manifest.json'))['files']:
       data=z.read(entry['name']);assert len(data)==entry['bytes'] and hashlib.sha256(data).hexdigest()==entry['sha256']
      assert any(n.endswith('.png') for n in z.namelist());assert 'EXPORT-WARNINGS.txt' not in z.namelist()
     await page.wait_for_function("()=>!document.querySelector('#download').disabled")
     results.append({'theme':theme,'width':width,'version':version,'previews':len(values),'axe':axe,'overflow':overflow,'zip_hashes':'passed'})
    await page.screenshot(path=str(OUT/f'practice-{theme}-{width}.png'),full_page=True)
    await page.select_option('#version','original');await page.wait_for_function("()=>!document.querySelector('#download').disabled")
    tamper=True;await page.select_option('#version','revised');await page.wait_for_function("()=>document.querySelector('#status').textContent.includes('Could not verify')")
    assert await page.locator('#download').is_disabled()
    assert not forbidden and not errors,(forbidden,errors)
    await context.close()
  await browser.close()
 (OUT/'results.json').write_text(json.dumps(results,indent=2)+'\n');print(json.dumps({'views':len(results),'failures':0,'tampered_sample_rejected':4,'API_or_provider_requests':0}))
asyncio.run(main())
