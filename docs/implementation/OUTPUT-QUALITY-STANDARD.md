# Draft publishable-output standard — owner approval required

Phase 6A proposes this rubric for Q01. **It is not a certification of current output.** Geometry tests are necessary, not sufficient; the owner and target customers must approve the thresholds and examples before any default rollout or “publish-ready” marketing claim.

## Hard rejection gates

Reject an individual ad if any applies:

1. Missing, shortened, unsupported or unreadable brand, proposition, action, price or material eligibility condition that the ad needs. A brand/action strip can be valid for awareness, but is not a substitute for a promotional ad with missing terms.
2. False/unverified claims, fabricated proof, unsupported exclusivity, misleading pricing, wrong product representation or unapproved likeness/logo.
3. Text clashes, clipping, glyph loss, unresolved bidirectional text, illegible intended-size text or critical information under platform controls.
4. Wrong dimensions, destination, language, attribution policy, or mismatch between image and accompanying campaign copy.
5. The reviewer cannot explain what the ad offers, who it is for, and what to do next.

A passing geometric report cannot override these gates. A failing sample stays in the regression corpus; do not quietly remove it to improve a pass rate.

## Human rubric (score each 0–3)

0 = reject; 1 = major revision; 2 = usable with a small documented revision; 3 = ready for the specific intended placement after proofing.

| Dimension | Reviewer question |
|---|---|
| Hierarchy | Can an unfamiliar reader find the main proposition and action within roughly three seconds? |
| Legibility | Is every required word readable at actual intended display size, not only on a zoomed source? |
| Spacing | Are text blocks, margins and platform-safe areas intentional rather than empty or cramped? |
| Brand fit | Would this plausibly belong to this client without relying only on the printed brand name? |
| Composition | Is the arrangement appropriate to this offer, service and placement? Does imagery earn its place? |
| Offer clarity | Are price, quantity, exclusions, dates and action unambiguous and consistent? |
| Factual correctness | Can every objective statement be tied to approved source information? |
| Product fidelity | Does imagery show the actual approved product, or clearly avoid implying an invented substitute? |
| Revision effort | Can the ordinary user reach approval with a small, measured amount of editing? Log minutes and retries. |

**Proposed release gate:** all applicable dimensions ≥2, all hard gates passed, and no claim of readiness until a human signs off the final image, copy and placement together. Record N/A rather than awarding free points for absent product imagery. Scores do not compensate for a missing price condition.

Before choosing a default, the owner should define an acceptable revision-time target and test unfamiliar users on ordinary briefs against free alternatives. Do not infer purchase likelihood from the rubric or a synthetic benchmark.

## Reproducible initial corpus

Run `node scripts/make_editorial_fixture.mjs <output-directory>` or `python scripts/editorial_quality_qa.py` after the documented Cloud/browser dependencies are installed.

The fixture source retains six fictional briefs × five formats: coffee, fitness, property service, Urdu tea, Hindi care, and an intentionally excessive copy/terms brief. All supplied offers are **test data**, not actual prices or promotions. The examples are outlined vectors, not photographs or verified testimonials.

- Hero: 1200×630; square: 1080×1080; story: 1080×1920; display: 300×250; strip: 320×50.
- Include short and excessive text, light and dark palettes, and low-contrast supplied colors. Unit tests also cover all 21 presets, both attribution states, a supplied PNG, unsupported decorative characters and extra benefits.
- Editorial foreground is black or white against its solid background/action fill. This is not proof of every real logo's contrast or human readability.
- The fitter targets at least 12px body/brand/action and 18px headline at a **configured reference width**: at most 600px for wide/strip, 360px otherwise; smaller assets are tested at native width. A 1200px hero viewed at 320px is below this reference and still needs a real placement review.
- Story margins reserve approximately 10% of the artwork height above and 14% below the reading area, in addition to the separate Free footer. These are advisory, not guaranteed platform safe areas.

## Local review observations — not owner acceptance

The hero, square and story coffee samples are more legible and less ornamented than the previous generator style. Brand-colored flat actions and omission of unrelated icons improve clarity. They remain generic typography-led layouts, with basic font hierarchy and no real product photography; the large story gaps and single-column rhythm still need art direction.

The first pass omitted two ordinary 300px CTAs. That was a layout defect, not a reason to label ordinary text a stress test. The action region was enlarged and a regression assertion added. Both now fit.

The final 30-image set has **20 with no reported omissions and 10 with omissions**. This is NOT a 20/30 publishability score:

- Five normal strips deliberately omit headline, secondary copy, benefits and offer. They are not complete offer ads.
- All five long-copy samples remain rejected; some can become nearly empty. The warnings identify the omissions rather than quietly printing part of a price/condition.
- Urdu/Hindi samples pass local geometry and shaping checks only. Native-language advertising typography and mixed-direction proofing remain mandatory.
- No native reviewer, uncoached customer, platform or production campaign approved this corpus. No competitive or conversion benchmark was performed.

## Record for each future review

Keep: generator commit, renderer version, exact brief and source approvals, plan/attribution, dimensions, file SHA-256, intended placement/display width, all diagnostics, hard-gate outcomes, nine rubric ratings with reasons, rejected image bytes, reviewer/language competency, requested revisions, minutes spent, final approval and date. This initial corpus establishes a repeatable starting point, not a finished quality program.
