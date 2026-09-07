import { describe, it, expect } from "vitest";
import { BUNDLES, LANGS, pickLang, t } from "../api/_lib/i18n.js";
import { runCampaign } from "../api/_lib/engine.js";

const FIXED = {
  product: "Apex Coffee",
  industry: "Specialty Coffee",
  audience: "Busy professionals",
  benefits: "organic beans, same-day delivery",
  watermark: false,
};

describe("i18n — bundle shape", () => {
  it("every language has exactly the English key set", () => {
    const english = Object.keys(BUNDLES.en).sort();
    for (const lang of LANGS) expect(Object.keys(BUNDLES[lang]).sort()).toEqual(english);
  });
});

describe("i18n — pickLang contract", () => {
  it("accepts supported langs, falls back to en otherwise", () => {
    expect(pickLang("hi")).toBe("hi");
    expect(pickLang("UR")).toBe("ur");
    expect(pickLang("fr")).toBe("en");
    expect(pickLang(undefined)).toBe("en");
    expect(pickLang("")).toBe("en");
    expect(LANGS).toEqual(["en", "hi", "ur", "es", "pt"]);
  });

  it("t() returns en values for missing keys", () => {
    expect(t("hi", "ctaVal")).toBeTruthy();
    expect(t("fr", "ctaVal")).toBe(t("en", "ctaVal"));
  });
});

describe("i18n — each language renders (no placeholder leaks)", () => {
  for (const lang of LANGS) {
    it(`${lang} produces non-English, placeholder-free output`, async () => {
      const out = await runCampaign({ ...FIXED, lang }, { groqKey: "" });
      for (const field of ["strategy", "copy", "seo"]) {
        expect(out[field]).toBeTruthy();
        expect(out[field].length).toBeGreaterThan(50);
        // no unresolved ${...} or raw bundle keys leaking
        expect(out[field]).not.toMatch(/\$\{t\(/);
        expect(out[field]).not.toMatch(/offlineNote\d|ctaVal|brandLabel/);
      }
      const svg = out.files.find((f) => f.name === "hero_banner.svg").content;
      expect(svg).toContain("<svg");
    });
  }
});

describe("i18n — language differences are real", () => {
  it("hi/ur/es/pt outputs differ from en (not just the same strings)", async () => {
    const en = await runCampaign(FIXED, { groqKey: "" });
    for (const lang of ["hi", "ur", "es", "pt"]) {
      const out = await runCampaign({ ...FIXED, lang }, { groqKey: "" });
      expect(out.copy).not.toBe(en.copy);
    }
  });

  it("unknown lang falls back to en byte-identical", async () => {
    const en = await runCampaign(FIXED, { groqKey: "" });
    const fallback = await runCampaign({ ...FIXED, lang: "fr" }, { groqKey: "" });
    expect(fallback.copy).toBe(en.copy);
  });
});

describe("i18n — HTML escaping holds in every language (hostile input)", () => {
  for (const lang of LANGS) {
    it(`${lang}: hostile product/audience/benefits never reach the SVG raw`, async () => {
      const out = await runCampaign(
        { ...FIXED, lang, product: "<img src=x onerror=alert(1)>", audience: "<script>x</script>", benefits: '"><b>hi</b>' },
        { groqKey: "" }
      );
      const svg = out.files.find((f) => f.name === "hero_banner.svg").content;
      expect(svg).not.toContain("<img");
      expect(svg).not.toContain("<script");
      expect(svg).not.toContain("<b>");
    });
  }
});
