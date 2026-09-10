"""Download CIE past papers by generating their URLs and fetching them.

A CIE filename is fully determined by (subject, session, year, paper, variant,
type), so the whole configured scope can be turned into candidate URLs; we GET
each one, save the PDFs, and skip 404s (that combination never existed).

The mirror (PapaCambridge) may refuse automated requests -- a 403, or a Cloudflare
challenge page served with HTTP 200. A missing paper is normal (a 404, or -- on
PapaCambridge -- a 302 redirect to the site homepage, which the fetcher maps to
404); anything else that repeats is treated as the mirror blocking us and the run
aborts with a clear message.
Files saved before an abort are kept, and re-running resumes (existing files are
skipped). This module writes only PDFs and a CSV attempt log -- never the
database; run ``paper-finder build`` afterwards.

Respect the mirror's robots.txt and keep this to personal study use.
"""

from __future__ import annotations

import csv
import datetime as dt
import time
import urllib.error
import urllib.parse
import urllib.request
from collections.abc import Callable, Iterator
from dataclasses import dataclass, field
from pathlib import Path

from paper_finder import config
from paper_finder.filenames import build_filename

_PDF_MAGIC = b"%PDF"
_CSV_HEADER = ["timestamp", "filename", "url", "status", "outcome", "bytes", "message"]


@dataclass(frozen=True)
class FetchResult:
    status: int  # HTTP status code; 0 means the request never completed
    body: bytes
    error: str = ""


Fetcher = Callable[[str], FetchResult]


def _urllib_fetcher(url: str) -> FetchResult:
    request = urllib.request.Request(url, headers={"User-Agent": config.USER_AGENT})
    try:
        with urllib.request.urlopen(request, timeout=config.REQUEST_TIMEOUT_SECONDS) as response:
            # PapaCambridge answers a paper it does not hold with a 302 to its
            # homepage instead of a 404. urllib follows the redirect, so detect it
            # by the final URL no longer pointing at the .pdf and report not-found.
            if not response.geturl().lower().endswith(".pdf"):
                return FetchResult(status=404, body=b"")
            return FetchResult(status=response.status, body=response.read())
    except urllib.error.HTTPError as exc:
        return FetchResult(status=exc.code, body=b"")
    except (urllib.error.URLError, TimeoutError, OSError) as exc:
        return FetchResult(status=0, body=b"", error=str(exc))


def mirror_url(filename: str) -> str:
    """The mirror stores every PDF flat: ``{MIRROR_BASE_URL}/9702_s24_qp_12.pdf``."""
    return f"{config.MIRROR_BASE_URL.rstrip('/')}/{urllib.parse.quote(filename)}"


@dataclass(frozen=True)
class Candidate:
    filename: str
    url: str
    subject_code: str
    year: int


def iter_candidates(scope: dict | None = None) -> Iterator[Candidate]:
    """Enumerate candidate PDFs. ``scope["subjects"]`` maps a subject code to its
    own ``{"papers": [...], "variants": [...]}``; ``years`` / ``sessions`` /
    ``types`` are shared across subjects."""
    scope = scope if scope is not None else config.DOWNLOAD_SCOPE
    for subject_code, sub in scope["subjects"].items():
        for year in scope["years"]:
            for session in scope["sessions"]:
                for paper in sub["papers"]:
                    for variant in sub["variants"]:
                        for paper_type in scope["types"]:
                            filename = build_filename(
                                subject_code, session, year, paper_type, paper, variant
                            )
                            yield Candidate(
                                filename=filename,
                                url=mirror_url(filename),
                                subject_code=subject_code,
                                year=year,
                            )


@dataclass
class DownloadReport:
    downloaded: list[str] = field(default_factory=list)
    skipped_existing: list[str] = field(default_factory=list)
    not_found: list[str] = field(default_factory=list)  # 4xx/5xx -- paper not on mirror
    failed: list[tuple[str, str]] = field(default_factory=list)  # (filename, reason)
    would_fetch: list[str] = field(default_factory=list)  # dry-run only
    aborted: str = ""


_ABORT_MESSAGE = (
    "Mirror is refusing automated requests (HTTP 403 / challenge page / network "
    "errors). Try another MIRROR_BASE_URL / USER_AGENT in config.py, or download "
    "the rest by hand (data/raw/README.md). Files saved this run are kept."
)


def _classify(result: FetchResult) -> tuple[str, str]:
    """Return ``(bucket, reason)`` where bucket is downloaded / not_found / blocked."""
    if result.status == 200 and result.body.startswith(_PDF_MAGIC):
        return "downloaded", ""
    if result.status == 403:
        return "blocked", "HTTP 403"
    if result.status == 200:
        return "blocked", "HTTP 200 but body is not a PDF (challenge page?)"
    if result.status == 0:
        return "blocked", f"network error: {result.error}"
    return "not_found", f"HTTP {result.status}"  # 404 / 500 / other -- not on the mirror


def _timestamp() -> str:
    return dt.datetime.now(tz=dt.UTC).isoformat(timespec="seconds")


def download(
    *,
    scope: dict | None = None,
    raw_dir: Path | None = None,
    log_path: Path | None = None,
    fetcher: Fetcher = _urllib_fetcher,
    limit: int | None = None,
    dry_run: bool = False,
    delay: float | None = None,
    max_consecutive_failures: int = 3,
) -> DownloadReport:
    raw_dir = raw_dir if raw_dir is not None else config.RAW_DIR
    log_path = log_path if log_path is not None else config.DOWNLOAD_LOG_PATH
    delay = delay if delay is not None else config.REQUEST_DELAY_SECONDS

    report = DownloadReport()
    candidates = list(iter_candidates(scope))

    if dry_run:
        for candidate in candidates:
            if (raw_dir / candidate.filename).exists():
                report.skipped_existing.append(candidate.filename)
            else:
                report.would_fetch.append(candidate.url)
        return report

    raw_dir.mkdir(parents=True, exist_ok=True)
    log_path.parent.mkdir(parents=True, exist_ok=True)
    write_header = not log_path.exists()

    with log_path.open("a", newline="", encoding="utf-8") as handle:
        writer = csv.writer(handle)
        if write_header:
            writer.writerow(_CSV_HEADER)

        def log(candidate_or_none, status, outcome, size="", message=""):
            filename = candidate_or_none.filename if candidate_or_none else ""
            url = candidate_or_none.url if candidate_or_none else ""
            writer.writerow([_timestamp(), filename, url, status, outcome, size, message])

        consecutive_failures = 0
        first_request = True

        for candidate in candidates:
            dest = raw_dir / candidate.filename

            if dest.exists():
                report.skipped_existing.append(candidate.filename)
                log(candidate, "", "skipped_existing")
                continue

            if limit is not None and len(report.downloaded) >= limit:
                break

            if not first_request:
                time.sleep(delay)
            first_request = False

            result = fetcher(candidate.url)
            bucket, reason = _classify(result)

            if bucket == "downloaded":
                dest.write_bytes(result.body)
                report.downloaded.append(candidate.filename)
                consecutive_failures = 0
                log(candidate, 200, "downloaded", size=len(result.body))
                continue

            if bucket == "not_found":
                report.not_found.append(candidate.filename)
                consecutive_failures = 0
                log(candidate, result.status, "not_found", message=reason)
                continue

            # bucket == "blocked"
            report.failed.append((candidate.filename, reason))
            log(candidate, result.status, "failed", message=reason)
            if result.status == 403:
                report.aborted = _ABORT_MESSAGE
            else:
                consecutive_failures += 1
                if consecutive_failures >= max_consecutive_failures:
                    report.aborted = _ABORT_MESSAGE
            if report.aborted:
                log(None, "", "aborted", message=report.aborted)
                break

    return report
