"""Actual local ASGI app + built Svelte dashboard through an in-process bridge.
No open port, no live providers. Linux proof, NOT Windows/macOS certification.
"""
import asyncio,json,os,sys,re
from pathlib import Path
from urllib.parse import urlparse
from unittest.mock import patch
ROOT=Path(__file__).resolve().parents[1];OUT=Path(os.environ.get('BRANDFORGE_QA_DIR',str(ROOT/'qa-results/desktop-workspace')));OUT.mkdir(parents=True,exist_ok=True)
os.environ['BRANDFORGE_DATA_DIR']=str(OUT/'isolated-data');os.environ['BRANDFORGE_UPDATE_CHECK']='0'
sys.path.insert(0,str(ROOT/'app'))
from fastapi.testclient import TestClient
from playwright.async_api import async_playwright
import server
AXE=(ROOT/'cloud/node_modules/axe-core/axe.min.js').read_text()
ORIGIN='http://127.0.0.1'
async def main():
 results=[]
 with patch('requests.sessions.Session.request',side_effect=RuntimeError('External requests forbidden in offline Desktop QA')):
  with TestClient(server.app,base_url=ORIGIN,client=('127.0.0.1',23456)) as client:
   async with async_playwright() as p:
    browser=await getattr(p,os.environ.get('BF_BROWSER','chromium')).launch(args=['--no-sandbox'] if os.environ.get('BF_BROWSER','chromium')=='chromium' else [])
    for theme in ['light','dark']:
     for width in [390,1440]:
      failed_session=False;errors=[]
      async def route(r):
       u=urlparse(r.request.url)
       if u.scheme in ('blob','data'):return await r.continue_()
       if u.hostname!='127.0.0.1':return await r.abort()
       if failed_session and u.path=='/api/session':return await r.fulfill(status=503,json={'error':'fixture outage'})
       response=await asyncio.to_thread(client.request,r.request.method,u.path+('?' +u.query if u.query else ''),content=r.request.post_data_buffer,headers={k:v for k,v in r.request.headers.items() if k not in ['host','content-length']})
       headers={k:v for k,v in response.headers.items() if k not in ['content-encoding','content-length','transfer-encoding']}
       await r.fulfill(status=response.status_code,headers=headers,body=response.content)
      context=await browser.new_context(viewport={'width':width,'height':1000},reduced_motion='reduce');await context.route('**/*',route);await context.add_init_script(f"localStorage.setItem('vg-theme','{theme}')")
      page=await context.new_page();page.on('pageerror',lambda e:errors.append(str(e)))
      await page.goto(ORIGIN,wait_until='networkidle');await page.wait_for_selector('#product-name-input')
      await page.evaluate(AXE);violations=await page.evaluate("async()=> (await axe.run()).violations.map(v=>({id:v.id,nodes:v.nodes.map(n=>({target:n.target,html:n.html,summary:n.failureSummary}))}))")
      overflow=await page.evaluate('document.documentElement.scrollWidth>innerWidth')
      await page.screenshot(path=str(OUT/f'desktop-{theme}-{width}.png'))
      results.append({'theme':theme,'width':width,'state':'actual local app','axe':violations,'overflow':overflow,'errors':list(errors)})
      nav_overlap=await page.evaluate("""()=>{const r=[...document.querySelectorAll('nav > div > div')].map(e=>e.getBoundingClientRect());return r.some((a,i)=>r.slice(i+1).some(b=>Math.min(a.right,b.right)-Math.max(a.left,b.left)>1&&Math.min(a.bottom,b.bottom)-Math.max(a.top,b.top)>1))}""")
      assert not nav_overlap,'Navigation groups overlap'
      await page.locator('button[aria-controls="network-ledger"]').click();await page.wait_for_selector('#network-ledger')
      assert not await page.evaluate('document.documentElement.scrollWidth>innerWidth')
      await page.get_by_role('button',name='Close network ledger').click()
      for tab in ['Settings','My Campaigns','Ask BrandForge']:
       await page.get_by_role('button',name=tab,exact=True).click();await page.get_by_role('heading',name=tab,exact=True).wait_for()
       if tab=='Settings':
        await page.get_by_role('button',name='Edit',exact=True).click()
        attribution=page.get_by_role('checkbox',name='Include “Prepared with BrandForge OS” in client-facing exports')
        await attribution.uncheck()
        await page.get_by_role('button',name='Save Brand Brain',exact=True).click()
        await page.get_by_text('Brand Brain saved. Future campaigns will use these guardrails.').wait_for()
        assert not client.get('/api/clients').json()['active']['show_brandforge_branding']
        assert not await attribution.is_checked()
       await page.evaluate(AXE);v=await page.evaluate("async()=> (await axe.run()).violations.map(v=>({id:v.id,nodes:v.nodes.map(n=>({target:n.target,summary:n.failureSummary}))}))")
       ov=await page.evaluate('document.documentElement.scrollWidth>innerWidth')
       results.append({'theme':theme,'width':width,'state':tab,'axe':v,'overflow':ov,'errors':list(errors)})
      failed_session=True;await page.reload(wait_until='networkidle');await page.get_by_role('button',name='Reload workspace',exact=True).wait_for()
      assert 'could not connect' in await page.locator('h1').text_content()
      failed_session=False;await page.get_by_role('button',name='Reload workspace',exact=True).click();await page.wait_for_selector('#product-name-input')
      results.append({'theme':theme,'width':width,'state':'failed session and reload recovery','errors':list(errors)})
      if theme=='light' and width==390:
       await page.locator('#product-name-input').fill('Native bridge coffee');await page.locator('#campaign-no-ai').check();await page.get_by_role('button',name=re.compile('Create My Campaign')).click()
       await page.get_by_role('button',name='View Campaign',exact=True).wait_for(timeout=60000);await page.get_by_role('button',name='View Campaign',exact=True).click()
       await page.get_by_role('button',name='Open selected campaign in canvas',exact=True).wait_for();page.once('dialog',lambda d:d.accept());await page.get_by_role('button',name='Open selected campaign in canvas',exact=True).click()
       await page.wait_for_url('**/canvas/');await page.wait_for_function("document.querySelector('#layers')?.textContent.includes('image')")
       assert await page.locator('#copy').input_value()
       results.append({'theme':theme,'width':width,'state':'actual no-AI generation and historical-artwork canvas bridge','errors':list(errors)})

      await context.close()
    await browser.close()
 (OUT/'results.json').write_text(json.dumps(results,indent=2));bad=[r for r in results if r.get('axe') or r.get('overflow') or r.get('errors')];print(json.dumps({'states':len(results),'failures':bad},indent=2));assert not bad
asyncio.run(main())
