/* BRANDFORGE OS — scroll reveal (staggered, once, reduced-motion safe) */
(function () {
  var els = document.querySelectorAll('[data-rv]');
  if (!els.length) return;
  if (!('IntersectionObserver' in window)) {
    els.forEach(function (e) { e.classList.add('in'); });
  } else {
    var io = new IntersectionObserver(function (entries) {
      entries.forEach(function (e) {
        if (e.isIntersecting) { e.target.classList.add('in'); io.unobserve(e.target); }
      });
    }, { threshold: 0.14, rootMargin: '0px 0px -40px 0px' });
    els.forEach(function (e) { io.observe(e); });
  }
  setTimeout(function () { document.body.classList.add('loaded'); }, 80);
})();
