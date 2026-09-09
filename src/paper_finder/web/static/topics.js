"use strict";

// The topic-browse page: pick one or more syllabus sections, get every
// past-paper question tagged with any of them as a flashcard deck -- one card at
// a time, answer hidden until revealed, arrows (or the keyboard) to move.
//
// Shared helpers live in common.js as window.PF (loaded first).

const { el } = PF;

const paperEl = document.getElementById("f-paper"); // CIE variant number
const seasonEl = document.getElementById("f-season"); // CIE session letter
const yearEl = document.getElementById("f-year");
const topicEl = document.getElementById("f-topic"); // syllabus section; deck stays hidden until one is picked
const clearAllBtn = document.getElementById("clear-all");
const statusEl = document.getElementById("status");
const cardEl = document.getElementById("card");
const prevBtn = document.getElementById("prev");
const nextBtn = document.getElementById("next");
const posEl = document.getElementById("pos");
const cardTitleEl = document.getElementById("card-title");
const cardFileEl = document.getElementById("card-file");
const cardMarksEl = document.getElementById("card-marks");
const cardImagesEl = document.getElementById("card-images");
const showTextBtn = document.getElementById("show-text");
const cardQuestionEl = document.getElementById("card-question");
const cardFigureEl = document.getElementById("card-figure");
const cardAnswerEl = document.getElementById("card-answer");
const corpusEl = document.getElementById("corpus");

const SHOWTEXT_KEY = "paper-finder.showtext"; // per-browser: keep the question text visible beside the image
const CROP_BUCKET = "question-crops";

const PAGE = 20; // deck rows fetched per request (keeps the cloud RPC cap intact)
const PREFETCH_WITHIN = 5; // fetch the next page when the cursor gets this close to the end
const YEARS = [2026, 2025, 2024]; // corpus range; a one-line change when it grows

let sb = null; // Supabase client in cloud mode; null in local mode
let topicList = []; // [{code, number, name, subsections, count}] — server is the source of valid codes
let selected = new Set(); // the picked topic (0 or 1 code); a Set keeps the deck/browse plumbing unchanged
// Paper(s) = CIE variant number, Season(s) = session letter. "" = no restriction.
const filters = { variant: "", season: "", year: "" };
let deck = [];
let total = 0;
let idx = 0;
let revealed = false;
let renderedImagesKey = null; // `${filename}#${qnum}` currently shown in #card-images; guards the swap
let showText = false;
try {
  showText = localStorage.getItem(SHOWTEXT_KEY) === "1";
} catch {
  /* private mode / storage blocked */
}
const signedCache = new Map(); // storage path -> { url, exp } (cloud mode signed URLs)
let loadingPage = false;
let deckToken = 0; // bumped on every new deck; a stale in-flight page load is dropped
let controller = null;

// --- URL state -----------------------------------------------------------

function readUrl() {
  const p = new URLSearchParams(location.search);
  const codes = (p.get("topics") || "").split(",").map((s) => s.trim()).filter(Boolean);
  filters.variant = p.get("variant") || "";
  filters.season = p.get("season") || "";
  filters.year = p.get("year") || "";
  const i = parseInt(p.get("i") || "0", 10);
  return { codes, i: Number.isFinite(i) && i > 0 ? i : 0 };
}

function writeUrl() {
  const p = new URLSearchParams();
  if (selected.size) p.set("topics", [...selected].join(","));
  if (filters.variant) p.set("variant", filters.variant);
  if (filters.season) p.set("season", filters.season);
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
  return filters.season ? [filters.season] : [];
}
function variantsParam() {
  return filters.variant ? [Number(filters.variant)] : [];
}
// local /api/* query string for the current scope filters
function scopeQuery(extra) {
  const p = new URLSearchParams(extra || {});
  if (filters.year) p.set("years", filters.year);
  if (filters.season) p.set("sessions", filters.season);
  if (filters.variant) p.set("variants", filters.variant);
  return p;
}

async function fetchCounts() {
  if (sb) {
    const { data, error } = await sb.rpc("topic_counts", {
      years: yearsParam(),
      sessions: sessionsParam(),
      variants: variantsParam(),
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
  const qs = scopeQuery().toString();
  const res = await fetch("/api/topics" + (qs ? "?" + qs : ""));
  if (!res.ok) throw new Error("HTTP " + res.status);
  return res.json(); // { topics, total, unlabelled }
}

async function fetchDeckPage(offset) {
  const codes = [...selected];
  if (sb) {
    const { data, error } = await sb.rpc("browse_questions", {
      codes,
      years: yearsParam(),
      sessions: sessionsParam(),
      variants: variantsParam(),
      max_results: PAGE,
      skip: offset,
    });
    if (error) throw new Error(error.message || "browse failed");
    return {
      count: data.length ? Number(data[0].total_count) : 0,
      results: data.map(PF.cloudRow),
    };
  }
  const p = scopeQuery({
    topics: codes.join(","),
    limit: String(PAGE),
    offset: String(offset),
  });
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
    corpusEl.textContent = bits.join(" · ");
  } catch {
    /* leave it blank */
  }
}

// --- topic dropdown -------------------------------------------------

// Rebuild the <option> list from the current (filter-scoped) counts, keeping the
// user's pick selected. A zero-count topic under the active filters is disabled.
function renderTopicOptions() {
  const current = [...selected][0] || "";
  topicEl.replaceChildren();
  topicEl.append(new Option("Choose a topic…", ""));
  for (const t of topicList) {
    const opt = new Option(`${t.number}. ${t.name} (${t.count})`, t.code);
    opt.disabled = t.count === 0 && t.code !== current;
    if (t.subsections && t.subsections.length) opt.title = t.subsections.join(" · ");
    topicEl.append(opt);
  }
  topicEl.value = current;
}

// --- the card ------------------------------------------------------

function setStatus(text) {
  statusEl.textContent = text || "";
}

function selectedNames() {
  return topicList.filter((t) => selected.has(t.code)).map((t) => t.name);
}

function cardKey(r) {
  return `${r.filename}#${r.question_number}`;
}

// The crop image URLs for a card, in page order. Local mode builds them straight
// off `crop_base`; cloud mode mints short-lived signed Storage URLs (batched,
// cached) since the bucket is private.
function cropUrls(r) {
  const stem = r.filename.replace(/\.pdf$/i, "");
  const names = [];
  for (let k = 1; k <= r.crop_count; k++) {
    names.push(`q${String(r.question_number).padStart(2, "0")}_p${k}.png`);
  }
  if (!sb) {
    return Promise.resolve(names.map((n) => `${r.crop_base}/${n}`));
  }
  return signedUrls(names.map((n) => `${stem}/${n}`));
}

async function signedUrls(paths) {
  const now = Date.now();
  const stale = paths.filter((p) => {
    const c = signedCache.get(p);
    return !c || c.exp < now + 60000;
  });
  if (stale.length) {
    const { data, error } = await sb.storage.from(CROP_BUCKET).createSignedUrls(stale, 3600);
    if (error) throw new Error(error.message || "signed URL request failed");
    for (const row of data || []) {
      if (row && row.signedUrl && !row.error) {
        signedCache.set(row.path, { url: row.signedUrl, exp: now + 3600 * 1000 });
      }
    }
  }
  return paths.map((p) => (signedCache.get(p) || {}).url).filter(Boolean);
}

// Drop back to the extracted text for this one card -- a crop failed to load, or
// none resolved. Not persisted; the next card tries its images again.
function fallbackToText(r) {
  renderedImagesKey = null;
  cardImagesEl.replaceChildren();
  cardImagesEl.hidden = true;
  showTextBtn.hidden = true;
  cardQuestionEl.hidden = false;
  cardQuestionEl.replaceChildren(PF.questionBlock(r.question_text));
  cardFigureEl.hidden = !r.has_figure;
}

async function renderCropImages(r) {
  const key = cardKey(r);
  cardImagesEl.replaceChildren();
  let urls;
  try {
    urls = await cropUrls(r);
  } catch {
    urls = [];
  }
  if (renderedImagesKey !== key) return; // navigated away while awaiting
  if (!urls.length) {
    fallbackToText(r);
    return;
  }
  urls.forEach((u, i) => {
    const img = el("img", "card-image");
    // Eager, not lazy: the crop *is* the card, and the card is often below the
    // fold on load -- a lazy image there stays 0-height and never enters view.
    img.decoding = "async";
    img.alt = `${r.title} — image ${i + 1} of ${urls.length}`;
    img.addEventListener("error", () => {
      if (renderedImagesKey === key) fallbackToText(r);
    });
    img.src = u;
    cardImagesEl.append(img);
  });
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

  const hasCrops = r.crop_count > 0;
  const key = cardKey(r);
  if (hasCrops) {
    if (renderedImagesKey !== key) {
      renderedImagesKey = key;
      renderCropImages(r); // async; swaps in <img> nodes, or calls fallbackToText
    }
    cardImagesEl.hidden = false;
    showTextBtn.hidden = false;
    showTextBtn.textContent = showText ? "Hide text" : "Show text";
  } else {
    renderedImagesKey = null;
    cardImagesEl.replaceChildren();
    cardImagesEl.hidden = true;
    showTextBtn.hidden = true;
  }

  const textVisible = !hasCrops || showText;
  cardQuestionEl.hidden = !textVisible;
  if (textVisible) {
    cardQuestionEl.replaceChildren(PF.questionBlock(r.question_text));
  }
  // when the crop is shown the figure lives in it; the note only helps the text view
  cardFigureEl.hidden = !r.has_figure || hasCrops;

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
  renderTopicOptions();

  if (controller) controller.abort();
  controller = new AbortController();
  const token = ++deckToken;
  deck = [];
  total = 0;
  loadingPage = false;

  // counts first (dropdown labels), then the deck -- both under the current filters
  try {
    const counts = await fetchCounts();
    if (token !== deckToken) return;
    topicList = counts.topics;
    // the server's topic list is the authority on valid codes: a hand-edited
    // ?topics= can never reach the DOM or an RPC
    const valid = new Set(topicList.map((t) => t.code));
    for (const code of [...selected]) if (!valid.has(code)) selected.delete(code);
    renderTopicOptions();
  } catch {
    /* keep the last-known counts */
  }

  if (selected.size === 0) {
    cardEl.hidden = true;
    setStatus("Choose a topic to start revising.");
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

paperEl.addEventListener("change", () => {
  filters.variant = paperEl.value;
  idx = 0;
  refresh();
});
seasonEl.addEventListener("change", () => {
  filters.season = seasonEl.value;
  idx = 0;
  refresh();
});
yearEl.addEventListener("change", () => {
  filters.year = yearEl.value;
  idx = 0;
  refresh();
});
topicEl.addEventListener("change", () => {
  selected.clear();
  if (topicEl.value) selected.add(topicEl.value);
  idx = 0;
  refresh();
});
clearAllBtn.addEventListener("click", () => {
  selected.clear();
  filters.variant = "";
  filters.season = "";
  filters.year = "";
  paperEl.value = "";
  seasonEl.value = "";
  yearEl.value = "";
  topicEl.value = "";
  idx = 0;
  refresh();
});
prevBtn.addEventListener("click", () => go(-1));
nextBtn.addEventListener("click", () => go(1));

showTextBtn.addEventListener("click", () => {
  showText = !showText;
  try {
    localStorage.setItem(SHOWTEXT_KEY, showText ? "1" : "");
  } catch {
    /* private mode / storage blocked */
  }
  renderCard();
});

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
  paperEl.value = filters.variant;
  seasonEl.value = filters.season;
  yearEl.value = filters.year;
  idx = i;
  selected = new Set(codes.slice(0, 1)); // single-select now; pruned in refresh()
  refresh();
}

PF.initAuth({ onReady });
