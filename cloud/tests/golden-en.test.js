import {it,expect} from 'vitest';
import {readFileSync} from 'node:fs';
import {runCampaign} from '../api/_lib/engine.js';
it('freezes the intentionally improved coffee copy, not the retired marketing-software boilerplate',async()=>{
 const expected=JSON.parse(readFileSync(new URL('./golden/en.json',import.meta.url),'utf8'));
 const r=await runCampaign({product:'Apex Coffee',industry:'Specialty Coffee',audience:'Busy professionals',benefits:'organic beans, same-day delivery'});
 for(const k of ['strategy','copy','seo'])expect(r[k]).toBe(expected[k]);
 expect(r.files[0].content).toContain('Apex Coffee');expect(r.files[0].content).toContain('organic beans');
});
