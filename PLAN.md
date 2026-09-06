# Paper Finder — Project Plan

**Goal:** Type a few words of an exam question → get back the exact past paper it
came from (subject, year, session, paper, variant, question number) and the answer.

**Later:** Upload a photo of a question → same result.

**Context:** Personal / extracurricular project. Exam board: **Cambridge International
(CIE)** AS & A Level. Built one stage at a time.

---

## 1. Guiding principles

1. **Vertical slice before scale.** Get the whole pipeline (download → extract →
   split into questions → search → return paper + answer) working on ~10–20 papers
   before downloading hundreds. A bug in text extraction is cheap to find on 12
   PDFs and expensive to find on 700.
2. **The corpus is the product.** Most of the hard work is turning messy PDFs into
   clean, correctly-labelled questions. The search itself is comparatively easy.
3. **Keep every stage runnable.** After each stage you should be able to run
   something and see a result, even if crude.
4. **Store raw + processed separately.** Never mutate `data/raw/`. Everything
   downstream is regenerated from it, so you can re-run the pipeline as it improves.
5. **Personal use only.** CIE past papers are copyright of Cambridge Assessment.
   A private study tool is fine; do not publish or redistribute the collected PDFs
   or extracted question bank.

---

## 2. Tech stack

| Concern | Choice | Why |
|---|---|---|
| Language | **Python 3.11+** | Best PDF + NLP + ML ecosystem |
| Env / packaging | `venv` + `pyproject.toml` (or `uv`) | Standard, simple |
| PDF text extraction | **PyMuPDF** (`pip install pymupdf`, imported as `fitz`) | Fast, gives text *with coordinates* — needed for margin-based question detection |
| OCR (older scanned papers, later) | Tesseract (`pytesseract`) or a vision model | Most CIE papers 2016+ have a text layer; OCR is a fallback |
| Database | **SQLite** (stdlib `sqlite3`) | Zero setup; has FTS5 full-text search built in |
| Keyword search | SQLite **FTS5** + BM25 ranking | Great for verbatim phrase fragments |
| Semantic search (Stage 6) | `sentence-transformers` (`all-MiniLM-L6-v2`) + brute-force cosine, or FAISS | Local, free; corpus is small enough that brute force is fast |
| Web UI (Stage 7) | FastAPI + one HTML page | Minimal |
| Image input (Stage 8) | Vision model API, or Mathpix / `pix2tex` | Plain Tesseract is weak on equations |
| Tests | `pytest` | — |

---

## 3. CIE data reference

### Filename convention

```
{subjectcode}_{session}{yy}_{type}_{paper}{variant}.pdf

subjectcode  4 digits, e.g. 9702 = Physics, 9701 = Chemistry, 9709 = Mathematics
session      s = May/June    w = Oct/Nov    m = Feb/March (India variant only, some subjects)
yy           2-digit year, e.g. 23
type         qp = question paper    ms = mark scheme    in = insert
             gt = grade thresholds  er = examiner report  sp/sm = specimen
paper        1 digit  (Physics: 1=MCQ, 2=AS structured, 3=practical, 4=A2 structured, 5=planning/analysis)
variant      1 digit  (1 / 2 / 3 — regional time zones)

Examples:  9702_s23_qp_12.pdf     9702_w21_ms_42.pdf     9709_m22_qp_12.pdf
```

### Where the PDFs live

Mirror sites expose them at stable, predictable paths (so you *generate* URLs, you
don't crawl). Example structure:

```
https://papers.gceguide.com/A%20Levels/Physics%20(9702)/2023/9702_s23_qp_12.pdf
```

Other mirrors: PapaCambridge, Dynamic Papers, XtremePapers, Physics & Maths Tutor.
Pick one, confirm its exact URL pattern by downloading 2–3 files by hand first.

### Paper types and how answers work

- **Paper 1 (Multiple Choice).** 40 questions, options A–D. Mark scheme is just a
  table: `Question | Answer` → `1 | B`. Trivial to parse. Best target for the
  first slice.
- **Structured papers (2, 4, …).** Questions numbered `1, 2, …` with sub-parts
  `(a) (b) (i) (ii)`; marks shown right-aligned as `[3]` or `[Total: 8]`. Mark
  scheme lists acceptable answers per mark point under each question number.

### Recommended starting scope

**Physics 9702, Paper 1 (MCQ) + Paper 2, May/June + Oct/Nov, 2019–2024.**
≈ 2 papers × 2 sessions × ~2.5 variants × 6 years × 2 (qp+ms) ≈ **120 PDFs**.
Small enough to iterate, big enough to be genuinely useful.

Full 9702 (all papers, 2016–2024) is roughly 600–700 PDFs — that's Stage 4.

---

## 4. Project structure

```
paper-finder/
  data/
    raw/                  # downloaded PDFs — never edited
    processed/            # extracted text / JSON per paper
  src/paper_finder/
    __init__.py
    config.py             # subjects, years, sessions, paths
    download.py           # generate URLs, fetch PDFs, rate-limit
    extract.py            # PDF -> text (+ coordinates)
    segment.py            # text -> individual questions with metadata
    marks.py              # mark scheme -> answers
    index.py              # build FTS5 (and later embedding) index
    search.py             # query -> ranked results
    cli.py                # command-line entry point
  tests/
  papers.db               # SQLite (gitignored)
  pyproject.toml
  README.md
  PLAN.md
  CLAUDE.md
```

`.gitignore`: `data/raw/`, `data/processed/`, `papers.db`, `.venv/`, `__pycache__/`

---

## 5. Database schema

```sql
CREATE TABLE papers (
    id            INTEGER PRIMARY KEY,
    subject_code  TEXT NOT NULL,      -- '9702'
    subject_name  TEXT,               -- 'Physics'
    year          INTEGER NOT NULL,   -- 2023
    session       TEXT NOT NULL,      -- 's' | 'w' | 'm'
    paper         INTEGER NOT NULL,   -- 1
    variant       INTEGER NOT NULL,   -- 2
    paper_type    TEXT NOT NULL,      -- 'qp' | 'ms'
    filename      TEXT NOT NULL UNIQUE,
    source_url    TEXT,
    downloaded_at TEXT,
    has_text_layer INTEGER            -- 1 / 0, set during extract
);

CREATE TABLE questions (
    id              INTEGER PRIMARY KEY,
    paper_id        INTEGER NOT NULL REFERENCES papers(id),
    question_number INTEGER NOT NULL,
    question_text   TEXT NOT NULL,
    marks           INTEGER,
    is_mcq          INTEGER,
    page_start      INTEGER,
    UNIQUE (paper_id, question_number)
);

CREATE TABLE answers (
    id           INTEGER PRIMARY KEY,
    question_id  INTEGER NOT NULL REFERENCES questions(id),
    answer_text  TEXT NOT NULL,
    source       TEXT                -- 'mark_scheme'
);

-- Full-text index (contentless, mirrors questions.question_text)
CREATE VIRTUAL TABLE questions_fts USING fts5(
    question_text,
    content='questions',
    content_rowid='id'
);
```

---

## 6. Stages

Each stage lists **tasks**, the **deliverable**, and **done when** (how you know
it works).

### Stage 1 — Skeleton + tiny corpus

- `git init`; create venv; `pyproject.toml` with `pymupdf`.
- Create folder structure and `.gitignore`.
- `config.py` with paths and the starting scope.
- Write `db.py` that creates the schema above.
- **By hand**, download ~6 question papers + their 6 mark schemes (Physics 9702
  Paper 1, 2022–2024) into `data/raw/`. Keep the original filenames.
- Write `ingest_filenames.py`: parse each filename in `data/raw/` into a `papers`
  row.

**Deliverable:** `papers.db` with ~12 paper rows.
**Done when:** `SELECT * FROM papers` shows correct subject/year/session/paper/variant for every file.

### Stage 2 — Extract & segment

- `extract.py`: for each `qp` paper, use PyMuPDF `page.get_text("dict")` to get
  text blocks with `(x, y)` positions. Save raw text to `data/processed/<name>.txt`
  and structured blocks to `<name>.json`. Set `papers.has_text_layer` (flag as 0
  if a page returns almost no text → scanned, skip for now).
- `segment.py`:
  - **MCQ papers:** find lines that are a lone number `1`–`40` near the left
    margin; everything until the next number (minus the `A B C D` options, which
    you keep) is that question. Store with `is_mcq = 1`.
  - **Structured papers:** find question numbers in the left margin by x-position;
    capture text up to the next number; pull `marks` from `[Total: N]` or the last
    `[N]`.
  - Insert `questions` rows.
- Populate `questions_fts` from `questions`.

**Deliverable:** `questions` table with a few hundred rows.
**Done when:** spot-checking 10 random questions against the actual PDF, the text
and question number are right for at least 8.

### Stage 3 — Keyword search (CLI)

- `search.py`: given a phrase, query `questions_fts` ranked by `bm25()`, join to
  `papers`, return top 5 with a readable label:
  `9702/s23/12 Q17 [1 mark] — "A car accelerates uniformly from rest…"`
- `cli.py`: `python -m paper_finder search "uniformly from rest"`.
- Build a **validation set**: a text file of ~20 lines, each a phrase you typed
  yourself paired with the paper + question you know it's from. Write
  `evaluate.py` that reports top-1 and top-5 accuracy.

**Deliverable:** working CLI search over the tiny corpus.
**Done when:** top-5 accuracy on your validation set is ≥ 90% for verbatim phrases.

> 🎯 **This is the first genuinely useful version. Everything after is expansion.**

### Stage 4 — Automated downloader

- `download.py`:
  - Nested loops over `config` scope: year × session × paper × variant × type.
  - Build the mirror URL from the filename convention; `requests.get`.
  - Save to `data/raw/` on HTTP 200; skip 404 (that combination doesn't exist).
  - `time.sleep(1.5)` between requests; set a `User-Agent`; check the site's
    `robots.txt` once; add `--resume` behaviour (skip files already on disk).
  - Log every attempt to a CSV so failures are visible.
- Expand `config` scope to full Physics 9702, 2016–2024.
- Re-run Stages 1–3 ingestion over the full set.

**Deliverable:** ~600 PDFs in `data/raw/`, all pipeline steps re-run.
**Done when:** the downloader can be re-run and downloads 0 new files (idempotent),
and search still passes the validation set on the larger corpus.

**Progress (2026-09):** `download.py` + `paper-finder download` implemented — pure
URL generation (no scraping), stdlib `urllib`, injected `fetcher` for tests, small
default `config.DOWNLOAD_SCOPE`, CSV attempt log at `data/download_log.csv`,
`--dry-run` / `--limit`, aborts on 403 / challenge page / repeated network errors.
GCE Guide's direct-download URLs are dead (JS app now); mirror is **Dynamic
Papers** (flat `{base}/{filename}`), swappable via `config.MIRROR_BASE_URL`.

### Stage 5 — Answers from mark schemes

- `marks.py`:
  - **MCQ mark schemes:** parse the `Question | Answer` grid → one `answers` row
    per question (`answer_text` = `"B"`).
  - **Structured mark schemes:** split by question-number headers; store the block
    of mark points as `answer_text` for that question (don't over-engineer parsing
    of individual mark points yet).
  - Match a mark scheme to its question paper by
    `(subject_code, year, session, paper, variant)`.
- Update `search.py` output to show the answer beneath each result.

**Deliverable:** answers shown in search results.
**Done when:** for 10 random MCQ hits, the displayed letter matches the real mark
scheme.

### Stage 6 — Semantic search

- `index.py`: embed every `question_text` with `all-MiniLM-L6-v2`; store vectors
  (a `.npy` file keyed by question id is fine for < 100k rows).
- `search.py`: **hybrid** — get top 50 from FTS5 and top 50 by cosine similarity,
  combine scores (e.g. reciprocal rank fusion), return top 5.
- Re-run `evaluate.py`, and add *paraphrased* queries to the validation set (same
  question, your own wording).

**Deliverable:** search that works when the user's wording differs from the paper.
**Done when:** top-5 accuracy on paraphrased queries clearly beats Stage 3
keyword-only.

### Stage 7 — Web UI

- FastAPI app: one `GET /search?q=` endpoint returning JSON; one static HTML page
  with a search box and results list (paper label, question text, answer,
  optionally a link to open the PDF at the right page).
- `python -m paper_finder serve`.

**Deliverable:** searchable in a browser on `localhost`.

**Status (2026-09): done.** `paper_finder.web.create_app()` (FastAPI) +
hand-written static page in `web/static/`. Routes: `GET /`, `/api/search?q=&limit=`
(the page owns `/`), `/api/stats`, `/pdf/{filename}`. Run with
`paper-finder serve [--host 127.0.0.1] [--port 8000] [--no-pdfs]`; `fastapi` /
`uvicorn` are the optional `web` extra, lazily imported so the other commands work
without them. PDF serving is gated on `parse_filename` + a `papers` row +
`serve_pdfs`, and `--no-pdfs` / `serve_pdfs=False` is the deploy-safe mode.

### Stage 8 — Image input (future)

- `POST /search-image`: accept an uploaded photo.
- Send it to a vision model (or Mathpix / `pix2tex`) → get the question text.
- Feed that text into the existing Stage 6 search. No new search logic needed.
- Handle: cropping, glare, handwriting in margins, multi-question photos.

**Deliverable:** photo → same results as typing the question.

---

## 7. Known technical challenges

| Challenge | Plan |
|---|---|
| Equations/symbols rendered as **images**, not text | Those questions get partial text. Fine for v0 — users type prose fragments. Add math OCR later if needed. |
| **Scanned** older papers (pre-2016) | Detected via `has_text_layer = 0`; excluded initially. Add a Tesseract path in a later stage. |
| Question **segmentation errors** (merged/split questions) | Use x-coordinate of the number in the margin, not just regex. Keep the validation set to catch regressions. |
| **Diagrams / graphs** in questions | Ignored for text search. |
| Matching **mark scheme ↔ question paper** | Join on `(subject, year, session, paper, variant)` — all in the filename. |
| Multiple **variants** with near-identical questions | Expected; return all matches, ranked. |
| Mirror site **changes layout or rate-limits** | Downloader logs every attempt; keep `data/raw/` so you never re-download. |

---

## 8. Milestones (rough, part-time)

1. Stage 1–2: skeleton, 12 papers, extraction + segmentation — 1–2 sessions
2. Stage 3: working CLI search + validation harness — 1–2 sessions
3. Stage 4: automated downloader, full 9702 corpus — 1 session
4. Stage 5: answers from mark schemes — 1–2 sessions
5. Stage 6: semantic / hybrid search — 1–2 sessions
6. Stage 7: web UI — 1–2 sessions
7. Stage 8: image input — later

---

## 9. Immediate next actions

1. Confirm the mirror site and its exact URL pattern (download 3 files by hand).
2. Set up the skeleton (Stage 1, tasks 1–4).
3. Download 12 Physics 9702 PDFs by hand into `data/raw/`.
4. Start `extract.py`.
