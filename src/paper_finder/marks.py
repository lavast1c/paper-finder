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


@dataclass
class Answer:
    question_number: int
    answer_text: str
    marks: int = 1


@dataclass
class MarksReport:
    linked: dict[str, int] = field(default_factory=dict)  # ms filename -> answers linked
    no_question_paper: list[str] = field(default_factory=list)
    missing_json: list[str] = field(default_factory=list)


def _content_texts(lines: list[dict]) -> list[str]:
    return [
        line["text"].strip() for line in lines if line["in_body"] and not is_noise(line["text"])
    ]


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
    current: int | None = None
    for text in _content_texts(lines):
        label = _PART_LABEL.match(text)
        if label:
            current = int(label.group(1))
            grouped.setdefault(current, []).append(text)
            continue
        if current is None:  # still in the pre-table marking-principles pages
            continue
        cleaned = re.sub(r"\s+", " ", _DOT_RUN.sub(" ", text)).strip()
        if cleaned:
            grouped[current].append(cleaned)

    return [Answer(number, "\n".join(block), marks=0) for number, block in sorted(grouped.items())]


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
                    "INSERT INTO answers (question_id, answer_text, source) VALUES (?, ?, ?)",
                    (question["id"], answer.answer_text, "mark_scheme"),
                )
                linked += 1
            report.linked[ms["filename"]] = linked

        conn.commit()

    return report
