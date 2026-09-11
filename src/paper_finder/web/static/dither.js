"use strict";

// Interactive dithered-wave backdrop (the surface the frosted panels refract).
// A dependency-free WebGL2 port of react-bits' <Dither />: a fractal-noise
// wave field is generated and ordered-dithered (8x8 Bayer matrix) in a single
// combined fragment-shader pass on a fullscreen triangle -- the upstream
// component's react-three-fiber + postprocessing two-pass pipeline collapses
// into one draw call here since this page has no other 3D content to
// composite with, and no react/three/postprocessing dependency is needed for
// that. The wave field reacts continuously to the pointer's screen-space
// distance (not the old dot grid's spring physics).
//
// Honours prefers-reduced-motion (one static frame, no pointer reactivity)
// and pauses while the tab is hidden. Loaded as a plain <script defer> on
// every page; owns only the #bg-dither canvas and nothing else. Silently
// does nothing if WebGL2 isn't available -- the page's plain `--bg` colour
// behind the (then-empty) canvas is still themed correctly.

(function () {
  const canvas = document.getElementById("bg-dither");
  if (!canvas) return;
  const gl = canvas.getContext("webgl2", { antialias: false, alpha: false, depth: false });
  if (!gl) return;

  // --- tunables --------------------------------------------------------
  // Matches the react-bits <Dither /> usage example; wave speed started at
  // 0.03, then slowed further twice per request (0.015, then 0.01), and
  // colour depth was raised from the component's default of 4 to 6, per request.
  const WAVE_SPEED = 0.01;
  const WAVE_FREQUENCY = 3;
  const WAVE_AMPLITUDE = 0.3;
  const MOUSE_RADIUS = 0.3;
  const COLOR_NUM = 6;
  const PIXEL_SIZE = 2;

  const reduceMotion = window.matchMedia("(prefers-reduced-motion: reduce)");

  // --- colour ------------------------------------------------------------
  // Read --dither-wave / --dither-bg off :root so the field tracks the theme --
  // both the wave (darker/more saturated in light mode for contrast against
  // the cream ground, lighter in dark mode against the navy) and the
  // background swap per theme.
  let waveRgb = [0.114, 0.306, 0.847]; // #1d4ed8 fallback (light-mode default)
  let bgRgb = [0.957, 0.929, 0.812]; // #f4edcf fallback

  function parseColor01(str, fallback) {
    str = (str || "").trim();
    let m = str.match(/^#([0-9a-f]{3})$/i);
    if (m) {
      const h = m[1];
      return [
        parseInt(h[0] + h[0], 16) / 255,
        parseInt(h[1] + h[1], 16) / 255,
        parseInt(h[2] + h[2], 16) / 255,
      ];
    }
    m = str.match(/^#([0-9a-f]{6})$/i);
    if (m) {
      return [
        parseInt(m[1].slice(0, 2), 16) / 255,
        parseInt(m[1].slice(2, 4), 16) / 255,
        parseInt(m[1].slice(4, 6), 16) / 255,
      ];
    }
    m = str.match(/^rgba?\(([^)]+)\)$/i);
    if (m) {
      const p = m[1].split(",").map((s) => parseFloat(s));
      return [(p[0] || 0) / 255, (p[1] || 0) / 255, (p[2] || 0) / 255];
    }
    return fallback;
  }

  function readColors() {
    const cs = getComputedStyle(document.documentElement);
    waveRgb = parseColor01(cs.getPropertyValue("--dither-wave"), waveRgb);
    bgRgb = parseColor01(cs.getPropertyValue("--dither-bg"), bgRgb);
  }

  // --- shaders -----------------------------------------------------------
  // A fullscreen triangle from gl_VertexID alone -- no vertex buffer needed.
  const VERTEX_SRC = `#version 300 es
    void main() {
      vec2 p = vec2((gl_VertexID << 1) & 2, gl_VertexID & 2);
      gl_Position = vec4(p * 2.0 - 1.0, 0.0, 1.0);
    }
  `;

  // The noise (mod289/permute/taylorInvSqrt/fade/cnoise/fbm/pattern) and the
  // 8x8 ordered-dither step are the upstream shaders verbatim, just fused
  // into one pass: `dither()` reads the wave colour directly instead of a
  // separate postprocessing texture sample.
  const FRAGMENT_SRC = `#version 300 es
    precision highp float;
    uniform vec2 uResolution;
    uniform float uTime;
    uniform float uWaveSpeed;
    uniform float uWaveFrequency;
    uniform float uWaveAmplitude;
    uniform vec3 uWaveColor;
    uniform vec3 uBackgroundColor;
    uniform vec2 uMouse;
    uniform int uMouseInteraction;
    uniform float uMouseRadius;
    uniform float uColorNum;
    uniform float uPixelSize;
    out vec4 fragColor;

    vec4 mod289(vec4 x) { return x - floor(x * (1.0 / 289.0)) * 289.0; }
    vec4 permute(vec4 x) { return mod289(((x * 34.0) + 1.0) * x); }
    vec4 taylorInvSqrt(vec4 r) { return 1.79284291400159 - 0.85373472095314 * r; }
    vec2 fade(vec2 t) { return t * t * t * (t * (t * 6.0 - 15.0) + 10.0); }

    float cnoise(vec2 P) {
      vec4 Pi = floor(P.xyxy) + vec4(0.0, 0.0, 1.0, 1.0);
      vec4 Pf = fract(P.xyxy) - vec4(0.0, 0.0, 1.0, 1.0);
      Pi = mod289(Pi);
      vec4 ix = Pi.xzxz;
      vec4 iy = Pi.yyww;
      vec4 fx = Pf.xzxz;
      vec4 fy = Pf.yyww;
      vec4 i = permute(permute(ix) + iy);
      vec4 gx = fract(i * (1.0 / 41.0)) * 2.0 - 1.0;
      vec4 gy = abs(gx) - 0.5;
      vec4 tx = floor(gx + 0.5);
      gx = gx - tx;
      vec2 g00 = vec2(gx.x, gy.x);
      vec2 g10 = vec2(gx.y, gy.y);
      vec2 g01 = vec2(gx.z, gy.z);
      vec2 g11 = vec2(gx.w, gy.w);
      vec4 norm = taylorInvSqrt(vec4(dot(g00, g00), dot(g01, g01), dot(g10, g10), dot(g11, g11)));
      g00 *= norm.x; g01 *= norm.y; g10 *= norm.z; g11 *= norm.w;
      float n00 = dot(g00, vec2(fx.x, fy.x));
      float n10 = dot(g10, vec2(fx.y, fy.y));
      float n01 = dot(g01, vec2(fx.z, fy.z));
      float n11 = dot(g11, vec2(fx.w, fy.w));
      vec2 fade_xy = fade(Pf.xy);
      vec2 n_x = mix(vec2(n00, n01), vec2(n10, n11), fade_xy.x);
      return 2.3 * mix(n_x.x, n_x.y, fade_xy.y);
    }

    float fbm(vec2 p) {
      float value = 0.0;
      float amp = 1.0;
      float freq = uWaveFrequency;
      for (int i = 0; i < 4; i++) {
        value += amp * abs(cnoise(p));
        p *= freq;
        amp *= uWaveAmplitude;
      }
      return value;
    }

    float pattern(vec2 p) {
      vec2 p2 = p - uTime * uWaveSpeed;
      return fbm(p + fbm(p2));
    }

    const float bayerMatrix8x8[64] = float[64](
      0.0 / 64.0, 48.0 / 64.0, 12.0 / 64.0, 60.0 / 64.0,  3.0 / 64.0, 51.0 / 64.0, 15.0 / 64.0, 63.0 / 64.0,
      32.0 / 64.0, 16.0 / 64.0, 44.0 / 64.0, 28.0 / 64.0, 35.0 / 64.0, 19.0 / 64.0, 47.0 / 64.0, 31.0 / 64.0,
      8.0 / 64.0, 56.0 / 64.0,  4.0 / 64.0, 52.0 / 64.0, 11.0 / 64.0, 59.0 / 64.0,  7.0 / 64.0, 55.0 / 64.0,
      40.0 / 64.0, 24.0 / 64.0, 36.0 / 64.0, 20.0 / 64.0, 43.0 / 64.0, 27.0 / 64.0, 39.0 / 64.0, 23.0 / 64.0,
      2.0 / 64.0, 50.0 / 64.0, 14.0 / 64.0, 62.0 / 64.0,  1.0 / 64.0, 49.0 / 64.0, 13.0 / 64.0, 61.0 / 64.0,
      34.0 / 64.0, 18.0 / 64.0, 46.0 / 64.0, 30.0 / 64.0, 33.0 / 64.0, 17.0 / 64.0, 45.0 / 64.0, 29.0 / 64.0,
      10.0 / 64.0, 58.0 / 64.0,  6.0 / 64.0, 54.0 / 64.0,  9.0 / 64.0, 57.0 / 64.0,  5.0 / 64.0, 53.0 / 64.0,
      42.0 / 64.0, 26.0 / 64.0, 38.0 / 64.0, 22.0 / 64.0, 41.0 / 64.0, 25.0 / 64.0, 37.0 / 64.0, 21.0 / 64.0
    );

    vec3 orderedDither(vec2 fragCoord, vec3 color) {
      vec2 scaledCoord = floor(fragCoord / uPixelSize);
      int x = int(mod(scaledCoord.x, 8.0));
      int y = int(mod(scaledCoord.y, 8.0));
      float threshold = bayerMatrix8x8[y * 8 + x] - 0.25;
      float step = 1.0 / (uColorNum - 1.0);
      color += threshold * step;
      float luminance = dot(color, vec3(0.2126, 0.7152, 0.0722));
      float bias = mix(0.2, 0.0, smoothstep(0.45, 0.8, luminance));
      color = clamp(color - bias, 0.0, 1.0);
      return floor(color * (uColorNum - 1.0) + 0.5) / (uColorNum - 1.0);
    }

    void main() {
      // snap the sampling point to a uPixelSize grid first -- this mirrors the
      // upstream two-pass pipeline (wave generated at full res, then resampled
      // at pixelSize granularity by the dither post-process)
      vec2 pixelCoord = floor(gl_FragCoord.xy / uPixelSize) * uPixelSize;
      vec2 uv = pixelCoord / uResolution - 0.5;
      uv.x *= uResolution.x / uResolution.y;

      float f = pattern(uv);
      if (uMouseInteraction == 1) {
        vec2 mouseNDC = (uMouse / uResolution - 0.5) * vec2(1.0, -1.0);
        mouseNDC.x *= uResolution.x / uResolution.y;
        float dist = length(uv - mouseNDC);
        float effect = 1.0 - smoothstep(0.0, uMouseRadius, dist);
        f -= 0.5 * effect;
      }
      vec3 col = mix(uBackgroundColor, uWaveColor, clamp(f, 0.0, 1.0));
      col = orderedDither(gl_FragCoord.xy, col);
      fragColor = vec4(col, 1.0);
    }
  `;

  function compile(type, src) {
    const sh = gl.createShader(type);
    gl.shaderSource(sh, src);
    gl.compileShader(sh);
    if (!gl.getShaderParameter(sh, gl.COMPILE_STATUS)) {
      console.error("dither.js shader error:", gl.getShaderInfoLog(sh));
      gl.deleteShader(sh);
      return null;
    }
    return sh;
  }

  const vs = compile(gl.VERTEX_SHADER, VERTEX_SRC);
  const fs = compile(gl.FRAGMENT_SHADER, FRAGMENT_SRC);
  if (!vs || !fs) return;

  const program = gl.createProgram();
  gl.attachShader(program, vs);
  gl.attachShader(program, fs);
  gl.linkProgram(program);
  if (!gl.getProgramParameter(program, gl.LINK_STATUS)) {
    console.error("dither.js link error:", gl.getProgramInfoLog(program));
    return;
  }
  gl.useProgram(program);

  const u = {};
  for (const name of [
    "uResolution",
    "uTime",
    "uWaveSpeed",
    "uWaveFrequency",
    "uWaveAmplitude",
    "uWaveColor",
    "uBackgroundColor",
    "uMouse",
    "uMouseInteraction",
    "uMouseRadius",
    "uColorNum",
    "uPixelSize",
  ]) {
    u[name] = gl.getUniformLocation(program, name);
  }

  gl.uniform1f(u.uWaveSpeed, WAVE_SPEED);
  gl.uniform1f(u.uWaveFrequency, WAVE_FREQUENCY);
  gl.uniform1f(u.uWaveAmplitude, WAVE_AMPLITUDE);
  gl.uniform1f(u.uMouseRadius, MOUSE_RADIUS);
  gl.uniform1f(u.uColorNum, COLOR_NUM);
  gl.uniform1f(u.uPixelSize, PIXEL_SIZE);

  // --- sizing --------------------------------------------------------
  // Fixed at 1x regardless of devicePixelRatio, same as upstream's `dpr={1}`
  // -- the noise loop (4 fbm octaves) runs per pixel every frame, and the
  // dithering already chunks pixels, so a retina backing buffer would be
  // 4x the cost for no visible benefit on a decorative backdrop.
  let width = 0;
  let height = 0;
  function resize() {
    width = window.innerWidth;
    height = window.innerHeight;
    canvas.width = width;
    canvas.height = height;
    canvas.style.width = width + "px";
    canvas.style.height = height + "px";
    gl.viewport(0, 0, width, height);
    gl.uniform2f(u.uResolution, width, height);
  }

  // --- pointer ---------------------------------------------------------
  // Canvas is fixed at (0,0) and 1x scaled, so client coords == canvas coords.
  const mouse = { x: -9999, y: -9999 };
  function onMove(e) {
    mouse.x = e.clientX;
    mouse.y = e.clientY;
  }

  // --- draw ------------------------------------------------------------
  let startTime = 0;
  function paint(elapsed) {
    gl.uniform1f(u.uTime, elapsed);
    gl.uniform3f(u.uWaveColor, waveRgb[0], waveRgb[1], waveRgb[2]);
    gl.uniform3f(u.uBackgroundColor, bgRgb[0], bgRgb[1], bgRgb[2]);
    gl.uniform2f(u.uMouse, mouse.x, mouse.y);
    gl.drawArrays(gl.TRIANGLES, 0, 3);
  }

  // --- lifecycle ---------------------------------------------------
  let rafId = 0;
  function loop(now) {
    paint((now - startTime) / 1000);
    rafId = requestAnimationFrame(loop);
  }

  function start() {
    if (rafId || reduceMotion.matches) return;
    startTime = performance.now();
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
      resize();
      if (reduceMotion.matches) paint(0);
    }, 120);
  }

  function applyMotionMode() {
    stop();
    if (reduceMotion.matches) {
      window.removeEventListener("mousemove", onMove);
      gl.uniform1i(u.uMouseInteraction, 0);
      paint(0);
    } else {
      window.addEventListener("mousemove", onMove, { passive: true });
      gl.uniform1i(u.uMouseInteraction, 1);
      start();
    }
  }

  readColors();
  resize();
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
  // common.js fires this when the header toggle flips data-theme
  window.addEventListener("themechange", onScheme);
})();
