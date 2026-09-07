/* Real shipped media, page wiring and playback-controller regressions.
 * jsdom player events are fixtures; real codec/CSP/playback is checked in the browser suite.
 */
const fs = require('node:fs');
const path = require('node:path');
const crypto = require('node:crypto');
const { JSDOM } = require('jsdom');
const root = path.join(__dirname, '..');
let passed = 0;
function check(label, value) { if (!value) throw new Error(label); passed++; console.log('  ✓ ' + label); }
const read = file => fs.readFileSync(path.join(root, file), 'utf8');

(async () => {
  for (const name of ['index.html', 'demo.html']) {
    const dom = new JSDOM(read(name), {url: 'https://site.example.test/' + name, runScripts: 'outside-only'});
    const w = dom.window, d = w.document;
    const video = d.querySelector('[data-bf-tour] video');
    check(name + ': one integrated video, not an eager duplicate iframe', d.querySelectorAll('video').length === 1 && !d.querySelector('iframe') && !!video);
    check(name + ': native controls, inline playback and muted by default', video.hasAttribute('controls') && video.hasAttribute('playsinline') && video.hasAttribute('muted'));
    check(name + ': no autoplay or preload download', !video.hasAttribute('autoplay') && video.getAttribute('preload') === 'none');
    check(name + ': named accessible video', !!video.getAttribute('aria-label'));
    for (const element of [video.querySelector('source'), video.querySelector('track')]) {
      const asset = element.getAttribute('src');
      check(name + ': shipped ' + asset, fs.existsSync(path.join(root, asset)));
    }
    check(name + ': shipped poster', fs.existsSync(path.join(root, video.getAttribute('poster'))));
    check(name + ': no duplicate default caption overlay', !video.querySelector('track').hasAttribute('default'));
    check(name + ': animated alternative and video download present', !!d.querySelector('a[href="tour?paused=1"]') && !!d.querySelector('a[download][href="assets/product-demo/demo.mp4"]'));
    check(name + ': still explains fictional/example footage', /fictional offline sample/i.test(d.body.textContent) && /example account data/i.test(d.body.textContent));
    const button = d.querySelector('[data-tour-play]');
    let plays = 0;
    video.play = () => { plays++; video.dispatchEvent(new w.Event('play')); return Promise.resolve(); };
    video.pause = () => {};
    w.eval(read('assets/product-tour.js'));
    check(name + ': initialization never starts playback', plays === 0 && video.muted);
    button.click(); await Promise.resolve();
    check(name + ': explicit click plays and hides the poster control', plays === 1 && button.hidden);
    video.dispatchEvent(new w.Event('ended'));
    check(name + ': ending offers replay', !button.hidden && /replay/i.test(button.textContent));
    video.dispatchEvent(new w.Event('error'));
    check(name + ': media failure provides HTML/download alternatives', /animated HTML/.test(d.querySelector('[data-tour-status]').textContent));
    w.close();
  }
  const manifest = JSON.parse(read('assets/product-demo/manifest.json'));
  check('manifest declares 1080p, 30fps, fictional/non-live footage', manifest.width === 1920 && manifest.height === 1080 && manifest.fps === 30 && manifest.fictional_sample === true && manifest.live_provider_or_payment_demo === false);
  for (const item of manifest.files) {
    const bytes = fs.readFileSync(path.join(root, 'assets/product-demo', item.name));
    check('asset hash/size: ' + item.name, bytes.length === item.bytes && crypto.createHash('sha256').update(bytes).digest('hex') === item.sha256);
  }
  const movie = fs.readFileSync(path.join(root, 'assets/product-demo/demo.mp4'));
  check('video is a nonempty MP4', movie.length > 100000 && movie.toString('ascii', 4, 8) === 'ftyp');
  const tour = read('assets/product-demo/tour.html');
  check('HTML alternative embeds music and has accessible real next steps', tour.includes('data:audio/mpeg;base64,') && tour.includes('aria-label="Explore the products"') && tour.includes('demo#sample-pack'));
  check('standalone font notices retained', tour.includes('embedded-asset-licenses') && tour.includes('SIL OPEN FONT LICENSE'));
  check('homepage watch link and demo sample anchor are real', read('index.html').includes('href="#tour"') && read('index.html').includes('id="tour"') && read('demo.html').includes('id="sample-pack"'));
  check('marketing CSP permits embedded audio without allowing frames', JSON.parse(read('vercel.json')).headers[0].headers.some(h => h.key === 'Content-Security-Policy' && h.value.includes("media-src 'self' data:") && h.value.includes("frame-ancestors 'none'")));
  check('Netlify and Cloudflare marketing policies also allow the self-contained soundtrack', ['netlify.toml', '_headers'].every(file => read(file).includes("media-src 'self' data:")));
  check('checkout still off', /desktop_checkout_enabled:\s*false/.test(read('assets/config.js')));
  // --- Review-fix regression guards (2026-09-06) ---
  // /tour used to 404 live: two legacy 301 rules competed with the /tour
  // rewrite on clean-URL hosts (rewritten destination re-entered the rule
  // list). The canonical /tour URL keeps ONE rewrite and no tour 301 pair.
  const vercel = JSON.parse(read('vercel.json'));
  const tourRedirects = vercel.redirects.filter(r => /tour/.test(r.source || ''));
  check('vercel.json: no tour asset redirect competes with the /tour rewrite', tourRedirects.length === 0 && vercel.rewrites.some(r => r.source === '/tour' && r.destination === '/assets/product-demo/tour.html'));
  const netlify = read('netlify.toml');
  check('netlify.toml: single 200 /tour rewrite, no legacy tour 301s', /\[\[redirects\]\]\n  from = "\/tour"\n  to = "\/assets\/product-demo\/tour\.html"\n  status = 200/.test(netlify) && !netlify.includes('assets/product-demo/tour.html"\n  to = "/tour"'));
  const redirects = read('_redirects');
  check('_redirects: only the /tour 200 rewrite remains', /^\/tour \/assets\/product-demo\/tour\.html 200$/m.test(redirects) && !/tour \/tour 301/.test(redirects));
  check('publish build mirrors the self-contained tour at the site root', /product-demo\/tour\.html/.test(read('build.mjs')) && /join\(out\s*,\s*'tour\.html'\)/.test(read('build.mjs')));
  const pricing = read('pricing.html');
  check('Desktop CTAs promise the waitlist until a tier is configured for sale', pricing.includes('Join the waitlist — $199 at launch') && pricing.includes('Join the waitlist — $499 at launch') && !pricing.includes('>Buy once — $199<') && !pricing.includes('>Buy once — $499<'));
  check('workspace CTA matches the honest waitlist wording', read('workspace.html').includes('Join the waitlist — $199 at launch'));
  check('free plan copy matches the engine (hero + 1 preset)', pricing.includes('Hero + 1 preset per run'));
  const faqJson = read('pricing.html');
  check('FAQ JSON-LD mirrors the visible answers (no absolute offline overclaim)', (faqJson.match(/"@type": "Question"/g) || []).length === 10 && !faqJson.includes('data stays on your PC'));
  check('homepage hero shows real benefits and still states the honest limits', /One brief[\s\S]*Review every claim[\s\S]*Free to try[\s\S]*output is yours/.test(read('index.html')) && /No invented SEO scores/.test(read('index.html')));
  console.log(`RESULT: ${passed} demo integration checks passed`);
})().catch(error => { console.error(error); process.exitCode = 1; });
