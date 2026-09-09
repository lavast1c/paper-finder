"""SQLite database: connection helper and schema.

The full schema (papers, questions, answers, questions_fts) is created up front so
later stages don't need migrations. Stage 1 only populates ``papers``.
"""

from __future__ import annotations

import sqlite3
from pathlib import Path

from paper_finder import config
from paper_finder.topics import TOPICS

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
    has_figure      INTEGER NOT NULL DEFAULT 0,   -- question refers to a diagram/graph/table
    crop_rects      TEXT,                         -- JSON [[page,x0,y0,x1,y1], ...] page regions
    crop_count      INTEGER NOT NULL DEFAULT 0,   -- len(crop_rects); 0 = no crop image
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
    content_rowid='id',
    tokenize='porter unicode61'
);

-- Syllabus taxonomy. Rows are seeded from paper_finder.topics on init_db();
-- that module is the source of truth for names, this table exists for the join.
CREATE TABLE IF NOT EXISTS topics (
    code   TEXT PRIMARY KEY,       -- 's01'..'s11'
    number INTEGER NOT NULL,       -- syllabus section number, display order
    name   TEXT NOT NULL
);

-- Multi-label: a question may carry several topics. Rebuilt from
-- labels/question_topics.tsv by `paper-finder topics`, because `segment`
-- DELETEs and re-INSERTs every question (reassigning questions.id) and the
-- cascade below then empties this table -- `topics` is the repair for that.
-- Never write to this table from segment.py.
CREATE TABLE IF NOT EXISTS question_topics (
    question_id INTEGER NOT NULL REFERENCES questions(id) ON DELETE CASCADE,
    topic_code  TEXT    NOT NULL REFERENCES topics(code),
    PRIMARY KEY (question_id, topic_code)
);

CREATE INDEX IF NOT EXISTS question_topics_code_idx ON question_topics (topic_code);
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
        # The taxonomy is a code constant, not user data -- keep the FK target
        # for question_topics populated so a bare init-db can load labels.
        conn.executemany(
            "INSERT INTO topics (code, number, name) VALUES (?, ?, ?) "
            "ON CONFLICT(code) DO UPDATE SET number = excluded.number, name = excluded.name",
            [(t.code, t.number, t.name) for t in TOPICS],
        )
