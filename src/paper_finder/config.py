"""Project-wide paths and reference data.

Stage 1 only needs the paths and the lookup tables below. As new subjects are
downloaded, add their codes to ``SUBJECTS``.
"""

from __future__ import annotations

from pathlib import Path

# ``config.py`` lives at ``src/paper_finder/config.py`` -> project root is 2 up.
PROJECT_ROOT = Path(__file__).resolve().parents[2]

DATA_DIR = PROJECT_ROOT / "data"
RAW_DIR = DATA_DIR / "raw"  # downloaded PDFs — never edited by the pipeline
PROCESSED_DIR = DATA_DIR / "processed"  # extracted text / JSON, regenerated from RAW_DIR
DB_PATH = PROJECT_ROOT / "papers.db"

# CIE subject codes seen so far. Extend as the corpus grows.
SUBJECTS: dict[str, str] = {
    "9700": "Biology",
    "9701": "Chemistry",
    "9702": "Physics",
    "9708": "Economics",
    "9709": "Mathematics",
    "9231": "Further Mathematics",
}

# Exam session letter -> human name.
SESSIONS: dict[str, str] = {
    "s": "May/June",
    "w": "Oct/Nov",
    "m": "Feb/March",
}

# Document types in a CIE filename. Only the keys here are recorded on ingest;
# anything else in data/raw/ is reported as skipped.
PAPER_TYPES: dict[str, str] = {
    "qp": "Question Paper",
    "ms": "Mark Scheme",
    "in": "Insert",
    "gt": "Grade Thresholds",
    "er": "Examiner Report",
}
