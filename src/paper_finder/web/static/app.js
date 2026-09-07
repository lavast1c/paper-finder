"use strict";

const gateEl = document.getElementById("gate");
const appEl = document.getElementById("app");
const emailForm = document.getElementById("email-form");
const emailInput = document.getElementById("email");
const sendCodeBtn = document.getElementById("send-code");
const codeForm = document.getElementById("code-form");
const codeInput = document.getElementById("code");
const codeEmailEl = document.getElementById("code-email");
const verifyCodeBtn = document.getElementById("verify-code");
const codeBackBtn = document.getElementById("code-back");
const gateStatus = document.getElementById("gate-status");
const whoamiEl = document.getElementById("whoami");
const form = document.getElementById("search");
const input = document.getElementById("q");
const statusEl = document.getElementById("status");
const resultsEl = document.getElementById("results");
const corpusEl = document.getElementById("corpus");

const SESSION_NAMES = { s: "May/June", w: "Oct/Nov", m: "Feb/March" };

let controller = null;
let sb = null; // Supabase client in cloud mode; null in local mode
let ranInitial = false;
let pendingEmail = null; // email awaiting its one-time code

function setStatus(text) {
  statusEl.textContent = text;
}

function clearResults() {
  resultsEl.replaceChildren();
}

function el(tag, className, text) {
  const node = document.createElement(tag);
  if (className) node.className = className;
  if (text !== undefined) node.textContent = text;
  return node;
}

// --- search sources ------------------------------------------------------

async function localSearch(q) {
  const res = await fetch("/api/search?q=" + encodeURIComponent(q) + "&limit=10", {
    signal: controller.signal,
  });
  if (!res.ok) throw new Error("HTTP " + res.status);
  return res.json(); // { query, count, results: [result_payload...] }
}

function cloudRow(d) {
  const variant = d.paper == null ? "?" : `${d.paper}${d.variant ?? ""}`;
  const sname = SESSION_NAMES[d.session] || d.session;
  return {
    title: `${d.subject_name || "?"} · ${sname} ${d.year} · Paper ${variant} · Q${d.question_number}`,
    filename: d.filename,
    question_text: d.question_text,
    answer: d.answer_text,
    marks: d.marks,
    // no pdf_url — the deployed site has no PDFs
  };
}

async function cloudSearch(q) {
  const { data, error } = await sb.rpc("search_questions", { query: q, max_results: 5 });
  if (error) throw new Error(error.message || "search failed");
  return { count: data.length, results: data.map(cloudRow) };
}

function doSearch(q) {
  return sb ? cloudSearch(q) : localSearch(q);
}

// --- stats -------------------------------------------------------------

async function loadStats() {
  try {
    let s;
    if (sb) {
      const { data, error } = await sb.rpc("corpus_stats");
      if (error) return;
      s = data;
    } else {
      const res = await fetch("/api/stats");
      if (!res.ok) return;
      s = await res.json();
    }
    const bits = [
      `${Number(s.questions).toLocaleString()} questions`,
      `${s.question_papers} question papers`,
    ];
    if (s.subjects && s.subjects.length) bits.push(s.subjects.join(", "));
    corpusEl.textContent = bits.join(" · ");
  } catch {
    /* leave the corpus line blank; never block search */
  }
}

// --- rendering --------------------------------------------------------

// Structured (theory) papers label sub-parts "(a) … (b) … (i) … (ii) …" inline
// in the question, and "2(a)", "2(b)(i)" on their own line in the mark scheme.
// Split those out so each sub-part is visually separated.

const ROMAN = new Set(["i", "ii", "iii", "iv", "v", "vi", "vii", "viii", "ix", "x"]);
// a real part label is preceded by whitespace/start (so "1(a)" cross-refs don't match)
const PART_RE = /(?:^|\s)\((?<tok>[a-z]{1,3}|[ivx]{1,4})\)(?=\s|$)/g;
const MS_PART_RE = /^\d+\([a-z]\)(?:\([ivx]+\))*$/; // "2(a)", "2(b)(i)"
const MS_MARK_RE = /^\(?[ABCM]\d\)?$/; // "B1", "M1", "(A1)", "C1"

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
    box.textContent = text || "";
    return box;
  }
  box.classList.add("question--parts");
  for (const p of parts) {
    if (!p.label) {
      box.append(el("div", "qpart qpart--intro", p.text));
      continue;
    }
    const row = el("div", "qpart" + (p.roman ? " qpart--sub" : ""));
    row.append(el("span", "qpart-label", p.label));
    if (p.text) row.append(el("span", "qpart-text", p.text));
    else row.classList.add("qpart--group");
    box.append(row);
  }
  return box;
}

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
      group.append(el("span", "ms-mark", line));
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

async function run() {
  const q = input.value.trim();
  clearResults();

  if (!q) {
    setStatus("Type a few words from the question.");
    history.replaceState(null, "", location.pathname);
    return;
  }
  history.replaceState(null, "", "?q=" + encodeURIComponent(q));

  if (controller) controller.abort();
  controller = new AbortController();

  setStatus("Searching…");
  let data;
  try {
    data = await doSearch(q);
  } catch (err) {
    if (err.name === "AbortError") return;
    setStatus(`Search failed: ${err.message || err}`);
    return;
  }

  if (data.count === 0) {
    setStatus(`No match for “${q}”. Try a longer, more distinctive phrase.`);
    return;
  }
  setStatus(`${data.count} result${data.count === 1 ? "" : "s"}`);
  data.results.forEach((r, i) => resultsEl.append(renderResult(r, i + 1)));
}

form.addEventListener("submit", (e) => {
  e.preventDefault();
  run();
});

// --- boot ------------------------------------------------------------

function showApp(email) {
  gateEl.hidden = true;
  appEl.hidden = false;

  if (email) {
    whoamiEl.hidden = false;
    whoamiEl.replaceChildren(document.createTextNode(`Signed in as ${email} · `));
    const out = el("button", "linkbtn", "Sign out");
    out.type = "button";
    out.addEventListener("click", () => sb.auth.signOut());
    whoamiEl.append(out);
  } else {
    whoamiEl.hidden = true;
  }

  loadStats();
  if (!ranInitial) {
    ranInitial = true;
    const initial = new URLSearchParams(location.search).get("q");
    if (initial) {
      input.value = initial;
      run();
    }
  }
}

function showGate(msg) {
  appEl.hidden = true;
  gateEl.hidden = false;
  codeForm.hidden = true;
  emailForm.hidden = false;
  codeInput.value = "";
  gateStatus.textContent = msg || "";
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
    sendCodeBtn.disabled = true;
    return;
  }

  sb = window.supabase.createClient(cfg.supabase_url, cfg.supabase_key);

  emailForm.addEventListener("submit", async (e) => {
    e.preventDefault();
    const email = emailInput.value.trim();
    if (!email) return;
    sendCodeBtn.disabled = true;
    gateStatus.textContent = "Sending code…";
    const { error } = await sb.auth.signInWithOtp({
      email,
      options: { shouldCreateUser: true },
    });
    sendCodeBtn.disabled = false;
    if (error) {
      gateStatus.textContent = error.message;
      return;
    }
    pendingEmail = email;
    codeEmailEl.textContent = email;
    emailForm.hidden = true;
    codeForm.hidden = false;
    gateStatus.textContent = "";
    codeInput.focus();
  });

  codeForm.addEventListener("submit", async (e) => {
    e.preventDefault();
    const token = codeInput.value.trim();
    if (!token || !pendingEmail) return;
    verifyCodeBtn.disabled = true;
    gateStatus.textContent = "Verifying…";
    const { error } = await sb.auth.verifyOtp({
      email: pendingEmail,
      token,
      type: "email",
    });
    verifyCodeBtn.disabled = false;
    if (error) {
      gateStatus.textContent = error.message;
      return;
    }
    // onAuthStateChange fires with the new session -> showApp()
  });

  codeBackBtn.addEventListener("click", () => {
    pendingEmail = null;
    showGate("");
    emailInput.focus();
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
