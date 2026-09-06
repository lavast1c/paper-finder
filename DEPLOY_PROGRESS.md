# Deploy progress — Vercel + Supabase (Stage 7b)

Plan: `~/.claude/plans/yes-can-you-implement-expressive-comet.md`
Resume by reading this file + `git log --oneline -15` + the plan, then do **NEXT**.
No secrets in this file.

**NEXT:** Commit 5 — Vercel files (`api/index.py`, `requirements.txt`, `vercel.json`).

## Code commits (§7)

- [x] 0 — Ignore `.env` / Vercel artefacts (`.gitignore`, `.env.example`, `.vercelignore`, this file)
- [x] 1 — Supabase schema `0001_question_bank` applied (migration file committed, advisors clean, anon locked out — verified via curl)
- [x] 2 — `paper-finder publish` — NOT yet run for real: needs the user's `.env` `SUPABASE_DB_URL` (session pooler). Local dry-run = 34 papers / 790 questions / 765 answered.
- [x] 3 — `/api/config` + `/api/health` + cloud-mode 501 guards in `web/app.py` — 100 tests green
- [x] 4 — Google sign-in + Supabase search in `web/static/` (supabase-js@2.115.0 pinned + SRI; `#gate` login screen; `cloudRow` adapter; local mode unchanged — verified via `paper-finder serve`)
- [ ] 5 — Vercel files (`api/index.py`, `requirements.txt`, `vercel.json`)
- [ ] 6 — Docs (`CLAUDE.md`, `README.md`, `PLAN.md`)

## Supabase state (project `gfigwnbkzkgwxcdoqxtz`, region ap-south-1)

- [x] migration `0001_question_bank` applied
- [x] `get_advisors(security)` clean (no lints)
- [ ] `paper-finder publish` run for real — papers ____ / questions ____  (USER: needs `.env` SUPABASE_DB_URL)
- [x] anon curl: table read + `rpc/search_questions` both `permission denied`; `rpc/ping` → `"ok"`

Project URL: `https://gfigwnbkzkgwxcdoqxtz.supabase.co`
Publishable key id: `default` (`sb_publishable_…`) — value goes in Vercel env, not here.

## Manual steps (user only — see plan §5)

- [ ] Google Cloud: OAuth client (Web) created; redirect URI = `https://gfigwnbkzkgwxcdoqxtz.supabase.co/auth/v1/callback`
- [ ] Supabase dashboard: Google provider enabled (Client ID + Secret pasted)
- [ ] Supabase dashboard: Auth → URL Configuration → Site URL + Redirect URLs = Vercel URL
- [ ] Vercel: GitHub repo connected
- [ ] Vercel: env vars `SUPABASE_URL` + `SUPABASE_PUBLISHABLE_KEY` set
- [ ] Local `.env`: `SUPABASE_DB_URL` set (session pooler) — needed before commit 2's publish run
- [ ] Deployed URL: ____________  (fill in once live)
