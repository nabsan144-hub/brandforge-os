/* Phase 0 funnel verification — exercises the REAL shipped sales-site JS.
   Loads actual pricing.html markup into jsdom, evals actual config.js /
   buy.js / waitlist.js, and asserts funnel behavior in both states:
   A) current placeholder state   B) operator-configured state
   C) homepage fallback redirect                                    */
const fs = require('fs');
const path = require('path');
const { JSDOM, VirtualConsole } = require('jsdom');

const SALES = path.join(__dirname, '..');
const read = f => fs.readFileSync(path.join(SALES, f), 'utf8');

const pricingHtml = read('pricing.html');
const indexHtml = read('index.html');
const configJs = read('assets/config.js');
const buyJs = read('assets/buy.js');
const availabilityJs=read('assets/availability.js');
const capabilities={schema:1,cloud:{checkout_enabled:true},desktop:{checkout_enabled:true},imagery:{configured:false,scope:'hero_only',resized_banners:'vector_only'},generation_paused:false};
const waitlistJs = read('assets/waitlist.js');

let pass = 0, fail = 0;
function assert(name, cond, extra) {
  if (cond) { pass++; console.log('  ✓ ' + name); }
  else { fail++; console.log('  ✗ ' + name + (extra ? ' — ' + extra : '')); }
}

async function makeDom(html, url) {
  const errors = [];
  const vc = new VirtualConsole();
  vc.on('jsdomError', e => errors.push(String(e.message)));
  const dom = new JSDOM(html, {
    url: url || 'https://brandforge-os.com/pricing.html',
    runScripts: 'outside-only',
    pretendToBeVisual: true,
    virtualConsole: vc,
  });
  const w = dom.window;
  w.HTMLElement.prototype.scrollIntoView=function(){};
  w.eval(configJs);
  w.eval(availabilityJs);
  w.eval(buyJs);
  w.eval(waitlistJs);
  // waitlist.js defers init() to DOMContentLoaded when readyState==='loading' —
  // wait for load so handlers are attached before we submit.
  if (w.document.readyState !== 'complete') {
    await new Promise(r => w.addEventListener('load', r));
  }
  dom.__errors = errors;
  return dom;
}

async function submitForm(dom, email, tier, honey) {
  const w = dom.window;
  const d = w.document;
  d.getElementById('wl-email').value = email;
  if (tier) d.getElementById('wl-tier').value = tier;
  d.querySelector('[name="_honey"]').value = honey === undefined ? '' : honey;
  const form = d.getElementById('waitlist-form');
  form.dispatchEvent(new w.Event('submit', { bubbles: true, cancelable: true }));
  await new Promise(r => setTimeout(r, 40)); // let the fetch promise chain settle
  return d.getElementById('wl-msg').textContent;
}

(async () => {
  console.log('\n=== STATE A — current repo state (honest pre-launch: Paddle off, waitlist live) ===');
  {
    const dom = await makeDom(pricingHtml);
    const w = dom.window;
    const CFG = w.BRANDFORGE_LAUNCH;

    assert('config exposes window.BRANDFORGE_LAUNCH', !!CFG);
    assert('no FormSubmit placeholder inbox remains', !(CFG.waitlist_email || '').includes('YOUR-EMAIL'));
    assert('waitlist posts to the cloud /api/waitlist backend', CFG.waitlistEndpoint() === 'https://app.brandforge-os.com/api/waitlist', CFG.waitlistEndpoint());
    assert('waitlistReady === true (endpoint is wired)', CFG.waitlistReady === true);
    assert('paddle_client_token empty → paddleReady === false', CFG.paddleReady === false);
    assert('configuredTiers() === []', JSON.stringify(CFG.configuredTiers()) === '[]');
    const ownerCta = w.document.querySelector('[data-cta-tier="owner"]');
    assert('default state → Owner CTA promises the waitlist, never checkout', !!ownerCta && ownerCta.textContent === 'Join the waitlist — $199 at launch', ownerCta && ownerCta.textContent);

    let lastFetch = null;
    w.fetch = (url, opts) => { lastFetch = { url, opts }; return Promise.resolve({ ok: true, status: 200, json: () => Promise.resolve({ ok: true, queued: true }) }); };

    let msg = await submitForm(dom, 'buyer@example.com', 'owner');
    assert('valid email posts to the waitlist endpoint', !!lastFetch && lastFetch.url === 'https://app.brandforge-os.com/api/waitlist', lastFetch && lastFetch.url);
    const payload = lastFetch && JSON.parse(lastFetch.opts.body);
    assert('payload carries email + tier (no FormSubmit keys)', !!payload && payload.email === 'buyer@example.com' && payload.tier === 'owner' && payload.Email === undefined, JSON.stringify(payload));
    assert('backend success → confirmation shown (waitlist is live pre-launch)', /on the list/i.test(msg), 'msg=' + JSON.stringify(msg));
    assert('no unhandled native form navigation occurred', dom.__errors.length === 0, dom.__errors.join('|'));

    // Backend not live yet (waitlist table / Supabase not created) → honest message.
    w.fetch = () => Promise.resolve({ ok: false, status: 501, json: () => Promise.resolve({ error: 'Waitlist is not enabled yet — email support@brandforge-os.com and we will add you to the list.' }) });
    msg = await submitForm(dom, 'buyer@example.com', 'owner');
    assert('backend 501 → actionable "not enabled / email support" message', /support@brandforge-os\.com/i.test(msg), 'msg=' + msg);

    w.fetch = () => Promise.resolve({ ok: false, status: 500, json: () => Promise.resolve({ error: 'Could not save your spot' }) });
    msg = await submitForm(dom, 'buyer@example.com', 'owner');
    assert('backend 5xx → honest failure message', /Could not save/i.test(msg), 'msg=' + msg);

    msg = await submitForm(dom, 'not-an-email', 'owner');
    assert('invalid email → validation message', /valid email/i.test(msg), 'msg=' + msg);

    let fetchCalls = 0;
    w.fetch = () => { fetchCalls++; return Promise.resolve({ ok: true, status: 200, json: () => Promise.resolve({ ok: true }) }); };
    msg = await submitForm(dom, 'buyer@example.com', 'owner', 'i-am-a-bot');
    assert('honeypot filled → fake success, still no fetch', /on the list/i.test(msg) && fetchCalls === 0, 'msg=' + msg);
  }

  console.log('\n=== STATE A2 — domain integrity (regression guard, audit 2026-08-28) ===');
  {
    const dom = await makeDom(pricingHtml);
    const CFG = dom.window.BRANDFORGE_LAUNCH;

    // The support inbox must live on the SAME domain as the site itself.
    // Regression: it used to be support@brandforgeos.com — an unowned,
    // un-hyphenated lookalike of the real brandforge-os.com (every mail bounced).
    const siteHost = CFG.effectiveSiteUrl.replace(/^https?:\/\//, '').split('/')[0];
    // Email addresses never carry a `www.` prefix, but the site serves at
    // www.<domain> while the inbox lives at <domain> (apex). Normalize both by
    // stripping a leading www. so they compare as the same registrable domain.
    const norm = (h) => h.replace(/^www\./i, '');
    const supportHost = norm(String(CFG.support_email).split('@')[1] || '');
    assert('support_email domain === production site domain', supportHost === norm(siteHost),
      supportHost + ' !== ' + norm(siteHost));

    // The dead legacy domain must not appear in ANY shipped sales file.
    const shipped = [
      ...fs.readdirSync(path.join(SALES, 'assets')).filter(f => f.endsWith('.js')).map(f => 'assets/' + f),
      ...fs.readdirSync(SALES).filter(f => f.endsWith('.html')),
    ];
    const offenders = shipped.filter(f => read(f).includes('brandforgeos.com'));
    assert('no shipped sales file references dead domain brandforgeos.com',
      offenders.length === 0, offenders.join(', '));
  }

  console.log('\n=== STATE B — operator-configured (simulates pasting real values) ===');
  {
    const dom = await makeDom(pricingHtml);
    const w = dom.window;
    const CFG = w.BRANDFORGE_LAUNCH;

    // 0.1 — waitlist endpoint is wired from hosted_url; operator may also set
    //        an explicit waitlist_endpoint.
    assert('waitlistReady === true (endpoint resolved)', CFG.waitlistReady === true);
    assert('waitlist endpoint resolves to the cloud backend', CFG.waitlistEndpoint() === 'https://app.brandforge-os.com/api/waitlist', CFG.waitlistEndpoint());

    let lastFetch = null;
    w.fetch = (url, opts) => { lastFetch = { url, opts }; return Promise.resolve({ ok: true, status: 200, json: () => Promise.resolve({ ok: true, queued: true }) }); };
    let msg = await submitForm(dom, 'buyer@example.com', 'agency_source');
    assert('posts to the cloud /api/waitlist backend', !!lastFetch && lastFetch.url === 'https://app.brandforge-os.com/api/waitlist', lastFetch && lastFetch.url);
    const payload = lastFetch && JSON.parse(lastFetch.opts.body);
    assert('payload carries email + selected tier', !!payload && payload.email === 'buyer@example.com' && payload.tier === 'agency_source', JSON.stringify(payload));
    assert('backend success → confirmation shown', /on the list/i.test(msg), 'msg=' + msg);

    // Backend responds 501 (table not created yet) → honest message.
    w.fetch = () => Promise.resolve({ ok: false, status: 501, json: () => Promise.resolve({ error: 'Waitlist is not enabled yet — email support@brandforge-os.com and we will add you to the list.' }) });
    msg = await submitForm(dom, 'buyer2@example.com', 'agency_source');
    assert('backend 501 → honest "not enabled" message', /support@brandforge-os\.com/i.test(msg), 'msg=' + msg);

    // 0.2 — real Paddle sandbox credentials pasted into config.js
    CFG.paddle_client_token = 'test_01JABCDEFGHIJK1234567890';
    CFG.prices.owner.id = 'pri_01jowner00000000000000000';
    CFG.prices.agency_source.id = 'pri_01jasource000000000000000';
    assert('public token + prices alone cannot enable paid checkout', CFG.paddleReady === false);
    CFG.desktop_checkout_enabled=true;
    assert('both desktop tiers configured', JSON.stringify(CFG.configuredTiers()) === '["owner","agency_source"]');
    w.refreshDesktopCtas();
    assert('public flag + prices do not promise checkout without server state',w.document.querySelector('[data-cta-tier="owner"]').textContent.includes('waitlist'));
    w.fetch=async()=>({ok:true,json:async()=>capabilities});
    await w.BRANDFORGE_AVAILABILITY.refresh();
    const labelOf = tier => w.document.querySelector('[data-cta-tier="' + tier + '"]').textContent;
    assert('fully configured → CTAs promise checkout, not the waitlist', labelOf('owner') === 'Buy once — $199' && labelOf('agency_source') === 'Buy once — $499', labelOf('owner') + ' | ' + labelOf('agency_source'));

    // The SDK opens only a server-authorized transaction; it never chooses
    // raw prices or assumes a client-side event grants fulfillment.
    let openedWith=null,onEvent=null,checkouts=[];
    w.Paddle={Environment:{set(){}},Initialize(o){onEvent=o.eventCallback;},Checkout:{open(o){openedWith=o;}}};
    w.fetch=async(url,opts)=>({ok:true,status:200,json:async()=>{
      if(url.endsWith('/capabilities'))return capabilities;
      if(url.endsWith('/paddle-client-token'))return {token:'test_fixture',environment:'sandbox'};
      checkouts.push(JSON.parse(opts.body));return {transaction_id:'txn_'+JSON.parse(opts.body).tier};
    }});
    await w.brandforgeBuy('owner');
    assert('Owner opens the authorized transaction, not a raw price',openedWith?.transactionId==='txn_owner'&&!openedWith.items);
    onEvent({name:'checkout.closed'});openedWith=null;
    await w.brandforgeBuy('agency_source');
    assert('Source opens its own authorized transaction',openedWith?.transactionId==='txn_agency_source');
    assert('server receives only an allowlisted edition request',checkouts.length===2&&checkouts[0].tier==='owner');

    // Legacy price metadata is not authoritative; server readiness controls both editions.
    CFG.prices.agency_source.id = '';
    assert('partial config → configuredTiers drops agency_source', JSON.stringify(CFG.configuredTiers()) === '["owner"]');
    w.refreshDesktopCtas();
    assert('legacy price metadata cannot override verified server state', labelOf('owner') === 'Buy once — $199' && labelOf('agency_source') === 'Buy once — $499');
    onEvent({name:'checkout.closed'});openedWith=null;
    w.fetch=async()=>({ok:true,json:async()=>({...capabilities,desktop:{checkout_enabled:false}})});
    await w.brandforgeBuy('owner');
    assert('server closure is rechecked before SDK or transaction',openedWith===null&&labelOf('owner').includes('waitlist'));
    w.fetch=async()=>{throw new Error('offline')};await w.BRANDFORGE_AVAILABILITY.refresh();
    assert('network failure does not retain an old buy label',labelOf('agency_source').includes('waitlist'));
  }

  console.log('\n=== STATE C — homepage fallback (index.html has no waitlist form) ===');
  {
    const dom = await makeDom(indexHtml, 'https://brandforge-os.com/');
    const w = dom.window;
    assert('index.html has no #waitlist element', w.document.getElementById('waitlist') === null);
    // jsdom blocks real navigation but reports it as a jsdomError — that IS
    // the observable redirect attempt.
    const before = dom.__errors.length;
    w.brandforgeBuy('owner'); // unconfigured on this dom
    const navigated = dom.__errors.slice(before).some(m => /navigation/i.test(m));
    assert('unconfigured buy CTA attempts redirect (to pricing.html#waitlist)', navigated, 'errors=' + JSON.stringify(dom.__errors));
    assert('waitlist fallback preserves the selected Desktop tier', buyJs.includes("pricing?tier=")&&buyJs.includes("#waitlist"));
  }

  console.log(`\nRESULT: ${pass} passed, ${fail} failed`);
  process.exit(fail ? 1 : 0);
})().catch(e => { console.error('HARNESS ERROR:', e); process.exit(2); });
