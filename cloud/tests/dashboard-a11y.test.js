/**
 * Accessibility + structure gate for the Cloud dashboard (`public/index.html`).
 *
 * This is the file the original audit flagged as having ZERO automated a11y
 * coverage (only sales/* was gated). It is served at app.brandforge-os.com —
 * the login/signup/workspace every customer actually uses.
 *
 * Covers the audit backlog:
 *   §2.1  label -> input association (no orphan labels, no dangling `for`)
 *   §2.4  banner-size picker is now a touch-friendly chip group, not a native
 *         <select multiple> that needs Ctrl/Cmd
 *   §4.4  a light theme exists (data-theme="light") with a toggle button
 *
 * Axe runs jsdom (no real rendering), so color-contrast is disabled just like
 * the sales gate; semantic/ARIA/structural rules run fully.
 */
import fs from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";
import { createRequire } from "node:module";
import { describe, it, expect } from "vitest";
import { JSDOM, VirtualConsole } from "jsdom";

const require = createRequire(import.meta.url);
const __dirname = path.dirname(fileURLToPath(import.meta.url));
const PUBLIC = path.join(__dirname, "..", "public");

function loadDom() {
  const file = path.join(PUBLIC, "index.html");
  const html = fs.readFileSync(file, "utf8");
  const vc = new VirtualConsole();
  const dom = new JSDOM(html, {
    url: "https://app.brandforge-os.com/",
    runScripts: "outside-only",
    pretendToBeVisual: true,
    virtualConsole: vc,
  });
  return dom;
}

function runAxe(dom) {
  const w = dom.window;
  // Evaluate axe's source inside the jsdom window so axe uses the same DOM.
  w.eval(fs.readFileSync(require.resolve("axe-core/axe.min.js"), "utf8"));
  return w.axe.run(w.document, {
    rules: { "color-contrast": { enabled: false } },
  });
}

describe("dashboard (cloud/public/index.html) — axe accessibility", () => {
  it("has zero axe violations (color-contrast disabled for jsdom)", async () => {
    const dom = loadDom();
    const results = await runAxe(dom);
    if (results.violations.length) {
      const summary = results.violations
        .map(
          (v) =>
            `[${v.impact}] ${v.id}: ${v.nodes.length} node(s) — ` +
            v.nodes.slice(0, 3).map((n) => n.html.slice(0, 120)).join(" | ")
        )
        .join("\n      ");
      expect(results.violations, `axe violations:\n      ${summary}`).toHaveLength(0);
    }
    dom.window.close();
  });
});

describe("dashboard label & structure invariants (audit §2.1, §2.4, §4.4)", () => {
  it("every <label> is associated: has a valid `for` or wraps a form control", () => {
    const dom = loadDom();
    const doc = dom.window.document;
    const labels = [...doc.querySelectorAll("label")];
    expect(labels.length).toBeGreaterThan(0);
    const orphans = [];
    for (const lab of labels) {
      const forId = lab.getAttribute("for");
      const wraps = !!lab.querySelector("input,select,textarea,meter,progress");
      if (!forId && !wraps) orphans.push(`<label>${lab.textContent.trim()}</label>`);
    }
    expect(orphans, `orphan labels (no for, no wrapped control): ${orphans.join(" ; ")}`).toEqual([]);
    // Every `for` must resolve to an existing element id.
    for (const lab of labels) {
      const forId = lab.getAttribute("for");
      if (forId) {
        expect(doc.getElementById(forId), `<label for="${forId}"> has no matching element`)
          .not.toBeNull();
      }
    }
    dom.window.close();
  });

  it("has no duplicate element ids", () => {
    const dom = loadDom();
    const doc = dom.window.document;
    const seen = new Set();
    const dups = [];
    for (const el of doc.querySelectorAll("[id]")) {
      const id = el.id;
      if (seen.has(id)) dups.push(id);
      seen.add(id);
    }
    expect(dups).toEqual([]);
    dom.window.close();
  });

  it("banner-size picker is a touch-friendly chip group, not a native multi-select (§2.4)", () => {
    const dom = loadDom();
    const doc = dom.window.document;
    const preset = doc.getElementById("c-preset");
    expect(preset).not.toBeNull();
    expect(preset.tagName.toLowerCase()).toBe("div");
    expect(preset.className).toContain("chip-grid");
    // No <select multiple> banner picker anymore.
    const multiSelect = doc.querySelector("#c-preset[multiple]");
    expect(multiSelect).toBeNull();
    // The sizes heading is a group heading (aria-labelledby), not an orphan label.
    const heading = doc.getElementById("c-sizes-label");
    expect(heading).not.toBeNull();
    expect(heading.tagName.toLowerCase()).not.toBe("label");
    dom.window.close();
  });

  it("has a light-theme block and a toggle button (§4.4)", () => {
    const dom = loadDom();
    const doc = dom.window.document;
    const style = doc.head.querySelector("style");
    expect(style.textContent).toContain('[data-theme="light"]');
    const toggle = doc.getElementById("nav-theme");
    expect(toggle).not.toBeNull();
    expect(toggle.getAttribute("aria-label")).toMatch(/theme/i);
    dom.window.close();
  });
});
