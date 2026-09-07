import pytest

from paper_finder.db import connect, init_db
from paper_finder.search import build_fts_query, search


def test_build_fts_query_quotes_tokens_and_drops_punctuation():
    assert build_fts_query("What is θ? (angle)") == '"what" OR "is" OR "angle"'
    assert build_fts_query("!!!") == ""


@pytest.fixture
def populated_db(tmp_path):
    db_path = tmp_path / "papers.db"
    init_db(db_path)
    with connect(db_path) as conn:
        conn.execute(
            """INSERT INTO papers (id, subject_code, subject_name, year, session,
                   paper, variant, paper_type, filename)
               VALUES (1, '9702', 'Physics', 2026, 's', 1, 1, 'qp', '9702_s26_qp_11.pdf')"""
        )
        rows = [
            (1, 1, 1, "A ball is thrown horizontally with a speed of 10 m/s.", 1, 1, 4),
            (2, 1, 2, "What is an SI base quantity?", 1, 1, 3),
            (3, 1, 3, "A book rests on a table with weight W.", 1, 0, 5),
        ]
        conn.executemany(
            """INSERT INTO questions
               (id, paper_id, question_number, question_text, marks, is_mcq, page_start)
               VALUES (?, ?, ?, ?, ?, ?, ?)""",
            rows,
        )
        conn.execute(
            "INSERT INTO answers (question_id, answer_text, source) VALUES (1, 'C', 'mark_scheme')"
        )
        conn.execute("INSERT INTO questions_fts(questions_fts) VALUES ('rebuild')")
        conn.commit()
    return db_path


def test_search_finds_expected_question_first(populated_db):
    hits = search("ball thrown horizontally speed", db_path=populated_db)
    assert hits
    assert hits[0].question_number == 1
    assert hits[0].answer == "C"
    assert hits[0].page_start == 4
    assert hits[0].label == "Physics 2026 s paper 11 Q1"


def test_search_stemming_matches_word_variants(populated_db):
    # 'resting' should still match 'rests' thanks to the porter tokenizer
    hits = search("book resting on table", db_path=populated_db)
    assert hits[0].question_number == 3


def test_search_empty_query_returns_nothing(populated_db):
    assert search("???", db_path=populated_db) == []


def test_search_kind_filter(populated_db):
    q = "ball thrown quantity book table weight"  # matches all three questions
    assert {h.question_number for h in search(q, db_path=populated_db)} == {1, 2, 3}
    # q1/q2 are is_mcq=1, q3 is is_mcq=0
    assert {h.question_number for h in search(q, db_path=populated_db, kind="mcq")} == {1, 2}
    assert {h.question_number for h in search(q, db_path=populated_db, kind="theory")} == {3}
    # an unknown kind falls back to 'all'
    assert {h.question_number for h in search(q, db_path=populated_db, kind="bogus")} == {1, 2, 3}
