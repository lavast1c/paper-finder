# Deploy progress — Vercel + Supabase (Stage 7b)

Plan: `~/.claude/plans/yes-can-you-implement-expressive-comet.md`
Resume by reading this file + `git log --oneline -15` + the plan, then do **NEXT**.
No secrets in this file.

**NEXT:** Code done + pushed. Step 1 (publish) done — Supabase index populated
(34 / 790 / 765). Auth is **email one-time code** (not Google — Google needed a
custom domain to publish). Remaining = Steps 2–5 in **Manual steps**: a free SMTP
relay (Brevo), Supabase Auth config (SMTP + email template + Site URL), Vercel
import + 2 env vars, verify.

## Code commits (§7)

- [x] 0 — Ignore `.env` / Vercel artefacts (`.gitignore`, `.env.example`, `.vercelignore`, this file)
- [x] 1 — Supabase schema `0001_question_bank` applied (migration file committed, advisors clean, anon locked out — verified via curl)
- [x] 2 — `paper-finder publish` — NOT yet run for real: needs the user's `.env` `SUPABASE_DB_URL` (session pooler). Local dry-run = 34 papers / 790 questions / 765 answered.
- [x] 3 — `/api/config` + `/api/health` + cloud-mode 501 guards in `web/app.py` — 100 tests green
- [x] 4 — Email one-time-code sign-in + Supabase search in `web/static/` (supabase-js@2.115.0 pinned + SRI; `#gate` = email step then 6-digit-code step; `signInWithOtp`/`verifyOtp`; `cloudRow` adapter; local mode unchanged — verified via `paper-finder serve`). Was Google OAuth; switched 2026-09-07 because publishing a Google app needs a custom domain. UI restyled 2026-09-07 — full-bleed, theme-aware, token-driven `style.css`, WCAG-AA checked, a11y fallbacks; then de-slopped (unslop-ui skill): brick-red accent (`#9c2f24`/`#f08a78`), IBM Plex type, tight radii, solid buttons, static backdrop, bigger answer text.
- [x] 5 — Vercel files: root `app.py` (Vercel FastAPI preset entrypoint; sys.path + create_app), `requirements.txt` (fastapi), `vercel.json` (region bom1 + daily /api/health cron). No `api/` dir, no rewrites (preset routes all paths). (Was `api/index.py` + rewrites; rebuilt 2026-09-07 for Vercel's current FastAPI preset, which ignores `api/`.) First real deploy 2026-09-07 crashed `ModuleNotFoundError: fastapi` — Vercel installs deps from `pyproject.toml`, not `requirements.txt` — fixed by moving `fastapi` into `[project.dependencies]`.
- [x] 6 — Docs (`CLAUDE.md`, `README.md`, `PLAN.md`) + this file's manual runbook

## Supabase state (project `gfigwnbkzkgwxcdoqxtz`, region ap-south-1)

- [x] migration `0001_question_bank` applied
- [x] migration `0002_search_kind_filter` applied (2026-09-07) — `search_questions` gains `kind text default 'all'` (`all`/`mcq`=Paper 1/`theory`=non-1); verified mcq→paper 1 only, theory→paper 2 only
- [x] migration `0003_question_has_figure` applied (2026-09-08) — `questions.has_figure boolean` + the RPC returns it; verified the function signature
- [x] `get_advisors(security)` clean (only the unrelated `auth_leaked_password_protection` WARN — N/A, this project is OTP-only)
- [x] `paper-finder publish` run for real — last run 2026-09-08: **40 papers / 931 questions / 906 answered / 285 has_figure** (replace-all, one txn). Cloud row counts verified via `execute_sql`; `search_questions('ball thrown horizontally projectile')` returns 2024 papers with correct `has_figure`. May/June = 22 papers (s24 v1-3, s25/s26 v1-4), Oct/Nov = 14, Feb/March = 4 (m24 + m26, variant 2)
- [x] anon curl: table read + `rpc/search_questions` both `permission denied`; `rpc/ping` → `"ok"`
- [ ] custom SMTP configured (Brevo) — USER, Step 3a
- [ ] "Magic Link" + "Confirm sign up" email templates contain `{{ .Token }}` (makes it a code, not a link) — USER, Step 3b
- [ ] Site URL set to the Vercel URL — USER, Step 4

Project URL: `https://gfigwnbkzkgwxcdoqxtz.supabase.co`
Publishable key id: `default` (`sb_publishable_…`) — value goes in Vercel env, not here.
Auth model: email OTP (`signInWithOtp` + `verifyOtp`, `type: "email"`). No Google.

## Manual steps (user only)

Everything in code is done and pushed. What's left is account/dashboard work I
can't do for you. Order: **1** (data, done) → **2** (SMTP) → **3** (Supabase Auth
config) → **4** (Vercel deploy) → **5** (verify).

Auth is **email one-time code**: the user types their email, Supabase emails a
6-digit code, they type it back, they're in. No Google, no passwords. Sessions
last indefinitely (Supabase default) so people sign in once.

Fixed values you'll reuse:

| Thing | Value |
|---|---|
| Supabase project ref | `gfigwnbkzkgwxcdoqxtz` |
| Supabase project URL | `https://gfigwnbkzkgwxcdoqxtz.supabase.co` |
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

- [x] Step 1 done (2026-09-07) — published 34 papers / 790 questions / 765 answered

---

### Step 2 — A free SMTP relay (Brevo)

Supabase's built-in email sender **only delivers to your project's team
addresses** — useless for friends. You need a real SMTP provider. Brevo's free
tier is 300 emails/day and, unlike Resend/Mailgun, works with just a **verified
sender email — no domain to buy.**

1. Sign up at <https://www.brevo.com> (free "Starter" plan).
2. **Senders, Domains & Dedicated IPs → Senders → Add a sender.** Use an email
   you control (a Gmail is fine), e.g. `paperfinder.login@gmail.com` or your own
   address. Brevo emails it a confirmation link — click it. Status must show
   **verified**.
3. **SMTP & API → SMTP** (left nav). Note:
   - Server: `smtp-relay.brevo.com`
   - Port: `587`
   - Login: the email shown there (a Brevo account address, *not* your sender)
   - Password: click **Generate a new SMTP key** → copy it (shown once)

- [ ] Step 2 done — Brevo sender verified, SMTP key generated

---

### Step 3 — Supabase Auth configuration

All in the Supabase dashboard for project `gfigwnbkzkgwxcdoqxtz`.

**3a. Custom SMTP** — **Authentication → Emails → SMTP Settings** (or
**Project Settings → Auth → SMTP**):
- Enable **Custom SMTP**.
- Sender email: your **verified Brevo sender** from Step 2.
- Sender name: `Paper Finder`
- Host: `smtp-relay.brevo.com`  ·  Port: `587`
- Username: your Brevo SMTP **login**  ·  Password: the Brevo **SMTP key**
- Save. Use the **"Send test email"** button if present.

**3b. Make the email send a CODE, not a link** — **Authentication → Emails →
Templates**. Supabase sends a numeric code **only if the template body contains
`{{ .Token }}`** (default templates only have `{{ .ConfirmationURL }}`, a link).
Edit **both** "Magic Link" **and** "Confirm sign up" (existing users get the
first, brand-new emails get the second) — set each body to:
```html
<h2>Your Paper Finder sign-in code</h2>
<p>Enter this code to sign in:</p>
<p style="font-size:24px;letter-spacing:3px;"><strong>{{ .Token }}</strong></p>
<p>It expires in 1 hour. If you didn't request it, ignore this email.</p>
```
Code length = **Authentication → Sign In / Providers → Email → Email OTP Length**.
The `#code` input is fixed at 6 digits (matches the current setting) — if you
change the length there, also change `maxlength` / `pattern` on `#code` in
`web/static/index.html`.
Subject for both: `Your Paper Finder sign-in code`. Save each.

**3c. Allow sign-ups** — **Authentication → Sign In / Providers → Email**:
- **Email** provider: enabled.
- **Confirm email**: on (fine — the code *is* the confirmation).
- Elsewhere: **Authentication → (Sign-ups / User Signups)** → "Allow new users to
  sign up" must be **on** (this is "allow all emails for now").

**3d. Site URL** — **Authentication → URL Configuration**:
- Set **Site URL** to your Vercel URL once you have it (Step 4). Until then
  `http://localhost:8000` is fine. Add `http://localhost:8000/**` to
  **Redirect URLs** if you want to test cloud mode locally. (The code flow
  doesn't redirect, but Supabase still wants a Site URL set.)

- [ ] Step 3 done — SMTP saved + test email received; Magic Link template has `{{ .Token }}`; sign-ups on

---

### Step 4 — Deploy to Vercel

The repo is set up for Vercel's **FastAPI preset**: root `app.py` exposes the
app, `requirements.txt` pins just `fastapi`, `vercel.json` sets the region + the
keep-warm cron. You don't configure a framework or build command — Vercel detects
it.

1. <https://vercel.com> → sign in with GitHub.
2. **Add New… → Project** → import `Lavastic-Gaming/paper-finder`. If it's not
   listed, "Adjust GitHub App Permissions" and grant access to the repo.
3. On the configure screen:
   - **Framework Preset:** it should auto-detect **FastAPI**. If it shows "Other",
     that's fine too — leave it; `app.py` is still the entrypoint.
   - Root Directory: leave as the repo root.
   - Build and Output Settings: leave **everything blank** — no build command, no
     output dir, no install command override.
   - **Environment Variables** — add both, for all environments:
     | Name | Value |
     |---|---|
     | `SUPABASE_URL` | `https://gfigwnbkzkgwxcdoqxtz.supabase.co` |
     | `SUPABASE_PUBLISHABLE_KEY` | Supabase → **Project Settings → API keys** → the **publishable** key (`sb_publishable_…`) |
   - **Do NOT add** `SUPABASE_DB_URL` or any `service_role` / secret key — those
     two are the only vars, and both are browser-safe.
4. **Deploy.** Watch the build log — it should `pip install fastapi …` (Vercel
   may also install pymupdf from `pyproject.toml`; harmless, the app doesn't
   import it). Finishes "Deploying outputs…". Copy the URL, e.g.
   `https://paper-finder-xxxx.vercel.app`.
   - If it fails with **"No Python entrypoint found"**: the FastAPI preset didn't
     see `fastapi` — check `requirements.txt` is at the repo root in the deployed
     commit.
   - If the function crashes with **`ModuleNotFoundError: No module named
     'fastapi'`**: Vercel installed from `pyproject.toml` and it lacked fastapi.
     Fixed 2026-09-07 — `fastapi` is now in `[project.dependencies]`. Redeploy
     from a commit at/after that fix.
   - If a page loads but `/` 404s: the preset isn't routing. Re-check the build
     detected FastAPI; redeploy.
5. Back in **Supabase → Authentication → URL Configuration**:
   - **Site URL** = that Vercel URL.
   - **Redirect URLs** → add `https://paper-finder-xxxx.vercel.app/**`.
6. Visit `https://paper-finder-xxxx.vercel.app/api/health` → `{"ok":true}` and
   `/api/config` → your URL + publishable key. Then do Step 5.

- [ ] Step 4 done — Vercel URL: __________________________________

---

### Step 5 — Verify end to end

1. Open the Vercel URL in a normal browser window → you see the **email prompt**,
   not the search box.
2. Enter your email → **Send code** → check your inbox → enter the 6-digit code →
   **Verify** → you're in ("Signed in as you@… · Sign out" + search box).
3. Search `ball thrown horizontally` → result cards with paper / question number
   / question text / answer / marks — **no "open PDF" link**.
4. CLI smoke checks:
   ```
   curl https://paper-finder-xxxx.vercel.app/api/config   → {"supabase_url":"...","supabase_key":"sb_publishable_..."}
   curl https://paper-finder-xxxx.vercel.app/api/health   → {"ok":true}
   ```
5. Sign out → the email prompt returns.
6. (Optional) have a friend try — they should get a code and get in with no
   action from you.

- [ ] Step 5 done — deployed site works: email code login, answers shown, no PDFs

**Free-tier note:** the Supabase project auto-pauses after ~7 days idle. The
`vercel.json` cron hits `/api/health` daily (which pings Supabase) to prevent it.
If it pauses anyway, un-pause from the dashboard.

**Email rate note:** Supabase caps auth emails per hour (raised once custom SMTP
is on; default ~30/hr). Brevo caps 300/day. Fine for friends; if a burst of
sign-ins hits the limit, people just retry a few minutes later.

---

### Later — refreshing the corpus

```powershell
.venv\Scripts\paper-finder download          # new PDFs into data/raw/
.venv\Scripts\paper-finder build             # rebuild papers.db
.venv\Scripts\paper-finder publish           # push to Supabase (replace-all, safe)
```
No redeploy needed — the deployed site reads Supabase live.

### Later — restricting to specific emails

Right now anyone who can receive a code can sign in and search. To lock it to an
allowlist: add an `allowed_emails` table + a `private.is_member()` function, swap
the RLS policy `using (true)` → `using ((select private.is_member()))`, and add a
`before-user-created` auth hook that rejects non-listed emails. One migration;
noted in `PLAN.md`.
