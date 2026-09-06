# Paper Finder

Identify which past exam paper a question came from.

Type a few words of a question → get back the exact paper it came from (subject,
year, session, paper, variant, question number) and the answer. A later stage adds
lookup from a photo of the question.

- **Exam board:** Cambridge International (CIE) AS & A Level
- **Status:** early development — see [`PLAN.md`](PLAN.md) for the full roadmap
- **Stack:** Python 3.11+, PyMuPDF, SQLite (FTS5), FastAPI

## Web UI

```
pip install -e ".[web]"
paper-finder serve            # http://127.0.0.1:8000
```

Type a few words of a question; each result shows the paper (subject, session,
year, paper/variant, question number), the question text, the marks, the
mark-scheme answer, and a link that opens the PDF at the right page.

Binds to localhost only. If you ever host this anywhere public, run
`paper-finder serve --no-pdfs` and do not deploy `data/raw/` — the past papers
are copyright of Cambridge Assessment and must not be redistributed.

## Notes

Personal / extracurricular project. CIE past papers are copyright of Cambridge
Assessment — the downloaded papers and the extracted question bank are **not**
committed to this repository and are for private study use only.
