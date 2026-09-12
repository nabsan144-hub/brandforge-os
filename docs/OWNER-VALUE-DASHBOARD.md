# Owner value review (B07)

Open `tools/value-dashboard.html` directly in a browser. No server, API credentials, telemetry or network access is required. It is an owner tool, not a public customer dashboard. Empty data stays empty: missing measurement is never represented as success.

## Weekly procedure

1. Obtain permission for the pilot measurement, explain its purpose and use opaque references. Keep any identity mapping separately under your retention policy.
2. Include **every generated pack in the selected cohort**, including abandoned/failed exports. Record usability only after an actual review (`null` until then). Do not equate an export click with usable work.
3. Measure actual editing minutes and elapsed minutes until the first usable export. The existing app's optional daily event counts and “minutes saved” feedback cannot substitute for these measurements.
4. Reconcile provider costs to usage/invoices. Leave unknown values `null`; zero means measured zero. Record support time, refund amount and a categorical cause.
5. Import a JSON file with `schema:1` and a `records` array. Review by week; compare cohorts with identical eligibility rules. Weekly reviewed-and-exported packs per **represented customer** is a candidate value measure, not all-account DAU.
6. Use protected `/api/ops/status` and its failure/fallback/feedback summaries alongside this review. Never put `CRON_SECRET` in this HTML or publish raw measurement files.
7. Close the page to clear its memory. Keep the original de-identified measurement file and retention date under owner control; the application does not write it into localStorage.

## Record example — fictional schema illustration, not results

```json
{"schema":1,"records":[{
 "day":"2026-09-12","customer_ref":"pilot-001","campaign_ref":"pack-001",
 "reviewed":true,"exported":true,"usable":null,
 "editing_minutes":null,"first_usable_export_minutes":null,
 "provider_cost_usd":null,"fallback":false,"image_failed":false,
 "export_failed":false,"support_minutes":null,"refund_usd":0,"refund_reason":"none"
}]}
```

Use exactly these fields. Maximum: 10,000 records and 2 MB. One record per campaign reference. `usable` is true/false/null; unknown durations and costs are null. Refund causes: none, quality, missing_feature, setup, delivery, billing, other. References accept letters, digits, hyphen and underscore only; no names/emails/prompts/keys.

The dashboard reports generated versus reviewed/exported/usable work, usability response denominator, median measured editing and first-usable-export time, provider cost per usable pack only when costs are complete, fallback/image/export failures, support time and refunds by cause. It does **not** independently certify publication suitability, attribute causation, reconcile every invoice or calculate profit. For full support/hosting/acquisition/refund unit economics use `scripts/unit_economics.py`. Real customer measurements and a commercial go/no-go remain owner gates.
