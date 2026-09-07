/* BrandForge hero swarm — the six agent orbs.
   One transparent canvas behind the hero copy: six orbs orbit AROUND the
   headline on a wide ellipse. Each orb carries its OWN agent color
   (strategy=gold, copy=pink, visuals=teal, distribution=blue, audit=violet,
   ROI=orange) with a matching comet trail — one per pipeline stage.
   Theme-aware: light mode uses deeper hues with a tighter halo so trails
   read as color on paper (a pale-gold glow would smudge brown on cream).
   Trails are drawn per-segment on a cleared canvas (no fade rectangle), so
   the canvas stays fully transparent and brand glows show through.
   Honors prefers-reduced-motion (static frame), pauses when the tab hides,
   scales for devicePixelRatio, re-measures/recolors on resize + theme toggle.
   No dependencies. */
(function () {
  'use strict';
  const canvas = document.getElementById('hero-swarm');
  if (!canvas) return;
  const hero = canvas.parentElement;
  const ctx = canvas.getContext('2d');
  if (!ctx) return;

  const ORBS = 6;
  const PERIOD_MS = 42000;
  const TRAIL = 26;
  const PALETTES = {
    // [r,g,b] per agent — saturated enough to read as distinct hues on dark navy
    dark: [[232,181,74],[244,114,182],[45,212,191],[96,165,250],[167,139,250],[251,146,60]],
    // deepened for paper backgrounds; halos kept faint so nothing smudges
    light: [[176,118,10],[199,44,124],[8,145,129],[29,105,216],[124,58,237],[217,99,10]]
  };
  const reduced = window.matchMedia && window.matchMedia('(prefers-reduced-motion: reduce)').matches;

  let W = 0, H = 0, dpr = 1, raf = 0, trails = [];

  function theme() {
    return document.documentElement.getAttribute('data-theme') === 'light' ? 'light' : 'dark';
  }
  function rgba(rgb, a) { return `rgba(${rgb[0]},${rgb[1]},${rgb[2]},${a})`; }

  function resize() {
    dpr = Math.min(window.devicePixelRatio || 1, 2);
    W = hero.clientWidth; H = hero.clientHeight;
    canvas.width = Math.round(W * dpr);
    canvas.height = Math.round(H * dpr);
    ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
  }

  function pos(i, t) {
    const cx = W / 2, cy = H * 0.44;
    const rx = Math.max(W * 0.48, 260), ry = Math.max(H * 0.37, 130);
    const a = (t / PERIOD_MS) * Math.PI * 2 + (i * Math.PI * 2) / ORBS;
    return { x: cx + Math.cos(a) * rx, y: cy + Math.sin(a) * ry, s: 1 + 0.18 * Math.sin(a * 3 + i) };
  }

  function frame(t) {
    const mode = theme(), pal = PALETTES[mode], isLight = mode === 'light';
    ctx.clearRect(0, 0, W, H);
    ctx.strokeStyle = isLight ? 'rgba(120,90,20,0.09)' : 'rgba(232,181,74,0.07)';
    ctx.lineWidth = 1;
    ctx.beginPath();
    ctx.ellipse(W / 2, H * 0.44, Math.max(W * 0.48, 260), Math.max(H * 0.37, 130), 0, 0, Math.PI * 2);
    ctx.stroke();
    for (let i = 0; i < ORBS; i++) {
      const c = pal[i], now = pos(i, t);
      trails[i] = trails[i] || [];
      trails[i].push(now); if (trails[i].length > TRAIL) trails[i].shift();
      for (let j = 0; j < trails[i].length; j++) {
        const q = trails[i][j], f = j / trails[i].length;
        ctx.beginPath();
        ctx.arc(q.x, q.y, 1.4 + 2.2 * f, 0, Math.PI * 2);
        ctx.fillStyle = rgba(c, (isLight ? 0.04 : 0.05) + (isLight ? 0.16 : 0.20) * f);
        ctx.fill();
      }
      const r = 4.2 * now.s;
      const g = ctx.createRadialGradient(now.x, now.y, 0, now.x, now.y, r * 4);
      g.addColorStop(0, rgba(c, isLight ? 0.30 : 0.55)); g.addColorStop(1, rgba(c, 0));
      ctx.beginPath(); ctx.arc(now.x, now.y, r * 4, 0, Math.PI * 2); ctx.fillStyle = g; ctx.fill();
      ctx.beginPath(); ctx.arc(now.x, now.y, r, 0, Math.PI * 2);
      ctx.fillStyle = rgba(c, isLight ? 0.95 : 0.9);
      ctx.fill();
    }
  }

  function loop(t) { frame(t); raf = requestAnimationFrame(loop); }
  function start() { if (!raf && !reduced) raf = requestAnimationFrame(loop); }
  function stop() { cancelAnimationFrame(raf); raf = 0; }

  resize();
  if (reduced) { frame(0); } else { start(); }
  document.addEventListener('visibilitychange', function () { document.hidden ? stop() : start(); });
  const redraw = function () { resize(); if (reduced) frame(0); };
  if (window.ResizeObserver) new ResizeObserver(redraw).observe(hero);
  else window.addEventListener('resize', redraw);
  new MutationObserver(function () { if (reduced) frame(0); })
    .observe(document.documentElement, { attributes: true, attributeFilter: ['data-theme'] });
})();
