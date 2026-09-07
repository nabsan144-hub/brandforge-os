# BrandForge OS — Security

BrandForge OS is a local-first marketing product with an optional multi-tenant
hosted service and a Vercel cloud port. This file documents the security model,
how to report issues, and what operators must configure.

## Security model

### Desktop app (`app/`)
- **Loopback by default.** `python brandforge.py --server` binds `127.0.0.1`.
  Binding `0.0.0.0` exposes an **unauthenticated** API (campaigns, memory,
  settings) — only do it behind a trusted proxy, and expect a loud warning.
- **No secrets in code.** API keys live in `.env` (chmod 600), provider-specific
  env vars only (`GROQ_API_KEY`, `GEMINI_API_KEY`, …). A Groq key never authorizes
  a Gemini call.
- **Untrusted input:** slugs/filenames are traversal-safe by construction;
  HTML/SVG deliverables are entity-escaped at render boundaries and served with a
  sandboxed CSP (`default-src 'none'`).
- **SSRF:** `modules/web_searcher.py` blocks private/loopback/link-local ranges,
  re-resolves hostnames (DNS-rebinding), re-checks every redirect hop and guards
  every Playwright subresource.
- **CSRF:** cross-origin state-changing requests are rejected when an Origin
  header is present (loopback API is unauthenticated by design).
- **Rate limiting:** per-IP buckets with eviction on chat, swarm, tool and
  approval-link endpoints.

### Hosted service (`hosted/`)
- Passwords: PBKDF2-SHA256, 600k iterations (OWASP 2023+), per-hash iteration
  count. Session tokens are one-way hashed at rest; raw tokens live only in the
  httpOnly cookie.
- Login hardening: constant-time dummy-hash verification (no email enumeration
  via timing), per-IP + per-email rate limits, DB-backed exponential lockout.
- Tenant isolation: every tenant runs the engine against its own `data_dir`;
  campaign assets are stored under `tenants/<user_id>/`; all queries are
  user-scoped.
- Plan limits are enforced **server-side** (never from client-declared values).
- Paddle webhooks: HMAC-SHA256 over `ts:raw-body` with a 5-minute replay window.
- `BRANDFORGE_ALLOW_DEV_UPGRADE=1` refuses to boot unless `BRANDFORGE_ENV=dev`.

### Vercel cloud port (`cloud/`)
- Supabase auth + row-level security; plan quotas enforced by an **atomic**
  `reserve_campaign_slot` DB RPC (no TOCTOU).
- Deliverable SVGs are rendered client-side via Blob `<img>`, never `innerHTML`.

## Operator checklist (before public deploy)

- Set a real production domain and run `scripts/check_site_url.sh` (CI does it).
- Configure `PADDLE_WEBHOOK_SECRET` + price IDs, `BRANDFORGE_LICENSE_SECRET`,
  `BRANDFORGE_COOKIE_SECURE=1`, `BRANDFORGE_ALLOW_DEV_UPGRADE=0`.
- Set `BRANDFORGE_TRUSTED_PROXIES` to your edge IPs so rate limiting can't be
  reset via forged `X-Forwarded-For`.
- Persist `BRANDFORGE_HOSTED_DATA` (SQLite + tenant assets) on durable storage.
- Re-run `cloud/schema.sql` on existing Supabase projects (new quota RPCs).

## Dependency policy

- `pip-audit` and `npm audit` are run in CI and must report **0 known
  vulnerabilities**.
- `chromadb` (optional vector memory) currently has open CVEs with no fix
  release; it stays optional with a SQLite fallback — re-check before enabling.

## Reporting

Do **not** open a public issue for security problems. Email
`security@brandforge-os.com` with a description, repro steps and impact. We aim to
acknowledge within 48h and ship a fix promptly.
