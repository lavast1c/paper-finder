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
CROP_DIR = DATA_DIR / "crops"  # per-question PNG/WebP crops, regenerated from RAW_DIR + papers.db
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

# Some CIE codes split into papers that are effectively separate subjects with
# their own syllabus content and topic taxonomy. A (code, paper) here overrides
# SUBJECTS for papers.subject_name -- this is the value the UI's Subject filter
# offers and paper_finder.topics.taxonomy_by_name() keys on.
SUBJECT_PAPER_NAMES: dict[tuple[str, int], str] = {
    ("9231", 1): "Further Pure Mathematics",  # 9231 Paper 1
    ("9231", 4): "Further Probability & Statistics",  # 9231 Paper 4
    ("9709", 1): "Pure Mathematics 1",  # 9709 Paper 1
    ("9709", 5): "Probability & Statistics 1",  # 9709 Paper 5
}


def subject_name_for(subject_code: str, paper: int | None) -> str | None:
    """papers.subject_name for a paper: the (code, paper) override, else SUBJECTS."""
    if paper is not None:
        override = SUBJECT_PAPER_NAMES.get((subject_code, paper))
        if override is not None:
            return override
    return SUBJECTS.get(subject_code)


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
# PapaCambridge stores every PDF flat in one directory, so the URL is just
# "{MIRROR_BASE_URL}/{filename}". A paper it does not hold is answered with a
# 302 redirect to the site homepage rather than a 404 -- download._urllib_fetcher
# treats "redirected away from the .pdf" as not-found. To use a folder-structured
# mirror instead, edit both this value and download.mirror_url.
# (The former mirror, dynamicpapers.com/wp-content/uploads/2015/09, began
# returning HTTP 500 for every direct PDF request in 2026.)
MIRROR_BASE_URL = "https://pastpapers.papacambridge.com/directories/CAIE/CAIE-pastpapers/upload"
USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/120.0 Safari/537.36"
)
REQUEST_DELAY_SECONDS = 1.5
REQUEST_TIMEOUT_SECONDS = 30
DOWNLOAD_LOG_PATH = DATA_DIR / "download_log.csv"

# --- topic classification (`paper-finder classify`) ---
# The model that labels questions with syllabus sections. Override per-run with
# `--model`. Only used when no Labeller is injected (i.e. the real Claude call).
CLASSIFY_MODEL = "claude-sonnet-5"
CLASSIFY_BATCH_SIZE = 20  # questions per API call; the taxonomy prompt is cached across them

# Default scope for `paper-finder download`; override per-run with CLI flags.
# `subjects` is per-code: each subject carries its own papers + variants, since
# 9702 (P1 MCQ / P2 structured), 9231 (P1 Further Pure / P4 Further Stats) and
# 9709 (P1 Pure Math 1 / P5 Prob & Stats 1) have nothing in common. years /
# sessions / types are shared. The candidate cross-product over-generates
# (e.g. 9702 "m" is variant 2 only); 404s are expected and harmless -- download
# treats "not on mirror" as a non-event.
DOWNLOAD_SCOPE: dict = {
    "subjects": {
        "9702": {"papers": [1, 2], "variants": [1, 2, 3, 4]},  # a 4th variant was added from 2025
        "9231": {"papers": [1, 4], "variants": [1, 2, 3]},  # Further Maths: Pure 1 + Prob & Stats
        "9709": {"papers": [1, 5], "variants": [1, 2, 3]},  # Maths: Pure 1 + Prob & Stats 1
    },
    "years": [2020, 2021, 2022, 2023, 2024, 2025, 2026],
    "sessions": ["s", "w", "m"],  # May/June, Oct/Nov, Feb/March
    "types": ["qp", "ms"],
}
