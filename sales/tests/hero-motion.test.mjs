import assert from 'node:assert/strict';
import {readFileSync} from 'node:fs';
import vm from 'node:vm';
const code=readFileSync(new URL('../assets/hero-swarm.js',import.meta.url),'utf8');
assert.match(readFileSync(new URL('../index.html',import.meta.url),'utf8'), /<canvas[^>]*id="hero-swarm"[^>]*aria-hidden="true"/);
let preference,intersection,visibility,scheduled=0,draws=0;
const frames=new Set();
const ctx={setTransform(){},clearRect(){draws++;},beginPath(){},arc(){},fill(){},createRadialGradient(){return {addColorStop(){}};}};
const hero={clientWidth:1200,clientHeight:700,addEventListener(){}};
const document={hidden:false,documentElement:{getAttribute(){return 'light';}},getElementById(){return {parentElement:hero,getContext(){return ctx;}};},addEventListener(name,cb){if(name==='visibilitychange')visibility=cb;}};
class Observer{observe(){}}
class Intersection extends Observer{constructor(cb){super();intersection=cb;}}
const window={matchMedia(){return {matches:true,addEventListener(name,cb){preference=cb;}};},devicePixelRatio:1,IntersectionObserver:Intersection,ResizeObserver:Observer};
vm.runInNewContext(code,{window,document,IntersectionObserver:Intersection,ResizeObserver:Observer,MutationObserver:Observer,requestAnimationFrame(){frames.add(++scheduled);return scheduled;},cancelAnimationFrame(id){frames.delete(id);}});
assert.equal(frames.size,0);assert.ok(draws>0);
preference({matches:false});assert.equal(frames.size,1);
intersection([{isIntersecting:false}]);assert.equal(frames.size,0);
intersection([{isIntersecting:true}]);assert.equal(frames.size,1);
document.hidden=true;visibility();assert.equal(frames.size,0);
intersection([{isIntersecting:true}]);assert.equal(frames.size,0);
document.hidden=false;visibility();assert.equal(frames.size,1);
preference({matches:true});assert.equal(frames.size,0);
console.log('Hero motion: reduced-motion changes, off-screen and hidden-tab pause/resume passed.');
