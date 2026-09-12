/* Theme-contrast regression gate (incident 2026-08-30):
   Gold buttons were painted with a HARDCODED dark ink (#0A0D14) against
   background:var(--gold). In light theme --gold flips to rich amber #B47D12,
   so the nav "Start free" pill rendered dark-gold-on-black — unreadable.
   The correct pattern is background:rgb(var(--sb-gold-rgb)) +
   color:var(--gold-ink) (or the .btn-gold/.cta-gold classes, which do
   exactly this). This test fails CI if any gold background is paired with
   a hardcoded ink/text color again. */
const fs = require('node:fs');
const path = require('node:path');

const dir = path.join(__dirname, '..');
const files = [
  ...fs.readdirSync(dir).filter((n) => n.endsWith('.html')).map((n) => path.join(dir, n)),
  ...fs.readdirSync(path.join(dir, 'assets')).filter((n) => n.endsWith('.css')).map((n) => path.join(dir, 'assets', n)),
];

// gold background without the theme-aware ink on the same declaration
const BAD = [];
const GOLD_BG = /background(?:-color)?\s*:\s*(?:rgb\s*\(\s*var\(--sb-gold-rgb\)\s*\)|var\(--gold\))/;

for (const f of files) {
  const src = fs.readFileSync(f, 'utf8');
  // check line-by-line (incl. inline `style="..."` attrs and css class bodies)
  src.split(/\r?\n/).forEach((line, i) => {
    if (!GOLD_BG.test(line)) return;
    // split a css rule line into declarations before matching the ink
    const decls = line.split(';');
    decls.forEach((d, j) => {
      if (!GOLD_BG.test(d)) return;
      const rest = decls.slice(j + 1).join(';') + ';' + decls.slice(0, j).join(';');
      if (rest.includes('var(--gold-ink)')) return;
      if (/(color)\s*:\s*#0?[a-f0-9]{3,8}\b/i.test(rest) && !rest.includes('var(--gold-ink)')) {
        BAD.push(`${path.basename(f)}:${i + 1} — gold background with hardcoded ink`);
      } else if (/color\s*:\s*#/.test(rest)) {
        BAD.push(`${path.basename(f)}:${i + 1} — gold background with hardcoded text color`);
      }
    });
  });
}

if (BAD.length) {
  console.error('RESULT: theme-contrast ✗');
  BAD.forEach((b) => console.error('  ' + b));
  process.exit(1);
}
console.log(`RESULT: theme-contrast ✓ (${files.length} files scanned, all gold backgrounds use theme-aware ink)`);

// ---- §1.1 incident (2026-08-30): 7 pages shipped footer HTML containing
// literal backslash-escaped quotes (class=\"...\"). Browsers treat the
// backslash as part of an UNQUOTED attribute value, so every class after
// the first word silently vanished — footer lost flex layout on 7 pages.
// Lint/tests/axe all passed because the markup is technically "valid".
const escaped = [];
for (const f of files) {
  const src = fs.readFileSync(f, 'utf8');
  // any raw backslash+quote inside an HTML attribute position is suspicious
  src.split(/\r?\n/).forEach((line, i) => {
    // ignore inside <script> blocks… cheap approximation: flag attribute-like
    if (/=\\"/.test(line) || /\\\"\s*>/.test(line)) {
      escaped.push(`${path.basename(f)}:${i + 1} — literal backslash-quote in markup`);
    }
  });
}
if (escaped.length) {
  console.error('RESULT: escaped-quote ✗');
  escaped.forEach((b) => console.error('  ' + b));
  process.exit(1);
}
console.log('RESULT: escaped-quote ✓ (no literal backslash-quotes in attributes)');

// ---- §2 (2026-09-05): light-mode gold TEXT contrast gate ----
// .text-gold must flip to var(--gold-text) in light theme, and that value
// must hold >=4.5:1 on BOTH the paper background and white cards. Gold
// buttons: light-theme primary CTAs are DARK INK PILL + cream text (the amber
// pill with dark ink read as muddy brown on paper — founder-flagged). The test
// pins that override and its contrast; gold text on paper stays >=4.5:1.
// Catches the 3.4:1 amber-on-paper regression an external review found.
{
  const css = fs.readFileSync(path.join(dir, 'assets', 'theme.css'), 'utf8');
  const tokens = JSON.parse(fs.readFileSync(path.join(dir,'../shared/design-tokens.json'),'utf8'));
  const generated = fs.readFileSync(path.join(dir,'assets/semantic-tokens.css'),'utf8');
  const must = (cond, msg) => { if (!cond) { console.error('RESULT: light-gold-contrast ✗ — ' + msg); process.exit(1); } };
  must(generated.includes('--gold-text:var(--bf-accent)'), 'canonical gold text alias missing');
  const goldText = tokens.light.accent.slice(1);
  const lum = (hex) => {
    const [r, g, b] = [0, 2, 4].map((i) => parseInt(hex.slice(i, i + 2), 16) / 255);
    const f = (v) => (v <= 0.04045 ? v / 12.92 : Math.pow((v + 0.055) / 1.055, 2.4));
    return 0.2126 * f(r) + 0.7152 * f(g) + 0.0722 * f(b);
  };
  const ratio = (a, b) => { const [l1, l2] = [lum(a), lum(b)].sort((x, y) => y - x); return (l1 + 0.05) / (l2 + 0.05); };
  must(/\[data-theme="light"\]\s*\.text-gold\s*\{\s*color:\s*var\(--gold-text\)/.test(css),
    'light .text-gold must use var(--gold-text)');
  must(ratio(goldText, 'F6F4EF') >= 4.5, `gold text ${goldText} on paper #F6F4EF is ${ratio(goldText, 'F6F4EF').toFixed(2)}:1 (<4.5)`);
  must(ratio(goldText, 'FFFFFF') >= 4.5, `gold text ${goldText} on white cards is ${ratio(goldText, 'FFFFFF').toFixed(2)}:1 (<4.5)`);
  const button = css.match(/\[data-theme="light"\]\s*\.btn-gold,\s*\n?\[data-theme="light"\]\s*\.cta-gold\s*\{([\s\S]*?)\}/i);
  must(button, 'light .btn-gold/.cta-gold override block not found');
  must(/background-color:\s*#14181F/i.test(button[1]) && /color:\s*#F6F4EF/i.test(button[1]),
    'light primary buttons must be the dark-ink pill (#14181F bg + #F6F4EF text), not amber');
  must(ratio('14181F', 'F6F4EF') >= 4.5, `button cream #F6F4EF on ink #14181F is ${ratio('14181F', 'F6F4EF').toFixed(2)}:1 (<4.5)`);
  console.log(`RESULT: light-gold-contrast ✓ (text ${ratio(goldText, 'F6F4EF').toFixed(2)}:1 on paper, buttons ${ratio('14181F', 'F6F4EF').toFixed(2)}:1 dark-pill)`);
}
