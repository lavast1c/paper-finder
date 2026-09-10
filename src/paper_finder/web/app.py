"""FastAPI application: the web UI over the question bank.

A thin JSON + static layer. Endpoints are plain ``def`` so Starlette runs them in
its threadpool -- ``search()`` is synchronous and opens its own SQLite connection
per call, so there is no cross-thread connection to guard.

Two modes, chosen by the browser from ``GET /api/config``:

* **local** -- no Supabase env vars. ``/api/search`` / ``/api/stats`` / ``/pdf``
  run against the local ``papers.db`` and ``data/raw/`` (this is ``paper-finder
  serve``: full detail, PDF deep-links, no login).
* **cloud** -- ``SUPABASE_URL`` + ``SUPABASE_PUBLISHABLE_KEY`` are set (the Vercel
  deployment). The page loads ``supabase-js``, signs the user in with an emailed
  one-time code (Supabase Auth), and calls the ``search_questions`` RPC directly;
  the Python app only serves the static page, ``/api/config`` and ``/api/health``.
  No ``papers.db`` on the server.
"""

from __future__ import annotations

import os
import re
import urllib.request
from dataclasses import asdict
from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles

from paper_finder import config
from paper_finder.config import SESSIONS
from paper_finder.db import connect, init_db
from paper_finder.filenames import parse_filename
from paper_finder.search import SearchHit, browse_by_topic, search, topic_counts

STATIC_DIR = Path(__file__).parent / "static"
DEFAULT_LIMIT = 10
MAX_LIMIT = 50

# A question crop filename, exactly as `figures.crop_path` writes it: q07_p1.png.
# A whitelist, not a sanitiser -- anything else (traversal, other extensions) is
# a 404.
_CROP_NAME = re.compile(r"^q\d{2}_p\d\.png$")


def _supabase_env() -> tuple[str, str] | None:
    """``(url, publishable_key)`` when both are set -- i.e. run in cloud mode."""
    url = os.environ.get("SUPABASE_URL")
    key = os.environ.get("SUPABASE_PUBLISHABLE_KEY")
    return (url.rstrip("/"), key) if url and key else None


def _csv_param(raw: str) -> list[str]:
    """``"s07, s08 ,"`` -> ``["s07", "s08"]``."""
    return [part.strip() for part in raw.split(",") if part.strip()]


def _int_csv(raw: str) -> list[int]:
    """``"2025, 2026, x"`` -> ``[2025, 2026]`` -- non-numeric tokens are dropped
    so a hand-edited query string degrades to "no filter" rather than a 500."""
    out: list[int] = []
    for part in _csv_param(raw):
        try:
            out.append(int(part))
        except ValueError:
            pass
    return out


def result_payload(hit: SearchHit, *, serve_pdfs: bool = True) -> dict:
    """A :class:`SearchHit` as the JSON object the browser consumes."""
    page = hit.page_start or 1
    session_name = SESSIONS.get(hit.session, hit.session)
    data = asdict(hit)  # every dataclass field, incl. has_figure + raw bm25 ``score``
    data["session_name"] = session_name
    data["paper_variant"] = hit.paper_variant
    data["page"] = page
    data["title"] = (
        f"{hit.subject_name or '?'} · {session_name} {hit.year} · "
        f"Paper {hit.paper_variant} · Q{hit.question_number}"
    )
    data["pdf_url"] = f"/pdf/{hit.filename}#page={page}" if serve_pdfs else None
    # One base per question; the browser appends `/q{NN}_p{k}.png` for k in
    # 1..crop_count. Gated by the same flag as the PDFs -- a crop of a page is
    # the same copyright profile as the page.
    data["crop_base"] = f"/figure/{hit.filename}" if serve_pdfs and hit.crop_count else None
    # The mark-scheme crops live under the `ms` stem (same paper, `_qp_` -> `_ms_`);
    # the browser appends `/q{NN}_p{k}.png` for k in 1..answer_crop_count.
    ms_filename = hit.filename.replace("_qp_", "_ms_")
    data["ms_crop_base"] = (
        f"/figure/{ms_filename}" if serve_pdfs and hit.answer_crop_count else None
    )
    return data


def resolve_pdf(filename: str, *, raw_dir: Path, db_path: Path | None) -> Path | None:
    """The on-disk PDF for a requested filename, or ``None`` if it must not be served."""
    parsed = parse_filename(filename)
    if (
        parsed is None
        or parsed.filename != filename.lower()
        or parsed.paper_type not in {"qp", "ms"}
    ):
        return None

    init_db(db_path)
    with connect(db_path) as conn:
        row = conn.execute("SELECT 1 FROM papers WHERE filename = ?", (parsed.filename,)).fetchone()
    if row is None:
        return None

    path = raw_dir / parsed.filename
    return path if path.is_file() else None


def resolve_crop(filename: str, crop: str, *, crop_dir: Path, db_path: Path | None) -> Path | None:
    """The on-disk crop image for a request, or ``None`` if it must not be served.

    Same gauntlet as :func:`resolve_pdf`: the filename must parse and round-trip
    exactly (kills ``../``, ``%2F``, odd suffixes), be a ``qp`` (question crop) or
    ``ms`` (mark-scheme crop), and have a ``papers`` row; the crop segment must
    match ``_CROP_NAME`` exactly; the file must exist under ``crop_dir/<stem>/``.
    """
    if not _CROP_NAME.match(crop):
        return None
    parsed = parse_filename(filename)
    if (
        parsed is None
        or parsed.filename != filename.lower()
        or parsed.paper_type not in {"qp", "ms"}
    ):
        return None

    init_db(db_path)
    with connect(db_path) as conn:
        row = conn.execute("SELECT 1 FROM papers WHERE filename = ?", (parsed.filename,)).fetchone()
    if row is None:
        return None

    path = crop_dir / Path(parsed.filename).stem / crop
    return path if path.is_file() else None


def corpus_stats(db_path: Path | None = None) -> dict:
    init_db(db_path)
    with connect(db_path) as conn:
        counts = conn.execute(
            """
            SELECT
                (SELECT COUNT(*) FROM papers)                         AS papers,
                (SELECT COUNT(*) FROM papers WHERE paper_type = 'qp') AS question_papers,
                (SELECT COUNT(*) FROM questions)                      AS questions,
                (SELECT COUNT(*) FROM answers)                        AS answers
            """
        ).fetchone()
        subjects = [
            r["subject_name"]
            for r in conn.execute(
                "SELECT DISTINCT subject_name FROM papers "
                "WHERE subject_name IS NOT NULL ORDER BY subject_name"
            )
        ]
    return {**dict(counts), "subjects": subjects}


def create_app(
    *,
    db_path: Path | None = None,
    raw_dir: Path | None = None,
    crop_dir: Path | None = None,
    serve_pdfs: bool = True,
) -> FastAPI:
    raw_dir = Path(raw_dir) if raw_dir is not None else config.RAW_DIR
    crop_dir = Path(crop_dir) if crop_dir is not None else config.CROP_DIR

    app = FastAPI(title="Paper Finder", docs_url=None, redoc_url=None)
    app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")

    @app.get("/", include_in_schema=False)
    def index() -> FileResponse:
        # Browse by topic is the landing page; keyword search moved to /search.
        return FileResponse(STATIC_DIR / "topics.html")

    @app.get("/search", include_in_schema=False)
    def search_page() -> FileResponse:
        return FileResponse(STATIC_DIR / "index.html")

    @app.get("/topics", include_in_schema=False)
    def topics_page() -> RedirectResponse:
        return RedirectResponse("/", status_code=308)  # old bookmarks/links

    @app.get("/api/config", include_in_schema=False)
    def api_config() -> dict:
        """Hands the browser the public Supabase creds in cloud mode, else ``{}``.

        The publishable key is safe in the browser -- RLS + the ``authenticated``
        grants are the real gate, and it can only reach ``search_questions`` /
        ``corpus_stats`` after an email one-time-code sign-in.
        """
        env = _supabase_env()
        return {"supabase_url": env[0], "supabase_key": env[1]} if env else {}

    @app.get("/api/health", include_in_schema=False)
    def api_health() -> dict:
        """Cheap keep-warm: the Vercel cron hits this daily; in cloud mode it
        pokes ``public.ping()`` so the free Supabase project doesn't auto-pause."""
        env = _supabase_env()
        if env:
            request = urllib.request.Request(
                f"{env[0]}/rest/v1/rpc/ping",
                data=b"{}",
                headers={"apikey": env[1], "Content-Type": "application/json"},
            )
            try:
                urllib.request.urlopen(request, timeout=10).read()
            except OSError:
                return {"ok": False}
        return {"ok": True}

    @app.get("/api/search")
    def api_search(
        q: str = "",
        limit: int = DEFAULT_LIMIT,
        kind: str = "all",
        years: str = "",
        sessions: str = "",
        variants: str = "",
    ) -> dict:
        if _supabase_env():  # cloud mode: the browser queries Supabase directly
            raise HTTPException(status_code=501, detail="cloud mode: use the Supabase RPC")
        limit = max(1, min(limit, MAX_LIMIT))
        hits = search(
            q,
            limit=limit,
            db_path=db_path,
            kind=kind,
            years=_int_csv(years) or None,
            sessions=_csv_param(sessions) or None,
            variants=_int_csv(variants) or None,
        )
        return {
            "query": q,
            "count": len(hits),
            "results": [result_payload(hit, serve_pdfs=serve_pdfs) for hit in hits],
        }

    @app.get("/api/stats")
    def api_stats() -> dict:
        if _supabase_env():
            raise HTTPException(status_code=501, detail="cloud mode: use the Supabase RPC")
        return corpus_stats(db_path)

    @app.get("/api/topics")
    def api_topics(
        kind: str = "all", years: str = "", sessions: str = "", variants: str = ""
    ) -> dict:
        """Per-topic counts under the current filters -- feeds the topic chips."""
        if _supabase_env():
            raise HTTPException(status_code=501, detail="cloud mode: use the Supabase RPC")
        return topic_counts(
            kind=kind,
            years=_int_csv(years) or None,
            sessions=_csv_param(sessions) or None,
            variants=_int_csv(variants) or None,
            db_path=db_path,
        )

    @app.get("/api/browse")
    def api_browse(
        topics: str = "",
        kind: str = "all",
        years: str = "",
        sessions: str = "",
        variants: str = "",
        limit: int = DEFAULT_LIMIT,
        offset: int = 0,
    ) -> dict:
        """Flashcard deck: questions tagged with any of ``topics`` (union),
        newest paper first. ``count`` is the full match total, not the page
        length, so the pager can render "n / total" from the first request."""
        if _supabase_env():
            raise HTTPException(status_code=501, detail="cloud mode: use the Supabase RPC")
        limit = max(1, min(limit, MAX_LIMIT))
        offset = max(0, offset)
        hits, total = browse_by_topic(
            _csv_param(topics),
            kind=kind,
            years=_int_csv(years) or None,
            sessions=_csv_param(sessions) or None,
            variants=_int_csv(variants) or None,
            limit=limit,
            offset=offset,
            db_path=db_path,
        )
        return {
            "topics": _csv_param(topics),
            "count": total,
            "offset": offset,
            "results": [result_payload(hit, serve_pdfs=serve_pdfs) for hit in hits],
        }

    @app.get("/pdf/{filename}", include_in_schema=False)
    def pdf(filename: str) -> FileResponse:
        if not serve_pdfs:
            raise HTTPException(status_code=404)
        path = resolve_pdf(filename, raw_dir=raw_dir, db_path=db_path)
        if path is None:
            raise HTTPException(status_code=404)
        return FileResponse(path, media_type="application/pdf")

    @app.get("/figure/{filename}/{crop}", include_in_schema=False)
    def figure(filename: str, crop: str) -> FileResponse:
        # A crop of a page has the same copyright profile as the page, so it is
        # gated by the same flag as the PDFs.
        if not serve_pdfs:
            raise HTTPException(status_code=404)
        path = resolve_crop(filename, crop, crop_dir=crop_dir, db_path=db_path)
        if path is None:
            raise HTTPException(status_code=404)
        return FileResponse(path, media_type="image/png")

    return app
