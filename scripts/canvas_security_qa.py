"""Exercise the actual SVG importer in three browser engines, without network."""
import asyncio
import json
from pathlib import Path
from urllib.parse import urlparse
from playwright.async_api import async_playwright
ROOT=Path(__file__).resolve().parents[1]
ORIGIN='https://canvas-security.example.test'

async def main():
    attacks=[
        '<!DOCTYPE svg [<!ENTITY x "boom">]><svg xmlns="http://www.w3.org/2000/svg" width="100" height="100">&x;</svg>',
        '<script>alert(1)</script>', '<foreignObject><div>active</div></foreignObject>',
        '<animate attributeName="href" values="https://external.example/x"/>',
        '<image href="https://external.example/x"/>',
        '<g id="cycle"><use href="#cycle"/></g>',
        '<rect width="50" height="50" onload="alert(1)"/>',
        '<g xml:base="https://external.example/"><use href="#x"/></g>',
        '<rect width="50" height="50" fill="u\\72l(https://external.example/x)"/>',
    ]
    results=[]
    async with async_playwright() as p:
        for engine in ['chromium','firefox','webkit']:
            print('Testing',engine,flush=True);browser=await getattr(p,engine).launch();page=await browser.new_page();external=[]
            async def route(r):
                u=urlparse(r.request.url)
                if u.scheme in ('blob','data'):return await r.continue_()
                if u.hostname!=urlparse(ORIGIN).hostname:external.append(r.request.url);return await r.abort()
                if u.path=='/':return await r.fulfill(content_type='text/html',body='<html lang="en"><title>Importer check</title><main>Local security test</main></html>')
                file=ROOT/'shared/canvas'/u.path.split('/')[-1]
                if file.is_file():return await r.fulfill(content_type='application/javascript',body=file.read_bytes())
                await r.fulfill(status=404,body='Not found')
            await page.route('**/*',route);await page.goto(ORIGIN)
            rejected=await page.evaluate('''async attacks=>{const {prepareReference}=await import('/canvas/import-image.js');let n=0;for(let source of attacks){if(!source.startsWith('<!DOCTYPE'))source='<svg xmlns="http://www.w3.org/2000/svg" width="100" height="100">'+source+'</svg>';try{await prepareReference(new File([source],'attack.svg',{type:'image/svg+xml'}));}catch{n++;}}return n;}''',attacks)
            assert rejected==len(attacks),(engine,rejected)
            positive=await page.evaluate('''async()=>{const {prepareReference}=await import('/canvas/import-image.js');return (await prepareReference(new File(['<svg xmlns="http://www.w3.org/2000/svg" width="100" height="100"><rect width="100" height="100" fill="#123456"/></svg>'],'safe.svg',{type:'image/svg+xml'}))).startsWith('data:image/png;base64,');}''')
            assert positive and not external
            results.append({'engine':engine,'malicious_references_rejected':rejected,'static_reference_flattened':True,'external_requests':0});await browser.close()
    print(json.dumps(results,indent=2))
asyncio.run(main())
