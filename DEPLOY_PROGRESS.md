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

Everything in code is done and pushed. What's left is account/dashboard work I
can't do for you. Rough order: **1** (data), then **2 → 3 → 4** (the URL
chicken-and-egg — do 2 partly, deploy in 3, finish 2 + do 4 with the real URL),
then **5** (verify).

Fixed values you'll reuse:

| Thing | Value |
|---|---|
| Supabase project ref | `gfigwnbkzkgwxcdoqxtz` |
| Supabase project URL | `https://gfigwnbkzkgwxcdoqxtz.supabase.co` |
| Google OAuth **redirect URI** (never changes) | `https://gfigwnbkzkgwxcdoqxtz.supabase.co/auth/v1/callback` |
| GitHub repo | `Lavastic-Gaming/paper-finder` |
| Expected publish counts | 34 papers / 790 questions / 765 answered |

---

### Step 1 — Get the question bank into Supabase (`paper-finder publish`)

This is independent of everything else; do it first.

1. **Get the DB connection string.** Supabase dashboard → your project → gear
   icon **Project Settings** (bottom left) → **Database** → section
   **Connection string** → tab **URI** → toggle **Use connection pooling** ON →
   **Mode: Session** (NOT "Transaction"). Copy the string. It looks like:
   ```
   postgresql://postgres.gfigwnbkzkgwxcdoqxtz:[YOUR-PASSWORD]@aws-0-ap-south-1.pooler.supabase.com:5432/postgres
   ```
   - Port must be **5432** (session pooler). 6543 is the transaction pooler and
     breaks psycopg — don't use it.
   - Replace `[YOUR-PASSWORD]` with your database password. If you don't know it:
     same page, **Database password** → **Reset database password** (this only
     affects direct DB access, not the app).

2. **Create `.env`** in the repo root (`C:\Users\vihaa\Downloads\Paper Finder\.env`).
   It's gitignored — it will never be committed or uploaded. One line:
   ```
   SUPABASE_DB_URL=postgresql://postgres.gfigwnbkzkgwxcdoqxtz:YOURPASSWORD@aws-0-ap-south-1.pooler.supabase.com:5432/postgres
   ```
   In PowerShell from the repo root:
   ```powershell
   'SUPABASE_DB_URL=postgresql://postgres.gfigwnbkzkgwxcdoqxtz:YOURPASSWORD@aws-0-ap-south-1.pooler.supabase.com:5432/postgres' | Out-File -Encoding utf8 .env
   ```

3. **Run the publish:**
   ```powershell
   .venv\Scripts\python -m pip install -e ".[publish]"
   .venv\Scripts\paper-finder publish --dry-run     # prints counts, sends nothing
   .venv\Scripts\paper-finder publish               # the real push (replace-all, one transaction)
   ```
   Expect: `papers 34 / questions 790 (765 with an answer)`. Safe to re-run any
   time — it wipes and reloads.

4. Verify in the dashboard: **Table Editor** → `papers` (34 rows), `questions`
   (790 rows).

- [ ] Step 1 done — published ____ papers / ____ questions

---

### Step 2 — Google OAuth client (Google Cloud Console)

You need a Google OAuth "client" so Supabase can offer "Sign in with Google".

1. Go to <https://console.cloud.google.com>. Top bar → project dropdown → **New
   Project** → name it `paper-finder` → Create. Make sure it's selected.

2. Left menu (hamburger) → **APIs & Services** → **OAuth consent screen** (newer
   consoles call this **Google Auth Platform → Branding**).
   - User type: **External** → Create.
   - App name: `Paper Finder`. User support email: your email. Developer contact:
     your email. Save and continue.
   - **Scopes:** Add → tick `.../auth/userinfo.email`, `.../auth/userinfo.profile`,
     `openid` → Update → Save and continue.
   - **Test users:** while the app is in "Testing" mode only emails you add here
     can sign in. Add your Gmail and your friends' Gmails. (Or later click
     **Publish app** to allow any Google account — that's the "allow all emails"
     state. Publishing an app that only uses email/profile scopes does **not**
     need Google verification.)
   - Save.

3. Left menu → **APIs & Services** → **Credentials** → **+ Create Credentials** →
   **OAuth client ID**.
   - Application type: **Web application**.
   - Name: `paper-finder-web`.
   - **Authorized redirect URIs** → Add URI →
     `https://gfigwnbkzkgwxcdoqxtz.supabase.co/auth/v1/callback`
     (exactly this — it's the Supabase callback and never changes).
   - **Authorized JavaScript origins:** leave empty for now — you'll add the
     Vercel URL here in Step 4 once you have it. (Add `http://localhost:8000` too
     if you ever want to run cloud mode locally.)
   - Create. A dialog shows **Client ID** and **Client secret** — keep this tab
     open, you need both in Step 3.

- [ ] Step 2 done — OAuth client created, redirect URI set (JS origin pending Step 4)

---

### Step 3 — Wire Google into Supabase, then deploy to Vercel

**3a. Supabase → enable Google**

1. Supabase dashboard → **Authentication** → **Sign In / Providers** (or
   **Providers**) → find **Google** → enable.
2. Paste the **Client ID** and **Client Secret** from Step 2. Save.
3. Leave "Skip nonce checks" off. You don't need to touch "Authorized Client IDs".

**3b. Vercel → import and deploy**

1. Go to <https://vercel.com>, sign in with GitHub.
2. **Add New… → Project** → import `Lavastic-Gaming/paper-finder`. If Vercel
   can't see it, "Adjust GitHub App Permissions" and grant access to that repo.
3. Configure project:
   - **Framework Preset: Other.**
   - Root Directory: leave as is (repo root).
   - Build & Output Settings: leave all blank (the `vercel.json` handles it).
   - **Environment Variables** — add two (Environment: all of Production,
     Preview, Development):
     | Name | Value |
     |---|---|
     | `SUPABASE_URL` | `https://gfigwnbkzkgwxcdoqxtz.supabase.co` |
     | `SUPABASE_PUBLISHABLE_KEY` | copy from Supabase → **Project Settings → API keys** → the **publishable** key (`sb_publishable_…`) |
   - **Do NOT add** `SUPABASE_DB_URL` or any `service_role` / secret key here.
     Those two above are the only ones, and both are safe to expose in a browser.
4. **Deploy.** When it finishes, copy the production URL, e.g.
   `https://paper-finder-xxxx.vercel.app`.

**3c. Feed the Vercel URL back into Google + Supabase**

1. **Google Cloud** → Credentials → your OAuth client → **Authorized JavaScript
   origins** → Add → your Vercel URL (`https://paper-finder-xxxx.vercel.app`, no
   trailing slash, no path) → Save. (Changes can take a few minutes to apply.)
2. **Supabase** → **Authentication** → **URL Configuration**:
   - **Site URL:** `https://paper-finder-xxxx.vercel.app`
   - **Redirect URLs:** Add `https://paper-finder-xxxx.vercel.app/**`
     (and `http://localhost:8000/**` if you test locally).

- [ ] Step 3 done — Vercel URL: __________________________________

---

### Step 4 — (only if you added a custom domain) repeat 3c for the new domain

Skip unless you attach your own domain in Vercel. If you do, add that domain to
Google JS origins and Supabase Site URL / Redirect URLs too.

---

### Step 5 — Verify end to end

1. Open your Vercel URL in a normal browser window. You should see the
   **"Sign in to search"** gate, not the search box.
2. Click **Continue with Google** → pick your account → consent → you land back
   on the page, now showing "Signed in as you@gmail.com" and the search box.
3. Search `ball thrown horizontally` → you get result cards with the paper
   (subject / session / year / paper / variant / question number), the question
   text, the answer, and marks — **no "open PDF" link** (correct: no PDFs in the
   cloud).
4. Command-line smoke checks (any shell):
   ```
   curl https://paper-finder-xxxx.vercel.app/api/config    → {"supabase_url":"...","supabase_key":"sb_publishable_..."}
   curl https://paper-finder-xxxx.vercel.app/api/health    → {"ok":true}
   ```
5. Sign out, confirm the gate comes back.

- [ ] Step 5 done — deployed site works, login required, answers shown, no PDFs

**Free-tier note:** the project auto-pauses after ~7 days of no activity. The
`vercel.json` cron hits `/api/health` daily (which pings Supabase) to prevent
that. If it ever pauses anyway, un-pause from the Supabase dashboard.

---

### Later — refreshing the corpus

When you download more papers:
```powershell
.venv\Scripts\paper-finder download          # new PDFs into data/raw/
.venv\Scripts\paper-finder build             # rebuild papers.db
.venv\Scripts\paper-finder publish           # push to Supabase (replace-all, safe)
```
No redeploy needed — the deployed site reads Supabase live.

### Later — restricting to specific emails

Right now any Google account that signs in can search. To lock it to an
allowlist: add an `allowed_emails` table + a `private.is_member()` function, swap
the RLS policy `using (true)` → `using ((select private.is_member()))`, and add a
`before-user-created` auth hook. One migration; noted in `PLAN.md`.
