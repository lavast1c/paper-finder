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

# --- Stage 4: automated download ---
# Papers are fetched by generating their predictable URLs, not by scraping.
# Dynamic Papers stores every PDF flat in one directory, so the URL is just
# "{MIRROR_BASE_URL}/{filename}". To use a folder-structured mirror instead, edit
# both this value and download.mirror_url.
MIRROR_BASE_URL = "https://dynamicpapers.com/wp-content/uploads/2015/09"
USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/120.0 Safari/537.36"
)
REQUEST_DELAY_SECONDS = 1.5
REQUEST_TIMEOUT_SECONDS = 30
DOWNLOAD_LOG_PATH = DATA_DIR / "download_log.csv"

# Default scope for `paper-finder download`; override per-run with CLI flags.
DOWNLOAD_SCOPE: dict[str, list] = {
    "subjects": ["9702"],  # Physics only for now
    "years": [2024, 2025],  # recent, reliably published on the mirror
    "sessions": ["s", "w"],  # May/June, Oct/Nov (Physics has no "m")
    "papers": [1, 2],  # 1 = multiple choice, 2 = AS structured
    "variants": [1, 2, 3],  # regional time zones
    "types": ["qp", "ms"],
}
