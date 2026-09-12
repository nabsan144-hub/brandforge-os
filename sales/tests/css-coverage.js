#!/usr/bin/env node
/**
 * CSS coverage regression guard (incident 2026-08-30):
 * assets/tailwind.css was a hand-pruned one-off build from an older page set;
 * classes used later (px-3.5, py-1.5, gap-3.5, clamps, semantic colors) were
 * never compiled → buttons clipped and ~60 subtle styling gaps shipped live.
 * Tailwind is now built from everything: `npm run build:css` + config content
 * globs covering all pages. This test fails if any class token used in any
 * sales page (including inline <style> blocks) has no rule anywhere in the
 * shipped CSS — catching both forgotten rebuilds and bad arbitrary-value
 * syntax (spaces instead of underscores inside text-[...]).
 */
const fs = require('node:fs');
const path = require('node:path');

const dir = path.join(__dirname, '..');

let css = '';
for (const f of fs.readdirSync(path.join(dir, 'assets')).filter(n=>n.endsWith('.css')).map(n=>'assets/'+n)) {
  css += fs.readFileSync(path.join(dir, f), 'utf8');
}

const used = new Set();
for (const f of fs.readdirSync(dir).filter((n) => n.endsWith('.html'))) {
  const src = fs.readFileSync(path.join(dir, f), 'utf8');
  for (const m of src.matchAll(/class="([^"]+)"/g)) {
    for (const tok of m[1].split(/\s+/)) if (tok) used.add(tok);
  }
  for (const m of src.matchAll(/<style[^>]*>([\s\S]*?)<\/style>/g)) css += m[1];
}

const ESCAPE = { '[': '\\[', ']': '\\]', '.': '\\.', ':': '\\:', '/': '\\/', '%': '\\%', '#': '\\#', '(': '\\(', ')': '\\)' };
const sel = (c) => [...c].map((ch) => ESCAPE[ch] ?? ch).join('');
const JS_HOOKS = new Set(['copy-docs', 'txt', 'group', 'peer']); // JS querySelector hooks, not style utilities

const missing = [];
for (const tok of [...used].sort()) {
  if (JS_HOOKS.has(tok) || tok.startsWith('[')) continue;
  const s = '.' + sel(tok);
  // Tailwind escapes commas inside arbitrary values as \2c
  if (css.includes(s) || css.includes(s.replaceAll(',', '\\2c ')) || css.includes(s.replaceAll(',', '\\2c'))) continue;
  missing.push(tok);
}

if (missing.length) {
  console.error('✗ classes used in sales pages but MISSING from shipped CSS:');
  for (const m of missing) console.error('  -', m);
  console.error('Fix: cd sales && npm run build:css  (and check arbitrary values use _underscores_, not spaces)');
  process.exit(1);
}
console.log(`RESULT: css coverage ✓ (${used.size} class tokens all present)`);
