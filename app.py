"""Vercel entrypoint for the deployed web UI.

Vercel's FastAPI preset (triggered by ``fastapi`` in ``requirements.txt``) loads
a module-level ``app`` from one of a fixed set of filenames at the repo root --
this is that file. The repo is src-layout and is deliberately NOT pip-installed
on Vercel (that would pull PyMuPDF for a deployment that never opens a PDF), so
put ``src/`` on the path and import the package.

In cloud mode (``SUPABASE_URL`` + ``SUPABASE_PUBLISHABLE_KEY`` set in the Vercel
project) ``create_app`` serves only the static page, ``/api/config`` and
``/api/health`` -- the browser talks to Supabase directly.
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent / "src"))

from paper_finder.web.app import create_app  # noqa: E402

app = create_app()
