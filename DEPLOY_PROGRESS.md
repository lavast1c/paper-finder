# Deploy progress — Vercel + Supabase (Stage 7b)

Plan: `~/.claude/plans/yes-can-you-implement-expressive-comet.md`
Resume by reading this file + `git log --oneline -15` + the plan, then do **NEXT**.
No secrets in this file.

**NEXT:** All 7 code commits (0–6) are done and pushed. Nothing left in code.
Remaining work is the **Manual steps** section below — account/dashboard actions
only the user can do (local `.env` + `paper-finder publish`, Google Cloud OAuth,
Supabase Google provider + URL config, Vercel import + env vars).

## Code commits (§7)

- [x] 0 — Ignore `.env` / Vercel artefacts (`.gitignore`, `.env.example`, `.vercelignore`, this file)
- [x] 1 — Supabase schema `0001_question_bank` applied (migration file committed, advisors clean, anon locked out — verified via curl)
- [x] 2 — `paper-finder publish` — NOT yet run for real: needs the user's `.env` `SUPABASE_DB_URL` (session pooler). Local dry-run = 34 papers / 790 questions / 765 answered.
- [x] 3 — `/api/config` + `/api/health` + cloud-mode 501 guards in `web/app.py` — 100 tests green
- [x] 4 — Google sign-in + Supabase search in `web/static/` (supabase-js@2.115.0 pinned + SRI; `#gate` login screen; `cloudRow` adapter; local mode unchanged — verified via `paper-finder serve`)
- [x] 5 — Vercel files: `api/index.py` (sys.path + create_app), `requirements.txt` (fastapi only), `vercel.json` (rewrites + includeFiles + bom1 + daily /api/health cron). Entrypoint import verified.
- [x] 6 — Docs (`CLAUDE.md`, `README.md`, `PLAN.md`) + this file's manual runbook

## Supabase state (project `gfigwnbkzkgwxcdoqxtz`, region ap-south-1)

- [x] migration `0001_question_bank` applied
- [x] `get_advisors(security)` clean (no lints)
- [ ] `paper-finder publish` run for real — papers ____ / questions ____  (USER: needs `.env` SUPABASE_DB_URL)
- [x] anon curl: table read + `rpc/search_questions` both `permission denied`; `rpc/ping` → `"ok"`

Project URL: `https://gfigwnbkzkgwxcdoqxtz.supabase.co`
Publishable key id: `default` (`sb_publishable_…`) — value goes in Vercel env, not here.

## Manual steps (user only)

Everything in code is done and pushed. These are the account/dashboard actions
only you can do. Order matters a little: do 1→2→3, then 4, then 5, then 6.

### 1. Local `.env` + first publish
- [ ] Supabase → Project Settings → Database → **Connection string → Session
      pooler** (URI, port 5432, user `postgres.gfigwnbkzkgwxcdoqxtz`). Put it in
      `.env` at the repo root as `SUPABASE_DB_URL=...` (`.env` is gitignored).
- [ ] `pip install -e ".[publish]"` then `paper-finder publish` → should report
      `papers 34 / questions 790 (765 with an answer)`.

### 2. Google Cloud OAuth client (~10 min)
- [ ] console.cloud.google.com → create/select a project.
- [ ] "Google Auth Platform" → set up the consent screen (External; app name
      "Paper Finder"; your email). Scopes: `openid`, `.../auth/userinfo.email`,
      `.../auth/userinfo.profile`.
- [ ] Clients → **Create OAuth client → Web application**:
      - Authorized redirect URI: `https://gfigwnbkzkgwxcdoqxtz.supabase.co/auth/v1/callback`
      - Authorized JavaScript origins: your Vercel URL (add after step 4; you can
        edit the client later). Add `http://localhost:8000` only if you want to
        test cloud mode locally.
- [ ] Copy the **Client ID** and **Client secret**.

### 3. Supabase dashboard
- [ ] Authentication → Sign In / Providers → **Google** → enable, paste Client ID
      + Secret, save.
- [ ] Authentication → URL Configuration → **Site URL** = your Vercel URL; add it
      (and `http://localhost:8000` if testing locally) under **Redirect URLs**.

### 4. Vercel
- [ ] Import the GitHub repo `Lavastic-Gaming/paper-finder` (New Project → Import).
      Framework preset: **Other**. No build command needed.
- [ ] Project → Settings → Environment Variables (Production + Preview):
      - `SUPABASE_URL` = `https://gfigwnbkzkgwxcdoqxtz.supabase.co`
      - `SUPABASE_PUBLISHABLE_KEY` = the `sb_publishable_…` key (Supabase →
        Project Settings → API). Both are browser-safe.
- [ ] Deploy. Note the URL: ____________
- [ ] Go back to steps 2 + 3 and put that URL into Google "Authorized JavaScript
      origins" and Supabase "Site URL" / "Redirect URLs".

### 5. Verify
- [ ] Open the Vercel URL → "Continue with Google" → consent → back, signed in.
- [ ] Search "ball thrown horizontally" → results with question text + answer, no
      PDF link.
- [ ] Redeploy / visit again after a day → still up (the cron holds the pause off).

### 6. Refreshing the corpus later
- [ ] `paper-finder download … && paper-finder build && paper-finder publish`
      (publish replaces everything — safe to re-run).
