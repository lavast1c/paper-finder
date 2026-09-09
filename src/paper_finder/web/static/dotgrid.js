"use strict";

// Interactive dot-grid backdrop (the surface the frosted panels refract).
// A dependency-free port of react-bits' <DotGrid />: dots sit dim at rest and
// light up toward the page accent (--primary) near the pointer. A deliberate
// fast swipe nudges nearby dots; a click bursts every dot in range radially
// outward. Displaced dots ride a frame-rate-independent damped spring home
// (one soft overshoot, then still) — a slow aiming move leaves the grid
// perfectly quiet.
//
// Honours prefers-reduced-motion (static grid, no reactivity) and pauses while
// the tab is hidden. Loaded as a plain <script defer> on every page; owns only
// the #bg-dots canvas and nothing else.

(function () {
  const canvas = document.getElementById("bg-dots");
  if (!canvas) return;
  const ctx = canvas.getContext("2d");
  if (!ctx) return;

  // --- tunables ---------------------------------------------------------
  const DOT_SIZE = 4; // px, at 1x
  const GAP = 26; // px between dot centres minus DOT_SIZE
  const PROXIMITY = 150; // px: pointer influence radius (colour glow)

  // motion: a frame-rate-independent damped spring (semi-implicit Euler).
  // STIFFNESS pulls a displaced dot home; DAMPING < critical leaves a soft
  // single overshoot — the "burst and settle".
  const STIFFNESS = 46;
  const DAMPING = 5.6;
  const MAX_DT = 1 / 30; // clamp long frames (tab refocus) so the spring can't blow up
  const MAX_OFFSET = 42; // px a dot may stray from home
  const MAX_VELOCITY = 560; // px/s cap so repeated clicks can't fling dots away

  // pointer flick: only a deliberate fast swipe nudges dots — a slow aiming
  // move must leave the grid perfectly still.
  const SPEED_TRIGGER = 650; // px/s
  const FLICK_STRENGTH = 55; // impulse (px/s) at the pointer, tapering over PROXIMITY
  const FLICK_COOLDOWN = 450; // ms before the same dot can be flicked again

  // click burst: every dot in range gets shoved radially outward, then springs back
  const SHOCK_RADIUS = 260; // px
  const SHOCK_STRENGTH = 190; // impulse (px/s) at the epicentre

  const reduceMotion = window.matchMedia("(prefers-reduced-motion: reduce)");

  // --- colour ----------------------------------------------------------
  // Read --dot-base / --primary off :root so the grid tracks the theme.
  let baseRgb = { r: 37, g: 99, b: 235, a: 0.18 };
  let activeRgb = { r: 37, g: 99, b: 235, a: 1 };

  function parseColor(str, fallback) {
    str = (str || "").trim();
    let m = str.match(/^#([0-9a-f]{3})$/i);
    if (m) {
      const h = m[1];
      return {
        r: parseInt(h[0] + h[0], 16),
        g: parseInt(h[1] + h[1], 16),
        b: parseInt(h[2] + h[2], 16),
        a: 1,
      };
    }
    m = str.match(/^#([0-9a-f]{6})$/i);
    if (m) {
      return {
        r: parseInt(m[1].slice(0, 2), 16),
        g: parseInt(m[1].slice(2, 4), 16),
        b: parseInt(m[1].slice(4, 6), 16),
        a: 1,
      };
    }
    m = str.match(/^rgba?\(([^)]+)\)$/i);
    if (m) {
      const p = m[1].split(",").map((s) => parseFloat(s));
      return { r: p[0] || 0, g: p[1] || 0, b: p[2] || 0, a: p[3] == null ? 1 : p[3] };
    }
    return fallback;
  }

  function readColors() {
    const cs = getComputedStyle(document.documentElement);
    baseRgb = parseColor(cs.getPropertyValue("--dot-base"), baseRgb);
    activeRgb = parseColor(cs.getPropertyValue("--primary"), activeRgb);
  }

  // --- grid ------------------------------------------------------------
  let dots = [];
  let dpr = 1;

  function buildGrid() {
    const w = window.innerWidth;
    const h = window.innerHeight;
    dpr = window.devicePixelRatio || 1;

    canvas.width = Math.round(w * dpr);
    canvas.height = Math.round(h * dpr);
    canvas.style.width = w + "px";
    canvas.style.height = h + "px";
    ctx.setTransform(dpr, 0, 0, dpr, 0, 0);

    const cell = DOT_SIZE + GAP;
    const cols = Math.max(1, Math.floor((w + GAP) / cell));
    const rows = Math.max(1, Math.floor((h + GAP) / cell));
    const startX = (w - (cell * cols - GAP)) / 2 + DOT_SIZE / 2;
    const startY = (h - (cell * rows - GAP)) / 2 + DOT_SIZE / 2;

    dots = [];
    for (let y = 0; y < rows; y++) {
      for (let x = 0; x < cols; x++) {
        dots.push({
          cx: startX + x * cell,
          cy: startY + y * cell,
          ox: 0,
          oy: 0,
          vx: 0,
          vy: 0,
          flickT: 0,
        });
      }
    }
  }

  // --- pointer --------------------------------------------------------
  const pointer = { x: -9999, y: -9999, lastX: 0, lastY: 0, lastT: 0, speed: 0, vx: 0, vy: 0 };

  function onMove(e) {
    const now = performance.now();
    const dt = pointer.lastT ? Math.max(now - pointer.lastT, 1) : 16;
    const dx = e.clientX - pointer.lastX;
    const dy = e.clientY - pointer.lastY;
    pointer.vx = (dx / dt) * 1000;
    pointer.vy = (dy / dt) * 1000;
    // low-pass the speed so one noisy throttled sample can't spike past the trigger
    pointer.speed = pointer.speed * 0.4 + Math.hypot(pointer.vx, pointer.vy) * 0.6;
    pointer.lastT = now;
    pointer.lastX = e.clientX;
    pointer.lastY = e.clientY;
    pointer.x = e.clientX; // canvas is fixed at (0,0) → client coords are canvas coords
    pointer.y = e.clientY;

    if (pointer.speed <= SPEED_TRIGGER) return;
    const proxSq = PROXIMITY * PROXIMITY;
    for (const dot of dots) {
      if (now - dot.flickT < FLICK_COOLDOWN) continue;
      const ddx = dot.cx - pointer.x;
      const ddy = dot.cy - pointer.y;
      const dsq = ddx * ddx + ddy * ddy;
      if (dsq > proxSq || dsq < 1) continue;
      const dist = Math.sqrt(dsq);
      const taper = 1 - dist / PROXIMITY;
      const impulse = (FLICK_STRENGTH * taper) / dist;
      dot.vx += ddx * impulse;
      dot.vy += ddy * impulse;
      dot.flickT = now;
    }
  }

  function onClick(e) {
    const cx = e.clientX;
    const cy = e.clientY;
    for (const dot of dots) {
      const ddx = dot.cx - cx;
      const ddy = dot.cy - cy;
      const dist = Math.hypot(ddx, ddy);
      if (dist >= SHOCK_RADIUS || dist < 0.001) continue;
      const falloff = Math.pow(1 - dist / SHOCK_RADIUS, 0.55);
      const impulse = (SHOCK_STRENGTH * falloff) / dist;
      dot.vx += ddx * impulse;
      dot.vy += ddy * impulse;
    }
  }

  let moveQueued = 0;
  function throttledMove(e) {
    const now = performance.now();
    if (now - moveQueued < 32) return;
    moveQueued = now;
    onMove(e);
  }

  // --- draw ----------------------------------------------------------
  const TAU = Math.PI * 2;

  function paint(dt) {
    ctx.clearRect(0, 0, canvas.width, canvas.height);
    const proxSq = PROXIMITY * PROXIMITY;
    const { r: br, g: bg, b: bb, a: ba } = baseRgb;
    const { r: ar, g: ag, b: ab, a: aa } = activeRgb;
    const animate = dt > 0;

    for (const dot of dots) {
      if (animate && (dot.ox || dot.oy || dot.vx || dot.vy)) {
        // damped spring back to home, integrated frame-rate-independently
        dot.vx += (-STIFFNESS * dot.ox - DAMPING * dot.vx) * dt;
        dot.vy += (-STIFFNESS * dot.oy - DAMPING * dot.vy) * dt;

        const v = Math.hypot(dot.vx, dot.vy);
        if (v > MAX_VELOCITY) {
          const s = MAX_VELOCITY / v;
          dot.vx *= s;
          dot.vy *= s;
        }

        dot.ox += dot.vx * dt;
        dot.oy += dot.vy * dt;

        const off = Math.hypot(dot.ox, dot.oy);
        if (off > MAX_OFFSET) {
          const s = MAX_OFFSET / off;
          dot.ox *= s;
          dot.oy *= s;
        }

        // settle: once the wobble is sub-pixel, snap to rest so nothing jitters
        if (Math.abs(dot.ox) < 0.05 && Math.abs(dot.oy) < 0.05 && v < 1.5) {
          dot.ox = dot.oy = dot.vx = dot.vy = 0;
        }
      }

      let cr = br;
      let cg = bg;
      let cb = bb;
      let ca = ba;
      let radius = DOT_SIZE / 2;
      if (animate) {
        const ddx = dot.cx - pointer.x;
        const ddy = dot.cy - pointer.y;
        const dsq = ddx * ddx + ddy * ddy;
        if (dsq <= proxSq) {
          const lin = 1 - Math.sqrt(dsq) / PROXIMITY;
          const t = lin * (2 - lin); // ease-out: a broader, softer glow
          cr = br + (ar - br) * t;
          cg = bg + (ag - bg) * t;
          cb = bb + (ab - bb) * t;
          ca = ba + (aa - ba) * t;
          radius += radius * t * 0.45; // active dots bloom a little
        }
      }

      ctx.beginPath();
      ctx.fillStyle = `rgba(${cr | 0},${cg | 0},${cb | 0},${ca})`;
      ctx.arc(dot.cx + dot.ox, dot.cy + dot.oy, radius, 0, TAU);
      ctx.fill();
    }
  }

  // --- lifecycle ---------------------------------------------------
  let rafId = 0;
  let lastFrame = 0;
  function loop(now) {
    let dt = (now - lastFrame) / 1000;
    lastFrame = now;
    if (!(dt > 0) || dt > MAX_DT) dt = MAX_DT;
    paint(dt);
    rafId = requestAnimationFrame(loop);
  }

  function start() {
    if (rafId || reduceMotion.matches) return;
    lastFrame = performance.now();
    rafId = requestAnimationFrame(loop);
  }
  function stop() {
    cancelAnimationFrame(rafId);
    rafId = 0;
  }

  let resizeTimer = 0;
  function onResize() {
    clearTimeout(resizeTimer);
    resizeTimer = setTimeout(() => {
      buildGrid();
      if (reduceMotion.matches) paint(0);
    }, 120);
  }

  function applyMotionMode() {
    stop();
    if (reduceMotion.matches) {
      window.removeEventListener("mousemove", throttledMove);
      window.removeEventListener("click", onClick);
      paint(0);
    } else {
      window.addEventListener("mousemove", throttledMove, { passive: true });
      window.addEventListener("click", onClick);
      start();
    }
  }

  readColors();
  buildGrid();
  applyMotionMode();

  window.addEventListener("resize", onResize);
  document.addEventListener("visibilitychange", () => {
    if (document.hidden) stop();
    else start();
  });
  const schemeQuery = window.matchMedia("(prefers-color-scheme: dark)");
  const onScheme = () => {
    readColors();
    if (reduceMotion.matches) paint(0);
  };
  if (schemeQuery.addEventListener) schemeQuery.addEventListener("change", onScheme);
  if (reduceMotion.addEventListener) reduceMotion.addEventListener("change", applyMotionMode);
})();
