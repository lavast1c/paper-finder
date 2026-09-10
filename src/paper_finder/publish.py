"""Publish the local question bank to Supabase Postgres (development only).

Pushes ONLY filename-derived paper metadata + question text + answer text into
the deployed Postgres. Never the PDFs, never ``source_url``, never the download
log. Replace-all inside one transaction, so a refresh is atomic and idempotent.

Needs the optional ``publish`` extra (``pip install -e ".[publish]"`` -> psycopg)
and a ``SUPABASE_DB_URL`` (the Supabase **session** pooler URI) in the
environment or in a local ``.env``. Not part of ``paper-finder build`` -- it has
a network side effect, like ``download``.
"""

from __future__ import annotations

import os
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from paper_finder import config
from paper_finder.db import connect
from paper_finder.topics import TOPICS

# str (db url) -> a context-manager connection with .cursor() and commit-on-exit
Connector = Callable[[str], Any]

_PAPERS_SQL = """
SELECT p.id, p.subject_code, p.subject_name, p.year, p.session, p.paper,
       p.variant, p.filename
FROM papers p
WHERE p.paper_type = 'qp'
  AND EXISTS (SELECT 1 FROM questions q WHERE q.paper_id = p.id)
ORDER BY p.id
"""

_QUESTIONS_SQL = """
SELECT q.id, q.paper_id, q.question_number, q.question_text, q.marks, q.has_figure,
       (SELECT a.answer_text FROM answers a WHERE a.question_id = q.id LIMIT 1),
       (SELECT group_concat(qt.topic_code) FROM question_topics qt WHERE qt.question_id = q.id),
       q.crop_count,
       (SELECT a.answer_crop_count FROM answers a WHERE a.question_id = q.id LIMIT 1)
FROM questions q
JOIN papers p ON p.id = q.paper_id
WHERE p.paper_type = 'qp'
ORDER BY q.id
"""

_INSERT_PAPERS = (
    "INSERT INTO public.papers "
    "(id, subject_code, subject_name, year, session, paper, variant, filename) "
    "VALUES (%s, %s, %s, %s, %s, %s, %s, %s)"
)
_INSERT_QUESTIONS = (
    "INSERT INTO public.questions "
    "(id, paper_id, question_number, question_text, marks, has_figure, answer_text, "
    "topic_codes, crop_count, answer_crop_count) "
    "VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)"
)
# public.topics has no FK from public.papers, so `DELETE FROM public.papers` does
# not cascade to it -- re-upsert it from the taxonomy on every publish so it
# cannot drift. paper_finder.topics stays the single source of truth.
_UPSERT_TOPICS = (
    "INSERT INTO public.topics (code, number, name, subsections) "
    "VALUES (%s, %s, %s, %s) "
    "ON CONFLICT (code) DO UPDATE SET "
    "number = excluded.number, name = excluded.name, subsections = excluded.subsections"
)
_TOPIC_ROWS = [(t.code, t.number, t.name, list(t.subsections)) for t in TOPICS]


@dataclass
class PublishReport:
    papers: int = 0
    questions: int = 0
    answers: int = 0
    dry_run: bool = False


def read_local(db_path: Path | None = None) -> tuple[list[tuple], list[tuple]]:
    """Rows to publish: ``qp`` papers that have questions, and their questions.

    Mark schemes, ``source_url``, ``page_start`` and the like are dropped here so
    the "nothing sensitive leaves the machine" rule is structural, not a policy.
    """
    with connect(db_path) as conn:
        papers = [tuple(row) for row in conn.execute(_PAPERS_SQL)]
        questions = [_question_row(row) for row in conn.execute(_QUESTIONS_SQL)]
    return papers, questions


def _question_row(row: tuple) -> tuple:
    """SQLite row -> INSERT tuple. Coerce ``has_figure`` (col 5, stored 0/1) to a
    real ``bool`` and the ``group_concat`` topic codes (col 7, ``"s02,s09"`` or
    ``None``) to a sorted ``list`` -- psycopg3 adapts a list to a Postgres array.
    Col 8 (``crop_count``) is already an int and rides along untouched. Col 9
    (``answer_crop_count``) is NULL when the question has no answer row -- send 0."""
    values = list(row)
    values[5] = bool(values[5])
    values[7] = sorted(values[7].split(",")) if values[7] else []
    values[9] = values[9] or 0
    return tuple(values)


def _read_dotenv(path: Path) -> dict[str, str]:
    values: dict[str, str] = {}
    if not path.is_file():
        return values
    for raw in path.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        values[key.strip()] = value.strip().strip('"').strip("'")
    return values


def resolve_db_url(explicit: str | None = None) -> str:
    """``--db-url`` > ``SUPABASE_DB_URL`` env > ``.env`` file, else a clear error."""
    if explicit:
        return explicit
    from_env = os.environ.get("SUPABASE_DB_URL")
    if from_env:
        return from_env
    from_file = _read_dotenv(config.PROJECT_ROOT / ".env").get("SUPABASE_DB_URL")
    if from_file:
        return from_file
    raise RuntimeError(
        "No SUPABASE_DB_URL. Put it in .env (gitignored), export it, or pass "
        "--db-url.\nSupabase dashboard -> Project Settings -> Database -> "
        "Connection string -> Session pooler (IPv4, port 5432) -- NOT the 6543 "
        "transaction pooler."
    )


def _psycopg_connector(url: str) -> Any:
    import psycopg  # optional 'publish' extra; imported lazily

    return psycopg.connect(url)


def publish(
    *,
    db_path: Path | None = None,
    db_url: str | None = None,
    dry_run: bool = False,
    connect_pg: Connector | None = None,
) -> PublishReport:
    papers, questions = read_local(db_path)
    report = PublishReport(
        papers=len(papers),
        questions=len(questions),
        answers=sum(1 for q in questions if q[6] is not None),
        dry_run=dry_run,
    )
    if dry_run:
        return report

    url = resolve_db_url(db_url)
    connector = connect_pg or _psycopg_connector
    with connector(url) as conn:  # psycopg3: commit on clean exit, rollback on raise
        with conn.cursor() as cur:
            cur.execute("DELETE FROM public.papers")  # cascades to questions
            cur.executemany(_UPSERT_TOPICS, _TOPIC_ROWS)
            cur.executemany(_INSERT_PAPERS, papers)
            cur.executemany(_INSERT_QUESTIONS, questions)
    return report
