"""Scan ``data/raw/`` and record every recognised CIE paper in the database.

Idempotent: running it again updates existing rows, adds new files, and prunes
rows whose PDF has been removed from ``data/raw/``.
"""

from __future__ import annotations

import datetime as dt
from dataclasses import dataclass, field
from pathlib import Path

from paper_finder import config
from paper_finder.db import connect, init_db
from paper_finder.filenames import PaperName, parse_filename

_UPSERT = """
INSERT INTO papers (subject_code, subject_name, year, session, paper, variant,
                    paper_type, filename, downloaded_at)
VALUES (:subject_code, :subject_name, :year, :session, :paper, :variant,
        :paper_type, :filename, :downloaded_at)
ON CONFLICT(filename) DO UPDATE SET
    subject_code  = excluded.subject_code,
    subject_name  = excluded.subject_name,
    year          = excluded.year,
    session       = excluded.session,
    paper         = excluded.paper,
    variant       = excluded.variant,
    paper_type    = excluded.paper_type,
    downloaded_at = excluded.downloaded_at
"""


@dataclass
class IngestReport:
    found: int = 0  # PDFs present in data/raw/
    ingested: int = 0  # rows inserted or updated
    pruned: list[str] = field(default_factory=list)  # rows removed (file gone)
    skipped: list[str] = field(default_factory=list)  # not a CIE paper type we track
    unknown_subjects: list[str] = field(default_factory=list)


def _row(paper: PaperName, mtime: float) -> dict:
    downloaded_at = dt.datetime.fromtimestamp(mtime, tz=dt.UTC).isoformat(timespec="seconds")
    return {
        "subject_code": paper.subject_code,
        "subject_name": paper.subject_name,
        "year": paper.year,
        "session": paper.session,
        "paper": paper.paper,
        "variant": paper.variant,
        "paper_type": paper.paper_type,
        "filename": paper.filename,
        "downloaded_at": downloaded_at,
    }


def ingest(raw_dir: Path | None = None, db_path: Path | None = None) -> IngestReport:
    raw_dir = raw_dir if raw_dir is not None else config.RAW_DIR
    init_db(db_path)
    report = IngestReport()

    pdfs = sorted(raw_dir.glob("*.pdf"))
    report.found = len(pdfs)

    parsed: list[tuple[PaperName, float]] = []
    for pdf in pdfs:
        if pdf.name in config.EXCLUDE_FILENAMES:
            report.skipped.append(pdf.name)
            continue
        paper = parse_filename(pdf.name)
        if paper is None or paper.paper_type not in config.PAPER_TYPES:
            report.skipped.append(pdf.name)
            continue
        if paper.subject_name is None:
            report.unknown_subjects.append(paper.subject_code)
        parsed.append((paper, pdf.stat().st_mtime))

    present = {paper.filename for paper, _ in parsed}

    with connect(db_path) as conn:
        for paper, mtime in parsed:
            conn.execute(_UPSERT, _row(paper, mtime))
        report.ingested = len(parsed)

        existing = {r["filename"] for r in conn.execute("SELECT filename FROM papers")}
        stale = sorted(existing - present)
        if stale:
            conn.executemany("DELETE FROM papers WHERE filename = ?", [(name,) for name in stale])
            report.pruned = stale
        conn.commit()

    report.unknown_subjects = sorted(set(report.unknown_subjects))
    return report
