/* BRANDFORGE OS — theme toggle (dark default, persisted) */
(function () {
  var KEY = 'brandforge-theme';
  function current() { return document.documentElement.getAttribute('data-theme') || 'dark'; }
  function set(t) {
    if (t === 'light') document.documentElement.setAttribute('data-theme', 'light');
    else document.documentElement.removeAttribute('data-theme');
    try { localStorage.setItem(KEY, t); } catch (e) {}
    // Persist to a site-wide cookie so app.brandforge-os.com agrees with www.
    try { document.cookie = 'brandforge-theme=' + t + ';Path=/;Domain=.brandforge-os.com;Max-Age=' + (365 * 24 * 60 * 60); } catch (e) {}
    document.dispatchEvent(new CustomEvent('brandforge-theme-change', { detail: { theme: current() } }));
  }
  window.bfSetTheme = function (t) { set(t); };
  document.addEventListener('DOMContentLoaded', function () {
    document.querySelectorAll('.theme-toggle').forEach(function (btn) {
      btn.addEventListener('click', function () { set(current() === 'dark' ? 'light' : 'dark'); });
    });
  });
})();
