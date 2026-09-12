/* Accessibility regression gate (audit backlog 2026-08-28).
   Runs axe-core over every shipped sales page in jsdom and fails on any
   violation. Catches a11y regressions on every push instead of relying on
   the periodic manual sweeps (Sweep 3 did the last manual pass).

   Notes:
   - jsdom has no real rendering engine, so color-contrast and other
     visual rules report as "incomplete" (not violations) — those stay
     covered by the manual Lighthouse passes. Structural/ARIA/semantic
     rules (the ones that actually break screen readers) run fully.
   - Scripts are NOT executed (runScripts: 'outside-only') so the scan is
     hermetic — no network, no external CSS/JS. */
const fs = require('fs');
const path = require('path');
const { JSDOM, VirtualConsole } = require('jsdom');
const axe = require('axe-core');

const SALES = path.join(__dirname, '..');

const PAGES = [
  'index.html',
  'pricing.html',
  'agents.html',
  'docs.html',
  'changelog.html',
  'tools.html',
  'workspace.html',
  'privacy.html',
  'terms.html',
  'refund.html',
  '404.html',
  'demo.html',
  'vs-canva-ad-creator.html',
  'best-ad-copy-generator.html',
];

// Rules that cannot be meaningfully evaluated without a real rendering
// engine (jsdom reports layout as zero-size everywhere).
const AXE_OPTIONS = {
  rules: {
    'color-contrast': { enabled: false },
  },
};

let pass = 0, fail = 0;
function assert(name, cond, extra) {
  if (cond) { pass++; console.log('  ✓ ' + name); }
  else { fail++; console.log('  ✗ ' + name + (extra ? '\n      ' + extra : '')); }
}

function summarize(violations) {
  return violations
    .map(v => `[${v.impact}] ${v.id}: ${v.nodes.length} node(s) — ` +
      v.nodes.slice(0, 3).map(n => n.html.slice(0, 120)).join(' | '))
    .join('\n      ');
}

(async () => {
  console.log('=== Accessibility gate (axe-core) — shipped sales pages ===');
  for (const page of PAGES) {
    const file = path.join(SALES, page);
    if (!fs.existsSync(file)) { assert(page + ' exists', false, 'file missing'); continue; }
    const html = fs.readFileSync(file, 'utf8');
    const vc = new VirtualConsole(); // swallow jsdom noise (unexecuted inline scripts etc.)
    const dom = new JSDOM(html, {
      url: 'https://brandforge-os.com/' + (page === 'index.html' ? '' : page),
      runScripts: 'outside-only',
      pretendToBeVisual: true,
      virtualConsole: vc,
    });
    const w = dom.window;
    // axe-core needs a same-window axe instance: evaluate its source inside jsdom.
    w.eval(fs.readFileSync(require.resolve('axe-core/axe.min.js'), 'utf8'));
    const results = await w.axe.run(w.document, AXE_OPTIONS);
    assert(page + ' — no axe violations', results.violations.length === 0,
      summarize(results.violations));
    w.close();
  }

  console.log(`\nRESULT: ${pass} passed, ${fail} failed`);
  process.exit(fail ? 1 : 0);
})().catch(e => { console.error('A11Y HARNESS ERROR:', e); process.exit(2); });
