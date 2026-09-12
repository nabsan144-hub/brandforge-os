/* BrandForge hero swarm — the six agent orbs.
   One transparent canvas behind the hero copy: six orbs DRIFT FREELY through
   the hero (no fixed orbit, no guide ring — an earlier version stroked the
   ellipse path and read as a visible circle). Each orb carries its OWN agent
   color (strategy=gold, copy=pink, visuals=teal, distribution=blue, audit=violet,
   ROI=orange) with a matching comet trail — one per pipeline stage.
   Motion model per orb: smooth layered-sine steering + soft acceleration toward
   the hero's comfortable zone when it strays near the edges, plus a SCATTER
   impulse when the visitor clicks/taps anywhere in the hero — the orbs are the
   6 agents being poked. Pointer events stay off the canvas itself; the scatter
   listens on the hero so links/buttons still behave normally.
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
  const TRAIL = 26;
  const PALETTES = {
    // [r,g,b] per agent — saturated enough to read as distinct hues on dark navy
    dark: [[232,181,74],[244,114,182],[45,212,191],[96,165,250],[167,139,250],[251,146,60]],
    // deepened for paper backgrounds; halos kept faint so nothing smudges
    light: [[176,118,10],[199,44,124],[8,145,129],[29,105,216],[124,58,237],[217,99,10]]
  };
  const reduced = window.matchMedia && window.matchMedia('(prefers-reduced-motion: reduce)').matches;

  let W = 0, H = 0, dpr = 1, raf = 0, last = 0, trails = [];
  const orbs = [];

  function theme() {
    return document.documentElement.getAttribute('data-theme') === 'light' ? 'light' : 'dark';
  }
  function rgba(rgb, a) { return `rgba(${rgb[0]},${rgb[1]},${rgb[2]},${a})`; }

  function seed(i) {
    // deterministic, well-spread starting positions (ring -> scattered)
    const a = (i * Math.PI * 2) / ORBS + i * 1.7;
    return {
      x: W / 2 + Math.cos(a) * W * 0.22,
      y: H * 0.45 + Math.sin(a) * H * 0.18,
      vx: Math.cos(a + 1.3) * 14,            // px/s, gentle
      vy: Math.sin(a + 1.3) * 14,
      f1: 0.00021 + i * 0.00003,             // wander frequencies (distinct per orb)
      f2: 0.00034 + i * 0.00005,
      p1: i * 2.13,                          // wander phases
      p2: i * 3.71,
      pulse: i * 1.31
    };
  }

  function resize() {
    dpr = Math.min(window.devicePixelRatio || 1, 2);
    W = hero.clientWidth; H = hero.clientHeight;
    canvas.width = Math.round(W * dpr);
    canvas.height = Math.round(H * dpr);
    ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
    for (let i = 0; i < ORBS; i++) {
      if (!orbs[i]) orbs[i] = seed(i);
      else { // keep everyone inside after a big resize
        orbs[i].x = Math.min(Math.max(orbs[i].x, W * 0.04), W * 0.96);
        orbs[i].y = Math.min(Math.max(orbs[i].y, H * 0.06), H * 0.94);
      }
    }
  }

  // comfortable roaming zone — orbs may briefly leave it, then get steered back
  function step(dt, t) {
    const minX = W * 0.05, maxX = W * 0.95, minY = H * 0.08, maxY = H * 0.92;
    for (let i = 0; i < ORBS; i++) {
      const o = orbs[i];
      // organic wander: two layered sine pushes, distinct per orb
      let ax = Math.sin(t * o.f1 + o.p1) * 26 + Math.cos(t * o.f2 + o.p2) * 16;
      let ay = Math.cos(t * o.f2 + o.p1) * 22 + Math.sin(t * o.f1 + o.p2) * 14;
      // soft containment: only accelerates back when straying past the zone
      if (o.x < minX) ax += (minX - o.x) * 1.4;
      if (o.x > maxX) ax -= (o.x - maxX) * 1.4;
      if (o.y < minY) ay += (minY - o.y) * 1.4;
      if (o.y > maxY) ay -= (o.y - maxY) * 1.4;
      o.vx = (o.vx + ax * dt) * 0.992;
      o.vy = (o.vy + ay * dt) * 0.992;
      // cap speed so a scatter kick decays back to a gentle drift
      const sp = Math.hypot(o.vx, o.vy), max = 64;
      if (sp > max) { o.vx = o.vx / sp * max; o.vy = o.vy / sp * max; }
      o.x += o.vx * dt;
      o.y += o.vy * dt;
      o.s = 1 + 0.18 * Math.sin(t * 0.0011 + o.pulse);
      trails[i] = trails[i] || [];
      trails[i].push({ x: o.x, y: o.y });
      if (trails[i].length > TRAIL) trails[i].shift();
    }
  }

  function draw(t) {
    const mode = theme(), pal = PALETTES[mode], isLight = mode === 'light';
    ctx.clearRect(0, 0, W, H);
    // deliberate: NO guide ring. The orbs read as free-floating agents.
    for (let i = 0; i < ORBS; i++) {
      const c = pal[i], o = orbs[i], tr = trails[i] || [{ x: o.x, y: o.y }];
      for (let j = 0; j < tr.length; j++) {
        const q = tr[j], f = j / tr.length;
        ctx.beginPath();
        ctx.arc(q.x, q.y, 1.4 + 2.2 * f, 0, Math.PI * 2);
        ctx.fillStyle = rgba(c, (isLight ? 0.04 : 0.05) + (isLight ? 0.16 : 0.20) * f);
        ctx.fill();
      }
      const r = 4.2 * (o.s || 1);
      const g = ctx.createRadialGradient(o.x, o.y, 0, o.x, o.y, r * 4);
      g.addColorStop(0, rgba(c, isLight ? 0.30 : 0.55)); g.addColorStop(1, rgba(c, 0));
      ctx.beginPath(); ctx.arc(o.x, o.y, r * 4, 0, Math.PI * 2); ctx.fillStyle = g; ctx.fill();
      ctx.beginPath(); ctx.arc(o.x, o.y, r, 0, Math.PI * 2);
      ctx.fillStyle = rgba(c, isLight ? 0.95 : 0.9);
      ctx.fill();
    }
  }

  function loop(t) {
    const dt = Math.min((t - last) / 1000, 0.05) || 0.016;
    last = t;
    step(dt, t);
    draw(t);
    raf = requestAnimationFrame(loop);
  }
  function start() { if (!raf && !reduced) { last = 0; raf = requestAnimationFrame(loop); } }
  function stop() { cancelAnimationFrame(raf); raf = 0; }

  // click/tap anywhere in the hero -> the agents scatter from the pointer
  hero.addEventListener('pointerdown', function (e) {
    if (reduced) return;
    const r = hero.getBoundingClientRect();
    const px = e.clientX - r.left, py = e.clientY - r.top;
    for (let i = 0; i < ORBS; i++) {
      const o = orbs[i];
      const dx = o.x - px, dy = o.y - py;
      const d = Math.max(Math.hypot(dx, dy), 24);
      const kick = Math.min(260 / d, 4.5) * 42;   // nearer orbs get a bigger shove
      o.vx += (dx / d) * kick;
      o.vy += (dy / d) * kick;
    }
  });

  resize();
  if (reduced) { draw(0); } else { start(); }
  document.addEventListener('visibilitychange', function () { document.hidden ? stop() : start(); });
  const redraw = function () { resize(); if (reduced) draw(0); };
  if (window.ResizeObserver) new ResizeObserver(redraw).observe(hero);
  else window.addEventListener('resize', redraw);
  new MutationObserver(function () { if (reduced) draw(0); })
    .observe(document.documentElement, { attributes: true, attributeFilter: ['data-theme'] });
})();
