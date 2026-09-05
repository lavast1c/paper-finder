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

Not yet implemented (as of 2026-09-05). Currently at Stage 1 of `PLAN.md`.
Update this section and the sections below as each stage lands.

## Setup

_TODO: fill in when the project skeleton exists (Python 3.11+, venv, `pip install -e .`)._

## Build / test / lint

_TODO: fill in the exact commands. Planned: `pytest`, and a CLI entry point
`python -m paper_finder ...`._

## Conventions

- `data/raw/` holds downloaded PDFs and is **never edited** — everything in
  `data/processed/` and `papers.db` is regenerated from it.
- CIE past papers are copyright of Cambridge Assessment: this is a private study
  tool; the corpus and extracted question bank are not to be published or
  redistributed.
- _TODO: add code style / branch / commit conventions once coding starts._
