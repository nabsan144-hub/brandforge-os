import { describe, it, expect } from "vitest";
import { clientIp } from "../api/_lib/routes/campaigns.js";

function reqWithHeaders(headers) {
  return { headers: { get: (name) => headers[name] ?? null } };
}

describe("clientIp (rate-limit source, audit P1.4)", () => {
  it("trusts the LAST hop of x-vercel-forwarded-for (platform-set, not spoofable)", () => {
    const r = reqWithHeaders({ "x-forwarded-for": "6.6.6.6, 5.5.5.5", "x-vercel-forwarded-for": "1.2.3.4, 9.9.9.9" });
    expect(clientIp(r)).toBe("9.9.9.9");
  });

  it("falls back to x-real-ip when x-vercel-forwarded-for is absent", () => {
    const r = reqWithHeaders({ "x-real-ip": "2.2.2.2", "x-forwarded-for": "6.6.6.6, 5.5.5.5" });
    expect(clientIp(r)).toBe("2.2.2.2");
  });

  it("never trusts the first x-forwarded-for hop (attacker-controlled)", () => {
    // Client prepends a spoofed value; the true client is the LAST hop.
    const r = reqWithHeaders({ "x-forwarded-for": "6.6.6.6, 5.5.5.5" });
    expect(clientIp(r)).toBe("5.5.5.5");
    expect(clientIp(r)).not.toBe("6.6.6.6");
  });

  it("returns 'unknown' when there is no IP header", () => {
    const r = reqWithHeaders({});
    expect(clientIp(r)).toBe("unknown");
  });

  it("is safe when req.headers is missing entirely", () => {
    expect(clientIp({})).toBe("unknown");
  });
});
