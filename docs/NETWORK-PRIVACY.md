# Network boundaries and privacy

## Desktop is local, not an egress firewall

The server defaults to loopback. Unknown Host headers are denied even when an attacker supplies a matching Origin. State-changing API calls require a per-install local capability; the dashboard obtains it from `/api/session` and sends `X-BrandForge-Token` only to the same origin. It is never put in a URL or localStorage. This is browser/CSRF hardening, **not** multi-user authentication or protection against malware running as the local user.

Keep the local app off the public internet. `BRANDFORGE_ALLOWED_HOSTS` is an explicit development/reverse-proxy exception, not permission to expose unauthenticated data. Do not set wildcard CORS. Approval links have their own limited, expiring capability and should be shared deliberately.

| Transport / feature | Can use network? | Covered by tracked-requests counter? |
|---|---|---|
| Desktop offline templates | No provider call requested | Only if a requests-library call actually occurs |
| `requests` text/image/search transport | Yes, when configured/selected | Yes; host/status/duration, no body/query/key |
| `urllib` / other HTTP transports | Yes | Not necessarily |
| `httpx` and external SDKs | Yes | Not necessarily |
| Browser, fonts/assets and optional UI integrations | Yes | No |
| Initial pip setup / explicit repair | Yes | No |
| Optional update checks | Yes, with consent | Transport-dependent; not a complete monitor |
| Local model runtime downloading models | Yes, separately | No |
| Other processes on the machine | Yes | No |

A zero badge is **not proof of zero traffic**. Verify offline behavior with networking disabled and, if needed, an OS-level network capture/firewall. Normal configured launch does not invoke pip; setup/repair is explicit.

Connected prompts may contain the brief, selected client brand rules, proof and relevant memory—not only the latest sentence. Do not put secrets or unnecessary personal data into prompts. Saved personal provider keys outrank operator keys in Cloud Auto mode. Read/decryption failures do not silently route that request elsewhere. The selected provider can fall back to locally generated templates, not an undisclosed second provider.

## Cloud

Cloud uses hosted authentication/database/storage and selected model providers. It is not “data stays on your PC.” The service role is server-only; browser roles have no direct read/write access to waitlist leads, encrypted keys, generation ledgers or commerce tables. User-facing handlers scope workspace records to authenticated IDs. Generation usage is separate from deletable campaign content.

Account export is paged and excludes secret key material. Account deletion reconciles/cancels billable subscriptions **before** destroying the identity; on uncertainty it retains the identity and reports a retryable failure. Minimal transaction/order records are separate from erased campaign data. The operator must approve and disclose lawful retention periods and verify vendor settings before deployment.

Payment/download/portal tokens must not be logged. Email links keep their bearer token in the URL fragment (not sent in HTTP request URLs). The download page submits it in a POST body; do not enable body logging on that route. Application logs contain only event IDs/error codes. Private signed storage URLs have a short lifetime; revocation cannot erase files a customer already downloaded.

Public research/image URLs use checked, pinned public IPs, verified HTTPS identities, bounded reads and per-hop checks. Optional browser audits are isolated read-only contexts: worker/websocket paths are disabled and HTTP reads use the pinned fetcher. This is not a claim of an OS-level malware sandbox or zero network activity. Public image fallback now requires BRANDFORGE_PUBLIC_IMAGES=1; Off and an explicitly selected provider cannot silently switch to it.
