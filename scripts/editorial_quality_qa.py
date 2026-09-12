"""Raster and real-geometry proof, offline. No model or production requests."""
import asyncio, json, os, subprocess, html, base64
from pathlib import Path
from playwright.async_api import async_playwright
ROOT=Path(__file__).resolve().parents[1]
OUT=Path(os.environ.get('BRANDFORGE_QA_DIR',str(ROOT/'qa-results/editorial')));OUT.mkdir(parents=True,exist_ok=True)
subprocess.run(['node',str(ROOT/'scripts/make_editorial_fixture.mjs'),str(OUT)],cwd=ROOT,check=True)
async def main():
 fixture=json.loads((OUT/'fixtures.json').read_text());results=[]
 async with async_playwright() as p:
  browser=await p.chromium.launch(args=['--no-sandbox']);page=await browser.new_page()
  for e in fixture['entries']:
   await page.set_viewport_size({'width':e['width'],'height':e['height']})
   await page.set_content((OUT/e['name']).read_text())
   geometry=await page.evaluate('''()=>{const root=document.querySelector('svg'),w=root.width.baseVal.value,h=root.height.baseVal.value;return [...document.querySelectorAll('[data-box]')].map(g=>({box:g.dataset.box.split(',').map(Number),label:g.getAttribute('aria-label')})).filter(({box:[x,y,bw,bh]})=>x<-.1||y<-.1||x+bw>w+.1||y+bh>h+.1)}''')
   assert not geometry,(e['name'],geometry)
   # Real SVG geometric bounding boxes mapped to the root viewport, including
   # nested attribution artwork. Outlined glyphs must stay inside the canvas.
   # Default body margin is deliberately removed before actual geometry proof.
   await page.add_style_tag(content='body{margin:0}')
   actual=await page.evaluate('''()=>{const root=document.querySelector('svg'),w=root.width.baseVal.value,h=root.height.baseVal.value;return [...document.querySelectorAll('[data-box]')].filter(g=>{const b=g.getBoundingClientRect();return b.left<-.2||b.top<-.2||b.right>w+.2||b.bottom>h+.2}).map(g=>g.getAttribute('aria-label'))}''')
   assert not actual,(e['name'],actual)
   await page.locator('svg').first.screenshot(path=str(OUT/e['name'].replace('.svg','.png')))
   results.append({**e,'geometry':'pass','raster':'pass'})
  await browser.close()
 (OUT/'results.json').write_text(json.dumps(results,indent=2))
 cards=[]
 for brief in fixture['cases']:
  samples=[]
  for e in results:
   if e['id']!=brief['id']:continue
   uri='data:image/png;base64,'+base64.b64encode((OUT/e['name'].replace('.svg','.png')).read_bytes()).decode()
   issues='; '.join(e['issues']) or 'No geometric omissions detected. Human review still required.'
   samples.append(f'<article><h3>{html.escape(e["format"])} · {e["width"]} × {e["height"]}</h3><img src="{uri}" alt="{html.escape(brief["product"])} {e["format"]} draft"><p>{html.escape(issues)}</p></article>')
  cards.append('<section><h2>'+html.escape(brief['product'])+'</h2><div class="grid">'+''.join(samples)+'</div></section>')
 document='''<!doctype html><html lang="en"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>BrandForge — Editorial review candidate</title><style>*{box-sizing:border-box}body{margin:0;padding:32px;background:#eeeae2;color:#17251f;font:16px/1.55 system-ui}main{max-width:1500px;margin:auto}h1{font-size:42px;line-height:1.1}header{max-width:850px;margin-bottom:40px}.grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(260px,1fr));gap:16px}section{margin:40px 0}article{padding:16px;background:white;border:1px solid #ccc}h3{font-size:14px}img{display:block;max-width:100%;max-height:450px;margin:auto}article p{font-size:12px;overflow-wrap:anywhere}.note{padding:16px;background:#fff0bf;border-left:4px solid #8b5900}</style><main><header><p>PHASE 6A / LOCAL REVIEW / OPT-IN</p><h1>Editorial, not certified.</h1><p>A type-led vector candidate with flat brand-colored actions, no decorative benefit icons and explicit omissions. These are fictional test briefs, not customer testimonials or real offers.</p><p class="note">Do not publish an image with missing price or eligibility terms. The long brief is intentionally retained as a rejected stress case. Urdu/Hindi require native-language advertising review. Raster sizes here are constrained for comparison: inspect native files and intended placement before approval.</p><p>This does not replace the default renderer, rebuild historical files, add product photography or prove people will buy the output.</p></header>'''+''.join(cards)+'</main></html>'
 (OUT/'review.html').write_text(document)
 print(json.dumps({'renders':len(results),'geometry':'pass','raster':'pass','with_omissions':sum(bool(e['issues']) for e in results)}))
asyncio.run(main())
