vi.mock('../api/_lib/limit.js',()=>({rateLimit:vi.fn(async()=>true)}));
import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";

vi.mock("../api/_lib/sb.js", () => ({
  admin: vi.fn(),
}));

import { admin } from "../api/_lib/sb.js";
import handler from "../api/_lib/routes/waitlist.js";

const okSb = () => ({
  from: vi.fn(() => ({
    upsert: vi.fn(() => ({
      select: vi.fn(() => ({
        single: vi.fn(() => Promise.resolve({ data: { email: "a@b.co" }, error: null })),
      })),
    })),
  })),
});

const missingTableSb = () => ({
  from: vi.fn(() => ({
    upsert: vi.fn(() => ({
      select: vi.fn(() => ({
        single: vi.fn(() => Promise.resolve({ data: null, error: { code: "PGRST205", message: 'relation "public.waitlist" does not exist' } })),
      })),
    })),
  })),
});

function webReq(method, body) {
  return new Request("https://app.brandforge-os.com/api/waitlist", {
    method,
    headers: { "Content-Type": "application/json" },
    body: body ? JSON.stringify(body) : undefined,
  });
}

beforeEach(() => {
  vi.clearAllMocks();
});
afterEach(() => {
  vi.restoreAllMocks();
});

describe("waitlist endpoint", () => {
  it("accepts a valid email + tier and stores it (upsert on email)", async () => {
    const sb = okSb();
    admin.mockReturnValue(sb);
    const res = await handler(webReq("POST", { email: "a@b.co", tier: "owner" }));
    expect(res.status).toBe(200);
    const body = await res.json();
    expect(body.ok).toBe(true);
    expect(body.queued).toBe(true);
    expect(sb.from).toHaveBeenCalledWith("waitlist");
    const upsert = sb.from.mock.results[0].value.upsert;
    expect(upsert).toHaveBeenCalledWith({ email: "a@b.co", tier: "owner" }, { onConflict: "email" });
  });

  it("normalizes a valid uppercase email and defaults unknown tiers", async () => {
    const sb = okSb();
    admin.mockReturnValue(sb);
    const res = await handler(webReq("POST", { email: "  A@B.CO ", tier: "hacker" }));
    expect(res.status).toBe(200);
    const upsert = sb.from.mock.results[0].value.upsert;
    expect(upsert).toHaveBeenCalledWith({ email: "a@b.co", tier: "undecided" }, { onConflict: "email" });
  });

  it("rejects an invalid email", async () => {
    const sb = okSb();
    admin.mockReturnValue(sb);
    const res = await handler(webReq("POST", { email: "not-an-email", tier: "owner" }));
    expect(res.status).toBe(400);
    expect(sb.from).not.toHaveBeenCalled();
  });

  it("treats a filled honeypot as success and stores nothing", async () => {
    const sb = okSb();
    admin.mockReturnValue(sb);
    const res = await handler(webReq("POST", { email: "a@b.co", tier: "owner", _honey: "spam" }));
    expect(res.status).toBe(200);
    const body = await res.json();
    expect(body.queued).toBe(false);
    expect(sb.from).not.toHaveBeenCalled();
  });

  it("returns 501 with an actionable message when the waitlist table is missing", async () => {
    const sb = missingTableSb();
    admin.mockReturnValue(sb);
    const res = await handler(webReq("POST", { email: "a@b.co", tier: "owner" }));
    expect(res.status).toBe(501);
    const body = await res.json();
    expect(body.error).toMatch(/support@brandforge-os.com/);
  });

  it("rejects non-POST methods with 405", async () => {
    const res = await handler(webReq("GET"));
    expect(res.status).toBe(405);
  });

  it("answers CORS preflight with 204 and CORS headers", async () => {
    const res = await handler(webReq("OPTIONS"));
    expect(res.status).toBe(204);
    expect(res.headers.get("Access-Control-Allow-Origin")).toBe("*");
  });
});
