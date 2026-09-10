import json

import pytest

from paper_finder.db import connect, init_db
from paper_finder.labels import load_topic_labels, parse_labels
from paper_finder.segment import segment_all
from paper_finder.topics import (
    ALL_TOPICS,
    BY_CODE,
    CODES,
    TAXONOMIES,
    TOPICS,
    taxonomy_by_name,
    taxonomy_for,
)


def _write_labels(tmp_path, body):
    path = tmp_path / "question_topics.tsv"
    path.write_text(body, encoding="utf-8")
    return path


def _mcq_json(stem, n_questions):
    """Minimal processed-JSON for an MCQ paper load_lines() can read."""
    pages = [
        {
            "page": 1,
            "width": 595.0,
            "height": 842.0,
            "lines": [
                {"x0": 100.0, "y0": 120.0, "x1": 300.0, "y1": 132.0, "text": "Multiple Choice"}
            ],
        }
    ]
    lines = []
    y = 120.0
    for q in range(1, n_questions + 1):
        lines.append({"x0": 49.6, "y0": y, "x1": 56.0, "y1": y + 10, "text": str(q)})
        lines.append(
            {"x0": 72.0, "y0": y, "x1": 400.0, "y1": y + 10, "text": f"{stem} question {q}?"}
        )
        for opt in ("A", "B", "C", "D"):
            y += 18
            lines.append({"x0": 72.0, "y0": y, "x1": 90.0, "y1": y + 10, "text": opt})
            lines.append(
                {"x0": 90.0, "y0": y, "x1": 200.0, "y1": y + 10, "text": f"option {opt.lower()}"}
            )
        y += 26
    pages.append({"page": 2, "width": 595.0, "height": 842.0, "lines": lines})
    return {
        "filename": "x.pdf",
        "page_count": 2,
        "char_count": 999,
        "has_text_layer": True,
        "pages": pages,
    }


@pytest.fixture
def segmented_db(tmp_path):
    """A DB with one segmented MCQ paper (3 questions) and its processed JSON dir."""
    processed = tmp_path / "processed"
    processed.mkdir()
    (processed / "9702_s26_qp_11.json").write_text(
        json.dumps(_mcq_json("Physics", 3)), encoding="utf-8"
    )
    db_path = tmp_path / "papers.db"
    init_db(db_path)
    with connect(db_path) as conn:
        conn.execute(
            """INSERT INTO papers (id, subject_code, subject_name, year, session, paper,
                   variant, paper_type, filename, has_text_layer)
               VALUES (1, '9702', 'Physics', 2026, 's', 1, 1, 'qp', '9702_s26_qp_11.pdf', 1)"""
        )
        conn.commit()
    segment_all(processed_dir=processed, db_path=db_path)
    return db_path, processed


def test_physics_taxonomy_is_the_eleven_syllabus_sections():
    assert len(TOPICS) == 11
    assert [t.code for t in TOPICS] == [f"s{n:02d}" for n in range(1, 12)]
    assert [t.number for t in TOPICS] == list(range(1, 12))


def test_each_taxonomy_numbers_its_topics_from_one():
    for tax in TAXONOMIES:
        assert [t.number for t in tax.topics] == list(range(1, len(tax.topics) + 1)), tax.key
    codes = {"9702": "s", "9231p1": "fp", "9231p4": "fs"}
    for tax in TAXONOMIES:
        assert all(t.code.startswith(codes[tax.key]) for t in tax.topics), tax.key


def test_every_topic_has_a_name_blurb_and_subsections():
    for t in ALL_TOPICS:
        assert t.name.strip()
        assert len(t.blurb) > 80, f"{t.code} blurb is too thin to classify against"
        assert t.subsections, t.code
        assert all(s.strip() for s in t.subsections)


def test_lookup_tables_are_the_union_of_every_taxonomy():
    assert set(CODES) == {t.code for t in ALL_TOPICS}
    assert len(ALL_TOPICS) == sum(len(tax.topics) for tax in TAXONOMIES)
    assert len({t.code for t in ALL_TOPICS}) == len(ALL_TOPICS), (
        "topic codes collide across taxonomies"
    )
    assert BY_CODE["s07"].name == "Waves"
    assert BY_CODE["fp4"].name == "Matrices"
    assert BY_CODE["fs3"].name == "Chi-squared tests"
    assert all(BY_CODE[t.code] is t for t in ALL_TOPICS)


def test_taxonomy_for_picks_by_subject_code_and_paper():
    assert taxonomy_for("9702", 1).subject_name == "Physics"
    assert taxonomy_for("9702", 2).subject_name == "Physics"
    assert taxonomy_for("9231", 1).subject_name == "Further Pure Mathematics"
    assert taxonomy_for("9231", 4).subject_name == "Further Probability & Statistics"
    assert taxonomy_for("9231", 2) is None
    assert taxonomy_for("0000", 1) is None
    # paper unknown -> first taxonomy for that subject code
    assert taxonomy_for("9231", None).subject_code == "9231"


def test_taxonomy_by_name_round_trips():
    for tax in TAXONOMIES:
        assert taxonomy_by_name(tax.subject_name) is tax
    assert taxonomy_by_name("Chemistry") is None


def test_topic_is_frozen():
    import dataclasses

    with pytest.raises(dataclasses.FrozenInstanceError):
        TOPICS[0].name = "changed"  # type: ignore[misc]


# --------------------------------------------------------------- schema seeding


def test_init_db_seeds_every_taxonomy_with_its_subject(tmp_path):
    db_path = tmp_path / "papers.db"
    init_db(db_path)
    with connect(db_path) as conn:
        rows = conn.execute("SELECT code, number, name, subject FROM topics").fetchall()
    assert {r["code"] for r in rows} == set(CODES)
    by_code = {r["code"]: r for r in rows}
    for tax in TAXONOMIES:
        for t in tax.topics:
            assert by_code[t.code]["subject"] == tax.subject_name
            assert by_code[t.code]["number"] == t.number
    # Physics still seeds all eleven, in order
    physics = sorted((r for r in rows if r["subject"] == "Physics"), key=lambda r: r["number"])
    assert [r["code"] for r in physics] == [t.code for t in TOPICS]


def test_init_db_reseeds_after_a_name_change(tmp_path):
    db_path = tmp_path / "papers.db"
    init_db(db_path)
    with connect(db_path) as conn:
        conn.execute("UPDATE topics SET name = 'stale' WHERE code = 's07'")
        conn.commit()
    init_db(db_path)
    with connect(db_path) as conn:
        assert conn.execute("SELECT name FROM topics WHERE code = 's07'").fetchone()[0] == "Waves"


# --------------------------------------------------------------- label parsing


def test_parse_labels_reads_good_rows(tmp_path):
    path = _write_labels(
        tmp_path,
        "# comment\n\n9702_s26_qp_11.pdf\t1\ts02\thand\n9702_s26_qp_11.pdf\t2\ts01,s03\tllm\n",
    )
    rows = parse_labels(path)
    assert [(r.question_number, r.topic_codes, r.source) for r in rows] == [
        (1, ("s02",), "hand"),
        (2, ("s01", "s03"), "llm"),
    ]


def test_parse_labels_rejects_unknown_code(tmp_path):
    path = _write_labels(tmp_path, "9702_s26_qp_11.pdf\t1\ts99\thand\n")
    with pytest.raises(ValueError, match="s99"):
        parse_labels(path)


def test_parse_labels_accepts_further_maths_codes_for_9231(tmp_path):
    path = _write_labels(
        tmp_path,
        "9231_s24_qp_11.pdf\t1\tfp4\thand\n9231_s24_qp_41.pdf\t2\tfs2,fs3\tllm\n",
    )
    rows = parse_labels(path)
    assert [(r.filename, r.topic_codes) for r in rows] == [
        ("9231_s24_qp_11.pdf", ("fp4",)),
        ("9231_s24_qp_41.pdf", ("fs2", "fs3")),
    ]


def test_parse_labels_rejects_code_from_the_wrong_taxonomy(tmp_path):
    # a real code, but Physics -- not valid on a 9231 Paper 4 row
    path = _write_labels(tmp_path, "9231_s24_qp_41.pdf\t1\ts02\thand\n")
    with pytest.raises(ValueError, match="Further Probability & Statistics"):
        parse_labels(path)
    # and the reverse: fp1 on a Physics row
    path = _write_labels(tmp_path, "9702_s26_qp_11.pdf\t1\tfp1\thand\n")
    with pytest.raises(ValueError, match="Physics"):
        parse_labels(path)
    # 9231 Paper 1 tagged with a Paper 4 (stats) code
    path = _write_labels(tmp_path, "9231_s24_qp_11.pdf\t1\tfs1\thand\n")
    with pytest.raises(ValueError, match="Further Pure Mathematics"):
        parse_labels(path)


def test_parse_labels_rejects_empty_code_list(tmp_path):
    path = _write_labels(tmp_path, "9702_s26_qp_11.pdf\t1\t\thand\n")
    with pytest.raises(ValueError, match="no topic codes"):
        parse_labels(path)


def test_parse_labels_rejects_duplicate_question(tmp_path):
    path = _write_labels(
        tmp_path, "9702_s26_qp_11.pdf\t1\ts02\thand\n9702_s26_qp_11.pdf\t1\ts03\tllm\n"
    )
    with pytest.raises(ValueError, match="duplicate"):
        parse_labels(path)


# --------------------------------------------------------------- label loading


def test_load_topic_labels_populates_and_counts(segmented_db):
    db_path, _ = segmented_db
    path = db_path.parent / "labels.tsv"
    path.write_text(
        "9702_s26_qp_11.pdf\t1\ts02\thand\n9702_s26_qp_11.pdf\t2\ts01,s03\tllm\n",
        encoding="utf-8",
    )
    report = load_topic_labels(path=path, db_path=db_path)
    assert report.rows == 2
    assert report.labelled == 2
    assert report.unlabelled == 1
    assert report.counts == {"s02": 1, "s01": 1, "s03": 1}
    assert report.orphans == []


def test_load_topic_labels_is_idempotent(segmented_db):
    db_path, _ = segmented_db
    path = db_path.parent / "labels.tsv"
    path.write_text("9702_s26_qp_11.pdf\t1\ts02,s03\thand\n", encoding="utf-8")
    load_topic_labels(path=path, db_path=db_path)
    load_topic_labels(path=path, db_path=db_path)
    with connect(db_path) as conn:
        assert conn.execute("SELECT COUNT(*) FROM question_topics").fetchone()[0] == 2


def test_load_reports_orphans_without_failing(segmented_db):
    db_path, _ = segmented_db
    path = db_path.parent / "labels.tsv"
    path.write_text(
        "9702_s26_qp_11.pdf\t1\ts02\thand\n9702_w99_qp_11.pdf\t3\ts07\tllm\n",
        encoding="utf-8",
    )
    report = load_topic_labels(path=path, db_path=db_path)
    assert report.orphans == ["9702_w99_qp_11.pdf Q3"]
    assert report.labelled == 1


def test_labels_survive_a_resegment(segmented_db):
    """The load-bearing regression test: labels are keyed on (filename, qnum), so
    they outlive segment.py reassigning questions.id and cascading the table."""
    db_path, processed = segmented_db
    path = db_path.parent / "labels.tsv"
    path.write_text(
        "9702_s26_qp_11.pdf\t1\ts02\thand\n9702_s26_qp_11.pdf\t3\ts03,s05\tllm\n",
        encoding="utf-8",
    )
    load_topic_labels(path=path, db_path=db_path)

    def triples():
        with connect(db_path) as conn:
            return sorted(
                tuple(r)
                for r in conn.execute(
                    """SELECT p.filename, q.question_number, qt.topic_code
                       FROM question_topics qt
                       JOIN questions q ON q.id = qt.question_id
                       JOIN papers p ON p.id = q.paper_id"""
                ).fetchall()
            )

    before = triples()
    with connect(db_path) as conn:
        ids_before = {r[0] for r in conn.execute("SELECT id FROM questions").fetchall()}
        # Force the rowid counter forward so the re-insert cannot reuse the same
        # ids, the way volume does in the real corpus.
        conn.execute(
            """INSERT INTO papers (id, subject_code, year, session, paper_type, filename,
                   has_text_layer)
               VALUES (99, '9702', 2000, 's', 'ms', 'sentinel.pdf', 1)"""
        )
        conn.execute(
            "INSERT INTO questions (id, paper_id, question_number, question_text) "
            "VALUES (9000, 99, 1, 'sentinel')"
        )
        conn.commit()

    segment_all(processed_dir=processed, db_path=db_path)  # ids churn, cascade fires

    with connect(db_path) as conn:
        assert conn.execute("SELECT COUNT(*) FROM question_topics").fetchone()[0] == 0
        ids_after = {
            r[0] for r in conn.execute("SELECT id FROM questions WHERE paper_id = 1").fetchall()
        }
    assert ids_before.isdisjoint(ids_after), "segment should have reassigned questions.id"

    load_topic_labels(path=path, db_path=db_path)
    assert triples() == before
