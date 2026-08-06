# Build Log

## 2026-08-06 — Phone OTP verification on student & school sign-up (Sevenomedia SMS)
- New `accounts/otp.py`: `generate_and_send(request, phone)` (6-digit OTP, stored in **session** for gunicorn-multi-worker reliability, 10-min expiry) + `verify(request, phone, code)`. Hits the Sevenomedia `bulksms_v2.php` gateway (apikey-based); success detected via `SUCCESS | <msg-id> | <mobile>` response.
- Endpoint `POST /accounts/api/send-otp/` (`send_otp_api`). `sign_up` and `school_sign_up` views now call `otp.verify(...)` before creating the account and `otp.clear(...)` on success.
- Templates `sign_up.html` + `school_sign_up.html`: "Send OTP" button, OTP field (revealed after send / on error), and AJAX JS. Phone stays mandatory on both self-signup forms. (Admin onboarding left as-is — OTP impractical when an admin enters someone else's number.)
- Settings: `SMS_API_KEY/ENTITY_ID/OTP_TEMPLATE_ID/SENDER/API_URL` + `OTP_EXPIRY_SECONDS` from env. Sender `ENLRNG`, entity `1701159084703702132`, DLT OTP template `1777178593352822435` (registered + approved on SmartPing DLT).
- Verified: real SMS delivered to 2 test numbers; local end-to-end (wrong/no OTP blocks account, correct OTP creates it) for both student & school; production send-OTP endpoint returns success (real OTP delivered from Railway). Env vars set on Railway main IFT + local `.env`.

## 2026-08-03 — Fix payments that succeed on Razorpay but never record on our side
- **Reported case:** rituforai@gmail.com's own screenshot showed "₹1,600.00 Paid Successfully" (Payment Id `pay_TK4KQB7OQD53qx`, UPI, 31 Jul 2026 15:29:19 IST) but the admin panel showed NON-PAID.
- **Root cause:** `students/views.py:verify_payment` was the *only* path that ever marked a student paid, and it only runs if the client-side Razorpay JS `handler` callback fires and completes a `fetch()` to our server. With Razorpay's UPI intent flow (pay in a UPI app, then return to the browser), it's common for the payment to capture successfully on Razorpay's side while the browser tab is backgrounded/closed/drops network before that callback completes — payment succeeds, our DB never hears about it. No server-side webhook existed at all.
- **Durable fix:** added `students/views.py:razorpay_webhook` (`POST /payment/webhook/`, CSRF-exempt) — Razorpay calls this directly on `payment.captured`/`order.paid` regardless of what the browser does. Verifies `X-Razorpay-Signature` via `RAZORPAY_WEBHOOK_SECRET` (new setting; skips verification with a logged warning if unset, so it doesn't hard-fail before the webhook is configured in Razorpay's dashboard). Looks up the `Student` by `razorpay_order_id` (already stored at `initiate_payment` time), marks paid, sends the same confirmation email/notification as the existing client-side path. Idempotent — a repeat webhook call for an already-paid student is a no-op. **Still needs**: `RAZORPAY_WEBHOOK_SECRET` set in Railway env, and the webhook URL registered in Razorpay's dashboard — that's on the user.
- **Immediate reconciliation tool:** added `admins/views.py:mark_student_paid` (`POST /super-admin/user-management/student/<id>/mark-paid/`) + a "Mark as Paid" button in the Student Details sidebar's Payment section (only shown when unpaid) — prompts for the Razorpay payment ID as a paper trail (required) and optional amount, sets `is_paid`/`payment_transaction_id`/`payment_amount`/`paid_at` directly. This exists because I have no way to reach production's Postgres from here (`postgres.railway.internal` only resolves inside Railway's network) to fix Ritu's row myself — this lets the user (or any admin) fix it and any future mismatches from the UI, without needing direct DB access.
- Verified both via test client: webhook correctly finds the student by order_id, marks paid, sends email, and is idempotent on a second identical call; mark-paid endpoint validates the required transaction ID, sets all fields correctly, rejects a blank ID with a clear error.

## 2026-08-03 — Fixed stacked action-icons in 4 admin list tables + 2 new emails
- **List table alignment**: `.btn-icon-action` used `display:flex` (block-level) in `students_list.html`, `evaluators_list.html`, `evaluator_management.html`, `all_submissions_v3.html` — with multiple sibling buttons in a cell, each rendered as its own block, so the row-action icons stacked vertically instead of sitting in a row. `schools_list.html` already had it right (`inline-flex`). Fixed all 4 to `inline-flex`. Verified in-browser: icons now render side-by-side on Students and Evaluators lists.
- **New milestone emails**:
  - `hall_of_fame` ("Claim Your Pitch Ticket! You're Officially A Part Of IFT's Hall Of Fame") — fires automatically alongside `top12` whenever an admin flips `is_top_12` True in Django admin (same event: 2-day Bootcamp + Grand Finale). Assumption: client confirmed this is a *separate* email from Top 12, not a replacement.
  - `teacher_mentorship` — weekly broadcast to ALL active schools, every Wednesday, from 2026-08-07 to 2026-09-25 (the window around the Friday mentorship sessions). New `admins.RecurringEmailLog` model (school, email_key, sent_date) dedupes by calendar day so a same-day double-run of the cron never double-sends, but it correctly re-fires every subsequent Wednesday. Wired into the existing `send_scheduled_emails` daily cron command (same Railway cron-job setup note applies).
  - Verified: Top12+HallOfFame both fire once on flag flip, no dupe on re-save; weekly broadcast fires 0 on non-Wednesday/out-of-window, fires for all active schools on in-window Wednesdays, 0 on same-day re-run, fires again next Wednesday.
- **Non-paid label → "Unpaid"**: students list badge and dashboard KPI both said "Non-paid"; changed to "Unpaid" for consistent wording (the sidebar payment-detail badge already said "Unpaid").
- **Submissions page stat cards uneven height**: `.stat-card` had no `height:100%`, so a card with a wrapping label (e.g. "Under Review") stretched taller than its siblings even though the Bootstrap row stretches the column divs evenly. Added `height:100%` to `.stat-card`.
- **Global button underline removal**: added `button, .btn, a[class*="btn"], input[type="button"], input[type="submit"] { text-decoration: none; }` to every template's inline `<style>` block (76 files, no shared base across admin/student pages) plus `static/css/style.css` for the marketing site. Verified via computed-style check in-browser: 0 violations across all button-like elements on a sample page.

## 2026-08-03 — "Tata ClassEdge | ENpower Initiative" header banner (all roles)
- Added a dismissible purple gradient banner ("**Tata ClassEdge** | **ENpower** Initiative", X to close) into the `<header class="top-header">` of every dashboard page across all 4 roles: student (1 shared partial `templates/students/partials/header.html` — covers all 16 pages that include it), school (11 own-header pages), evaluator (5 own-header pages), admin (26 own-header pages, incl. content/digital_resources/halloffame/user_management subfolders). 43 files total, inserted via a script matching the `<header class="top-header">` anchor (verified exactly 1 occurrence per file first).
- Self-contained per insertion (inline `<style>`/`<script>` right next to the markup — these files have no shared CSS/JS to hook into): dismiss sets `localStorage.ift_banner_dismissed=1`, and a small inline script hides it on future loads. Two school pages (`school_halloffame.html`, `school_payments.html`) have no top-header at all and were skipped.
- Verified: `manage.py check` clean; visually confirmed in-browser on admin (Analytics Command Center — matches the reference screenshot exactly), school, and evaluator dashboards; dismiss + persistence-across-reload confirmed via localStorage check.

### 2026-08-03 follow-up: made permanent, reordered, weight fix
- Removed the dismiss (X) button and its localStorage/JS entirely — banner is now always shown, no way to hide it, per client request.
- Fixed ordering: banner was accidentally inserted BEFORE the hamburger/sidebar-toggle icon; swapped so hamburger comes first, banner after (matches the original reference screenshot: [hamburger][banner][bell][avatar]).
- `.ift-branding-banner strong` font-weight 800 → 600.
- `templates/admins/schedule.html` uses a different mobile-only hamburger pattern (`onclick` toggle, no shared `id="sidebarToggleBtn"`) — fixed by hand; the other 42 files were fixed via a script matching+reordering the two blocks.
- Re-verified: `manage.py check` clean, 0 leftover dismiss references, 43/43 files at font-weight 600; visually confirmed correct order on student and admin dashboards.

## 2026-08-02 — Students CSV export (Schools already had one) — re-added after conflicting removal
- Checked both list pages per request: **Schools** already had a real working export (`export_schools_csv`, wired to a genuine URL). **Students** only had a JS placeholder button (`onclick="exportCSV()"` → `alert('CSV export feature coming soon.')`) — no backend endpoint existed.
- Added `admins/views.py:export_students_csv`, mirroring `export_schools_csv`'s pattern: honors the same search/school/grade filters as `students_list`, one row per student (id, name, email, phone, school, grade, division, roll number, academic year, board, stream, gender, DOB, nationality, parent contact, address, payment status, submission count, account status, joined date).
- Wired at `user-management/students/export/`. Replaced the placeholder button with a real link carrying the current filters as query params (same UX as Schools' export link). Removed the now-dead `exportCSV()` JS placeholder.
- Verified via test client: 200, correct `Content-Type: text/csv` and `Content-Disposition` filename, correct header row. Confirmed in-browser the button renders as a real filtered link, not a JS handler.
- **Conflict note:** while pushing, discovered a teammate (Prasad) had concurrently pushed a commit removing Export CSV from both list pages entirely, reasoning that export belongs on the Reports page instead. Investigated: the Reports page's "Export" is `window.print()` on an aggregate analytics dashboard — not a real per-row CSV. Flagged to the user; explicit decision was to keep this real export and override the removal. Re-applied the Students export button (this entry); Schools' export button was similarly restored on rebase.

## 2026-08-01 — Google Tag Manager added site-wide (same pattern as GA4)
- Added `GoogleTagManagerMiddleware` to `ift_platform/middleware.py`, mirroring the existing `GoogleAnalyticsMiddleware` approach (site has no shared base template, so middleware is the only way to cover every page in one place). Injects the GTM head script (`GTM-PF4TLHG6`) right after `<head>`, and the noscript iframe right after the opening `<body>` tag, on every HTML response.
- Registered in `MIDDLEWARE` in `ift_platform/settings.py`, right after `GoogleAnalyticsMiddleware`.
- Verified via test client on multiple page types (landing page, sign-in, school sign-up): both snippets present, correct order (head script before body content, noscript iframe right after `<body>`), GA4 unaffected.

## 2026-08-01 — Storage: replaced Wasabi-specific backend with generic django-storages default
- Per request, removed the Wasabi-branded `admins/storage_backends.py` (custom `get_resource_storage()` scoped only to `DigitalResource.file`) and replaced it with a standard django-storages `S3Boto3Storage` configured as the **site-wide default** (`STORAGES['default']`), using conventional `AWS_ACCESS_KEY_ID`/`AWS_SECRET_ACCESS_KEY`/`AWS_STORAGE_BUCKET_NAME`/`AWS_S3_ENDPOINT_URL`/`AWS_S3_REGION_NAME` env vars. Falls back to local disk (`FileSystemStorage`) when those aren't set, same as before.
- This is broader than the original scope: it now also fixes the durability problem for the *pre-existing* uploads (Student photos, submission files, Hall of Fame photos), not just Digital Resources — those were already on ephemeral local disk before today's Digital Resources feature existed.
- Still S3-compatible-provider-agnostic: pointing `AWS_S3_ENDPOINT_URL` at Wasabi's endpoint (or leaving it unset for real AWS S3) both work with the same code.
- `DigitalResource.file` no longer pins a specific storage — uses whatever `default_storage` resolves to. Edited the just-applied migration `0011_digitalresource` in place to drop the now-removed storage reference (safe: FileField storage is Python-side metadata, not part of the DB schema, so this doesn't require a new migration or affect already-applied state).
- Re-verified end-to-end: upload → correct storage class resolved (FileSystemStorage locally, no AWS creds set) → student page shows it. Cleaned up test data.

## 2026-08-01 — Digital Resources: downloadable collaterals for Students/Schools + admin CRUD + Wasabi storage
- **Checked for existing Wasabi/S3 setup — none existed.** All uploads (Student.photo, submission files, Hall of Fame photos) were on local `FileSystemStorage`, which doesn't persist across Railway deploys/restarts. Added `boto3` + `django-storages` and a lazy `admins/storage_backends.py:get_resource_storage()` that uses Wasabi (S3-compatible) when `WASABI_ACCESS_KEY`/`WASABI_SECRET_KEY` env vars are set, falling back to local disk otherwise (so it works today without real Wasabi credentials, and picks them up automatically once configured). New settings: `WASABI_ACCESS_KEY/SECRET_KEY/BUCKET_NAME/ENDPOINT_URL/REGION`. Only applied to the new feature's FileField — didn't touch existing upload paths.
- **New `DigitalResource` model** (`admins/models.py`, migration `0011_digitalresource`): title, category (WhatsApp Template/Flyer/Brochure/Standee/Banner/BMC/Pitch Template/Other), description, file, visibility (all/students/schools), is_active, uploaded_by, created_at.
- **Admin CRUD**: list (`/super-admin/digital-resources/`, search + category filter, stats), upload, edit (metadata + optional file replace), delete (also deletes the underlying file), toggle active/inactive. New templates under `templates/admins/digital_resources/`.
- **Student-facing page** (`/digital-resources/`, `templates/students/digital_resources.html`) and **School-facing page** (`/school/digital-resources/`, `templates/students/school_digital_resources.html`) — both grouped by category, download links, filtered by visibility server-side. Added "Digital Resources" nav item to the student sidebar partial and to all 10 school-portal templates that have the inline sidebar (bulk-inserted via script for 8, hand-fixed 2 with differing HTML formatting).
- Verified end-to-end via test client: uploaded 3 resources (students-only, schools-only, all), confirmed each visibility filter works correctly on both student and school pages, confirmed edit/toggle-status(hides when inactive)/delete all work. Verified visually in-browser (admin list + student page) — branding, grouping, and download links all correct.

## 2026-08-01 — 3 of 6 outstanding issues fixed: grade dropdown, reset-password wording, student bulk actions
- **Grade dropdown consistency**: `accounts/forms.py:StudentSignUpForm` (self sign-up) and `templates/admins/user_management/onboard_student.html` (admin onboarding) both started at Class 6; changed to start at 7, matching the earlier profile-page fix.
- **Password-reset email wording**: the CRUD "Reset Password" actions (added earlier today) were reusing `send_onboard_credentials`, so the email said "your account has been created" even on a pure password reset. Added `accounts/emails.py:send_password_reset_by_admin` + new template `templates/accounts/email_password_reset_by_admin.html` (extends the shared base, overrides greeting/intro only) with correct copy: "Your password ... was just reset by an administrator." Wired into `reset_student_password`/`reset_school_password`. Verified subject line and body via test client.
- **Bulk actions for Students list**: added the same bulk-select pattern Schools already had — row checkboxes, "select all", and a bulk action bar (Activate/Deactivate/Delete Selected). New endpoints `bulk_toggle_student_status` (flips `User.is_active`) and `bulk_delete_students` (deletes the Users, cascades to Student profiles). Verified via test client: bulk-deactivated 2 students, then bulk-deleted both.
- **Production 500 (issue from earlier)**: confirmed resolved — checked Railway HTTP logs for the current live deployment (`d5ce39e`), zero 5xx responses in the last 12h.
- **Still blocked** (need user input, not fixable from code): the duplicate-schools production report (needs a way to query the production Postgres DB — internal hostname only resolves inside Railway's network, and reading DB credentials via Railway MCP was blocked by the permission system) and sending real test emails via ZeptoMail (needs the actual `ZEPTOMAIL_API_KEY`, which is set in Railway's production env but reading it was likewise blocked).

## 2026-08-01 — Full CRUD for Schools and Students (edit/delete/reset password)
- **Student**: added `edit_student` (new `templates/admins/user_management/edit_student.html`, scaffolded from `edit_school.html` — Personal/Academic/Contact sections, school reassignment dropdown, AJAX submit + toast), `delete_student` (deletes the linked `User`, which cascades to the `Student` profile via the OneToOne `CASCADE` FK), and `reset_student_password` (generates a token, emails via the existing `send_onboard_credentials` helper).
- **School**: added `delete_school` (deletes the School and its linked login `User` if any; students keep their `school_name` text but lose the FK per `SET_NULL`, matching existing behavior) and `reset_school_password`.
- Wired 6 new URLs under `user-management/` in `admins/urls.py`; added Edit/Reset-Password/Delete icon buttons to both `schools_list.html` and `students_list.html` row actions (students_list.html didn't have a toast system yet — added the same CSS/JS pattern used in schools_list.html).
- Verified full cycle via Django test client for both School and Student: create → edit (confirmed field changes persist, including the `edit_school` contact_email/phone fix from earlier today) → reset password (email sent) → delete (row and login both gone). Also confirmed in-browser: edit form pre-fills correctly, all action icons present and correctly linked on both list pages.

## 2026-08-01 — School-side Learning Resources also had the stale hardcoded videos
- Same bug as the student-facing page (fixed earlier today), but on the School Admin portal: `students/views.py:school_learning_resources` rendered `school_learning_resources.html`'s hardcoded 8-module grid instead of real `LearningVideo` rows — so videos added via the admin panel never appeared here. Now passes real `learning_videos` queryset; template loops over it instead of the fixed module list. Verified via test client: old "Module 1" text gone, real seeded session title present.

## 2026-08-01 — Fix Announcements badge/list mismatch; grade dropdown starts at 7
- **Notifications page**: the "Announcements" tab badge counted *all* published `Content` (FAQs, trainings, announcements alike) via `content_count`, but the actual filtered list only shows items where `content_type == 'announcement'` — so the badge could say "10" while the list showed nothing (all 10 were FAQs/trainings). `students/views.py:notifications_page` now computes `announcement_content_count` from only announcement-type content for that badge. Verified via test client: seeded 1 training + 1 FAQ + 1 announcement, badge now correctly shows 1 instead of 3.
- **Student profile grade dropdown** (`templates/students/profile.html`) started at Grade 1; changed to start at Grade 7 per request (loop `"123456789"` → `"789"`, keeping 10/11/12 as before).

## 2026-08-01 — Student Details sidebar: added Payment/Transaction section
- Admin panel's Student Details sidebar (`templates/admins/user_management/students_list.html`) had no visibility into payment status — only Personal/Academic/Contact/Activity. Added `data-is-paid`, `data-payment-amount`, `data-payment-txn`, `data-razorpay-order`, `data-paid-at` attributes to each row and a new "Payment" section in the sidebar (status badge Paid/Unpaid, amount, transaction ID, Razorpay order ID, paid-at timestamp).
- Verified via test client (payment data renders correctly in row attributes) and in-browser (sidebar shows STATUS: PAID, AMOUNT: ₹25.00, TRANSACTION ID: COUPON-IFT99OFF, PAID AT timestamp for a test student).

## 2026-08-01 — Learning Resources page wired to real video data; 99%-off coupon re-added
- **Learning Resources page was stale**: `students/views.py:learning_resources` rendered a hardcoded 8-module grid with fixed YouTube IDs, completely disconnected from the `LearningVideo`/`VideoProgress` models the Dashboard already uses (which now has 11 real sessions with per-student watched tracking). Rewired the view to build the same `learning_videos`/`videos_total`/`videos_watched` context as `dashboard()`, and replaced the template's hardcoded grid with a `{% for %}` loop mirroring the dashboard's card markup (thumbnail, watched checkmark, `markVideoWatched()` JS call to `/video/<id>/watched/`). Verified in-browser: page now shows the same session list/count as the dashboard.
- **Re-added a coupon code to the payment page** (`students/views.py:initiate_payment`, `templates/students/payment.html`) — a similar `IFTFREE2026` bypass coupon existed before but was deliberately removed on 2026-07-29 to close a gap around the real payment gate. Re-added per explicit request, with a new code `IFT99OFF` giving 99% off (records `payment_amount` as 1% of the fee, e.g. ₹25 of ₹2500) rather than a full bypass. Confirmed via test client: valid code marks the student paid at the discounted amount; invalid codes show an error and fall through to the normal Razorpay flow.

## 2026-08-01 — Fix infinite redirect loop for orphaned school-role logins
- **Live production bug**, reported as "too many redirects" on `/school/dashboard/`. Root cause: `accounts:role_redirect` → `students:school_dashboard` → (no linked `School` row, e.g. after a School record was deleted) → redirected back to `accounts:sign_in` → (still authenticated) → `role_redirect` → ... looped forever.
- `accounts/views.py:role_redirect` now checks `hasattr(request.user, 'school_profile')` before redirecting to the school dashboard; falls back to the student dashboard with an error message if missing. `students/views.py:school_dashboard` and `school_payments` also redirect to `students:dashboard` instead of `accounts:sign_in` on `School.DoesNotExist`, so neither path can loop back into `role_redirect`.
- Also fixed in passing: `admins/views.py:edit_school` was reading the wrong POST keys for contact email/phone (`school_email`/`school_phone` instead of `contact_email`/`contact_phone`), so those two fields silently never saved.
- Verified by reproducing the exact scenario (a 'school'-role user with no `School` row) via test client — resolved in 2 hops instead of looping.

## 2026-08-01 — Prevent duplicate school self-registration via Google Place ID
- **Problem:** the same physical school could register multiple times (e.g. "Adani DAV Public School" registered 3× with different coordinator emails) — `SchoolSignUpForm` only checked email uniqueness, never the school itself.
- Added `School.google_place_id` (`students/models.py`, migration `0025_school_google_place_id`, unique + nullable — existing rows have no value and multiple NULLs are allowed).
- `templates/accounts/school_sign_up.html` — the existing Google Places Autocomplete widget now also requests `place_id` and writes it into a new hidden `google_place_id` input on `place_changed`. If the user edits the school name after picking a suggestion, the hidden value is cleared (an edited name isn't guaranteed to still match that place).
- `accounts/forms.py:SchoolSignUpForm` — new hidden `google_place_id` field with `clean_google_place_id` rejecting registration if a School with that place_id already exists ("This school is already registered on IFT. Please sign in instead...").
- `accounts/views.py:school_sign_up` now saves `google_place_id` on the created School.
- Verified end-to-end via Django test client: first registration with a given place_id succeeds; second registration reusing the same place_id is blocked (200 re-render with the error, no User/School created).
- Note: this only prevents *new* duplicates going forward — the 3 existing "Adani DAV Public School" rows (and any other pre-existing dupes) are untouched; that needs a manual data-cleanup pass since merging would affect existing logins/student records.

## 2026-08-01 — Admin panel: school activate/deactivate (single + bulk)
- School model already had `is_active`/`status` (pending/inactive/active) fields, set on self-registration (`accounts/views.py:school_sign_up` creates schools as `status='pending', is_active=False`), but admins had no way to flip it — only the school itself could activate by completing its profile.
- Added `admins/views.py:toggle_school_status` (POST, per-school) and `bulk_toggle_school_status` (POST, list of IDs + `activate` flag), wired at `admins/urls.py` (`school/<id>/toggle-status/`, `schools/bulk-toggle-status/`).
- `templates/admins/user_management/schools_list.html` — added a toggle icon per row, row checkboxes + "select all", and a bulk action bar (Activate/Deactivate Selected) that appears once rows are checked. Added toast notifications (reused the `content_list.html` toast pattern) for success/failure instead of `alert()`/silent reload.
- Fix: removed the native `confirm()` on the single-row toggle — it was silently swallowing clicks with no visual feedback, which looked like the toggle "wasn't working."
- Verified: backend endpoints tested directly via Django test client (single toggle flips is_active/status correctly; bulk toggle activated then deactivated 2 schools, correct JSON + DB state each time).

## 2026-07-29 — TCE school validation working in production (Cloud Run Mumbai proxy)
- **Goal:** Real-time TCE (Tata ClassEdge) partner detection during school registration → ₹1600 (TCE) vs ₹2500. Must be fully API-driven, no manual DB edits.
- **Root cause (diagnosed):** TCE API (`ce-ift.tataclassedge.com/schoolcheck/api/v1/school/validate`) is reachable only from **Indian IPs**. Railway runs in Singapore (egress `34.21.177.21`, GCP) → ConnectTimeout. Cloudflare Worker proxy also failed: for Railway-originated requests the Worker runs at the SIN colo (proven via `request.cf.colo="SIN"` diagnostic), and Smart Placement won't relocate to India (the failing subrequest gives it no latency signal; no way to pin a colo). Note: `railway run curl` misleadingly "worked" because it executes on the local India PC, not the Railway cloud.
- **Fix:** Flask proxy on **Google Cloud Run, asia-south1 (Mumbai)** — India egress reaches TCE in ~1s. Confirmed India *datacenter* IPs are allowed (not residential-only).
  - Proxy source: `C:\Users\kunal\Desktop\tce-proxy-gcp\` (`main.py` Flask + `Dockerfile` + `requirements.txt`).
  - Deployed to GCP project `ift-platform-499910` (account `enpowerlab.ai@gmail.com`, billing linked `0110FF-5060A4-87B695`). Enabled run/cloudbuild/artifactregistry APIs. URL: `https://tce-proxy-222521293721.asia-south1.run.app`. Auth header `X-Proxy-Secret`.
  - `accounts/views.py:school_sign_up` — rewrote TCE block to POST to the proxy (`TCE_PROXY_URL`) with `X-Proxy-Secret`, 20s timeout; dropped the always-failing direct attempt. Sets `School.is_tata_classedge` from `is_tce_school`.
  - `Procfile` — gunicorn `--timeout 60`.
  - Railway env var `TCE_PROXY_URL` set to the Cloud Run URL (`TCE_PROXY_SECRET`/`TCE_API_*` already present).
- **Verified end-to-end:** production registration of a TCE partner school → log `Proxy: status=200 is_tce_school:true`, DB `is_tata_classedge=t`, ~3.7s response.
- **Cleanup:** deleted 5 debug test schools + their users/notifications from prod DB; deleted the obsolete Cloudflare Worker `tce-proxy` (its every-minute cron was needlessly pinging TCE).
- Commits pushed to `techinfinity/main`: `5be3494` (Mumbai proxy), plus timeout/diagnostic commits `81772fb`, `5ad1c6c`, `abbc105`.

## 2026-07-29 — Learning videos made OPTIONAL + notification badge fix
- **Videos no longer mandatory** for students (leader or members). Removed the blocking "Complete Mandatory Videos" popup from `templates/students/submit_idea_v2.html` (the whole `{% if not all_videos_done %}` overlay block). Idea submission was never blocked server-side, so only the UI gate existed.
- `students/views.py`: `_learning_progress()` and `video_completion_status()` no longer filter on `is_mandatory` — they count all active videos and are now purely informational.
- `templates/students/dashboard_v2.html`: removed the "Complete all mandatory videos before submitting your idea" warning banner, renamed the section to "Learning Videos", and the per-video badge now reads "Optional".
- `LearningVideo.is_mandatory` field left in place (default True) but is no longer used for any gating — legacy/cosmetic only. No migration needed.
- Verified (seeded 8 videos, student with 0 watched): submit page 200 with no popup and a usable form; dashboard shows videos with "Optional" label and no nag banner.
- **Notification bell badge**: "Mark all as read" cleared the DB but the server-rendered header badge (`.notif-badge-dot`, pulsing) stayed until a page reload. Added `clearHeaderBadge()` / `decrementHeaderBadge()` in `templates/students/notifications.html` and wired them into the mark-all and per-notification handlers. Backend was already correct (marks notifications read + sets `announcements_read_at`). Verified in-browser: badge 3 → removed instantly without reload, and stays gone after refresh.

## 2026-07-28 — Branded HTML password reset email
- Split `templates/accounts/password_reset_email.html` into a plain-text fallback (`password_reset_email.txt`) and a new branded HTML version (`password_reset_email_html.html`, same purple/gold header + logo + CTA button style as the onboarding emails).
- `accounts/views.py:ForgotPasswordView` now sets `html_email_template_name` (Django's `PasswordResetForm` sends both parts as multipart automatically) and injects `logo_url` via `extra_email_context`/`get_extra_email_context` + `form_valid` override.
- Verified: test-client POST to `/accounts/forgot-password/` produced correct multipart output (plain + HTML) on console backend; HTML rendering visually confirmed in-browser via temporary preview route (added and removed same session). Test user cleaned up after.

## 2026-07-28 — All outgoing mail redirected to hemant@techinfinity.io (dev safety net)
- Added `accounts/email_backend.py:RedirectEmailBackend` — wraps whichever real backend is configured (`EMAIL_BACKEND_REAL`, console locally / ZeptoMail in prod) and rewrites every message's to/cc/bcc to `settings.EMAIL_REDIRECT_TO` before delegating, prefixing the subject with the original intended recipient(s) for traceability. Covers every send path project-wide (onboarding, certificates, password reset, landing inquiries) without touching individual call sites.
- `ift_platform/settings.py` — `EMAIL_BACKEND` now resolves to `RedirectEmailBackend` only when `EMAIL_REDIRECT_TO` is set in env; otherwise falls back to the real backend unchanged.
- `.env` — set `EMAIL_REDIRECT_TO=hemant@techinfinity.io`.
- Verified via shell: `send_mail` to `someoneelse@example.com` arrived addressed to `hemant@techinfinity.io` with subject prefixed `[to: someoneelse@example.com] ...`. Restarted dev server to pick up the setting.
- To turn off: remove/blank `EMAIL_REDIRECT_TO` in `.env`.

## 2026-07-28 — Onboarding emails: HTML templates + student onboarding wired
- Audited every event in the platform for existing/missing transactional emails (accounts, students, admins, ai_assistant, re_evaluation) — see chat history for full table; biggest gaps found: re_evaluation has zero applicant-facing email at any stage, and top 400/100/school-champion designation fires no notification.
- Wired the first gap: `admins/views.py:onboard_student` now sends a credentials email on student onboarding (previously silent), reusing `accounts/emails.py:send_onboard_credentials` (same helper already used for school/evaluator onboarding).
- Replaced the single generic plain-text onboarding template with branded HTML templates per role: `templates/accounts/email_onboard_{student,school,evaluator}.html`, all extending a shared `email_onboard_base.html` (purple/gold IFT branding, credentials box, CTA button). Plain-text `.txt` counterparts kept as the multipart fallback; old generic `email_onboard_credentials.txt` kept as last-resort fallback only.
- `send_onboard_credentials` now sends `EmailMultiAlternatives` (text + HTML) instead of plain `send_mail`; role-specific template resolution via `email_onboard_{role.lower()}.{html,txt}`.
- Verified: Django `check` clean; test-client onboarding POST renders correct subject/template/recipient on console backend; HTML rendering visually confirmed in-browser via a temporary preview route (added and removed same session) for student and evaluator variants.
- Note: `admins/views.py:onboard_school` still creates no `User` account (School record only) — no credentials to email there; separate gap if needed later.
- Added actual IFT crest logo to the email header (was text "ift" before). New asset `static/images/email_logo.png` (320x320, transparent bg, white-ribbon variant — legible on the dark purple header, sourced/resized from `static/landing/IFT Logo_revised-White.png`). `send_onboard_credentials` now passes an absolute `logo_url` (via `SITE_URL` + `staticfiles_storage.url(...)`) since email images must be absolute URLs, not relative static paths. Verified visually in-browser (temporary preview route, removed after).

## 2026-07-28 — Fresh clone: local dev environment setup
- Cloned repo to `/Users/hemantshah/Desktop/AI/Claude/IFT` (preserved pre-existing local `.claude/` dir).
- Created `venv` with Python 3.12.7 (matching `runtime.txt`; system default was 3.14.4) and installed `requirements.txt`.
- Created `.env` from provided project credentials (SECRET_KEY, OPENROUTER_API_KEY, Razorpay test keys, SQLite DB).
- Ran `python manage.py migrate` — all 5 apps' migrations applied cleanly to a fresh SQLite DB.
- Added `.claude/launch.json` (`ift-django` config, port 8000) and started the dev server via the browser preview tool; verified landing page renders correctly (200s on all static assets, screenshot confirmed).

## 2026-07-21 — Certificates: manual per-recipient send with name autocomplete
- Removed the **"Send to all pending"** bulk button from all 4 cards (client sends individually).
- Each card now has **"Send to a student/school"**: a name autocomplete input — type a partial name (e.g. "aar") → dropdown of eligible recipients (name + email, "Sent" tag if already sent) → select → **Send** (real, tracked). Preview kept.
- New views `admins/views.py`: `certificate_suggestions(cert_type)` (JSON, filters `_certificate_recipients` by name/email `?q=`, unsent-first) and `send_single_certificate` (POST cert_type+kind+entity_id → real `_send_certificate`, is_test=False). URLs `certificates/suggest/<cert_type>/` and `certificates/send-one/`. `send_certificates_batch` view left in place but no longer linked from UI.
- Also added a **"View"** action per Recent-activity row → opens that row's certificate PDF (`preview_certificate` with the row's name+type).
- Verified locally (console forced): suggest 'mee'→Meera(unsent)/'aar'→Aarav(sent); send-one creates 1 real row + sent-flag flips; invalid id guarded. Browser: autocomplete dropdown + select + Send-enable confirmed (screenshot).

## 2026-07-21 — Participation certificate: auto-send on submit
- **Participation** now emails **automatically** when a student publishes their idea (`students/views.py:publish_idea`). Other 3 types stay **manual** (per client: rankings vary, send on click).
- New helper `admins/views.py:send_participation_certificate(student, sent_by)` — background daemon thread, dedupes via CertificateIssue (one per student), swallows all errors so it never affects the submission. Reuses `_send_certificate`.
- Verified locally (console backend forced): 1st publish → 1 cert row (full name), 2nd call → 0 (dedupe). Note: on live (ZeptoMail env) this sends a REAL email on every new publish. Pre-existing submitted ideas won't auto-send (hook fires only on new publish) — use the manual batch button for those.

## 2026-07-21 — Certificate emailing feature (admin-triggered)

**Goal:** Email PDF certificates with each student's proper name (Dancing Script, black), triggered manually by super-admin.

**Delivered — all 4 flows:**
- Participation → student (submitted an idea)
- Top 400 → student (`AIEvaluation.is_top_400`)
- Top 100 → student (`rank <= 100`) **and** their school
- School Champion → school (one per school, school name; eligible = schools with a Top-100 student). Confirmed logic: Top 100 issues to student + school.

**Changes:**
- `admins/certificates.py` (new) — Pillow name overlay; CMYK→sRGB via ICC (colour-accurate); returns PDF bytes.
- `static/fonts/DancingScript.ttf` (new) — bundled font.
- `static/certificates/*.jpg` — 4 templates (participation, top100, top400, school-champion).
- `accounts/email_backend.py` — ZeptoMail attachment support (base64).
- `admins/models.py` + migration `0010` — `CertificateIssue` audit model.
- `admins/views.py` — `certificates_view`, `preview_certificate`, `send_test_certificate`, `send_certificates_batch`.
- `admins/urls.py` — 4 routes under `/super-admin/certificates/`.
- `templates/admins/certificates.html` (new) + "Certificates" nav link added to 21 admin sidebars.

**Verified (local, Django test client + console email backend):**
- Page renders 200; correct eligible/pending counts (participation 4, top100 1, top400 2, school_champion 1 on seed).
- All 4 preview endpoints return valid PDFs; ZeptoMail attachment payload base64-correct.
- school-champion PDF capped to ~0.46 MB (from 6.5 MB) via width cap; school name placement correct.
- Batch send emails all eligible + records CertificateIssue (student or school); re-run skips already-sent (dedupe by student/school).
- Admin UI screenshot confirmed (all 4 cards).

**Notes:** `top400.jpg` body text still says "School Champion" (client to confirm); nothing committed yet; LearningVideo/VideoProgress migration still out of scope.

---

## 2026-08-05 — Official India Zone/Region mapping for reports

**Why:** Reports "Zone" column used a guessed `_STATE_ZONES` dict in `admins/views.py` that was WRONG vs the client's authoritative `India_Zone_Region_State_City_Mapping.xlsx`. Mismatches fixed: UP/Uttarakhand = North (was Central), Lakshadweep = North (was South), Andaman & Nicobar = Central (was South), zone label `North-East` → `Northeast`.

**Changes:**
- `admins/zones.py` (new) — official baked-in mapping from the Excel: `STATE_ZONE` (36 states/UTs), `CITY_ZONE` (169 cities), each → (region, zone). Helpers `resolve_zone(state, city='')` / `resolve_region(...)`. STATE-FIRST, city fallback (avoids Udaipur Rajasthan/Tripura collision). Normalisation drops `(NCT)` etc.; `_STATE_ALIASES`/`_CITY_ALIASES` for old names (Orissa, Bangalore, Gurgaon, Pondicherry, …). Region == Zone in this dataset; `resolve_region` kept for a future Zonal Report.
- `admins/views.py` — removed hardcoded `_STATE_ZONES`; `_state_to_zone(state, city='')` now delegates to `zones.resolve_zone`; added `_submission_city(sub)`. Top-N CSV + students export + schools export now pass city for city-aware zone (column + zone filter).
- `templates/admins/reports.html` — Zone filter dropdown `North-East` → `Northeast` to match new label.

**Verified (local):**
- `manage.py check` clean.
- 18 assertions pass (UP→North, Uttarakhand→North, Maharashtra→West, Assam→Northeast, Kerala→South, Bihar→East, MP→Central, Lakshadweep→North, Andaman→Central; cities Gurugram→North, Indore→Central, Panaji→West; Delhi(NCT)→North; Rajasthan+Udaipur→North [state-first]; Bangalore alias→South; Pondicherry→South; junk→Unknown).
- Test client (temp superuser, deleted after): reports page 200, students/schools previews 200 (JSON), xlsx exports 200 (spreadsheet content-type), `?zone=northeast` filter 200.

**Notes:** No DB/migration change — pure data + helper, additive, zero break risk. All existing `_state_to_zone` callers keep working (signature preserved). Not committed yet.

---

## 2026-08-05 — Dashboard KPI cards clickable (drill-down to details)

**Why:** Super Admin dashboard KPI cards were static; client wanted to click a number and see the underlying records.

**Changes:**
- `templates/admins/admin_dashboard.html` — wrapped 11 of 12 KPI cards in `<a class="kpi-link">` to existing list pages: Total Participants/Students → students_list; Idea Submissions/Published → all_submissions; Pending → all_submissions?status=submitted; Unpublished → all_submissions?status=draft; Schools/Total Schools → schools_list; Evaluators → evaluators_list; Paid → students_list?paid=true; Unpaid → students_list?paid=false. Added `.kpi-link` CSS (invisible wrapper). **Total Teams** left non-clickable (no teams list page exists).
- `admins/views.py` `students_list` — added optional `?paid=true/false` filter (`is_paid`) + `selected_paid` context.

**Verified (local, temp superuser):** dashboard 200, 11 kpi-links present, all 8 destination URLs 200 (incl. new paid filter). `manage.py check` clean.

**Notes:** Additive only — no DB/model/migration change, existing pages/links unchanged. Zero break risk.

---

## 2026-08-05 — Fix: announcements not showing in evaluator bell (end-to-end audit)

**Reported:** Announcements "not working" — recipient bell should show announcements super admin targeted via visibility.

**End-to-end audit result:** Backend + create flow are CORRECT. `content_create` saves visibility/status; `accounts/context_processors.unread_notification_count` gates by `status='published'` and `visibility in ['all', <role>]` (jury→evaluators). Verified via simulation: published+targeted announcement appears; schools-only and draft correctly hidden.

**Actual bug:** The **evaluator dashboard bell was hardcoded** to "No new notifications" — `templates/students/evaluator_dashboard.html` never rendered `header_notifications_combined`/`unread_notification_count`, so evaluators never saw announcements targeted to "Evaluators Only" or "All Users". (Student & school bells were already wired via `students/partials/header.html` and `school_dashboard.html`.)

**Fix:** Wired the evaluator bell — badge count on the button + loop over `header_notifications_combined` with unread highlight and empty-state fallback. No view/model/context change (data was already provided to the page).

**Verified (local, temp jury user + announcements, cleaned up):** evaluator dashboard 200; evaluators-only + all-users announcements both render; badge shows; "No new notifications" gone. `manage.py check` clean.

**Note (out of scope, minor):** Super Admin's own dashboard bell button has no dropdown panel at all — but super admin is the *sender*, not a typical recipient. Left as-is.

---

## 2026-08-05 — Raise a Ticket / Support module (Phase 1)

**Feature:** Full support-ticket system. Students & Schools raise tickets ("Help" tab under FAQ); Super Admin manages (reply, assign, status, priority, resolve, reopen). Attachments via S3 (standard FileField), bell + email notifications.

**New app `support/`** (registered in INSTALLED_APPS):
- Models: `Ticket` (number `TKT-000001` auto via save-after-pk, category/priority/status/assigned_to/resolution_note/resolved_at), `TicketMessage` (thread, is_internal reserved for Phase 2), `TicketAttachment` (`FileField upload_to='tickets/%Y/%m/'`). Migration `0001_initial`.
- Views: user side `my_tickets`/`raise_ticket`/`ticket_detail` (owner-only); admin side `admin_tickets` (cards + student/school tabs + status/priority filters) / `admin_ticket_detail` (reply, status, priority, assign, resolve, reopen). Helpers: `_notify` (students.push.notify), `_email` (send_branded_email → new `templates/accounts/email_generic.html`), `is_staff_or_superuser`.

**URLs:** `students/urls.py` → `/help/`, `/help/raise/`, `/help/ticket/<id>/`. `admins/urls.py` → `/super-admin/tickets/`, `/super-admin/tickets/<id>/`.

**Templates:** `templates/support/{base_user,my_tickets,raise_ticket,ticket_detail}.html` (role-aware sidebar: student vs school, no change to originals), `templates/admins/tickets/{base_admin,list,detail}.html`.

**Sidebars:** "Help" nav added to `students/partials/sidebar.html` + `school_dashboard.html` (after FAQ). "Tickets" nav added to 24 admin sidebar templates (scripted insert after Reports) + reports.html manual.

**Notifications flow:** create → bell to all superadmins; user reply → bell to assignee/admins; admin reply → bell + email to user; resolve → bell + email w/ resolution note; reopen → back to admin queue.

**Verified (local, throwaway users, cleaned up):** raise→TKT-000001, admin bell, admin list+tabs, admin reply→auto in_progress+student bell, assign/priority/status, resolve→resolved+resolved_at+email(result=1)+note visible to user, user reopen→reopened, school ticket→creator_type=school in school tab, access control (student→admin tickets 302, other's ticket 404). All 7 auto-edited admin pages still render 200. `manage.py check` clean.

**Phase 2 (deferred):** SLA/overdue card, internal notes UI, merge duplicates, delete, rich-text, action timeline, configurable reopen window.

---

## 2026-08-05 — Raise a Ticket support module (Phase 2)

**Added on top of Phase 1:**
- **Models** (`support/models.py`, migration `0002`): `Ticket.merged_into` FK (duplicate merge); `TicketEvent` (action timeline: created/assigned/replied/status/priority/resolved/reopened/merged/note, with icon). SLA helpers: `SLA_HOURS` (urgent 8/high 24/medium 48/low 72), `sla_due_at`, `is_overdue`; `REOPEN_WINDOW_DAYS=7` enforced in `can_reopen`.
- **Admin detail** (`support/views.py` + `templates/admins/tickets/detail.html`): internal notes (`is_internal`, private form, hidden from user, distinct yellow style); merge duplicate (dropdown of same-user tickets → moves conversation+attachments, closes source, redirects to target); delete ticket (confirm); action **Timeline** panel; every action now logs a `TicketEvent`.
- **Admin list** (`list.html`): **Overdue (Beyond SLA)** card (clickable → `?overdue=1` filter) + per-row Overdue chip; merged tickets excluded from list/counts.
- **User reopen** now respects the 7-day window via `can_reopen`.

**Verified (local, throwaway users, cleaned up):** created→event logged; internal note added + user cannot see it; overdue detection (urgent 48h) + card + chip + filter; merge (t2→t1, closed, msgs moved, hidden); timeline renders; reopen window fresh=yes / 8-days=no; delete works. Browser UI check (student + admin, all pages) — internal note form, merge dropdown, timeline, delete, 8 KPI cards incl. Overdue all render. `manage.py check` clean.

**Still deferred:** rich-text editor (textareas keep line breaks via pre-wrap), SLA in true *working* hours (currently calendar hours).

---

## 2026-08-05 — New registrants don't see old announcements in the bell

**Why:** A newly registered student/school saw all past published announcements in their notification bell (broadcast `Content`, not scoped to join date; new user's `announcements_read_at` is None so all counted as unread).

**Fix:** `accounts/context_processors.py` `unread_notification_count` — floor the announcement queryset by `request.user.date_joined` (`content_qs.filter(created_at__gte=joined)`). Applies to both count and displayed list. One file, ~4 lines, no migration/registration change.

**Verified (local, throwaway users, cleaned up):** new student (joined after an announcement) → count 0, old announcement hidden; announcement posted after join → visible + counted; existing user (joined before announcements) → still sees all (no regression). `manage.py check` clean.

**Note:** Only broadcast `Content` announcements are floored; per-user Notifications (ticket replies etc.) unaffected. First test run showed a false negative purely from a test-timing artifact (artificial date_joined vs real-time created_at); re-test with explicit timestamps passed all cases.

---

## 2026-08-05 — IFTx Highlights module (new tab, above FAQ in School Dashboard)

**Feature (item 1 of the big request):** Schools/teachers upload IFTx event photos/videos/PPT/PDF/doc + summary + event date + participating students; super admin reviews/tracks with filters + Excel dump. Media on S3 (standard FileField).

**New app `highlights/`** (registered in INSTALLED_APPS, migration `0001`):
- Models: `IFTxHighlight` (school FK, created_by, title, event_date, summary, is_reviewed/reviewed_at), `HighlightMedia` (file `upload_to=iftx_highlights/%Y/%m/`, media_type, size_bytes), `HighlightParticipant` (student_name, grade). `MAX_MB` + `EXT_TYPE` maps drive per-type size limits.
- Size limits enforced in upload view: video 250MB, PPT/PDF 25MB, images/docs 5MB (oversized/unsupported skipped with a message).
- School views (`highlights/views.py`): `my_highlights`, `upload_highlight` (media + participant rows), `highlight_detail` (view + add media). Routes in `students/urls.py` `/iftx-highlights/*`.
- Admin views: `admin_highlights` (KPI + filters: school, media type, event date range), `admin_highlight_detail` (media, participants, mark reviewed toggle), `admin_highlights_export` (Excel "dump" via admins.reports.xlsx_response). Routes in `admins/urls.py` `/super-admin/highlights/*`.
- Templates: `templates/highlights/{base_school,my_highlights,upload_highlight,highlight_detail}.html`, `templates/admins/highlights/{base_admin,list,detail}.html`.
- Nav: "IFTx Highlights" added ABOVE FAQ in school sidebar (school_dashboard.html + support/base_user.html school branch); "IFTx Highlights" added to 24 admin sidebar templates (scripted after Tickets) + tickets/base_admin.html manual.

**Verified:** `manage.py check` clean. School e2e: list/upload/detail 200, upload creates highlight w/ media+participants+event_date, oversized doc rejected. Admin e2e: list 200, filters (school/media/date) correct, detail 200, mark-reviewed works, Excel dump 200 xlsx, school blocked from admin (302). All 10 existing admin pages still render 200 (nav insert safe). Browser UI check: school IFTx Highlights list + upload form + admin list all render cleanly with correct nav placement.

**Zero break:** brand-new isolated app; only additive nav lines touch existing templates.

**Still pending (next):** School Resources tab under Digital Resources; teacher video-seen tracking; Top-400 re-edit. Blocked: Zonal Report (Pinky→Hemant), Lock teacher RSS (Sushil Sir).

---

## 2026-08-05 — Ticket watcher emails (rayaan@ + pinky@ get every event)

**Why:** Two internal addresses must receive a full email for every support-ticket event.

**Changes:**
- `ift_platform/settings.py` — `TICKET_NOTIFY_EMAILS = ['rayaan@enlearning.in','pinky@enlearning.in']` (env `TICKET_NOTIFY_EMAILS` overridable).
- `support/views.py` — new `_notify_watchers(ticket, event_label, detail)` (branded ZeptoMail to the list, full ticket snapshot: number/subject/category/priority/status/raised-by/assignee + event detail + admin link; try/except fail-safe). Called on: create, user reply, user reopen, admin reply, internal note (included per client), status, priority, assign, resolve, admin reopen, merge.

**Verified (locmem outbox, throwaway users, cleaned up):** all 9 events send an email to BOTH watchers with the ticket number in the body; owner's existing emails unchanged; `manage.py check` clean. Additive only — no model/migration/template change.

---

## 2026-08-06 — Registration page images + badge unlock = total registrations

- **Registration images:** `Student registration.jpeg` → `/sign-up` and `School registration.jpeg` → `/school-sign-up`, shown via the auth `left_image` block (`static/images/auth/{student,school}-registration.jpg`; `templates/accounts/sign_up.html` + `school_sign_up.html`, added `{% load static %}`). Verified both load 200.
- **Badge unlock fix:** per the registration-milestones image ("20/30/40+ Student Registrations → Silver/Gold/Excellence"), changed school badge metric from `paid_count` → `student_count` (total registrations) in `students/views.py` school_dashboard; updated `school_dashboard.html` labels "registered & paid" → "student registrations". Thresholds/names already matched (20/30/40, Silver/Gold/Excellence Trophy).
