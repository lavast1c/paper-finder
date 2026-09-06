"""Split extracted question papers into individual questions.

Currently handles multiple-choice papers (CIE science Paper 1): questions numbered
1..40, each with options A-D. Structured papers come in a later stage.

Two signals make question-number detection reliable:

* **x-position** — a real question number sits in the left margin (x0 well below
  the body text), which rejects diagram labels like ``6 N`` and centred page
  numbers.
* **expected sequence** — numbers run 1, 2, 3, ...; a candidate that doesn't
  continue the sequence is ignored.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from pathlib import Path

from paper_finder import config
from paper_finder.db import connect, init_db

MCQ_QUESTION_COUNT = 40
_MARGIN_X = 60.0  # question numbers sit at x0 ~= 49; body text starts ~= 70

# Fraction-of-page-height band that holds real content. Outside it: the centred
# page number (top) and the CIE / mirror-site footer block (bottom).
_BODY_TOP = 0.055
_BODY_BOTTOM = 0.90

# A line that is page furniture rather than question content.
_NOISE = re.compile(
    r"""
      papacambridge
    | ^downloaded\ from
    | ^licensed\ for\ hosting
    | ^re-uploading
    | ^trace\ id:
    | source:\ papacambridge
    | ^\N{COPYRIGHT SIGN}\ cambridge
    | ^cambridge\ international\ (as|education)
    | ^\d{4}/\d{2}(/[a-z])*(/\d{2})?$          # 9702/11  or  9702/11/M/J/26
    | ^\[turn\ over
    | ^this\ document\ (has|consists)
    | ^blank\ page$
    | ^\d{4}/\d{2}\ (question\ paper|mark\ scheme)\b     # running header
    | ^permission\ to\ reproduce                        # -- CIE end-of-paper block
    | ^reasonable\ effort\ has\ been\ made
    | ^have\ unwittingly\ been\ included
    | ^to\ avoid\ the\ issue\ of\ disclosure
    | ^acknowledgements\ booklet
    | ^live\ examination\ series
    | ^university\ of\ cambridge\.?$                     # --
    | ^\*\d+\*$                                 # barcode
    | ^ib\d{2}\b                                # e.g. IB26 06_9702_11/FP_R
    | www\.cambridgeinternational\.org
    | ^page\ \d+\ of\ \d+$
    | ^(question|answer|marks)$                 # mark-scheme table header
    """,
    re.VERBOSE | re.IGNORECASE,
)

_QSTART = re.compile(r"^(\d{1,2})(?:\s+(.*\S))?\s*$")
_OPTION_LETTERS = ("A", "B", "C", "D")


@dataclass
class Question:
    number: int
    text: str
    page_start: int
    marks: int = 1
    is_mcq: bool = True


@dataclass
class SegmentReport:
    segmented: dict[str, int] = field(default_factory=dict)  # filename -> question count
    not_mcq: list[str] = field(default_factory=list)
    no_text_layer: list[str] = field(default_factory=list)
    missing_json: list[str] = field(default_factory=list)


def is_noise(text: str) -> bool:
    return bool(_NOISE.search(text))


def load_lines(json_path: Path) -> list[dict]:
    data = json.loads(json_path.read_text(encoding="utf-8"))
    lines: list[dict] = []
    for page in data["pages"]:
        height = page["height"] or 842.0
        top, bottom = _BODY_TOP * height, _BODY_BOTTOM * height
        for line in page["lines"]:
            lines.append(
                {
                    "page": page["page"],
                    "text": line["text"],
                    "x0": line["x0"],
                    "in_body": top <= line["y0"] <= bottom,
                }
            )
    return lines


def looks_like_mcq(lines: list[dict]) -> bool:
    head = " ".join(line["text"] for line in lines[:40]).lower()
    return "multiple choice" in head


def _split_stem_and_options(texts: list[str]) -> tuple[list[str], dict[str, list[str]]]:
    """Find the trailing A/B/C/D option block; everything before it is the stem.

    Uses the *last* A that has B, C, D standalone letters after it in order, so
    stray option letters inside a diagram earlier in the question are ignored.
    """
    positions = {
        letter: [i for i, t in enumerate(texts) if t == letter] for letter in _OPTION_LETTERS
    }

    chosen: tuple[int, int, int, int] | None = None
    for a in reversed(positions["A"]):
        b = next((i for i in positions["B"] if i > a), None)
        c = next((i for i in positions["C"] if b is not None and i > b), None)
        d = next((i for i in positions["D"] if c is not None and i > c), None)
        if b is not None and c is not None and d is not None:
            chosen = (a, b, c, d)
            break

    if chosen is None:
        return texts, {}

    a, b, c, d = chosen
    return texts[:a], {
        "A": texts[a + 1 : b],
        "B": texts[b + 1 : c],
        "C": texts[c + 1 : d],
        "D": texts[d + 1 :],
    }


def _collapse(parts: list[str]) -> str:
    return re.sub(r"\s+", " ", " ".join(parts)).strip()


def _format_question(block: list[dict]) -> str:
    first = _QSTART.match(block[0]["text"])
    texts: list[str] = []
    if first and first.group(2):
        texts.append(first.group(2))
    texts.extend(line["text"] for line in block[1:])

    stem, options = _split_stem_and_options(texts)
    result = _collapse(stem)
    for letter in _OPTION_LETTERS:
        if letter in options:
            result += f"\n{letter}. {_collapse(options[letter])}"
    return result.strip()


def segment_mcq(lines: list[dict]) -> list[Question]:
    content = [line for line in lines if line["in_body"] and not is_noise(line["text"])]

    starts: list[int] = []
    expected = 1
    for i, line in enumerate(content):
        match = _QSTART.match(line["text"])
        if match is None or int(match.group(1)) != expected:
            continue
        if line["x0"] > _MARGIN_X:  # not in the left margin -> not a question number
            continue
        starts.append(i)
        expected += 1
        if expected > MCQ_QUESTION_COUNT:
            break

    questions: list[Question] = []
    for idx, start_i in enumerate(starts):
        end_i = starts[idx + 1] if idx + 1 < len(starts) else len(content)
        block = content[start_i:end_i]
        questions.append(
            Question(
                number=idx + 1,
                text=_format_question(block),
                page_start=block[0]["page"],
            )
        )
    return questions


_UPSERT_QUESTION = """
INSERT INTO questions (paper_id, question_number, question_text, marks, is_mcq, page_start)
VALUES (:paper_id, :number, :text, :marks, :is_mcq, :page_start)
ON CONFLICT(paper_id, question_number) DO UPDATE SET
    question_text = excluded.question_text,
    marks         = excluded.marks,
    is_mcq        = excluded.is_mcq,
    page_start    = excluded.page_start
"""


def segment_all(
    processed_dir: Path | None = None,
    db_path: Path | None = None,
) -> SegmentReport:
    processed_dir = processed_dir if processed_dir is not None else config.PROCESSED_DIR
    init_db(db_path)
    report = SegmentReport()

    with connect(db_path) as conn:
        papers = conn.execute(
            "SELECT id, filename, has_text_layer FROM papers WHERE paper_type = 'qp'"
        ).fetchall()

        for paper in papers:
            stem = Path(paper["filename"]).stem
            json_path = processed_dir / f"{stem}.json"
            if not json_path.exists():
                report.missing_json.append(paper["filename"])
                continue
            if paper["has_text_layer"] == 0:
                report.no_text_layer.append(paper["filename"])
                continue

            lines = load_lines(json_path)
            if not looks_like_mcq(lines):
                report.not_mcq.append(paper["filename"])
                continue

            questions = segment_mcq(lines)
            conn.execute("DELETE FROM questions WHERE paper_id = ?", (paper["id"],))
            for question in questions:
                conn.execute(
                    _UPSERT_QUESTION,
                    {
                        "paper_id": paper["id"],
                        "number": question.number,
                        "text": question.text,
                        "marks": question.marks,
                        "is_mcq": 1 if question.is_mcq else 0,
                        "page_start": question.page_start,
                    },
                )
            report.segmented[paper["filename"]] = len(questions)

        conn.execute("INSERT INTO questions_fts(questions_fts) VALUES ('rebuild')")
        conn.commit()

    return report
