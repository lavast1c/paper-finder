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
function multiSelect(root) {
  if (root._ms) return root._ms;
  const toggle = root.querySelector(".ms-toggle");
  const panel = root.querySelector(".ms-panel");
  const valueEl = root.querySelector(".ms-value");
  const boxes = [...panel.querySelectorAll('input[type="checkbox"]')];
  const placeholder = root.dataset.placeholder || "Any";

  function values() {
    return boxes.filter((b) => b.checked).map((b) => b.value);
  }

  function paintLabel() {
    const picked = boxes.filter((b) => b.checked);
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
  function open() {
    if (!panel.hidden) return;
    panel.hidden = false;
    toggle.setAttribute("aria-expanded", "true");
    document.addEventListener("click", onDocClick, true);
    document.addEventListener("keydown", onKey, true);
  }
  function close() {
    if (panel.hidden) return;
    panel.hidden = true;
    toggle.setAttribute("aria-expanded", "false");
    document.removeEventListener("click", onDocClick, true);
    document.removeEventListener("keydown", onKey, true);
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
      for (const b of boxes) b.checked = want.has(b.value);
      paintLabel();
    },
    close,
  };
  root._ms = api;
  return api;
}
PF.multiSelect = multiSelect;

// The "Paper(s)" filter is really the MCQ-vs-theory split: CIE Physics Paper 1
// is multiple-choice, Paper 2 is structured/theory (there is no Paper 3 or 4).
// Ticked box values are the paper number; collapse them to the `kind` the
// search / browse endpoints take. Both (or neither) ticked = no restriction.
PF.paperKind = function paperKind(values) {
  const s = new Set(values || []);
  if (s.size !== 1) return "all";
  return s.has("1") ? "mcq" : "theory";
};

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
