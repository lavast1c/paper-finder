import pytest

from paper_finder.db import connect, init_db
from paper_finder.search import (
    browse_by_topic,
    build_fts_query,
    search,
    topic_counts,
)


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
    assert hits[0].has_figure is False
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


# --------------------------------------------------------------- browse by topic


@pytest.fixture
def topic_db(tmp_path):
    """Two papers (s26 newer, w25 older), five questions, some multi-labelled."""
    db_path = tmp_path / "papers.db"
    init_db(db_path)
    with connect(db_path) as conn:
        conn.executemany(
            """INSERT INTO papers (id, subject_code, subject_name, year, session,
                   paper, variant, paper_type, filename)
               VALUES (?, '9702', 'Physics', ?, ?, ?, ?, 'qp', ?)""",
            [
                (1, 2026, "s", 1, 1, "9702_s26_qp_11.pdf"),
                (2, 2025, "w", 2, 1, "9702_w25_qp_21.pdf"),
            ],
        )
        conn.executemany(
            """INSERT INTO questions
               (id, paper_id, question_number, question_text, marks, is_mcq)
               VALUES (?, ?, ?, ?, ?, ?)""",
            [
                (1, 1, 1, "A transverse wave travels along a string.", 1, 1),
                (2, 1, 2, "Two coherent sources produce an interference pattern.", 1, 1),
                (3, 1, 3, "Define the wavelength of a progressive wave.", 2, 0),
                (4, 2, 1, "A stationary wave forms on a stretched wire.", 3, 0),
                (5, 2, 2, "State Ohm's law for a metallic conductor.", 2, 0),
            ],
        )
        conn.executemany(
            "INSERT INTO question_topics (question_id, topic_code) VALUES (?, ?)",
            [
                (1, "s07"),
                (2, "s08"),
                (3, "s07"),
                (4, "s07"),
                (4, "s08"),  # multi-label
                (5, "s09"),
            ],
        )
        conn.commit()
    return db_path


def test_browse_union_across_codes(topic_db):
    page, total = browse_by_topic(["s07", "s08"], db_path=topic_db)
    assert total == 4
    assert {h.question_number for h in page} == {1, 2, 3}  # q-numbers, two papers
    assert {(h.filename, h.question_number) for h in page} == {
        ("9702_s26_qp_11.pdf", 1),
        ("9702_s26_qp_11.pdf", 2),
        ("9702_s26_qp_11.pdf", 3),
        ("9702_w25_qp_21.pdf", 1),
    }


def test_browse_multi_label_question_returned_once(topic_db):
    page, total = browse_by_topic(["s07", "s08"], db_path=topic_db)
    q4 = [h for h in page if h.filename == "9702_w25_qp_21.pdf"]
    assert len(q4) == 1
    assert set(q4[0].topic_codes) == {"s07", "s08"}


def test_browse_newest_paper_first(topic_db):
    page, _ = browse_by_topic(["s07", "s08"], db_path=topic_db)
    assert [h.filename for h in page] == [
        "9702_s26_qp_11.pdf",
        "9702_s26_qp_11.pdf",
        "9702_s26_qp_11.pdf",
        "9702_w25_qp_21.pdf",
    ]


def test_browse_kind_filter(topic_db):
    page, total = browse_by_topic(["s07", "s08"], kind="theory", db_path=topic_db)
    assert total == 2
    assert {(h.filename, h.question_number) for h in page} == {
        ("9702_s26_qp_11.pdf", 3),
        ("9702_w25_qp_21.pdf", 1),
    }


def test_browse_session_and_year_filter(topic_db):
    _, total = browse_by_topic(["s07", "s08"], sessions=["w"], db_path=topic_db)
    assert total == 1
    _, total = browse_by_topic(["s07"], years=[2026], db_path=topic_db)
    assert total == 2


def test_browse_paging_disjoint_rows_stable_total(topic_db):
    p1, t1 = browse_by_topic(["s07", "s08"], limit=2, offset=0, db_path=topic_db)
    p2, t2 = browse_by_topic(["s07", "s08"], limit=2, offset=2, db_path=topic_db)
    assert t1 == t2 == 4
    keys1 = {(h.filename, h.question_number) for h in p1}
    keys2 = {(h.filename, h.question_number) for h in p2}
    assert keys1.isdisjoint(keys2)
    assert len(keys1 | keys2) == 4


def test_browse_empty_or_unknown_codes(topic_db):
    assert browse_by_topic([], db_path=topic_db) == ([], 0)
    assert browse_by_topic(["s99", "nope"], db_path=topic_db) == ([], 0)


def test_search_populates_topic_codes(topic_db):
    with connect(topic_db) as conn:
        conn.execute("INSERT INTO questions_fts(questions_fts) VALUES ('rebuild')")
        conn.commit()
    hits = search("stationary wave stretched wire", db_path=topic_db)
    assert hits[0].question_number == 1
    assert set(hits[0].topic_codes) == {"s07", "s08"}


def test_topic_counts_includes_zero_topics(topic_db):
    result = topic_counts(db_path=topic_db)
    by_code = {t["code"]: t for t in result["topics"]}
    assert len(result["topics"]) == 11
    assert by_code["s07"]["count"] == 3
    assert by_code["s08"]["count"] == 2
    assert by_code["s09"]["count"] == 1
    assert by_code["s01"]["count"] == 0
    assert by_code["s07"]["subsections"]
    assert result["total"] == 5
    assert result["unlabelled"] == 0


def test_topic_counts_respects_kind_filter(topic_db):
    result = topic_counts(kind="theory", db_path=topic_db)
    by_code = {t["code"]: t for t in result["topics"]}
    assert by_code["s07"]["count"] == 2  # q3, q4
    assert by_code["s08"]["count"] == 1  # q4
    assert result["total"] == 3
