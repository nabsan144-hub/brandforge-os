"""Offline Chromium: real engine/renderer fixtures + shipped correction form,
uncertain-save retry, reviewed ZIP, and exact visual restore. No live services.
"""
import base64,asyncio,hashlib,io,json,mimetypes,os,subprocess,zipfile
from pathlib import Path
from urllib.parse import urlparse
from PIL import Image
from playwright.async_api import async_playwright
ROOT=Path(__file__).resolve().parents[1];OUT=Path(os.environ.get('BRANDFORGE_QA_DIR',str(ROOT/'qa-results/vector-corrections')));OUT.mkdir(parents=True,exist_ok=True)
subprocess.run(['node',str(ROOT/'scripts/make_vector_correction_fixture.mjs'),str(OUT)],check=True,cwd=ROOT)
FIX=json.loads((OUT/'fixtures.json').read_text());ORIGIN='https://correction.example.test'
AXE=(ROOT/'cloud/node_modules/axe-core/axe.min.js').read_text()
HEADERS={h['key']:h['value'] for rule in json.loads((ROOT/'cloud/vercel.json').read_text())['headers'] if rule['source']=='/(.*)' for h in rule['headers']}
async def main():
 results=[]
 async with async_playwright() as p:
  browser=await p.chromium.launch(args=['--no-sandbox'])
  for theme in ['light','dark']:
   for width in [390,1440]:
    c=json.loads(json.dumps(FIX['before']));calls=[];errors=[];downloads=[]
    async def route(r):
     nonlocal c
     u=urlparse(r.request.url);path=u.path
     if u.hostname!=urlparse(ORIGIN).hostname:return await r.abort()
     if path=='/vendor/supabase.mjs':return await r.fulfill(content_type='application/javascript',body="export function createClient(){return {auth:{onAuthStateChange(){},async getSession(){return {data:{session:{access_token:'fixture',user:{id:'owner'}}}}}}}}")
     if path=='/api/config':data={'supabaseUrl':ORIGIN,'supabaseAnonKey':'fixture','adSizes':FIX['sizes'],'images':{'enabled':False},'vectorCorrectionsEnabled':True}
     elif path=='/api/me':data={'plan':'free','limits':FIX['limits'],'usage':{'campaigns_lifetime':1},'plan_status':'active'}
     elif path=='/api/brands':data={'brands':[]}
     elif path=='/api/me/keys':data={'providers':[]}
     elif path=='/api/campaigns':data={'campaigns':[c],'total':1,'has_more':False}
     elif path=='/api/campaigns/'+c['id']+'/visuals':
      assert r.request.headers.get('x-brandforge-visuals')=='vector-corrections-v1'
      b=json.loads(r.request.post_data);calls.append(b);assert b['visual_fields']==FIX['fields'] and b['revision']==1
      assert b['visual_layout']['logo_rights'] is True and b['visual_layout']['logo'].startswith('data:image/png;base64,')
      c=json.loads(json.dumps(FIX['after']))
      if len(calls)==1:return await r.fulfill(status=503,json={'error':'Save could not be confirmed. Retry this same correction.'})
      assert calls[0]['request_id']==b['request_id'];data={'ok':True,'id':c['id'],'revision':2,'replayed':True}
     elif path=='/api/campaigns/'+c['id']:
      assert r.request.headers.get('x-brandforge-visuals')=='vector-corrections-v1'
      if r.request.method=='PATCH':
       b=json.loads(r.request.post_data);assert b['revision']==2
       if b.get('acknowledge_visuals'):c['visual_review_ack_revision']=2;c['visual_review_ack_at']='2026-09-11T00:00:00Z'
       else:assert b.get('restore_revision')==1;c=json.loads(json.dumps(FIX['restored']))
      data=c
     else:
      file=ROOT/'cloud/public'/('index.html' if path=='/' else path.lstrip('/'))
      if file.is_file():return await r.fulfill(body=file.read_bytes(),headers=HEADERS,content_type=mimetypes.guess_type(str(file))[0] or 'application/octet-stream')
      return await r.fulfill(status=404,body='Not found')
     await r.fulfill(json=data)
    context=await browser.new_context(viewport={'width':width,'height':1000},reduced_motion='reduce');await context.route('**/*',route);await context.add_init_script(f"localStorage.setItem('brandforge-theme','{theme}')")
    page=await context.new_page();page.on('pageerror',lambda e:errors.append(str(e)));page.on('download',lambda d:downloads.append(d))
    await page.goto(ORIGIN);await page.locator('#camp-list [data-id]').click();await page.locator('#d-visual-edit').click()
    for k,v in FIX['fields'].items():await page.locator('#visual-'+k).fill(v)
    await page.locator('#visual-logo-replacement').set_input_files(str(OUT/'replacement-logo.png'))
    await page.wait_for_function("()=>!document.querySelector('#visual-correction-form button[type=submit]').disabled")
    await page.get_by_role('button',name='Save and redraw vectors',exact=True).click()
    assert not calls and 'Confirm rights' in await page.locator('#d-action-msg').inner_text()
    await page.locator('#visual-logo-rights').check()
    if os.environ.get('BF_QA_SCENE')=='1':assert await page.locator('#visual-photo-fit').count()==0
    await page.evaluate(AXE);violations=await page.evaluate("async()=> (await axe.run()).violations.map(v=>({id:v.id,nodes:v.nodes.map(n=>n.target)}))")
    assert not violations,violations
    await page.locator('#visual-correction-form').scroll_into_view_if_needed();await page.screenshot(path=str(OUT/f'form-{theme}-{width}.png'))
    await page.get_by_role('button',name='Save and redraw vectors',exact=True).click();await page.wait_for_function("()=>document.querySelector('#d-action-msg').textContent.includes('could not be confirmed')")
    await page.get_by_role('button',name='Save and redraw vectors',exact=True).click();await page.wait_for_function("()=>document.querySelector('#d-field-report').textContent.includes('headline omitted')")
    await page.locator('#d-zip').click();assert not downloads;assert 'Review the copy' in await page.locator('#d-action-msg').inner_text()
    page.once('dialog',lambda d:d.accept());await page.locator('#d-review-ack').click();await page.wait_for_selector('#d-review-ack',state='hidden')
    async with page.expect_download() as info:await page.locator('#d-zip').click()
    downloaded=await info.value;target=OUT/f'corrected-{theme}-{width}.zip';await downloaded.save_as(target)
    with zipfile.ZipFile(target) as z:
     assert json.loads(z.read('VISUAL-FIELDS.json'))['fields']==FIX['fields']
     assert z.read('copy.md').decode()==FIX['before']['copy']
     for entry in json.loads(z.read('manifest.json'))['files']:assert hashlib.sha256(z.read(entry['name'])).hexdigest()==entry['sha256']
     for f in FIX['after']['files']:
      assert z.read('visuals/'+f['name'])==(base64.b64decode(f['content']) if f.get('encoding')=='base64' else f['content'].encode())
      if f['name'].endswith('.svg'):assert 'data-watermark="brandforge"' in f['content']
     im=Image.open(io.BytesIO(z.read('visuals/hero_banner.png'))).convert('RGB');assert im.size==(1200,630)
     pixels=list(im.crop((0,602,1200,630)).get_flattened_data());assert sum(1 for r,g,b in pixels if min(r,g,b)>170)>5
     (OUT/f'corrected-hero-{theme}-{width}.png').write_bytes(z.read('visuals/hero_banner.png'))
    await page.locator('#d-revisions').select_option('1');page.once('dialog',lambda d:d.accept());await page.locator('#d-restore').click();await page.wait_for_function("()=>document.querySelector('#d-stage-status').textContent.startsWith('Version 3.')")
    await page.locator('#d-visual-edit').click();assert await page.locator('#visual-headline').input_value()==FIX['before']['visual_fields']['headline']
    assert c['files']==FIX['before']['files'];assert len(calls)==2 and len(downloads)==1 and not errors,errors
    overflow=await page.evaluate('document.documentElement.scrollWidth>innerWidth');assert not overflow
    results.append({'theme':theme,'width':width,'uncertain_retry_same_id':True,'canonical_fields_saved':True,'omitted_fields_reported':True,'review_required':True,'free_watermark_svg_png':True,'zip_sha256':'pass','restore_original_fields_and_bytes':True,'copy_unchanged':True,'page_errors':errors,'axe':violations,'overflow':overflow})
    await context.close()
  await browser.close()
 (OUT/'results.json').write_text(json.dumps(results,indent=2));print(json.dumps({'views':4,'correction_retry_export_restore':'pass','axe_violations':0,'overflow':0,'page_errors':0}))
asyncio.run(main())
