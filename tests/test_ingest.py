from paper_finder import config
from paper_finder import db as db_mod
from paper_finder.ingest import ingest


def _touch(path):
    path.write_bytes(b"%PDF-1.4\n")  # ingest never opens the file in Stage 1


def test_ingest_records_prunes_and_skips(tmp_path):
    raw = tmp_path / "raw"
    raw.mkdir()
    db_path = tmp_path / "papers.db"

    _touch(raw / "9702_s23_qp_12.pdf")
    _touch(raw / "9702_s23_ms_12.pdf")
    _touch(raw / "notes.pdf")  # unrecognised -> skipped

    report = ingest(raw_dir=raw, db_path=db_path)
    assert report.found == 3
    assert report.ingested == 2
    assert report.skipped == ["notes.pdf"]

    with db_mod.connect(db_path) as conn:
        assert conn.execute("SELECT COUNT(*) FROM papers").fetchone()[0] == 2

    # Re-run with one file removed: it should be pruned, nothing duplicated.
    (raw / "9702_s23_ms_12.pdf").unlink()
    report = ingest(raw_dir=raw, db_path=db_path)
    assert report.ingested == 1
    assert report.pruned == ["9702_s23_ms_12.pdf"]

    with db_mod.connect(db_path) as conn:
        rows = conn.execute("SELECT filename FROM papers").fetchall()
    assert [r["filename"] for r in rows] == ["9702_s23_qp_12.pdf"]


def test_ingest_excludes_and_prunes_config_exclude_filenames(tmp_path, monkeypatch):
    raw = tmp_path / "raw"
    raw.mkdir()
    db_path = tmp_path / "papers.db"
    monkeypatch.setattr(config, "EXCLUDE_FILENAMES", frozenset({"9702_s23_qp_13.pdf"}))

    _touch(raw / "9702_s23_qp_12.pdf")
    _touch(raw / "9702_s23_qp_13.pdf")  # excluded -> never recorded

    report = ingest(raw_dir=raw, db_path=db_path)
    assert report.ingested == 1
    assert "9702_s23_qp_13.pdf" in report.skipped
    with db_mod.connect(db_path) as conn:
        names = [r["filename"] for r in conn.execute("SELECT filename FROM papers")]
    assert names == ["9702_s23_qp_12.pdf"]

    # A row already present for a now-excluded file is pruned on the next run.
    monkeypatch.setattr(config, "EXCLUDE_FILENAMES", frozenset())
    ingest(raw_dir=raw, db_path=db_path)
    monkeypatch.setattr(config, "EXCLUDE_FILENAMES", frozenset({"9702_s23_qp_13.pdf"}))
    report = ingest(raw_dir=raw, db_path=db_path)
    assert report.pruned == ["9702_s23_qp_13.pdf"]
