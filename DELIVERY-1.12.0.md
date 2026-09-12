# BrandForge 1.12.0 — complete source candidate

This is the complete source tree, not a patch. Start with `docs/audit/FOLLOW-UP-1.12.0.md`, `docs/audit/OWNER-HANDOFF.md` and `docs/audit/PUSH-WINDOWS-CMD.txt`.

New: rights-gated approved-logo replacement, nine photo crop anchors, hash-preserving AI text/logo overlay edits for new/recovered heroes, safer logo decoding, and expanded regression coverage. Migration 0023 is required before enabling the new write paths.

438 Python and 429 Cloud tests pass; eight correction and eight product browser views pass. These are local checks, not real-service or signed native certification. **Production approved: false. Entire 91-item backlog complete: false.** All remaining acceptance items are retained in `docs/audit/91-ITEM-RECONCILIATION.md`.

The working source was recovered from the verified 1.11.0 ZIP because nested working files and Git objects were absent this session. The new local Git baseline is an explicit artifact import; preserve existing PC/GitHub history and do not force-push reconstructed history. No credentials, installed dependencies, customer state or native binary is included.
