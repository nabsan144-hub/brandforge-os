"""Real browser checks for the integrated, prelaunch marketing tour.

Run a loopback sales preview with --production-headers first. All third-party
requests are blocked; this script does not authorize payment or provider calls.
"""
import asyncio
import json
import os
from pathlib import Path
from urllib.parse import urlparse

from playwright.async_api import async_playwright

ROOT = Path(__file__).resolve().parents[1]
URL = os.environ.get('BRANDFORGE_SALES_QA_URL', 'http://127.0.0.1:8768')
assert urlparse(URL).hostname in ('127.0.0.1', 'localhost'), 'Use an isolated loopback preview, not production'
OUT = Path(os.environ.get('BRANDFORGE_DEMO_QA_DIR', str(ROOT / 'qa-results/demo-integration')))
OUT.mkdir(parents=True, exist_ok=True)
AXE = (ROOT / 'sales/node_modules/axe-core/axe.min.js').read_text()


async def audit(page):
    await page.evaluate(AXE)
    return await page.evaluate("""async()=>({
      width:innerWidth, scroll:document.documentElement.scrollWidth,
      violations:(await axe.run(document,{runOnly:{type:'tag',values:['wcag2a','wcag2aa','wcag21aa']}})).violations.map(v=>({id:v.id,impact:v.impact,nodes:v.nodes.map(n=>n.target)}))
    })""")


async def wait_state(page, condition, timeout=20000):
    # Playwright wait_for_function uses in-page eval, which a correct production
    # CSP blocks. Poll a directly evaluated fixed test closure instead; do not
    # weaken CSP or enable bypass_csp just for the harness.
    await page.evaluate(f"""async () => {{
        const ready=()=>({condition});
        const deadline=performance.now()+{timeout};
        while (!ready()) {{
            if (performance.now()>deadline) throw new Error('State did not become ready: '+document.querySelector('[data-tour-status]')?.textContent);
            await new Promise(resolve=>setTimeout(resolve,50));
        }}
    }}""")


async def main():
    results = []
    async with async_playwright() as pw:
        browser = await pw.chromium.launch(headless=True, args=['--no-sandbox'])
        for theme in ('dark', 'light'):
            for width in (320, 390, 768, 1440):
                for path in ('/', '/demo'):
                    context = await browser.new_context(viewport={'width':width,'height':1000}, reduced_motion='reduce')
                    await context.add_init_script(f"localStorage.setItem('brandforge-theme','{theme}')")
                    blocked = []
                    async def restrict(route):
                        if urlparse(route.request.url).hostname not in ('127.0.0.1','localhost'):
                            blocked.append(route.request.url)
                            return await route.abort()
                        await route.continue_()
                    await context.route('**/*', restrict)
                    page = await context.new_page()
                    errors = []
                    page.on('pageerror', lambda error: errors.append(str(error)))
                    requested = []
                    page.on('request', lambda request: requested.append(request.url))
                    response = await page.goto(URL + path, wait_until='networkidle')
                    assert "media-src 'self' data:" in response.headers['content-security-policy']
                    assert response.headers['x-frame-options'] == 'DENY'
                    assert not any('demo.mp4' in item for item in requested), requested
                    before = await audit(page)
                    button = page.locator('[data-tour-play]')
                    await button.focus()
                    await page.keyboard.press('Enter')
                    await wait_state(page, "document.querySelector('video').currentTime > .15", timeout=20000)
                    state = await page.locator('video').evaluate('(v)=>({muted:v.muted,width:v.videoWidth,height:v.videoHeight,duration:v.duration,error:v.error?.code||null})')
                    assert state['muted'] and state['width']==1920 and state['height']==1080 and 59.9<state['duration']<60.1, state
                    assert await button.is_hidden()
                    await page.locator('video').evaluate('(v)=>{v.pause();v.currentTime=42;}')
                    await wait_state(page, "Math.abs(document.querySelector('video').currentTime-42)<.2 && !document.querySelector('video').seeking")
                    # Ending then an explicit replay are checked against real media events.
                    await page.locator('video').evaluate('(v)=>{v.currentTime=v.duration-.08;return v.play()}')
                    await wait_state(page, "document.querySelector('video').ended")
                    assert await button.is_visible() and 'Replay' in await button.inner_text()
                    await button.click()
                    await wait_state(page, "document.querySelector('video').currentTime>.05 && document.querySelector('video').currentTime<2")
                    await page.locator('video').evaluate('(v)=>v.pause()')
                    if path=='/demo':
                        await page.locator('summary').click()
                        assert await page.locator('.bf-tour-transcript li').count()==8
                    after = await audit(page)
                    results.append({'view':f'{path}/{theme}/{width}','before':before,'after':after,'eager_mp4_requests':0,'playback_seek_replay':'PASS','media':state,'page_errors':errors,'blocked_third_party_requests':blocked})
                    if width==1440 and theme=='dark':
                        await page.screenshot(path=str(OUT/('homepage.png' if path=='/' else 'demo-page.png')), full_page=True)
                    if width==390 and theme=='light' and path=='/demo':
                        await page.screenshot(path=str(OUT/'demo-mobile-light.png'),full_page=True)
                    await context.close()
        # The actual self-contained HTML under the marketing CSP, not just a file preview.
        context = await browser.new_context(viewport={'width':1200,'height':950}, reduced_motion='reduce')
        page = await context.new_page(); errors=[]
        page.on('pageerror', lambda error: errors.append(str(error)))
        await page.goto(URL+'/tour?paused=1',wait_until='networkidle')
        await wait_state(page, 'window.__demoReady')
        assert not (await page.evaluate('demo.getState()'))['playing']
        await page.locator('#sound').click();await page.locator('#play').click()
        await wait_state(page, "document.getElementById('music').currentTime>.1 && !document.getElementById('music').paused")
        await page.locator('#play').click()
        await page.get_by_role('button',name='Jump to Choose your fit').click()
        assert (await page.evaluate('demo.getState()'))['chapter']==6
        expected = URL+'/pricing#feature-matrix'
        assert await page.get_by_role('link',name='Compare Desktop and Cloud').get_attribute('href')=='pricing#feature-matrix'
        assert await page.get_by_role('link',name='Compare Desktop and Cloud').evaluate('(a)=>a.href')==expected
        html_check = await audit(page)
        results.append({'view':'HTML alternative under marketing CSP','sound_and_chapters':'PASS','next_links':'PASS','layout':html_check,'page_errors':errors})
        await context.close()
        # Actual byte-range and caption content type, not a file-extension assertion.
        request = await pw.request.new_context()
        byte_range = await request.get(URL+'/assets/product-demo/demo.mp4',headers={'Range':'bytes=0-1023'})
        assert byte_range.status==206 and len(await byte_range.body())==1024
        assert byte_range.headers['content-type'].startswith('video/mp4')
        caption = await request.get(URL+'/assets/product-demo/captions.vtt')
        assert caption.headers['content-type'].startswith('text/vtt') and (await caption.text()).startswith('WEBVTT')
        await request.dispose();await browser.close()
    failures=[]
    for row in results:
        if row.get('page_errors'):failures.append(row)
        for key in ('before','after','layout'):
            data=row.get(key,{})
            if data.get('violations') or data.get('scroll',0)>data.get('width',0):failures.append(row)
    report={'views':results,'range_and_caption_mime':'PASS','failures':failures,'scope':'Local Chromium with production-equivalent marketing headers; no live third-party session'}
    (OUT/'verification.json').write_text(json.dumps(report,indent=2))
    print(json.dumps({'views':len(results),'failures':len(failures),'media_and_controls':'PASS','byte_ranges_and_caption_mime':'PASS'},indent=2))
    assert not failures, 'See integrated demo verification.json'


if __name__ == '__main__':
    asyncio.run(main())
