import {it,expect} from 'vitest';
import {readFileSync} from 'node:fs';
import {runCampaign,completeCopy} from '../api/_lib/engine.js';
it.each(['ur','hi','es','pt'])('freezes complete %s template structures without translating brand names',async lang=>{
 const expected=JSON.parse(readFileSync(new URL('./golden/'+lang+'.json',import.meta.url),'utf8'));
 const r=await runCampaign({product:'Apex Coffee',industry:'Specialty Coffee',audience:'Busy professionals',benefits:'organic beans, same-day delivery',lang});
 for(const k of ['strategy','copy','seo']){expect(r[k]).toBe(expected[k]);expect(r[k]).toContain('Apex Coffee');}
 expect(completeCopy(r.copy)).toBe(true);expect(r.seo).not.toContain('78/100');
});
