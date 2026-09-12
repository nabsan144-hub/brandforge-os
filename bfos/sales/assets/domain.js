/* BrandForge OS — Domain-agnostic runtime canonical fixer
   Works on ANY domain (free host, custom, netlify, cloudflare, localhost).
   Load AFTER config.js. Updates canonical, og:url, og:image, JSON-LD at runtime.
   Static tags remain for crawlers without JS, but runtime fixes preview mismatch.
   Does NOT touch sitemap.xml/robots.txt — use scripts/set_site_url.sh for those. */
(function () {
  try {
    var cfg = window.BRANDFORGE_LAUNCH || {};
    var effective = (cfg.effectiveSiteUrl || cfg.site_url || '').replace(/\/+$/, '');
    if (!effective || effective.indexOf('YOUR') !== -1) {
      effective = window.location.origin.replace(/\/+$/, '');
    }
    if (!effective) return;

    // Domain-agnostic: canonical always = effective + pathname (no hardcoded defaultProd)
    var canonical = document.querySelector('link[rel="canonical"]');
    if (canonical) {
      var path = window.location.pathname || '/';
      if (path === '/index.html') path = '/';
      if (path.charAt(0) !== '/') path = '/' + path;
      canonical.setAttribute('href', effective + path);
    }
    var ogUrl = document.querySelector('meta[property="og:url"]');
    if (ogUrl) ogUrl.setAttribute('content', effective + (window.location.pathname || '/'));
    var ogImage = document.querySelector('meta[property="og:image"]');
    if (ogImage) {
      var img = ogImage.getAttribute('content') || '';
      try {
        // If img is absolute with different origin, replace origin with effective (domain-agnostic)
        if (img.indexOf('http') === 0) {
          var urlObj = new URL(img);
          var effObj = new URL(effective);
          if (urlObj.hostname !== effObj.hostname) {
            ogImage.setAttribute('content', effective + urlObj.pathname + urlObj.search + urlObj.hash);
          }
        } else if (img.charAt(0) === '/' || img.indexOf('assets/') === 0) {
          ogImage.setAttribute('content', effective + (img.charAt(0) === '/' ? '' : '/') + img);
        }
      } catch(e) {
        // Fallback (URL parsing unavailable): swap the origin of any absolute
        // og:image onto the effective domain — domain-agnostic, no literals.
        if (img.indexOf('http') === 0) {
          ogImage.setAttribute('content', img.replace(/^https?:\/\/[^\/]+/, effective));
        }
      }
    }
    var ld = document.querySelectorAll('script[type="application/ld+json"]');
    ld.forEach(function (s) {
      try {
        var json = JSON.parse(s.textContent);
        var updated = false;
        function replaceUrl(obj) {
          if (!obj || typeof obj !== 'object') return;
          if (Array.isArray(obj)) { obj.forEach(replaceUrl); return; }
          // Domain-agnostic: if url/logo is absolute, replace its origin with effective
          if (obj.url && typeof obj.url === 'string' && obj.url.indexOf('http') === 0) {
            try {
              var u = new URL(obj.url);
              var e = new URL(effective);
              if (u.hostname !== e.hostname) {
                obj.url = effective + u.pathname + u.search + u.hash;
                updated = true;
              }
            } catch(e) {}
          }
          if (obj.logo && typeof obj.logo === 'string' && obj.logo.indexOf('http') === 0) {
            try {
              var u2 = new URL(obj.logo);
              var e2 = new URL(effective);
              if (u2.hostname !== e2.hostname) {
                obj.logo = effective + u2.pathname + u2.search + u2.hash;
                updated = true;
              }
            } catch(e) {}
          }
          if (obj['@graph'] && Array.isArray(obj['@graph'])) obj['@graph'].forEach(replaceUrl);
          Object.keys(obj).forEach(function (k) { if (obj[k] && typeof obj[k] === 'object') replaceUrl(obj[k]); });
        }
        replaceUrl(json);
        if (updated) s.textContent = JSON.stringify(json);
      } catch(e) {}
    });
    // Update support email spans from config (domain-agnostic)
    try {
      var supportEmail = (cfg.support_email || 'support@brandforge-os.com').trim();
      if (supportEmail && supportEmail.indexOf('YOUR')===-1) {
        document.querySelectorAll('[data-support-email]').forEach(function(el){
          el.textContent = supportEmail;
        });
      }
    } catch(e) {}
    if (window.console && window.location.search.indexOf('debug') !== -1) console.info('BrandForge OS: effective domain', effective);
  } catch(e) { if (window.console) console.warn('Domain fixer failed', e); }
})();
