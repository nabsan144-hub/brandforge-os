# 1.12.0 continuation — 12 September 2026

## Implemented, not just documented

- **Approved-logo replacement:** a bounded, complete PNG and explicit rights are required. Server re-encoding strips metadata and preserves transparency. Approved source files and all supported banners update together; generated concept logos remain separate. Exact historical source/recipe restore is retained.
- **Crop controls:** nine anchor positions for Product-first supplied images. Contain remains the default. Crop can remove edges; it is not arbitrary canvas pan/zoom.
- **AI overlay editing:** newly generated AI heroes and newly successful image recoveries retain a schema-2 recipe with a SHA-256-bound JPEG scene. Text and left/hidden brand-logo corrections preserve scene bytes and provenance, with no image-provider call or additional campaign allowance. Resized banners remain vectors. Verified private-bundle support, optimistic revisions, replay and exact restore remain in force.
- **Safety fixes:** reject oversized PNG/JPEG/WebP logo dimensions before browser decoding; strip PNG metadata; reject missing rights/malformed images, unknown controls and corrupt scene bytes. Disable form controls during a save to prevent preparation/save races.
- **Regression tooling:** correction browser QA now uploads a replacement logo, verifies rights rejection and retry, validates binary source bytes in ZIPs, and runs in both vector and scene modes. CI includes the additional scene-mode run.

## Verification

Full local release gate: **438 Python tests and 429 Cloud tests passed**, plus Ruff, Sales integrity/build, Desktop dashboard build, schema consistency, semantic-token consistency and prelaunch safety. Focused private-scene suite passes after extending the recovered-private-scene edit/restore test. Browser: four vector correction views, four scene correction views and eight product views pass; correction runs report zero axe violations, overflow and page errors. Services/auth are mocked in browser QA; no real provider call was made. See `continuation-1.12-evidence/`.

## Scope still open

This is not completion of the entire 91-item backlog. Historical packs without sufficient rendering recipes are not reconstructed; full canvas manipulation and automatic free-form-copy synchronization remain unsupported. Editable Cloud/Desktop project migration/sync, signed nontechnical native installers, full legacy UI/design consolidation, native-language review, real external-service tests, legal/seller approval, support funding and uncoached customer/competitive-value validation remain open. All original tracker IDs remain.

## Provenance and release boundary

The session's nested checkout and Git objects were missing. All 700 source files in the 1.11.0 artifact were restored after checking ZIP SHA-256 `05104589b5a9b80bdee9136c4207cf3ec04a8c4f3471f6ece3ea5808ea5d09b8` and every manifest file hash. New Git history explicitly records an imported artifact baseline; it is not fabricated original ancestry. Preserve your PC/GitHub history when applying this delivery.

Requires migration 0023 after 0022. New write features remain default-off. No push, deployment, purchase activation, paid call, signing or production approval occurred. The previous 1.11.0 native smoke is historical evidence, not certification of a new native installer.
