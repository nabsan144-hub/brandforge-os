/* Dashboard contrast gate (port of sales/tests/theme-contrast.test.js).
   The dashboard CSS is inline in cloud/public/index.html. Axe's jsdom run
   cannot compute colors, so this static gate owns the claim:
   any gold background must pair with the dark gold-ink text (in BOTH themes),
   and the light theme must actually redefine the tokens. */
import { describe, it, expect } from "vitest";
import { readFileSync } from "node:fs";
import { join } from "node:path";

const html = readFileSync(join(process.cwd(), "public", "index.html"), "utf8");
const styles = html.match(/<style[^>]*>([\s\S]*?)<\/style>/g)?.map(s => s) || [];

describe("dashboard theme contrast (static gate)", () => {
  it("defines the theme tokens and a light theme override", () => {
    const all = html;
    expect(all).toMatch(/--gold:\s*#E8B54A/);           // dark gold token
    expect(all).toMatch(/--ink:\s*#F8FAFC/);            // dark ink token
    expect(all).toMatch(/\[data-theme="light"\][^{]*\{[^}]*--gold:/); // light redefines gold
    expect(all).toMatch(/\[data-theme="light"\][^{]*\{[^}]*--ink:/);  // light redefines ink
  });
  it("every gold background pairs with the dark gold ink (no washed-out buttons)", () => {
    // .btn.gold{background:var(--gold);color:#0A0D14} + light override must do the same
    expect(html).toMatch(/background:\s*var\(--gold\);[^}]*color:\s*#0A0D14/);
    const light = html.match(/\[data-theme="light"\][^{]*\{[^}]*\}/g)?.find(r => r.includes(".btn.gold")) || "";
    expect(light).toMatch(/background:\s*#E8B54A;[^}]*color:\s*#0A0D14/);
  });
  it("no hardcoded near-white ink declared against a gold background", () => {
    const bad = styles.filter(s => /background:\s*(?:var\(--gold\)|#E8B54A)/.test(s) && /color:\s*(?:#F8FAFC|#fff|white)/i.test(s));
    expect(bad).toEqual([]);
  });
  it("empty plan pill and focus-visible fixes remain present", () => {
    expect(html).toMatch(/#nav-plan:empty\{display:none\}/);
    expect(html).toMatch(/input:focus-visible/);
  });
});
