"""Upload the rendered question crops to the private Supabase Storage bucket.

``paper-finder publish-figures`` walks ``data/crops/`` and PUTs every PNG to the
``question-crops`` bucket through the Storage REST API. Stdlib ``urllib`` only --
no ``supabase-py``, no ``httpx``, no new dependency -- matching ``download.py``'s
posture and ``web/app.py``'s ``/api/health`` call.

Separate from ``paper-finder publish``: that is a one-transaction replace-all of a
few thousand small rows and takes seconds; this is a long, resumable,
network-flaky ~35 MB binary upload with a completely different failure mode.

Needs ``SUPABASE_URL`` and ``SUPABASE_SERVICE_ROLE_KEY`` (a server-side key --
never in a browser payload) in the environment or a local ``.env``. Idempotent
and resumable: it lists what is already in the bucket per paper prefix and skips
those unless ``--force``.
"""

from __future__ import annotations

import json
import os
import urllib.error
import urllib.request
from collections.abc import Callable
from dataclasses import dataclass, field
from pathlib import Path

from paper_finder import config
from paper_finder.publish import _read_dotenv

BUCKET = "question-crops"
_CONTENT_TYPE = "image/png"
_LIST_PAGE = 100

# (method, url, headers, body) -> (status_code, response_body). The single seam
# tests inject over, so nothing here ever touches the network in a test.
HttpFn = Callable[[str, str, dict[str, str], bytes | None], tuple[int, bytes]]


@dataclass
class FigureUploadReport:
    papers: int = 0
    uploaded: int = 0
    skipped_existing: int = 0
    failures: list[str] = field(default_factory=list)
    dry_run: bool = False


def _urllib_http(
    method: str, url: str, headers: dict[str, str], body: bytes | None
) -> tuple[int, bytes]:
    request = urllib.request.Request(url, data=body, headers=headers, method=method)
    try:
        with urllib.request.urlopen(request, timeout=30) as resp:
            return resp.status, resp.read()
    except urllib.error.HTTPError as exc:
        return exc.code, exc.read()


def _resolve(name: str, explicit: str | None, hint: str) -> str:
    """``explicit`` > env > ``.env`` > a clear error naming where to find it."""
    if explicit:
        return explicit
    from_env = os.environ.get(name)
    if from_env:
        return from_env
    from_file = _read_dotenv(config.PROJECT_ROOT / ".env").get(name)
    if from_file:
        return from_file
    raise RuntimeError(f"No {name}. Put it in .env (gitignored) or export it.\n{hint}")


def resolve_url(explicit: str | None = None) -> str:
    return _resolve(
        "SUPABASE_URL",
        explicit,
        "Supabase dashboard -> Project Settings -> API -> Project URL.",
    ).rstrip("/")


def resolve_service_key(explicit: str | None = None) -> str:
    return _resolve(
        "SUPABASE_SERVICE_ROLE_KEY",
        explicit,
        "Supabase dashboard -> Project Settings -> API -> Project API keys -> "
        "service_role (secret). Server-side only -- never commit it, never put it "
        "in a browser payload.",
    )


def _list_prefix(http: HttpFn, base: str, key: str, prefix: str) -> set[str]:
    """Every object name directly under ``prefix`` already in the bucket."""
    names: set[str] = set()
    offset = 0
    while True:
        status, raw = http(
            "POST",
            f"{base}/storage/v1/object/list/{BUCKET}",
            {"Authorization": f"Bearer {key}", "Content-Type": "application/json"},
            json.dumps({"prefix": prefix, "limit": _LIST_PAGE, "offset": offset}).encode(),
        )
        if status != 200:
            raise RuntimeError(f"list {prefix!r} -> HTTP {status}: {raw[:200]!r}")
        batch = json.loads(raw or b"[]")
        names.update(item["name"] for item in batch)
        if len(batch) < _LIST_PAGE:
            return names
        offset += len(batch)


def _upload(http: HttpFn, base: str, key: str, object_path: str, data: bytes) -> None:
    status, raw = http(
        "POST",
        f"{base}/storage/v1/object/{BUCKET}/{object_path}",
        {
            "Authorization": f"Bearer {key}",
            "Content-Type": _CONTENT_TYPE,
            "x-upsert": "true",
        },
        data,
    )
    if status not in (200, 201):
        raise RuntimeError(f"upload {object_path} -> HTTP {status}: {raw[:200]!r}")


def upload_all(
    *,
    crop_dir: Path | None = None,
    url: str | None = None,
    service_key: str | None = None,
    only: str | None = None,
    limit: int | None = None,
    force: bool = False,
    dry_run: bool = False,
    http: HttpFn | None = None,
) -> FigureUploadReport:
    crop_dir = crop_dir if crop_dir is not None else config.CROP_DIR
    http = http or _urllib_http
    report = FigureUploadReport(dry_run=dry_run)

    stems = sorted(p for p in crop_dir.iterdir() if p.is_dir()) if crop_dir.is_dir() else []
    base = key = ""
    if not dry_run:
        base = resolve_url(url)
        key = resolve_service_key(service_key)

    for stem_dir in stems:
        stem = stem_dir.name
        if only and only not in stem:
            continue
        pngs = sorted(stem_dir.glob("q*_p*.png"))
        if not pngs:
            continue
        report.papers += 1

        existing: set[str] = set()
        if not force and not dry_run:
            existing = _list_prefix(http, base, key, f"{stem}/")

        for png in pngs:
            if limit is not None and report.uploaded >= limit:
                return report
            if png.name in existing:
                report.skipped_existing += 1
                continue
            if dry_run:
                report.uploaded += 1
                continue
            try:
                _upload(http, base, key, f"{stem}/{png.name}", png.read_bytes())
                report.uploaded += 1
            except RuntimeError as exc:
                report.failures.append(str(exc))

    return report
