"""Offline Chromium regression for the shipped Cloud UI; all network is stubbed.
Requires: pip install playwright; playwright install --with-deps chromium
Run after npm ci --prefix cloud. No real account, provider, email or payment.
"""
import asyncio
import json
import mimetypes
import os
from pathlib import Path
import subprocess
from urllib.parse import urlparse
from playwright.async_api import async_playwright

ROOT = Path(__file__).resolve().parents[1]
OUT = Path(os.environ.get('BRANDFORGE_QA_DIR', str(ROOT / 'qa-results/image-consent')))
OUT.mkdir(parents=True, exist_ok=True)
subprocess.run(['node', str(ROOT / 'scripts/make_browser_fixture.mjs'), str(OUT)], check=True, cwd=ROOT)
FIXTURE = json.loads((OUT / 'cloud-fixture.json').read_text())
ORIGIN = 'https://image-consent.example.test'
AXE = (ROOT / 'cloud/node_modules/axe-core/axe.min.js').read_text()

async def main():
 results = []
 async with async_playwright() as p:
  browser = await p.chromium.launch(args=['--no-sandbox'])
  for plan in ['free', 'pro']:
   for theme in ['dark', 'light']:
    for width in [390, 1440]:
     errors, submissions = [], []
     campaign = {**FIXTURE['campaign'], 'visual_status': {'mode':'svg', 'state':'fallback', 'provider':'openai', 'model':'gpt-image-1', 'reason':'VISUAL_RATE_LIMIT', 'scope':'hero_only'}}
     async def route(r):
      u=urlparse(r.request.url)
      if u.hostname != urlparse(ORIGIN).hostname:
       return await r.abort()
      path=u.path
      if path=='/vendor/supabase.mjs':
       return await r.fulfill(content_type='application/javascript', body="export function createClient(){return {auth:{onAuthStateChange(){},async getSession(){return {data:{session:{access_token:'fixture',user:{id:'test',email:'fixture@example.test'}}}}}}}}")
      if path=='/api/config':
       data={'supabaseUrl':ORIGIN, 'supabaseAnonKey':'fixture', 'adSizes':FIXTURE['sizes'], 'images':{'enabled':True, 'provider':'openai', 'model':'gpt-image-1'}, 'whatsappEnabled':False}
      elif path=='/api/me':
       data={'plan':plan,'limits':FIXTURE['limits'][plan],'usage':{'campaigns_lifetime':0,'campaigns_this_month':0},'plan_status':'active'}
      elif path=='/api/brands': data={'brands':[]}
      elif path=='/api/me/keys': data={'providers':[]}
      elif path=='/api/campaigns' and r.request.method=='POST':
       submissions.append(json.loads(r.request.post_data))
       data={'id':campaign['id'],'visual_status':campaign['visual_status']}
      elif path=='/api/campaigns': data={'campaigns':[],'total':0,'has_more':False}
      elif path=='/api/campaigns/'+campaign['id']: data=campaign
      else:
       f=ROOT/'cloud/public'/('index.html' if path=='/' else path.lstrip('/'))
       if f.is_file(): return await r.fulfill(body=f.read_bytes(),content_type=mimetypes.guess_type(str(f))[0] or 'application/octet-stream')
       return await r.fulfill(status=404,body='Not found')
      await r.fulfill(content_type='application/json',body=json.dumps(data))
     context=await browser.new_context(viewport={'width':width,'height':900},reduced_motion='reduce')
     await context.route('**/*',route)
     await context.add_init_script(f"localStorage.setItem('brandforge-theme','{theme}')")
     page=await context.new_page();page.on('pageerror',lambda e:errors.append(str(e)))
     await page.goto(ORIGIN+'/',wait_until='networkidle')
     box=page.locator('#c-images')
     await page.wait_for_function("window.__bfMe !== undefined")
     assert not await box.is_checked()
     assert await box.is_disabled() == (plan=='free')
     if plan=='pro':
      assert 'openai' in await page.locator('#image-consent-help').inner_text()
      assert 'not sent' in await page.locator('#image-consent-help').inner_text()
      await box.check()
     await page.locator('#c-provider').select_option('offline')
     assert await box.is_disabled() and not await box.is_checked()
     assert 'no text or image model' in await page.locator('#image-consent-help').inner_text()
     await page.locator('#c-provider').select_option('auto')
     assert not await box.is_checked()
     if plan=='pro':await box.check()
     await page.locator('#c-product').fill('Audit Coffee')
     await page.locator('#c-go').click()
     await page.wait_for_selector('#detail:not(.hidden)')
     assert submissions[-1]['visuals_ai']==(plan=='pro')
     assert submissions[-1]['visual_provider']==('openai' if plan=='pro' else '')
     assert 'Image: fallback' in await page.locator('#d-stage-status').inner_text()
     assert 'visual rate limit' in await page.locator('#d-stage-status').inner_text()
     await page.locator('#d-duplicate').click()
     assert not await box.is_checked(), 'Reusing a brief must reset image consent'
     await page.evaluate(AXE)
     violations=await page.evaluate("async()=> (await axe.run()).violations.map(v=>({id:v.id,nodes:v.nodes.map(n=>n.target)}))")
     overflow=await page.evaluate('document.documentElement.scrollWidth > innerWidth')
     await box.scroll_into_view_if_needed()
     if plan=='pro':await page.screenshot(path=str(OUT/f'consent-{theme}-{width}.png'))
     results.append({'plan':plan,'theme':theme,'width':width,'page_errors':errors,'axe':violations,'overflow':overflow,'consent_and_submission':'pass'})
     await context.close()
  await browser.close()
 (OUT/'results.json').write_text(json.dumps(results,indent=2))
 assert not any(x['page_errors'] or x['axe'] or x['overflow'] for x in results), results
 print(json.dumps({'views':len(results),'consent_flows':'passed','axe_violations':0,'page_errors':0,'overflow':0}))

asyncio.run(main())
