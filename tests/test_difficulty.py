import pytest
from test_topics import segmented_db  # noqa: F401  (pytest fixture)

from paper_finder.db import connect
from paper_finder.difficulty import load_difficulty_labels, parse_difficulty
from paper_finder.segment import segment_all


def _write(tmp_path, body):
    path = tmp_path / "question_difficulty.tsv"
    path.write_text(body, encoding="utf-8")
    return path


def test_parse_difficulty_reads_good_rows_and_skips_comments(tmp_path):
    path = _write(
        tmp_path,
        "# header\n\n9709_s20_qp_11.pdf\t1\t2\thand\n9709_s20_qp_11.pdf\t11\t5\thand\n",
    )
    rows = parse_difficulty(path)
    assert [(r.filename, r.question_number, r.difficulty, r.source) for r in rows] == [
        ("9709_s20_qp_11.pdf", 1, 2, "hand"),
        ("9709_s20_qp_11.pdf", 11, 5, "hand"),
    ]


@pytest.mark.parametrize("value", ["0", "6", "x", "2.5"])
def test_parse_difficulty_rejects_out_of_range_or_non_integer(tmp_path, value):
    path = _write(tmp_path, f"9709_s20_qp_11.pdf\t1\t{value}\thand\n")
    with pytest.raises(ValueError, match=":1:"):
        parse_difficulty(path)


def test_parse_difficulty_rejects_unknown_source(tmp_path):
    path = _write(tmp_path, "9709_s20_qp_11.pdf\t1\t3\tguess\n")
    with pytest.raises(ValueError, match="source"):
        parse_difficulty(path)


def test_parse_difficulty_rejects_duplicate_question(tmp_path):
    path = _write(tmp_path, "9709_s20_qp_11.pdf\t1\t3\thand\n9709_s20_qp_11.pdf\t1\t4\thand\n")
    with pytest.raises(ValueError, match="duplicate"):
        parse_difficulty(path)


def test_load_difficulty_labels_populates_and_counts(segmented_db):  # noqa: F811
    db_path, _ = segmented_db
    path = _write(
        db_path.parent,
        "9702_s26_qp_11.pdf\t1\t2\thand\n9702_s26_qp_11.pdf\t2\t5\thand\n"
        "9702_w99_qp_11.pdf\t3\t1\thand\n",
    )
    report = load_difficulty_labels(path=path, db_path=db_path)
    assert report.rows == 3
    assert report.rated == 2
    assert report.unrated == 1
    assert report.counts == {2: 1, 5: 1}
    assert report.orphans == ["9702_w99_qp_11.pdf Q3"]
    assert report.by_subject == {"Physics": (2, 1)}


def test_load_difficulty_labels_is_idempotent_and_survives_resegment(segmented_db):  # noqa: F811
    db_path, processed = segmented_db
    path = _write(db_path.parent, "9702_s26_qp_11.pdf\t3\t4\thand\n")
    load_difficulty_labels(path=path, db_path=db_path)
    load_difficulty_labels(path=path, db_path=db_path)

    def rows():
        with connect(db_path) as conn:
            return [
                tuple(r)
                for r in conn.execute(
                    """SELECT p.filename, q.question_number, d.difficulty
                       FROM question_difficulty d
                       JOIN questions q ON q.id = d.question_id
                       JOIN papers p ON p.id = q.paper_id"""
                )
            ]

    assert rows() == [("9702_s26_qp_11.pdf", 3, 4)]
    segment_all(processed_dir=processed, db_path=db_path)
    assert rows() == []  # re-segmenting cascades the table away...
    load_difficulty_labels(path=path, db_path=db_path)
    assert rows() == [("9702_s26_qp_11.pdf", 3, 4)]  # ...and reloading repairs it


def test_load_difficulty_labels_without_a_file_is_a_no_op(segmented_db):  # noqa: F811
    db_path, _ = segmented_db
    report = load_difficulty_labels(path=db_path.parent / "missing.tsv", db_path=db_path)
    assert report.rows == 0 and report.rated == 0
