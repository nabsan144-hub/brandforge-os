"""Offline Chromium proof: backend-encoded private bundle -> verified files ->
real PNG/JPEG + ZIP + portable account JSON. No live storage or paid providers.
"""
import asyncio,base64,hashlib,io,json,mimetypes,os,subprocess,zipfile
from pathlib import Path
from urllib.parse import urlparse
from PIL import Image
from playwright.async_api import async_playwright
ROOT=Path(__file__).resolve().parents[1]
OUT=Path(os.environ.get('BRANDFORGE_QA_DIR',str(ROOT/'qa-results/private-assets')))
OUT.mkdir(parents=True,exist_ok=True)
subprocess.run(['node',str(ROOT/'scripts/make_watermark_fixture.mjs'),str(OUT)],check=True,cwd=ROOT)
# Use the actual server encoder, not a Python reimplementation of its contract.
subprocess.run(['node','--input-type=module','-e',"""
import {readFileSync,writeFileSync} from 'node:fs';
import {encodeAssetBundle} from './cloud/api/_lib/assets.js';
const out=process.argv[1];
const fixtures=JSON.parse(readFileSync(out+'/fixtures.json'));
const pack=encodeAssetBundle(fixtures.filter(f=>f.free).map(f=>({name:f.name,content:f.content})));
writeFileSync(out+'/bundle.json',pack.data);
writeFileSync(out+'/metadata.json',JSON.stringify({campaign:{id:'fixture',asset_bundle_id:'bundle-fixture',name:'Private Free pack',revision:1,visual_review_state:'unchanged',files:pack.manifest},auth:{url:'https://qa-storage.supabase.co/private/bundle.json?token=offline',schema:1,bytes:pack.data.length,sha256:pack.sha256}}));
""",str(OUT)],check=True,cwd=ROOT)
metadata=json.loads((OUT/'metadata.json').read_text())
fixtures={f['name']:f for f in json.loads((OUT/'fixtures.json').read_text()) if f['free']}
ORIGIN='https://assets.example.test'
async def main():
 async with async_playwright() as p:
  browser=await p.chromium.launch(args=['--no-sandbox']);page=await browser.new_page();errors=[];storage_requests=[]
  page.on('pageerror',lambda e:errors.append(str(e)))
  async def route(r):
   u=urlparse(r.request.url)
   if u.hostname=='qa-storage.supabase.co':
    storage_requests.append(r.request.headers)
    return await r.fulfill(body=(OUT/'bundle.json').read_bytes(),headers={'Content-Type':'application/json','Access-Control-Allow-Origin':ORIGIN})
   if u.hostname!=urlparse(ORIGIN).hostname:return await r.abort()
   if u.path=='/':return await r.fulfill(content_type='text/html',body='<html><body><h1>Private export QA</h1></body></html>')
   if u.path=='/campaigns/fixture/assets':return await r.fulfill(json=metadata['auth'])
   file=ROOT/'cloud/public'/u.path.lstrip('/')
   if file.is_file():return await r.fulfill(body=file.read_bytes(),content_type=mimetypes.guess_type(str(file))[0] or 'application/octet-stream')
   await r.abort()
  await page.route('**/*',route);await page.goto(ORIGIN)
  result=await page.evaluate('''async ({campaign})=>{
   const {hydrateCampaign,hydrateAccountExport}=await import('/private-assets.js');
   const {campaignZip,rasterize,fileBytes}=await import('/workspace-tools.js');
   const get=async path=>(await fetch(path)).json();
   let unresolved=false;try{fileBytes(campaign.files[0])}catch{unresolved=true}
   const hydrated=await hydrateCampaign(campaign,get,'https://qa-storage.supabase.co');
   const portable=await hydrateAccountExport({data:{campaigns:[campaign]}},get,'https://qa-storage.supabase.co');
   const asBase64=blob=>new Promise((ok,no)=>{const r=new FileReader();r.onload=()=>ok(r.result.split(',')[1]);r.onerror=no;r.readAsDataURL(blob)});
   const pack=await campaignZip(hydrated);
   const rasters=[];
   for(const file of hydrated.files)for(const type of ['image/png','image/jpeg'])rasters.push({name:file.name,type,data:await asBase64(await rasterize(file,type))});
   const denied=await hydrateCampaign(campaign,get,'https://qa-storage.supabase.co',async()=>new Response('expired',{status:403})).then(()=>false,()=>true);
   const corrupt=await hydrateCampaign(campaign,get,'https://qa-storage.supabase.co',async()=>new Response('corrupt')).then(()=>false,()=>true);
   return {zip:await asBase64(pack.blob),warnings:pack.warnings,rasters,portable,unresolved,denied,corrupt};
  }''',metadata)
  assert result['unresolved'] and result['denied'] and result['corrupt'] and not result['warnings']
  blob=base64.b64decode(result['zip']);(OUT/'Private-Free-Pack.zip').write_bytes(blob)
  with zipfile.ZipFile(io.BytesIO(blob)) as z:
   for entry in json.loads(z.read('manifest.json'))['files']:
    assert hashlib.sha256(z.read(entry['name'])).hexdigest()==entry['sha256']
   for name,f in fixtures.items():assert z.read('visuals/'+name).decode()==f['content']
  for item in result['rasters']:
   f=fixtures[item['name']];im=Image.open(io.BytesIO(base64.b64decode(item['data']))).convert('RGB')
   assert im.size==(f['width'],f['height'])
   band=im.crop((0,im.height-f['footer'],im.width,im.height))
   pixels=list(band.get_flattened_data() if hasattr(band,'get_flattened_data') else band.getdata())
   assert sum(1 for r,g,b in pixels if abs(r-16)<16 and abs(g-24)<16 and abs(b-32)<16)>len(pixels)*.5
   assert sum(1 for r,g,b in pixels if min(r,g,b)>170)>5
  portable=json.dumps(result['portable'],ensure_ascii=False)
  assert 'token=offline' not in portable
  for f in result['portable']['data']['campaigns'][0]['files']:assert f['content']==fixtures[f['name']]['content']
  (OUT/'Portable-Account.json').write_text(portable)
  assert len(storage_requests)==2
  assert all('authorization' not in r and 'cookie' not in r and 'referer' not in r for r in storage_requests)
  assert not errors,errors
  report={'backend_encoder':'actual','browser':'Chromium','network':'offline mocked private storage','hydrated_files':len(fixtures),'raster_watermark_checks':len(result['rasters']),'zip_sources_and_sha256':'pass','portable_account_bytes':'pass','signed_urls_not_persisted':'pass','no_storage_credentials_or_referrer':'pass','unresolved_files_rejected':'pass','expired_and_corrupt_downloads_rejected':'pass','page_errors':errors}
  (OUT/'results.json').write_text(json.dumps(report,indent=2));print(json.dumps(report,indent=2));await browser.close()
asyncio.run(main())
