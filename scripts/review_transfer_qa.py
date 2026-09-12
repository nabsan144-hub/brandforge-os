"""Browser review/archive flows with hosted auth/storage mocked; SQL tested separately."""
import asyncio
import hashlib
import json
import mimetypes
import os
import zipfile
from pathlib import Path
from urllib.parse import urlparse
from playwright.async_api import async_playwright
ROOT=Path(__file__).resolve().parents[1]
OUT=Path(os.environ.get('BRANDFORGE_QA_DIR',ROOT/'qa-results/review-transfer'));OUT.mkdir(parents=True,exist_ok=True)
ORIGIN='https://review.example.test';TOKEN='a'*64
SAMPLE=json.loads((ROOT/'cloud/public/assets/practice/original.json').read_text())
HEADERS={h['key']:h['value'] for rule in json.loads((ROOT/'cloud/vercel.json').read_text())['headers'] if rule['source']=='/(.*)' for h in rule['headers']}
AXE=(ROOT/'cloud/node_modules/axe-core/axe.min.js').read_text()
async def main():
 results=[]
 async with async_playwright() as pw:
  browser=await pw.chromium.launch(args=['--no-sandbox'])
  for theme in ['light','dark']:
   for width in [390,1440]:
    comments=[];active=True;errors=[];external=[];archives={};imports=0
    async def route(r):
     nonlocal imports
     u=urlparse(r.request.url);path=u.path
     if u.hostname!=urlparse(ORIGIN).hostname:external.append(r.request.url);return await r.abort()
     if path=='/api/review':
      assert r.request.headers['authorization']=='Bearer '+TOKEN
      if not active:return await r.fulfill(status=404,json={'error':'Review revoked.'})
      if r.request.method=='POST':comments.append(json.loads(r.request.post_data))
      return await r.fulfill(json={'ok':True,'campaign':SAMPLE,'review':{'revision':1,'expires_at':'2026-09-18T00:00:00Z','status':comments[-1]['decision'] if comments else 'pending','comments':comments}})
     if path=='/vendor/supabase.mjs':return await r.fulfill(content_type='application/javascript',body="export function createClient(){return {auth:{async getSession(){return {data:{session:{access_token:'fixture'}}}}}}}")
     if path=='/api/config':return await r.fulfill(json={'supabaseUrl':ORIGIN,'supabaseAnonKey':'fixture'})
     if path=='/api/transfers':
      if r.request.method=='POST':
       b=json.loads(r.request.post_data);imports+=1;archives[b['request_id']]=b['pack'];return await r.fulfill(json={'ok':True,'id':b['request_id']})
      if u.query:
       key=u.query.split('=')[-1]
       if r.request.method=='DELETE':archives.pop(key,None);return await r.fulfill(json={'ok':True})
       return await r.fulfill(json={'pack':archives[key]})
      return await r.fulfill(json={'archives':[{'id':key,'name':p['name']} for key,p in archives.items()]})
     f=ROOT/'cloud/public'/({'/review':'review.html','/transfer':'transfer.html'}.get(path,path.lstrip('/')))
     if f.is_file():return await r.fulfill(body=f.read_bytes(),headers=HEADERS,content_type=mimetypes.guess_type(str(f))[0] or 'application/octet-stream')
     return await r.fulfill(status=404,body='Not found')
    c=await browser.new_context(viewport={'width':width,'height':1000},color_scheme=theme,reduced_motion='reduce',accept_downloads=True)
    await c.route('**/*',route);page=await c.new_page();page.on('pageerror',lambda e:errors.append(str(e)))
    await page.goto(ORIGIN+'/review#'+TOKEN);await page.wait_for_selector('#pack:not([hidden])')
    await page.fill('#name','<img src=x onerror=alert(1)>');await page.fill('#note','Please use this version.');await page.select_option('#decision','approved');await page.click('#send');await page.wait_for_function("()=>document.querySelector('#message').textContent.includes('recorded')")
    assert await page.locator('#comments img').count()==0
    async with page.expect_download() as d:await page.click('#download')
    path=OUT/f'review-{theme}-{width}.zip';await(await d.value).save_as(path)
    with zipfile.ZipFile(path) as z:
     for f in json.loads(z.read('manifest.json'))['files']:assert hashlib.sha256(z.read(f['name'])).hexdigest()==f['sha256']
    await page.evaluate(AXE);assert not await page.evaluate('async()=> (await axe.run()).violations')
    assert not await page.evaluate('document.documentElement.scrollWidth>innerWidth')
    await page.screenshot(path=str(OUT/f'review-{theme}-{width}.png'),full_page=True)
    active=False;await page.click('#refresh');await page.wait_for_function("()=>document.querySelector('#message').textContent.includes('revoked')");assert await page.locator('#pack').get_attribute('hidden') is not None
    # Use the actual exporter and validators; no arbitrary successful import fixture.
    await page.goto(ORIGIN+'/transfer');await page.wait_for_function("()=>document.querySelector('#message').textContent.includes('Ready')")
    portable=await page.evaluate("async c => (await import('/portable-pack.js')).exportPortable(c)",SAMPLE)
    p=OUT/'portable.json';p.write_text(json.dumps(portable,separators=(',',':')))
    await page.set_input_files('#file',p);await page.wait_for_selector('#inspection:not([hidden])');assert imports==0
    await page.click('#save');assert imports==0;await page.check('#consent');await page.click('#save');await page.wait_for_function("()=>document.querySelector('#message').textContent.includes('Archive saved')");assert imports==1
    async with page.expect_download() as d:await page.click('#export')
    p=OUT/f'portable-{theme}-{width}.json';await(await d.value).save_as(p);assert json.loads(p.read_text())==portable
    await page.evaluate(AXE);assert not await page.evaluate('async()=> (await axe.run()).violations')
    assert not await page.evaluate('document.documentElement.scrollWidth>innerWidth')
    await page.screenshot(path=str(OUT/f'transfer-{theme}-{width}.png'),full_page=True)
    bad={**portable,'version':999};p=OUT/'bad.json';p.write_text(json.dumps(bad));await page.set_input_files('#file',p);await page.wait_for_function("()=>document.querySelector('#message').textContent.includes('Unsupported')");assert imports==1
    assert not errors and not external,(errors,external)
    results.append({'theme':theme,'width':width,'review':'pass','archive':'pass','axe':0,'errors':errors,'external_requests':external})
    await c.close()
  await browser.close()
 (OUT/'results.json').write_text(json.dumps(results,indent=2));print(json.dumps({'views':8,'flows':'passed','axe':0,'errors':0,'external_requests':0}))
asyncio.run(main())
