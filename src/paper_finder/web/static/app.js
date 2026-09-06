"use strict";

const form = document.getElementById("search");
const input = document.getElementById("q");
const statusEl = document.getElementById("status");
const resultsEl = document.getElementById("results");
const corpusEl = document.getElementById("corpus");

let controller = null;

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

async function loadStats() {
  try {
    const res = await fetch("/api/stats");
    if (!res.ok) return;
    const s = await res.json();
    const bits = [
      `${s.questions.toLocaleString()} questions`,
      `${s.question_papers} question papers`,
    ];
    if (s.subjects && s.subjects.length) bits.push(s.subjects.join(", "));
    corpusEl.textContent = bits.join(" · ");
  } catch {
    /* leave the corpus line blank; never block search */
  }
}

function answerBlock(answer) {
  const box = el("div", "answer");
  box.append(el("span", "label", "Answer"));
  if (answer == null || answer === "") {
    box.className = "answer answer--none";
    box.append(el("span", "value", "No mark scheme answer linked."));
    return box;
  }
  const single = answer.trim().length === 1;
  box.className = single ? "answer answer--letter" : "answer answer--long";
  box.append(el("span", "value", single ? answer.trim() : answer));
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

  li.append(el("div", "question", r.question_text));
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
    const res = await fetch(
      "/api/search?q=" + encodeURIComponent(q) + "&limit=10",
      { signal: controller.signal },
    );
    if (!res.ok) {
      setStatus(`Search failed (HTTP ${res.status}).`);
      return;
    }
    data = await res.json();
  } catch (err) {
    if (err.name === "AbortError") return;
    setStatus("Could not reach the server. Is `paper-finder serve` still running?");
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

const initial = new URLSearchParams(location.search).get("q");
if (initial) {
  input.value = initial;
  run();
}
loadStats();
