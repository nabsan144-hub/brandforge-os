/* ============================================================================
   BRANDFORGE OS — LAUNCH CONFIG (single source of truth for the sales site)
   ============================================================================
   DOMAIN-AGNOSTIC (2026-08-26): Works on ANY domain — Vercel preview,
   custom domain, Netlify, Cloudflare, localhost. No hardcoded dependency.

   - site_url: your PRODUCTION domain (e.g. https://brandforge-os.com or
     your deployment host). If empty/placeholder, site auto-uses
     window.location.origin at runtime (via domain.js).
   - To finalize domain for SEO (canonical/sitemap/robots static tags):
     ./scripts/set_site_url.sh https://yourdomain.com

   1. SITE_URL — production domain or empty for auto-detect
   2. WAITLIST — posts to the cloud /api/waitlist backend (no placeholder
      inbox, no FormSubmit). Set hosted_url to the cloud app origin.
   3. Checkout is server-authorized; never put API/webhook secrets in this file
   4. SUPPORT_EMAIL — email fallback
   ========================================================================== */
window.BRANDFORGE_LAUNCH = {
  // 1) PRODUCTION DOMAIN — empty = auto-detect window.location.origin at runtime
  // (works on any deployment host with zero edits).
  // After deploying, bake the final URL into the static SEO tags too:
  //   ./scripts/set_site_url.sh https://<your-deployment-host>
  site_url: 'https://www.brandforge-os.com',

  // 2) WAITLIST — the cloud app origin. The form POSTs to
  //    `{hosted_url}/api/waitlist`, which stores the lead in Supabase. No
  //    placeholder inbox and no FormSubmit.co dependency. Override with an
  //    explicit `waitlist_endpoint` if you host it somewhere else.
  hosted_url: 'https://app.brandforge-os.com',
  waitlist_endpoint: '',

  // 3) PUBLIC FUNNEL FLAG — enable only after the canonical launch runbook.
  desktop_checkout_enabled: false,

  // 4) FOUNDER TRUST BLOCK — filled in; the homepage renders a short
  //    "behind the product" section whenever `name` is set. A findable
  //    founder matters for the $199/$499 source-license buyers.
  founder: {
    name: 'Nabeel Ali',
    role: 'Founder, BrandForge OS — also builds CopyForge AI',
    blurb: 'Building a reviewable campaign workspace for small businesses and marketers.',
    email: '',        // optional direct email; falls back to support@
    linkedin: 'https://www.linkedin.com/in/nabeel-ali-ops/'
  },

  // 5) ANALYTICS (optional, privacy-friendly only) — nothing loads while
  //    provider is ''. You cannot fix a funnel you cannot see; when you
  //    enable this, ALSO add the provider origin to script-src + connect-src
  //    in sales/_headers (and any Vercel/Cloudflare header config), or CSP
  //    will block the script.
  first_party_metrics_enabled: false,
  analytics: {
    provider: '',    // 'plausible' | 'umami'
    domain: '',      // 'brandforge-os.com' (plausible) or umami website ID
    src: ''          // umami script URL, e.g. 'https://cloud.umami.is/script.js'
  },
  // Legacy public metadata below is not authorization to charge.
  paddle_client_token: '',
  paddle_env: 'sandbox',
  prices: {
    owner:         { id: '', price: 199 },
    agency_source: { id: '', price: 499 }
  },

  // 4) SUPPORT
  support_email: 'support@brandforge-os.com',

  // ---- helpers ----
  isRealPaddleToken(value) {
    const token = String(value || '').trim();
    return /^(live|test)_[A-Za-z0-9_-]+$/.test(token) && token.toUpperCase().indexOf('YOUR') === -1;
  },
  isRealPaddlePrice(value) {
    const id = String(value || '').trim();
    return /^pri_[A-Za-z0-9_-]+$/.test(id) && id.toUpperCase().indexOf('YOUR') === -1;
  },
  get paddleReady() {
    return this.desktop_checkout_enabled === true;
  },
  // Legacy metadata only. availability.js + server readiness own CTA state.
  configuredTiers() {
    const out = [];
    for (const n of ['owner','agency_source']) {
      const id = (this.prices && this.prices[n] && this.prices[n].id) || '';
      if (this.isRealPaddlePrice(id)) out.push(n);
    }
    return out;
  },
  // The waitlist endpoint the form actually posts to: an explicit override, or
  // the cloud app origin + /api/waitlist.
  waitlistEndpoint() {
    const explicit = String(this.waitlist_endpoint || '').trim();
    if (explicit) return explicit;
    const base = String(this.hosted_url || '').trim().replace(/\/+$/, '');
    return base ? base + '/api/waitlist' : '';
  },
  get waitlistReady() {
    const url = this.waitlistEndpoint();
    return /^https?:\/\/[^\s]+$/.test(url) && url.indexOf('YOUR') === -1 && url.indexOf('example') === -1;
  },
  // 5) PRE-LAUNCH STATE — true while a business-critical config is still
  //    placeholder (no Paddle checkout), used by buy.js to route Buy buttons to
  //    the (working) waitlist instead of a fake payment. The waitlist itself is
  //    live once `waitlistReady` — so a pre-launch visitor can always register.
  get isPreLaunch() {
    return !this.paddleReady;
  },
  get effectiveSiteUrl() {
    var raw = String(this.site_url || '').trim().replace(/\/+$/, '');
    var isPlaceholder = !raw || raw.indexOf('YOUR') !== -1 || raw.indexOf('example') !== -1 || raw.length < 8;
    // Domain-agnostic: if placeholder, use current origin (works on ANY domain)
    if (isPlaceholder) {
      try { if (typeof window !== 'undefined' && window.location.origin) return window.location.origin.replace(/\/+$/, ''); } catch(e) {}
      return raw || (typeof window !== 'undefined' ? window.location.origin.replace(/\/+$/, '') : '');
    }
    // Fully domain-agnostic: no hardcoded production-domain check — if site_url is set, respect it
    // For preview deployments, operator can set site_url to preview URL explicitly via set_site_url.sh, or leave empty for auto
    return raw;
  }
};
