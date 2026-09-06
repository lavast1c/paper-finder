# Deploy progress — Vercel + Supabase (Stage 7b)

Plan: `~/.claude/plans/yes-can-you-implement-expressive-comet.md`
Resume by reading this file + `git log --oneline -15` + the plan, then do **NEXT**.
No secrets in this file.

**NEXT:** Commit 1 — create & apply the Supabase schema migration.

## Code commits (§7)

- [x] 0 — Ignore `.env` / Vercel artefacts (`.gitignore`, `.env.example`, `.vercelignore`, this file)
- [ ] 1 — Supabase schema: `supabase/migrations/0001_question_bank.sql`, applied via MCP, advisors clean
- [ ] 2 — `paper-finder publish` (`publish.py`, cli, `publish` extra, `conftest.py`, `test_publish.py`)
- [ ] 3 — `/api/config` + `/api/health` in `web/app.py` (+ `test_web.py` additions)
- [ ] 4 — Google sign-in + Supabase search in `web/static/` (`index.html`, `app.js`, `style.css`)
- [ ] 5 — Vercel files (`api/index.py`, `requirements.txt`, `vercel.json`)
- [ ] 6 — Docs (`CLAUDE.md`, `README.md`, `PLAN.md`)

## Supabase state (project `gfigwnbkzkgwxcdoqxtz`, region ap-south-1)

- [ ] migration `0001_question_bank` applied (`list_migrations`)
- [ ] `get_advisors(security)` clean
- [ ] `paper-finder publish` run — papers ____ / questions ____
- [ ] anon `curl` to `rpc/search_questions` returns `[]` (RLS proof)

## Manual steps (user only — see plan §5)

- [ ] Google Cloud: OAuth client (Web) created; redirect URI = `https://gfigwnbkzkgwxcdoqxtz.supabase.co/auth/v1/callback`
- [ ] Supabase dashboard: Google provider enabled (Client ID + Secret pasted)
- [ ] Supabase dashboard: Auth → URL Configuration → Site URL + Redirect URLs = Vercel URL
- [ ] Vercel: GitHub repo connected
- [ ] Vercel: env vars `SUPABASE_URL` + `SUPABASE_PUBLISHABLE_KEY` set
- [ ] Local `.env`: `SUPABASE_DB_URL` set (session pooler) — needed before commit 2's publish run
- [ ] Deployed URL: ____________  (fill in once live)
