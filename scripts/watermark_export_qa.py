"""Render real offline SVG fixtures through the shipped browser export code.
No external network. Checks pixel watermark presence in PNG/JPEG and ZIP hashes.
Requires Playwright Chromium, Pillow and cloud npm dependencies.
"""
import asyncio
import base64
import hashlib
import io
import json
import mimetypes
import os
from pathlib import Path
import subprocess
from urllib.parse import urlparse
import zipfile
from PIL import Image
from playwright.async_api import async_playwright

ROOT=Path(__file__).resolve().parents[1]
OUT=Path(os.environ.get('BRANDFORGE_QA_DIR',str(ROOT/'qa-results/watermark')))
OUT.mkdir(parents=True,exist_ok=True)
subprocess.run(['node',str(ROOT/'scripts/make_watermark_fixture.mjs'),str(OUT)],check=True,cwd=ROOT)
fixtures=json.loads((OUT/'fixtures.json').read_text())
ORIGIN='https://watermark.example.test'

def check_footer(blob,fixture):
 im=Image.open(io.BytesIO(blob)).convert('RGB')
 assert im.size==(fixture['width'],fixture['height'])
 if fixture['free']:
  band=im.crop((0,im.height-fixture['footer'],im.width,im.height))
  # Actual dark footer and outlined white lettering, not just metadata strings.
  pixels=list(band.get_flattened_data() if hasattr(band,'get_flattened_data') else band.getdata())
  assert sum(1 for r,g,b in pixels if abs(r-16)<16 and abs(g-24)<16 and abs(b-32)<16)>len(pixels)*.5
  assert sum(1 for r,g,b in pixels if min(r,g,b)>170)>5
 return im

async def main():
 results=[]
 async with async_playwright() as p:
  browser=await p.chromium.launch(args=['--no-sandbox'])
  page=await browser.new_page(viewport={'width':1280,'height':920})
  errors=[];page.on('pageerror',lambda e:errors.append(str(e)))
  async def route(r):
   u=urlparse(r.request.url)
   if u.hostname!=urlparse(ORIGIN).hostname:return await r.abort()
   if u.path=='/':return await r.fulfill(content_type='text/html',body='<html><body></body></html>')
   if u.path=='/preview':return await r.fulfill(content_type='text/html',body=(OUT/'Watermark-Preview.html').read_text())
   f=ROOT/'cloud/public'/u.path.lstrip('/')
   if f.is_file():return await r.fulfill(body=f.read_bytes(),content_type=mimetypes.guess_type(str(f))[0] or 'application/octet-stream')
   await r.abort()
  await page.route('**/*',route);await page.goto(ORIGIN)
  for fixture in fixtures:
   for mime,ext in [('image/png','.png'),('image/jpeg','.jpg')]:
    b64=await page.evaluate('''async ({file,mime})=>{
      const {rasterize}=await import('/workspace-tools.js');
      const blob=await rasterize(file,mime);
      return await new Promise((ok,no)=>{const r=new FileReader();r.onload=()=>ok(r.result.split(',')[1]);r.onerror=no;r.readAsDataURL(blob)});
    }''',{'file':fixture,'mime':mime})
    blob=base64.b64decode(b64);check_footer(blob,fixture)
    (OUT/fixture['name'].replace('.svg',ext)).write_bytes(blob)
    results.append({'file':fixture['name'],'format':mime,'dimensions':'pass','watermark_pixels':'pass' if fixture['free'] else 'not added (SVG assertion)'})
   assert ('data-watermark="brandforge"' in fixture['content'])==fixture['free']
  free=[{'name':f['name'],'content':f['content']} for f in fixtures if f['free']]
  packed=await page.evaluate('''async files=>{
   const {campaignZip}=await import('/workspace-tools.js');
   const result=await campaignZip({id:'fixture',name:'Free watermark sample',revision:1,visual_review_state:'unchanged',files});
   const data=await new Promise((ok,no)=>{const r=new FileReader();r.onload=()=>ok(r.result.split(',')[1]);r.onerror=no;r.readAsDataURL(result.blob)});
   return {data,warnings:result.warnings};
  }''',free)
  assert not packed['warnings'],packed['warnings']
  blob=base64.b64decode(packed['data']);(OUT/'Free-Watermark-Sample.zip').write_bytes(blob)
  with zipfile.ZipFile(io.BytesIO(blob)) as z:
   manifest=json.loads(z.read('manifest.json'))
   for entry in manifest['files']:
    assert hashlib.sha256(z.read(entry['name'])).hexdigest()==entry['sha256']
   for f in fixtures:
    if f['free']:
     assert b'data-watermark="brandforge"' in z.read('visuals/'+f['name'])
     check_footer(z.read('visuals/'+f['name'].replace('.svg','.png')),f)
  await page.goto(ORIGIN+'/preview');await page.screenshot(path=str(OUT/'Watermark-Preview.png'),full_page=True)
  assert not errors,errors
  await browser.close()
 report={'raster_checks':results,'zip_watermarks':'passed','manifest_checksums':'passed','page_errors':errors}
 (OUT/'results.json').write_text(json.dumps(report,indent=2))
 print(json.dumps({'raster_checks':len(results),'zip_watermarks':'passed','manifest_checksums':'passed','page_errors':len(errors)}))

asyncio.run(main())
