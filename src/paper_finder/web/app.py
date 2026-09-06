"""FastAPI application: a local web UI over the existing question bank.

A thin JSON + static layer over ``search.search()``. Endpoints are plain ``def``
so Starlette runs them in its threadpool -- ``search()`` is synchronous and opens
its own SQLite connection per call, so there is no cross-thread connection to
guard.

Serving the past-paper PDFs is opt-out (``serve_pdfs=False``): the papers are
copyright of Cambridge Assessment, so a public deployment must run without them
and must not ship ``data/raw/``.
"""

from __future__ import annotations

from dataclasses import asdict
from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from paper_finder import config
from paper_finder.config import SESSIONS
from paper_finder.db import connect, init_db
from paper_finder.filenames import parse_filename
from paper_finder.search import SearchHit, search

STATIC_DIR = Path(__file__).parent / "static"
DEFAULT_LIMIT = 10
MAX_LIMIT = 50


def result_payload(hit: SearchHit, *, serve_pdfs: bool = True) -> dict:
    """A :class:`SearchHit` as the JSON object the browser consumes."""
    page = hit.page_start or 1
    session_name = SESSIONS.get(hit.session, hit.session)
    data = asdict(hit)  # the 12 dataclass fields (raw bm25 ``score`` included)
    data["session_name"] = session_name
    data["paper_variant"] = hit.paper_variant
    data["page"] = page
    data["title"] = (
        f"{hit.subject_name or '?'} · {session_name} {hit.year} · "
        f"Paper {hit.paper_variant} · Q{hit.question_number}"
    )
    data["pdf_url"] = f"/pdf/{hit.filename}#page={page}" if serve_pdfs else None
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
    serve_pdfs: bool = True,
) -> FastAPI:
    raw_dir = Path(raw_dir) if raw_dir is not None else config.RAW_DIR

    app = FastAPI(title="Paper Finder", docs_url=None, redoc_url=None)
    app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")

    @app.get("/", include_in_schema=False)
    def index() -> FileResponse:
        return FileResponse(STATIC_DIR / "index.html")

    @app.get("/api/search")
    def api_search(q: str = "", limit: int = DEFAULT_LIMIT) -> dict:
        limit = max(1, min(limit, MAX_LIMIT))
        hits = search(q, limit=limit, db_path=db_path)
        return {
            "query": q,
            "count": len(hits),
            "results": [result_payload(hit, serve_pdfs=serve_pdfs) for hit in hits],
        }

    @app.get("/api/stats")
    def api_stats() -> dict:
        return corpus_stats(db_path)

    @app.get("/pdf/{filename}", include_in_schema=False)
    def pdf(filename: str) -> FileResponse:
        if not serve_pdfs:
            raise HTTPException(status_code=404)
        path = resolve_pdf(filename, raw_dir=raw_dir, db_path=db_path)
        if path is None:
            raise HTTPException(status_code=404)
        return FileResponse(path, media_type="application/pdf")

    return app
