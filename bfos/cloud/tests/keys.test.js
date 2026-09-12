import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";

vi.mock("../api/_lib/sb.js", () => ({
  authUser: vi.fn(),
  admin: vi.fn(),
  json: (body, status = 200) => ({ status, body }),
}));

import { authUser, admin } from "../api/_lib/sb.js";
import {
  BYOK_ENABLED,
  encryptKey,
  decryptKey,
  keyPrefix,
  validateKey,
  resolveGroqKey,
} from "../api/_lib/keys.js";
import handler from "../api/_lib/routes/me-keys.js";

// 32-byte hex key for tests
const CRYPTO_KEY = "a".repeat(64);
const USER = { id: "u1" };

// fluent supabase mock that records calls; the chain is THENABLE like the real
// Postgrest builder (a chain ending in .eq() is awaited directly by GET)
function makeLink({ result = null, rec = null } = {}) {
  return new Proxy({}, {
    get(_t, prop) {
      if (prop === "then") return (resolve) => resolve(result); // awaitable chain
      if (prop === "single") return () => Promise.resolve(result);
      if (prop === "limit") return () => Promise.resolve(result);
      return (...args) => {
        if (rec) rec.push({ method: prop, args });
        return makeLink({ result, rec });
      };
    },
  });
}

function makeSb({ keysResult = null } = {}) {
  const rec = [];
  // default: a successful empty result so awaited chains destructure cleanly
  const ok = { data: null, error: null };
  const sb = {
    from: vi.fn((table) => {
      if (table === "user_api_keys") return makeLink({ result: keysResult ?? ok, rec });
      return makeLink({ result: ok, rec });
    }),
    rec,
  };
  return sb;
}

beforeEach(() => {
  vi.clearAllMocks();
  process.env.BRANDFORGE_ENCRYPTION_KEY = CRYPTO_KEY;
  process.env.BYOK_ENABLED = "1";
});
afterEach(() => {
  delete process.env.BRANDFORGE_ENCRYPTION_KEY;
  delete process.env.BYOK_ENABLED;
});

describe("keys lib — encryption contract", () => {
  it("encrypt → decrypt round-trips", () => {
    const secret = "gsk_this-is-a-real-looking-key-123456";
    const enc = encryptKey(secret);
    expect(enc).not.toContain(secret);
    expect(enc.split(":")).toHaveLength(3);
    expect(decryptKey(enc)).toBe(secret);
  });

  it("fails loudly without BRANDFORGE_ENCRYPTION_KEY", () => {
    delete process.env.BRANDFORGE_ENCRYPTION_KEY;
    expect(() => encryptKey("x")).toThrow(/BRANDFORGE_ENCRYPTION_KEY/);
  });

  it("keyPrefix shows only the first 8 chars", () => {
    expect(keyPrefix("gsk_abcdef123456")).toBe("gsk_abcd…");
  });

  it("BYOK_ENABLED reflects the env flag (default OFF)", () => {
    delete process.env.BYOK_ENABLED;
    expect(BYOK_ENABLED()).toBe(false);
    process.env.BYOK_ENABLED = "1";
    expect(BYOK_ENABLED()).toBe(true);
  });
});

describe("keys lib — validateKey (1-token ping, mocked fetch)", () => {
  it("accepts a key the provider accepts (200)", async () => {
    global.fetch = vi.fn(async () => ({ ok: true }));
    expect(await validateKey("groq", "gsk_1234567890")).toBe(true);
    expect(await validateKey("gemini", "AIza1234567890")).toBe(true);
    expect(global.fetch).toHaveBeenCalledTimes(2);
  });

  it("rejects a key the provider rejects (401)", async () => {
    global.fetch = vi.fn(async () => ({ ok: false }));
    expect(await validateKey("groq", "gsk_bad")).toBe(false);
  });

  it("rejects on network error (never saves an unverifiable key)", async () => {
    global.fetch = vi.fn(async () => { throw new Error("offline"); });
    expect(await validateKey("groq", "gsk_1234567890")).toBe(false);
  });

  it("rejects unsupported providers and too-short keys", async () => {
    global.fetch = vi.fn();
    expect(await validateKey("ollama", "gsk_1234567890")).toBe(false);
    expect(await validateKey("groq", "short")).toBe(false);
    expect(global.fetch).not.toHaveBeenCalled();
  });
});

describe("keys lib — resolveGroqKey precedence", () => {
  it("user key wins over env", async () => {
    process.env.GROQ_API_KEY = "env-key";
    const sb = makeSb({ keysResult: { data: [{ provider: "groq", encrypted_key: encryptKey("user-key") }], error: null } });
    const got = await resolveGroqKey(sb, "u1");
    expect(got).toBe("user-key");
    delete process.env.GROQ_API_KEY;
  });

  it("env fallback when no user key", async () => {
    process.env.GROQ_API_KEY = "env-key";
    const sb = makeSb({ keysResult: { data: [], error: null } });
    expect(await resolveGroqKey(sb, "u1")).toBe("env-key");
    delete process.env.GROQ_API_KEY;
  });

  it("BYOK off checks for stored personal keys before using the operator key", async () => {
    process.env.BYOK_ENABLED = "0";
    process.env.GROQ_API_KEY = "env-key";
    const sb = makeSb();
    expect(await resolveGroqKey(sb, "u1")).toBe("env-key");
    expect(sb.from).toHaveBeenCalledWith("user_api_keys");
    delete process.env.GROQ_API_KEY;
  });
});

describe("me/keys endpoint contract", () => {
  it("404 when BYOK is disabled (feature flag)", async () => {
    process.env.BYOK_ENABLED = "0";
    const res = await handler({ method: "GET" });
    expect(res.status).toBe(404);
  });

  it("401 when not signed in", async () => {
    authUser.mockResolvedValue(null);
    const res = await handler({ method: "GET" });
    expect(res.status).toBe(401);
  });

  it("GET returns only redacted fields — never the plaintext", async () => {
    authUser.mockResolvedValue(USER);
    const sb = makeSb({
      keysResult: {
        data: [
          { provider: "groq", key_prefix: "gsk_ab12…", created_at: "t", updated_at: "t" },
          { provider: "gemini", key_prefix: "AIza9x…", created_at: "t", updated_at: "t" },
        ],
        error: null,
      },
    });
    admin.mockReturnValue(sb);
    const res = await handler({ method: "GET" });
    expect(res.status).toBe(200);
    expect(res.body.keys).toHaveLength(2);
    const json = JSON.stringify(res.body);
    expect(json).not.toMatch(/encrypted_key/);
    expect(json).not.toMatch(/gsk_ab12[^…]/);
  });

  it("PUT validates then encrypts + upserts; returns prefix only", async () => {
    authUser.mockResolvedValue(USER);
    global.fetch = vi.fn(async () => ({ ok: true }));
    const sb = makeSb();
    admin.mockReturnValue(sb);
    const res = await handler({
      method: "PUT",
      json: async () => ({ provider: "groq", api_key: "gsk_this-is-a-valid-key-12345" }),
    });
    expect(res.status).toBe(200);
    expect(res.body.key_prefix).toBe("gsk_this…");
    expect(JSON.stringify(res.body)).not.toContain("gsk_this-is-a-valid-key-12345");
    const upsert = sb.rec.find((r) => r.method === "upsert");
    expect(upsert).toBeTruthy();
    // encrypted payload is 3-part hex, not the plaintext
    expect(upsert.args[0].encrypted_key).not.toContain("gsk_this-is-a-valid-key-12345");
    expect(upsert.args[0].encrypted_key.split(":")).toHaveLength(3);
  });

  it("PUT rejects a key the provider rejects (400)", async () => {
    authUser.mockResolvedValue(USER);
    global.fetch = vi.fn(async () => ({ ok: false }));
    const sb = makeSb();
    admin.mockReturnValue(sb);
    const res = await handler({
      method: "PUT",
      json: async () => ({ provider: "groq", api_key: "gsk_definitely-bad-key-99" }),
    });
    expect(res.status).toBe(400);
    expect(sb.rec.filter((r) => r.method === "upsert")).toHaveLength(0);
  });

  it("DELETE removes the key for the given provider", async () => {
    authUser.mockResolvedValue(USER);
    const sb = makeSb();
    admin.mockReturnValue(sb);
    const res = await handler({ method: "DELETE", url: "/api/me/keys?provider=groq" });
    expect(res.status).toBe(200);
    const del = sb.rec.find((r) => r.method === "delete");
    expect(del).toBeTruthy();
  });

  it("PUT rejects newlines / too-short keys", async () => {
    authUser.mockResolvedValue(USER);
    const res = await handler({ method: "PUT", json: async () => ({ provider: "groq", api_key: "a\nb" }) });
    expect(res.status).toBe(400);
  });
});
