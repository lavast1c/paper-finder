# Paper Finder

Identify which past exam paper a question came from.

Type a few words of a question → get back the exact paper it came from (subject,
year, session, paper, variant, question number) and the answer. A later stage adds
lookup from a photo of the question.

- **Exam board:** Cambridge International (CIE) AS & A Level
- **Status:** early development — see [`PLAN.md`](PLAN.md) for the full roadmap
- **Stack:** Python 3.11+, PyMuPDF, SQLite (FTS5), sentence-transformers, FastAPI

## Notes

Personal / extracurricular project. CIE past papers are copyright of Cambridge
Assessment — the downloaded papers and the extracted question bank are **not**
committed to this repository and are for private study use only.
