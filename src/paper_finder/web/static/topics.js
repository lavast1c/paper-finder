"use strict";

// The topic-browse page: pick one or more syllabus sections, get every
// past-paper question tagged with any of them as a flashcard deck -- one card at
// a time, answer hidden until revealed, arrows (or the keyboard) to move.
//
// Shared helpers live in common.js as window.PF (loaded first).

const { el } = PF;

const subjectEl = document.getElementById("subject"); // Physics / Further Pure Maths / Further Prob & Stats
const fbPaperEl = document.getElementById("fb-paper"); // Paper(s) field wrapper — hidden off Physics
const paperEl = document.getElementById("f-paper"); // multi-select dropdown: Paper 1 (MCQ) / Paper 2 (theory)
const seasonEl = document.getElementById("f-season"); // multi-select dropdown: CIE session letters
const yearEl = document.getElementById("f-year"); // multi-select dropdown: years
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
const revealBtn = document.getElementById("reveal");
const qZoombarEl = document.getElementById("q-zoombar");
const aZoombarEl = document.getElementById("a-zoombar");
const fsToggleBtn = document.getElementById("fullscreen-toggle");
const cardImagesEl = document.getElementById("card-images");
const showTextBtn = document.getElementById("show-text");
const cardQuestionEl = document.getElementById("card-question");
const cardFigureEl = document.getElementById("card-figure");
const cardAnswerEl = document.getElementById("card-answer");
const answerImagesEl = document.getElementById("answer-images");
const answerShowTextBtn = document.getElementById("answer-show-text");
const answerBodyEl = document.getElementById("answer-body");
const corpusEl = document.getElementById("corpus");

const SHOWTEXT_KEY = "paper-finder.showtext"; // per-browser: keep the question text visible beside the image
const SHOWANSWERTEXT_KEY = "paper-finder.showanswertext"; // same, for the revealed mark scheme
const QZOOM_KEY = "paper-finder.qzoom"; // per-browser question-crop zoom level
const AZOOM_KEY = "paper-finder.azoom"; // per-browser mark-scheme-crop zoom level
const ZOOM_MIN = 0.5;
const ZOOM_MAX = 3;
const ZOOM_STEP = 0.25;
const CROP_BUCKET = "question-crops";

const PAGE = 20; // deck rows fetched per request (keeps the cloud RPC cap intact)
const PREFETCH_WITHIN = 5; // fetch the next page when the cursor gets this close to the end

const DEFAULT_SUBJECT = "Physics";
let subject = DEFAULT_SUBJECT; // one subject at a time; its taxonomy fills the Topic dropdown

let sb = null; // Supabase client in cloud mode; null in local mode
let topicList = []; // [{code, number, name, subsections, count}] — server is the source of valid codes
let selected = new Set(); // the picked topic (0 or 1 code); a Set keeps the deck/browse plumbing unchanged
// Multi-select scope filters (each a .multiselect dropdown). Paper(s) = paper
// number ("1" = MCQ, "2" = theory), Season(s) = session letters, Year(s) =
// years. An empty array = no restriction on that axis.
const filters = { papers: [], seasons: [], years: [] };

const csv = (s) => (s || "").split(",").map((x) => x.trim()).filter(Boolean);
let deck = [];
let total = 0;
let idx = 0;
let revealed = false;
let renderedImagesKey = null; // `${filename}#${qnum}` currently shown in #card-images; guards the swap
let renderedAnswerKey = null; // same, for #answer-images (separate slot -- the two must not share a guard)
let showText = false;
let showAnswerText = false;
try {
  showText = localStorage.getItem(SHOWTEXT_KEY) === "1";
  showAnswerText = localStorage.getItem(SHOWANSWERTEXT_KEY) === "1";
} catch {
  /* private mode / storage blocked */
}

function readZoom(key) {
  try {
    const z = parseFloat(localStorage.getItem(key));
    if (z >= ZOOM_MIN && z <= ZOOM_MAX) return z;
  } catch {
    /* private mode / storage blocked */
  }
  return 1;
}
const signedCache = new Map(); // storage path -> { url, exp } (cloud mode signed URLs)
let loadingPage = false;
let deckToken = 0; // bumped on every new deck; a stale in-flight page load is dropped
let controller = null;

// --- URL state -----------------------------------------------------------

function readUrl() {
  const p = new URLSearchParams(location.search);
  const codes = csv(p.get("topics"));
  const wantSubject = p.get("subject");
  if (subjectEl && wantSubject && [...subjectEl.options].some((o) => o.value === wantSubject)) {
    subject = wantSubject;
  }
  filters.papers = csv(p.get("paper"));
  filters.seasons = csv(p.get("season"));
  filters.years = csv(p.get("year"));
  const i = parseInt(p.get("i") || "0", 10);
  return { codes, i: Number.isFinite(i) && i > 0 ? i : 0 };
}

function writeUrl() {
  const p = new URLSearchParams();
  if (selected.size) p.set("topics", [...selected].join(","));
  if (subject !== DEFAULT_SUBJECT) p.set("subject", subject);
  if (filters.papers.length) p.set("paper", filters.papers.join(","));
  if (filters.seasons.length) p.set("season", filters.seasons.join(","));
  if (filters.years.length) p.set("year", filters.years.join(","));
  if (idx > 0) p.set("i", String(idx));
  const qs = p.toString();
  history.replaceState(null, "", qs ? "?" + qs : location.pathname);
}

// --- data sources ------------------------------------------------------

function yearsParam() {
  return filters.years.map(Number);
}
function sessionsParam() {
  return filters.seasons.slice();
}
function kindParam() {
  // the MCQ-vs-theory split is Physics-only; off Physics the field is hidden
  return subject === DEFAULT_SUBJECT ? PF.paperKind(filters.papers) : "all";
}
// local /api/* query string for the current scope filters
function scopeQuery(extra) {
  const p = new URLSearchParams(extra || {});
  const kind = kindParam();
  if (kind !== "all") p.set("kind", kind);
  if (filters.years.length) p.set("years", filters.years.join(","));
  if (filters.seasons.length) p.set("sessions", filters.seasons.join(","));
  p.set("subject", subject);
  return p;
}

async function fetchCounts() {
  if (sb) {
    const { data, error } = await sb.rpc("topic_counts", {
      kind: kindParam(),
      years: yearsParam(),
      sessions: sessionsParam(),
      subjects: [subject],
      topic_subject: subject, // restricts the returned topic list to this subject's taxonomy
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
      kind: kindParam(),
      years: yearsParam(),
      sessions: sessionsParam(),
      subjects: [subject],
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

// The mark-scheme crop URLs for a revealed card, in page order. They live under
// the `ms` stem (same paper, `_qp_` -> `_ms_`); local builds them off
// `ms_crop_base`, cloud mints signed Storage URLs from the same private bucket.
function answerCropUrls(r) {
  const msStem = r.filename.replace(/_qp_/i, "_ms_").replace(/\.pdf$/i, "");
  const names = [];
  for (let k = 1; k <= r.answer_crop_count; k++) {
    names.push(`q${String(r.question_number).padStart(2, "0")}_p${k}.png`);
  }
  if (!sb) {
    return Promise.resolve(names.map((n) => `${r.ms_crop_base}/${n}`));
  }
  return signedUrls(names.map((n) => `${msStem}/${n}`));
}

// A mark-scheme crop failed to load, or none resolved -> show the extracted text
// for this one card. Not persisted; the next reveal tries its images again.
function answerFallbackToText(r) {
  renderedAnswerKey = null;
  answerImagesEl.replaceChildren();
  answerImagesEl.hidden = true;
  answerShowTextBtn.hidden = true;
  answerBodyEl.replaceChildren(PF.answerBlock(r.answer));
}

async function renderAnswerImages(r) {
  const key = cardKey(r);
  answerImagesEl.replaceChildren();
  let urls;
  try {
    urls = await answerCropUrls(r);
  } catch {
    urls = [];
  }
  if (renderedAnswerKey !== key) return; // navigated away while awaiting
  if (!urls.length) {
    answerFallbackToText(r);
    return;
  }
  urls.forEach((u, i) => {
    const img = el("img", "card-image");
    img.decoding = "async";
    img.alt = `${r.title} — mark scheme ${i + 1} of ${urls.length}`;
    img.addEventListener("error", () => {
      if (renderedAnswerKey === key) answerFallbackToText(r);
    });
    img.src = u;
    answerImagesEl.append(img);
  });
}

function renderCard() {
  const r = deck[idx];
  if (!r) return;
  posEl.textContent = `${idx + 1} / ${total}`;
  prevBtn.disabled = idx === 0;
  nextBtn.disabled = idx >= total - 1;
  // drives the fullscreen split: question left, mark scheme right once revealed
  cardEl.classList.toggle("is-revealed", revealed);

  cardTitleEl.textContent = r.title;
  cardFileEl.textContent = r.filename;
  revealBtn.textContent = revealed ? "Hide answer" : "Reveal answer";
  revealBtn.setAttribute("aria-expanded", revealed ? "true" : "false");
  cardAnswerEl.hidden = !revealed;
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
  qZoombarEl.hidden = !hasCrops; // the zoom control only makes sense with a crop

  const textVisible = !hasCrops || showText;
  cardQuestionEl.hidden = !textVisible;
  if (textVisible) {
    cardQuestionEl.replaceChildren(PF.questionBlock(r.question_text));
  }
  // when the crop is shown the figure lives in it; the note only helps the text view
  cardFigureEl.hidden = !r.has_figure || hasCrops;

  // --- answer: hidden until the #card-head "Reveal answer" toggle is pressed,
  // then either the mark-scheme crop (theory questions with a crop) + a "Show
  // text" toggle, or the text answer. The toggle also hides it again.
  answerBodyEl.replaceChildren();
  if (!revealed) {
    renderedAnswerKey = null;
    answerImagesEl.replaceChildren();
    answerImagesEl.hidden = true;
    answerShowTextBtn.hidden = true;
    aZoombarEl.hidden = true;
    return;
  }

  aZoombarEl.hidden = r.answer_crop_count === 0;
  if (r.answer_crop_count > 0) {
    const akey = cardKey(r);
    if (renderedAnswerKey !== akey) {
      renderedAnswerKey = akey;
      renderAnswerImages(r); // async; swaps in <img> nodes, or calls answerFallbackToText
    }
    answerImagesEl.hidden = false;
    answerShowTextBtn.hidden = false;
    answerShowTextBtn.textContent = showAnswerText ? "Hide text" : "Show text";
    if (showAnswerText) answerBodyEl.append(PF.answerBlock(r.answer));
  } else {
    renderedAnswerKey = null;
    answerImagesEl.replaceChildren();
    answerImagesEl.hidden = true;
    answerShowTextBtn.hidden = true;
    answerBodyEl.append(PF.answerBlock(r.answer));
  }
}

function toggleAnswer() {
  if (!deck[idx]) return;
  revealed = !revealed;
  renderCard();
}

// --- zoom: one control per crop column. Each scales its own `.card-images`
// via an `--img-zoom` custom property; the crop <img>s (rebuilt on every card)
// inherit it, and the inline style survives a `replaceChildren()`, so it only
// runs on a change. `#q-zoombar` drives the question, `#a-zoombar` the scheme.
function makeZoom({ barEl, imagesEl, storeKey }) {
  let z = readZoom(storeKey);
  const outBtn = barEl.querySelector('[id$="-zoom-out"]');
  const inBtn = barEl.querySelector('[id$="-zoom-in"]');
  const levelEl = barEl.querySelector('[id$="-zoom-level"]');
  function apply() {
    z = Math.min(ZOOM_MAX, Math.max(ZOOM_MIN, Math.round(z * 20) / 20));
    imagesEl.style.setProperty("--img-zoom", String(z));
    levelEl.textContent = Math.round(z * 100) + "%";
    outBtn.disabled = z <= ZOOM_MIN;
    inBtn.disabled = z >= ZOOM_MAX;
    try {
      localStorage.setItem(storeKey, String(z));
    } catch {
      /* private mode / storage blocked */
    }
  }
  function bump(delta) {
    z += delta;
    apply();
  }
  function reset() {
    z = 1;
    apply();
  }
  outBtn.addEventListener("click", () => bump(-ZOOM_STEP));
  inBtn.addEventListener("click", () => bump(ZOOM_STEP));
  levelEl.addEventListener("click", reset);
  apply();
  return { bump, reset };
}
const qZoom = makeZoom({ barEl: qZoombarEl, imagesEl: cardImagesEl, storeKey: QZOOM_KEY });
const aZoom = makeZoom({ barEl: aZoombarEl, imagesEl: answerImagesEl, storeKey: AZOOM_KEY });

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

// --- fullscreen ---------------------------------------------------
// Blow the current card up to fill the screen. The whole #card subtree goes
// fullscreen, so Prev / Next (buttons or ← →) and Reveal keep working; once
// revealed, `.is-revealed` splits it into question (left) + mark scheme (right).

function fsElement() {
  return document.fullscreenElement || document.webkitFullscreenElement || null;
}
function inFullscreen() {
  return fsElement() === cardEl;
}
function enterFullscreen() {
  const req = cardEl.requestFullscreen || cardEl.webkitRequestFullscreen;
  if (!req) return;
  try {
    const p = req.call(cardEl);
    if (p && p.catch) p.catch(() => {});
  } catch {
    /* rejected (no user gesture / blocked) */
  }
}
function exitFullscreen() {
  const ex = document.exitFullscreen || document.webkitExitFullscreen;
  if (!ex) return;
  try {
    const p = ex.call(document);
    if (p && p.catch) p.catch(() => {});
  } catch {
    /* ignore */
  }
}
function toggleFullscreen() {
  if (cardEl.hidden) return;
  if (inFullscreen()) exitFullscreen();
  else enterFullscreen();
}
function syncFullscreenUI() {
  const on = inFullscreen();
  cardEl.classList.toggle("card--fs", on);
  if (fsToggleBtn) {
    fsToggleBtn.setAttribute("aria-label", on ? "Exit fullscreen" : "Enter fullscreen");
    fsToggleBtn.setAttribute("aria-pressed", on ? "true" : "false");
    fsToggleBtn.title = on ? "Exit fullscreen (f or Esc)" : "Fullscreen (press f)";
  }
}
if (fsToggleBtn) fsToggleBtn.addEventListener("click", toggleFullscreen);
document.addEventListener("fullscreenchange", syncFullscreenUI);
document.addEventListener("webkitfullscreenchange", syncFullscreenUI);

// --- wiring --------------------------------------------------------

const SCOPE_GROUPS = [
  [paperEl, "papers"],
  [yearEl, "years"],
  [seasonEl, "seasons"],
];

// Push the current `filters` arrays back into the dropdowns (deep-link restore).
function syncToggleUI() {
  for (const [group, key] of SCOPE_GROUPS) {
    if (group && group._ms) group._ms.setValues(filters[key]);
  }
}

// A .multiselect dropdown -> the `filters[key]` array. The checkboxes are real,
// so their `change` bubbles to the root; read every ticked box off it.
function wireScopeGroup(groupEl, key) {
  if (!groupEl) return;
  PF.multiSelect(groupEl);
  groupEl.addEventListener("change", () => {
    filters[key] = [...groupEl.querySelectorAll('input[type="checkbox"]:checked')].map(
      (b) => b.value,
    );
    idx = 0;
    refresh();
  });
}
for (const [group, key] of SCOPE_GROUPS) wireScopeGroup(group, key);

function syncPaperFieldVisibility() {
  if (fbPaperEl) fbPaperEl.hidden = subject !== DEFAULT_SUBJECT;
}

if (subjectEl) {
  subjectEl.addEventListener("change", () => {
    subject = subjectEl.value;
    syncPaperFieldVisibility();
    // the picked topic and any Paper(s) pick belong to the old subject
    selected.clear();
    topicEl.value = "";
    if (subject !== DEFAULT_SUBJECT) {
      filters.papers = [];
      if (paperEl && paperEl._ms) paperEl._ms.setValues([]);
    }
    idx = 0;
    refresh();
  });
}

topicEl.addEventListener("change", () => {
  selected.clear();
  if (topicEl.value) selected.add(topicEl.value);
  idx = 0;
  refresh();
});
clearAllBtn.addEventListener("click", () => {
  selected.clear();
  filters.papers = [];
  filters.seasons = [];
  filters.years = [];
  topicEl.value = "";
  syncToggleUI();
  idx = 0;
  refresh();
});
prevBtn.addEventListener("click", () => go(-1));
nextBtn.addEventListener("click", () => go(1));
revealBtn.addEventListener("click", toggleAnswer);

showTextBtn.addEventListener("click", () => {
  showText = !showText;
  try {
    localStorage.setItem(SHOWTEXT_KEY, showText ? "1" : "");
  } catch {
    /* private mode / storage blocked */
  }
  renderCard();
});

answerShowTextBtn.addEventListener("click", () => {
  showAnswerText = !showAnswerText;
  try {
    localStorage.setItem(SHOWANSWERTEXT_KEY, showAnswerText ? "1" : "");
  } catch {
    /* private mode / storage blocked */
  }
  renderCard();
});

document.addEventListener("keydown", (e) => {
  const tag = (e.target && e.target.tagName) || "";
  if (tag === "SELECT" || tag === "INPUT" || tag === "TEXTAREA") return;
  if (cardEl.hidden) return;
  // A focused button normally swallows these (it runs its own click on
  // Space/Enter). Let them through when the focus is on one of the card's own
  // controls -- that is the usual state in fullscreen, where ← → must still
  // page the deck after a Prev/Next click.
  if (tag === "BUTTON" && !cardEl.contains(e.target)) return;
  if (e.key === "ArrowLeft") {
    e.preventDefault();
    go(-1);
  } else if (e.key === "ArrowRight") {
    e.preventDefault();
    go(1);
  } else if (e.key === " " || e.key === "Spacebar") {
    if (tag === "BUTTON") return; // the focused card button clicks itself
    e.preventDefault();
    toggleAnswer();
  } else if (e.key === "f" || e.key === "F") {
    e.preventDefault();
    toggleFullscreen();
  } else if (e.key === "+" || e.key === "=") {
    e.preventDefault();
    qZoom.bump(ZOOM_STEP); // the keys drive the question; the mark scheme has its own buttons
  } else if (e.key === "-" || e.key === "_") {
    e.preventDefault();
    qZoom.bump(-ZOOM_STEP);
  } else if (e.key === "0") {
    e.preventDefault();
    qZoom.reset();
  }
});

// --- boot ---------------------------------------------------------

let ranInitial = false;

function onReady(email, client) {
  sb = client;
  loadCorpusLine();
  if (ranInitial) return;
  ranInitial = true; // onAuthStateChange fires more than once

  const { codes, i } = readUrl();
  if (subjectEl) subjectEl.value = subject;
  syncPaperFieldVisibility();
  syncToggleUI();
  idx = i;
  selected = new Set(codes.slice(0, 1)); // single-select now; pruned in refresh()
  refresh();
}

PF.initAuth({ onReady });
