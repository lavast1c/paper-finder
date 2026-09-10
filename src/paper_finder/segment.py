"""Split extracted question papers into individual questions.

Two paper shapes are handled:

* **Multiple choice** (CIE science Paper 1) -- questions 1..40, each with options
  A-D.
* **Structured** (CIE science Paper 2 / 4) -- a handful of questions, each with
  ``(a)``, ``(b)(i)`` ... sub-parts and a ``[Total: N]`` line at the end.

Question-number detection leans on three signals: the number sits in the left
margin (small x0), it continues the 1, 2, 3 ... sequence, and -- for structured
papers -- it appears at the top of a page right after the previous question's
``[Total:]`` line.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from pathlib import Path

from paper_finder import config
from paper_finder.db import connect, init_db

MCQ_QUESTION_COUNT = 40
_MARGIN_X = 60.0  # question numbers sit at x0 ~= 49; body text starts ~= 72

# Fraction-of-page-height band that holds real content. Outside it: the centred
# page number (top) and the CIE / mirror-site footer block (bottom). The bottom
# edge sits just below a low ``[Total: N]`` line (~0.91) but above the copyright
# footer (~0.95).
_BODY_TOP = 0.055
_BODY_BOTTOM = 0.93

# A structured question number sits in the upper part of its page. CIE Physics
# Paper 2 puts it at ~0.07; the Maths papers give each short question a lot of
# answer space, so the next question can begin well down the page it shares with
# the previous one's answer lines -- 9231 ~0.34, 9709 Stats ~0.51. Anything
# above this (a number in the footer band) is never a start.
_STRUCTURED_START_MAX_Y = 0.88
# A bare margin number this near the top of its page, continuing the sequence,
# is a question start on its own -- CIE starts each structured question on a
# fresh page. Below this band the body-lookahead has to confirm it (the mid-page
# case). 9709 Pure Maths opens many questions with a full-width graph whose
# axis-label fragments run well past any sane lookahead before the prose.
_STRUCTURED_START_TOP_OF_PAGE = 0.12
# How many lines after a bare question number to scan for a body-like line (a
# part label or a sentence) before giving up on it being a question start.
_STRUCTURED_BODY_LOOKAHEAD = 16

# --- question-image crop rectangles (Stage 2) ---
# A crop is the whole question column, page by page, at fixed x-bounds -- NOT the
# text bbox union: a diagram or table is routinely wider than the narrowest text
# line above it. The vertical band is the same _BODY_TOP.._BODY_BOTTOM content
# band the segmenter already trusts, which also keeps the PapaCambridge footer
# banner (y > ~0.97h) out of frame.
_CROP_X0 = 40.0
_CROP_X1 = 555.0
_CROP_TOP_PAD = 4.0  # a few points of headroom above the first line / below the next question
_CROP_MIN_HEIGHT = 20.0  # a shorter band is a stray label, nothing to render
_DEFAULT_PAGE_HEIGHT = 842.0  # A4 portrait at 72 dpi; every 9702 qp page

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
    | ^cambridge\ international\ .+mark\ scheme        # MS running header
    | ^\d{4}/\d{2}(/[a-z])*(/\d{2})?$                  # 9702/11  or  9702/11/M/J/26
    | ^\[turn\ over
    | ^turn\ over$
    | ^this\ document\ (has|consists)
    | ^blank\ page$
    | ^additional\ page$
    | ^if\ you\ use\ the\ following\ page                # "Additional page" instruction block
    | ^write\ your\ answers?\ on\ the\ separate
    | ^do\ not\ write\ in\ this\ margin
    | ^dfd$
    | ^\d{4}/\d{2}\ (question\ paper|mark\ scheme)\b   # running header
    | ^\*[\s\d]+\*$                                    # barcode: * 0000800000004 *
    | ^permission\ to\ reproduce                       # -- CIE end-of-paper block
    | ^reasonable\ effort\ has\ been\ made
    | ^have\ unwittingly\ been\ included
    | ^to\ avoid\ the\ issue\ of\ disclosure
    | ^acknowledgements\ booklet
    | copyright\ acknowledgements\ booklet
    | ^(the\ )?publisher\ (will\ be\ pleased|\(ucles\))
    | ^cambridge\ assessment\ international\ education
    | is\ the\ brand\ name\ of\ the\ university\ of\ cambridge
    | local\ examinations\ syndicate
    | which\ is\ a\ department\ of\ the\ university
    | ^live\ examination\ series
    | ^university\ of\ cambridge\.?$                   # --
    | ^published$                                      # -- MS front-matter
    | ^maximum\ mark\s*:
    | ^(general|science-specific)\ marking\ principles
    | ^annotations?$
    | ^abbreviations$
    | ^mark\ categories$                               # --
    | ^ib\d{2}\b                                       # e.g. IB26 06_9702_11/FP_R
    | www\.cambridgeinternational\.org
    | ^page\ \d+\ of\ \d+$
    | ^(question|answer|marks|guidance)$               # mark-scheme table header
    """,
    re.VERBOSE | re.IGNORECASE,
)

# Glyphs from the barcode font PyMuPDF renders as random Latin Extended letters;
# CIE English physics papers never use this Unicode block in real text.
_BARCODE_FONT = re.compile(r"[Ā-ɏ]")
_JUNK_SYMBOLS = frozenset("¬¦¤¥§")
_CONTROL_CHARS = re.compile(r"[\x00-\x08\x0b-\x1f]")

# The question leans on something the text extraction can't carry: a labelled
# figure, a diagram/graph, or a table. Used to flag "check the original PDF" in
# the UI. Tuned against the 9702 corpus (CIE is rigid about "Fig. 1.1" labels
# and "The diagram shows" / "The graph shows" phrasing).
_FIGURE_REF = re.compile(
    r"""
      \bfig(?:s|ure|ures)?\.?\s*\d                          # Fig. 1.1 / Figure 2 / Figs 1.1
    | \bdiagram\b
    | \bgraph\s+(?:shows|below|above|is\ shown|represents)
    | \b(?:table)\s+\d                                      # Table 1.1 (extraction mangles tables)
    | \bshows?\s+(?:the\s+)?(?:variation|arrangement|apparatus|circuit|path|
                              forces?|set-?up|shape|structure)
    | \bshown\s+(?:in\s+the\s+)?(?:diagram|figure|graph|circuit|arrangement|below)
    | \bimage\b | \bphotograph\b
    """,
    re.VERBOSE | re.IGNORECASE,
)


def mentions_figure(text: str) -> bool:
    """Whether a question's text points at a diagram/graph/table (see ``_FIGURE_REF``)."""
    return bool(_FIGURE_REF.search(text))


_QSTART = re.compile(r"^(\d{1,2})(?:\s+(.*\S))?\s*$")
_BARE_NUMBER = re.compile(r"^(\d{1,2})$")
_TOTAL = re.compile(r"^\[\s*total\s*:\s*(\d+)\s*\]", re.IGNORECASE)
_MARK_BRACKET = re.compile(r"\[\s*\d+\s*\]")
_DOT_RUN = re.compile(r"\.{3,}")
_OPTION_LETTERS = ("A", "B", "C", "D")


@dataclass
class Question:
    number: int
    text: str
    page_start: int
    marks: int | None = 1
    is_mcq: bool = True
    has_figure: bool = False
    # One (page, x0, y0, x1, y1) rect per page the question occupies, in page
    # order. `paper-finder figures` renders each to an image; empty = no crop.
    crop_rects: tuple[tuple[int, float, float, float, float], ...] = ()


@dataclass
class SegmentReport:
    segmented: dict[str, int] = field(default_factory=dict)  # filename -> question count
    unparsed: list[str] = field(default_factory=list)  # produced no questions
    no_text_layer: list[str] = field(default_factory=list)
    missing_json: list[str] = field(default_factory=list)


def _is_stray_page_number(line: dict) -> bool:
    """A bare 1-3 digit number away from the left margin is the centred page
    number, not a question label -- it would otherwise pad a crop out to the
    trailing blank pages of a paper."""
    return bool(_BARE_NUMBER.match(line["text"].strip())) and line.get("x0", 0.0) >= _MARGIN_X


def content_lines(lines: list[dict]) -> list[dict]:
    """Body lines that carry real question content (drops page furniture)."""
    return [
        line
        for line in lines
        if line["in_body"] and not is_noise(line["text"]) and not _is_stray_page_number(line)
    ]


def is_noise(text: str) -> bool:
    stripped = _CONTROL_CHARS.sub("", text).strip()
    if not stripped:
        return True
    if _NOISE.search(stripped):
        return True
    if _BARCODE_FONT.search(stripped):
        return True
    if any(ch in _JUNK_SYMBOLS for ch in stripped):
        return True
    return not stripped.strip(", \t\r\n")  # stray comma / whitespace / newline lines


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
                    "y0": line["y0"],
                    "y1": line["y1"],
                    "height": height,
                    "y_frac": line["y0"] / height,
                    "in_body": top <= line["y0"] <= bottom,
                }
            )
    return lines


def looks_like_mcq(lines: list[dict]) -> bool:
    head = " ".join(line["text"] for line in lines[:40]).lower()
    return "multiple choice" in head


def _collapse(parts: list[str]) -> str:
    return re.sub(r"\s+", " ", " ".join(parts)).strip()


def _line_y0(line: dict) -> float:
    height = line.get("height", _DEFAULT_PAGE_HEIGHT)
    return line.get("y0", line["y_frac"] * height)


def _crop_rects(
    block: list[dict], next_start: dict | None
) -> tuple[tuple[int, float, float, float, float], ...]:
    """The page regions to render for one question.

    One rect per page from the question's first to its last, inclusive -- pages
    are taken as a contiguous *range*, not from the pages that happen to carry a
    text line, so a full-page diagram between two text pages is not dropped. The
    bottom edge runs to the next question's first line when it shares the last
    page, otherwise to the content-band bottom -- so a figure sitting below the
    final line of text is still inside the crop.
    """
    if not block:
        return ()
    pages = [ln["page"] for ln in block]
    first_page, last_page = min(pages), max(pages)
    heights = {ln["page"]: ln.get("height", _DEFAULT_PAGE_HEIGHT) for ln in block}
    default_height = max(heights.values(), default=_DEFAULT_PAGE_HEIGHT)

    rects: list[tuple[int, float, float, float, float]] = []
    for page in range(first_page, last_page + 1):
        height = heights.get(page, default_height)
        band_top, band_bottom = _BODY_TOP * height, _BODY_BOTTOM * height

        page_lines = [ln for ln in block if ln["page"] == page]
        if page == first_page and page_lines:
            top = min(_line_y0(ln) for ln in page_lines) - _CROP_TOP_PAD
        else:
            top = band_top

        if next_start is not None and next_start["page"] == page:
            bottom = _line_y0(next_start) - _CROP_TOP_PAD
        else:
            bottom = band_bottom

        top = max(top, band_top)
        bottom = min(bottom, band_bottom)
        if bottom - top < _CROP_MIN_HEIGHT:
            continue
        rects.append((page, _CROP_X0, round(top, 1), _CROP_X1, round(bottom, 1)))
    return tuple(rects)


# --------------------------------------------------------------------------- MCQ


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


def _format_mcq_question(block: list[dict]) -> str:
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
    content = content_lines(lines)

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
        next_i = starts[idx + 1] if idx + 1 < len(starts) else None
        block = content[start_i : next_i if next_i is not None else len(content)]
        text = _format_mcq_question(block)
        questions.append(
            Question(
                number=idx + 1,
                text=text,
                page_start=block[0]["page"],
                has_figure=mentions_figure(text),
                crop_rects=_crop_rects(block, content[next_i] if next_i is not None else None),
            )
        )
    return questions


# -------------------------------------------------------------------- structured


def _looks_like_question_body(text: str) -> bool:
    # the line right after a bare question number: a part label or a sentence
    return text.startswith("(") or (text[:1].isalpha() and text[:1].isupper())


def _format_structured_question(block: list[dict]) -> str:
    parts: list[str] = []
    # The number line is usually bare, but can carry the opening words of the
    # question ("10 The equation..."); keep that text, drop the leading number.
    first = _QSTART.match(block[0]["text"].strip())
    if first and first.group(2):
        parts.append(first.group(2).strip())
    for line in block[1:]:
        text = line["text"].strip()
        if _TOTAL.match(text):
            continue
        text = _DOT_RUN.sub(" ", text)
        text = _MARK_BRACKET.sub(" ", text)
        text = re.sub(r"\s+", " ", text).strip()
        if text:
            parts.append(text)
    return " ".join(parts).strip()


def _is_structured_question_start(content: list[dict], i: int, expected: int) -> bool:
    line = content[i]
    # Usually the number is alone on its line, but 2024+ papers sometimes set a
    # two-digit number on the same line as the first words of the question, so
    # match "10 The equation..." as well as a bare "10".
    match = _QSTART.match(line["text"].strip())
    if not (
        match
        and int(match.group(1)) == expected
        and line["x0"] < _MARGIN_X
        and line["y_frac"] < _STRUCTURED_START_MAX_Y
    ):
        return False
    # When the number shares its line with the opening words, that trailing text
    # is the body confirmation.
    inline = (match.group(2) or "").strip()
    if _looks_like_question_body(inline):
        return True
    # The first prose/part line usually follows immediately, but a figure or a
    # displayed formula (e.g. an "f(x)" axis label) can sit in between -- scan a
    # few lines ahead, stopping if another bare margin number appears first (a
    # column of numbers is a table, not a run of question starts).
    for j in range(i + 1, min(i + 1 + _STRUCTURED_BODY_LOOKAHEAD, len(content))):
        nxt = content[j]["text"].strip()
        if _BARE_NUMBER.match(nxt) and content[j]["x0"] < _MARGIN_X:
            return False
        if _looks_like_question_body(nxt):
            return True
    # No prose line within the window and no rival margin number -- for a number
    # right at the top of a page, that means the question opens with a full-page
    # graph whose axis labels crowd out the first sentence (9709 Pure Maths).
    # CIE starts each structured question on a fresh page, so accept it.
    return line["y_frac"] < _STRUCTURED_START_TOP_OF_PAGE


def segment_structured(lines: list[dict]) -> list[Question]:
    content = content_lines(lines)

    starts: list[int] = []
    expected = 1
    for i in range(len(content)):
        if _is_structured_question_start(content, i, expected):
            starts.append(i)
            expected += 1

    questions: list[Question] = []
    for idx, start_i in enumerate(starts):
        next_i = starts[idx + 1] if idx + 1 < len(starts) else None
        block = content[start_i : next_i if next_i is not None else len(content)]
        marks = next(
            (
                int(_TOTAL.match(line["text"].strip()).group(1))
                for line in reversed(block)
                if _TOTAL.match(line["text"].strip())
            ),
            None,
        )
        text = _format_structured_question(block)
        questions.append(
            Question(
                number=idx + 1,
                text=text,
                page_start=block[0]["page"],
                marks=marks,
                is_mcq=False,
                has_figure=mentions_figure(text),
                crop_rects=_crop_rects(block, content[next_i] if next_i is not None else None),
            )
        )
    return questions


# ------------------------------------------------------------------------ driver


def segment_paper(lines: list[dict]) -> list[Question]:
    return segment_mcq(lines) if looks_like_mcq(lines) else segment_structured(lines)


_UPSERT_QUESTION = """
INSERT INTO questions
    (paper_id, question_number, question_text, marks, is_mcq, page_start, has_figure,
     crop_rects, crop_count)
VALUES (:paper_id, :number, :text, :marks, :is_mcq, :page_start, :has_figure,
        :crop_rects, :crop_count)
ON CONFLICT(paper_id, question_number) DO UPDATE SET
    question_text = excluded.question_text,
    marks         = excluded.marks,
    is_mcq        = excluded.is_mcq,
    page_start    = excluded.page_start,
    has_figure    = excluded.has_figure,
    crop_rects    = excluded.crop_rects,
    crop_count    = excluded.crop_count
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
            json_path = processed_dir / f"{Path(paper['filename']).stem}.json"
            if not json_path.exists():
                report.missing_json.append(paper["filename"])
                continue
            if paper["has_text_layer"] == 0:
                report.no_text_layer.append(paper["filename"])
                continue

            questions = segment_paper(load_lines(json_path))
            if not questions:
                report.unparsed.append(paper["filename"])
                continue

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
                        "has_figure": 1 if question.has_figure else 0,
                        "crop_rects": json.dumps([list(r) for r in question.crop_rects]),
                        "crop_count": len(question.crop_rects),
                    },
                )
            report.segmented[paper["filename"]] = len(questions)

        conn.execute("INSERT INTO questions_fts(questions_fts) VALUES ('rebuild')")
        conn.commit()

    return report
