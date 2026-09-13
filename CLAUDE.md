# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project overview

Paper Finder identifies which past exam paper a question came from. A user types a
few words of a question; the tool returns the exact paper (subject, year, session,
paper, variant, question number) and the answer. Future: lookup from a photo of a
question.

The **UI is branded "Paper Analyser"** (`<h1>`, `<title>`s, footer); the Python
package (`paper_finder`), the CLI (`paper-finder`), the repo and this file keep
the original name.

Personal / extracurricular project. Exam board: **Cambridge International (CIE)**
AS & A Level. Built one stage at a time — see `@PLAN.md` for the full roadmap,
tech stack, data reference, and database schema.

## Status

Stages 1-5 + 7 + 7b (Vercel/Supabase deploy) done. Stage 6 (semantic search) open.

**Corpus: six syllabus codes / eleven subjects / eleven topic taxonomies**,
distinguished by `papers.subject_name`. Sessions across all subjects:
`s20`-`s26` (May/June), `w20`-`w25` (Oct/Nov), and Feb/March `m20`-`m26`
(variant 2 only) for 9702/9709/9701/9700/9708 (9231 has no `m` series or
`w26`). 9709 is now split into five per-paper subjects (P1/P3/P4/P5/P6), the
same disjoint-subject pattern as 9231's P1/P4 — not the one-taxonomy-spans-
both-papers pattern used for the MCQ+structured subjects below.

| Subject | Code/paper | QP papers | Questions | Answered | Taxonomy |
|---|---|---|---|---|---|
| Physics | 9702 P1+P2 | 97 | 2285 | 2285 | `s01`-`s11` (11) |
| Further Pure Maths | 9231 P1 | 39 | 273 | 273 | `fp1`-`fp7` (7) |
| Further Prob & Stats | 9231 P4 | 39 | 237 | 237 | `fs1`-`fs5` (5) |
| Pure Mathematics 1 | 9709 P1 | 46 | 502 | 501 | `pm1`-`pm8` (8) |
| Probability & Stats 1 | 9709 P5 | 46 | 307 | 307 | `ps1`-`ps5` (5) |
| Pure Mathematics 3 | 9709 P3 | 45 | 479 | 478 | `pm31`-`pm39` (9) |
| Mechanics | 9709 P4 | 46 | 321 | 321 | `mc1`-`mc5` (5) |
| Probability & Stats 2 | 9709 P6 | 46 | 313 | 313 | `ps21`-`ps25` (5) |
| Chemistry | 9701 P1+P2 | 98 | 2186 | 2185 | `ch01`-`ch22` (22) |
| Biology | 9700 P1+P2 | 96 | 2208 | 2208 | `bi01`-`bi11` (11) |
| Economics | 9708 P1+P2 | 98 | 1694 | 1694 | `ec01`-`ec06` (6) |

Physics/Chemistry/Biology/Economics Paper 1 is MCQ, Paper 2 structured — the
only four subjects where `is_mcq` varies within a subject; 9231/9709 papers
are all structured. Taxonomies for Physics/Chemistry/Biology/Economics each
span both papers (one taxonomy, not split by paper) — Economics is coarser
than the others (6 topics, not 11-22) since that's the AS syllabus's own
top-level section count there. `pm3`/`ps2` extend the existing `pm`/`ps`
(Pure Maths / Prob & Stats) code family without colliding as strings with
9709 P1/P5's `pm1`-`pm8`/`ps1`-`ps5`; `mc` (Mechanics) was unclaimed.

Known gaps (all confirmed as real source-document issues, not pipeline bugs):
`9702_s26_qp_21` is excluded entirely via `config.EXCLUDE_FILENAMES` (its mark
scheme was never published — every question would show unanswered);
`9701_s24_qp_22.pdf` question 5, `9709_s26_qp_12` (a 4-page preview PDF, 9
questions short), and `9709_s24_qp_33.pdf` question 11 (its mark scheme's
answer table stops at question 10) each have one missing answer/paper but
stay in the corpus.

Taxonomies live in `src/paper_finder/topics.py` as eleven `Taxonomy` instances
(`TAXONOMIES`, 94 topics total); `taxonomy_for(subject_code, paper)` /
`taxonomy_by_name(subject_name)` resolve one. Labels live in
`labels/question_topics.tsv` (hand-committable TSV, no CIE text — just
`filename<TAB>qnum<TAB>codes<TAB>source`), loaded by `paper-finder topics`
(part of `build` — `segment` cascades the join table to zero every run, so
this is the repair step, not optional).

**Labelling, no `ANTHROPIC_API_KEY` set:** only 9702's 2024-2026 papers were
labelled by `paper-finder classify` (the LLM labeller). Everything else was
labelled without a key: MCQ papers (9702/9701/9700/9708 Paper 1) via a fixed
position-in-paper heuristic weighting each topic's typical share of the paper
— applied identically to every P1 file in a subject, not a per-paper read, so
treat it as ~80-85% accurate; every structured paper (9702 P2, all 9231, all
9709 including the newly-added P3/P4/P6, 9701 P2, 9700 P2, 9708 P2) was
hand-labelled by reading each question. Refine any `llm` row later with
`classify --relabel` once a key is set (`classify.py` is not yet
taxonomy-aware).

Every question has a rendered **image crop** of itself
(`questions.crop_rects`/`crop_count`, set by `segment`), and structured
questions also get an **image crop of their mark-scheme answer**
(`answers.answer_crop_rects`/`answer_crop_count`, set by `marks`). Both are
rendered by `paper-finder figures` into `data/crops/<stem>/qNN_pK.png`
(greyscale PNGs, ~150 MB total, gitignored + vercelignored). Every mark
scheme was landscape (h=595 w=842) until Economics 9708, whose MS is
portrait (h=842 w=595) instead — `marks.py`'s crop x-bounds are a *fraction*
of each page's real width, not fixed pixels, so this needed no per-subject
branch (see Pipeline fixes below). The browse-by-topic flashcard
(served at `/`) shows crops instead of raw text, with a "Show text" fallback
toggle; MCQ answers show just the letter (no mark-scheme crop exists for
them).

`evaluate` ≈ 73% top-1 / 100% top-5 on `eval/validation.tsv` (top-1 falls as
near-duplicate questions across sessions accumulate — a Stage 6 + better-phrases
job). Download mirror: **PapaCambridge**
(`pastpapers.papacambridge.com/directories/CAIE/CAIE-pastpapers/upload/<file>`)
— a missing paper 302s to its homepage, which `download._urllib_fetcher` maps
to not-found.

### Pipeline fixes worth knowing about

These are general, subject-agnostic correctness fixes (not `if subject_code ==`
patches), each verified against a full cross-subject rebuild when made —
`segment.py`/`marks.py` should stay unconditional on subject.

- **Rotated mark-scheme pages** (2026-09-10): `extract.py` maps every line
  bbox through `page.rotation_matrix` + `.normalize()` into the display frame
  `page.rect` already uses, so the segmenter and `figures.py` see coherent
  coords instead of y-coords outside the page height.
- **Three `segment.py` fixes, found via Chemistry** (2026-09-11): (1)
  `content_lines()` truncates a trailing data-sheet/periodic-table appendix
  (`_DATA_SHEET_START`) that was bleeding into the last question's text; (2)
  `looks_like_mcq()` gained an option-letter-frequency fallback
  (`_MIN_OPTION_LETTER_COUNT`) for cover pages with a broken ToUnicode CMap
  where the literal `"multiple choice"` text check misses; (3) `load_lines()`
  re-sorts lines per page by clustering y0 gaps (`_reading_order()`,
  `_ROW_Y_TOLERANCE = 2.0pt`) instead of a fixed `round(y0)` bucket — the
  bucket approach fixed the same issue but broke a Physics mark scheme whose
  landscape Marks column sits ~0.13pt off its row, straddling the rounding
  boundary inconsistently.
- **MCQ "Question Discounted" rows, found via Biology** (2026-09-11):
  `marks.py`'s `parse_mcq_answers()` assumed every answer row was a fixed
  `(number, letter, marks)` triple. When CIE voids an MCQ item after
  publication, its Answer-column cell reads "Question Discounted" instead of
  a letter (with an inconsistent trailing Marks digit), which broke the
  sequence match and silently dropped every later question in that paper. A
  `_DISCOUNTED` regex + resync branch (checking whether the next token is
  already the *following* question's number) fixes this generally.
- **Portrait mark schemes, found via Economics** (2026-09-12): every prior
  subject's MS was landscape (842x595); Economics 9708's is portrait
  (595x842). `segment.py`'s `load_lines()` now exposes each line's page
  `width` (mirroring the existing `height`), and `marks.py`'s
  `_answer_crop_rects()` derives its crop x-bounds as a *fraction* of each
  page's real width instead of the old fixed pixel constants — a no-op for
  every existing 842pt-wide MS.
- **MCQ voided-question free-text notices, found via Economics** (2026-09-12):
  `parse_mcq_answers()` only recognized a voided item written as the fixed
  "Question discounted" cell (see above). One Economics MS voids two items
  with free prose instead ("Due to an issue with question N, the question has
  been removed from the question paper."), wrapped across however many
  physical lines the sentence needs. `_voided_question_end()` resyncs on the
  next question's own label (or the end of the table, for a voided last
  question) rather than pinning down every phrasing CIE might use, accepting
  the gap as a voided-question notice only when a token in it reads like one.
- **Chart y-axis mistaken for a question number, found via Economics**
  (2026-09-12): a data-response chart's y-axis often draws its numeric scale
  as bare small integers in the page's left margin — the same x0/text shape a
  genuine question number has, and Economics's charts are native PDF text,
  not an embedded image, so this is the first subject to hit it. One chart's
  "2" tick collided with `segment_structured`'s expected next number, and a
  chart-legend word right after it satisfied the body-lookahead's prose
  check, cutting a question off mid-chart. `_is_axis_tick_column()`
  generalizes the fix: several bare small integers stacked in the same
  x-column at tight, regular (<60pt) spacing is a signal a genuine structured
  question number never gives (its body always runs to a full page or more).
  Wired into `_is_structured_question_start()` only — an MCQ paper's real
  1..40 sequence can legitimately be this tightly packed.
- **Margin-label reading-order bug, found via Pure Mathematics 3**
  (2026-09-13): a question's margin number label is set in a font tall
  enough that its own y0 can land several points *below* the y0 of its own
  opening line when that line is a short one-liner with inline sub/super-
  script math (e.g. an integral's bounds) — `_reading_order()`'s plain
  top-gap chain then sorted the label after its own prose, so
  `segment_structured` found the label at a later content-line index than
  the sentence and swept that sentence into the *previous* question's block,
  leaving the real question with no text at all (`9709_s20_qp_33.pdf` Q1
  silently absorbing Q2's opening line). `_looks_like_margin_label()` flags a
  bare-number line in the left margin, and only *that* line gets a wider
  same-row tolerance (`_LABEL_ROW_Y_TOLERANCE = 18.0pt`, empirically the max
  genuine same-row gap seen across the whole Pure Maths 3 corpus, still well
  under the ~26pt floor for a genuine different-row gap in this one-question-
  per-page paper style) — ordinary body lines keep the tight
  `_ROW_Y_TOLERANCE`. Two broader fixes were tried and reverted first: (1)
  y-range-overlap clustering, which let a rotated "DO NOT WRITE IN THIS
  MARGIN" sidebar's near-full-page-height bbox bridge every row on the page
  into one, scrambling an Economics MCQ paper's question order; (2)
  pre-filtering `is_noise()` lines before `_reading_order()`, which removed
  the raw "Question" table-header text that `marks.py`'s
  `_answer_table_first_page()` depends on to find a mark scheme's real Q1,
  breaking answer parsing corpus-wide. The kept fix never inspects a line's
  y1/height, only x0/text, so it carries none of the first approach's risk.

**Deployed** to Vercel + Supabase (see `DEPLOY_PROGRESS.md`). The local build
pipeline is unchanged (still SQLite). `paper-finder publish` pushes `qp`
papers + questions (text, flat `answer_text`, `has_figure`, `topic_codes`,
`crop_count`/`answer_crop_count` — no PDFs, no source URLs) to a Supabase
Postgres index; `paper-finder publish-figures` uploads the crop PNGs to a
private Storage bucket. The deployed page (root `app.py` → `create_app()`,
Vercel's FastAPI preset) runs in **cloud mode**: `GET /api/config` hands the
browser the Supabase URL + publishable key, the browser signs in with an
**emailed 6-digit code** (Supabase Auth OTP) and calls RPCs
(`search_questions` / `browse_questions` / `topic_counts`) directly with the
user's JWT. RLS + `EXECUTE` grants restrict everything to `authenticated`;
anon gets nothing. Local `paper-finder serve` (no Supabase env) is untouched
— SQLite, no login, PDF deep-links.

Supabase migrations `0001`-`0014` are applied (project
`gfigwnbkzkgwxcdoqxtz`, ap-south-1; full history in `supabase/migrations/`).
Each subject-addition migration since 0008 is DDL-only: widen the
`questions_topic_codes_valid` CHECK to include the new taxonomy's codes —
`questions.is_mcq`, `topics.subject`, and the RPCs' `subjects`/`topic_subject`
params are already generic (added in 0008/0009) and don't need touching.
`publish` re-upserts `public.topics` from `topics.py` every run.

Cloud is live: **696 qp papers, 10805 questions, 10803 answered**; crop PNGs
for every subject are uploaded to the private `question-crops` bucket (anon
`list`/`sign` both fail — genuinely private). Deployed at
`pastpaperanalyser.vercel.app`.

**Frontend, briefly:** `/` is a topic-browse flashcard page
(`web/static/topics.html` + `topics.js`), `/search` is keyword search
(`index.html` + `app.js`), shared code in `common.js`. The filter bar
(Curriculum / Subject / Paper(s) / Year(s) / Season(s), plus Topic(s) on the
browse page) is a set of custom multi-select dropdowns
(`PF.multiSelect()` in `common.js`) that serialize to the URL as query params
so state is deep-linkable. Curriculum is a real, derived filter as of the
9709 P3/P4/P6 addition (previously inert decoration with one hardcoded
option): `PF.curriculumOf(subject)` in `common.js` maps
`PF.A_LEVEL_SUBJECTS` (Mechanics, Probability & Statistics 2, Pure
Mathematics 3) to `"A"` and everything else to `"AS"`; there's no separate
URL param — `#curriculum` is derived from and kept in sync with the selected
`#subject`, and picking a curriculum that doesn't contain the current subject
switches to the first now-visible subject option. The Paper(s) filter (MCQ
vs Theory) is hidden for every subject except Physics/Chemistry/Biology/
Economics (`PF.MCQ_SUBJECTS`
in `common.js`) since only those have a real MCQ paper. The flashcard reveals a
question/mark-scheme crop pair side-by-side (stacked to one column on MCQs,
which have no mark-scheme crop, and on narrow screens), each crop pan/zoomable
and independently resizable, with a fullscreen mode. Default theme follows
local clock time (light 06:00-18:59, dark otherwise — not OS preference)
unless the user has explicitly toggled it, in which case that choice is
persisted in `localStorage` and wins from then on; the time-based default
re-checks every 5 minutes so an open tab still flips at the boundary.
Background is an interactive WebGL2 dithered wave-field
canvas (`dither.js`, `#bg-dither`, `position: fixed` + `will-change:
transform`/`translateZ(0)` to force its own compositor layer — without that,
mobile browsers can defer repainting a fixed element mid-touch-scroll and only
snap it into place once the finger lifts) behind a liquid-glass
(`backdrop-filter`) header/filter bar/flashcard, with opaque fallbacks when
`backdrop-filter` is unsupported or `prefers-reduced-transparency` is set.
`@media (pointer: coarse)` (touchscreens, not a width breakpoint) gets the same
opaque/no-blur fallback for GPU cost, and `dither.js` turns off the
pointer-ripple uniform there (no real pointer to react to). Pinch-to-zoom on
the crop images is a hand-rolled 2-pointer gesture in `topics.js`
(`makeCropViewer`) rather than the browser's native page-zoom — `touch-action`
on `.card-images` stays `pan-x pan-y` (no `pinch-zoom` component) everywhere so
the browser never starts its own zoom there and our gesture has the touch
events to itself; the desktop drag-pan/wheel-zoom still only engages for
`pointerType === "mouse"`/`"wheel"`, and the "drag to pan/scroll to zoom" hint
hides on `pointer: coarse` since it no longer describes what's available.
`:root[data-theme="dark"]` exists alongside `[data-theme="light"]` (was
missing — dark mode had silently only worked when the OS *also* preferred
dark) so the clock-based default renders correctly regardless of OS theme. See
the files directly for exact values/constants — this file only needs to flag
that these are deliberate, tuned choices, not arbitrary numbers to "clean up".

Next: Stage 6 (semantic search) — see `PLAN.md`.

## Setup

- Python 3.11+ (developed on 3.14). `src/` layout, package `paper_finder`.
- `python -m venv .venv` then `.venv\Scripts\python -m pip install -e ".[dev]"`
  (PowerShell) — installs PyMuPDF + FastAPI plus pytest/ruff and the
  `paper-finder` CLI.

## Build / test / lint

- Tests: `.venv\Scripts\python -m pytest`   Lint: `.venv\Scripts\ruff check .`
  Format: `.venv\Scripts\ruff format .`
- Fetch more papers: `paper-finder download [--dry-run] [--limit N]
  [--subject 9702,9231,9709,9701,9700,9708] [--years 2024-2026] [--sessions s,w,m]
  [--papers 1,2] [--variants 1,2,3,4]` — scope defaults in
  `config.DOWNLOAD_SCOPE`, which is **per-subject** (`{"subjects": {"9702":
  {papers, variants}, "9231": {...}, "9709": {papers: [1, 3, 4, 5, 6],
  variants: [1, 2, 3, 4]}, "9701": {papers: [1, 2], variants: [1, 2, 3, 4]},
  "9700": {papers: [1, 2], variants: [1, 2, 3, 4]}, "9708": {papers: [1, 2],
  variants: [1, 2, 3, 4]}}}` — the 4th variant is a harmless 404 for
  subjects/papers that don't have one); `--papers`/`--variants` apply to
  every selected subject, `--subject` picks which. NOT part of `build`
  (network side effect). Idempotent (skips files already in `data/raw/`).
- Rebuild the whole question bank from `data/raw/`: `paper-finder build`
  (= `ingest` -> `extract` -> `segment` -> `answers` -> `topics` -> `figures`,
  each idempotent). A `db.py` schema change = delete `papers.db` first, then
  `build`.
- Then: `paper-finder search "<a few words>"`, `paper-finder evaluate`,
  `paper-finder questions [--paper qp_12] [--limit N]`, `paper-finder papers`,
  `paper-finder topics` (reload `labels/question_topics.tsv` + print
  per-section counts; also runs as the last `build` step).
- Re-label questions by topic: `paper-finder classify [--only <substr>] [--limit N]
  [--relabel] [--model ...] [--dry-run]` — LLM multi-label, writes
  `labels/question_topics.tsv`. Needs `[classify]` extra (`anthropic`, lazy
  import) + `ANTHROPIC_API_KEY`. NOT part of `build`; skips already-labelled
  questions so an interrupted run resumes.
- Web UI: `pip install -e ".[web]"` then `paper-finder serve [--host 127.0.0.1]
  [--port 8000] [--no-pdfs]`. `fastapi` is a core dep (Vercel needs it); only
  `uvicorn` is the optional `web` extra, lazily imported so every other
  command works without it.
- Render the image crops: `paper-finder figures [--only <substr>] [--limit N]
  [--force] [--dry-run]` — part of `build`, idempotent (skips existing).
- Publish to the deployed Supabase index: `pip install -e ".[publish]"` then
  `paper-finder publish [--dry-run] [--db-url ...]` — reads `SUPABASE_DB_URL`
  (Supabase **session** pooler, port 5432) from the env or `.env` (gitignored).
  Replace-all, one transaction. NOT part of `build`.
- Upload the crops to Storage: `paper-finder publish-figures [--only <substr>]
  [--limit N] [--force] [--dry-run]` — stdlib-urllib PUTs `data/crops/*.png`
  to the private `question-crops` bucket. Needs `SUPABASE_URL` +
  `SUPABASE_SERVICE_ROLE_KEY` in the env or `.env`. Idempotent/resumable
  (lists each paper prefix, skips what is already there — but note
  `--dry-run` always reports the full local count, not what's still missing).
  NOT part of `build`.
- Deploy = Vercel FastAPI preset: root `app.py` exposes `app = create_app()`,
  `requirements.txt` = fastapi only (keeps PyMuPDF out of the deployed import
  chain), `vercel.json` = region `bom1` + a daily `/api/health` cron. Env on
  Vercel: `SUPABASE_URL` + `SUPABASE_PUBLISHABLE_KEY` (both browser-safe).
  Auth = Supabase email OTP; needs custom SMTP + "Magic Link"/"Confirm sign
  up" templates containing `{{ .Token }}` — see `DEPLOY_PROGRESS.md`.
- Local SQLite schema change during early dev = delete `papers.db` and re-run
  `build` (FTS5 virtual table not migrated). The Supabase schema IS migrated
  — edit `supabase/migrations/` and apply via the Supabase MCP / CLI.

## Version control

- Repo: `github.com/Lavastic-Gaming/paper-finder` (private), remote `origin`,
  default branch `main`.
- Commit identity is set locally on this repo (`Lavastic-Gaming` /
  `vihaantalluri@gmail.com`) — do not rely on global git config.
- Workflow: after each meaningful, working change, make a clean commit
  (concise imperative subject, body explaining what and why) and `git push`
  to `origin`. Keep `main` in a working state — the user wants a pushed
  checkpoint at every step so the project is easy to revert.

## Conventions

- `data/raw/` holds downloaded PDFs and is **never edited** — everything in
  `data/processed/` and `papers.db` is regenerated from it.
- CIE past papers are copyright of Cambridge Assessment: this is a private
  study tool; the corpus and extracted question bank are not committed to git
  and the **whole PDFs** are never uploaded anywhere. `.vercelignore` (not
  `.gitignore`) is what keeps `papers.db` / `data/raw/` / `data/crops/` off
  Vercel. The deployed Supabase index (question text + answers, no PDFs) is
  gated behind an email-code login; single-question image crops may go to
  the private `question-crops` Storage bucket behind that same login. Full
  PDFs never leave the machine.
- Code style: ruff (`select = E, F, I, UP, B, DTZ`, line length 100); run
  `ruff format` before committing. Prefer functions that take an explicit
  `db_path` / `raw_dir` (defaulting to `config`) so they stay unit-testable.
- CIE filename grammar and the parser live in `src/paper_finder/filenames.py`
  (`build_filename()` is the inverse of `parse_filename()`); the DB schema
  (all tables, created up front) in `src/paper_finder/db.py`.
- Pipeline modules, in order: `download` (mirror URLs from `DOWNLOAD_SCOPE` ->
  `data/raw/`; stdlib `urllib`, injected `fetcher` for tests) → `ingest`
  (filenames -> `papers` rows) → `extract` (PDF -> text+bbox JSON in
  `data/processed/`, via PyMuPDF, mapping rotated pages into the display
  frame) → `segment` (paper -> `questions`; MCQ and structured, dispatches on
  `looks_like_mcq`; `is_noise` filters page furniture) → `marks` (mark scheme
  -> `answers`; MCQ letter table or structured per-question blocks;
  `_answer_crop_rects` mirrors `segment`'s crop-rect logic for the mark
  scheme) → `topics` (loads `labels/question_topics.tsv` into the
  `question_topics` join table, keyed on `(filename, question_number)` never
  `questions.id` since `segment` reassigns ids every run) → `figures`
  (renders both `questions.crop_rects` and `answers.answer_crop_rects` into
  greyscale PNGs). `classify` (LLM labeller, injectable `Labeller`) and
  `publish`/`publish_figures` (push to Supabase) are network side effects,
  outside `build`. `search` (FTS5 + BM25; `kind`/year/session/variant/subject
  filters; `browse_by_topic` + `topic_counts` for the browse page) and `web`
  (FastAPI app in `web/app.py` + hand-written static frontend in
  `web/static/`, local JSON mode or cloud Supabase-RPC mode picked by
  `GET /api/config`) round it out.
- `symbols.py` repairs Adobe Symbol-font PUA code points from PDF extraction
  — extend `_SYMBOL` if new glyphs show up in a new subject.
