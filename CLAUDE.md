# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project overview

Paper Finder identifies which past exam paper a question came from. A user types a
few words of a question; the tool returns the exact paper (subject, year, session,
paper, variant, question number) and the answer. Future: lookup from a photo of a
question.

Personal / extracurricular project. Exam board: **Cambridge International (CIE)**
AS & A Level. Built one stage at a time — see `@PLAN.md` for the full roadmap,
tech stack, data reference, and database schema.

## Status

Stages 1-5 + 7 + 7b (Vercel/Supabase deploy) done + Stage 4 downloader (as of
2026-09-06). Stage 6 (semantic search) still open. Corpus: 9702
s24/w24/s25/w25/s26 + m26 + s26 variant 4, Papers 1 & 2 = 34 question papers,
790 questions, 765 answers linked.
`evaluate` = ~76% top-1 / 100% top-5 on `eval/validation.tsv` (top-1 keeps
falling as near-duplicate questions across sessions appear — the validation
phrases are too generic; a job for Stage 6 + better phrases).
Note (2026): CIE 9702 gained a **Feb/March ("m") series** and a **4th variant**
(`s26_qp_14/24`); `filenames.py` already allowed both. The download mirror moved
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
questions (text + flat `answer_text`, no PDFs, no source URLs) to a Supabase
Postgres index. The deployed page (root `app.py` → `create_app()`, Vercel's
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
`supabase/migrations/0001_question_bank.sql` (applied via the Supabase MCP;
`get_advisors` clean). Project ref `gfigwnbkzkgwxcdoqxtz` (ap-south-1).

Next: fix rotated-page extraction, or Stage 6 (semantic search) — see `PLAN.md`.

## Setup

- Python 3.11+ (developed on 3.14). `src/` layout, package `paper_finder`.
- `python -m venv .venv` then `.venv\Scripts\python -m pip install -e ".[dev]"`
  (PowerShell) — installs PyMuPDF plus pytest/ruff and the `paper-finder` CLI.

## Build / test / lint

- Tests: `.venv\Scripts\python -m pytest`   Lint: `.venv\Scripts\ruff check .`
  Format: `.venv\Scripts\ruff format .`
- Fetch more papers: `paper-finder download [--dry-run] [--limit N]
  [--subject 9702] [--years 2024-2026] [--sessions s,w,m] [--papers 1,2]
  [--variants 1,2,3,4]` — scope defaults in `config.DOWNLOAD_SCOPE`; NOT part of
  `build` (network side effect). Idempotent (skips files already in `data/raw/`).
- Rebuild the whole question bank from `data/raw/`: `paper-finder build`
  (= `ingest` -> `extract` -> `segment` -> `answers`, each idempotent).
- Then: `paper-finder search "<a few words>"`, `paper-finder evaluate`,
  `paper-finder questions [--paper qp_12] [--limit N]`, `paper-finder papers`.
- Web UI: `pip install -e ".[web]"` then `paper-finder serve [--host 127.0.0.1]
  [--port 8000] [--no-pdfs]`. `fastapi`/`uvicorn` are the optional `web` extra;
  `_cmd_serve` imports them lazily so every other command works without them.
- Publish to the deployed Supabase index: `pip install -e ".[publish]"` then
  `paper-finder publish [--dry-run] [--db-url ...]` — reads `SUPABASE_DB_URL`
  (Supabase **session** pooler, port 5432) from the env or `.env` (gitignored).
  Replace-all, one transaction. NOT part of `build` (network side effect).
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
  PDFs are never uploaded anywhere. `.vercelignore` (not `.gitignore`) is what
  keeps `papers.db` / `data/raw/` off Vercel — the `vercel` CLI uploads the
  working dir. The deployed Supabase index (question text + answers, no PDFs) is
  gated behind an email-code login.
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
  per-question blocks), `search` (FTS5 + BM25), `evaluate`,
  `web` (`create_app(db_path, raw_dir, serve_pdfs)` — FastAPI + a hand-written
  static page in `web/static/`. Local mode: JSON over `search()`, `/pdf/` gated on
  `parse_filename` + a `papers` row + `serve_pdfs`. `GET /api/config` picks local
  vs cloud mode; in cloud mode `/api/search` + `/api/stats` return 501 and the
  browser calls the Supabase RPC instead), `publish` (local SQLite -> Supabase
  Postgres via psycopg; `read_local()` drops mark schemes, source URLs, PDFs).
- `filenames.build_filename()` is the inverse of `parse_filename()`; the
  downloader uses it to enumerate candidates.
- `segment.is_noise` filters page furniture: a regex list + barcode-font glyphs
  (Latin Extended) + control chars + junk symbols + a body-height band.
- `symbols.py` repairs Adobe Symbol-font PUA code points from PDF extraction —
  extend `_SYMBOL` if new glyphs show up in a new subject.
