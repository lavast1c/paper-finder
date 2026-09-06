import pymupdf

from paper_finder import db as db_mod
from paper_finder.extract import extract_all, extract_paper
from paper_finder.ingest import ingest

_PARAGRAPH = (
    "A ball is thrown vertically upwards and returns to its starting point. "
    "Air resistance is negligible throughout the motion of the ball. "
    "Which statement about the velocity and acceleration of the ball is correct?"
)


def _make_pdf(path, body=_PARAGRAPH):
    doc = pymupdf.open()
    page = doc.new_page()
    page.insert_text((72, 72), body)
    doc.save(path)
    doc.close()


def test_extract_paper_reads_lines_and_flags_text_layer(tmp_path):
    pdf = tmp_path / "9702_s26_qp_11.pdf"
    _make_pdf(pdf)

    result = extract_paper(pdf)

    assert result.page_count == 1
    assert result.has_text_layer is True
    joined = " ".join(line.text for page in result.pages for line in page.lines)
    assert "ball is thrown vertically upwards" in joined
    # bounding boxes are populated
    first = result.pages[0].lines[0]
    assert first.x0 >= 0 and first.y1 > first.y0


def test_extract_paper_flags_missing_text_layer(tmp_path):
    pdf = tmp_path / "9702_s26_qp_12.pdf"
    _make_pdf(pdf, body="1")  # almost no text -> looks scanned

    result = extract_paper(pdf)

    assert result.has_text_layer is False


def test_extract_all_writes_files_and_updates_db(tmp_path):
    raw = tmp_path / "raw"
    raw.mkdir()
    processed = tmp_path / "processed"
    db_path = tmp_path / "papers.db"

    _make_pdf(raw / "9702_s26_qp_11.pdf")
    ingest(raw_dir=raw, db_path=db_path)

    report = extract_all(raw_dir=raw, processed_dir=processed, db_path=db_path)

    assert report.extracted == ["9702_s26_qp_11.pdf"]
    assert (processed / "9702_s26_qp_11.txt").exists()
    assert (processed / "9702_s26_qp_11.json").exists()

    with db_mod.connect(db_path) as conn:
        row = conn.execute(
            "SELECT has_text_layer FROM papers WHERE filename = '9702_s26_qp_11.pdf'"
        ).fetchone()
    assert row["has_text_layer"] == 1
