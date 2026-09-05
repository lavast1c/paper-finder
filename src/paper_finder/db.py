"""SQLite database: connection helper and schema.

The full schema (papers, questions, answers, questions_fts) is created up front so
later stages don't need migrations. Stage 1 only populates ``papers``.
"""

from __future__ import annotations

import sqlite3
from pathlib import Path

from paper_finder import config

SCHEMA = """
CREATE TABLE IF NOT EXISTS papers (
    id             INTEGER PRIMARY KEY,
    subject_code   TEXT NOT NULL,
    subject_name   TEXT,
    year           INTEGER NOT NULL,
    session        TEXT NOT NULL,          -- 's' | 'w' | 'm'
    paper          INTEGER,
    variant        INTEGER,
    paper_type     TEXT NOT NULL,          -- 'qp' | 'ms' | ...
    filename       TEXT NOT NULL UNIQUE,
    source_url     TEXT,
    downloaded_at  TEXT,
    has_text_layer INTEGER                 -- set during extraction (Stage 2)
);

CREATE TABLE IF NOT EXISTS questions (
    id              INTEGER PRIMARY KEY,
    paper_id        INTEGER NOT NULL REFERENCES papers(id) ON DELETE CASCADE,
    question_number INTEGER NOT NULL,
    question_text   TEXT NOT NULL,
    marks           INTEGER,
    is_mcq          INTEGER,
    page_start      INTEGER,
    UNIQUE (paper_id, question_number)
);

CREATE TABLE IF NOT EXISTS answers (
    id          INTEGER PRIMARY KEY,
    question_id INTEGER NOT NULL REFERENCES questions(id) ON DELETE CASCADE,
    answer_text TEXT NOT NULL,
    source      TEXT
);

CREATE VIRTUAL TABLE IF NOT EXISTS questions_fts USING fts5 (
    question_text,
    content='questions',
    content_rowid='id'
);
"""


def connect(db_path: Path | str | None = None) -> sqlite3.Connection:
    """Open a connection with row access by name and foreign keys enabled.

    ``db_path`` defaults to ``config.DB_PATH``, read at call time so tests can
    point it at a temporary file.
    """
    conn = sqlite3.connect(db_path if db_path is not None else config.DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def init_db(db_path: Path | str | None = None) -> None:
    """Create the schema if it does not already exist. Safe to run repeatedly."""
    with connect(db_path) as conn:
        conn.executescript(SCHEMA)
