"""Offline owner dashboard browser/validation checks, with fictional records only."""
import asyncio
import json
from pathlib import Path
from playwright.async_api import async_playwright
ROOT=Path(__file__).resolve().parents[1]

async def main():
    sample={'day':'2026-09-12','customer_ref':'pilot-1','campaign_ref':'pack-1','reviewed':True,'exported':True,'usable':True,'editing_minutes':8,'first_usable_export_minutes':12,'provider_cost_usd':1.25,'fallback':False,'image_failed':False,'export_failed':False,'support_minutes':0,'refund_usd':0,'refund_reason':'none'}
    async with async_playwright() as p:
        for name in ['chromium','firefox','webkit']:
            browser=await getattr(p,name).launch();page=await browser.new_page(viewport={'width':390,'height':900});requests=[];page.on('request',lambda r:requests.append(r.url))
            await page.set_content((ROOT/'tools/value-dashboard.html').read_text())
            assert 'Not measured' in await page.locator('#cards').inner_text()
            await page.locator('#file').set_input_files({'name':'fictional-test.json','mimeType':'application/json','buffer':json.dumps({'schema':1,'records':[sample]}).encode()})
            await page.wait_for_function("document.querySelector('#status').textContent.startsWith('1 records')")
            result=await page.evaluate('(row)=>BFValue.summarize(BFValue.validate({schema:1,records:[row]}))',sample)
            assert result['usableRate']==1 and result['costPerUsable']==1.25 and result['editingMedian']==8
            await page.locator('#file').set_input_files({'name':'duplicate.json','mimeType':'application/json','buffer':json.dumps({'schema':1,'records':[sample,sample]}).encode()})
            await page.wait_for_function("document.querySelector('#status').textContent.includes('Duplicate')")
            await page.evaluate((ROOT/'cloud/node_modules/axe-core/axe.min.js').read_text());assert await page.evaluate('async()=>(await axe.run()).violations')==[]
            assert not requests and not await page.evaluate('document.documentElement.scrollWidth>innerWidth')
            await browser.close()
    print(json.dumps({'engines':3,'empty_state':'pass','measurements':'pass','duplicate_rejected':'pass','axe':0,'external_requests':0,'data':'fictional test only'}))
asyncio.run(main())
