import { describe, it, expect } from "vitest";
import { readFileSync, existsSync } from "node:fs";
import { fileURLToPath } from "node:url";
import path from "node:path";

const ROOT = path.dirname(path.dirname(fileURLToPath(import.meta.url)));
const vendor = path.join(ROOT, "public", "vendor", "supabase.mjs");

describe("supabase-js is vendored (no esm.sh runtime dependency)", () => {
  it("ships a self-contained browser ESM bundle in cloud/public/vendor/", () => {
    expect(existsSync(vendor)).toBe(true);
    const js = readFileSync(vendor, "utf8");
    expect(js.length).toBeGreaterThan(50_000);
    // Must be a true ESM entry that exports createClient, not a re-export stub
    // that still imports from a CDN.
    expect(js).toMatch(/export\s*\{[^}]*createClient/);
    expect(js).not.toMatch(/from\s*["']https?:\/\//);
  });

  it("the cloud SPA imports the local vendor file, not esm.sh", () => {
    // The SPA logic is now externalized to public/app.js (loaded via
    // <script type="module" src="/app.js">) so the CSP can drop 'unsafe-inline'.
    const spa = readFileSync(path.join(ROOT, "public", "index.html"), "utf8");
    const app = readFileSync(path.join(ROOT, "public", "app.js"), "utf8");
    expect(app).toContain('import { createClient } from "/vendor/supabase.mjs"');
    expect(spa).toMatch(/<script type="module" src="\/app\.js"><\/script>/);
    expect(spa).not.toMatch(/esm\.sh/);
    expect(spa).not.toMatch(/cdn\.jsdelivr/);
    expect(app).not.toMatch(/esm\.sh/);
    expect(app).not.toMatch(/cdn\.jsdelivr/);
  });

  it("the cloud CSP no longer allows esm.sh or jsdelivr, but still allows Paddle", () => {
    const config = JSON.parse(readFileSync(path.join(ROOT, "vercel.json"), "utf8"));
    const csp = config.headers.flatMap((entry) => entry.headers || [])
      .find((header) => header.key === "Content-Security-Policy")?.value || "";
    expect(csp).toContain("https://cdn.paddle.com");
    expect(csp).toContain("script-src 'self'");
    // SEC-1: 'unsafe-inline' must NOT be in script-src (the SPA script is
    // externalized to /app.js, so the inline script loophole is closed).
    const scriptSrc = (csp.match(/script-src[^;]*/) || [""])[0];
    expect(scriptSrc).not.toMatch(/unsafe-inline/);
    expect(csp).not.toMatch(/esm\.sh/);
    expect(csp).not.toMatch(/cdn\.jsdelivr/);
  });

  it("the CSP frame-src allows the Turnstile and Paddle iframes", () => {
    const config = JSON.parse(readFileSync(path.join(ROOT, "vercel.json"), "utf8"));
    const csp = config.headers.flatMap((entry) => entry.headers || [])
      .find((header) => header.key === "Content-Security-Policy")?.value || "";
    expect(csp).toMatch(/frame-src[^;]*https:\/\/challenges\.cloudflare\.com/);
    expect(csp).toMatch(/frame-src[^;]*https:\/\/.*paddle\.com/);
  });
});
