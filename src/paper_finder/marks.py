"""Extract answers from mark schemes and link them to questions.

* **Multiple choice** -- a Question / Answer / Marks table read as
  ``(question_number, letter, marks)`` triples in sequence.
* **Structured** -- answer blocks keyed by part label (``1(a)``, ``1(b)(i)`` ...).
  Blocks are grouped by their question number and stored as one answer text per
  question (the whole mark scheme for that question).

Each answer is matched to the question paper that shares the mark scheme's
subject/year/session/paper/variant.
"""

from __future__ import annotations

import json
import re
from collections import Counter
from dataclasses import dataclass, field
from pathlib import Path

from paper_finder import config
from paper_finder.db import connect, init_db
from paper_finder.segment import MCQ_QUESTION_COUNT, is_noise, load_lines, looks_like_mcq

_LETTER = re.compile(r"^[A-D]$")
_SMALL_INT = re.compile(r"^\d{1,2}$")
# CIE occasionally voids an MCQ item after publication (a flawed question with
# no single correct answer) and marks its Answer-column cell "Question
# discounted" instead of a letter -- every candidate is awarded the mark.
# Whether a Marks-column digit follows is inconsistent between papers, so
# parse_mcq_answers() disambiguates by checking whether the next token is
# already the following question's number rather than assuming a fixed
# triple width for this one row.
_DISCOUNTED = re.compile(r"^question\s+discounted$", re.IGNORECASE)
# CIE also voids a question with free-text prose instead of the fixed
# "Question discounted" cell -- e.g. "Due to an issue with question 22, the
# question has been removed from the question paper.", wrapped across however
# many physical lines the sentence needs (found via Economics 9708). Rather
# than pin down every phrasing CIE might use, _voided_question_end() resyncs
# on the next question's own label (or the end of the table, for a voided
# last question) and only accepts the gap as a voided-question notice when at
# least one token in it reads like one.
_VOIDED_HINT = re.compile(r"remov|discount|void", re.IGNORECASE)
_VOIDED_RESYNC_LOOKAHEAD = 8  # generous bound on wrapped physical lines
_PART_LABEL = re.compile(r"^(\d{1,2})\([a-z]\)(?:\([ivx]+\))?\s*$")
# A question with no lettered parts is labelled with a bare number in the
# Question column (CIE 9231 does this for its shorter questions). The column
# starts at x0 ~= 69-90; answer text sits at x0 ~= 122, so a low x0 disambiguates
# a question label from a stray "5" inside an answer. A leading "." is
# tolerated -- found via 9709_w22_ms_11.pdf, whose own PDF content stream has
# question 4's label as the two literal characters ".4" (confirmed via the raw
# glyph codes, not a pymupdf artifact); the answer text immediately follows it
# in full, so this is a genuine but recoverable label typo, not an absent
# mark scheme like the documented known gaps.
_BARE_LABEL = re.compile(r"^\.?(\d{1,2})$")
_MS_QUESTION_COL_MAX_X = 95.0  # fallback ceiling when a scheme has no part labels
_MS_QUESTION_COL_TOLERANCE = 14.0  # px a bare label may sit from the part-label column
_DOT_RUN = re.compile(r"\.{3,}")


def _part_label_number(text: str) -> int | None:
    part = _PART_LABEL.match(text)
    return int(part.group(1)) if part else None


def _question_column_x0(lines: list[dict]) -> float:
    """Left edge of the Question column, taken from the (unambiguous) lettered
    part labels -- ``1(a)``, ``4(b)`` never occur inside an answer body. Most
    labels in a scheme share one x0, but a longer compound label like
    ``10(b)(ii)`` can render several points further left than a plain
    ``N(a)``/``N(b)`` -- e.g. found via a 9709 Pure Mathematics 3 mark scheme
    where two ``N(a)(i)``/``N(b)(ii)`` rows sat at x0 ~81-83 against every
    other label's ~91, and ``min()`` picked that outlier as "the" column edge,
    pushing it far enough left that a bare (no-sub-part) question's own label
    fell outside _bare_label_number's tolerance. The most common x0 is used
    instead so a single such outlier can't drag the whole column. Falls back
    to a fixed ceiling when a scheme has no lettered parts at all."""
    xs = [round(ln.get("x0", 0.0), 1) for ln in lines if _PART_LABEL.match(ln["text"].strip())]
    return Counter(xs).most_common(1)[0][0] if xs else _MS_QUESTION_COL_MAX_X


# --- mark-scheme crop rectangles ---
# The MS is a Question / Answer / Marks table; a crop is the full-width band
# from a question's first row down to the next question's first row (several
# questions share a page). Wider x-span than the QP crop -- it has to reach the
# Marks column -- and a tighter body band that stays clear of the page footer.
# Every subject's MS was landscape (842x595) until Economics 9708, whose MS is
# portrait (595x842) instead -- so the x-span is a *fraction* of each page's
# real width (applied per page below), not the fixed absolute pixels a
# landscape-only assumption would bake in. The fractions themselves are the
# original landscape pixel bounds (55.0 / 795.0 of an 842pt-wide page).
_MS_CROP_X0_FRAC = 55.0 / 842.0
_MS_CROP_X1_FRAC = 795.0 / 842.0
_MS_BODY_TOP = 0.045
_MS_BODY_BOTTOM = 0.915
_MS_CROP_TOP_PAD = 4.0
_MS_CROP_MIN_HEIGHT = 20.0
_MS_DEFAULT_PAGE_HEIGHT = 595.0  # A4 landscape at 72 dpi; every 9702 ms page 2+
_MS_DEFAULT_PAGE_WIDTH = 842.0  # matches _MS_DEFAULT_PAGE_HEIGHT's landscape baseline


@dataclass
class Answer:
    question_number: int
    answer_text: str
    marks: int = 1
    # one (page, x0, y0, x1, y1) rect per page the mark scheme occupies; empty
    # for MCQ answers and for structured answers with no usable coordinates
    crop_rects: tuple[tuple[int, float, float, float, float], ...] = ()


@dataclass
class MarksReport:
    linked: dict[str, int] = field(default_factory=dict)  # ms filename -> answers linked
    no_question_paper: list[str] = field(default_factory=list)
    missing_json: list[str] = field(default_factory=list)


def _content_lines(lines: list[dict]) -> list[dict]:
    # Mark schemes number their footer "Page N of M" (caught by is_noise), and
    # 9231 puts bare question labels in the Question column at x0 ~= 60-90 -- so
    # the segmenter's stray-page-number filter is deliberately NOT applied here.
    return [line for line in lines if line["in_body"] and not is_noise(line["text"])]


def _content_texts(lines: list[dict]) -> list[str]:
    return [line["text"].strip() for line in _content_lines(lines)]


def _ms_line_y0(line: dict) -> float:
    height = line.get("height", _MS_DEFAULT_PAGE_HEIGHT)
    return line.get("y0", line.get("y_frac", 0.0) * height)


def _answer_crop_rects(
    block: list[dict], next_start: dict | None
) -> tuple[tuple[int, float, float, float, float], ...]:
    """Page regions to render for one question's mark scheme -- one rect per page
    from its first to its last, inclusive. The bottom edge runs to the next
    question's first line when it shares that page, otherwise to the content-band
    bottom (mirrors ``segment._crop_rects`` with landscape MS geometry)."""
    if not block:
        return ()
    pages = [ln["page"] for ln in block]
    first_page, last_page = min(pages), max(pages)
    heights = {ln["page"]: ln.get("height", _MS_DEFAULT_PAGE_HEIGHT) for ln in block}
    default_height = max(heights.values(), default=_MS_DEFAULT_PAGE_HEIGHT)
    widths = {ln["page"]: ln.get("width", _MS_DEFAULT_PAGE_WIDTH) for ln in block}
    default_width = max(widths.values(), default=_MS_DEFAULT_PAGE_WIDTH)

    rects: list[tuple[int, float, float, float, float]] = []
    for page in range(first_page, last_page + 1):
        height = heights.get(page, default_height)
        width = widths.get(page, default_width)
        band_top, band_bottom = _MS_BODY_TOP * height, _MS_BODY_BOTTOM * height
        crop_x0, crop_x1 = _MS_CROP_X0_FRAC * width, _MS_CROP_X1_FRAC * width

        page_lines = [ln for ln in block if ln["page"] == page]
        if page == first_page and page_lines:
            top = min(_ms_line_y0(ln) for ln in page_lines) - _MS_CROP_TOP_PAD
        else:
            top = band_top

        if next_start is not None and next_start["page"] == page:
            bottom = _ms_line_y0(next_start) - _MS_CROP_TOP_PAD
        else:
            bottom = band_bottom

        top = max(top, band_top)
        bottom = min(bottom, band_bottom)
        if bottom - top < _MS_CROP_MIN_HEIGHT:
            continue
        rects.append((page, round(crop_x0, 1), round(top, 1), round(crop_x1, 1), round(bottom, 1)))
    return tuple(rects)


def _voided_question_end(texts: list[str], i: int, expected: int) -> int | None:
    """Index just past a free-text voided-question notice starting at
    ``texts[i] == str(expected)``, or ``None`` if what follows doesn't read
    like one. Resyncs on the next question's own label within a short
    lookahead, or on the end of the table when the voided question is the
    paper's last (no further label to resync on)."""
    next_label = str(expected + 1)
    limit = min(len(texts), i + 1 + _VOIDED_RESYNC_LOOKAHEAD)
    for j in range(i + 1, limit):
        if texts[j] == next_label:
            return j if _VOIDED_HINT.search(" ".join(texts[i + 1 : j])) else None
    if limit == len(texts) and _VOIDED_HINT.search(" ".join(texts[i + 1 : limit])):
        return limit
    return None


def parse_mcq_answers(lines: list[dict]) -> list[Answer]:
    texts = _content_texts(lines)
    answers: list[Answer] = []
    expected = 1
    i = 0
    while i < len(texts) and expected <= MCQ_QUESTION_COUNT:
        triple = texts[i : i + 3]
        if len(triple) == 3 and triple[0] == str(expected) and _LETTER.match(triple[1]):
            marks = int(triple[2]) if _SMALL_INT.match(triple[2]) else 1
            answers.append(Answer(expected, triple[1], marks))
            expected += 1
            i += 3
        elif i + 1 < len(texts) and texts[i] == str(expected) and _DISCOUNTED.match(texts[i + 1]):
            answers.append(Answer(expected, "Question discounted", 1))
            expected += 1
            # A Marks-column digit may or may not follow -- only consume it
            # when it isn't actually the next question's own label.
            has_marks_digit = i + 2 < len(texts) and _SMALL_INT.match(texts[i + 2])
            is_next_question = i + 2 < len(texts) and texts[i + 2] == str(expected)
            i += 3 if (has_marks_digit and not is_next_question) else 2
        elif (
            texts[i] == str(expected)
            and (end := _voided_question_end(texts, i, expected)) is not None
        ):
            answers.append(Answer(expected, "Question voided", 1))
            expected += 1
            i = end
        else:
            i += 1
    return answers


def _answer_table_first_page(lines: list[dict]) -> int | None:
    """First page of the Question/Answer/Marks table.

    The generic and subject-specific marking principles that open every mark
    scheme are a numbered list at the same left margin as the Question column,
    so a bare "1".."6" there is indistinguishable from a question label. The
    standalone "Question" table header (dropped by ``is_noise`` from the content
    stream, but present in the raw lines) tells us where the real table starts.
    """
    pages = [
        ln["page"]
        for ln in lines
        if ln["text"].strip().lower() == "question" and ln.get("x0", 999.0) < 120.0
    ]
    return min(pages) if pages else None


def _bare_label_number(line: dict, col_x0: float, expected: int) -> int | None:
    """A bare number is a question label only if it (a) sits in the Question
    column and (b) is the next question in sequence -- answer bodies are full of
    stray small integers, some of them near the left margin."""
    bare = _BARE_LABEL.match(line["text"].strip())
    if not bare:
        return None
    n = int(bare.group(1))
    x0 = line.get("x0", 999.0)
    near_column = abs(x0 - col_x0) <= _MS_QUESTION_COL_TOLERANCE or x0 < _MS_QUESTION_COL_MAX_X
    return n if n == expected and near_column else None


def parse_structured_answers(lines: list[dict]) -> list[Answer]:
    grouped: dict[int, list[str]] = {}
    grouped_lines: dict[int, list[dict]] = {}
    current: int | None = None
    expected = 1  # next question number we have not seen a label for
    col_x0 = _question_column_x0(lines)
    table_page = _answer_table_first_page(lines)
    seen_part_label = False  # fallback trip if the header line was not extracted
    for line in _content_lines(lines):
        text = line["text"].strip()
        in_table = seen_part_label or (table_page is not None and line["page"] >= table_page)
        if not in_table:
            if _PART_LABEL.match(text):
                seen_part_label = True
            else:
                continue
        number = _part_label_number(text) or _bare_label_number(line, col_x0, expected)
        if number is not None:
            current = number
            expected = max(expected, number + 1)
            grouped.setdefault(current, []).append(text)
            grouped_lines.setdefault(current, []).append(line)
            continue
        if current is None:  # in the table, but the first question row not yet
            continue
        grouped_lines[current].append(line)
        cleaned = re.sub(r"\s+", " ", _DOT_RUN.sub(" ", text)).strip()
        if cleaned:
            grouped[current].append(cleaned)

    ordered = sorted(grouped)
    answers: list[Answer] = []
    for i, number in enumerate(ordered):
        next_start = grouped_lines[ordered[i + 1]][0] if i + 1 < len(ordered) else None
        answers.append(
            Answer(
                number,
                "\n".join(grouped[number]),
                marks=0,
                crop_rects=_answer_crop_rects(grouped_lines[number], next_start),
            )
        )
    return answers


def parse_answers(lines: list[dict]) -> list[Answer]:
    return parse_mcq_answers(lines) if looks_like_mcq(lines) else parse_structured_answers(lines)


def extract_answers_all(
    processed_dir: Path | None = None,
    db_path: Path | None = None,
) -> MarksReport:
    processed_dir = processed_dir if processed_dir is not None else config.PROCESSED_DIR
    init_db(db_path)
    report = MarksReport()

    with connect(db_path) as conn:
        mark_schemes = conn.execute(
            """
            SELECT id, filename, subject_code, year, session, paper, variant
            FROM papers
            WHERE paper_type = 'ms' AND has_text_layer = 1
            """
        ).fetchall()

        for ms in mark_schemes:
            json_path = processed_dir / f"{Path(ms['filename']).stem}.json"
            if not json_path.exists():
                report.missing_json.append(ms["filename"])
                continue

            qp = conn.execute(
                """
                SELECT id FROM papers
                WHERE paper_type = 'qp' AND subject_code = ? AND year = ?
                  AND session = ? AND paper IS ? AND variant IS ?
                """,
                (ms["subject_code"], ms["year"], ms["session"], ms["paper"], ms["variant"]),
            ).fetchone()
            if qp is None:
                report.no_question_paper.append(ms["filename"])
                continue

            answers = parse_answers(load_lines(json_path))
            conn.execute(
                "DELETE FROM answers WHERE question_id IN "
                "(SELECT id FROM questions WHERE paper_id = ?)",
                (qp["id"],),
            )
            linked = 0
            for answer in answers:
                question = conn.execute(
                    "SELECT id FROM questions WHERE paper_id = ? AND question_number = ?",
                    (qp["id"], answer.question_number),
                ).fetchone()
                if question is None:
                    continue
                conn.execute(
                    "INSERT INTO answers "
                    "(question_id, answer_text, source, answer_crop_rects, answer_crop_count) "
                    "VALUES (?, ?, ?, ?, ?)",
                    (
                        question["id"],
                        answer.answer_text,
                        "mark_scheme",
                        json.dumps([list(r) for r in answer.crop_rects]),
                        len(answer.crop_rects),
                    ),
                )
                linked += 1
            report.linked[ms["filename"]] = linked

        conn.commit()

    return report
