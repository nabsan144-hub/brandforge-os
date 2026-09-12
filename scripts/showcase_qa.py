"""Real browser checks of concept gallery; API availability is mocked, not live AI."""
import asyncio
import json
import mimetypes
from pathlib import Path
from urllib.parse import urlparse
from playwright.async_api import async_playwright

ROOT = Path(__file__).resolve().parents[1]
SITE = ROOT / 'sales'
ORIGIN = 'https://showcase.example.test'
OUT = ROOT / '.cache/showcase-interactions'
OUT.mkdir(parents=True, exist_ok=True)
AXE = (SITE / 'node_modules/axe-core/axe.min.js').read_text()
HEADERS = {h['key']: h['value'] for rule in json.loads((SITE / 'vercel.json').read_text())['headers'] if rule['source'] == '/(.*)' for h in rule['headers']}


async def main():
    results = []
    async with async_playwright() as playwright:
        for engine in ['chromium', 'firefox', 'webkit']:
            browser = await getattr(playwright, engine).launch()
            for theme in ['light', 'dark']:
                for width in [390, 1440]:
                    context = await browser.new_context(viewport={'width': width, 'height': 900}, reduced_motion='reduce')
                    await context.add_init_script(f"localStorage.setItem('brandforge-theme','{theme}')")
                    external = []
                    async def route(r):
                        u = urlparse(r.request.url)
                        if u.scheme in ('blob', 'data'):
                            return await r.continue_()
                        if u.path == '/api/capabilities':
                            return await r.fulfill(json={'schema': 1, 'generation_paused': False, 'cloud': {'checkout_enabled': False}, 'desktop': {'checkout_enabled': False}, 'imagery': {'configured': False, 'scope': 'hero_only', 'resized_banners': 'vector_only'}}, headers={'Access-Control-Allow-Origin': ORIGIN})
                        if u.hostname != urlparse(ORIGIN).hostname:
                            external.append(r.request.url)
                            return await r.abort()
                        name = u.path.lstrip('/') or 'index.html'
                        if not Path(name).suffix:
                            name += '.html'
                        file = SITE / name
                        if file.is_file():
                            return await r.fulfill(body=file.read_bytes(), content_type=mimetypes.guess_type(str(file))[0] or 'application/octet-stream', headers=HEADERS)
                        return await r.fulfill(status=404)
                    await context.route('**/*', route)
                    page = await context.new_page()
                    errors = []
                    page.on('pageerror', lambda e: errors.append(str(e)))
                    await page.goto(ORIGIN, wait_until='networkidle')
                    assert await page.locator('img[src*="assets/gallery/"], img[src*="assets/sample/"]').count() == 0
                    assert await page.locator('#hero-swarm').count() == 1
                    await page.wait_for_function("document.querySelector('#hero-swarm').width > 0")
                    assert await page.locator('#hero-swarm').evaluate("c=>c.getContext('2d').getImageData(0,0,c.width,c.height).data.some((v,i)=>i%4===3&&v>0)")
                    assert 'not by the current app' in await page.locator('.bf-art-disclosure').inner_text()
                    links = page.locator('a.showcase-open')
                    assert await links.count() == 4
                    for i in range(4):
                        link = links.nth(i)
                        await link.click()
                        assert await page.locator('#artwork-viewer').evaluate('(d)=>d.open')
                        await page.wait_for_function("document.querySelector('#artwork-full').naturalWidth > 0")
                        assert await page.locator('#artwork-full').get_attribute('alt')
                        await page.evaluate(AXE)
                        assert not await page.evaluate("async()=> (await axe.run(document.querySelector('#artwork-viewer'))).violations")
                        if i % 2:
                            await page.locator('#artwork-close').click()
                        else:
                            await page.keyboard.press('Escape')
                        assert not await page.locator('#artwork-viewer').evaluate('(d)=>d.open')
                        assert await link.evaluate('(e)=>e===document.activeElement')
                    assert not await page.evaluate('document.documentElement.scrollWidth > innerWidth')
                    assert not external and not errors, {"browser": engine, "external": external, "errors": errors}
                    results.append({'browser': engine, 'theme': theme, 'width': width, 'four_previews': 'pass', 'escape_close_focus': 'pass', 'dialog_axe': 0, 'unexpected_external_requests': 0, 'page_errors': errors})
                    await context.close()
            normal = await browser.new_context(viewport={'width':1440,'height':900}, reduced_motion='no-preference')
            await normal.add_init_script("""window.__heroClicks=0;const old=EventTarget.prototype.addEventListener;EventTarget.prototype.addEventListener=function(type,cb,opts){if(type==='pointerdown'&&this.matches?.('.bf-art-hero')){const original=cb;cb=function(e){window.__heroClicks++;return original.call(this,e)}}return old.call(this,type,cb,opts)}""")
            await normal.route('**/*', route)
            moving = await normal.new_page()
            await moving.goto(ORIGIN, wait_until='networkidle')
            snapshot = lambda: moving.locator('#hero-swarm').evaluate('(c)=>c.toDataURL()')
            first = await snapshot()
            await moving.wait_for_timeout(150)
            assert first != await snapshot(), 'Normal-motion hero must actually animate'
            await moving.locator('.bf-art-copy h1').click()
            assert await moving.evaluate('window.__heroClicks') == 1, 'Real hero click must invoke the orb impulse listener'
            await moving.emulate_media(reduced_motion='reduce')
            await moving.wait_for_timeout(100)
            still = await snapshot()
            await moving.wait_for_timeout(150)
            assert still == await snapshot(), 'Reduced motion must stop drawing motion'
            await normal.close()
            await browser.close()
    (OUT / 'results.json').write_text(json.dumps(results, indent=2))
    print(json.dumps({'states': len(results), 'previews_opened': len(results) * 4, 'failures': []}))


asyncio.run(main())
