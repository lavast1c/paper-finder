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

Stages 1-5 done + Stage 4 downloader (as of 2026-09-06). Corpus: 9702 s24/w24/
s25/w25/s26, Papers 1 & 2 = ~29 papers, ~691 questions, ~668 answers linked.
`evaluate` = ~85% top-1 / 100% top-5 on `eval/validation.tsv` (top-1 fell as
near-duplicate questions across sessions appeared — the validation phrases are
too generic; a job for Stage 6 + better phrases).
Both MCQ and structured papers supported; `segment_paper` dispatches on
`looks_like_mcq`.

Known bug: some **landscape/rotated** Paper 2 mark-scheme pages (e.g.
`9702_s24_ms_21/22/23`) extract with y-coords outside the page height, so
`segment.load_lines`' body-band drops the `1(a)` labels and `marks.py` links 0
answers. `extract.py` needs page-rotation handling. Question papers are fine.

Next: fix rotated-page extraction, or Stage 6 (semantic search) — see `PLAN.md`.

## Setup

- Python 3.11+ (developed on 3.14). `src/` layout, package `paper_finder`.
- `python -m venv .venv` then `.venv\Scripts\python -m pip install -e ".[dev]"`
  (PowerShell) — installs PyMuPDF plus pytest/ruff and the `paper-finder` CLI.

## Build / test / lint

- Tests: `.venv\Scripts\python -m pytest`   Lint: `.venv\Scripts\ruff check .`
  Format: `.venv\Scripts\ruff format .`
- Fetch more papers: `paper-finder download [--dry-run] [--limit N]
  [--subject 9702] [--years 2022-2024] [--sessions s,w] [--papers 1,2]
  [--variants 1,2,3]` — scope defaults in `config.DOWNLOAD_SCOPE`; NOT part of
  `build` (network side effect). Idempotent (skips files already in `data/raw/`).
- Rebuild the whole question bank from `data/raw/`: `paper-finder build`
  (= `ingest` -> `extract` -> `segment` -> `answers`, each idempotent).
- Then: `paper-finder search "<a few words>"`, `paper-finder evaluate`,
  `paper-finder questions [--paper qp_12] [--limit N]`, `paper-finder papers`.
- Schema change during early dev = delete `papers.db` and re-run `build` (the FTS
  virtual table is not migrated).

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
  tool; the corpus and extracted question bank are not committed and not to be
  published or redistributed.
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
  per-question blocks), `search` (FTS5 + BM25), `evaluate`.
- `filenames.build_filename()` is the inverse of `parse_filename()`; the
  downloader uses it to enumerate candidates.
- `segment.is_noise` filters page furniture: a regex list + barcode-font glyphs
  (Latin Extended) + control chars + junk symbols + a body-height band.
- `symbols.py` repairs Adobe Symbol-font PUA code points from PDF extraction —
  extend `_SYMBOL` if new glyphs show up in a new subject.
