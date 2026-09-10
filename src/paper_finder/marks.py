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
from dataclasses import dataclass, field
from pathlib import Path

from paper_finder import config
from paper_finder.db import connect, init_db
from paper_finder.segment import MCQ_QUESTION_COUNT, is_noise, load_lines, looks_like_mcq

_LETTER = re.compile(r"^[A-D]$")
_SMALL_INT = re.compile(r"^\d{1,2}$")
_PART_LABEL = re.compile(r"^(\d{1,2})\([a-z]\)(?:\([ivx]+\))?\s*$")
_DOT_RUN = re.compile(r"\.{3,}")

# --- mark-scheme crop rectangles ---
# The MS is a landscape Question / Answer / Marks table; a crop is the full-width
# band from a question's first row down to the next question's first row (several
# questions share a page). Wider x-span than the QP crop -- it has to reach the
# Marks column -- and a tighter body band that stays clear of the page footer.
_MS_CROP_X0 = 55.0
_MS_CROP_X1 = 795.0
_MS_BODY_TOP = 0.045
_MS_BODY_BOTTOM = 0.915
_MS_CROP_TOP_PAD = 4.0
_MS_CROP_MIN_HEIGHT = 20.0
_MS_DEFAULT_PAGE_HEIGHT = 595.0  # A4 landscape at 72 dpi; every 9702 ms page 2+


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

    rects: list[tuple[int, float, float, float, float]] = []
    for page in range(first_page, last_page + 1):
        height = heights.get(page, default_height)
        band_top, band_bottom = _MS_BODY_TOP * height, _MS_BODY_BOTTOM * height

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
        rects.append((page, _MS_CROP_X0, round(top, 1), _MS_CROP_X1, round(bottom, 1)))
    return tuple(rects)


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
        else:
            i += 1
    return answers


def parse_structured_answers(lines: list[dict]) -> list[Answer]:
    grouped: dict[int, list[str]] = {}
    grouped_lines: dict[int, list[dict]] = {}
    current: int | None = None
    for line in _content_lines(lines):
        text = line["text"].strip()
        label = _PART_LABEL.match(text)
        if label:
            current = int(label.group(1))
            grouped.setdefault(current, []).append(text)
            grouped_lines.setdefault(current, []).append(line)
            continue
        if current is None:  # still in the pre-table marking-principles pages
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
