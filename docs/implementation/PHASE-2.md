# Phase 2 — Free-plan watermark and payload containment

**Implemented locally. Not pushed or deployed.**

Branch: `fix/phase-2-watermark-payload`

This batch follows Phase 1 (`82c35ff43c3201d74d91c4bcec6664706037f651`) and adds the user's request for visible BrandForge attribution on the three-lifetime-campaign Free plan.

## W01 — visible Free-plan attribution

- Newly generated Free banners show **Made with BrandForge** in a bottom-right footer.
- The footer occupies reserved space; it does not overlay the customer logo or CTA.
- Very narrow formats use **BrandForge** or **BF**, with the full attribution retained in accessible SVG metadata.
- The text is outlined into vector paths. It is part of the actual SVG, not a browser-only overlay, so PNG/JPEG/ZIP export preserves it.
- Generated Free logo concepts are attributed too. Uploaded customer logos remain unchanged.
- The server's plan settings determine attribution; a request cannot disable it by submitting `watermark:false`.
- Newly generated Pro/Agency assets do not receive this watermark.
- An upgrade does not rewrite previously saved Free assets. Existing outputs are not retroactively changed.
- The three lifetime campaigns and their quota behavior are unchanged.

This is **visible attribution**, not invisible forensic watermarking, tamper-proof DRM or a copy of Google's identity. An editable SVG can be modified and raster images can be cropped; no claim of unremovability is made.

### Preview

`evidence/phase-2/Watermark-Preview.html` is self-contained and uses actual offline renderer output. It compares Free and paid hero/strip assets. It demonstrates watermark placement only: the later campaign-quality redesign remains open.

## T03 — interim payload protection (PARTIAL, not private storage)

The previous implementation could accept a 3.6 MB scene and embed it in more than 5 MB of campaign JSON. This batch contains that class of failure while a proper private-object-storage migration remains to be implemented.

### New limits and behavior

| Boundary | Limit | Behavior when exceeded |
|---|---:|---|
| Image-provider response body | 2,200,000 bytes | Abort bounded read; explicit image fallback |
| Decoded scene payload | 1,500,000 bytes | Explicit `VISUAL_TOO_LARGE` vector fallback |
| Complete campaign JSON before save | 3,000,000 UTF-8 bytes | `CAMPAIGN_PAYLOAD_LIMIT`; no campaign commit/allowance consumed |
| Campaign detail response | 4,000,000 UTF-8 bytes | Bounded `LEGACY_PAYLOAD_LIMIT` instead of attempting an oversized response |
| Compressed account-export response | 4,000,000 bytes | Bounded `EXPORT_PAYLOAD_LIMIT` with a support-export message |

Limits deliberately leave margin below the documented Vercel 4.5 MB function-body limit. They include JSON/base64 overhead where relevant rather than incorrectly treating decoded image bytes as response bytes.

- Provider response streams are bounded before the entire response is collected.
- Base64 syntax and supported MIME values are checked; this is not a complete image-decoder/normalization pipeline.
- The pre-save check covers all files, brief and metadata before `complete_generation` commits the quota.
- If an image was already requested before another size check fails, operator provider cost reservations are retained: the provider may have charged. A campaign allowance refund is not a claim that the provider refunded its call.
- Existing oversized records are not deleted or silently truncated. Owners receive a controlled error; cross-owner access still returns not found.
- The browser now displays campaign-load failures instead of silently returning.

### Still open under T03 / V06

- Private object storage, owner-authorized delivery, lifecycle/deletion cleanup and migration of historical inline assets.
- Full image decoding, dimensional validation and normalization/compression.
- A support/offline extraction tool for legacy records that also exceed the compressed export ceiling. The user-facing support message is not an already-built recovery service.
- Maximum-size real-provider/staging deployment tests, including egress/memory/latency.

**Do not treat these interim bounds as completion of T03 or approval to launch paid imagery.** They may reject large valid images that a future storage-backed implementation can support.

## Gemini key / Free-plan policy

The user reports that a Gemini key is configured in live Vercel. This batch does not read, rotate, remove or modify that key, and does not change Vercel configuration.

A working Gemini text key is not proof of image-model access or zero-cost image generation. Accordingly:

- Free remains vector-only, with visible attribution.
- Phase 1's explicit image consent, paid entitlement, model-bound cost reservation and image kill switch remain in place.
- No paid providers, real accounts or payments were used during implementation/testing.
- A possible Free AI-artwork trial needs a separate explicit entitlement/allowance decision plus verified model access, current provider pricing and budget enforcement. It is not enabled by this batch.

## Tests run

| Test | Result |
|---|---|
| Full Cloud Vitest suite | **252 passed**, 28 files (19 additional tests in this batch) |
| Watermark unit checks | All 21 catalog entries plus a 50×50 case, both banner styles; Free/Pro/Agency enforcement; generated logo concepts |
| Actual browser raster checks | **18 passed**: PNG and JPEG across Free/paid hero, story, strip, micro and Free logo fixtures |
| ZIP export | Generated SVG and PNG watermark content verified; all manifest hashes verified |
| Consent UI regression | **8 states passed**, no axe violations, overflow or page errors |
| Payload route tests | Oversized pre-save rejection preserves allowance; legacy oversized detail is owner-scoped; high-entropy oversized account export returns a controlled error |
| Provider-response tests | Oversized stream cancellation, decoded-image bounds, invalid encodings and visible vector fallback |

The watermark export test is added to the existing offline browser CI job. Remote CI and production deployment were not run here.

## Reproduce

```sh
npm ci --prefix cloud
npm test --prefix cloud
python -m pip install playwright==1.62.0 Pillow==12.3.0
python -m playwright install --with-deps chromium
python scripts/watermark_export_qa.py
python scripts/image_consent_qa.py
```

Both browser scripts intercept network requests and use offline/synthetic fixtures. Output paths are configurable with `BRANDFORGE_QA_DIR`.

## Rollout notes

1. Review/apply this batch after Phase 1. Keep paid checkout/image release gates closed.
2. Phase 2 introduces no additional database migration; Phase 1 still requires migration `0012_visual_status.sql` before deploying its code to an existing database.
3. Deploy to staging before production; test Free generation, preview and all downloads there.
4. Confirm old campaigns remain untouched, Free allowance remains three lifetime runs, and new paid assets remain unmarked.
5. Do not make any change to the existing live Gemini key merely to apply the watermark.
6. Follow the remaining gate work in `PROGRESS.csv`. It contains the original 90 tasks plus W01, the new watermark request.

## Next

Complete the storage-backed asset lifecycle, then the structured edit/rerender flow and generated-design quality work. The watermark is not a substitute for improving the creative output.
