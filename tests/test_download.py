import csv
import datetime as dt

from paper_finder import download as dl
from paper_finder.download import FetchResult, download, iter_candidates, mirror_url

_TINY_SCOPE = {
    "subjects": {"9702": {"papers": [1], "variants": [1, 2]}},
    "years": [2024],
    "sessions": ["s"],
    "types": ["qp", "ms"],
}

_MULTI_SUBJECT_SCOPE = {
    "subjects": {
        "9702": {"papers": [1], "variants": [1]},
        "9231": {"papers": [1, 4], "variants": [1]},
    },
    "years": [2024],
    "sessions": ["s"],
    "types": ["qp"],
}


def make_fetcher(mapping):
    """Fake fetcher: `mapping` is url-substring -> FetchResult; default is 404."""
    calls = []

    def fetch(url):
        calls.append(url)
        for key, result in mapping.items():
            if key in url:
                return result
        return FetchResult(404, b"")

    fetch.calls = calls
    return fetch


def _pdf(size=512):
    return b"%PDF-1.7\n" + b"x" * size


def test_mirror_url_is_flat():
    assert mirror_url("9702_s24_qp_12.pdf") == (
        "https://pastpapers.papacambridge.com/directories/CAIE/CAIE-pastpapers/upload/"
        "9702_s24_qp_12.pdf"
    )


def test_iter_candidates_order_and_filenames():
    names = [c.filename for c in iter_candidates(_TINY_SCOPE)]
    assert names == [
        "9702_s24_qp_11.pdf",
        "9702_s24_ms_11.pdf",
        "9702_s24_qp_12.pdf",
        "9702_s24_ms_12.pdf",
    ]


def test_iter_candidates_uses_each_subjects_own_papers_and_variants():
    cands = list(iter_candidates(_MULTI_SUBJECT_SCOPE))
    names = [c.filename for c in cands]
    # 9702 keeps paper 1 only; 9231 gets its own papers 1 and 4
    assert names == [
        "9702_s24_qp_11.pdf",
        "9231_s24_qp_11.pdf",
        "9231_s24_qp_41.pdf",
    ]
    assert {c.subject_code for c in cands} == {"9702", "9231"}


def _run(tmp_path, fetcher, **kw):
    kw.setdefault("delay", 0)
    return download(
        scope=_TINY_SCOPE,
        raw_dir=tmp_path / "raw",
        log_path=tmp_path / "log.csv",
        fetcher=fetcher,
        **kw,
    )


def test_skips_existing_file(tmp_path):
    raw = tmp_path / "raw"
    raw.mkdir()
    (raw / "9702_s24_qp_11.pdf").write_bytes(b"already here")
    fetcher = make_fetcher({"qp_11": FetchResult(200, _pdf())})

    report = _run(tmp_path, fetcher)

    assert "9702_s24_qp_11.pdf" in report.skipped_existing
    assert all("qp_11" not in url for url in fetcher.calls)
    assert (raw / "9702_s24_qp_11.pdf").read_bytes() == b"already here"


def test_404_and_500_are_not_found_no_abort(tmp_path):
    fetcher = make_fetcher({"qp_11": FetchResult(404, b""), "qp_12": FetchResult(500, b"oops")})
    report = _run(tmp_path, fetcher)
    assert len(report.not_found) == 4
    assert report.downloaded == []
    assert report.aborted == ""


def test_saves_valid_pdf_bytes(tmp_path):
    body = _pdf()
    report = _run(tmp_path, make_fetcher({".pdf": FetchResult(200, body)}))
    assert len(report.downloaded) == 4
    assert (tmp_path / "raw" / "9702_s24_qp_11.pdf").read_bytes() == body


def test_rejects_non_pdf_body_and_aborts(tmp_path):
    fetcher = make_fetcher({".pdf": FetchResult(200, b"<!DOCTYPE html>")})
    report = _run(tmp_path, fetcher, max_consecutive_failures=3)
    assert report.aborted
    assert len(report.failed) == 3
    assert not (tmp_path / "raw" / "9702_s24_qp_11.pdf").exists()


def test_limit_stops_early(tmp_path):
    fetcher = make_fetcher({".pdf": FetchResult(200, _pdf())})
    report = _run(tmp_path, fetcher, limit=2)
    assert len(report.downloaded) == 2
    assert len(fetcher.calls) == 2


def test_aborts_on_repeated_network_errors(tmp_path):
    fetcher = make_fetcher({".pdf": FetchResult(0, b"", error="conn reset")})
    report = _run(tmp_path, fetcher, max_consecutive_failures=3)
    assert report.aborted
    assert len(fetcher.calls) == 3


def test_aborts_immediately_on_403(tmp_path):
    fetcher = make_fetcher({".pdf": FetchResult(403, b"")})
    report = _run(tmp_path, fetcher)
    assert report.aborted
    assert len(fetcher.calls) == 1


def test_dry_run_writes_nothing(tmp_path):
    report = download(
        scope=_TINY_SCOPE,
        raw_dir=tmp_path / "raw",
        log_path=tmp_path / "log.csv",
        fetcher=make_fetcher({".pdf": FetchResult(200, _pdf())}),
        dry_run=True,
        delay=0,
    )
    assert len(report.would_fetch) == 4
    assert not (tmp_path / "raw").exists()
    assert not (tmp_path / "log.csv").exists()


def test_csv_log_written(tmp_path):
    fetcher = make_fetcher({"qp_11": FetchResult(200, _pdf()), "ms_11": FetchResult(200, _pdf())})
    _run(tmp_path, fetcher)

    rows = list(csv.DictReader((tmp_path / "log.csv").read_text(encoding="utf-8").splitlines()))
    assert len(rows) == 4  # one per candidate
    outcomes = {r["filename"]: r["outcome"] for r in rows}
    assert outcomes["9702_s24_qp_11.pdf"] == "downloaded"
    assert outcomes["9702_s24_qp_12.pdf"] == "not_found"
    assert dt.datetime.fromisoformat(rows[0]["timestamp"]).tzinfo is not None


def test_csv_log_appends_across_runs(tmp_path):
    fetcher = make_fetcher({})
    _run(tmp_path, fetcher)
    _run(tmp_path, fetcher)
    lines = (tmp_path / "log.csv").read_text(encoding="utf-8").strip().splitlines()
    assert lines[0].startswith("timestamp")  # header written once
    assert len(lines) == 1 + 8  # header + 4 + 4


class _FakeResponse:
    def __init__(self, url, status=200, body=b"%PDF-1.7\n"):
        self._url = url
        self.status = status
        self._body = body

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False

    def geturl(self):
        return self._url

    def read(self):
        return self._body


def test_urllib_fetcher_maps_homepage_redirect_to_not_found(monkeypatch):
    # PapaCambridge answers a missing paper with a 302 to its homepage; urllib
    # follows it, so the final URL no longer ends in .pdf.
    monkeypatch.setattr(
        dl.urllib.request,
        "urlopen",
        lambda req, timeout=None: _FakeResponse("https://papacambridge.com/", body=b"<html>"),
    )
    result = dl._urllib_fetcher("https://example.test/9702_m26_qp_11.pdf")
    assert result.status == 404
    assert result.body == b""


def test_urllib_fetcher_returns_pdf_when_not_redirected(monkeypatch):
    monkeypatch.setattr(
        dl.urllib.request,
        "urlopen",
        lambda req, timeout=None: _FakeResponse("https://example.test/9702_s26_qp_21.pdf"),
    )
    result = dl._urllib_fetcher("https://example.test/9702_s26_qp_21.pdf")
    assert result.status == 200
    assert result.body.startswith(b"%PDF")


def test_sleeps_between_requests_not_before_first(tmp_path, monkeypatch):
    sleeps = []
    monkeypatch.setattr(dl.time, "sleep", lambda s: sleeps.append(s))
    download(
        scope=_TINY_SCOPE,
        raw_dir=tmp_path / "raw",
        log_path=tmp_path / "log.csv",
        fetcher=make_fetcher({}),
        delay=1.5,
    )
    assert sleeps == [1.5, 1.5, 1.5]  # 4 candidates -> 3 gaps
