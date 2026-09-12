/* BRANDFORGE OS — mobile navigation (hamburger + slide-down panel).
   Shared by all sales pages. Panel markup: #mobile-menu, burger: .nav-burger.
   Styling lives in assets/theme.css (pure CSS — no Tailwind dependency). */
(function () {
  function init() {
    var burger = document.querySelector('.nav-burger');
    var panel = document.getElementById('mobile-menu');
    if (!burger || !panel) return;

    function setOpen(open) {
      panel.classList.toggle('vg-open', open);
      burger.setAttribute('aria-expanded', open ? 'true' : 'false');
      // Keep screen readers / keyboard users out of the hidden duplicate nav:
      // when closed, the panel (and its links) must not be in the a11y tree.
      panel.setAttribute('aria-hidden', open ? 'false' : 'true');
    }

    burger.addEventListener('click', function (e) {
      e.stopPropagation();
      setOpen(!panel.classList.contains('vg-open'));
    });

    // Close after navigating
    panel.querySelectorAll('a').forEach(function (a) {
      a.addEventListener('click', function () { setOpen(false); });
    });

    // Escape closes
    document.addEventListener('keydown', function (e) {
      if (e.key === 'Escape') setOpen(false);
    });

    // Click outside closes
    document.addEventListener('click', function (e) {
      if (!panel.contains(e.target) && !burger.contains(e.target)) setOpen(false);
    });
  }

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', init);
  } else {
    init();
  }
})();

/* Optional privacy-friendly analytics — completely inert until configured in
   assets/config.js (BRANDFORGE_LAUNCH.analytics.provider). No cookies set by
   this loader itself. Remember to allow the origin in the CSP headers too. */
(function () {
  try {
    var a = (window.BRANDFORGE_LAUNCH || {}).analytics || {};
    if (!a.provider) return;
    var s = document.createElement('script');
    s.defer = true;
    if (a.provider === 'plausible' && a.domain) {
      s.src = 'https://plausible.io/js/script.js';
      s.setAttribute('data-domain', a.domain);
    } else if (a.provider === 'umami' && a.domain && a.src) {
      s.src = a.src;
      s.setAttribute('data-website-id', a.domain);
    } else {
      return;
    }
    document.head.appendChild(s);
  } catch (e) { /* analytics must never break the page */ }
})();
