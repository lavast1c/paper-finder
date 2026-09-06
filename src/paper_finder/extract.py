"""Extract text (with positions) from the PDFs recorded in the database.

For every paper in ``papers`` we read the PDF from ``data/raw/`` and write two
files to ``data/processed/``:

* ``<stem>.txt``  — plain text, one line per PDF text line, pages separated by a
  form feed. Handy for eyeballing.
* ``<stem>.json`` — structured: every line with its bounding box, so the
  segmenter (Stage 2b) can find question numbers by their x-position in the
  margin.

``papers.has_text_layer`` is set from the average characters per page: a scanned
PDF with no embedded text extracts almost nothing and needs OCR (a later stage).
"""

from __future__ import annotations

import json
import re
from dataclasses import asdict, dataclass, field
from pathlib import Path

import pymupdf

from paper_finder import config
from paper_finder.db import connect, init_db
from paper_finder.symbols import normalise

# Below this many characters per page on average, assume there is no usable text
# layer (the PDF is scanned images) and flag it for OCR later.
MIN_CHARS_PER_PAGE = 80


@dataclass
class Line:
    page: int  # 1-indexed
    x0: float
    y0: float
    x1: float
    y1: float
    text: str


@dataclass
class Page:
    page: int
    width: float
    height: float
    lines: list[Line] = field(default_factory=list)


@dataclass
class ExtractedPaper:
    filename: str
    page_count: int
    char_count: int
    has_text_layer: bool
    pages: list[Page]

    def to_json(self) -> str:
        return json.dumps(
            {
                "filename": self.filename,
                "page_count": self.page_count,
                "char_count": self.char_count,
                "has_text_layer": self.has_text_layer,
                "pages": [asdict(p) for p in self.pages],
            },
            indent=1,
            ensure_ascii=False,
        )

    def to_text(self) -> str:
        page_blocks = ["\n".join(line.text for line in p.lines) for p in self.pages]
        return "\f\n".join(page_blocks)


_CONTROL_CHARS = re.compile(r"[\x00-\x08\x0b-\x1f]")  # keep \t and \n; drop the rest


def _clean(text: str) -> str:
    # Repair Symbol-font glyphs, drop control chars (barcode glyphs extract as
    # these), then normalise NBSPs and trailing space.
    text = _CONTROL_CHARS.sub("", normalise(text))
    return text.replace("\xa0", " ").rstrip()


def extract_paper(pdf_path: Path) -> ExtractedPaper:
    pages: list[Page] = []
    char_count = 0

    with pymupdf.open(pdf_path) as doc:
        for index, page in enumerate(doc, start=1):
            rect = page.rect
            out_page = Page(page=index, width=rect.width, height=rect.height)
            data = page.get_text("dict")
            for block in data.get("blocks", []):
                for line in block.get("lines", []):
                    text = _clean("".join(span["text"] for span in line.get("spans", [])))
                    if not text:
                        continue
                    x0, y0, x1, y1 = line["bbox"]
                    out_page.lines.append(Line(page=index, x0=x0, y0=y0, x1=x1, y1=y1, text=text))
                    char_count += len(text)
            pages.append(out_page)

    page_count = len(pages)
    has_text_layer = page_count > 0 and (char_count / page_count) >= MIN_CHARS_PER_PAGE
    return ExtractedPaper(
        filename=pdf_path.name,
        page_count=page_count,
        char_count=char_count,
        has_text_layer=has_text_layer,
        pages=pages,
    )


@dataclass
class ExtractReport:
    extracted: list[str] = field(default_factory=list)
    no_text_layer: list[str] = field(default_factory=list)
    missing_pdf: list[str] = field(default_factory=list)


def extract_all(
    raw_dir: Path | None = None,
    processed_dir: Path | None = None,
    db_path: Path | None = None,
) -> ExtractReport:
    raw_dir = raw_dir if raw_dir is not None else config.RAW_DIR
    processed_dir = processed_dir if processed_dir is not None else config.PROCESSED_DIR
    processed_dir.mkdir(parents=True, exist_ok=True)

    init_db(db_path)
    report = ExtractReport()

    with connect(db_path) as conn:
        filenames = [r["filename"] for r in conn.execute("SELECT filename FROM papers")]

        for filename in filenames:
            pdf_path = raw_dir / filename
            if not pdf_path.exists():
                report.missing_pdf.append(filename)
                continue

            result = extract_paper(pdf_path)
            stem = pdf_path.stem
            (processed_dir / f"{stem}.txt").write_text(result.to_text(), encoding="utf-8")
            (processed_dir / f"{stem}.json").write_text(result.to_json(), encoding="utf-8")

            conn.execute(
                "UPDATE papers SET has_text_layer = ? WHERE filename = ?",
                (1 if result.has_text_layer else 0, filename),
            )
            report.extracted.append(filename)
            if not result.has_text_layer:
                report.no_text_layer.append(filename)

        conn.commit()

    return report
