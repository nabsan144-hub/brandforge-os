"""Cloud UI + actual input validator/renderer, with auth/storage mocked.
SQL, permissions, preview non-mutation and saved quotas are tested separately.
"""
import asyncio,json,mimetypes,os,subprocess,zipfile,hashlib
from pathlib import Path
from urllib.parse import urlparse
from PIL import Image,ImageDraw
from playwright.async_api import async_playwright
ROOT=Path(__file__).resolve().parents[1];OUT=Path(os.environ.get('BRANDFORGE_QA_DIR',str(ROOT/'qa-results/product')));OUT.mkdir(parents=True,exist_ok=True)
subprocess.run(['node','scripts/make_browser_fixture.mjs',str(OUT)],cwd=ROOT,check=True)
FIXTURE=json.loads((OUT/'cloud-fixture.json').read_text());ORIGIN='https://product.example.test'
image=Image.new('RGB',(300,180),'white');draw=ImageDraw.Draw(image);draw.rectangle((60,10,240,170),fill='#AE542A');draw.rectangle((0,0,12,12),fill='#FF0000');draw.rectangle((287,167,299,179),fill='#0000FF');image.save(OUT/'test-product.jpg')
AXE=(ROOT/'cloud/node_modules/axe-core/axe.min.js').read_text()
HEADERS={h['key']:h['value'] for rule in json.loads((ROOT/'cloud/vercel.json').read_text())['headers'] if rule['source']=='/(.*)' for h in rule['headers']}
async def main():
 results=[]
 async with async_playwright() as p:
  browser=await p.chromium.launch(args=['--no-sandbox'])
  for plan in ['free','pro']:
   for theme in ['light','dark']:
    for width in [390,1440]:
     saved=None;creates=0;previews=0;errors=[];external=[]
     async def route(r):
      nonlocal saved,creates,previews
      u=urlparse(r.request.url);path=u.path
      if u.hostname!=urlparse(ORIGIN).hostname:external.append(r.request.url);return await r.abort()
      if path=='/vendor/supabase.mjs':return await r.fulfill(content_type='application/javascript',body="export function createClient(){return {auth:{onAuthStateChange(){},async getSession(){return {data:{session:{access_token:'fixture',user:{id:'owner',email:'owner@example.test'}}}}}}}}")
      if path=='/api/config':data={'supabaseUrl':ORIGIN,'supabaseAnonKey':'fixture','adSizes':FIXTURE['sizes'],'images':{'enabled':True,'provider':'openai','model':'gpt-image-1'}}
      elif path=='/api/me':data={'plan':plan,'limits':FIXTURE['limits'][plan],'usage':{'campaigns_lifetime':creates,'campaigns_this_month':creates}}
      elif path=='/api/brands':data={'brands':[]}
      elif path=='/api/me/keys':data={'providers':[]}
      elif path in ['/api/campaign-preview','/api/campaigns'] and r.request.method=='POST':
       is_preview=path.endswith('preview');body=json.loads(r.request.post_data)
       result=await asyncio.to_thread(subprocess.run,['node','scripts/render_product_fixture.mjs'],cwd=ROOT,input=json.dumps({'body':body,'plan':plan,'preview':is_preview}),capture_output=True,text=True,check=True)
       rendered=json.loads(result.stdout)
       if not rendered['ok']:return await r.fulfill(status=rendered['status'],json={'error':rendered['error']})
       data=rendered['data']
       if is_preview:previews+=1
       else:creates+=1;saved=data
      elif path=='/api/campaigns':data={'campaigns':[saved] if saved else [],'total':creates,'has_more':False}
      elif saved and path=='/api/campaigns/'+saved['id']:data=saved
      else:
       f=ROOT/'cloud/public'/('index.html' if path=='/' else path.lstrip('/'))
       if f.is_file():return await r.fulfill(body=f.read_bytes(),headers=HEADERS,content_type=mimetypes.guess_type(str(f))[0] or 'application/octet-stream')
       return await r.fulfill(status=404,body='Not found')
      await r.fulfill(json=data)
     context=await browser.new_context(viewport={'width':width,'height':1000},reduced_motion='reduce',accept_downloads=True);await context.route('**/*',route);await context.add_init_script(f"localStorage.setItem('brandforge-theme','{theme}')")
     page=await context.new_page();page.on('pageerror',lambda e:errors.append(str(e)))
     await page.goto(ORIGIN);await page.wait_for_function('()=>window.__bfMe!==undefined')
     await page.fill('#c-product','Northline Coffee');await page.fill('#c-ben','Whole beans; Small batches')
     await page.locator('details').filter(has=page.locator('#c-cta')).locator('summary').click();await page.fill('#c-offer','250 g / Rs 1450');await page.fill('#c-cta','View the roasts')
     await page.locator('details').filter(has=page.locator('#product-photo')).locator('summary').click();await page.set_input_files('#product-photo',OUT/'test-product.jpg');await page.wait_for_function("()=>document.querySelector('#product-photo-preview').getAttribute('src')")
     assert await page.input_value('#c-style')=='product-v1';assert await page.locator('#c-images').is_disabled()
     await page.click('#template-preview');await page.wait_for_function("()=>document.querySelector('#run-msg').textContent.includes('permission')");assert creates==0 and previews==0
     await page.check('#product-photo-rights');await page.click('#template-preview');await page.wait_for_selector('#template-preview-panel:not(.hidden)');assert creates==0 and previews==1
     await page.fill('#c-offer','500 g / Rs 2700');assert await page.locator('#template-preview-panel').evaluate("e=>e.classList.contains('hidden')")
     await page.click('#template-preview');await page.fill('#c-offer','250 g / Rs 1450')
     await page.wait_for_function("()=>!document.querySelector('#template-preview').disabled")
     assert await page.locator('#template-preview-panel').evaluate("e=>e.classList.contains('hidden')")
     await page.click('#template-preview');await page.wait_for_selector('#template-preview-panel:not(.hidden)');assert creates==0 and previews==3
     for option in await page.locator('#template-preview-size option').evaluate_all('(els)=>els.map(x=>x.value)'):
      await page.select_option('#template-preview-size',option);await page.wait_for_function("()=>document.querySelector('#template-preview-image').complete && document.querySelector('#template-preview-image').naturalWidth>0")
     await page.evaluate(AXE);violations=await page.evaluate("async()=> (await axe.run()).violations.map(v=>({id:v.id,nodes:v.nodes.map(n=>n.target)}))")
     assert not violations,violations;assert not await page.evaluate('document.documentElement.scrollWidth>innerWidth')
     await page.locator('#template-preview-panel').scroll_into_view_if_needed();await page.screenshot(path=str(OUT/f'product-{plan}-{theme}-{width}.png'))
     await page.click('#c-go');await page.wait_for_selector('#detail:not(.hidden)');assert creates==1;assert saved['visual_status']['mode']=='uploaded'
     async with page.expect_download() as info:await page.click('#d-zip')
     download=await info.value;path=OUT/f'product-{plan}-{theme}-{width}.zip';await download.save_as(path)
     with zipfile.ZipFile(path) as z:
      assert 'visuals/approved_product_photo.jpg' in z.namelist();assert 'EXPORT-WARNINGS.txt' not in z.namelist()
      for entry in json.loads(z.read('manifest.json'))['files']:assert hashlib.sha256(z.read(entry['name'])).hexdigest()==entry['sha256']
      for f in saved['files']:
       if f['name'].endswith('.svg'):assert ('data-watermark="brandforge"' in f['content'])==(plan=='free')
     assert not errors and not external,(errors,external)
     results.append({'plan':plan,'theme':theme,'width':width,'rights_enforced':True,'preview_creates':0,'saved_creates':creates,'zip_hashes':'pass','axe':violations,'errors':errors})
     await context.close()
  await browser.close()
 (OUT/'results.json').write_text(json.dumps(results,indent=2));print(json.dumps({'views':len(results),'result':'passed'}))
asyncio.run(main())
