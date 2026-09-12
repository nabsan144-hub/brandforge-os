import {it,expect} from 'vitest';
import {allowanceCopy} from '../public/allowance.js';
it('separates Free lifetime allowance from its daily cap and pending reservations',()=>{
 const out=allowanceCopy({plan:'free',limits:{lifetime:3,daily:3},usage:{campaigns_lifetime:1,reserved:1}});
 expect(out.summary).toContain('1 available');expect(out.summary).toContain('1 in progress');expect(out.policy).toContain('never resets');expect(out.policy).toContain('At most 3');
});
it('uses UTC calendar months rather than billing dates',()=>{
 const out=allowanceCopy({plan:'pro',limits:{lifetime:null,monthly:50,daily:20},usage:{campaigns_this_month:12,reserved:2}});
 expect(out.summary).toContain('36 available');expect(out.policy).toContain('not your subscription billing date');expect(out.policy).toContain('00:00 UTC');
});
it('never displays a negative allowance and keeps degraded-result/deletion rules visible',()=>{
 const out=allowanceCopy({plan:'free',limits:{lifetime:3},usage:{campaigns_lifetime:5}});
 expect(out.summary).toContain('0 available');expect(out.policy).toContain('including labeled template fallbacks');expect(out.policy).toContain('Deleting work does not restore');
});
