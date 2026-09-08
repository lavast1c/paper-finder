"""Keyword search over the segmented question bank (SQLite FTS5 + BM25)."""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path

from paper_finder.db import connect, init_db

_TOKEN = re.compile(r"[0-9a-z]+")


@dataclass
class SearchHit:
    filename: str
    subject_name: str | None
    year: int
    session: str
    paper: int | None
    variant: int | None
    question_number: int
    question_text: str
    marks: int | None
    answer: str | None
    page_start: int | None
    has_figure: bool
    score: float

    @property
    def paper_variant(self) -> str:
        if self.paper is None:
            return "?"
        return f"{self.paper}{self.variant if self.variant is not None else ''}"

    @property
    def label(self) -> str:
        subject = self.subject_name or "?"
        return (
            f"{subject} {self.year} {self.session} "
            f"paper {self.paper_variant} Q{self.question_number}"
        )


def build_fts_query(text: str) -> str:
    """Free-text phrase -> a safe FTS5 MATCH string (each word quoted, OR-joined).

    Quoting isolates every token so punctuation in the user's text can never be
    read as FTS5 query syntax. BM25 then ranks questions that contain more of the
    words higher.
    """
    tokens = _TOKEN.findall(text.lower())
    return " OR ".join(f'"{token}"' for token in tokens)


KINDS = ("all", "mcq", "theory")

_SEARCH_SQL = """
SELECT
    p.filename, p.subject_name, p.year, p.session, p.paper, p.variant,
    q.question_number, q.question_text, q.marks, q.page_start, q.has_figure,
    (SELECT a.answer_text FROM answers a WHERE a.question_id = q.id LIMIT 1) AS answer,
    bm25(questions_fts) AS score
FROM questions_fts
JOIN questions q ON q.id = questions_fts.rowid
JOIN papers p ON p.id = q.paper_id
WHERE questions_fts MATCH :query
  AND (:kind = 'all'
       OR (:kind = 'mcq' AND q.is_mcq = 1)
       OR (:kind = 'theory' AND q.is_mcq = 0))
ORDER BY score
LIMIT :limit
"""


def search(
    query: str,
    limit: int = 5,
    db_path: Path | None = None,
    kind: str = "all",
) -> list[SearchHit]:
    """Keyword search. ``kind`` filters by question type: ``all`` (default),
    ``mcq`` (multiple-choice questions only) or ``theory`` (structured only)."""
    fts_query = build_fts_query(query)
    if not fts_query:
        return []
    if kind not in KINDS:
        kind = "all"

    init_db(db_path)
    with connect(db_path) as conn:
        rows = conn.execute(
            _SEARCH_SQL, {"query": fts_query, "limit": limit, "kind": kind}
        ).fetchall()

    return [
        SearchHit(
            filename=row["filename"],
            subject_name=row["subject_name"],
            year=row["year"],
            session=row["session"],
            paper=row["paper"],
            variant=row["variant"],
            question_number=row["question_number"],
            question_text=row["question_text"],
            marks=row["marks"],
            answer=row["answer"],
            page_start=row["page_start"],
            has_figure=bool(row["has_figure"]),
            score=row["score"],
        )
        for row in rows
    ]
