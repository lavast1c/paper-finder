"use strict";

// The topic-browse page: pick one or more syllabus sections, get every
// past-paper question tagged with any of them as a flashcard deck -- one card at
// a time, answer hidden until revealed, arrows (or the keyboard) to move.
//
// Shared helpers live in common.js as window.PF (loaded first).

const { el } = PF;

const chipsEl = document.getElementById("topic-chips");
const kindEl = document.getElementById("kind");
const sessionEl = document.getElementById("session");
const yearEl = document.getElementById("year");
const clearAllBtn = document.getElementById("clear-all");
const statusEl = document.getElementById("status");
const cardEl = document.getElementById("card");
const prevBtn = document.getElementById("prev");
const nextBtn = document.getElementById("next");
const posEl = document.getElementById("pos");
const cardTitleEl = document.getElementById("card-title");
const cardFileEl = document.getElementById("card-file");
const cardMarksEl = document.getElementById("card-marks");
const cardQuestionEl = document.getElementById("card-question");
const cardFigureEl = document.getElementById("card-figure");
const cardAnswerEl = document.getElementById("card-answer");
const corpusEl = document.getElementById("corpus");

const PAGE = 20; // deck rows fetched per request (keeps the cloud RPC cap intact)
const PREFETCH_WITHIN = 5; // fetch the next page when the cursor gets this close to the end
const YEARS = [2026, 2025, 2024]; // corpus range; a one-line change when it grows

let sb = null; // Supabase client in cloud mode; null in local mode
let topicList = []; // [{code, number, name, subsections, count}] — server is the source of valid codes
let selected = new Set();
const filters = { kind: "all", session: "", year: "" };
let deck = [];
let total = 0;
let idx = 0;
let revealed = false;
let loadingPage = false;
let deckToken = 0; // bumped on every new deck; a stale in-flight page load is dropped
let controller = null;

// --- URL state -----------------------------------------------------------

function readUrl() {
  const p = new URLSearchParams(location.search);
  const codes = (p.get("topics") || "").split(",").map((s) => s.trim()).filter(Boolean);
  filters.kind = p.get("kind") || "all";
  filters.session = p.get("session") || "";
  filters.year = p.get("year") || "";
  const i = parseInt(p.get("i") || "0", 10);
  return { codes, i: Number.isFinite(i) && i > 0 ? i : 0 };
}

function writeUrl() {
  const p = new URLSearchParams();
  if (selected.size) p.set("topics", [...selected].join(","));
  if (filters.kind !== "all") p.set("kind", filters.kind);
  if (filters.session) p.set("session", filters.session);
  if (filters.year) p.set("year", filters.year);
  if (idx > 0) p.set("i", String(idx));
  const qs = p.toString();
  history.replaceState(null, "", qs ? "?" + qs : location.pathname);
}

// --- data sources ------------------------------------------------------

function yearsParam() {
  return filters.year ? [Number(filters.year)] : [];
}
function sessionsParam() {
  return filters.session ? [filters.session] : [];
}

async function fetchCounts() {
  if (sb) {
    const { data, error } = await sb.rpc("topic_counts", {
      kind: filters.kind,
      years: yearsParam(),
      sessions: sessionsParam(),
    });
    if (error) throw new Error(error.message || "topic counts failed");
    return {
      topics: data.map((r) => ({
        code: r.code,
        number: r.number,
        name: r.name,
        subsections: r.subsections || [],
        count: Number(r.count),
      })),
      total: data.reduce((n, r) => n + Number(r.count), 0),
    };
  }
  const p = new URLSearchParams({ kind: filters.kind });
  if (filters.year) p.set("years", filters.year);
  if (filters.session) p.set("sessions", filters.session);
  const res = await fetch("/api/topics?" + p.toString());
  if (!res.ok) throw new Error("HTTP " + res.status);
  return res.json(); // { topics, total, unlabelled }
}

async function fetchDeckPage(offset) {
  const codes = [...selected];
  if (sb) {
    const { data, error } = await sb.rpc("browse_questions", {
      codes,
      kind: filters.kind,
      years: yearsParam(),
      sessions: sessionsParam(),
      max_results: PAGE,
      skip: offset,
    });
    if (error) throw new Error(error.message || "browse failed");
    return {
      count: data.length ? Number(data[0].total_count) : 0,
      results: data.map(PF.cloudRow),
    };
  }
  const p = new URLSearchParams({
    topics: codes.join(","),
    kind: filters.kind,
    limit: String(PAGE),
    offset: String(offset),
  });
  if (filters.year) p.set("years", filters.year);
  if (filters.session) p.set("sessions", filters.session);
  const res = await fetch("/api/browse?" + p.toString(), {
    signal: controller ? controller.signal : undefined,
  });
  if (!res.ok) throw new Error("HTTP " + res.status);
  return res.json(); // { topics, count, offset, results }
}

// --- corpus line -----------------------------------------------------

async function loadCorpusLine() {
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
    /* leave it blank */
  }
}

// --- chips -----------------------------------------------------------

function renderChips() {
  chipsEl.replaceChildren();
  for (const t of topicList) {
    const on = selected.has(t.code);
    const chip = el("button", "chip");
    chip.type = "button";
    chip.setAttribute("aria-pressed", on ? "true" : "false");
    chip.disabled = t.count === 0 && !on;
    if (t.subsections && t.subsections.length) chip.title = t.subsections.join(" · ");
    chip.append(el("span", "chip-num", String(t.number)));
    chip.append(el("span", "chip-name", t.name));
    chip.append(el("span", "chip-count", String(t.count)));
    chip.addEventListener("click", () => {
      if (selected.has(t.code)) selected.delete(t.code);
      else selected.add(t.code);
      idx = 0;
      refresh();
    });
    chipsEl.append(chip);
  }
}

// --- the card ------------------------------------------------------

function setStatus(text) {
  statusEl.textContent = text || "";
}

function selectedNames() {
  return topicList.filter((t) => selected.has(t.code)).map((t) => t.name);
}

function renderCard() {
  const r = deck[idx];
  if (!r) return;
  posEl.textContent = `${idx + 1} / ${total}`;
  prevBtn.disabled = idx === 0;
  nextBtn.disabled = idx >= total - 1;

  cardTitleEl.textContent = r.title;
  cardFileEl.textContent = r.filename;
  if (r.marks) {
    cardMarksEl.hidden = false;
    cardMarksEl.textContent = `${r.marks} mark${r.marks === 1 ? "" : "s"}`;
  } else {
    cardMarksEl.hidden = true;
  }

  cardQuestionEl.replaceChildren(PF.questionBlock(r.question_text));
  cardFigureEl.hidden = !r.has_figure;

  cardAnswerEl.replaceChildren();
  if (revealed) {
    cardAnswerEl.append(PF.answerBlock(r.answer));
  } else {
    const btn = el("button", null, "Reveal answer");
    btn.type = "button";
    btn.id = "reveal";
    btn.addEventListener("click", reveal);
    cardAnswerEl.append(btn);
  }
}

function reveal() {
  if (revealed || !deck[idx]) return;
  revealed = true;
  renderCard();
}

// Walk forward one page at a time until the deck covers `target` -- used when a
// deep-link ?i= lands past the first page.
async function ensureLoaded(target, token) {
  while (deck.length <= target && deck.length < total) {
    loadingPage = true;
    let data;
    try {
      data = await fetchDeckPage(deck.length);
    } finally {
      if (token === deckToken) loadingPage = false;
    }
    if (token !== deckToken) return;
    if (!data.results.length) break;
    deck = deck.concat(data.results);
    total = data.count;
  }
}

function maybePrefetch() {
  if (loadingPage || deck.length >= total) return;
  if (idx < deck.length - PREFETCH_WITHIN) return;
  const token = deckToken;
  const offset = deck.length;
  loadingPage = true;
  fetchDeckPage(offset)
    .then((data) => {
      if (token !== deckToken) return; // deck changed under us
      deck = deck.concat(data.results);
      total = data.count;
      renderCard();
    })
    .catch(() => {})
    .finally(() => {
      if (token === deckToken) loadingPage = false;
    });
}

async function go(delta) {
  const target = Math.min(Math.max(idx + delta, 0), Math.max(total - 1, 0));
  if (target === idx) return;
  idx = target;
  revealed = false;
  const token = deckToken;
  if (idx >= deck.length) {
    setStatus("Loading…");
    await ensureLoaded(idx, token);
    if (token !== deckToken) return;
    setStatus("");
    if (idx >= deck.length) idx = deck.length - 1;
  }
  renderCard();
  maybePrefetch();
  writeUrl();
}

// --- refresh (counts + deck together) --------------------------------

async function refresh() {
  writeUrl();
  renderChips();

  if (controller) controller.abort();
  controller = new AbortController();
  const token = ++deckToken;
  deck = [];
  total = 0;
  loadingPage = false;

  // counts first (chip badges), then the deck -- both under the current filters
  try {
    const counts = await fetchCounts();
    if (token !== deckToken) return;
    topicList = counts.topics;
    // the server's topic list is the authority on valid codes: a hand-edited
    // ?topics= can never reach the DOM or an RPC
    const valid = new Set(topicList.map((t) => t.code));
    for (const code of [...selected]) if (!valid.has(code)) selected.delete(code);
    renderChips();
  } catch {
    /* keep the last-known counts */
  }

  if (selected.size === 0) {
    cardEl.hidden = true;
    setStatus("Pick one or more topics above.");
    return;
  }

  setStatus("Loading…");
  let data;
  try {
    data = await fetchDeckPage(0);
  } catch (err) {
    if (err && err.name === "AbortError") return;
    if (token !== deckToken) return;
    cardEl.hidden = true;
    setStatus(`Could not load questions: ${(err && err.message) || err}`);
    return;
  }
  if (token !== deckToken) return;

  deck = data.results;
  total = data.count;

  if (total === 0) {
    cardEl.hidden = true;
    const names = selectedNames();
    setStatus(`No questions tagged ${names.join(" or ")} yet.`);
    return;
  }

  if (idx > total - 1) idx = total - 1;
  await ensureLoaded(idx, token);
  if (token !== deckToken) return;
  if (idx >= deck.length) idx = deck.length - 1;

  revealed = false;
  setStatus("");
  cardEl.hidden = false;
  renderCard();
  maybePrefetch();
  writeUrl();
}

// --- wiring --------------------------------------------------------

kindEl.addEventListener("change", () => {
  filters.kind = kindEl.value || "all";
  idx = 0;
  refresh();
});
sessionEl.addEventListener("change", () => {
  filters.session = sessionEl.value;
  idx = 0;
  refresh();
});
yearEl.addEventListener("change", () => {
  filters.year = yearEl.value;
  idx = 0;
  refresh();
});
clearAllBtn.addEventListener("click", () => {
  selected.clear();
  filters.kind = "all";
  filters.session = "";
  filters.year = "";
  kindEl.value = "all";
  sessionEl.value = "";
  yearEl.value = "";
  idx = 0;
  refresh();
});
prevBtn.addEventListener("click", () => go(-1));
nextBtn.addEventListener("click", () => go(1));

document.addEventListener("keydown", (e) => {
  const tag = (e.target && e.target.tagName) || "";
  if (tag === "SELECT" || tag === "INPUT" || tag === "TEXTAREA") return;
  if (cardEl.hidden) return;
  if (e.key === "ArrowLeft") {
    e.preventDefault();
    go(-1);
  } else if (e.key === "ArrowRight") {
    e.preventDefault();
    go(1);
  } else if (e.key === " " || e.key === "Spacebar") {
    e.preventDefault();
    reveal();
  }
});

// --- boot ---------------------------------------------------------

for (const y of YEARS) {
  yearEl.append(new Option(String(y), String(y)));
}

let ranInitial = false;

function onReady(email, client) {
  sb = client;
  loadCorpusLine();
  if (ranInitial) return;
  ranInitial = true; // onAuthStateChange fires more than once

  const { codes, i } = readUrl();
  kindEl.value = filters.kind;
  sessionEl.value = filters.session;
  yearEl.value = filters.year;
  idx = i;
  selected = new Set(codes); // pruned against the server's topic list in refresh()
  refresh();
}

PF.initAuth({ onReady });
