"""Shipped Cloud UI: opt-in choice, diagnostics, SVG/PNG/ZIP under actual CSP."""
import asyncio,hashlib,io,json,mimetypes,os,subprocess,zipfile
from pathlib import Path
from urllib.parse import urlparse
from PIL import Image
from playwright.async_api import async_playwright
ROOT=Path(__file__).resolve().parents[1];OUT=Path(os.environ.get('BRANDFORGE_QA_DIR',str(ROOT/'qa-results/editorial-workspace')));OUT.mkdir(parents=True,exist_ok=True)
subprocess.run(['node',str(ROOT/'scripts/make_editorial_fixture.mjs'),str(OUT)],cwd=ROOT,check=True)
CAM=json.loads((OUT/'campaign.json').read_text());FIX=json.loads((OUT/'fixtures.json').read_text());ORIGIN='https://editorial.example.test'
AXE=(ROOT/'cloud/node_modules/axe-core/axe.min.js').read_text()
HEADERS={h['key']:h['value'] for rule in json.loads((ROOT/'cloud/vercel.json').read_text())['headers'] if rule['source']=='/(.*)' for h in rule['headers']}
async def main():
 results=[]
 async with async_playwright() as p:
  browser=await p.chromium.launch(args=['--no-sandbox'])
  for theme in ['light','dark']:
   for width in [390,1440]:
    errors=[]
    async def route(r):
     u=urlparse(r.request.url);path=u.path
     if u.hostname!=urlparse(ORIGIN).hostname:return await r.abort()
     if path=='/vendor/supabase.mjs':return await r.fulfill(content_type='application/javascript',body="export function createClient(){return {auth:{onAuthStateChange(){},async getSession(){return {data:{session:{access_token:'fixture',user:{id:'owner'}}}}}}}}")
     if path=='/api/config':data={'supabaseUrl':ORIGIN,'supabaseAnonKey':'fixture','adSizes':FIX['sizes'],'images':{'enabled':False},'vectorCorrectionsEnabled':False}
     elif path=='/api/me':data={'plan':'free','limits':{'custom_presets':3,'watermark':True},'usage':{'campaigns_lifetime':1},'plan_status':'active'}
     elif path=='/api/brands':data={'brands':[]}
     elif path=='/api/me/keys':data={'providers':[]}
     elif path=='/api/campaigns':data={'campaigns':[CAM],'total':1,'has_more':False}
     elif path=='/api/campaigns/'+CAM['id']:data=CAM
     else:
      file=ROOT/'cloud/public'/('index.html' if path=='/' else path.lstrip('/'))
      if file.is_file():return await r.fulfill(body=file.read_bytes(),headers=HEADERS,content_type=mimetypes.guess_type(str(file))[0] or 'application/octet-stream')
      return await r.fulfill(status=404,body='Not found')
     await r.fulfill(json=data)
    ctx=await browser.new_context(viewport={'width':width,'height':1000},reduced_motion='reduce');await ctx.route('**/*',route);await ctx.add_init_script(f"localStorage.setItem('brandforge-theme','{theme}')")
    page=await ctx.new_page();page.on('pageerror',lambda e:errors.append(str(e)));await page.goto(ORIGIN)
    # Verify the new control without changing default selection or image consent.
    assert await page.locator('#c-style').input_value()=='bold'
    assert await page.locator('#c-style option[value="editorial-v1"]').count()==1
    consent=await page.locator('#c-images').is_checked()
    await page.locator('#c-style').select_option('editorial-v1')
    assert await page.locator('#c-style').input_value()=='editorial-v1'
    assert await page.locator('#c-images').is_checked()==consent
    assert 'omitted and reported' in await page.locator('#c-style-help').text_content()
    await page.locator('#camp-list [data-id]').click()
    await page.wait_for_function("()=>document.querySelector('#d-field-report').textContent.includes('NOT printed')")
    note=await page.locator('#d-field-report').text_content();assert 'NOT printed' in note and 'offer omitted in this format' in note
    await page.evaluate(AXE);axe=await page.evaluate("async()=> (await axe.run()).violations.map(v=>({id:v.id,nodes:v.nodes.map(n=>n.target)}))");assert not axe,axe
    assert not await page.evaluate('document.documentElement.scrollWidth>innerWidth')
    await page.screenshot(path=str(OUT/f'workspace-{theme}-{width}.png'))
    async with page.expect_download() as info:await page.locator('#d-zip').click()
    download=await info.value;target=OUT/f'editorial-{theme}-{width}.zip';await download.save_as(target)
    with zipfile.ZipFile(target) as z:
     quality=json.loads(z.read('VISUAL-QUALITY.json'));assert len(quality['formats'])==2
     assert any(f['status']=='omitted_format' for f in quality['formats'][1]['fields'])
     for f in json.loads(z.read('manifest.json'))['files']:assert hashlib.sha256(z.read(f['name'])).hexdigest()==f['sha256']
     assert z.read('copy.md').decode()==CAM['copy']
     assert z.read('visuals/hero_banner.svg').decode()==CAM['files'][0]['content']
     im=Image.open(io.BytesIO(z.read('visuals/hero_banner.png'))).convert('RGB');assert im.size==(1200,630)
     pixels=list(im.crop((0,602,1200,630)).get_flattened_data());assert sum(min(v)>170 for v in pixels)>5;assert sum(max(v)<80 for v in pixels)>len(pixels)*.8
    assert not errors,errors
    results.append({'theme':theme,'width':width,'opt_in_default_preserved':True,'omission_notice':True,'quality_manifest_sha256':True,'copy_unchanged':True,'free_svg_png_watermark':True,'axe':axe,'page_errors':errors,'overflow':False})
    await ctx.close()
  await browser.close()
 (OUT/'results.json').write_text(json.dumps(results,indent=2));print(json.dumps({'views':4,'diagnostics_export':'pass','axe':0,'overflow':0,'page_errors':0}))
asyncio.run(main())
