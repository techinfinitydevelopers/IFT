# IFT Platform — Project Memory & Knowledge Base

> Context file for the IFT (India's Future Tycoons) Django platform.
> Last updated: 2026-07-21. Keep this current as work progresses.

## What this project is
IFT (India's Future Tycoons) — a national student innovation/entrepreneurship
competition platform for ages 13–18, run by **Tata ClassEdge | ENpower**.
Students submit venture ideas, get AI + jury evaluated, ranked (Top 400 / Top
100), and schools onboard/track their students.

- **Repo:** github.com/techinfinitydevelopers/IFT → local `/Users/apple/Downloads/IFT-AI/IFT`
- **Branch/workflow:** work goes **directly to `main`**. Commit/push ONLY when the user explicitly says "commit & push karo main pe" (per batch). Otherwise hold.
- **Stack:** Django 5.2.16, Python 3.12 (`.venv/`). SQLite local, PostgreSQL on Railway. WhiteNoise static. `dj_database_url` (`sqlite:///db.sqlite3`, relative to CWD). `python-dotenv` (`load_dotenv()`). `USE_TZ=True`, `TIME_ZONE=Asia/Kolkata`.
- **Apps:** `accounts` (auth/roles/email), `students` (student+school+submissions+teams), `admins` (super-admin dashboard, content, rankings, certificates), `ai_assistant` (AIEvaluation, ranking), `re_evaluation`.
- **Roles:** superadmin, jury/evaluator, school, student (via `accounts.UserProfile.role`).
- **Templates:** mostly **standalone HTML** with a per-role sidebar copied into each file (no shared base for admin/dashboards). Public/home uses `base.html`; auth uses `accounts/auth_base.html`.
- **Email:** ZeptoMail HTTP API via `accounts/email_backend.py` (`ZeptoMailBackend`). Enabled only when env sets `EMAIL_BACKEND=accounts.email_backend.ZeptoMailBackend` + `ZEPTOMAIL_API_KEY`. Default (local) = console backend (no real send).

## Deployments (Railway)
- **Original production:** `indiafuturetycoons.com` / `ift-production.up.railway.app`.
- **Capgemini instance:** `capgemini.indiafuturetycoons.com` — SEPARATE Railway project, **independent Postgres DB**, same repo, Dockerfile build (`CMD` runs `migrate` then gunicorn `--bind 0.0.0.0:8000`). GoDaddy DNS: CNAME + TXT (spelling is **capgemini**, not capegemini).
- Required env vars on each: `SECRET_KEY`, `DEBUG=False`, `ALLOWED_HOSTS`, `CSRF_TRUSTED_ORIGINS`, `SITE_URL`, `DEFAULT_FROM_EMAIL`, `EMAIL_BACKEND`, `ZEPTOMAIL_API_KEY`, AI keys; `DATABASE_URL` auto-provided by Railway.
- `SESSION_COOKIE_SECURE`/`CSRF_COOKIE_SECURE` are True only when `DEBUG=False`.

## Features built (recent sessions)
- Logo swapped to `static/images/New-Final-ift-logo.png` everywhere; auth logo `max-width:100px`; dashboard `.logo-img` height `95px`.
- School sign-up: **Coordinator Name** + **is_tata_classedge** ("Tata ClassEdge Network School? Yes/No").
- Student registration: unregistered-school popup (autocomplete); **Gender** (male/female) — stored in DB. Student model also has `is_paid`, `payment_transaction_id`, `middle_name`. Team max size = 2.
- School dashboard **Students tab**: 5 bento boxes + Payment + Transaction ID columns.
- **Teams & Submissions merged**: kept the submission page as-is, only ADDED a Members column (avatar circles, member-stack style). Restored pagination, idea view, submission pipeline, search + filters. (User was emphatic: do NOT remove the Team column.)
- School dashboard **Learning Resources** tab (copied from student page).
- **Upcoming Training Calendar**: super-admin managed via Content Management (`admins.Content` type `training` with `event_date`/`event_time`/`event_mode`); shown in school card + notification modal.
- **School & Teacher Benefits** badges: Silver(20+)/Gold(30+)/Excellence(40+) on registered+paid students, 3 progress bars.
- Fixed `submission_detail` 404 for school admin; "View Full Submission" opens within school dashboard chrome.
- Text changes: "Competition Results"→"Results", "Competition insights"→"Program Insights for", "competition"→"program" (5 student pages); "School Finals — Top 3"→"School Finals — Top Team".
- **Go-live confetti**: from 29 Jul 2026 11:00 AM IST, all users, once per user (localStorage `ift_launch_confetti_seen`). `accounts/context_processors.py:launch_confetti` + `templates/partials/launch_confetti.html` (canvas-confetti). Included in `base.html` + `auth_base.html`.
- **Certificate emailing** (this session, admin-triggered) — see [BUILD_LOG.md](BUILD_LOG.md) and native memory `certificate-feature.md`. 4 types: participation/top400/top100 → student, school_champion → school (one per school, school name). Uncommitted.

## Ranking system (for certs/reports)
`ai_assistant.AIEvaluation` (OneToOne → IdeaSubmission, related_name `ai_evaluation`): `final_score`, `rank`, `is_top_400`, `is_disqualified`. `ai_assistant/evaluator.py`: `update_rankings()` sets `rank` by score desc and `is_top_400 = rank<=400`; `get_top_n(n)`. **Top 100 = `rank<=100 & not disqualified`; Top 400 = `is_top_400`.**

## ⚠️ Gotchas / hard-won knowledge
- **Local runserver DB mismatch:** `preview_start` launches runserver with CWD = **parent** `/Users/apple/Downloads/IFT-AI` → it uses the **parent** `db.sqlite3`, NOT `IFT/db.sqlite3` (which `manage.py shell` uses from the IFT dir). Migrate/seed the DB matching the process's CWD, or the browser and shell will disagree.
- **In-app browser + localhost:** the sign-in page renders an empty accessibility tree (drive by JS/coords); the in-app browser drops localhost session cookies — verify request/response via the **Django test client** (`Client().force_login`, add `testserver` to ALLOWED_HOSTS) instead of UI login.
- **LearningVideo/VideoProgress migration gap:** both models exist in `students/models.py` but migration `0016` was **intentionally trimmed** (its own comment says so) — NO migration creates their tables. On a **fresh DB (capgemini)** any learning-resources query → `relation "students_learningvideo" does not exist`. Fix: `makemigrations students`; **real-run** on capgemini, but `migrate students <n> --fake` on any DB where the tables already exist (original production).
- **Railway filesystem is ephemeral:** user-uploaded files (submission attachments, and any future school photo/video uploads) are **lost on every redeploy** unless stored in cloud (S3/Cloudinary). Blocks reliable media collection.
- **Certificate colour:** templates are **CMYK JPGs with a "U.S. Web Coated (SWOP) v2" ICC profile**. Convert CMYK→sRGB via `ImageCms` (naive PIL convert shifts purple→blue). Cap render width to 3600px (school-champion.jpg is 18759px → 6.5MB PDF; capped → ~0.46MB). Name overlaid in Dancing Script (`static/fonts/DancingScript.ttf`, weight 600).
- **Browser cached 301 loop:** Chrome caches 301/308 redirects hard; **deleting cookies does NOT clear them** → `ERR_TOO_MANY_REDIRECTS` persists even after a server fix. Fix via Incognito / clear cached files. (The capgemini `/accounts/sign-up/` loop was this — server returned clean 200.)
- **Railway 502:** usually transient (container restart/redeploy/cold start). A past hard 502 was a custom Start Command with empty `$PORT`; fixed by letting the Dockerfile CMD (`--bind 0.0.0.0:8000`) run.

## Git state (2026-08-31)
- Local `main` in sync with `origin/main`, working tree clean. Latest: `dfd6ae5` Payment Status filter on super-admin students list.
- Payment fields on `Student`: `is_paid` (bool), `payment_amount` set at Razorpay **order-creation** time (not just on success) — so a student who started but never completed payment still has `payment_amount` populated with `is_paid=False`. Students who never attempted payment have `payment_amount=NULL`. `admins/views.py:students_list` supports `school`/`grade`/`price`/`paid` GET params; UI (`templates/admins/user_management/students_list.html`) now exposes all four as dropdowns.

## Pending / next
1. **Certificate feature:** commit → `git pull --rebase origin main` → push → Railway auto-deploy → live email test (capgemini env has ZeptoMail). NOTE `top400.jpg`'s printed body still reads "School Champion" (client to confirm). `school-champion.jpg` is 19MB (repo weight).
2. **Resources tab on school dashboard** (client req, 2026-07-21): a "Resources" tab with (a) **Curriculum section** — super-admin uploads IFT curriculum materials (arriving ~27–28 Jul), schools download; (b) **school supporting-docs upload** (photos/videos/files); (c) **IFT Finale date** calendar picker per school. OPEN QUESTIONS: relationship to existing Learning Resources tab; admin-side view to collect dates+media; cloud storage for uploads (ephemeral FS!); meaning of "IFT X".
3. **LearningVideo/VideoProgress migration** fix on Railway (see gotcha above).
4. Certificate email body text updated to client's citation wording (in `EMAIL_COPY`); email HTML formatting + "Teams" vs "Ideas" wording still open.
5. Earlier flagged (not done): `DEBUG=False` verify, `createsuperuser` on capgemini, larger feature backlog (grade/SDG charts, live ticker, backstories).

## User preferences
- Communicates in **Hindi/Hinglish** — respond likewise.
- Wants **concise, precise** answers (org policy). No filler.
- Commits only on explicit instruction, directly to `main`.
- Often asks "sirf batao" / "kya tumhe samjha" → wants understanding/confirmation BEFORE building.
