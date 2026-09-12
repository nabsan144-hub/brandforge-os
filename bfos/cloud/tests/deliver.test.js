import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";

vi.mock("../api/_lib/sb.js", () => ({
  admin: vi.fn(),
  authUser: vi.fn(),
  json: (body, status = 200) => ({ status, body }),
}));

import { authUser, admin } from "../api/_lib/sb.js";
import { providerConfig, validPhone, sendWhatsApp, appUrl, WA_ENABLED, MAX_PER_HOUR } from "../api/_lib/deliver.js";
import handler from "../api/_lib/routes/camp-id-deliver.js";

const USER = { id: "u1" };
const CAMP = { id: "c1", name: "My Campaign", product: "Coffee" };

function makeLink({ result = null, rec = null, count = null } = {}) {
  return new Proxy({}, {
    get(_t, prop) {
      if (prop === "then") return (resolve) => resolve(result ?? { data: null, error: null });
      if (prop === "single") return () => Promise.resolve(result ?? { data: null, error: null });
      if (prop === "count") return { exact: "exact", head: true };
      if (prop === "limit") return () => Promise.resolve(count);
      return (...args) => {
        if (rec) rec.push({ method: prop, args });
        return makeLink({ result, rec, count });
      };
    },
  });
}

function makeSb({ camp = CAMP, count = 0, profile = { plan: "agency", whatsapp_phone: null } } = {}) {
  const rec = [];
  const reservation = count >= MAX_PER_HOUR
    ? { data: { ok: false, code: "LIMIT_HOURLY" }, error: null }
    : { data: { ok: true, id: "delivery-1" }, error: null };
  const sb = {
    from: vi.fn((table) => {
      if (table === "campaigns") return makeLink({ result: { data: camp, error: null }, rec });
      // Default profile carries an Agency plan so the happy path proceeds;
      // tests that exercise the plan gate pass a different profile plan.
      if (table === "profiles") return makeLink({ result: { data: profile, error: null }, rec });
      if (table === "delivery_log") return makeLink({ result: { data: null, error: null }, rec });
      return makeLink({ rec });
    }),
    rpc: vi.fn(async () => reservation),
    rec,
  };
  return sb;
}

beforeEach(() => {
  vi.clearAllMocks();
  process.env.WA_DELIVERY_ENABLED = "1";
  process.env.WHATSAPP_PROVIDER = "twilio";
  process.env.TWILIO_ACCOUNT_SID = "AC_test";
  process.env.TWILIO_AUTH_TOKEN = "token";
  process.env.TWILIO_WHATSAPP_TEMPLATE_SID = "HX_test";
  process.env.BRANDFORGE_APP_URL = "https://app.example.test";
});
afterEach(() => {
  delete process.env.BRANDFORGE_APP_URL;
  delete process.env.WA_DELIVERY_ENABLED;
  delete process.env.WHATSAPP_PROVIDER;
  delete process.env.TWILIO_ACCOUNT_SID;
  delete process.env.TWILIO_AUTH_TOKEN;
  delete process.env.TWILIO_WHATSAPP_TEMPLATE_SID;
  delete process.env.WABA_360DIALOG_TOKEN;
  delete process.env.WABA_NAMESPACE;
  delete process.env.WABA_TEMPLATE_NAME;
  delete global.fetch;
});

describe("deliver lib — flags, phone, provider config", () => {
  it("WA_ENABLED reflects the flag (default OFF)", () => {
    delete process.env.WA_DELIVERY_ENABLED;
    expect(WA_ENABLED()).toBe(false);
    process.env.WA_DELIVERY_ENABLED = "1";
    expect(WA_ENABLED()).toBe(true);
  });

  it("validPhone accepts E.164, rejects junk", () => {
    expect(validPhone("+923001234567")).toBe(true);
    expect(validPhone("03001234567")).toBe(false);
    expect(validPhone("+1 415 555 2671")).toBe(false);
    expect(validPhone("")).toBe(false);
  });

  it("providerConfig returns config only when fully set", () => {
    expect(providerConfig("twilio")).toBeTruthy();
    delete process.env.TWILIO_WHATSAPP_TEMPLATE_SID;
    expect(providerConfig("twilio")).toBeNull();
    expect(providerConfig("nope")).toBeNull();
  });

  it("appUrl uses env or default, no trailing slash (domain-agnostic)", () => {
    // Default is example placeholder, but operator MUST set BRANDFORGE_APP_URL for any other domain
    var defaultUrl = appUrl();
    expect(typeof defaultUrl).toBe("string");
    expect(defaultUrl.length).toBeGreaterThan(0);
    process.env.BRANDFORGE_APP_URL = "https://app.example.com/";
    expect(appUrl()).toBe("https://app.example.com");
    // Also supports BRANDFORGE_MARKETING_URL as fallback
    delete process.env.BRANDFORGE_APP_URL;
    process.env.BRANDFORGE_MARKETING_URL = "https://marketing.example.com/";
    expect(appUrl()).toBe("https://marketing.example.com");
  });
});

describe("deliver lib — sendWhatsApp (mocked fetch)", () => {
  it("twilio: posts the correct URL + Basic auth + template payload", async () => {
    global.fetch = vi.fn(async () => ({ ok: true }));
    await sendWhatsApp("twilio", "+923001234567", ["My Campaign", "https://example.com/app/c/c1"]);
    const [url, opts] = global.fetch.mock.calls[0];
    expect(url).toContain("/Accounts/AC_test/Messages.json");
    expect(opts.headers.Authorization).toBe("Basic " + Buffer.from("AC_test:token").toString("base64"));
    const body = new URLSearchParams(opts.body);
    expect(body.get("To")).toBe("whatsapp:+923001234567");
    expect(body.get("ContentSid")).toBe("HX_test");
    const vars = JSON.parse(body.get("ContentVariables"));
    expect(vars["1"]).toBe("My Campaign");
    expect(vars["2"]).toBe("https://example.com/app/c/c1");
  });

  it("360dialog: posts the WABA template payload", async () => {
    process.env.WHATSAPP_PROVIDER = "360dialog";
    process.env.WABA_360DIALOG_TOKEN = "tok";
    process.env.WABA_NAMESPACE = "ns";
    process.env.WABA_TEMPLATE_NAME = "campaign_ready";
    global.fetch = vi.fn(async () => ({ ok: true }));
    await sendWhatsApp("360dialog", "+923001234567", ["C", "U"]);
    const [url, opts] = global.fetch.mock.calls[0];
    expect(url).toBe("https://waba.360dialog.io/v1/messages");
    expect(opts.headers.Authorization).toBe("Bearer tok");
    const payload = JSON.parse(opts.body);
    expect(payload.template.namespace).toBe("ns");
    expect(payload.template.components[0].parameters).toHaveLength(2);
  });

  it("throws on provider non-200 (no silent failure)", async () => {
    global.fetch = vi.fn(async () => ({ ok: false, status: 401 }));
    await expect(sendWhatsApp("twilio", "+923001234567", ["a", "b"])).rejects.toThrow(/401/);
  });
});

describe("deliver endpoint contract", () => {
  it("404 when flag off", async () => {
    process.env.WA_DELIVERY_ENABLED = "0";
    const res = await handler({ method: "POST" }, { params: { id: "c1" } });
    expect(res.status).toBe(404);
  });

  it("401 unauthenticated", async () => {
    authUser.mockResolvedValue(null);
    const res = await handler({ method: "POST" }, { params: { id: "c1" } });
    expect(res.status).toBe(401);
  });

  it("404 when campaign not found or not owned", async () => {
    authUser.mockResolvedValue(USER);
    const sb = makeSb({ camp: null });
    admin.mockReturnValue(sb);
    const res = await handler({ method: "POST", json: async () => ({ phone: "+923001234567" }) }, { params: { id: "nope" } });
    expect(res.status).toBe(404);
  });

  it("400 invalid phone", async () => {
    authUser.mockResolvedValue(USER);
    admin.mockReturnValue(makeSb());
    const res = await handler({ method: "POST", json: async () => ({ phone: "0300" }) }, { params: { id: "c1" } });
    expect(res.status).toBe(400);
  });

  it("503 when provider not configured", async () => {
    authUser.mockResolvedValue(USER);
    delete process.env.TWILIO_WHATSAPP_TEMPLATE_SID;
    admin.mockReturnValue(makeSb());
    const res = await handler({ method: "POST", json: async () => ({ phone: "+923001234567" }) }, { params: { id: "c1" } });
    expect(res.status).toBe(503);
  });

  it("429 when rate limit reached", async () => {
    authUser.mockResolvedValue(USER);
    const sb = makeSb({ count: MAX_PER_HOUR });
    admin.mockReturnValue(sb);
    const res = await handler({ method: "POST", json: async () => ({ phone: "+923001234567" }) }, { params: { id: "c1" } });
    expect(res.status).toBe(429);
  });

  it("403 when the tenant's plan is not Agency (storefront-promised feature)", async () => {
    authUser.mockResolvedValue(USER);
    const sb = makeSb({ profile: { plan: "free", whatsapp_phone: null } });
    admin.mockReturnValue(sb);
    const res = await handler({ method: "POST", json: async () => ({ phone: "+923001234567" }) }, { params: { id: "c1" } });
    expect(res.status).toBe(403);
    expect(res.body.code).toBe("PLAN_REQUIRED");
    // no provider send and no reservation attempted
    expect(sb.rpc).not.toHaveBeenCalled();
    expect(global.fetch).toBeUndefined();
  });

  it("success: sends + logs the delivery", async () => {
    authUser.mockResolvedValue(USER);
    global.fetch = vi.fn(async () => ({ ok: true }));
    const sb = makeSb();
    admin.mockReturnValue(sb);
    const res = await handler({ method: "POST", json: async () => ({ phone: "+923001234567" }) }, { params: { id: "c1" } });
    expect(res.status).toBe(200);
    expect(res.body.ok).toBe(true);
    expect(sb.rpc).toHaveBeenCalledWith("reserve_delivery_slot", {
      uid: "u1", cid: "c1", p: "twilio", max_per_hour: MAX_PER_HOUR,
    });
    const update = sb.rec.find((r) => r.method === "update");
    expect(update).toBeTruthy();
    expect(update.args[0]).toEqual({ status: "sent" });
  });

  it("provider failure → 502, campaign untouched (no delivery logged)", async () => {
    authUser.mockResolvedValue(USER);
    global.fetch = vi.fn(async () => ({ ok: false, status: 500 }));
    const sb = makeSb();
    admin.mockReturnValue(sb);
    const res = await handler({ method: "POST", json: async () => ({ phone: "+923001234567" }) }, { params: { id: "c1" } });
    expect(res.status).toBe(502);
    expect(sb.rec.some((r) => r.method === "insert")).toBe(false);
  });
});

describe("deliver endpoint — profile phone fallback (BUG fix)", () => {
  it("uses whatsapp_phone from profiles when body.phone is absent", async () => {
    authUser.mockResolvedValue({ ...USER, whatsapp_phone: undefined }); // auth user has NO profile fields
    global.fetch = vi.fn(async () => ({ ok: true }));
    // profiles row carries the saved phone
    const rowFor = (table) =>
      table === "campaigns" ? { data: CAMP, error: null }
      : table === "profiles" ? { data: { plan: "agency", whatsapp_phone: "+923001234567" }, error: null }
      : { data: null, error: null };
    const sb = {
      from: vi.fn((table) => {
        const link = () => new Proxy({}, { get: (_t, p) => {
          if (p === "then") return (r) => r(rowFor(table));
          if (p === "single") return () => Promise.resolve(rowFor(table));
          return () => link();
        } });
        return link();
      }),
      rpc: vi.fn(async () => ({ data: { ok: true, id: "delivery-1" }, error: null })),
      rec: [],
    };
    admin.mockReturnValue(sb);
    const res = await handler({ method: "POST", json: async () => ({}) }, { params: { id: "c1" } });
    expect(res.status).toBe(200);
    // the saved profile phone must be sent as the Twilio `To` (whatsapp:<phone>)
    const [url, opts] = global.fetch.mock.calls[0];
    expect(url).toContain("/Messages.json");
    const body = new URLSearchParams(opts.body);
    expect(body.get("To")).toBe("whatsapp:+923001234567");
  });
});
