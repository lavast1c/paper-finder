# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project overview

Paper Finder identifies which past exam paper a question came from. A user types a
few words of a question; the tool returns the exact paper (subject, year, session,
paper, variant, question number) and the answer. Future: lookup from a photo of a
question.

The **UI is branded "Paper Analyser"** (the `<h1>`, `<title>`s and footer on both
pages, as of 2026-09-09); the Python package (`paper_finder`), the CLI
(`paper-finder`), the repo and this file keep the original name.

Personal / extracurricular project. Exam board: **Cambridge International (CIE)**
AS & A Level. Built one stage at a time — see `@PLAN.md` for the full roadmap,
tech stack, data reference, and database schema.

## Status

Stages 1-5 + 7 + 7b (Vercel/Supabase deploy) done + Stage 4 downloader (as of
2026-09-06). Stage 6 (semantic search) still open. Corpus: 9702
m24/s24/w24 + m25/s25/w25 + s26 + m26, Papers 1 & 2, variants 1-4 where they
exist (s25/w25/s26 have a 4th variant `qp_14/24`; the "m" series is
variant 2 only — `9702_m24/m25/m26_qp_12/22`) = 42 question
papers, 978 questions, 953 answers linked, 300 flagged `has_figure`, all 978
tagged into the 11 CIE 9702 AS syllabus sections (`s01`..`s11`, multi-label,
118 multi-section) — `labels/question_topics.tsv`, loaded by `paper-finder
topics`. Every question also has a rendered **image crop** of itself
(`questions.crop_rects`/`crop_count`, set in `segment`; `paper-finder figures`
renders 1155 PNGs into `data/crops/<stem>/qNN_pK.png`, ~35 MB — gitignored +
vercelignored). The browse-by-topic flashcard (served at `/`) shows the crop
instead of the extracted text (Stage 2).
`evaluate` = ~73% top-1 / 100% top-5 on `eval/validation.tsv` (top-1 keeps
falling as near-duplicate questions across sessions appear — the validation
phrases are too generic; a job for Stage 6 + better phrases).
Note: CIE 9702 has a **Feb/March ("m") series** (India zone, variant 2 only —
`m24`, `m25`, `m26` all on the mirror) and a **4th variant** (`qp_14/24`, on
the mirror for s25/w25/s26 — `9702_s24_qp_14/24` etc. 404, they were never
published); `filenames.py` allows both. The download mirror moved
to **PapaCambridge** (`pastpapers.papacambridge.com/directories/CAIE/
CAIE-pastpapers/upload/<file>`) — Dynamic Papers began 500ing every PDF. That
mirror answers a missing paper with a 302 to its homepage; `download.
_urllib_fetcher` maps "redirected off the .pdf" to not-found.
Both MCQ and structured papers supported; `segment_paper` dispatches on
`looks_like_mcq`.

Known bug: some **landscape/rotated** Paper 2 mark-scheme pages (e.g.
`9702_s24_ms_21/22/23`) extract with y-coords outside the page height, so
`segment.load_lines`' body-band drops the `1(a)` labels and `marks.py` links 0
answers. `extract.py` needs page-rotation handling. Question papers are fine.

**Stage 7b — deployed** to Vercel + Supabase (`~/.claude/plans/yes-can-you-...md`,
`DEPLOY_PROGRESS.md`). The local build pipeline is 100% unchanged (still SQLite).
`paper-finder publish` (new, `[publish]` extra = psycopg) pushes `qp` papers +
questions (text + flat `answer_text` + `has_figure`, no PDFs, no source URLs)
to a Supabase Postgres index. The deployed page (root `app.py` → `create_app()`, Vercel's
FastAPI preset) runs in **cloud mode**: `GET /api/config` hands the browser
`SUPABASE_URL` +
`SUPABASE_PUBLISHABLE_KEY`, the browser loads pinned `supabase-js`, signs the user
in with an **emailed 6-digit code** (`signInWithOtp` + `verifyOtp`, Supabase
Auth), and calls the `search_questions` RPC directly with the user's JWT. RLS on
`public.papers`/`public.questions` (`for select to authenticated using (true)` —
"allow all emails for now") + `EXECUTE` granted only to `authenticated` is the
whole access model; anon gets nothing. No PDFs and no
`papers.db` in the cloud. Local `paper-finder serve` (no Supabase env) is
untouched: SQLite, no login, PDF deep-links. Supabase schema:
`supabase/migrations/0001_question_bank.sql` + `0002_search_kind_filter.sql`
+ `0003_question_has_figure.sql` (adds `questions.has_figure` + the RPC's
`has_figure` column; applied via the Supabase MCP; `get_advisors` clean —
re-run `paper-finder publish` to populate the column)
+ `0004_question_topics.sql` (adds `public.topics` + seed, `questions.topic_codes
text[]` with a CHECK + GIN index, the `browse_questions` / `topic_counts` RPCs,
and recreates `search_questions` (+`topic_codes` column) / `corpus_stats`
(+`labelled`/`unlabelled`); `publish` carries the codes as a `text[]` column and
re-upserts `public.topics` from `topics.py`)
+ `0005_question_crops.sql` (adds `questions.crop_count`, recreates
`browse_questions` / `search_questions` with a `crop_count` column, and creates
the **private** `question-crops` Storage bucket + an `authenticated`-only read
policy on `storage.objects`; `publish` carries `crop_count`, and
`paper-finder publish-figures` uploads the PNGs — needs `SUPABASE_SERVICE_ROLE_KEY`).
+ `0006_paper_scope_filters.sql` (`drop function` + recreates `search_questions`
/ `browse_questions` / `topic_counts` with `years integer[]` / `sessions text[]` /
`variants integer[]` params, each `is null or cardinality = 0` = no restriction on
that axis).
Project ref `gfigwnbkzkgwxcdoqxtz` (ap-south-1).

Both `/api/search` (local) and the `search_questions` RPC (cloud) still take a
`kind` filter (`all` / `mcq` (Paper 1) / `theory` (non-1 papers) — local on
`questions.is_mcq`, cloud on `papers.paper`), but it is **no longer in the UI**;
the param stays for compatibility. The **filter bar** (`.filterbar`, on both
`index.html` and `topics.html`, styled from the `Ref Photos/` mock) replaces it:
a context row of **Curriculum** / **Subject** dropdowns (one option each,
`#curriculum` / `#subject` — wired for a future multi-subject corpus, not read
yet) above three real scope filters — **Paper(s)** = CIE variant number
(`#f-paper`, 1-4), **Year(s)** (`#f-year`), **Season(s)** (`#f-season`,
`s`=May/June `m`=Feb/March `w`=Oct/Nov) — plus, on the browse page only, the
single-select **Topic** (`#f-topic`) native `<select>`. Paper/Year/Season are each
a **custom multi-select dropdown** (`<div class="multiselect">` = a `.ms-toggle`
button + a hidden `.ms-panel` of checkbox `<label>`s), upgraded by
`PF.multiSelect()` in `common.js` (open/close, click-outside, Escape, a value
label; the checkboxes are real so their `change` bubbles to the root and the api
is stashed on `root._ms` for deep-link restore). `app.js` `picked()` /
`topics.js` `wireScopeGroup()` read the ticked boxes; nothing ticked = no
restriction on that axis; values serialize to the URL as comma lists
(`?variant=1,2&season=s,w`). There is no corpus-freshness badge.
`search.py._paper_scope()` turns
both `search()` and `browse_by_topic()` / `topic_counts()`; the local endpoints
parse them with `_int_csv` / `_csv_param`, cloud passes them straight to the RPCs.
The search box has a **custom** recent-search dropdown
(`#history` div, not a native `<datalist>` — that looked like browser
autofill and couldn't be styled): `openHistory`/`closeHistory` on focus/blur,
`historyItems` persisted in `localStorage` `paper-finder.history` (last 8),
with a "✕ Clear recent searches" row. Clearing the box wipes stale results
(`resetSearch`). Bare CIE mark codes (`B1`/`M1`/`A1`/`C1` alone on a line) are
dropped from the rendered mark scheme (`app.js` `answerLong`). Question text
`<mark>`s the runs that matched the query (`setQueryTerms` + `appendText`,
`--hl-bg`/`--hl-ink` tokens, `\b(term)\w{0,3}\b` so "force" also hits
"forces"); answers aren't highlighted. Results whose question refers to a
diagram/graph/table (`questions.has_figure`, set in `segment` by the
`_FIGURE_REF` text heuristic — "Fig. 1.1", "the diagram shows", "Table 7.1"…)
show a `◧ Has a diagram, graph or table — check the PDF` note (`.figure-note`).

**Topics + flashcard page (Stage 1 done).** Every question is tagged with all
fitting CIE 9702 AS syllabus sections (`src/paper_finder/topics.py` = the 11
`Topic`s; `labels/question_topics.tsv` = hand-committable, no CIE text — just
`filename<TAB>qnum<TAB>codes<TAB>source`). `paper-finder topics` loads the TSV
into `question_topics` (part of `build` — `segment` cascades that table to zero
every run, so `topics` is the repair, not an optional extra). `paper-finder
classify` is the LLM labeller (`[classify]` extra, network side effect, OUT of
`build` like `download`/`publish`; pluggable `Labeller` seam). `search.py` gains
`browse_by_topic()` (union / `IN` subquery, newest-paper-first) + `topic_counts()`;
`SearchHit` gains `topic_codes`. The flashcard page (`web/static/topics.html` +
`topics.js`, shared code hoisted to `common.js`) is the **landing page, served at
`/`** (route swap 2026-09-09: `/` → `topics.html`, `/search` → `index.html`,
`/topics` → 308 redirect to `/`; nav lists "Browse by topic" first). It is a
flashcard deck: one card at a time, ◂ ▸ / ←→ / space-to-reveal, answer hidden
until revealed. **Topic is a single-select `#f-topic` dropdown** in the filter
bar (after Season(s)), options `"<n>. <name> (<count>)"` from `topic_counts`,
zero-count options disabled — it replaced the old multi-select `#topic-chips`
row. The deck stays hidden ("Choose a topic to start revising.") until a topic is
picked. `browse_by_topic` still takes a `codes` array (the dropdown sends one);
old `?topics=a,b` deep links clamp to the first. Local endpoints `/api/topics` +
`/api/browse` (501 in cloud mode); cloud uses the `browse_questions` /
`topic_counts` RPCs. The corpus line under the `<h1>` shows just
`"<n> questions · <n> question papers"` (the subject name was dropped).

**Stage 2 done — local AND cloud, verified in-browser.** The flashcard shows a
PNG crop of the real question (`crop_count > 0` → image; `= 0` → the old text +
`◧` note). `web/app.py` `/figure/{filename}/{crop}` serves `data/crops/` behind
the same `serve_pdfs` flag as `/pdf/` (`resolve_crop` = `resolve_pdf`'s
round-trip check + a `^q\d{2}_p\d\.png$` whitelist); `result_payload` adds
`crop_base`. `topics.js` `renderCropImages` swaps `<img>`s idempotently (guarded
on `filename#qnum`), loads them **eagerly** (the card is below the fold on load —
lazy images there never enter view), offers a **"Show text"** toggle
(`localStorage` `paper-finder.showtext`), and in cloud mode mints batched signed
Storage URLs. `PF.cloudRow` must carry `question_number` — `topics.js` builds the
crop object path from it (`q{NN}_p{k}.png`); without it cloud paths were
`qundefined_p1.png`. **Cloud live:** 0005 applied, `publish` run (cloud
`crop_count` = 849/92/28/7/2), `publish-figures` uploaded all 1155 PNGs to the
private `question-crops` bucket (42 folders; anon `list` → `[]`, anon `sign` →
404 — genuinely private).

Next: fix rotated-page extraction, or Stage 6 (semantic search) — see `PLAN.md`.

## Setup

- Python 3.11+ (developed on 3.14). `src/` layout, package `paper_finder`.
- `python -m venv .venv` then `.venv\Scripts\python -m pip install -e ".[dev]"`
  (PowerShell) — installs PyMuPDF + FastAPI plus pytest/ruff and the
  `paper-finder` CLI.

## Build / test / lint

- Tests: `.venv\Scripts\python -m pytest`   Lint: `.venv\Scripts\ruff check .`
  Format: `.venv\Scripts\ruff format .`
- Fetch more papers: `paper-finder download [--dry-run] [--limit N]
  [--subject 9702] [--years 2024-2026] [--sessions s,w,m] [--papers 1,2]
  [--variants 1,2,3,4]` — scope defaults in `config.DOWNLOAD_SCOPE`; NOT part of
  `build` (network side effect). Idempotent (skips files already in `data/raw/`).
- Rebuild the whole question bank from `data/raw/`: `paper-finder build`
  (= `ingest` -> `extract` -> `segment` -> `answers` -> `topics` -> `figures`,
  each idempotent). A `db.py` schema change (e.g. the `crop_rects`/`crop_count`
  columns) = delete `papers.db` first, then `build`.
- Then: `paper-finder search "<a few words>"`, `paper-finder evaluate`,
  `paper-finder questions [--paper qp_12] [--limit N]`, `paper-finder papers`,
  `paper-finder topics` (reload `labels/question_topics.tsv` + print per-section
  counts; also runs as the last `build` step).
- Re-label questions by topic: `paper-finder classify [--only <substr>] [--limit N]
  [--relabel] [--model ...] [--dry-run]` — LLM multi-label into `s01`..`s11`,
  writes `labels/question_topics.tsv`. Needs `[classify]` extra (`anthropic`,
  lazy import) + `ANTHROPIC_API_KEY`. NOT part of `build` (network side effect);
  skips already-labelled questions so an interrupted run resumes.
- Web UI: `pip install -e ".[web]"` then `paper-finder serve [--host 127.0.0.1]
  [--port 8000] [--no-pdfs]`. `fastapi` is a core dep (Vercel needs it); only
  `uvicorn` is the optional `web` extra, lazily imported in `_cmd_serve` so every
  other command works without it.
- Render the per-question image crops: `paper-finder figures [--only <substr>]
  [--limit N] [--force] [--dry-run]` — PyMuPDF renders `questions.crop_rects`
  into `data/crops/<stem>/qNN_pK.png` (greyscale, 2x). Part of `build` (offline);
  idempotent (skips existing).
- Publish to the deployed Supabase index: `pip install -e ".[publish]"` then
  `paper-finder publish [--dry-run] [--db-url ...]` — reads `SUPABASE_DB_URL`
  (Supabase **session** pooler, port 5432) from the env or `.env` (gitignored).
  Replace-all, one transaction. NOT part of `build` (network side effect).
- Upload the crops to Storage: `paper-finder publish-figures [--only <substr>]
  [--limit N] [--force] [--dry-run]` — stdlib-urllib PUTs `data/crops/*.png` to
  the private `question-crops` bucket. Needs `SUPABASE_URL` +
  `SUPABASE_SERVICE_ROLE_KEY` (server-side key — paste it into `.env` yourself)
  in the env or `.env`. Idempotent/resumable (lists each paper prefix, skips
  what is already there). Separate from `publish` (long binary upload). NOT part
  of `build`.
- Deploy = Vercel FastAPI preset: root `app.py` exposes `app = create_app()`
  (puts `src/` on `sys.path`), `requirements.txt` = fastapi only (keeps PyMuPDF
  out — the deployed import chain is pymupdf-free), `vercel.json` = region `bom1`
  + a daily `/api/health` cron. No `api/` dir, no rewrites (the preset routes
  every path to `app`). Env on Vercel: `SUPABASE_URL` + `SUPABASE_PUBLISHABLE_KEY`
  (both browser-safe). Auth = Supabase email OTP; needs custom SMTP (the built-in
  sender only emails project-team addresses) + "Magic Link" / "Confirm sign up"
  templates containing `{{ .Token }}` — configured in the Supabase dashboard, see
  `DEPLOY_PROGRESS.md`.
- Local SQLite schema change during early dev = delete `papers.db` and re-run
  `build` (FTS5 virtual table not migrated). The Supabase schema IS migrated —
  edit `supabase/migrations/` and apply via the Supabase MCP / CLI.

## Version control

- Repo: `github.com/Lavastic-Gaming/paper-finder` (private), remote `origin`,
  default branch `main`.
- Commit identity is set locally on this repo (`Lavastic-Gaming` /
  `vihaantalluri@gmail.com`) — do not rely on global git config.
- Workflow: after each meaningful, working change, make a clean commit (concise
  imperative subject, body explaining what and why) and `git push` to `origin`.
  Keep `main` in a working state. The user wants a pushed checkpoint at every step
  so the project is easy to revert.

## Conventions

- `data/raw/` holds downloaded PDFs and is **never edited** — everything in
  `data/processed/` and `papers.db` is regenerated from it.
- CIE past papers are copyright of Cambridge Assessment: this is a private study
  tool; the corpus and extracted question bank are not committed to git and the
  **whole PDFs** are never uploaded anywhere. `.vercelignore` (not `.gitignore`)
  is what keeps `papers.db` / `data/raw/` / `data/crops/` off Vercel — the
  `vercel` CLI uploads the working dir. The deployed Supabase index (question
  text + answers, no PDFs) is gated behind an email-code login. **Single-question
  image crops** (`data/crops/`, gitignored + vercelignored) may go to the private
  `question-crops` Storage bucket behind that same login — a one-question crop is
  not the paper, and it sits at the same protection level as the question text
  already there. Full PDFs still never leave the machine.
- Code style: ruff (`select = E, F, I, UP, B, DTZ`, line length 100); run
  `ruff format` before committing. Prefer functions that take an explicit
  `db_path` / `raw_dir` (defaulting to `config`) so they stay unit-testable.
- CIE filename grammar and the parser live in `src/paper_finder/filenames.py`;
  the DB schema (all tables, created up front) in `src/paper_finder/db.py`.
- Pipeline modules: `download` (generate mirror URLs from `DOWNLOAD_SCOPE`, fetch
  PDFs into `data/raw/`, CSV attempt log at `data/download_log.csv`; stdlib
  `urllib`, injected `fetcher` for tests; aborts on 403 / challenge / repeated
  network errors), `ingest` (filenames -> papers), `extract` (PDF -> text+bbox
  JSON in `data/processed/`, via PyMuPDF), `segment` (paper -> questions; MCQ and
  structured), `marks` (mark scheme -> answers; MCQ letter table or structured
  per-question blocks), `topics` (load `labels/question_topics.tsv` -> the
  `question_topics` join table; keyed on `(filename, question_number)`, never
  `questions.id` — `segment` reassigns ids every run; orphan labels reported not
  fatal), `classify` (LLM multi-label -> the TSV; injectable `Labeller`, batched,
  lazy `anthropic`; network side effect, out of `build`),
  `figures` (`questions.crop_rects` -> greyscale PNG crops in `data/crops/` via
  PyMuPDF; part of `build`, idempotent, `crop_path` derives `qNN_pK.png` from
  `(stem, qnum, ordinal)`; skips `page.rotation != 0`; never imported from
  `web/app.py`), `search` (FTS5 + BM25;
  `kind=all|mcq|theory` filter + `_paper_scope()` year/session/variant filter;
  `browse_by_topic` + `topic_counts` for the browse page;
  `SearchHit` carries `topic_codes` + `crop_count`),
  `evaluate`,
  `web` (`create_app(db_path, raw_dir, crop_dir, serve_pdfs)` — FastAPI + a hand-written
  static page in `web/static/` (frosted-panel UI: token-driven `style.css`,
  theme-aware, full-bleed, IBM Plex type, a light-blue accent
  (`--primary` `#2563eb` light / `#60a5fa` dark, `--btn` / `--accent-ink`
  siblings; `--hl-bg` stays amber — highlighter, not chrome); opaque +
  reduced-transparency fallbacks). No page taglines — just the `<h1>` + the
  `#corpus` count line. The **header, search tray and filter bar** are true
  "liquid glass": `--glass: transparent` (zero fill), and
  `--glass-backdrop` = `url(#glass-refraction) saturate(1.6) brightness(1.05)
  blur(2px)` — an inline SVG `feTurbulence` + `feDisplacementMap` filter
  (`#glass-refraction`, duplicated into both HTML `<body>`s inside `svg.glass-defs`)
  that *bends* the dot grid behind the pane. `--glass` falls back to an opaque
  fill and `--glass-backdrop` to `none` in the no-`backdrop-filter` /
  `prefers-reduced-transparency` blocks. Content panels (`#gate`, `.card`,
  results) keep `--surface` / `--surface-strong`. Deployed at
  `pastpaperanalyser.vercel.app`. The backdrop the glass refracts is an
  **interactive dot grid** — `#bg-dots` canvas (first child of `<body>`, `z-index:
  -1`, `pointer-events: none`) driven by `dotgrid.js`, a dependency-free port of
  react-bits' `<DotGrid />` (no gsap; a hand-rolled frame-rate-independent damped
  spring per dot). Dots sit at `--dot-base` and lerp to `--primary` within ~150px
  of the pointer; a deliberate fast swipe nudges nearby dots and a click bursts
  every dot in range radially outward — both spring home with one soft overshoot.
  A slow aiming move never triggers the swipe (`SPEED_TRIGGER` + a settle-snap
  keep the grid dead still). `prefers-reduced-motion` → a static grid, no loop or
  listeners; pauses while the tab is hidden; re-reads the CSS colours on a theme
  change. It replaced the old static `--blob-*`
  radial-gradient mesh (`body::before`, removed). The styled-select
  rule is `.select-wrap select` (`appearance:none` + one CSS chevron on every
  filter select). Local mode: JSON over
  `search()`, `/pdf/` gated on
  `parse_filename` + a `papers` row + `serve_pdfs`; `/figure/{filename}/{crop}`
  serves `data/crops/` behind the same flag (`resolve_crop`). `GET /api/config`
  picks local vs cloud mode; in cloud mode `/api/search` + `/api/stats` +
  `/api/topics` + `/api/browse` return 501 and the browser calls the Supabase RPC
  instead. `/` = the browse-by-topic flashcard page (`topics.html`), `/search` =
  the keyword-search page (`index.html`), `/topics` 308-redirects to `/`; shared
  JS in `web/static/common.js`),
  `publish` (local SQLite -> Supabase
  Postgres via psycopg; `read_local()` drops mark schemes, source URLs, PDFs;
  carries `questions.topic_codes` as a `text[]` + `crop_count`, and re-upserts
  `public.topics` from `topics.py` (the `DELETE public.papers` cascade does not
  reach it)),
  `publish_figures` (stdlib-urllib upload of `data/crops/` PNGs to the private
  `question-crops` Storage bucket; injectable `http` seam, idempotent/resumable).
- `filenames.build_filename()` is the inverse of `parse_filename()`; the
  downloader uses it to enumerate candidates.
- `segment.is_noise` filters page furniture: a regex list + barcode-font glyphs
  (Latin Extended) + control chars + junk symbols + a body-height band.
- `symbols.py` repairs Adobe Symbol-font PUA code points from PDF extraction —
  extend `_SYMBOL` if new glyphs show up in a new subject.
