# Phase 6A — Opt-in Editorial vector quality candidate

**Implemented and tested locally. No push, deployment, migration, provider call or payment activation.**

## Delivered scope

Adds the explicit `editorial-v1` vector style to the Cloud selector, request validator, generation engine and saved rendering recipes. **Bold remains the default.** There is no claim that this candidate closes Q01–Q06 or makes the product competitive with free design tools.

The new composition uses:

- A typography-led reading area, without giant filled benefits panels, unrelated benefit icons, radial glows or glass/stacked-shadow actions.
- Plain brand names rather than invented initials badges in these banners; uploaded logos remain embedded unchanged. Existing separate logo concepts are not redesigned.
- Wide and stacked arrangements plus explicitly simplified strips/micro assets; these are variants of **one** family, not the full Q06 family system.
- Flat brand-colored actions, contrast-selected black/white type, format-aware minimum sizes and advisory story margins.
- Duplicate benefits represented once when their exact text is already printed in the heading/subheading. Extra benefits beyond three are reported as format omissions.
- All-or-nothing field fit: no ellipsis, partial price, or silent shrink below the configured minimum. A field with a missing bundled-font glyph is omitted and flagged instead of silently dropping that glyph.

Long or unsupported text can therefore leave an unusable image. **That is a rejection to resolve, not a publish-ready result.** No text is automatically rewritten to fit, and no model is called by the renderer.

## Diagnostics and exports

Editorial SVGs contain per-field status and font-size metadata. The workspace derives diagnostics from the actual hydrated SVG files, including private bundles; it does not trust stale recipe inputs for the report. Statuses distinguish included, empty, format omission, unfit text, unavailable glyph, approved-logo substitution and benefit text already printed in a heading.

The notice appears in campaign detail before download. ZIP exports include checksummed `VISUAL-QUALITY.json`; original SVGs retain diagnostic metadata. Raster PNG/JPEG files are just images: the diagnostic report is not burnt into them. Included is a geometric result, **not accuracy, product fidelity, contrast of an uploaded logo, native-language approval or legibility certification**.

This batch adds warnings, not a new server-enforced publication gate. Existing copy/visual acknowledgment rules remain in force; an unchanged new campaign may still be exported with omission warnings. Users must not publish rejected results. A universal quality gate and pre-generation fit preview remain open work.

## Preservation and billing boundaries

- Twenty golden outputs captured from the verified Phase 5B renderer remain byte-identical across Bold/Essential, five dimensions and Free/paid attribution states.
- Historical files are not touched or regenerated. Existing recipe styles keep their original dispatch; `editorial-v1` must remain available once used. Future redesigns must use a new version key rather than silently changing this renderer.
- Exact version restore remains stored-byte restore, with a new real-PGlite test for an Editorial campaign. Shared font/renderer dependency upgrades still need the golden suite and staging proof.
- Free attribution remains in the separate bottom footer; new paid artwork stays unmarked. Uploaded logo file bytes and other campaign files are preserved.
- AI heroes retain their previous scene renderer. With this selection, their resized vector banners use Editorial. AI-scene campaigns still cannot use the Phase 5B correction route.
- Inline Editorial campaigns with recipes can use Phase 5B corrections **only when its existing rollout flag is enabled**. That flag remains false by default; private/AI/legacy corrections remain unsupported.
- Selecting Editorial does not enable AI, change image consent, remove normal campaign charges/allowance consumption or make generation free. Rendering and supported corrections do not add a provider call; ordinary infrastructure costs still exist.

No new database migration or environment flag is introduced. Prior migrations through 0015 are still required for the cumulative application.

## Evidence

| Check | Local outcome |
|---|---|
| Full Cloud suite | **356 passed / 33 files** (38 additional tests over Phase 5B) |
| Legacy rendering | 20 pre-change SHA-256 golden cases unchanged |
| New format tests | All 21 presets, Free and paid bounds; supported scripts; absent glyphs; extra benefits; fit failures |
| New database proof | Editorial recipe persists and correction restores exact original bytes |
| Rendered review corpus | 30 PNGs: six briefs × five formats; metadata and real Chromium bounds pass |
| Editorial workspace | 4 light/dark × 390/1440px flows pass; choice/default/consent, notice, ZIP hashes, source/copy bytes and watermark |
| Existing correction UI | 4 retry/review/export/restore flows passed again |
| Existing review UI | 4 flows passed again |
| Existing consent UI | 8 states passed again |
| Existing raster/private exports | 18 watermark rasters and private portable/ZIP regressions passed again |
| Schema sync / whitespace | Passed; no schema change |

New workspace scans report zero axe violations, page errors and horizontal overflow. These are offline Chromium tests against the shipped modules and CSP with mocked APIs, **not production or cross-browser certification**. Unit/database tests exercise actual renderer and migration code separately. New browser gates are in CI; remote CI remains unrun.

See `OUTPUT-QUALITY-STANDARD.md` for the proposed rubric and honest visual assessment. `evidence/phase-6a-review.html` is the self-contained, reproducible review sheet. Source fixtures, including rejected text, remain in `scripts/make_editorial_fixture.mjs`.

## Rollout and rollback

1. Deploy matching API, static modules and UI in staging. The server correction module now imports the shared pure `cloud/public/vector-quality.js`; verify the serverless artifact includes it and the browser serves the same module.
2. Keep Bold as default. Generate an explicit Editorial vector campaign and test both inline/private delivery, actual maximum packs, exports and permissions with real services. No private-storage setting is changed by this batch.
3. Inspect brand/logo contrast and native-size layouts; test a live supported inline correction and exact restore with the existing correction flag only in approved staging.
4. Get owner/native-language/customer review before changing defaults or publishing showcase claims. Ordinary cases and rejected cases both belong in that evidence.
5. Roll back new selection by removing the UI choice and rejecting it for **new generation requests**, while retaining the versioned renderer, diagnostic reader/exporter and correction compatibility for already saved recipes. Do not alter stored SVGs, rewrite style keys or drop prior version tables.

## Still open

Q01 owner acceptance and representative customer benchmark; Q02 a proven new default; Q03 all real brief lengths/placements and preflight UX; Q04/Q05 old styles and broader creative direction; Q06 the remaining composition families; Q07 real brand distinction; Q08 approved product imagery; Q10–Q16 public showcases and human language/story review. T10 private/AI/legacy synchronization and all live storage/provider/payment/security/recovery gates remain open. All 91 tracker IDs are preserved; the duplicate `bfos/` tree is untouched.

## Restored workspace provenance

The snapshot again restored Phase 4 git history while retaining delivered Phase 5B files. Every changed file was checked against the Phase 5B archive manifest; only CI differed and was restored from that archive. Recovery commit `46d4b27` preserves the delivered Phase 5B baseline before this branch. The original delivery commit `3123043` and recovery hash differ. No unrelated user edits were overwritten.
