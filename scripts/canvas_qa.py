"""Actual local FastAPI + shared canvas: editing, migration, replay/restore and exports."""
import asyncio
import json
import os
from pathlib import Path
import socket
import subprocess
import sys
import tempfile
import urllib.request
from playwright.async_api import async_playwright
ROOT=Path(__file__).resolve().parents[1]
OUT=Path(os.environ.get('BRANDFORGE_QA_DIR',ROOT/'qa-results/canvas'));OUT.mkdir(parents=True,exist_ok=True)

async def main():
    with socket.socket() as s:s.bind(('127.0.0.1',0));port=s.getsockname()[1]
    with tempfile.TemporaryDirectory(prefix='canvas-',dir=ROOT/'.cache') as tmp:
        env={k:v for k,v in os.environ.items() if not any(x in k.upper() for x in ['API_KEY','SECRET','TOKEN'])};env['BRANDFORGE_DATA_DIR']=tmp
        with (OUT/'server.txt').open('w') as log:
            process=subprocess.Popen([sys.executable,'-m','uvicorn','server:app','--host','127.0.0.1','--port',str(port)],cwd=ROOT/'app',env=env,stdout=log,stderr=subprocess.STDOUT)
            try:
                origin=f'http://127.0.0.1:{port}'
                for _ in range(100):
                    try:
                        with urllib.request.urlopen(origin+'/health',timeout=1):break
                    except OSError:await asyncio.sleep(.1)
                else:raise RuntimeError('Local startup failed')
                axe=(ROOT/'cloud/node_modules/axe-core/axe.min.js').read_text();results=[]
                async with async_playwright() as p:
                    browser=await getattr(p,os.environ.get('BF_BROWSER','chromium')).launch(args=['--no-sandbox'] if os.environ.get('BF_BROWSER','chromium')=='chromium' else [])
                    for theme in ['light','dark']:
                        for width in [390,1440]:
                            context=await browser.new_context(viewport={'width':width,'height':1000},color_scheme=theme,accept_downloads=True)
                            if os.environ.get('BF_CANVAS_CLOUD')=='1':
                                with urllib.request.urlopen(origin+'/api/session') as response:cap=json.load(response)['capability']
                                async def route_cloud(route):
                                    path=route.request.url.removeprefix(origin)
                                    if path=='/api/session':return await route.fulfill(status=404,json={'error':'Not Desktop'})
                                    if path=='/api/config':return await route.fulfill(json={'supabaseUrl':origin,'supabaseAnonKey':'fixture'})
                                    if path=='/vendor/supabase.mjs':return await route.fulfill(content_type='application/javascript',body="export function createClient(){return {auth:{async getSession(){return {data:{session:{access_token:'canvas-fixture'}}}}}}}")
                                    if path.startswith('/api/canvas'):
                                        assert route.request.headers.get('authorization')=='Bearer canvas-fixture'
                                        response=await context.request.fetch(route.request.url,method=route.request.method,data=route.request.post_data,headers={'X-BrandForge-Token':cap,'Content-Type':'application/json'})
                                        return await route.fulfill(response=response)
                                    return await route.continue_()
                                await context.route('**/*',route_cloud)
                            page=await context.new_page();errors=[];external=[]
                            page.on('pageerror',lambda e:errors.append(str(e)));page.on('request',lambda r:external.append(r.url) if r.url.startswith('http') and not r.url.startswith(origin) else None)
                            await page.goto(origin+'/canvas/');await page.wait_for_function("()=>document.querySelector('#status').textContent.startsWith('Ready.')")
                            assert await page.evaluate("getComputedStyle(document.documentElement).getPropertyValue('--bf-bg').trim()")==json.loads((ROOT/'shared/design-tokens.json').read_text())[theme]['bg']
                            await page.locator('#file-actions').evaluate('(e)=>e.open=true');await page.locator('#text-sections').evaluate('(e)=>e.open=true');
                            await page.locator('[data-add=text]').click();await page.locator('#prop-text').fill('Coffee & tea\nReviewed offer');await page.locator('#prop-x').fill('20');await page.locator('#prop-width').fill('500');await page.locator('#properties button').click()
                            await page.locator('#strategy').fill('Portable strategy');await page.locator('#copy').fill('Editable content');await page.locator('#name').fill('Canvas '+theme+str(width));await page.locator('#consent').check();await page.locator('#save').click();await page.wait_for_function("()=>document.querySelector('#status').textContent.startsWith('Saved version 1')")
                            await page.locator('#background').fill('#faf0dd');await page.locator('#save').click();await page.wait_for_function("()=>document.querySelector('#status').textContent.startsWith('Saved version 2')")
                            await page.locator('#versions').select_option('1');page.once('dialog',lambda d:d.accept());await page.locator('#restore').click();await page.wait_for_function("()=>document.querySelector('#status').textContent.startsWith('Opened version 3')")
                            assert await page.locator('#background').input_value()=='#ffffff'
                            await page.locator('#zoom').select_option('100');await page.locator('#reviewed').check()
                            async with page.expect_download() as download:await page.locator('#export-svg').click()
                            svg=await(await download.value).path();text=Path(svg).read_text();assert 'Coffee &amp; tea' in text and 'data-selection' not in text and 'data-watermark' in text
                            async with page.expect_download() as download:await page.locator('#export-json').click()
                            artifact=Path(await(await download.value).path());doc=json.loads(artifact.read_text());assert doc['sections']['copy']=='Editable content'
                            # The same artifact is accepted without transformation by both target validators.
                            sys.path.insert(0,str(ROOT/'app'));from modules.canvas_projects import validate_document
                            assert validate_document(doc)==doc
                            await page.locator('#zoom').select_option('fit')
                            await page.evaluate(axe);violations=await page.evaluate("async()=> (await axe.run()).violations.map(v=>({id:v.id,nodes:v.nodes.map(n=>n.target)}))")
                            assert not violations,violations
                            assert not await page.evaluate('document.documentElement.scrollWidth>innerWidth')
                            await page.screenshot(path=str(OUT/f'canvas-{theme}-{width}.png'),full_page=True)
                            page.once('dialog',lambda d:d.accept());await page.locator('#import').set_input_files(str(artifact));await page.wait_for_function("()=>document.querySelector('#status').textContent.startsWith('Imported locally')")
                            assert await page.locator('#copy').input_value()=='Editable content'
                            assert not errors,errors;assert not external,external
                            results.append({'theme':theme,'width':width,'passed':True});await context.close()
                    await browser.close()
                (OUT/'results.json').write_text(json.dumps(results,indent=2));print(json.dumps({'views':len(results),'actual_desktop_api':'pass','edit_save_restore_json_svg':'pass','axe':0,'external_requests':0}))
            finally:
                process.terminate()
                try:process.wait(timeout=10)
                except subprocess.TimeoutExpired:process.kill();process.wait()
if __name__=='__main__':
    (ROOT/'.cache').mkdir(exist_ok=True);asyncio.run(main())
