"""Render a page-region image for every question, cropped from the source PDF.

``paper-finder figures`` reads the crop rectangles ``segment`` recorded on each
``questions`` row (:data:`paper_finder.segment._crop_rects`) and renders one PNG
per rectangle into ``data/crops/<stem>/``. Offline, idempotent and deterministic,
so it joins ``paper-finder build`` after ``segment``.

PyMuPDF is a core dependency, but this module is never imported from
``web/app.py`` -- the deployed import chain stays pymupdf-free.

The crops are derived works of copyrighted CIE papers, so ``data/crops/`` is
gitignored and vercelignored exactly like ``data/raw/``. A one-question crop is
not the paper; the whole PDF still never leaves the machine.
"""

from __future__ import annotations

import json
from collections import defaultdict
from dataclasses import dataclass, field
from pathlib import Path

import pymupdf

from paper_finder import config
from paper_finder.db import connect, init_db

# Render scale. 2x keeps 8-9 pt exam text and thin diagram strokes crisp on a
# high-DPI screen without the file size of a full 300 dpi rasterisation.
_ZOOM = 2.0

# CIE question papers are black line art on white -- greyscale is ~a third the
# bytes of RGB for no visible loss.
_COLORSPACE = pymupdf.csGRAY


@dataclass
class FigureReport:
    rendered: dict[str, int] = field(default_factory=dict)  # filename -> crop files written
    skipped_existing: int = 0
    bad_rects: list[str] = field(default_factory=list)  # "<filename> Q<n>: <reason>"
    missing_pdf: list[str] = field(default_factory=list)
    dry_run: bool = False

    @property
    def total_rendered(self) -> int:
        return sum(self.rendered.values())


def crop_path(stem: str, question_number: int, ordinal: int, crop_dir: Path) -> Path:
    """``data/crops/<stem>/q07_p1.png`` -- ``ordinal`` is 1..crop_count, the page's
    position *within the question*, not its PDF page number (the browser only
    knows the count)."""
    return crop_dir / stem / f"q{question_number:02d}_p{ordinal}.png"


_SELECT = """
SELECT p.filename, q.question_number, q.crop_rects
FROM questions q
JOIN papers p ON p.id = q.paper_id
WHERE p.paper_type = 'qp' AND q.crop_count > 0
ORDER BY p.filename, q.question_number
"""


def _render_rect(page: pymupdf.Page, rect: tuple, dest: Path) -> None:
    _, x0, y0, x1, y1 = rect
    clip = pymupdf.Rect(x0, y0, x1, y1) & page.rect  # never sample outside the page
    pix = page.get_pixmap(clip=clip, matrix=pymupdf.Matrix(_ZOOM, _ZOOM), colorspace=_COLORSPACE)
    dest.parent.mkdir(parents=True, exist_ok=True)
    pix.save(dest)


def render_all(
    *,
    limit: int | None = None,
    only: str | None = None,
    force: bool = False,
    dry_run: bool = False,
    db_path: Path | None = None,
    raw_dir: Path | None = None,
    crop_dir: Path | None = None,
) -> FigureReport:
    raw_dir = raw_dir if raw_dir is not None else config.RAW_DIR
    crop_dir = crop_dir if crop_dir is not None else config.CROP_DIR

    init_db(db_path)
    with connect(db_path) as conn:
        rows = conn.execute(_SELECT).fetchall()

    by_paper: dict[str, list[tuple[int, list]]] = defaultdict(list)
    for row in rows:
        if only and only not in row["filename"]:
            continue
        by_paper[row["filename"]].append(
            (row["question_number"], json.loads(row["crop_rects"] or "[]"))
        )

    report = FigureReport(dry_run=dry_run)
    for filename, questions in by_paper.items():
        if limit is not None and report.total_rendered >= limit:
            break
        pdf_path = raw_dir / filename
        if not pdf_path.is_file():
            report.missing_pdf.append(filename)
            continue

        stem = Path(filename).stem
        written = 0
        with pymupdf.open(pdf_path) as doc:
            for question_number, rects in questions:
                if limit is not None and report.total_rendered + written >= limit:
                    break
                for ordinal, rect in enumerate(rects, start=1):
                    dest = crop_path(stem, question_number, ordinal, crop_dir)
                    if dest.is_file() and not force:
                        report.skipped_existing += 1
                        continue
                    page_number = int(rect[0])
                    if not 1 <= page_number <= doc.page_count:
                        report.bad_rects.append(
                            f"{filename} Q{question_number}: page {page_number} out of range"
                        )
                        continue
                    # extract.py maps every line bbox into the page's rotated
                    # display frame, and page.get_pixmap(clip=) reads clip in that
                    # same frame -- so a rotated page (landscape Paper 2 mark
                    # schemes) crops correctly with no special handling.
                    page = doc[page_number - 1]
                    if not dry_run:
                        _render_rect(page, rect, dest)
                    written += 1

        if written:
            report.rendered[filename] = written

    return report
