# IFT Platform — Changes Log (28 Jul 2026)

All work done in this session, grouped by feature. Every change is additive and
non-breaking; existing flows were preserved and each fix was tested.

---

## 1. Email Standardization

**Goal:** Every transactional email uses ONE branded template; only the dynamic
content changes.

### What changed
- Refactored `templates/accounts/email_onboard_base.html` into a reusable base
  with overridable blocks: `greeting`, `intro`, `credentials`, `content`,
  `button`, `button_href`, `button_label`, `security_note`, `footer`.
- Added helper `send_branded_email(subject, to, template, context, attachments)`
  in `accounts/emails.py` — views no longer inline HTML.
- Migrated these emails to extend the base:

| Email | Template |
|-------|----------|
| Student welcome (signup) | `accounts/email_welcome_student.html` |
| Idea published | `students/email_idea_published.html` |
| Payment success (+ details box) | `students/email_payment_success.html` |
| Payment failed | `students/email_payment_failed.html` |
| Certificate (+ PDF attach) | `admins/email_certificate.html` |
| Password reset | `accounts/password_reset_email_html.html` (now extends base) |

- Certificate `EMAIL_COPY` (in `admins/certificates.py`) restructured into
  `heading` + core `body` so the template's attach note / footer no longer
  duplicate the sign-off.
- **Kept as-is (by request):** the two landing inquiry emails ("Bring IFT to my
  School", "Partner with IFT") on their original `_email_wrapper`.

### Greeting tweak
- Removed the comma after the greeting name across all templates:
  "Welcome, Aarav!" → "Welcome Aarav!" (welcome, onboarding, idea published,
  payment success, certificate).

**Commits:** `Unify all transactional emails…`, `Drop comma after greeting…`

---

## 2. Student Portal Fixes (from the "Student" doc tab)

### #5 — Team members couldn't see the progress list
- **Cause:** members got a separate page (`member_idea_view.html`) that never
  had the modules / "Team Members Progress" section.
- **Fix:** new shared helper `_learning_progress()` in `students/views.py`; the
  member page now renders the IFT modules checklist + Team Members Progress.

### #6 — Bell badge stayed lit (22) after "Mark all as read"
- **Cause:** `mark_all_read` only marked `Notification` rows; the badge also
  counted all published announcements (`Content`), which have no read state.
- **Fix:** added `UserProfile.announcements_read_at`; the badge now counts only
  announcements created after that time, and "Mark all as read" sets it.
- Files: `accounts/models.py`, `accounts/context_processors.py`,
  `students/views.py`.

### #7 — Profile photo upload didn't work
- **Cause:** no photo field, no upload input, no handling.
- **Fix:** `Student.photo` ImageField; upload handled in `student_profile`
  (JPG/PNG/WEBP, max 5 MB); avatar shows photo or initial fallback.
- Files: `students/models.py`, `students/views.py`, `templates/students/profile.html`.

### #8 — Couldn't approve a single question's suggestion
- **Cause:** "Approve & Merge" applied ALL suggested changes at once.
- **Fix:** `apply_changes(only_fields=…)`; `handle_suggestion` accepts a `fields`
  list. Per-question checkboxes + "Approve Selected" (plus "Approve All").
  Unselected changes stay pending (non-destructive).
- Files: `students/models.py`, `students/views.py`,
  `templates/students/review_suggestions.html`.

### #9 — Modal Like / Bookmark / Share buttons dead
- **Fix:** Like + Bookmark now persist (see #12); Share copies the idea link
  (native share sheet where available).

### #10 — "Team Members" count showed 0
- **Cause:** used the legacy `TeamMember` model.
- **Fix:** counts now use `Team`/`TeamMembership`, including pending invites.

### #11 — "Ideas Submitted" / "Team Members" not reflecting
- **Fix:** profile counts use the current team system; "Ideas Submitted" = the
  team's submitted ideas.

### #12 — Likes always showed 0
- **Cause:** likes had no backend; `data-likes="0"` was hardcoded.
- **Fix:** `IdeaLike` model + `POST /idea/<id>/like/`; real counts and per-user
  filled hearts on Idea Corner cards and the detail modal.
- Bonus: `IdeaBookmark` model + `POST /idea/<id>/bookmark/` for persistent
  bookmarks.

**Migrations:** `students 0021_idealike`, `0022_ideabookmark`, `0023_student_photo`,
`accounts 0005_userprofile_announcements_read_at`.

**Commit:** `Student portal fixes: likes, bookmarks, photo, counts, notifications`

---

## 3. Notifications for Every Email (In-app + Web Push)

**Goal:** whenever an email is sent, the user also gets a notification — a bell
alert in-app and a real phone/desktop pop-up (like an email notification).

### Phase 1 — In-app notification on every email
- Central helper `notify()` in `students/push.py`: creates a `Notification`
  AND fires a web push, all wrapped in `try/except`.
- `create_notification()` now delegates to `notify()`, so every existing
  notification also pushes.
- New notification points: welcome, onboarding (school/student/evaluator),
  payment failed, certificate (idea published + payment success already had one).

### Phase 2 — Web Push (works when the site is closed)
- `PushSubscription` model + `POST /push/subscribe/` endpoint.
- Service worker `static/js/push-sw.js` (push + notificationclick).
- `templates/partials/push_notifications.html` — registers the SW, asks
  permission on first interaction, subscribes; included in the student header.
- `pywebpush` dependency + VAPID keys read from env in `settings.py`.
- Coverage: Desktop + Android Chrome fully; **iPhone only after the site is
  installed as a PWA** ("Add to Home Screen") — an Apple limitation, not a code
  issue. Native app-style push (Gmail) would require a mobile app.

### Safety
- All push/notification code is best-effort and `try/except`-wrapped — email
  sending and page rendering are never affected.
- `pywebpush` import is guarded; if VAPID keys are unset, push is silently
  disabled (no errors), leaving in-app notifications working.

**Commit:** `Add notifications for every email: in-app + Web Push`

### ⚠️ Production deploy steps (required for push on Railway)
1. Set these environment variables in Railway → Variables:
   - `VAPID_PUBLIC_KEY`
   - `VAPID_PRIVATE_KEY`  *(secret — never commit or share publicly)*
   - `VAPID_ADMIN_EMAIL`
   (Values are in the local `.env`, which is gitignored.)
2. Deploy runs `pip install` (`pywebpush` is in `requirements.txt`) and
   `collectstatic` (serves the service worker) — part of the normal flow.
3. Web Push requires HTTPS — production is HTTPS; localhost is exempt for dev.

---

## Verification
- `python manage.py check` — clean throughout.
- `python manage.py makemigrations --check` — no missing migrations.
- Each fix tested via the Django test client / shell (likes toggle, bookmark,
  team counts, photo upload, per-question approval, badge clear, notify +
  subscribe endpoints).

## Git
All changes committed and pushed to `origin/main`. Rebased cleanly over
concurrent teammate commits (TCE logging, learning videos, forms/profile
validations) with no conflicts.
