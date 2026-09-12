# BRANDFORGE OS — Brand System v2 ("Premium Studio")
*24 Aug 2026 — replaces the v1 identity. This is the single source of truth for all visual decisions.*

## Positioning in one sentence
A calm, expensive, local-first studio tool — the visual opposite of "AI slop" (no glowing orbs, no fake status lights, no gradient text).

## Logo
- **Files:** `logo-mark.svg` (mark — nav, favicon, app icon, social) • `logo-lockup.svg` (mark + wordmark — press/footer)
- **The mark (v3, 2026-08-27):** a geometric gold **anvil** (face, left horn, waist, base) with a single diamond **spark** above it. The diamond carries over from the old crown point for identity continuity. The anvil is the brand thesis in one glyph: a forge turns raw material into something valuable — and an anvil is heavy, permanent, *owned*, the exact opposite of a rented cloud subscription. No glowing orbs, no robot heads, no sparkles-within-orbs like every AI competitor.
- **One logo, one treatment, everywhere.** No recoloring, no re-rotating, no emoji substitutes.
- Min size 16px. On dark: as-is. On light (rare): mark only, gold stays.

## Color — the one-gold rule
| Token | Hex | Use |
|---|---|---|
| bg | `#06080D` | page background |
| surface | `#0B0F17` | cards, panels |
| raised | `#111726` | nested elements, terminal chrome |
| line | `rgba(255,255,255,.07)` | hairlines only (1px) — never heavy borders |
| ink | `#F2F4F8` | headings, body |
| muted | `#9AA3B5` | supporting text |
| faint | `#76829B` (dark) / `#616B7A` (light) | metadata, footers |
| **gold** | **`#E8B54A`** | **one CTA + one accent per viewport. Nothing else.** |
| gold-bright | `#F6CE6B` | CTA hover only |
| emerald | `#10B981` | success states only |

- **No gradient text. No glow on type. No glassmorphism blur on cards** (flat surfaces + hairlines only).
- **Contrast: every text token and utility color must hit WCAG AA 4.5:1 on its surface in BOTH themes.** Theme-agnostic utility colors (zinc/emerald/blue/purple) are remapped per theme in `sales/assets/theme.css` and `app/web-modern/src/app.css` — never add a new colored text class without checking both themes (E2E section K enforces the token table).
- The old `#F59E0B` amber is retired; use `#E8B54A` (warmer, less "neon").

## Type
- **Display / accent:** `Instrument Serif` (italic) — hero lines, section accents, og-image. The serif is the brand's voice: *the craft the product sells.*
- **UI / body:** `Geist` 400–700.
- **Code / commands:** `Geist Mono`.
- Scale (shipped values): hero clamp(42px,8vw,84px) → H2 clamp(32px,5vw,52px) → H3 14px → body 16px → small 12px → **floor 11px**. 8–10px text is banned (E2E-enforced).
- Letter-spacing: tracking only on 11px caps labels (+0.12em).

## Iconography
- **Lucide** only (2px stroke, currentColor). No emoji as iconography, ever.
- Emoji is allowed *inside generated campaign content* (that's the product's copy output, not the brand UI).
- Icon containers: 36–40px squares, hairline border, neutral bg — no colored fills except the one gold accent slot.

## Motion
- One scroll reveal per section: `translateY(20px) + fade, 800ms, cubic-bezier(.2,.7,.2,1)`. Respect `prefers-reduced-motion`.
- Buttons: `translateY(-1px)` + (gold CTA only) soft gold shadow on hover, 250ms.
- No infinite pulses, no bouncing dots. **Live things must actually be live** — if a state indicator ships, it must reflect real system state (the sales demo panel does; fake "6 AGENTS ACTIVE" badges are banned).

## Voice
- Direct, short, concrete. "In seconds", not "20 seconds" (never invent precision).
- No hype verbs: *unleash, supercharge, next-gen, revolutionary.*
- Never reference the vendor's revenue model on customer surfaces.
- "Founder" is used inside the product (chat), not on the sales site.

## Proof over theater
- Every visual claim on a sales page must show **real output** (real SVG, real report excerpt, live demo) — no mockups, no screenshots of fake dashboards, no fabricated stats.
- Sample outputs shipped in `sales/assets/sample/` are genuine engine output, dated and labeled as such.

## Build
- Sales CSS: `sales/tailwind.config.js` (palette tokens) + tailwind build → `sales/assets/tailwind.css` (~20KB). **Run the build from the `sales/` directory** (Tailwind resolves content paths against the CWD — anywhere else silently produces an incomplete file). No CDN. The E2E suite rebuilds the CSS and diffs it against the committed file, so a stale build fails the audit.
- Dashboard: Svelte + Tailwind, icons via `lucide-svelte`, font loaded in `web-modern/index.html`.
- Rebuild: see the Development section of `README.md` (dashboard build, sales CSS build, release packager).
