import {describe,it,expect} from 'vitest';
import {readFileSync} from 'node:fs';
const html=readFileSync('public/index.html','utf8'),css=readFileSync('public/semantic-tokens.css','utf8'),tokens=JSON.parse(readFileSync('../shared/design-tokens.json','utf8'));
const luminance=hex=>hex.slice(1).match(/../g).map(x=>parseInt(x,16)/255).map(x=>x<=.04045?x/12.92:((x+.055)/1.055)**2.4).reduce((sum,x,i)=>sum+x*[.2126,.7152,.0722][i],0);
const contrast=(a,b)=>(Math.max(luminance(a),luminance(b))+.05)/(Math.min(luminance(a),luminance(b))+.05);
describe('generated semantic contrast contracts',()=>{
 it('loads canonical aliases in both themes rather than duplicating palettes',()=>{expect(html).toContain('href="/semantic-tokens.css"');expect(css).toContain('[data-theme="light"]');expect(css).toContain('--gold:var(--bf-accent)');});
 it('keeps normal text, status and action contrast at least 4.5:1',()=>{for(const theme of Object.values({dark:tokens.dark,light:tokens.light})){for(const color of ['ink','muted','faint','error','success','accent'])for(const surface of ['bg','card'])expect(contrast(theme[color],theme[surface]),color+' on '+surface).toBeGreaterThanOrEqual(4.5);expect(contrast(theme.action,theme.on_action)).toBeGreaterThanOrEqual(4.5);}});
 it('uses a matched semantic pair for gold actions and visible control boundaries',()=>{expect(html).toContain('background:var(--bf-action);color:var(--bf-on_action)');for(const theme of [tokens.dark,tokens.light])for(const surface of ['bg','card'])expect(contrast(theme.control_line,theme[surface])).toBeGreaterThanOrEqual(3);});
 it('retains focus-visible and empty-plan fixes',()=>{expect(html).toContain('#nav-plan:empty{display:none}');expect(css).toContain(':focus-visible{outline:3px solid var(--bf-focus)');});
});
