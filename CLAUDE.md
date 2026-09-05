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

Stage 1 of `PLAN.md` in progress (as of 2026-09-05): project skeleton + filename
parsing + `papers` table ingestion are done. Waiting on the user to download the
first ~12 Physics 9702 PDFs into `data/raw/` (see `data/raw/README.md`), then
`paper-finder ingest`. Stage 2 (PDF text extraction) is next.

## Setup

- Python 3.11+ (developed on 3.14). `src/` layout, package `paper_finder`.
- `python -m venv .venv` then `.venv\Scripts\python -m pip install -e ".[dev]"`
  (PowerShell) — installs PyMuPDF plus pytest/ruff and the `paper-finder` CLI.

## Build / test / lint

- Tests: `.venv\Scripts\python -m pytest`
- Lint: `.venv\Scripts\ruff check .`   Format: `.venv\Scripts\ruff format .`
- CLI: `paper-finder init-db` | `paper-finder ingest` | `paper-finder papers`
- `paper-finder ingest` is idempotent — it upserts, and prunes rows whose PDF was
  removed from `data/raw/`. All CLI commands create the schema if missing.

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
