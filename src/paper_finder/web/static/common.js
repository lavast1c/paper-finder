"use strict";

// Shared code for the search page (app.js) and the topic-browse page (topics.js).
// Loaded first -- both page scripts are `defer`, so document order is guaranteed.
// Everything hangs off the single global `window.PF`; there is no module system
// and no build step, matching the rest of web/static.
//
// This file is a straight extraction from app.js: the DOM helper, the
// query-term highlighter, the question / answer renderers, `renderResult`, the
// cloud-row shim, and the whole email-code auth gate (repackaged as
// `PF.initAuth`). No behaviour change -- app.js drives it exactly as before.
//
// The whole body is wrapped in an IIFE: these are classic scripts sharing one
// global lexical scope, so a bare top-level `el` here collides with the page
// script's `const { el } = PF` ("Identifier 'el' has already been declared",
// which aborts the page script entirely). Only `window.PF` escapes the IIFE.

(function () {
const PF = (window.PF = {});

// --- tiny DOM helper -------------------------------------------------------

function el(tag, className, text) {
  const node = document.createElement(tag);
  if (className) node.className = className;
  if (text !== undefined) node.textContent = text;
  return node;
}
PF.el = el;

PF.SESSION_NAMES = { s: "May/June", w: "Oct/Nov", m: "Feb/March" };

// --- header: visible only at the top, fades away on scroll ----------------
//
// Both page scripts are `defer`, so <header> is already parsed here. We toggle
// `.is-hidden` (the fade/slide lives in style.css) whenever the page is
// scrolled past a few pixels, and restore it at the very top.

(function revealHeaderOnlyAtTop() {
  const header = document.querySelector("header");
  if (!header) return;
  const THRESHOLD = 8; // px of scroll before the bar starts to disappear
  let ticking = false;
  function sync() {
    header.classList.toggle("is-hidden", window.scrollY > THRESHOLD);
    ticking = false;
  }
  window.addEventListener(
    "scroll",
    () => {
      if (ticking) return;
      ticking = true;
      requestAnimationFrame(sync);
    },
    { passive: true },
  );
  sync();
})();

// --- theme toggle: defaults to time-of-day, header button forces light / dark ---
//
// Absent an explicit user choice, the theme follows local clock time: light
// 06:00-18:59, dark otherwise (not OS `prefers-color-scheme`). The pre-paint
// inline <script> in each HTML <head> applies this (or a saved override)
// before first paint (avoids a flash) -- `root.dataset.theme` is therefore
// always already "light" or "dark" by the time this runs. This wires the
// button, keeps its label in sync, re-checks the clock periodically so a tab
// left open across the 6am/7pm boundary still flips without a reload, and
// pokes dither.js to re-read --dither-wave / --dither-bg.

(function themeToggle() {
  const btn = document.getElementById("theme-toggle");
  const labelEl = document.getElementById("theme-toggle-label");
  const KEY = "paper-finder.theme";
  const root = document.documentElement;
  const effective = () => root.dataset.theme || "light";

  function autoTheme() {
    const h = new Date().getHours();
    return h >= 6 && h < 19 ? "light" : "dark";
  }

  function hasExplicitChoice() {
    try {
      const t = localStorage.getItem(KEY);
      return t === "dark" || t === "light";
    } catch (e) {
      return false;
    }
  }

  // The visible label names the mode a click switches TO (not the current
  // one) so it always reads as a call to action, matching the aria-label.
  function syncLabel() {
    if (!btn) return;
    const light = effective() === "light";
    const targetLabel = light ? "Dark mode" : "Light mode";
    btn.setAttribute("aria-label", `Switch to ${targetLabel.toLowerCase()}`);
    btn.setAttribute("aria-pressed", String(light));
    if (labelEl) labelEl.textContent = targetLabel;
  }

  // Re-applies the time-based theme if the user hasn't explicitly picked one
  // via the button -- keeps an open tab in sync with the clock.
  function syncAuto() {
    if (hasExplicitChoice()) return;
    const next = autoTheme();
    if (root.dataset.theme !== next) {
      root.dataset.theme = next;
      syncLabel();
      window.dispatchEvent(new Event("themechange"));
    }
  }

  if (btn) {
    btn.addEventListener("click", () => {
      const next = effective() === "light" ? "dark" : "light";
      root.dataset.theme = next;
      try {
        localStorage.setItem(KEY, next);
      } catch (e) {
        /* private mode - the choice just won't persist */
      }
      syncLabel();
      window.dispatchEvent(new Event("themechange"));
    });
    syncLabel();
  }

  // Every 5 minutes is cheap and coarse enough that a missed tick near the
  // boundary is never off by more than that.
  setInterval(syncAuto, 5 * 60 * 1000);
})();

// --- multi-select dropdown ----------------------------------------------
//
// Upgrades <div class="multiselect"> (a .ms-toggle button + a hidden .ms-panel
// of checkbox <label>s) into a closeable dropdown that takes several picks. The
// checkboxes are real, so their native `change` events bubble to the root --
// page code listens for `change` on the root and reads the picks. The returned
// api is also stashed on `root._ms` for programmatic get/set (deep links).
//
//   const ms = PF.multiSelect(root);
//   ms.values();            // ["1", "2"]
//   ms.setValues(["3"]);    // ticks the boxes + repaints the label, no event
//
// Keyboard: the toggle is a plain <button> (Space/Enter opens); Escape closes
// and returns focus; the panel is the native focus order of its checkboxes.
//
// Open/close float the panel in/out (see `.ms-panel`/`.ms-panel--from` in
// style.css). The two directions work differently:
//   - open() is a plain `hidden = false` -- style.css's @starting-style rule
//     gives the panel its "just appeared" opacity/transform, so the float-in
//     needs no JS timing at all.
//   - close() adds `.ms-panel--from` (an ordinary transition, since the panel
//     is already rendered at that point -- always reliable) and only sets
//     `hidden = true` once that transition actually finishes
//     (`transitionend`, with a timeout fallback in case it never fires -- e.g.
//     the panel gets torn down mid-animation). An earlier version instead
//     tried to animate `display` itself (via @starting-style + allow-discrete)
//     for both directions -- that turned out to be unreliable for closing:
//     the discrete `display` transition could get stuck mid-flight and never
//     actually reach `display: none`, which then silently broke every
//     *subsequent* open's animation too (the element was technically never
//     "unrendered" again, so @starting-style had nothing left to trigger on).
const REDUCED_MOTION = window.matchMedia("(prefers-reduced-motion: reduce)").matches;
const MS_CLOSE_FALLBACK_MS = 260; // > style.css's .ms-panel transition (0.2s)

function multiSelect(root) {
  if (root._ms) return root._ms;
  const toggle = root.querySelector(".ms-toggle");
  const panel = root.querySelector(".ms-panel");
  const valueEl = root.querySelector(".ms-value");
  // Queried fresh each call, not captured once -- the topic panel's checkboxes
  // are rebuilt from scratch whenever the topic list changes (subject switch,
  // count refresh), so a one-time snapshot would go stale.
  const boxes = () => [...panel.querySelectorAll('input[type="checkbox"]')];
  const placeholder = root.dataset.placeholder || "Any";

  let closeTimer = null;
  let onCloseTransitionEnd = null;

  function values() {
    return boxes()
      .filter((b) => b.checked)
      .map((b) => b.value);
  }

  function paintLabel() {
    const picked = boxes().filter((b) => b.checked);
    valueEl.textContent = picked.length
      ? picked.map((b) => b.dataset.short || b.nextElementSibling.textContent.trim()).join(", ")
      : placeholder;
    root.classList.toggle("ms--set", picked.length > 0);
  }

  function onDocClick(e) {
    if (!root.contains(e.target)) close();
  }
  function onKey(e) {
    if (e.key === "Escape") {
      close();
      toggle.focus();
    }
  }

  // Cancels a pending close-then-hide (its timer and transitionend listener)
  // without touching `hidden` -- used when a close is interrupted by a
  // reopen, and at the start of a fresh close so two never overlap.
  function cancelPendingClose() {
    if (closeTimer !== null) {
      clearTimeout(closeTimer);
      closeTimer = null;
    }
    if (onCloseTransitionEnd) {
      panel.removeEventListener("transitionend", onCloseTransitionEnd);
      onCloseTransitionEnd = null;
    }
  }

  function open() {
    if (!panel.hidden) return;
    cancelPendingClose();
    // no JS timing needed here -- style.css's @starting-style gives this its
    // "just appeared" opacity/transform, so unhiding it is enough to float it
    // in (and, with no transition under reduced motion, this is already just
    // a plain instant show)
    panel.hidden = false;
    toggle.setAttribute("aria-expanded", "true");
    document.addEventListener("click", onDocClick, true);
    document.addEventListener("keydown", onKey, true);
  }
  function close() {
    if (panel.hidden) return;
    cancelPendingClose();
    toggle.setAttribute("aria-expanded", "false");
    document.removeEventListener("click", onDocClick, true);
    document.removeEventListener("keydown", onKey, true);
    if (REDUCED_MOTION) {
      panel.hidden = true;
      return;
    }
    panel.classList.add("ms-panel--from"); // animate to the closed pose
    const finish = () => {
      cancelPendingClose();
      panel.hidden = true;
      panel.classList.remove("ms-panel--from");
    };
    onCloseTransitionEnd = (e) => {
      if (e.target === panel && e.propertyName === "opacity") finish();
    };
    panel.addEventListener("transitionend", onCloseTransitionEnd);
    closeTimer = setTimeout(finish, MS_CLOSE_FALLBACK_MS);
  }

  toggle.addEventListener("click", () => (panel.hidden ? open() : close()));
  panel.addEventListener("change", (e) => {
    if (e.target.matches('input[type="checkbox"]')) paintLabel();
  });

  paintLabel();
  const api = {
    values,
    setValues(list) {
      const want = new Set(list || []);
      for (const b of boxes()) b.checked = want.has(b.value);
      paintLabel();
    },
    close,
  };
  root._ms = api;
  return api;
}
PF.multiSelect = multiSelect;

// The "Paper(s)" filter is really the MCQ-vs-theory split: CIE Physics,
// Chemistry, Biology and Economics Paper 1 are multiple-choice, Paper 2 is
// structured/theory (there is no Paper 3 or 4 in any of them). Ticked box
// values are the paper number; collapse them to the `kind` the search /
// browse endpoints take. Both (or neither) ticked = no restriction.
PF.paperKind = function paperKind(values) {
  const s = new Set(values || []);
  if (s.size !== 1) return "all";
  return s.has("1") ? "mcq" : "theory";
};

// Which subjects actually have an MCQ paper -- the Paper(s) filter is the
// MCQ-vs-theory split above, so it is shown (and `kind` honoured) only for
// these. 9231 splits into two subjects and 9709 into five, all of them
// structured, so none of those per-paper subjects has an MCQ paper. Separate
// from DEFAULT_SUBJECT (app.js / topics.js), which is only "which subject is
// preselected".
PF.MCQ_SUBJECTS = new Set(["Physics", "Chemistry", "Biology", "Economics"]);
PF.hasMcqPapers = (subject) => PF.MCQ_SUBJECTS.has(subject);

// The "Curriculum" filter groups Subject values under CIE AS Level (every
// subject below) or CIE A Level (9709's three A Level papers). Unlike
// MCQ_SUBJECTS this isn't sent to any API -- it only decides which <option>s
// in #subject are shown, and its own <select> value is always derived back
// from the current subject rather than tracked as separate state (see
// app.js / topics.js's syncCurriculum()).
PF.A_LEVEL_SUBJECTS = new Set(["Mechanics", "Probability & Statistics 2", "Pure Mathematics 3"]);
PF.curriculumOf = (subject) => (PF.A_LEVEL_SUBJECTS.has(subject) ? "A" : "AS");

// --- query-term highlighting -----------------------------------------

const STOPWORDS = new Set(
  "the a an of is in on at to and or with for as by from that this it".split(" "),
);
let queryTerms = []; // lowercased search tokens for the current query

// Set (or clear, with "") the terms `PF.appendText` wraps in <mark>. Pages that
// never highlight -- the topic deck -- just leave this empty.
function setQueryTerms(q) {
  const seen = new Set();
  queryTerms = (q.toLowerCase().match(/[0-9a-z]+/g) || []).filter((t) => {
    if (t.length < 2 || STOPWORDS.has(t) || seen.has(t)) return false;
    seen.add(t);
    return true;
  });
}
PF.setQueryTerms = setQueryTerms;

function escapeRegExp(s) {
  return s.replace(/[.*+?^${}()|[\]\\]/g, "\\$&");
}

// Append `text` to `node`, wrapping each run that matches a query term (plus a
// short suffix, so "force" also lights up "forces"/"forced") in a <mark>. With
// no query terms set it is a plain text node -- zero cost on the topic page.
function appendText(node, text) {
  if (!text) return;
  if (!queryTerms.length) {
    node.append(document.createTextNode(text));
    return;
  }
  const re = new RegExp("\\b(?:" + queryTerms.map(escapeRegExp).join("|") + ")\\w{0,3}\\b", "gi");
  let last = 0;
  for (let m = re.exec(text); m; m = re.exec(text)) {
    if (m.index > last) node.append(document.createTextNode(text.slice(last, m.index)));
    node.append(el("mark", null, m[0]));
    last = m.index + m[0].length;
  }
  if (last < text.length) node.append(document.createTextNode(text.slice(last)));
}
PF.appendText = appendText;

function textEl(tag, className, text) {
  const node = el(tag, className);
  appendText(node, text || "");
  return node;
}

// --- rendering --------------------------------------------------------

// Structured (theory) papers label sub-parts "(a) … (b) … (i) … (ii) …" inline
// in the question, and "2(a)", "2(b)(i)" on their own line in the mark scheme.
// Split those out so each sub-part is visually separated.

const ROMAN = new Set(["i", "ii", "iii", "iv", "v", "vi", "vii", "viii", "ix", "x"]);
// a real part label is preceded by whitespace/start (so "1(a)" cross-refs don't match)
const PART_RE = /(?:^|\s)\((?<tok>[a-z]{1,3}|[ivx]{1,4})\)(?=\s|$)/g;
const MS_PART_RE = /^\d+\([a-z]\)(?:\([ivx]+\))*$/; // "2(a)", "2(b)(i)"
const MS_MARK_RE = /^\(?[ABCM]\d\)?$/; // "B1", "M1", "(A1)", "C1" — dropped from display

function splitQuestionParts(text) {
  const matches = [...text.matchAll(PART_RE)];
  if (matches.length < 2) return null;
  const parts = [];
  const intro = text.slice(0, matches[0].index).trim();
  if (intro) parts.push({ label: "", text: intro });
  for (let i = 0; i < matches.length; i++) {
    const tok = matches[i].groups.tok;
    const start = matches[i].index + matches[i][0].length;
    const end = i + 1 < matches.length ? matches[i + 1].index : text.length;
    parts.push({ label: `(${tok})`, roman: ROMAN.has(tok), text: text.slice(start, end).trim() });
  }
  return parts;
}

function questionBlock(text) {
  const box = el("div", "question");
  const parts = text ? splitQuestionParts(text) : null;
  if (!parts) {
    appendText(box, text || "");
    return box;
  }
  box.classList.add("question--parts");
  for (const p of parts) {
    if (!p.label) {
      box.append(textEl("div", "qpart qpart--intro", p.text));
      continue;
    }
    const row = el("div", "qpart" + (p.roman ? " qpart--sub" : ""));
    row.append(el("span", "qpart-label", p.label));
    if (p.text) row.append(textEl("span", "qpart-text", p.text));
    else row.classList.add("qpart--group");
    box.append(row);
  }
  return box;
}
PF.questionBlock = questionBlock;

function answerLong(box, answer) {
  const lines = answer.split(/\r?\n/).map((l) => l.trim());
  if (!lines.some((l) => MS_PART_RE.test(l))) {
    box.append(el("span", "value", answer)); // no part headers -> keep as-is (pre-wrap)
    return;
  }
  const wrap = el("div", "value ms");
  let group = wrap;
  for (const line of lines) {
    if (!line) continue;
    if (MS_PART_RE.test(line)) {
      group = el("div", "ms-part");
      group.append(el("span", "ms-part-label", line));
      wrap.append(group);
    } else if (line === "OR" || line === "ALTERNATIVE") {
      group.append(el("span", "ms-or", "OR"));
    } else if (MS_MARK_RE.test(line)) {
      continue; // bare CIE mark code (B1/M1/A1/C1) — noise on its own line
    } else {
      group.append(el("div", "ms-line", line));
    }
  }
  box.append(wrap);
}

function answerBlock(answer) {
  const box = el("div", "answer");
  box.append(el("span", "label", "Answer"));
  if (answer == null || answer === "") {
    box.className = "answer answer--none";
    box.append(el("span", "value", "No mark scheme answer linked."));
    return box;
  }
  const trimmed = answer.trim();
  if (trimmed.length === 1) {
    box.className = "answer answer--letter";
    box.append(el("span", "value", trimmed));
    return box;
  }
  box.className = "answer answer--long";
  answerLong(box, answer);
  return box;
}
PF.answerBlock = answerBlock;

function renderResult(r, rank) {
  const li = document.createElement("li");

  const title = el("div", "title");
  title.append(el("span", "rank", `${rank}.`));
  title.append(el("span", "name", r.title));
  title.append(el("code", null, r.filename));
  if (r.marks) {
    title.append(el("span", "marks", `${r.marks} mark${r.marks === 1 ? "" : "s"}`));
  }
  li.append(title);

  li.append(questionBlock(r.question_text));
  if (r.has_figure) {
    const tail = r.pdf_url ? "check the PDF" : "see the original paper";
    li.append(el("p", "figure-note", `◧ Has a diagram, graph or table — ${tail}`));
  }
  li.append(answerBlock(r.answer));

  if (r.pdf_url) {
    const a = el("a", "pdf-link", `Open PDF ▸ page ${r.page}`);
    a.href = r.pdf_url;
    a.target = "_blank";
    a.rel = "noopener";
    li.append(a);
  }

  return li;
}
PF.renderResult = renderResult;

// A Supabase RPC row -> the shape `renderResult` expects. The deployed site has
// no PDFs, so no pdf_url.
function cloudRow(d) {
  const variant = d.paper == null ? "?" : `${d.paper}${d.variant ?? ""}`;
  const sname = PF.SESSION_NAMES[d.session] || d.session;
  return {
    title: `${d.subject_name || "?"} · ${sname} ${d.year} · Paper ${variant} · Q${d.question_number}`,
    filename: d.filename,
    question_number: d.question_number, // topics.js builds the crop filename from this
    question_text: d.question_text,
    answer: d.answer_text,
    marks: d.marks,
    has_figure: d.has_figure,
    crop_count: d.crop_count || 0,
    answer_crop_count: d.answer_crop_count || 0, // mark-scheme crops; topics.js mints their signed URLs
    // no pdf_url — the deployed site has no PDFs; crops come from signed
    // Storage URLs the topic page mints itself
  };
}
PF.cloudRow = cloudRow;

// --- auth gate -------------------------------------------------------
//
// Local mode (no Supabase env): calls `onReady(null, null)` immediately, no gate.
// Cloud mode: wires the email -> 6-digit-code flow against Supabase Auth and
// calls `onReady(email, sb)` once signed in (again on every `onAuthStateChange`
// -- the caller guards its one-time setup). `onSignedOut` is optional.

PF.initAuth = function initAuth({ onReady, onSignedOut }) {
  const ids = [
    "gate",
    "app",
    "email-form",
    "email",
    "send-code",
    "code-form",
    "code",
    "code-email",
    "verify-code",
    "code-back",
    "gate-status",
    "whoami",
  ];
  const g = {};
  for (const id of ids) {
    const node = document.getElementById(id);
    if (!node) throw new Error(`PF.initAuth: page is missing #${id}`);
    g[id.replace(/-([a-z])/g, (_, c) => c.toUpperCase())] = node;
  }

  let sb = null; // Supabase client in cloud mode; null in local mode
  let pendingEmail = null; // email awaiting its one-time code

  function showApp(email) {
    g.gate.hidden = true;
    g.app.hidden = false;

    if (email) {
      g.whoami.hidden = false;
      g.whoami.replaceChildren(document.createTextNode(`Signed in as ${email} · `));
      const out = el("button", "linkbtn", "Sign out");
      out.type = "button";
      out.addEventListener("click", () => sb.auth.signOut());
      g.whoami.append(out);
    } else {
      g.whoami.hidden = true;
    }

    onReady(email, sb);
  }

  function showGate(msg) {
    g.app.hidden = true;
    g.gate.hidden = false;
    g.codeForm.hidden = true;
    g.emailForm.hidden = false;
    g.code.value = "";
    g.gateStatus.textContent = msg || "";
    if (onSignedOut) onSignedOut();
  }

  async function boot() {
    let cfg = {};
    try {
      cfg = await (await fetch("/api/config")).json();
    } catch {
      /* treat as local mode */
    }

    if (!cfg.supabase_url) {
      showApp(null); // local mode: no login
      return;
    }

    document.body.dataset.mode = "cloud";
    if (!window.supabase || !window.supabase.createClient) {
      showGate("Sign-in is unavailable — the auth library did not load. Reload to retry.");
      g.sendCode.disabled = true;
      return;
    }

    sb = window.supabase.createClient(cfg.supabase_url, cfg.supabase_key);

    g.emailForm.addEventListener("submit", async (e) => {
      e.preventDefault();
      const email = g.email.value.trim();
      if (!email) return;
      g.sendCode.disabled = true;
      g.gateStatus.textContent = "Sending code…";
      const { error } = await sb.auth.signInWithOtp({
        email,
        options: { shouldCreateUser: true },
      });
      g.sendCode.disabled = false;
      if (error) {
        g.gateStatus.textContent = error.message;
        return;
      }
      pendingEmail = email;
      g.codeEmail.textContent = email;
      g.emailForm.hidden = true;
      g.codeForm.hidden = false;
      g.gateStatus.textContent = "";
      g.code.focus();
    });

    g.codeForm.addEventListener("submit", async (e) => {
      e.preventDefault();
      const token = g.code.value.trim();
      if (!token || !pendingEmail) return;
      g.verifyCode.disabled = true;
      g.gateStatus.textContent = "Verifying…";
      const { error } = await sb.auth.verifyOtp({
        email: pendingEmail,
        token,
        type: "email",
      });
      g.verifyCode.disabled = false;
      if (error) {
        g.gateStatus.textContent = error.message;
        return;
      }
      // onAuthStateChange fires with the new session -> showApp()
    });

    g.codeBack.addEventListener("click", () => {
      pendingEmail = null;
      showGate("");
      g.email.focus();
    });

    sb.auth.onAuthStateChange((_event, session) => {
      if (session) showApp(session.user.email);
      else showGate("");
    });

    const {
      data: { session },
    } = await sb.auth.getSession();
    if (session) showApp(session.user.email);
    else showGate("");
  }

  boot();
};
})();
