# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project overview

Paper Finder identifies which past exam paper a question came from. A user types a
few words of a question; the tool returns the exact paper (subject, year, session,
paper, variant, question number) and the answer. Future: lookup from a photo of a
question.

The **UI is branded "Paper Analyser"** (the `<h1>`, `<title>`s and footer on both
pages, as of 2026-09-09); the Python package (`paper_finder`), the CLI
(`paper-finder`), the repo and this file keep the original name. Browser-tab
icon: `web/static/favicon.svg` (a lined sheet of paper in `--primary` blue),
linked from both HTML `<head>`s as `rel="icon" type="image/svg+xml"`.

Personal / extracurricular project. Exam board: **Cambridge International (CIE)**
AS & A Level. Built one stage at a time — see `@PLAN.md` for the full roadmap,
tech stack, data reference, and database schema.

## Status

Stages 1-5 + 7 + 7b (Vercel/Supabase deploy) done + Stage 4 downloader (as of
2026-09-06). Stage 6 (semantic search) still open.

**The corpus is now four subjects / six topic taxonomies** (9701 added
2026-09-11), distinguished by `papers.subject_name`:

- **Physics** — 9702 2020-2026 (`m20`..`m26` Feb/March, `s20`..`s26`,
  `w20`..`w25`), Papers 1 & 2, variants 1-4 where they exist (s25/w25/s26 have a
  4th variant `qp_14/24`; the "m" series is variant 2 only — `9702_m2X_qp_12/22`;
  `9702_s26_qp_21` is excluded via `config.EXCLUDE_FILENAMES` — its mark scheme
  was never published, so every question showed unanswered)
  = 97 question papers, 2285 questions, 2285 answers linked, ~640 flagged
  `has_figure`, all 2285 tagged into the 11 CIE 9702 AS syllabus sections
  (`s01`..`s11`, multi-label, 155 multi-section).
- **Further Pure Mathematics** — 9231 Paper 1, variants 1-3, `s20`..`s26` +
  `w20`..`w25` (no `m` series, no `w26`) = 39 question papers, 273 questions,
  273 answers linked, tagged into the 7 syllabus §1 sections (`fp1`..`fp7`).
- **Further Probability & Statistics** — 9231 Paper 4, same sessions/variants =
  39 question papers, 237 questions, 237 answers linked, tagged into the 5
  syllabus §4 sections (`fs1`..`fs5`).
- **Pure Mathematics 1** — 9709 Paper 1, variants 1-3, `s20`..`s26` +
  `w20`..`w25` + `m20`..`m26` (Feb/March variant 2 only) = 46 question papers,
  502 questions, 501 answers linked, tagged into the 8 syllabus §1 sections
  (`pm1`..`pm8`: Quadratics / Functions / Coordinate geometry / Circular
  measure / Trigonometry / Series / Differentiation / Integration).
- **Probability & Statistics 1** — 9709 Paper 5, same sessions/variants = 46
  question papers, 307 questions, 307 answers linked, tagged into the 5
  syllabus §5 sections (`ps1`..`ps5`: Representation of data / Permutations and
  combinations / Probability / Discrete random variables / The normal
  distribution).
- **Chemistry** — 9701 Papers 1 & 2, variants 1-4 where they exist, `s20`..`s26`
  + `w20`..`w25` + `m20`..`m26` (Feb/March variant 2 only) — one taxonomy spans
  both papers (like Physics), since both examine the full AS syllabus = 98
  question papers (49 Paper 1 MCQ + 49 Paper 2 structured), 2186 questions
  (1960 MCQ + 226 theory), 2185/2186 answers linked, tagged into the 22
  syllabus sections (`ch01`..`ch22`, built from the syllabus PDF pages 16-38).
  `9701_s24_qp_22.pdf` question 5 (structured) has no linked answer — its mark
  scheme PDF on the mirror genuinely ends after question 4(e)(ii) ("Page 13 of
  13") with no question 5 content at all, confirmed against sibling variants
  `9701_s24_ms_21/23` which both do cover question 5; unlike the whole-paper
  `9702_s26_qp_21` exclusion, this is a single missing answer in an otherwise
  complete paper, so the paper stays in the corpus rather than being added to
  `config.EXCLUDE_FILENAMES`.

9231 total: **78 QP papers, 510 questions, 510/510 answers linked** across 13
sessions (`s20`-`s26`, `w20`-`w25`). 9709 total: **92 QP papers, 809 questions,
808/809 answers linked**, sessions `m20`-`m26` + `s20`-`s26` + `w20`-`w25` (no
`w26`; `9709_s26_qp_12` is a 4-page preview PDF on the mirror — 9 questions
short). Both 9231 papers and both 9709 papers are structured/theory (none is
MCQ). 9701 total: **98 QP papers, 2186 questions, 2185/2186 answers linked**
across 21 sessions (`m20`-`m26`, `s20`-`s26`, `w20`-`w25`); unlike 9231/9709,
9701 Paper 1 is MCQ and Paper 2 is structured/theory (the second subject,
after Physics, where `is_mcq` varies within a subject). Taxonomies live in
`src/paper_finder/topics.py` as six `Taxonomy`
instances (`TAXONOMIES`); `taxonomy_for(subject_code, paper)` /
`taxonomy_by_name(subject_name)` resolve one. Labels: `labels/question_topics.tsv`,
loaded by `paper-finder topics` (prints a per-subject block).

The 9702 2024-2026 papers were labelled by `paper-finder classify`; the 9702
2020-2023 ones (1311 questions), **every 9231 question** (510), **every 9709
question** (809) and **every 9701 question** (2186) were labelled without an
API key — 9702 Paper 1 MCQs by their position in the paper (Paper 1 tracks the
syllabus-section order closely, ~80-85% accurate); 9701 Paper 1's 1960 MCQs by
a fixed position-in-paper block (all 49 papers have exactly 40 questions, so
this maps question-number ranges to `ch01`..`ch22` by a heuristic weighting of
each section's typical share of the paper, applied identically to every P1
file — not a per-paper read, so treat it with the same ~80-85%-ish confidence
as the 9702 P1 heuristic); 9702 Paper 2 / all 9231 / all 9709 / 9701 Paper 2's
226 structured questions by reading each question — refine any `llm` row later
with `paper-finder classify --relabel` once `ANTHROPIC_API_KEY` is set
(`classify.py` is not yet taxonomy-aware — Commit 9, deferred).
Every question also has a rendered **image crop** of itself
(`questions.crop_rects`/`crop_count`, set in `segment`) and, for structured
questions, an **image crop of its mark scheme** cropped from the `ms` PDF
(`answers.answer_crop_rects`/`answer_crop_count`, set in `marks`; 324 Physics +
510 9231 + 807 9709 + 225 Chemistry answers). 9231, 9709 **and** 9701 mark
schemes are **landscape** like Physics (h=595 w=842), so `marks.py` crop
geometry is unchanged;
`_bare_label_number` handles the part-less questions (a bare number in the
Question column). `paper-finder figures` renders both — question PNGs into
`data/crops/<qp_stem>/qNN_pK.png` plus mark-scheme PNGs into
`data/crops/<ms_stem>/qNN_pK.png` (9709 alone = ~1330 qp + ~1620 ms) — ~150 MB,
gitignored + vercelignored. The
browse-by-topic flashcard (served at `/`) shows the question crop instead of
the extracted text, and on reveal shows the mark-scheme crop (with a "Show
text" toggle) instead of the flattened mark-scheme text (Stage 2).
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

Fixed (2026-09-10): **landscape/rotated** Paper 2 mark-scheme pages (e.g.
`9702_s24_ms_21/22/23`) used to extract with y-coords outside the page height,
so `marks.py` linked 0 answers for them. `extract.py` now maps every line bbox
through `page.rotation_matrix` (then `.normalize()`) into the rotated/display
frame that `page.rect` and `page.get_pixmap(clip=)` already use, so both the
segmenter and `figures.py` see coherent coords. `9702_s26_qp_21`'s mark scheme
was never published to the mirror (every question unanswered), so the paper is
now listed in `config.EXCLUDE_FILENAMES` — `download` will not fetch it and
`ingest` skips it and prunes any existing row.

Fixed (2026-09-11), while adding Chemistry: three `segment.py`
correctness fixes, discovered by real 9701 PDFs but verified against a full
cross-subject rebuild to rule out regressions on Physics/9231/9709. (1)
`content_lines()` now truncates at a trailing data-sheet/periodic-table
appendix (`_DATA_SHEET_START`), which 9701 question papers append and which
was otherwise bleeding into the last question's text. (2) `looks_like_mcq()`
gained an option-letter-frequency fallback (`_MIN_OPTION_LETTER_COUNT` = 20
occurrences of a bare "A"/"B"/"C"/"D" line) for a handful of 9701 Paper 1 PDFs
(`9701_s23_qp_11/12/13`, `9701_s26_qp_14`, `9701_w23_qp_11`) whose cover page
uses a font with a broken/shifted ToUnicode CMap, so the literal-text
`"multiple choice"` check missed them and they were mis-routed through
`segment_structured()`. (3) `load_lines()` gained a `_reading_order()` pass:
PyMuPDF's own line order isn't always strict top-to-bottom/left-to-right — a
differently-encoded font run (e.g. a margin question number) can land out of
visual order in the JSON even when its y0 says it belongs earlier. Lines are
now re-sorted per page by clustering on y0 gaps (`_ROW_Y_TOLERANCE` = 2.0pt)
rather than a fixed `round(y0)` bucket — a first attempt using the bucket
approach fixed the same 9701 papers but broke `9702_s20_ms_12` (Physics), whose
landscape Marks column sits ~0.13pt off its row's Question/Answer columns, a
sub-pixel offset that straddled the integer-rounding boundary inconsistently
row to row. All three fixes are general pipeline correctness fixes, not
Chemistry-specific patches.

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
+ `0007_answer_crops.sql` (adds `questions.answer_crop_count`, recreates
`browse_questions` / `search_questions` with an `answer_crop_count` column; **no**
bucket change — the `ms_` crop folders reuse the `question-crops` bucket and its
0005 `authenticated`-read policy; `publish` carries `answer_crop_count`,
`publish-figures` uploads the `ms_` PNGs with no code change).
+ `0008_further_maths.sql` (adds `questions.is_mcq boolean`; widens the
`questions_topic_codes_valid` CHECK to the union `s01..s11,fp1..fp7,fs1..fs5`;
adds `topics.subject text`; drop-then-recreates `search_questions` /
`browse_questions` / `topic_counts` with a `subjects text[]` param
(`p.subject_name = any(subjects)`), and `topic_counts` also a `subject text`
param filtering `public.topics`; **fixes the `kind` bug** — the mcq/theory
predicate is now `qu.is_mcq` / `not qu.is_mcq`, not `p.paper = 1`; `publish`
carries `is_mcq` and upserts `topics.subject`).
+ `0009_topic_counts_subject_param.sql` (renames `topic_counts`'s scalar
`subject` param to `topic_subject` — it collided with the `public.topics.subject`
column it was compared against, so in the `language sql` body `t.subject =
subject` bound to the column and the topic-list filter was a no-op (every
subject showed all 23 topics in the dropdown). `topics.js` `fetchCounts` now
passes `topic_subject`).
+ `0010_maths_9709.sql` (adds Mathematics 9709 Papers 1 & 5 as the subjects
`Pure Mathematics 1` (`pm1`..`pm8`) and `Probability & Statistics 1`
(`ps1`..`ps5`); the only DDL is widening the `questions_topic_codes_valid` CHECK
to the union of all five taxonomies — `is_mcq`, `topics.subject` and the RPC
`subjects`/`topic_subject` params already existed from 0008/0009, and `publish`
reseeds `public.topics` from `topics.py`).
+ `0011_chemistry_9701.sql` (adds Chemistry 9701 Papers 1 & 2 as the subject
`Chemistry` (`ch01`..`ch22`, one taxonomy spanning both papers, like Physics);
the only DDL is widening the `questions_topic_codes_valid` CHECK to the union
of all six taxonomies — `is_mcq`, `topics.subject` and the RPC
`subjects`/`topic_subject` params already existed, and `publish` reseeds
`public.topics` from `topics.py`).
Project ref `gfigwnbkzkgwxcdoqxtz` (ap-south-1). Migrations 0001-0011 applied.

`/api/search` + `/api/browse` + `/api/topics` (local) and the
`search_questions` / `browse_questions` / `topic_counts` RPCs (cloud) take a
`kind` filter (`all` / `mcq` / `theory` — **both** local and cloud now on
`questions.is_mcq`, since 0008); the **Paper(s)** filter drives it, and it is
hidden off every subject except Physics and Chemistry — the only two with a
real MCQ paper (`common.js` `PF.MCQ_SUBJECTS` / `PF.hasMcqPapers()`, which
`app.js`/`topics.js` use in place of the old `=== DEFAULT_SUBJECT` check).
They also take a
`subject` / `subjects` param (`papers.subject_name`) — **search works one
subject at a time** (no cross-subject search).
The **filter bar** (`.filterbar`, on both
`index.html` and `topics.html`, styled from the `Ref Photos/` mock):
a context row of **Curriculum** / **Subject** dropdowns — `#curriculum` still
one option, but **`#subject` is now live** with six real options (Physics /
Further Pure Mathematics / Further Probability & Statistics / Pure Mathematics
1 / Probability & Statistics 1 / Chemistry, default Physics;
`app.js` / `topics.js` `DEFAULT_SUBJECT`, `?subject=` URL token only when
non-default, changing it re-scopes search / clears the topic pick) — above
three real scope filters — **Paper(s)** (`#f-paper`, in `#fb-paper` wrapper so
JS can hide it, "Paper 1 · MCQ" /
"Paper 2 · Theory" — CIE Physics has no Paper 3/4; this is the MCQ-vs-theory
split, **not** a variant filter), **Year(s)** (`#f-year`), **Season(s)**
(`#f-season`, `s`=May/June `m`=Feb/March `w`=Oct/Nov) — plus, on the browse page
only, the single-select **Topic** (`#f-topic`) native `<select>`. Paper/Year/Season
are each a **custom multi-select dropdown** (`<div class="multiselect">` = a
`.ms-toggle` button + a hidden `.ms-panel` of checkbox `<label>`s), upgraded by
`PF.multiSelect()` in `common.js` (open/close, click-outside, Escape, a value
label; the checkboxes are real so their `change` bubbles to the root and the api
is stashed on `root._ms` for deep-link restore). `app.js` `picked()` /
`topics.js` `wireScopeGroup()` read the ticked boxes; nothing ticked = no
restriction on that axis. Year/Season serialize to the URL as comma lists
(`?year=2025,2026&season=s,w`); the Paper box's ticked values (`1` / `2`) go
through `PF.paperKind()` → the `kind` arg (`mcq` / `theory` / `all` for both or
neither), and `?paper=1` in the URL. A **"Clear all"** link (`#clear-all`) sits below the
fields on both pages and resets every filter. There is no corpus-freshness badge.
`.filterbar` is `z-index: 5` (and `form#search` / `.tray` `z-index: 6`) so an
open `.ms-panel` — or the recent-search dropdown — layers over the flashcard /
results below, while staying under the sticky header (`z-index: 10`).
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
fitting syllabus sections for its subject (`src/paper_finder/topics.py` = six
`Taxonomy` instances — 11 `s01`..`s11` for Physics, 7 `fp1`..`fp7`, 5
`fs1`..`fs5`, 8 `pm1`..`pm8`, 5 `ps1`..`ps5`, 22 `ch01`..`ch22` for Chemistry
(58 topics total); `TAXONOMIES`,
`ALL_TOPICS`, `taxonomy_for`, `taxonomy_by_name`;
`labels.parse_labels` validates each row against its own subject's taxonomy, not
the union; `labels/question_topics.tsv` = hand-committable, no CIE text — just
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
flashcard deck: one card at a time, ◂ ▸ / ←→ to move, and a **`#reveal`
toggle** on the right of the `.card-head` row (the site's solid-accent button
when hidden, a quiet outline when shown) — or the space bar — reveals **and
re-hides** the answer (`topics.js` `toggleAnswer`; `#card-answer` is `hidden`
until revealed). **Reveal splits the card into two columns** — question crop
left, mark-scheme crop right, each with its own scroll (`.card.is-revealed
.card-body` = a `1fr 1fr` grid; stacks to one column under 860px, and under
640px inside fullscreen). **MCQs stack instead of splitting** — an MCQ answer
is just a letter, no mark-scheme crop, so a side-by-side column would waste
half the card on it; `topics.js` toggles a `.no-answer-crop` class on `#card`
whenever `answer_crop_count === 0` (the same field that already picks the
letter-vs-crop answer rendering), and `.card.is-revealed.no-answer-crop
.card-body` (+ the fullscreen equivalent) forces `display: block` /
`flex-direction: column` so the answer renders full-width below the question,
in and out of fullscreen. **The question and mark-scheme crops are pan/zoom
surfaces** (`topics.js` `makeCropViewer(imagesEl, storeKey)`, one per
`.card-images`): drag to pan (mouse `pointer` events → scroll, at `PAN_SPEED`
= 1.6× the raw pointer movement so a short drag covers more ground; touch
keeps native scroll via `touch-action`), wheel to zoom toward the pointer,
double-click to reset, `+` `-` `0` keys zoom the question. The wheel handler
scales the zoom exponent by `(min(|deltaY|, 2×WHEEL_ZOOM_UNIT) /
WHEEL_ZOOM_UNIT) ** WHEEL_ZOOM_CURVE` instead of applying a flat `ZOOM_STEP`
per event — a mouse notch (`deltaY` ≈ 100, ratio 1) still zooms exactly one
full `ZOOM_STEP` regardless of the curve, but a touchpad's many small-`deltaY`
events (two-finger scroll) zoom by that fraction of a step raised to
`WHEEL_ZOOM_CURVE` (0.6, so < 1 biases small deltas up) rather than linearly,
which was the fix for touchpad zoom feeling wildly oversensitive (flat
per-event step) and then, after that first pass, too flat (strictly linear
scale-down); 0.6 was tuned to feel "a bit more sensitive" than linear while
leaving the mouse-notch anchor untouched. Zoom scales the
crop `<img>`s via an `--img-zoom` custom property on the container
(`.card-image { width: calc(100% * var(--img-zoom)) }`), 0.3×–6×, persisted
per column (`localStorage` `paper-finder.qzoom` / `.azoom`); the box starts at
`height: 70vh`. A zoomed-out crop (< 100%) is **centred with equal gaps on
both sides** — `.card-image` carries `margin-inline: auto`, a flexbox
auto-margin that is inherently "safe": it only absorbs positive leftover
space, so it resolves to `0` (normal flow-start alignment) the moment the
crop is zoomed in and overflows, leaving the drag-pan/wheel-zoom scroll math
(which assumes the un-scrolled left/top edge sits at `scrollLeft/scrollTop =
0`) untouched. The viewer drives whichever element actually scrolls —
`.card-images` itself normally, its scrolling ancestor (the column /
`.card-body`) in fullscreen where `.card-images` is `overflow: visible`. A
`.crop-hint` (`0.85rem`, sized up from an initial `0.72rem` — too small to
read comfortably) sits above each. Each box has its own **resize handle**
below it — a full-width `.crop-resize` drag bar (`topics.js`
`makeResizeHandle(handleEl, imagesEl, storeKey)`, `#q-resize`/`#a-resize`)
with a large `.crop-resize-grip` pill, replacing the native `resize:
vertical` corner grip (too small to find/grab reliably); the grip is visibly
accent-tinted (`var(--rule)`, `4.5rem × 8px`) even at rest, not just on
hover/drag (`var(--primary)`, widening to `5.5rem`) — an initial version that
only tinted on hover read as invisible until you happened to hover it.
Pointer-drag sets `imagesEl.style.height` directly (clamped `160px`–92vh),
double-click resets it, persisted per column (`localStorage`
`paper-finder.qheight` / `.aheight`) and hidden in fullscreen
(`#card.card--fs .crop-resize { display: none }`, since the column height
there is fixed to the viewport). `.card` scroll areas get accent-tinted
scrollbars (`scrollbar-color: var(--rule)` + a `::-webkit-scrollbar`
fallback). A **fullscreen toggle** (`#fullscreen-toggle` in `.card-nav`, or
press `f`) blows the current card up via the Fullscreen API on `#card`
(`topics.js` `toggleFullscreen` / `syncFullscreenUI` add `.card--fs` on
`fullscreenchange`); the button carries a visible `#fullscreen-toggle-label`
span next to its icon (was icon-only, easy to miss) reading "Fullscreen" /
"Exit fullscreen" in step with `.card--fs`, and `.card-fs-btn` widened
(`gap` + bigger padding/font) to fit it. Fullscreen keeps the same 2-col
reveal but swaps the page scroll for a per-column one so the nav/head stay pinned.
`syncFullscreenUI` also saves any manually-resized inline height on entry
(`imagesEl.dataset.savedHeight`, then clears the inline style so the
fullscreen `height: auto` rule applies) and restores it on exit — otherwise a
resized box's inline height would beat the fullscreen CSS rule and break the
per-column scroll. Prev/Next (buttons or arrow keys), Reveal and zoom keep
working — the whole `#card` subtree is what goes fullscreen. `.card-fs-btn`
uses the solid accent `--btn` fill (the same fill as the reveal/submit
buttons) rather than the translucent `--surface-strong`/`--glass` used
elsewhere on the card, so it stays legible/solid against the animated dither
backdrop showing through the liquid-glass `.card` panel behind it; hover is a
`box-shadow` escalation, active adds `translateY(1px)` like the other solid
buttons. `.crop-resize` is invisible at rest — just a floating solid-accent
`.crop-resize-grip` pill (with the "Resize" label inside it) centred in the
full-width drag hit area; while actively dragging (`.crop-resize.is-active`,
toggled by `topics.js` `makeResizeHandle` on pointerdown/up) the hit area
itself becomes visible as the same liquid glass as the rest of the card
(`--glass`/`--glass-backdrop`) rather than a solid fill, so it reads as part
of the glass panel; the pill stays solid-accent throughout so it's always
legible against whatever is behind it. **Topic(s) is a `.multiselect` dropdown**
(`#f-topic`, same `PF.multiSelect()` pattern as Paper(s)/Year(s)/Season(s) — a
`.ms-toggle` button + checkbox `.ms-opt` rows in a `.ms-panel`) in the filter
bar (after Season(s)); `topics.js` `renderTopicOptions()` rebuilds the panel's
checkboxes from `topic_counts` on every `refresh()` (`"<n>. <name> (<count>)"`,
zero-count options disabled unless already picked), then calls
`topicEl._ms.setValues([...selected])` to re-tick the survivors and repaint
the toggle's label. Each checkbox's `data-short` is just its section number,
so picking several keeps the closed toggle compact ("1, 3, 5") instead of
concatenating full names. `PF.multiSelect()` itself was changed to re-query its
panel's checkboxes on every call (`values()`/`setValues()`/`paintLabel()`)
rather than a one-time snapshot, since the topic panel's checkboxes -- unlike
Paper/Year/Season's static ones -- are rebuilt from scratch each refresh. The
deck stays hidden ("Choose one or more topics to start revising.") until at
least one is picked; `selected` is a `Set` of any size (was clamped to one
code) and `browse_by_topic` already unioned however many codes it was given
(newest-paper-first, a question tagged with more than one pick counted once).
`?topics=a,b` deep links now restore both instead of clamping to the first.
Local endpoints `/api/topics` +
`/api/browse` (501 in cloud mode); cloud uses the `browse_questions` /
`topic_counts` RPCs. The corpus line under the `<h1>` shows just
`"<n> questions · <n> question papers"` (the subject name was dropped).

**Stage 2 done — local AND cloud, verified in-browser.** The flashcard shows a
PNG crop of the real question (`crop_count > 0` → image; `= 0` → the old text +
`◧` note). `web/app.py` `/figure/{filename}/{crop}` serves `data/crops/` behind
the same `serve_pdfs` flag as `/pdf/` (`resolve_crop` = `resolve_pdf`'s
round-trip check + a `^q\d{2}_p\d\.png$` whitelist; accepts `qp` **and** `ms`
filenames); `result_payload` adds `crop_base` (qp) + `ms_crop_base` (qp filename
with `_qp_`→`_ms_`, only when `answer_crop_count`). `topics.js` `renderCropImages`
swaps `<img>`s idempotently (guarded on `filename#qnum`), loads them **eagerly**
(the card is below the fold on load — lazy images there never enter view), offers
a **"Show text"** toggle (`localStorage` `paper-finder.showtext`), and in cloud
mode mints batched signed Storage URLs. `PF.cloudRow` must carry
`question_number` — `topics.js` builds the crop object path from it
(`q{NN}_p{k}.png`); without it cloud paths were `qundefined_p1.png`.

**Mark-scheme crop on reveal.** `#card-answer` (itself `hidden` until the
`#reveal` toggle is on) holds `#answer-images` + `#answer-show-text` + an
`#answer-body` slot (the only part `renderCard` wipes each pass — the
images/toggle live outside it so they don't flicker on toggle/prefetch). `renderAnswerImages` / `answerCropUrls` / `renderedAnswerKey`
mirror the question side but off `ms_crop_base` (local) / a signed
`question-crops` URL under the `_ms_` stem (cloud); `paper-finder.showanswertext`
persists the toggle. An `<img>` load failure or no resolved URL falls back to
`PF.answerBlock` for that one card. MCQ answers (`answer_crop_count = 0`) keep
the single letter, no image, no toggle.

**Cloud live:** 0005 + 0007 + 0011 applied; `publish` run (all four subjects /
six taxonomies — 365 qp papers, 5790 questions, 5788 with an answer, cloud
`crop_count` on all, `answer_crop_count` > 0 where the ms was published);
`publish-figures` uploaded the question + `ms_` PNGs (Chemistry: 3106 PNGs
across 147 papers) to the private `question-crops`
bucket (anon `list` → `[]`, anon `sign` → 404 — genuinely private).
`publish-figures` needs `SUPABASE_URL` + `SUPABASE_SERVICE_ROLE_KEY` — both now
in `.env` (`SUPABASE_URL` is the browser-safe project URL, not a secret).

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
  [--subject 9702,9231,9709,9701] [--years 2024-2026] [--sessions s,w,m] [--papers 1,2]
  [--variants 1,2,3,4]` — scope defaults in `config.DOWNLOAD_SCOPE`, which is now
  **per-subject** (`{"subjects": {"9702": {papers, variants}, "9231": {...},
  "9709": {papers: [1, 5], variants: [1, 2, 3]}, "9701": {papers: [1, 2],
  variants: [1, 2, 3, 4]}}}`);
  `--papers`/`--variants` apply to every selected subject, `--subject` picks
  which. NOT part of `build` (network side effect). Idempotent (skips files
  already in `data/raw/`).
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
- Render the image crops: `paper-finder figures [--only <substr>]
  [--limit N] [--force] [--dry-run]` — PyMuPDF renders `questions.crop_rects`
  (from the `qp`) and `answers.answer_crop_rects` (from the `ms`) into
  `data/crops/<stem>/qNN_pK.png` (greyscale, 2x). Part of `build` (offline);
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
  JSON in `data/processed/`, via PyMuPDF; maps each line bbox through
  `page.rotation_matrix` so rotated pages land in the display frame), `segment`
  (paper -> questions; MCQ and
  structured — `_STRUCTURED_START_MAX_Y = 0.88` (was 0.18, then 0.45) so a Maths
  question can start well down a shared page (9709 Stats ~0.51), a
  `_STRUCTURED_START_TOP_OF_PAGE` fast-accept for a sequence-continuing margin
  number at the top of a fresh page (9709 Pure Maths opens questions with a
  full-page graph the body-lookahead can't see past), `_QSTART` matching
  "10 The equation..." so a two-digit number sharing its line with the opening
  words (2024+ 9709 papers) is still a start, plus a body-lookahead scan past a
  figure/formula, and `_is_stray_page_number` drops a bare margin number that is
  really a footer),
  `marks` (mark scheme -> answers; MCQ letter table or structured
  per-question blocks; `_bare_label_number` + `_answer_table_first_page` pick up
  9231's part-less questions (a bare number in the Question column, gated on the
  "Question" table header and the expected-sequence counter);
  `_answer_crop_rects` records `answers.answer_crop_rects` /
  `answer_crop_count` — a landscape-MS mirror of `segment._crop_rects`
  (9231 mark schemes are landscape, same as Physics)),
  `topics` (load `labels/question_topics.tsv` -> the
  `question_topics` join table; keyed on `(filename, question_number)`, never
  `questions.id` — `segment` reassigns ids every run; orphan labels reported not
  fatal), `classify` (LLM multi-label -> the TSV; injectable `Labeller`, batched,
  lazy `anthropic`; network side effect, out of `build`),
  `figures` (`questions.crop_rects` (from the `qp`) + `answers.answer_crop_rects`
  (from the `ms`, same stem `_qp_`→`_ms_`) -> greyscale PNG crops in `data/crops/`
  via PyMuPDF; part of `build`, idempotent, `crop_path` derives `qNN_pK.png` from
  `(stem, qnum, ordinal)`; rotated pages render fine now that `extract` maps
  coords into the display frame; never imported from
  `web/app.py`), `search` (FTS5 + BM25;
  `kind=all|mcq|theory` filter + `_paper_scope()` year/session/variant/**subject**
  filter (`subjects` -> `p.subject_name IN (...)`); `browse_by_topic` +
  `topic_counts` (the latter takes `subject` -> only that taxonomy's topics, via
  `taxonomy_by_name`) for the browse page;
  `SearchHit` carries `subject_code` + `topic_codes` + `crop_count` +
  `answer_crop_count`),
  `evaluate`,
  `web` (`create_app(db_path, raw_dir, crop_dir, serve_pdfs)` — FastAPI + a hand-written
  static page in `web/static/` (frosted-panel UI: token-driven `style.css`,
  theme-aware, full-bleed, IBM Plex type, a light-blue accent
  (`--primary` `#2563eb` light / `#60a5fa` dark, `--btn` / `--accent-ink`
  siblings; `--hl-bg` stays amber — highlighter, not chrome); opaque +
  reduced-transparency fallbacks). **Default theme is light**, not the OS
  preference — the pre-paint inline `<script>` in each HTML `<head>` sets
  `data-theme="light"` unless `localStorage["paper-finder.theme"]` was
  explicitly saved as `"dark"` by the header toggle; `common.js`'s
  `themeToggle` no longer tracks `prefers-color-scheme` at all, since
  `root.dataset.theme` is now always already set by the time it runs. The
  header's `#theme-toggle` button (sun/moon icon, `#theme-toggle-label` span)
  names the mode a click switches **to**, not the current one ("Dark mode"
  while in light theme, "Light mode" while in dark) — sized to match the
  fullscreen/reveal buttons (padding + icon bump 18px → 20px) rather than the
  old icon-only square. No page
  taglines — just the `<h1>` + the `#corpus` count line. The **header, search
  tray, filter bar and flashcard**
  are true "liquid glass": `--glass: transparent` (zero fill), and
  `--glass-backdrop` = `url(#glass-refraction) saturate(1.6) brightness(1.05)
  blur(2px)` — an inline SVG `feTurbulence` + `feDisplacementMap` filter
  (`#glass-refraction`, duplicated into both HTML `<body>`s inside `svg.glass-defs`)
  that *bends* the dot grid behind the pane. The **header** (`position:
  sticky`, fades via `.is-hidden` on scroll, `common.js`
  `revealHeaderOnlyAtTop`) hides with an **opacity-only** fade — it used to
  also slide via `transform: translateY(-100%)`, but animating `transform` on
  an element whose `backdrop-filter` runs that same SVG `feDisplacementMap`
  made Chromium briefly flash the raw, unfiltered dither wave (dark "waves")
  at the top edge while the filter's sample region caught up with the moving
  box each frame; fading in place removes the moving box entirely. `.card` (the topic-browse
  flashcard) moved onto this same `--glass`/`--glass-backdrop` pair (was a
  frosted-opaque `--surface-strong` + `blur(var(--blur-thick))` panel); its
  fullscreen state (`#card.card--fs`) keeps its own opaque `var(--bg)` ground,
  unaffected, since a fullscreened element needs a real backdrop against the
  browser's black fullscreen background. `--glass` falls back to an opaque
  fill and `--glass-backdrop` to `none` in the no-`backdrop-filter` /
  `prefers-reduced-transparency` blocks (so `.card` degrades the same way the
  header/tray/filterbar already did). Other content panels (`#gate`, search
  results) still keep `--surface` / `--surface-strong`. Deployed at
  `pastpaperanalyser.vercel.app`. The backdrop the glass refracts is an
  **interactive dithered wave field** (2026-09-12, replacing the earlier dot
  grid) — `#bg-dither` canvas (first child of `<body>`, `z-index: -1`,
  `pointer-events: none`) driven by `dither.js`, a dependency-free **WebGL2**
  port of react-bits' `<Dither />` (no react/three/`@react-three/fiber`/
  `postprocessing` — those are React-only and this is a no-build vanilla-JS
  site; the fractal-noise wave generation and the 8x8-Bayer ordered-dither
  post-process are fused into one fragment shader on a `gl_VertexID`-only
  fullscreen triangle, replacing the upstream's react-three-fiber +
  postprocessing two-pass pipeline since there's no other 3D content to
  composite with here). Tuned per request: `waveSpeed` started at 0.03, then
  slowed twice more to `0.015` and then `0.01`; `colorNum` 6 (raised from the component's
  default of 4), `waveFrequency` 3, `waveAmplitude` 0.3, `mouseRadius` 0.3,
  `pixelSize` 2, mouse interaction on. Colour comes from two theme-aware
  custom properties instead of component props: `--dither-wave` (`#1d4ed8` in
  light — the app's own `--btn` blue, darker/more saturated for contrast
  against the cream ground, per request — `#93c5fd` lighter blue in dark for
  contrast against the navy; **not** the same value across themes, unlike the
  background) and `--dither-bg` (`#f4edcf` system light / `#fcf4d9` explicit
  light — both match `--bg`, a Solarized/yellow cream — and `#0a1a33` navy in
  dark). `--dither-wave` is re-declared in `:root[data-theme="light"]` (not
  just the base `:root`) so an explicit light choice still gets the darker
  wave on a dark-OS machine, where the `@media (prefers-color-scheme: dark)`
  block would otherwise win that property. The canvas backing buffer is fixed at
  1x regardless of devicePixelRatio (matches the upstream component's own
  `dpr={1}`) since the noise loop runs per pixel every frame and pixelSize
  already chunks output pixels, so a retina buffer would be 4x the cost for
  no visible gain. `prefers-reduced-motion` → one static frame, no pointer
  reactivity, no rAF loop; pauses while the tab is hidden; re-reads the CSS
  colours on a theme change (same lifecycle shape `dotgrid.js` used). It
  replaced the old static `--blob-*`
  radial-gradient mesh (`body::before`, removed). `#card.card--fs` (the
  fullscreened flashcard) and `#card::backdrop` use `--dither-bg`, not `--bg`,
  as their ground — the two are identical in both light themes, but in dark
  mode `--bg` is a flatter near-black (`#0b0e13`) while `--dither-bg` is the
  wave field's own navy (`#0a1a33`), so fullscreen now matches the animated
  backdrop instead of reading as a separate, darker surface. The styled-select
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
