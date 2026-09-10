"""Load syllabus topic labels from ``labels/question_topics.tsv`` into the DB.

The TSV is the source of truth: one row per labelled question, keyed on
``(filename, question_number)`` -- **not** ``questions.id``, which ``segment.py``
reassigns on every ``paper-finder build``. ``paper-finder topics`` re-materialises
the ``question_topics`` table from it, and ``build`` runs that as its last step to
repair the cascade ``segment`` triggers.

Row format (tab-separated, no quoting -- no field may contain a tab)::

    filename <TAB> question_number <TAB> topic_codes <TAB> source

``topic_codes`` is a comma-separated list of syllabus section codes, drawn from
the taxonomy the row's subject + paper uses (``s01``..``s11`` for a 9702 paper,
``fp1``..``fp7`` for 9231 Paper 1, ``fs1``..``fs5`` for 9231 Paper 4);
``source`` is ``hand`` or ``llm``. Blank lines and ``#`` comments are skipped,
matching ``evaluate.load_validation``.
"""

from __future__ import annotations

from collections import Counter
from dataclasses import dataclass, field
from pathlib import Path

from paper_finder import config
from paper_finder.db import connect, init_db
from paper_finder.filenames import parse_filename
from paper_finder.topics import CODES, taxonomy_for

SOURCES = ("hand", "llm")


def default_path() -> Path:
    """Resolved at call time so tests can repoint ``config.PROJECT_ROOT``."""
    return config.PROJECT_ROOT / "labels" / "question_topics.tsv"


@dataclass(frozen=True)
class LabelRow:
    filename: str
    question_number: int
    topic_codes: tuple[str, ...]
    source: str


@dataclass
class LoadReport:
    rows: int = 0  # label rows read from the file
    labelled: int = 0  # questions in the DB that got >= 1 topic
    unlabelled: int = 0  # questions in the DB with no topic
    counts: dict[str, int] = field(default_factory=dict)  # topic code -> question count
    orphans: list[str] = field(default_factory=list)  # "filename Qn" with no matching question
    # subject_name -> (labelled, unlabelled) so adding 9231 doesn't make the
    # Physics totals look broken.
    by_subject: dict[str, tuple[int, int]] = field(default_factory=dict)


def parse_labels(path: Path) -> list[LabelRow]:
    """Parse the TSV. Raises ``ValueError`` (naming the line) on a typo:
    an unknown topic code, an empty code list, or a duplicate question key."""
    rows: list[LabelRow] = []
    seen: set[tuple[str, int]] = set()
    for lineno, raw in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        parts = line.split("\t")
        if len(parts) != 4:
            raise ValueError(f"{path}:{lineno}: expected 4 tab-separated fields, got {len(parts)}")
        filename, number_text, codes_text, source = (p.strip() for p in parts)

        try:
            number = int(number_text)
        except ValueError:
            raise ValueError(
                f"{path}:{lineno}: question number is not an integer: {number_text!r}"
            ) from None

        codes = tuple(c.strip() for c in codes_text.split(",") if c.strip())
        if not codes:
            raise ValueError(f"{path}:{lineno}: no topic codes (delete the row instead)")
        unknown = [c for c in codes if c not in CODES]
        if unknown:
            raise ValueError(f"{path}:{lineno}: unknown topic code(s): {', '.join(unknown)}")

        # Codes must belong to the taxonomy the filename's subject + paper uses,
        # not just the global union -- a 9231 Paper 4 row tagged 's02', or a 9702
        # row tagged 'fp1', is a mislabel.
        parsed = parse_filename(filename)
        tax = taxonomy_for(parsed.subject_code, parsed.paper) if parsed else None
        if tax is not None:
            off_taxonomy = [c for c in codes if c not in tax.codes]
            if off_taxonomy:
                raise ValueError(
                    f"{path}:{lineno}: {', '.join(off_taxonomy)} not in the "
                    f"{tax.subject_name} taxonomy (expected {'/'.join(sorted(tax.codes))})"
                )

        if source not in SOURCES:
            raise ValueError(f"{path}:{lineno}: source must be one of {SOURCES}, got {source!r}")

        key = (filename, number)
        if key in seen:
            raise ValueError(f"{path}:{lineno}: duplicate label for {filename} Q{number}")
        seen.add(key)

        rows.append(LabelRow(filename, number, tuple(dict.fromkeys(codes)), source))
    return rows


def load_topic_labels(path: Path | None = None, db_path: Path | None = None) -> LoadReport:
    """Rebuild ``question_topics`` from the TSV. Idempotent."""
    path = path if path is not None else default_path()
    init_db(db_path)
    report = LoadReport()

    if not path.exists():
        return report

    label_rows = parse_labels(path)
    report.rows = len(label_rows)

    with connect(db_path) as conn:
        conn.execute("DELETE FROM question_topics")
        labelled_ids: set[int] = set()
        code_counter: Counter[str] = Counter()

        for row in label_rows:
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
            for code in row.topic_codes:
                conn.execute(
                    "INSERT OR IGNORE INTO question_topics (question_id, topic_code) VALUES (?, ?)",
                    (question["id"], code),
                )
                code_counter[code] += 1
            labelled_ids.add(question["id"])

        total_questions = conn.execute("SELECT COUNT(*) FROM questions").fetchone()[0]

        by_subject: dict[str, tuple[int, int]] = {}
        subject_rows = conn.execute(
            """
            SELECT COALESCE(p.subject_name, p.subject_code) AS subject,
                   q.id IN (SELECT question_id FROM question_topics) AS is_labelled,
                   COUNT(*) AS n
            FROM questions q
            JOIN papers p ON p.id = q.paper_id
            GROUP BY subject, is_labelled
            """
        ).fetchall()
        for r in subject_rows:
            done, todo = by_subject.get(r["subject"], (0, 0))
            if r["is_labelled"]:
                done += r["n"]
            else:
                todo += r["n"]
            by_subject[r["subject"]] = (done, todo)
        conn.commit()

    report.labelled = len(labelled_ids)
    report.unlabelled = total_questions - report.labelled
    report.counts = dict(code_counter)
    report.by_subject = by_subject
    return report
