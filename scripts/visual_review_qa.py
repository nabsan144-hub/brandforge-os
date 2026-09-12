"""Actual Cloud UI edit/review/export flows in offline Chromium. SQL behavior is
covered separately by real PGlite tests. No account, provider or payment calls.
"""
import asyncio,json,mimetypes,os,subprocess,zipfile,hashlib
from pathlib import Path
from urllib.parse import urlparse
from playwright.async_api import async_playwright
ROOT=Path(__file__).resolve().parents[1];OUT=Path(os.environ.get('BRANDFORGE_QA_DIR',str(ROOT/'qa-results/visual-review')));OUT.mkdir(parents=True,exist_ok=True)
subprocess.run(['node',str(ROOT/'scripts/make_browser_fixture.mjs'),str(OUT)],check=True,cwd=ROOT)
FIXTURE=json.loads((OUT/'cloud-fixture.json').read_text());ORIGIN='https://review.example.test'
AXE=(ROOT/'cloud/node_modules/axe-core/axe.min.js').read_text()
HEADERS={h['key']:h['value'] for rule in json.loads((ROOT/'cloud/vercel.json').read_text())['headers'] if rule['source']=='/(.*)' for h in rule['headers']}
async def dialog_click(page,selector,accept):
 async with page.expect_event('dialog') as info:
  click=asyncio.create_task(page.locator(selector).click())
 dialog=await info.value
 if accept:await dialog.accept()
 else:await dialog.dismiss()
 await click
async def main():
 results=[]
 async with async_playwright() as p:
  browser=await p.chromium.launch(args=['--no-sandbox'])
  for theme in ['light','dark']:
   for width in [390,1440]:
    c=json.loads(json.dumps(FIXTURE['campaign']));errors=[];downloads=[];patches=[]
    async def route(r):
     u=urlparse(r.request.url);path=u.path
     if u.hostname!=urlparse(ORIGIN).hostname:return await r.abort()
     if path=='/vendor/supabase.mjs':return await r.fulfill(content_type='application/javascript',body="export function createClient(){return {auth:{onAuthStateChange(){},async getSession(){return {data:{session:{access_token:'fixture',user:{id:'owner',email:'owner@example.test'}}}}}}}}")
     if path=='/api/config':data={'supabaseUrl':ORIGIN,'supabaseAnonKey':'fixture','adSizes':FIXTURE['sizes'],'images':{'enabled':False},'whatsappEnabled':False}
     elif path=='/api/me':data={'plan':'free','limits':FIXTURE['limits']['free'],'usage':{'campaigns_lifetime':1,'campaigns_this_month':1},'plan_status':'active'}
     elif path=='/api/brands':data={'brands':[]}
     elif path=='/api/me/keys':data={'providers':[]}
     elif path=='/api/campaigns':data={'campaigns':[c],'total':1,'has_more':False}
     elif path=='/api/billing/status':data={'plan':'free','plan_status':'active','plans':FIXTURE['plans'],'checkout_enabled':False,'subscriptions':[]}
     elif path=='/api/me/export':
      assert r.request.headers.get('x-brandforge-review')=='visual-review-v1'
      data={'schema':2,'page':0,'has_more':False,'next_page':None,'data':{'campaigns':[c]},'archive_notice':'Account archive, not a publish-ready pack.','visual_review_required':[{'id':c['id'],'revision':c['revision']}]}
     elif path=='/api/campaigns/'+c['id']:
      if r.request.method=='GET':await asyncio.sleep(.15)
      assert r.request.headers.get('x-brandforge-review')=='visual-review-v1'
      if r.request.method=='PATCH':
       b=json.loads(r.request.post_data);patches.append(b);assert b['revision']==c['revision']
       if b.get('acknowledge_visuals'):
        c['visual_review_ack_revision']=c['revision'];c['visual_review_ack_at']='2026-09-11T00:00:00Z'
       else:
        c['copy']=b['copy'];c['stage_status']['copy']={'state':'edited','provider':'human'};c['revision']+=1;c['visual_review_state']='review_required';c['visual_review_ack_revision']=None;c['visual_review_ack_at']=None
      data=c
     else:
      file=ROOT/'cloud/public'/('index.html' if path=='/' else path.lstrip('/'))
      if file.is_file():return await r.fulfill(body=file.read_bytes(),headers=HEADERS,content_type=mimetypes.guess_type(str(file))[0] or 'application/octet-stream')
      return await r.fulfill(status=404,body='Not found')
     await r.fulfill(json=data)
    context=await browser.new_context(viewport={'width':width,'height':1000},reduced_motion='reduce');await context.route('**/*',route);await context.add_init_script(f"localStorage.setItem('brandforge-theme','{theme}')")
    page=await context.new_page();page.on('pageerror',lambda e:errors.append(str(e)));page.on('download',lambda d:downloads.append(d))
    await page.goto(ORIGIN);await page.locator('#camp-list [data-id]').click();await page.wait_for_selector('#detail:not(.hidden)')
    await page.locator('[data-t=copy]').click();await page.locator('#d-edit').click();await page.locator('#section-editor').fill('Corrected headline. Price is now 250. CTA: Shop today.')
    await page.get_by_role('button',name='Save new version',exact=True).click();await page.wait_for_function("()=>document.querySelector('#d-visual-review').textContent.includes('Copy changed')")
    assert await page.locator('#d-review-ack').is_visible()
    assert 'copy: edited (you)' in await page.locator('#d-stage-status').inner_text()
    await page.locator('#d-zip').click();assert 'Review the copy' in await page.locator('#d-action-msg').inner_text();assert not downloads
    await page.locator('[data-t=files]').click();await page.get_by_role('button',name='Download source',exact=True).first.click();assert not downloads
    await page.get_by_role('button',name='PNG',exact=True).first.click();assert 'Review the copy' in await page.locator('#d-action-msg').inner_text();assert not downloads
    await page.evaluate(AXE);violations=await page.evaluate("async()=> (await axe.run()).violations.map(v=>({id:v.id,nodes:v.nodes.map(n=>n.target)}))")
    overflow=await page.evaluate('document.documentElement.scrollWidth>innerWidth');assert not violations and not overflow,(violations,overflow)
    await page.locator('#d-visual-review').scroll_into_view_if_needed();await page.screenshot(path=str(OUT/f'review-{theme}-{width}.png'))
    # Data portability requires an archive-specific warning, not approval of visuals.
    await page.locator('#nav-billing').click();await page.wait_for_selector('#account-export:visible')
    await dialog_click(page,'#account-export',False);await page.wait_for_function('()=>!document.querySelector("#account-export").disabled');assert not downloads
    async with page.expect_download() as info:await dialog_click(page,'#account-export',True)
    downloaded=await info.value;data=json.loads(Path(await downloaded.path()).read_text());assert data['archive_review_acknowledged'] is True;assert data['data']['campaigns'][0]['visual_review_ack_revision'] is None
    await page.locator('#bill-back').click();await page.wait_for_selector('#d-review-ack:visible');assert await page.locator('#detail').get_attribute('aria-busy')=='false'
    await dialog_click(page,'#d-review-ack',False);assert len(patches)==1
    await dialog_click(page,'#d-review-ack',True);await page.wait_for_selector('#d-review-ack',state='hidden')
    assert c['revision']==2 and len(patches)==2
    async with page.expect_download() as info:await page.locator('#d-zip').click()
    downloaded=await info.value;target=OUT/f'reviewed-{theme}-{width}.zip';await downloaded.save_as(target)
    with zipfile.ZipFile(target) as z:
     note=z.read('COPY-VISUAL-REVIEW.txt').decode();assert 'NOT been redrawn' in note and 'version 2' in note
     for f in c['files']:assert z.read('visuals/'+f['name']).decode()==f['content']
     for entry in json.loads(z.read('manifest.json'))['files']:assert hashlib.sha256(z.read(entry['name'])).hexdigest()==entry['sha256']
    assert len(downloads)==2 and not errors,errors
    results.append({'theme':theme,'width':width,'unreviewed_zip_source_png_blocked':True,'archive_warning_cancel_accept':True,'ack_cancel_accept':True,'review_note_in_zip':True,'original_visual_bytes_preserved':True,'zip_sha256':'pass','page_errors':errors,'axe':violations,'overflow':overflow})
    await context.close()
  await browser.close()
 (OUT/'results.json').write_text(json.dumps(results,indent=2));print(json.dumps({'views':4,'review_and_export_flows':'pass','axe_violations':0,'overflow':0,'page_errors':0}))
asyncio.run(main())
