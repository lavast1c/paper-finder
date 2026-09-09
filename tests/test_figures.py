import json

import pymupdf
import pytest

from paper_finder.db import connect, init_db
from paper_finder.figures import crop_path, render_all

QP = "9702_s26_qp_11.pdf"


def _make_pdf(path, pages=2):
    doc = pymupdf.open()
    for i in range(pages):
        page = doc.new_page()  # A4 portrait, 595 x 842
        page.insert_text((60, 120), f"Question text on page {i + 1}.")
    doc.save(path)
    doc.close()


@pytest.fixture
def corpus(tmp_path):
    db_path = tmp_path / "papers.db"
    raw_dir = tmp_path / "raw"
    crop_dir = tmp_path / "crops"
    raw_dir.mkdir()
    _make_pdf(raw_dir / QP)

    init_db(db_path)
    with connect(db_path) as conn:
        conn.execute(
            """INSERT INTO papers (id, subject_code, subject_name, year, session,
                   paper, variant, paper_type, filename)
               VALUES (1, '9702', 'Physics', 2026, 's', 1, 1, 'qp', ?)""",
            (QP,),
        )
        conn.executemany(
            """INSERT INTO questions
                   (id, paper_id, question_number, question_text, marks, is_mcq,
                    page_start, has_figure, crop_rects, crop_count)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            [
                (1, 1, 1, "Q1", 1, 1, 1, 0, json.dumps([[1, 40.0, 90.0, 555.0, 300.0]]), 1),
                (2, 1, 2, "Q2", 1, 1, 1, 0, json.dumps([[1, 40.0, 300.0, 555.0, 783.0]]), 1),
                (
                    3,
                    1,
                    3,
                    "Q3",
                    5,
                    0,
                    2,
                    1,
                    json.dumps([[2, 40.0, 90.0, 555.0, 400.0], [2, 40.0, 400.0, 555.0, 783.0]]),
                    2,
                ),
            ],
        )
        conn.commit()
    return db_path, raw_dir, crop_dir


def test_renders_one_file_per_rect(corpus):
    db_path, raw_dir, crop_dir = corpus
    report = render_all(db_path=db_path, raw_dir=raw_dir, crop_dir=crop_dir)

    assert report.total_rendered == 4  # 1 + 1 + 2
    assert report.rendered == {QP: 4}
    stem = QP[:-4]
    for qnum, ordinal in [(1, 1), (2, 1), (3, 1), (3, 2)]:
        path = crop_path(stem, qnum, ordinal, crop_dir)
        assert path.is_file()
        assert path.read_bytes()[:8] == b"\x89PNG\r\n\x1a\n"


def test_second_run_skips_existing(corpus):
    db_path, raw_dir, crop_dir = corpus
    render_all(db_path=db_path, raw_dir=raw_dir, crop_dir=crop_dir)
    report = render_all(db_path=db_path, raw_dir=raw_dir, crop_dir=crop_dir)

    assert report.total_rendered == 0
    assert report.skipped_existing == 4


def test_force_rewrites(corpus):
    db_path, raw_dir, crop_dir = corpus
    render_all(db_path=db_path, raw_dir=raw_dir, crop_dir=crop_dir)
    report = render_all(db_path=db_path, raw_dir=raw_dir, crop_dir=crop_dir, force=True)

    assert report.total_rendered == 4
    assert report.skipped_existing == 0


def test_dry_run_writes_nothing(corpus):
    db_path, raw_dir, crop_dir = corpus
    report = render_all(db_path=db_path, raw_dir=raw_dir, crop_dir=crop_dir, dry_run=True)

    assert report.total_rendered == 4
    assert not crop_dir.exists()


def test_limit_caps_crop_files(corpus):
    db_path, raw_dir, crop_dir = corpus
    report = render_all(db_path=db_path, raw_dir=raw_dir, crop_dir=crop_dir, limit=2)

    assert report.total_rendered <= 2


def test_only_filters_by_filename(corpus):
    db_path, raw_dir, crop_dir = corpus
    report = render_all(db_path=db_path, raw_dir=raw_dir, crop_dir=crop_dir, only="qp_99")

    assert report.total_rendered == 0
    assert report.rendered == {}


def test_page_out_of_range_is_reported_not_fatal(corpus):
    db_path, raw_dir, crop_dir = corpus
    with connect(db_path) as conn:
        conn.execute(
            "UPDATE questions SET crop_rects = ? WHERE id = 1",
            (json.dumps([[9, 40.0, 90.0, 555.0, 300.0]]),),
        )
        conn.commit()

    report = render_all(db_path=db_path, raw_dir=raw_dir, crop_dir=crop_dir)

    assert any("page 9 out of range" in line for line in report.bad_rects)
    assert report.total_rendered == 3  # the other two questions still rendered


def test_rotated_page_is_skipped_with_a_warning(tmp_path):
    db_path = tmp_path / "papers.db"
    raw_dir = tmp_path / "raw"
    crop_dir = tmp_path / "crops"
    raw_dir.mkdir()

    doc = pymupdf.open()
    page = doc.new_page()
    page.insert_text((60, 120), "Rotated question.")
    page.set_rotation(90)
    doc.save(raw_dir / QP)
    doc.close()

    init_db(db_path)
    with connect(db_path) as conn:
        conn.execute(
            """INSERT INTO papers (id, subject_code, subject_name, year, session,
                   paper, variant, paper_type, filename)
               VALUES (1, '9702', 'Physics', 2026, 's', 1, 1, 'qp', ?)""",
            (QP,),
        )
        conn.execute(
            """INSERT INTO questions
                   (id, paper_id, question_number, question_text, marks, is_mcq,
                    page_start, has_figure, crop_rects, crop_count)
               VALUES (1, 1, 1, 'Q1', 1, 1, 1, 0, ?, 1)""",
            (json.dumps([[1, 40.0, 90.0, 555.0, 300.0]]),),
        )
        conn.commit()

    report = render_all(db_path=db_path, raw_dir=raw_dir, crop_dir=crop_dir)

    assert report.skipped_rotated == [f"{QP} p1"]
    assert report.total_rendered == 0


def test_missing_pdf_is_reported(tmp_path):
    db_path = tmp_path / "papers.db"
    raw_dir = tmp_path / "raw"
    crop_dir = tmp_path / "crops"
    raw_dir.mkdir()

    init_db(db_path)
    with connect(db_path) as conn:
        conn.execute(
            """INSERT INTO papers (id, subject_code, subject_name, year, session,
                   paper, variant, paper_type, filename)
               VALUES (1, '9702', 'Physics', 2026, 's', 1, 1, 'qp', ?)""",
            (QP,),
        )
        conn.execute(
            """INSERT INTO questions
                   (id, paper_id, question_number, question_text, marks, is_mcq,
                    page_start, has_figure, crop_rects, crop_count)
               VALUES (1, 1, 1, 'Q1', 1, 1, 1, 0, ?, 1)""",
            (json.dumps([[1, 40.0, 90.0, 555.0, 300.0]]),),
        )
        conn.commit()

    report = render_all(db_path=db_path, raw_dir=raw_dir, crop_dir=crop_dir)

    assert report.missing_pdf == [QP]
