// Regression tests for the single catch-all Function (api/index.js) that
// replaced 23 per-file Vercel Functions (Hobby caps deployments at 12
// Functions). These prove URL dispatch still reaches the right handlers:
//   - exact paths (health, me/export)
//   - dynamic path params (/api/campaigns/:id)
//   - unknown paths return JSON 404 (per-file mode gave platform text 404)
//   - trailing slashes normalize to the same route
//   - named HTTP-method exports route through the same dispatcher
import { describe, it, expect, vi } from "vitest";

vi.mock("../api/_lib/sb.js", () => ({
  authUser: vi.fn(async () => null),
  admin: vi.fn(),
  json: (b, s = 200) =>
    new Response(JSON.stringify(b), {
      status: s,
      headers: { "Content-Type": "application/json", "Cache-Control": "no-store" },
    }),
}));
vi.mock("../api/_lib/limit.js", () => ({ rateLimit: vi.fn(async () => true) }));

import dispatcher, { GET, POST } from "../api/index.js";

describe("api catch-all dispatcher (Hobby 12-Function refactor)", () => {
  it("routes the exact /api/health path to the health handler", async () => {
    const r = await dispatcher(new Request("https://app.brandforge-os.com/api/health"));
    expect(r.status).toBe(200);
    expect(await r.json()).toMatchObject({ ok: true });
  });

  it("normalizes a trailing slash to the same route", async () => {
    const r = await dispatcher(new Request("https://app.brandforge-os.com/api/health/"));
    expect(r.status).toBe(200);
  });

  it("routes /api/me/export (a previously nested file) to its handler", async () => {
    const r = await dispatcher(new Request("https://app.brandforge-os.com/api/me/export"));
    expect(r.status).toBe(401); // authUser mocked to null -> Not signed in
  });

  it("routes dynamic /api/campaigns/:id and passes params", async () => {
    const id = crypto.randomUUID();
    const r = await dispatcher(new Request(`https://app.brandforge-os.com/api/campaigns/${id}`));
    expect(r.status).toBe(401); // auth first -> Not signed in
  });

  it("routes owner-authorized private asset downloads", async () => {
    const r=await dispatcher(new Request(`https://app.brandforge-os.com/api/campaigns/${crypto.randomUUID()}/assets`));
    expect(r.status).toBe(401);
  });

  it("routes deeper dynamic /api/campaigns/:id/deliver", async () => {
    const r = await dispatcher(
      new Request(`https://app.brandforge-os.com/api/campaigns/${crypto.randomUUID()}/deliver`, {
        method: "POST",
        body: "{}",
        headers: { "content-type": "application/json" },
      })
    );
    // WhatsApp is not configured in tests, so the deliver handler itself
    // answers 404 "Delivery not enabled" — which proves the deeper dynamic
    // route reached the deliver handler (the dispatcher's own miss would
    // return 404 {"error":"Not found"}).
    expect(r.status).toBe(404);
    expect(await r.json()).toMatchObject({ error: "Delivery not enabled" });
  });

  it("returns JSON 404 for unknown api paths", async () => {
    const r = await dispatcher(new Request("https://app.brandforge-os.com/api/definitely-not-a-route"));
    expect(r.status).toBe(404);
    expect(await r.json()).toMatchObject({ error: "Not found" });
  });

  it("named method exports dispatch through the same table", async () => {
    const r = await GET(new Request("https://app.brandforge-os.com/api/health"));
    expect(r.status).toBe(200);
    const r2 = await POST(new Request("https://app.brandforge-os.com/api/me/export", { method: "POST" }));
    // me/export handler enforces GET-only -> 405 (proves POST reached the handler)
    expect(r2.status).toBe(405);
  });

  it("exact critical paths still work when invoked via their re-export files", async () => {
    const healthFile = (await import("../api/health.js")).default;
    const r = await healthFile(new Request("https://app.brandforge-os.com/api/health"));
    expect(r.status).toBe(200);
  });
});
