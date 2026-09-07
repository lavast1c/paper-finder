# Paper Finder

Identify which past exam paper a question came from.

Type a few words of a question → get back the exact paper it came from (subject,
year, session, paper, variant, question number) and the answer. A later stage adds
lookup from a photo of the question.

- **Exam board:** Cambridge International (CIE) AS & A Level
- **Status:** early development — see [`PLAN.md`](PLAN.md) for the full roadmap
- **Stack:** Python 3.11+, PyMuPDF, SQLite (FTS5), FastAPI

## Web UI (local)

```
pip install -e ".[web]"
paper-finder serve            # http://127.0.0.1:8000
```

Type a few words of a question; each result shows the paper (subject, session,
year, paper/variant, question number), the question text, the marks, the
mark-scheme answer, and a link that opens the PDF at the right page. Binds to
localhost only; no login; reads the local `papers.db` and `data/raw/`.

## Deployed (Vercel + Supabase)

The same app runs on Vercel in **cloud mode**: it serves only the static page,
`/api/config` and `/api/health`; the browser signs the user in with a 6-digit
code emailed by Supabase Auth, then queries a Supabase Postgres index directly.
That index holds question text + answers **only** — never the PDFs, which stay on
the author's machine. Anyone who can receive a code at their email can search
("allow all emails for now").

```
pip install -e ".[publish]"
paper-finder publish          # push the question bank to Supabase (needs SUPABASE_DB_URL)
```

`supabase/migrations/0001_question_bank.sql` is the schema (RLS + a
`search_questions` RPC). Full deploy runbook and the one-time Supabase / SMTP /
Vercel setup: [`DEPLOY_PROGRESS.md`](DEPLOY_PROGRESS.md).

## Notes

Personal / extracurricular project. CIE past papers are copyright of Cambridge
Assessment — the downloaded papers and the extracted question bank are **not**
committed to this repository and are for private study use only.
