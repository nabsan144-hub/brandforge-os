# Operating decisions and release responsibilities

These are internal owner instructions, not customer promises. Production checkout remains disabled until the live release evidence is complete.

## Product decision

The initial working segment is **solo marketers preparing repeat campaigns for small service/retail businesses with approved brand assets**. This is a hypothesis, not evidence of demand. Lead with reviewing and handing off useful work, not provider badges, agent counts or autonomous-agency claims. Desktop privacy/ownership and Source resale buyers require separate pilots.

Do not expand into autonomous posting or additional provider badges before the current output, edit/export, installation and delivery workflows pass acceptance. Cloud remains a single-account workspace; team seats, invitations, a remote approval portal and seamless Desktop/Cloud synchronization must not be sold as included. These expansion features remain unimplemented, not magically delivered by this document.

## Support operation

- Retain support@brandforge-os.com; verify that it receives and sends mail before launch. No guaranteed response SLA should be published until staffing is real.
- Assign one primary owner and one backup for support and incidents. Review the queue each business day; agree actual staffed hours and escalation contacts internally.
- Triage: payment charged/file unavailable, security/privacy incident, lost work, or cross-account exposure are urgent. Pause the affected checkout/generation path where necessary, preserve evidence privately and acknowledge the customer without guessing that a refund or delivery succeeded.
- Never ask for provider keys, .env files, bearer download links, full customer databases or unredacted screenshots. For Desktop installation issues request `python app/support_diagnostics.py > support-report.json`; this reports package/runtime versions without customer content.
- Ask for app version, OS, exact error code, approximate UTC time and a minimal non-sensitive reproduction. Verify account ownership through established support procedures before disclosing order information. Do not treat possession of an email address as authentication.
- Investigate against the exact released commit. Add a regression before closing a reproducible defect. For uncertain saves ask the customer to retry the unchanged request or check history, not start repeated paid work.
- Track resolution category, support minutes and refund cause privately. Review recurring issues weekly; do not label generation count as delivered value.

## Read-only operational monitoring

`GET /api/ops-status` requires `Authorization: Bearer CRON_SECRET`. Keep that secret in your monitor's encrypted secret store, not in a browser script, URL, log or repository. It performs read-only queries: generation aggregate, delivery backlog/oldest age, failed webhook events, asset deletion backlog and up to 1,000 recent feedback responses. It does not invoke maintenance, send emails, mutate usage or return customer notes/emails.

Suggested initial internal alert thresholds (validate against actual capacity): any failed webhook event; oldest paid delivery above 15 minutes; any asset-deletion backlog that persists across three scheduled cycles; rising generation failures; approaching configured provider budget. Alerts require human investigation, not automatic destructive repair.

Set up a separate external health monitor for `/api/health`, login availability and static-site availability. A healthy process is not proof of working email, payments or providers. No observed uptime is claimed by the source.

Paid delivery still needs a monitored five-minute maintenance schedule. The repository's daily fallback cron is not sufficient for that promise. Maintenance now shares a 50-second abort budget across SDK calls and delivery attempts; the alert POST also shares that budget. Verify real execution duration and queue capacity on the chosen hosting plan. Rehearse a provider/sender outage and subsequent recovery in staging.

## Release and incident checklist

1. Run the full local release gate and browser workflows; use the same locked dependencies in CI.
2. Apply migrations in order through 0015 for the current release. This product-workflow update adds no database migration.
3. Verify separate staging credentials, two-account isolation, CAPTCHA/auth emails, private assets, real image normalization, authorized payment/refund, webhook retries and actual inbox/download checks.
4. Verify native installation and document rendering on supported Windows/macOS machines. Signed installers require your actual signing identity; none is fabricated here.
5. Complete the release evidence file for the exact deployed commit. Only an authorized owner can approve production flags.
6. Retain versioned paid release files and matching SHA-256s. Test database, artifact and encryption/signing-key restoration into a separate project.
7. During an incident preserve read/export/portal access where safe, disable only affected writes, avoid destructive migrations, and restore from verified backups rather than changing customer data to make a test pass.

## Privacy and sensitive-client work

Cloud is hosted, not local-only. Uploaded product photos are sent to Cloud for validation/storage/rendering but not to text or image models. Avoid faces, patient/client records, addresses, IDs and other unnecessary personal data. Permission to possess a photograph is not necessarily permission to advertise with it.

For Desktop, keep loopback-only binding and the write capability. Do not expose the server publicly to share a client review. Local account compromise can still access local data: use separate OS accounts, supported full-disk encryption (BitLocker/device encryption/FileVault as applicable), encrypted backups and restricted folder permissions. Verify recovery keys privately. Local .env protection is not a substitute for OS security.

Define deletion/retention for campaign files, database backups, financial records and support tickets, including vendor retention. Obtain qualified review before claiming suitability for health/legal/regulated data. No HIPAA/GDPR or blanket-compliance certification is made.

## Business acceptance before paid growth

Run 5–10 uncoached pilots with real briefs and consent. Compare the same brief and comparable effort against the user's actual free-AI/design workflow. Record the version/model/date, editing minutes, rejected claims/omissions, usable-pack decision, repeat usage, provider/infrastructure cost and willingness to pay the displayed price. Do not turn a rendered-font test into native Urdu/Hindi advertising approval.

Proposed go/no-go rule, to approve before looking at pilot outcomes: no critical rights/price/claim/tenant-isolation defect; a clear majority can finish their task without help; output and end-to-end effort should not both lose to the user's current workflow. Keep rejected samples. Record whether the rule was met rather than retroactively lowering it.

Budget Desktop's 24-month maintenance and Source onboarding from the one-time price. Use actual support-time estimates, provider invoices, payment fees, refunds, acquisition and hosting costs. The supplied economics calculator is a scenario tool, not a current provider price quote or proof of profit.
