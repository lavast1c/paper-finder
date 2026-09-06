"""Vercel serverless entrypoint.

Vercel's Python runtime looks for a module-level ASGI ``app`` in a file under
``api/``. This repo is src-layout and is deliberately NOT pip-installed on Vercel
(that would pull in PyMuPDF for a deployment that never opens a PDF), so put
``src/`` on the path and import the package directly.

In cloud mode (``SUPABASE_URL`` + ``SUPABASE_PUBLISHABLE_KEY`` set in the Vercel
project) ``create_app`` serves only the static page, ``/api/config`` and
``/api/health`` — the browser talks to Supabase directly.
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from paper_finder.web.app import create_app  # noqa: E402

app = create_app()
