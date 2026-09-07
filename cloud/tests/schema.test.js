// Schema-vs-handler drift guard (2026-08-26 audit).
// The Supabase client is mocked in every other test, which is exactly how a
// missing column (campaigns.benefits) and a wrong PK (user_api_keys) shipped
// broken while all tests were green. This file pins schema.sql to what the
// handlers actually read/write.
import { readFileSync } from "node:fs";
import { fileURLToPath } from "node:url";
import path from "node:path";
import { describe, test, expect } from "vitest";

const root = path.dirname(path.dirname(fileURLToPath(import.meta.url)));
const schema = readFileSync(path.join(root, "schema.sql"), "utf8");
// strip full-line comments so a commented-out column can't satisfy a check
const code = schema.replace(/^--.*$/gm, "");

describe("schema.sql matches handler column usage", () => {
  test("campaigns table defines every column api/campaigns.js inserts", () => {
    // columns referenced by the insert in api/campaigns.js
    const required = [
      "user_id", "name", "product", "industry", "audience",
      "benefits", "lang", "strategy", "copy", "seo",
      "research_live", "provider", "files",
    ];
    for (const col of required) {
      // either in the CREATE TABLE body or an idempotent ALTER migration
      const inCreate = new RegExp(`\\b${col}\\s+text|\\b${col}\\s+boolean|\\b${col}\\s+jsonb|\\b${col}\\s+uuid`).test(code);
      const inAlter = new RegExp(`add\\s+column\\s+if\\s+not\\s+exists\\s+${col}\\b`, "i").test(code);
      expect(inCreate || inAlter).toBe(true);
    }
  });

  test("campaigns.benefits has an explicit migration (audit C1 regression)", () => {
    expect(code).toMatch(/add\s+column\s+if\s+not\s+exists\s+benefits\s+text/i);
  });

  test("user_api_keys PK is composite (user_id, provider) — audit C2 regression", () => {
    // the CREATE TABLE must use the composite PK...
    expect(code).toMatch(/create\s+table\s+if\s+not\s+exists\s+public\.user_api_keys[^;]*primary\s+key\s*\(user_id,\s*provider\)/is);
    // ...and a migration must repair installs created with the old single-column PK
    expect(code).toMatch(/drop\s+constraint\s+user_api_keys_pkey/i);
  });

  test("email lookup is indexed and quota functions are not browser-callable", () => {
    expect(code).toMatch(/profiles add column if not exists email text/i);
    expect(code).toMatch(/profiles add column if not exists paddle_subscription_id/i);
    expect(code).toMatch(/insert into public\.profiles[\s\S]*from auth\.users/i);
    expect(schema).toContain("idx_profiles_email");
    expect(code).toContain("create table if not exists public.paddle_events");
    expect(schema).toMatch(/revoke execute on function public\.reserve_campaign_slot[^;]+from public, anon, authenticated/i);
    expect(schema).not.toMatch(/grant execute on function public\.reserve_campaign_slot[^;]+to authenticated/i);
    expect(schema).toContain("create or replace function public.reserve_delivery_slot");
    expect(schema).toMatch(/revoke execute on function public\.reserve_delivery_slot[^;]+from public, anon, authenticated/i);
  });

});
