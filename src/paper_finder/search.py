"""Search and browse the segmented question bank.

``search()`` is keyword search (SQLite FTS5 + BM25). ``browse_by_topic()`` is a
plain index scan over ``question_topics`` with OR (union) semantics across the
requested syllabus sections, newest paper first -- it powers the topic page.
"""

from __future__ import annotations

import re
from collections.abc import Sequence
from dataclasses import dataclass, field
from pathlib import Path

from paper_finder.db import connect, init_db
from paper_finder.topics import CODES

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
    topic_codes: tuple[str, ...] = field(default_factory=tuple)
    crop_count: int = 0  # number of question-image crops; 0 = show text only

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

_KIND_FILTER = (
    "(:kind = 'all' OR (:kind = 'mcq' AND q.is_mcq = 1) OR (:kind = 'theory' AND q.is_mcq = 0))"
)

_TOPIC_CODES_SUBQUERY = (
    "(SELECT group_concat(qt.topic_code) FROM question_topics qt WHERE qt.question_id = q.id)"
)

_SEARCH_SELECT = f"""
SELECT
    p.filename, p.subject_name, p.year, p.session, p.paper, p.variant,
    q.question_number, q.question_text, q.marks, q.page_start, q.has_figure, q.crop_count,
    (SELECT a.answer_text FROM answers a WHERE a.question_id = q.id LIMIT 1) AS answer,
    {_TOPIC_CODES_SUBQUERY} AS topic_codes,
    bm25(questions_fts) AS score
FROM questions_fts
JOIN questions q ON q.id = questions_fts.rowid
JOIN papers p ON p.id = q.paper_id
WHERE questions_fts MATCH :query
  AND {_KIND_FILTER}
"""


def _split_codes(raw: str | None) -> tuple[str, ...]:
    """group_concat output -> a sorted tuple (SQLite does not order the concat)."""
    return tuple(sorted(raw.split(","))) if raw else ()


def search(
    query: str,
    limit: int = 5,
    db_path: Path | None = None,
    kind: str = "all",
    years: Sequence[int] | None = None,
    sessions: Sequence[str] | None = None,
    variants: Sequence[int] | None = None,
) -> list[SearchHit]:
    """Keyword search. ``kind`` filters by question type: ``all`` (default),
    ``mcq`` (multiple-choice questions only) or ``theory`` (structured only).
    ``years`` / ``sessions`` / ``variants`` narrow to matching papers; an empty
    or missing axis places no restriction on it."""
    fts_query = build_fts_query(query)
    if not fts_query:
        return []
    if kind not in KINDS:
        kind = "all"

    scope_where, scope_params = _paper_scope(years, sessions, variants)
    sql = _SEARCH_SELECT
    if scope_where:
        sql += "  AND " + "\n  AND ".join(scope_where) + "\n"
    sql += "ORDER BY score\nLIMIT :limit"
    params = {"query": fts_query, "limit": limit, "kind": kind, **scope_params}

    init_db(db_path)
    with connect(db_path) as conn:
        rows = conn.execute(sql, params).fetchall()

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
            topic_codes=_split_codes(row["topic_codes"]),
            crop_count=row["crop_count"],
        )
        for row in rows
    ]


_BROWSE_COLUMNS = f"""
    p.filename, p.subject_name, p.year, p.session, p.paper, p.variant,
    q.question_number, q.question_text, q.marks, q.page_start, q.has_figure, q.crop_count,
    (SELECT a.answer_text FROM answers a WHERE a.question_id = q.id LIMIT 1) AS answer,
    {_TOPIC_CODES_SUBQUERY} AS topic_codes
"""

_BROWSE_ORDER = "ORDER BY p.year DESC, p.session DESC, p.paper, p.variant, q.question_number"


def _in_clause(prefix: str, values: Sequence) -> tuple[str, dict]:
    """``('a', ['x', 'y'])`` -> ``('(:a0, :a1)', {'a0': 'x', 'a1': 'y'})``."""
    params = {f"{prefix}{i}": v for i, v in enumerate(values)}
    return "(" + ", ".join(f":{k}" for k in params) + ")", params


def _paper_scope(
    years: Sequence[int] | None,
    sessions: Sequence[str] | None,
    variants: Sequence[int] | None,
) -> tuple[list[str], dict]:
    """WHERE clauses + bind params restricting ``p`` (papers) by year / session /
    variant. An empty or missing axis places no restriction on it."""
    where: list[str] = []
    params: dict = {}
    if years:
        sql, p = _in_clause("y", [int(y) for y in years])
        where.append(f"p.year IN {sql}")
        params.update(p)
    if sessions:
        sql, p = _in_clause("s", list(sessions))
        where.append(f"p.session IN {sql}")
        params.update(p)
    if variants:
        sql, p = _in_clause("v", [int(v) for v in variants])
        where.append(f"p.variant IN {sql}")
        params.update(p)
    return where, params


def _browse_filters(
    topic_codes: Sequence[str],
    kind: str,
    years: Sequence[int] | None,
    sessions: Sequence[str] | None,
    variants: Sequence[int] | None,
) -> tuple[str, dict]:
    """Shared WHERE fragment + params for ``browse_by_topic`` and its COUNT."""
    codes_sql, params = _in_clause("t", topic_codes)
    where = [
        f"q.id IN (SELECT qt.question_id FROM question_topics qt "
        f"WHERE qt.topic_code IN {codes_sql})",
        _KIND_FILTER,
    ]
    params["kind"] = kind
    scope_where, scope_params = _paper_scope(years, sessions, variants)
    where.extend(scope_where)
    params.update(scope_params)
    return " AND ".join(where), params


def browse_by_topic(
    topic_codes: Sequence[str],
    *,
    kind: str = "all",
    years: Sequence[int] | None = None,
    sessions: Sequence[str] | None = None,
    variants: Sequence[int] | None = None,
    limit: int = 20,
    offset: int = 0,
    db_path: Path | None = None,
) -> tuple[list[SearchHit], int]:
    """Every question tagged with *any* of ``topic_codes`` (union), newest paper
    first. Returns ``(page, total)`` where ``total`` is the full match count
    ignoring ``limit``/``offset`` -- the flashcard pager renders "12 / 147" from
    the first call. Unknown codes are dropped; no valid code -> ``([], 0)``."""
    codes = tuple(sorted(c for c in dict.fromkeys(topic_codes) if c in CODES))
    if not codes:
        return [], 0
    if kind not in KINDS:
        kind = "all"

    where, params = _browse_filters(codes, kind, years, sessions, variants)
    init_db(db_path)
    with connect(db_path) as conn:
        total = conn.execute(
            f"SELECT COUNT(*) FROM questions q JOIN papers p ON p.id = q.paper_id WHERE {where}",
            params,
        ).fetchone()[0]
        rows = conn.execute(
            f"SELECT {_BROWSE_COLUMNS} FROM questions q JOIN papers p ON p.id = q.paper_id "
            f"WHERE {where} {_BROWSE_ORDER} LIMIT :limit OFFSET :offset",
            {**params, "limit": limit, "offset": offset},
        ).fetchall()

    page = [
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
            score=0.0,
            topic_codes=_split_codes(row["topic_codes"]),
            crop_count=row["crop_count"],
        )
        for row in rows
    ]
    return page, total


def topic_counts(
    *,
    kind: str = "all",
    years: Sequence[int] | None = None,
    sessions: Sequence[str] | None = None,
    variants: Sequence[int] | None = None,
    db_path: Path | None = None,
) -> dict:
    """Per-topic question count under the current filters, every topic present
    even at zero, plus corpus ``total`` and ``unlabelled`` counts.

    Shape::

        {"topics": [{"code", "number", "name", "subsections", "count"}, ...],
         "total": int, "unlabelled": int}
    """
    from paper_finder.topics import TOPICS

    if kind not in KINDS:
        kind = "all"

    where = [_KIND_FILTER]
    params: dict = {"kind": kind}
    scope_where, scope_params = _paper_scope(years, sessions, variants)
    where.extend(scope_where)
    params.update(scope_params)
    filt = " AND ".join(where)

    init_db(db_path)
    with connect(db_path) as conn:
        rows = conn.execute(
            f"""
            SELECT qt.topic_code AS code, COUNT(*) AS n
            FROM question_topics qt
            JOIN questions q ON q.id = qt.question_id
            JOIN papers p ON p.id = q.paper_id
            WHERE {filt}
            GROUP BY qt.topic_code
            """,
            params,
        ).fetchall()
        counts = {r["code"]: r["n"] for r in rows}

        total = conn.execute(
            f"SELECT COUNT(*) FROM questions q JOIN papers p ON p.id = q.paper_id WHERE {filt}",
            params,
        ).fetchone()[0]
        labelled = conn.execute(
            f"""
            SELECT COUNT(*) FROM questions q JOIN papers p ON p.id = q.paper_id
            WHERE {filt}
              AND q.id IN (SELECT qt.question_id FROM question_topics qt)
            """,
            params,
        ).fetchone()[0]

    return {
        "topics": [
            {
                "code": t.code,
                "number": t.number,
                "name": t.name,
                "subsections": list(t.subsections),
                "count": counts.get(t.code, 0),
            }
            for t in TOPICS
        ],
        "total": total,
        "unlabelled": total - labelled,
    }
