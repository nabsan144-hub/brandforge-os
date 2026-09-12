import asyncio, json, mimetypes, pathlib, urllib.parse, zipfile, hashlib
from playwright.async_api import async_playwright
import os
ROOT=pathlib.Path(__file__).resolve().parents[1]; OUT=pathlib.Path(os.environ.get('BRANDFORGE_QA_DIR',str(ROOT/'qa-results')));OUT.mkdir(exist_ok=True,parents=True); SHOTS=OUT/'screenshots';SHOTS.mkdir(exist_ok=True)
CLOUD=ROOT/'cloud/public';FIXTURE='https://local-ui.brandforge.test'
import subprocess
subprocess.run(['node',str(ROOT/'scripts/make_browser_fixture.mjs'),str(OUT)],check=True,cwd=ROOT)
fixture=json.loads((OUT/'cloud-fixture.json').read_text())
axe=(ROOT/'sales/node_modules/axe-core/axe.min.js').read_text()
results=[]
async def audit(page,label):
 await page.evaluate(axe)
 d=await page.evaluate("async()=>{const r=await axe.run(document,{runOnly:{type:'tag',values:['wcag2a','wcag2aa','wcag21aa']}});return r.violations.map(v=>({id:v.id,impact:v.impact,nodes:v.nodes.map(n=>({target:n.target,summary:n.failureSummary})).slice(0,8)}));}")
 width=await page.evaluate('({viewport:innerWidth,page:document.documentElement.scrollWidth})')
 results.append({'view':label,'width':width,'axe':d})
 return d
async def main():
 async with async_playwright() as p:
  engine=os.environ.get('BF_BROWSER','chromium')
  browser=await getattr(p,engine).launch(headless=True,args=['--no-sandbox'] if engine=='chromium' else [])
  # The real static site, no external submissions.
  for theme in ['dark','light']:
   for width in [390,1440]:
    context=await browser.new_context(viewport={'width':width,'height':900},reduced_motion='reduce')
    await context.add_init_script(f"localStorage.setItem('brandforge-theme','{theme}');")
    async def local_only(route):
     if urllib.parse.urlparse(route.request.url).hostname not in ('127.0.0.1','localhost'):return await route.abort()
     return await route.continue_()
    await context.route('**/*',local_only)
    page=await context.new_page()
    for path in ['','pricing','tools','demo','privacy','terms','refund','docs','agents','workspace','404']:
     await page.goto('http://127.0.0.1:8765/'+(path+'.html' if path else 'index.html'),wait_until='networkidle')
     await page.evaluate("document.querySelectorAll('[data-rv]').forEach(x=>x.classList.add('in','is-visible','revealed'))")
     # Reveal animations must not hide contrast failures.
     await page.add_style_tag(content='[data-rv]{opacity:1!important;transform:none!important}')
     await audit(page,f'sales/{path or "home"}/{theme}/{width}')
     if path=='' and width==1440 and theme=='dark':await page.screenshot(path=str(SHOTS/'homepage-desktop.png'),full_page=True)
    await context.close()
  # Actual Cloud DOM/scripts, provider/auth API fixtures only. No real login,
  # provider generation, payment or delivery is performed in this harness.
  for theme in ['dark','light']:
   for width in [320,390,768,1440]:
    for plan in ['pro','agency']:
     requests=[]; errors=[];current=json.loads(json.dumps(fixture['campaign']));state={'authenticated':True,'patches':0}
     async def route(r):
      u=urllib.parse.urlparse(r.request.url);path=u.path
      requests.append({'path':path,'method':r.request.method,'body':r.request.post_data,'headers':dict(r.request.headers)})
      if u.scheme in ('blob','data'):return await r.continue_()
      if u.hostname!=urllib.parse.urlparse(FIXTURE).hostname:return await r.abort()
      if path=='/vendor/supabase.mjs':
       module="export function createClient(){return {auth:{onAuthStateChange(){},async getSession(){return {data:{session:{access_token:'fixture-only',user:{id:'00000000-0000-4000-8000-000000000001',email:'fixture@example.test'}}}}},async signOut(){return {error:null}}}}}"
       return await r.fulfill(content_type='application/javascript',body=module)
      query=urllib.parse.parse_qs(u.query);page_num=int(query.get('page',['0'])[0]);search=query.get('q',[''])[0]
      config={'supabaseUrl':'https://fixture.example.test','supabaseAnonKey':'fixture-only','adSizes':fixture['sizes'],'captchaSiteKey':'','whatsappEnabled':True}
      me={'email':'fixture@example.test','plan':plan,'limits':fixture['limits'][plan],'usage':{'campaigns_this_month':1,'campaigns_lifetime':1},'plan_status':'active'}
      entries=[{'id':current['id'],'name':f'Campaign {i:02}','product':'Coffee','created_at':'2026-09-05T00:00:00Z','provider':'offline'} for i in range(55)]
      if search:entries=[c for c in entries if search in c['name']]
      billing={'plan':plan,'plan_status':'active','plans':fixture['plans'],'checkout_enabled':True,'has_subscription':True,'portal_available':True,'subscriptions':[{'id':'sub_fixture','plan':plan,'status':'active','billing_interval':'month'}]}
      api={'/api/config':config,'/api/me':me,'/api/brands':{'brands':[]},'/api/campaigns':{'campaigns':entries[page_num*20:page_num*20+20],'total':len(entries),'has_more':len(entries)>(page_num+1)*20},'/api/campaigns/'+current['id']:current,'/api/billing/status':billing,'/api/billing/change':{'preview':{'currency':'USD','immediate':{'total':'1500'},'next':{'total':'9900'}},'confirmation':'fixture-confirmation','notice':'Prorated immediately; this updates the existing subscription.'}}
      if path=='/api/campaigns/'+current['id'] and r.request.method=='PATCH':
       b=json.loads(r.request.post_data);current.update({k:v for k,v in b.items() if k in ['copy','strategy','seo']});current['revision']+=1;state['patches']+=1
       return await r.fulfill(content_type='application/json',body=json.dumps({'ok':True,'revision':current['revision']}))
      if path in api:return await r.fulfill(content_type='application/json',body=json.dumps(api[path]))
      if path=='/api/me/keys':return await r.fulfill(status=404,content_type='application/json',body='{}')
      if path in ['/','/signup','/login'] or path.startswith('/app/c/'):path='/index.html'
      if path=='/canvas/':path='/canvas/index.html'
      f=CLOUD/path.lstrip('/')
      if f.is_file():return await r.fulfill(body=f.read_bytes(),content_type=mimetypes.guess_type(str(f))[0] or 'application/octet-stream')
      return await r.fulfill(status=404,body='Not found')
     context=await browser.new_context(viewport={'width':width,'height':900},reduced_motion='reduce',accept_downloads=True)
     await context.route('**/*',route);await context.add_init_script(f"localStorage.setItem('brandforge-theme','{theme}');window.__checkoutCalls=[];window.Paddle={{Checkout:{{open(d){{window.__checkoutCalls.push(d)}}}}}};")
     page=await context.new_page();page.on('pageerror',lambda e:errors.append(e.stack))
     await page.goto(FIXTURE+'/',wait_until='networkidle');await page.wait_for_selector('#camp-list .row')
     await page.locator('summary').filter(has_text='Banner formats').click()
     assert await page.locator('#c-custom-wrap').is_visible()==(plan=='agency')
     await page.locator('summary').filter(has_text='Banner formats').click()
     await page.locator('#history-next').click();await page.locator('#history-next').click();await page.wait_for_function("document.getElementById('history-page').textContent.includes('Page 3')")
     assert 'Campaign 54' in await page.locator('#camp-list').inner_text()
     await page.locator('#camp-list .row').first.click();await page.wait_for_selector('#detail:not(.hidden)')
     await page.locator('[data-t=files]').click();await page.locator('#d-body img').first.wait_for()
     await page.wait_for_function("document.querySelector('#d-body img').complete")
     await audit(page,f'cloud/files/{plan}/{theme}/{width}')
     if width==390 and theme=='light' and plan=='agency':await page.screenshot(path=str(SHOTS/'cloud-files-mobile.png'),full_page=False)
     if width==1440 and theme=='dark' and plan=='pro':
      await page.locator('[data-t=copy]').click();await page.locator('#d-edit').click();await page.locator('#section-editor').fill('Reviewed client copy. Learn more.');await page.get_by_role('button',name='Save new version',exact=True).click();await page.wait_for_function("document.getElementById('d-stage-status').textContent.includes('Version 2')");assert state['patches']==1
      async with page.expect_download() as info:await page.locator('#d-zip').click()
      download=await info.value;destination=OUT/'browser-export.zip';await download.save_as(str(destination))
      with zipfile.ZipFile(destination) as z:
       manifest=json.loads(z.read('manifest.json'))
       for entry in manifest['files']:assert hashlib.sha256(z.read(entry['name'])).hexdigest()==entry['sha256']
       assert any(n.endswith('.png') for n in z.namelist())
       edited_export='Reviewed client copy' in z.read('copy.md').decode();assert edited_export
      results.append({'view':'Cloud ZIP fixture','manifest_files':len(manifest['files']),'checksums':'PASS','edited_copy_in_export':edited_export})
     await page.locator('#nav-billing').click();await page.wait_for_selector('[data-plan=agency]')
     await audit(page,f'cloud/billing/{plan}/{theme}/{width}')
     if plan=='pro':
      await page.locator('[data-plan=agency]').click();await page.wait_for_selector('#confirm-plan-change');assert not any(r['path']=='/api/billing/checkout' for r in requests);assert await page.evaluate('window.__checkoutCalls.length')==0
     results.append({'view':f'cloud flows/{plan}/{theme}/{width}','page_errors':errors,'history_oldest_reachable':True,'paid_changes_use_preview':plan=='pro'})
     if plan=='agency' and theme=='dark' and width==1440:
      await page.locator('#bill-back').click();await page.locator('#camp-list .row').first.click();await page.wait_for_selector('#detail:not(.hidden)')
      page.once('dialog',lambda d:d.accept());await page.locator('#d-canvas').click();await page.wait_for_url('**/canvas/')
      await page.wait_for_function("document.querySelector('#layers')?.textContent.includes('image')")
      assert await page.locator('#copy').input_value()
      results.append({'view':'Cloud recipe-less campaign to separate editable canvas','result':'pass','auth_transport':'mocked'})
     assert not errors,errors
     await context.close()
  # Auth layout on the actual DOM, with no session fixture.
  for width in [320,390,768,1440]:
   context=await browser.new_context(viewport={'width':width,'height':900},reduced_motion='reduce')
   async def auth_route(r):
    path=urllib.parse.urlparse(r.request.url).path
    if path=='/vendor/supabase.mjs':return await r.fulfill(content_type='application/javascript',body="export function createClient(){return {auth:{onAuthStateChange(){},async getSession(){return {data:{session:null}}}}}}")
    if path=='/api/config':return await r.fulfill(content_type='application/json',body=json.dumps({'supabaseUrl':'https://fixture.example.test','supabaseAnonKey':'fixture','adSizes':{}}))
    if path in ['/signup','/login','/']:path='/index.html'
    f=CLOUD/path.lstrip('/')
    if f.is_file():return await r.fulfill(body=f.read_bytes(),content_type=mimetypes.guess_type(str(f))[0] or 'application/octet-stream')
    await r.abort()
   await context.route('**/*',auth_route);page=await context.new_page();await page.goto(FIXTURE+'/signup',wait_until='networkidle');await audit(page,f'cloud/signup/{width}')
   if width==390:await page.screenshot(path=str(SHOTS/'cloud-signup-mobile.png'),full_page=True)
   await context.close()
  # Optional actual built Desktop client; start an isolated local server first.
  if os.environ.get('BRANDFORGE_DESKTOP_QA')=='1':
   context=await browser.new_context(viewport={'width':1440,'height':1000},reduced_motion='reduce');page=await context.new_page();errors=[];page.on('pageerror',lambda e:errors.append(e.stack))
   await page.goto('http://127.0.0.1:8767/',wait_until='networkidle');await audit(page,'desktop/initial/1440');await page.screenshot(path=str(SHOTS/'desktop-workspace.png'),full_page=False);results.append({'view':'Desktop actual built client','page_errors':errors});await context.close()
  await browser.close()
 (OUT/'browser-verification.json').write_text(json.dumps(results,indent=2));print(json.dumps({'views':len(results),'axe_violations':sum(len(r.get('axe',[])) for r in results),'overflows':[r['view'] for r in results if r.get('width',{}).get('page',0)>r.get('width',{}).get('viewport',0)],'errors':[r for r in results if r.get('page_errors')]},indent=2))
asyncio.run(main())
assert not any(r.get('axe') or r.get('page_errors') or r.get('width',{}).get('page',0)>r.get('width',{}).get('viewport',0) for r in results), 'Browser checks found failures; see browser-verification.json'

