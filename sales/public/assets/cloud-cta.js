/* BrandForge OS — honest Cloud CTA labels.
   The static markup ships the paid-plan wording ("Review Pro monthly" etc.) that is
   correct once checkout is open. Until the operator enables paid Cloud checkout the
   server's /api/billing/paddle-client-token returns 503 — when that happens these
   CTAs become an honest free signup instead of a dead-end purchase promise.
   Inert in tests: needs fetch + window.BRANDFORGE_LAUNCH, and never throws. */
(function () {
  try {
    if (typeof fetch !== "function") return;
    var cfg = window.BRANDFORGE_LAUNCH || {};
    var base = String(cfg.hosted_url || "").replace(/\/+$/, "");
    if (!/^https?:\/\//.test(base)) base = "https://app.brandforge-os.com";
    var ctas = document.querySelectorAll("[data-cloud-cta]");
    if (!ctas.length) return;
    ctas.forEach(function (a) {
      if (!a.getAttribute("data-cloud-original")) {
        a.setAttribute("data-cloud-original-text", a.textContent);
        a.setAttribute("data-cloud-original-href", a.getAttribute("href"));
      }
    });
    fetch(base + "/api/billing/paddle-client-token", { cache: "no-store" })
      .then(function (r) {
        var open = r.ok;
        ctas.forEach(function (a) {
          if (open) {
            a.textContent = a.getAttribute("data-cloud-original-text");
            a.setAttribute("href", a.getAttribute("data-cloud-original-href"));
          } else {
            a.textContent = "Start free — no card";
            a.setAttribute("href", base + "/signup");
          }
        });
      })
      .catch(function () { /* keep the static wording on network failure */ });
  } catch (e) { /* never break the page */ }
})();
