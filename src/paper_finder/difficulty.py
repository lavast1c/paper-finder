"""Load relative difficulty labels from ``labels/question_difficulty.tsv`` into the DB.

Same shape and reasoning as :mod:`paper_finder.labels`: the TSV is the source of
truth, keyed on ``(filename, question_number)`` -- never ``questions.id``, which
``segment.py`` reassigns on every build -- and ``paper-finder difficulty``
re-materialises the ``question_difficulty`` table from it (``build`` runs it
right after ``topics``).

Row format (tab-separated, no quoting)::

    filename <TAB> question_number <TAB> difficulty <TAB> source

``difficulty`` is an integer 1-5, relative to the question's own subject;
``source`` is ``hand`` or ``llm``. Blank lines and ``#`` comments are skipped.
"""

from __future__ import annotations

from collections import Counter
from dataclasses import dataclass, field
from pathlib import Path

from paper_finder import config
from paper_finder.db import connect, init_db

LEVELS = (1, 2, 3, 4, 5)
SOURCES = ("hand", "llm")


def default_path() -> Path:
    """Resolved at call time so tests can repoint ``config.PROJECT_ROOT``."""
    return config.PROJECT_ROOT / "labels" / "question_difficulty.tsv"


@dataclass(frozen=True)
class DifficultyRow:
    filename: str
    question_number: int
    difficulty: int
    source: str


@dataclass
class DifficultyReport:
    rows: int = 0  # rows read from the file
    rated: int = 0  # questions in the DB that got a difficulty
    unrated: int = 0  # questions in the DB with none
    counts: dict[int, int] = field(default_factory=dict)  # level -> question count
    orphans: list[str] = field(default_factory=list)  # "filename Qn" with no matching question
    by_subject: dict[str, tuple[int, int]] = field(default_factory=dict)  # (rated, unrated)


def parse_difficulty(path: Path) -> list[DifficultyRow]:
    """Parse the TSV. Raises ``ValueError`` (naming the line) on a typo: a level
    outside 1-5, an unknown source, or a duplicate question key."""
    rows: list[DifficultyRow] = []
    seen: set[tuple[str, int]] = set()
    for lineno, raw in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        parts = line.split("\t")
        if len(parts) != 4:
            raise ValueError(f"{path}:{lineno}: expected 4 tab-separated fields, got {len(parts)}")
        filename, number_text, level_text, source = (p.strip() for p in parts)

        try:
            number = int(number_text)
        except ValueError:
            raise ValueError(
                f"{path}:{lineno}: question number is not an integer: {number_text!r}"
            ) from None
        try:
            level = int(level_text)
        except ValueError:
            level = None
        if level not in LEVELS:
            raise ValueError(f"{path}:{lineno}: difficulty must be 1-5, got {level_text!r}")
        if source not in SOURCES:
            raise ValueError(f"{path}:{lineno}: source must be one of {SOURCES}, got {source!r}")

        key = (filename, number)
        if key in seen:
            raise ValueError(f"{path}:{lineno}: duplicate difficulty for {filename} Q{number}")
        seen.add(key)
        rows.append(DifficultyRow(filename, number, level, source))
    return rows


def load_difficulty_labels(
    path: Path | None = None, db_path: Path | None = None
) -> DifficultyReport:
    """Rebuild ``question_difficulty`` from the TSV. Idempotent."""
    path = path if path is not None else default_path()
    init_db(db_path)
    report = DifficultyReport()
    if not path.exists():
        return report

    rows = parse_difficulty(path)
    report.rows = len(rows)
    level_counter: Counter[int] = Counter()

    with connect(db_path) as conn:
        conn.execute("DELETE FROM question_difficulty")
        for row in rows:
            question = conn.execute(
                """
                SELECT q.id FROM questions q
                JOIN papers p ON p.id = q.paper_id
                WHERE p.filename = ? AND q.question_number = ?
                """,
                (row.filename, row.question_number),
            ).fetchone()
            if question is None:
                report.orphans.append(f"{row.filename} Q{row.question_number}")
                continue
            conn.execute(
                "INSERT INTO question_difficulty (question_id, difficulty) VALUES (?, ?)",
                (question["id"], row.difficulty),
            )
            level_counter[row.difficulty] += 1

        for r in conn.execute(
            """
            SELECT COALESCE(p.subject_name, p.subject_code) AS subject,
                   COUNT(d.question_id) AS rated,
                   COUNT(*) - COUNT(d.question_id) AS unrated
            FROM questions q
            JOIN papers p ON p.id = q.paper_id
            LEFT JOIN question_difficulty d ON d.question_id = q.id
            GROUP BY subject
            """
        ):
            report.by_subject[r["subject"]] = (r["rated"], r["unrated"])
        conn.commit()

    report.rated = sum(level_counter.values())
    report.unrated = sum(u for _, u in report.by_subject.values())
    report.counts = dict(level_counter)
    return report
