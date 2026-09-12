# Integrated product demo — final local handoff

The final website source includes both demo formats. No external video host or CDN is needed.

## What is wired

- Homepage: a **Watch the 60-second tour** link scrolls to a poster/click-to-play video before the existing sample section.
- `/demo`: the video, full transcript, animated HTML alternative, MP4 download, actual sample ZIP/PDF and the separate Cloud signup link are all present.
- `sales/assets/product-demo/demo.mp4`: web-optimized **1080p, 30 fps, approximately 60 seconds**, H.264 with stereo AAC instrumental music. Same story as the original master; a smaller web encode.
- `tour.html`: self-contained animated alternative with optional music, playback/chapter controls, transcript, embedded fonts and real links back to the site's product comparison/sample sections.
- `poster.jpg`, `.vtt`/`.srt` captions, asset notices, font licenses and a SHA-256 manifest are included. The Source archive includes the marketing media. The Owner archive contains the Desktop runtime and customer documentation only.

The video uses native controls and inline playback. It **does not autoplay**, starts **muted**, and uses `preload="none"`; the MP4 is not eagerly downloaded before a visitor starts it. The HTML alternative loads only when opened. Visible captions are already rendered into the picture; the optional caption track is not on by default, avoiding a second caption layer. A media error offers the HTML/download alternatives.

The Vercel, Netlify, Cloudflare Pages and local marketing CSPs now explicitly allow same-origin/data-URI media so the self-contained music can play. The authenticated Cloud policy, Desktop API policy and generated-artifact sandbox were not relaxed. The tour is available at the clean `/tour` route and opened as its own page, not an iframe that would conflict with the production frame restrictions.

## Truthful demo scope

Northline Coffee is fictional. Art and the PDF come from an actual offline-generated sample. Desktop captures use an isolated local interface; Cloud captures use the actual interface with synthetic authentication/account/API data. The brief card is a styled overview of real fields. This is not a real-time speed benchmark, live provider generation, real purchase/refund, inbox-delivery proof or customer endorsement.

The footage precedes final label-only Desktop polish; the text-revision/export behavior shown is unchanged. The final Desktop UI also removes unqualified timing/cost-comparison wording, calls its network indicator **tracked requests**, and displays the actual **21-size** selection cap. Desktop ownership and recurring Cloud subscriptions stay separate.

Original synthesized instrumental music contains no third-party song/recording samples. Font/music notices are bundled. Do not treat that as legal certification or a Content ID guarantee.

## Local preview

With the app's Python dependencies installed, from the repository root:

```sh
python scripts/serve_sales_preview.py --port 8765
```

Open `http://127.0.0.1:8765/` and `/demo`. This helper provides clean URLs and byte-range video responses, but is **not** the Cloud product or a production server. For a sandbox browser preview only, explicitly add `--bind 0.0.0.0`. Its default preview policy allows embedding; the actual `sales/vercel.json` still denies external framing. Use `--production-headers` on loopback for isolated QA with the deployed header policy.

## Verification

`npm test --prefix sales` includes page/media wiring, mute/preload rules, player event/error handling, exact media hashes, real next-step links and prelaunch controls. Archive creation also verifies the demo manifest against the actual packaged bytes.

`scripts/check_integrated_demo.py` adds real Chromium playback/seeking, no eager MP4 requests, sound opt-in, transcript/next-link behavior and selected axe/layout checks at multiple widths in both themes using production-equivalent headers. The full browser regression suite remains separate and uses explicit Cloud auth/API fixtures.

Before publishing, test the actual staging host's media MIME types, byte-range seeking, cache behavior and mobile Safari/other supported browsers. No local check substitutes for deployment, payments, delivery, supported-device or owner/legal approval. Checkout remains off until the canonical launch runbook is completed.
