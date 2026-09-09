import json

import pytest

from paper_finder.publish_figures import resolve_service_key, upload_all

_PNG = b"\x89PNG\r\n\x1a\n" + b"body"


@pytest.fixture
def crops(tmp_path):
    crop_dir = tmp_path / "crops"
    for stem, names in {
        "9702_s26_qp_11": ["q01_p1.png", "q02_p1.png"],
        "9702_s26_qp_21": ["q01_p1.png", "q01_p2.png"],
    }.items():
        d = crop_dir / stem
        d.mkdir(parents=True)
        for n in names:
            (d / n).write_bytes(_PNG)
    return crop_dir


class FakeHttp:
    """Records every request; serves `list` from an in-memory bucket, accepts uploads."""

    def __init__(self, existing=None):
        self.bucket = set(existing or [])  # "stem/qNN_pK.png"
        self.calls = []

    def __call__(self, method, url, headers, body):
        self.calls.append((method, url))
        if "/object/list/" in url:
            prefix = json.loads(body)["prefix"]
            names = [k[len(prefix) :] for k in sorted(self.bucket) if k.startswith(prefix)]
            return 200, json.dumps([{"name": n} for n in names]).encode()
        # upload: .../object/question-crops/<stem>/<file>
        key = url.split("/object/question-crops/", 1)[1]
        assert headers["x-upsert"] == "true"
        assert headers["Content-Type"] == "image/png"
        self.bucket.add(key)
        return 200, b"{}"


def _kw(crop_dir, http):
    return dict(crop_dir=crop_dir, url="https://x.supabase.co", service_key="svc", http=http)


def test_uploads_every_crop(crops):
    http = FakeHttp()
    report = upload_all(**_kw(crops, http))
    assert report.papers == 2
    assert report.uploaded == 4
    assert report.skipped_existing == 0
    assert http.bucket == {
        "9702_s26_qp_11/q01_p1.png",
        "9702_s26_qp_11/q02_p1.png",
        "9702_s26_qp_21/q01_p1.png",
        "9702_s26_qp_21/q01_p2.png",
    }


def test_second_run_skips_existing(crops):
    http = FakeHttp()
    upload_all(**_kw(crops, http))
    report = upload_all(**_kw(crops, http))
    assert report.uploaded == 0
    assert report.skipped_existing == 4


def test_force_reuploads_without_listing(crops):
    http = FakeHttp(existing=["9702_s26_qp_11/q01_p1.png"])
    report = upload_all(**_kw(crops, http), force=True)
    assert report.uploaded == 4
    assert report.skipped_existing == 0
    assert not any("/object/list/" in url for _, url in http.calls)


def test_dry_run_sends_nothing(crops):
    http = FakeHttp()
    report = upload_all(crop_dir=crops, http=http, dry_run=True)
    assert report.uploaded == 4
    assert http.calls == []


def test_only_filters_by_filename(crops):
    http = FakeHttp()
    report = upload_all(**_kw(crops, http), only="qp_21")
    assert report.papers == 1
    assert report.uploaded == 2
    assert all("qp_21" in k for k in http.bucket)


def test_limit_caps_uploads(crops):
    http = FakeHttp()
    report = upload_all(**_kw(crops, http), limit=1)
    assert report.uploaded == 1


def test_failed_upload_is_reported_not_fatal(crops):
    class Flaky(FakeHttp):
        def __call__(self, method, url, headers, body):
            if url.endswith("q02_p1.png"):
                return 500, b"server error"
            return super().__call__(method, url, headers, body)

    http = Flaky()
    report = upload_all(**_kw(crops, http))
    assert report.uploaded == 3
    assert len(report.failures) == 1
    assert "q02_p1.png" in report.failures[0]


def test_missing_service_key_raises():
    # conftest._no_supabase_env clears the env var and points PROJECT_ROOT at an
    # empty dir, so this exercises the "nothing configured" path.
    with pytest.raises(RuntimeError, match="SUPABASE_SERVICE_ROLE_KEY"):
        resolve_service_key()


def test_no_crop_dir_is_a_clean_noop(tmp_path):
    http = FakeHttp()
    report = upload_all(crop_dir=tmp_path / "nope", http=http, dry_run=True)
    assert (report.papers, report.uploaded) == (0, 0)
