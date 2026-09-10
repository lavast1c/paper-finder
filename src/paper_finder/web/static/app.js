"use strict";

// The search page. Shared helpers (DOM, highlighting, question/answer
// rendering, the auth gate) live in common.js as `window.PF` -- loaded first.

const { el } = PF;

const form = document.getElementById("search");
const input = document.getElementById("q");
const paperEl = document.getElementById("f-paper"); // multi-select dropdown: CIE variant numbers
const yearEl = document.getElementById("f-year"); // multi-select dropdown: years
const seasonEl = document.getElementById("f-season"); // multi-select dropdown: CIE session letters
const historyEl = document.getElementById("history"); // custom recent-search panel
const statusEl = document.getElementById("status");
const resultsEl = document.getElementById("results");
const corpusEl = document.getElementById("corpus");

// --- recent-search history --------------------------------------------------
//
// A small custom dropdown under the search box (not a native <datalist>, which
// renders like browser autofill and can't be styled). The list is kept in
// localStorage as a per-device convenience — cleared with the ✕ Clear row.

const HISTORY_KEY = "paper-finder.history";
const HISTORY_MAX = 8;

function loadHistory() {
  try {
    const raw = JSON.parse(localStorage.getItem(HISTORY_KEY) || "[]");
    return Array.isArray(raw) ? raw.filter((s) => typeof s === "string") : [];
  } catch {
    return [];
  }
}

function saveHistory(items) {
  try {
    localStorage.setItem(HISTORY_KEY, JSON.stringify(items));
  } catch {
    /* private mode / quota — history just won't persist */
  }
}

let historyItems = loadHistory();

function closeHistory() {
  if (!historyEl) return;
  historyEl.hidden = true;
  input.setAttribute("aria-expanded", "false");
}

function openHistory() {
  if (!historyEl || historyItems.length === 0 || input.value.trim()) {
    closeHistory();
    return;
  }
  historyEl.replaceChildren();
  historyItems.forEach((q) => {
    const item = el("button", "history-item", q);
    item.type = "button";
    item.setAttribute("role", "option");
    item.addEventListener("mousedown", (e) => {
      e.preventDefault(); // keep focus on the input; don't fire blur first
      input.value = q;
      closeHistory();
      run();
    });
    historyEl.append(item);
  });
  const clear = el("button", "history-clear", "✕ Clear recent searches");
  clear.type = "button";
  clear.addEventListener("mousedown", (e) => {
    e.preventDefault();
    historyItems = [];
    saveHistory(historyItems);
    closeHistory();
  });
  historyEl.append(clear);
  historyEl.hidden = false;
  input.setAttribute("aria-expanded", "true");
}

function rememberQuery(q) {
  historyItems = [q, ...historyItems.filter((s) => s.toLowerCase() !== q.toLowerCase())].slice(
    0,
    HISTORY_MAX,
  );
  saveHistory(historyItems);
}

let controller = null;
let sb = null; // Supabase client in cloud mode; null in local mode
let ranInitial = false;

function setStatus(text) {
  statusEl.textContent = text;
}

function clearResults() {
  resultsEl.replaceChildren();
}

// --- search sources ------------------------------------------------------

// The filter bar: Paper(s) = CIE variant number, Season(s) = session letter.
// Each is a multi-select dropdown of checkboxes; nothing ticked = no restriction
// on that axis.
function picked(groupEl) {
  return groupEl
    ? [...groupEl.querySelectorAll('input[type="checkbox"]:checked')].map((b) => b.value)
    : [];
}
function scope() {
  return { variants: picked(paperEl), years: picked(yearEl), sessions: picked(seasonEl) };
}

async function localSearch(q) {
  const s = scope();
  const params = new URLSearchParams({ q, limit: "10" });
  if (s.variants.length) params.set("variants", s.variants.join(","));
  if (s.years.length) params.set("years", s.years.join(","));
  if (s.sessions.length) params.set("sessions", s.sessions.join(","));
  const res = await fetch("/api/search?" + params.toString(), { signal: controller.signal });
  if (!res.ok) throw new Error("HTTP " + res.status);
  return res.json(); // { query, count, results: [result_payload...] }
}

async function cloudSearch(q) {
  const s = scope();
  const { data, error } = await sb.rpc("search_questions", {
    query: q,
    max_results: 5,
    years: s.years.map(Number),
    sessions: s.sessions,
    variants: s.variants.map(Number),
  });
  if (error) throw new Error(error.message || "search failed");
  return { count: data.length, results: data.map(PF.cloudRow) };
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
    corpusEl.textContent = bits.join(" · ");
  } catch {
    /* leave the corpus line blank; never block search */
  }
}

// --- run -------------------------------------------------------------

function resetSearch() {
  if (controller) controller.abort();
  PF.setQueryTerms("");
  clearResults();
  setStatus("");
  history.replaceState(null, "", location.pathname);
}

async function run() {
  const q = input.value.trim();
  if (!q) {
    resetSearch();
    return;
  }
  clearResults();
  PF.setQueryTerms(q);
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
  data.results.forEach((r, i) => resultsEl.append(PF.renderResult(r, i + 1)));
  rememberQuery(q);
}

form.addEventListener("submit", (e) => {
  e.preventDefault();
  run();
});

// native "search" event fires on the type=search ✕ clear button and on Esc;
// "input" covers typing the field empty. Either way: wipe the stale results.
function onQueryInput() {
  if (!input.value.trim()) {
    resetSearch();
    openHistory();
  } else {
    closeHistory();
  }
}
input.addEventListener("input", onQueryInput);
input.addEventListener("search", onQueryInput);
input.addEventListener("focus", openHistory);
input.addEventListener("blur", closeHistory);
input.addEventListener("keydown", (e) => {
  if (e.key === "Escape" && !historyEl.hidden) {
    e.stopPropagation();
    closeHistory();
  }
});

for (const group of [paperEl, yearEl, seasonEl]) {
  if (!group) continue;
  PF.multiSelect(group);
  group.addEventListener("change", () => {
    if (input.value.trim()) run();
  });
}

// --- boot ------------------------------------------------------------

function onReady(email, client) {
  sb = client;
  loadStats();
  historyItems = loadHistory();
  if (!ranInitial) {
    ranInitial = true; // onAuthStateChange fires more than once
    const initial = new URLSearchParams(location.search).get("q");
    if (initial) {
      input.value = initial;
      run();
    }
  }
}

PF.initAuth({ onReady });
