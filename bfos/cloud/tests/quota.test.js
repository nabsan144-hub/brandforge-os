import { describe, it, expect } from "vitest";
import { runCampaign, AD_SIZES } from "../api/_lib/engine.js";
import { readFileSync } from "node:fs";
import { fileURLToPath } from "node:url";
import { dirname, join } from "node:path";

const __dirname = dirname(fileURLToPath(import.meta.url));
const schema = readFileSync(join(__dirname, "..", "schema.sql"), "utf8");

// The real quota behavior is exercised by database.test.js and the separate
// multi-connection PostgreSQL test; string checks alone are not verification.
it("ships new immutable ledger RPCs and explicitly retires the old refund path",()=>{
  for(const fn of ['reserve_generation','complete_generation','fail_generation'])expect(schema).toContain(`create or replace function public.${fn}`);
  expect(schema).toContain('drop function if exists public.release_campaign_slot');
  expect(schema).toContain('on conflict on constraint usage_monthly_pkey');
});

describe("plan custom-size caps match the pricing table", () => {
  const base = { product: "X", industry: "Y", audience: "Z", benefits: "a, b", watermark: true };
  const sizes = [{ preset: "leaderboard" }, { width: 999, height: 88 }, { preset: "billboard" }];

  it("free: one preset banner, arbitrary sizes skipped", async () => {
    const out = await runCampaign({ ...base, custom_presets: 1, custom_any: false, custom_sizes: sizes }, { groqKey: "" });
    const customs = out.files.filter((f) => f.name.startsWith("banner_"));
    expect(customs).toHaveLength(1);
    expect(customs[0].name).toBe("banner_leaderboard.svg");
  });

  it("pro: up to 10 presets, arbitrary sizes skipped", async () => {
    const many = Array.from({ length: 14 }, (_, i) => ({ preset: Object.keys(AD_SIZES)[i % 21] }));
    const out = await runCampaign({ ...base, custom_presets: 10, custom_any: false, custom_sizes: many }, { groqKey: "" });
    expect(out.files.filter((f) => f.name.startsWith("banner_"))).toHaveLength(10);
  });

  it("agency: arbitrary sizes allowed", async () => {
    const out = await runCampaign({ ...base, custom_presets: 21, custom_any: true, custom_sizes: sizes }, { groqKey: "" });
    expect(out.files.filter((f) => f.name.startsWith("banner_"))).toHaveLength(3);
  });
});
