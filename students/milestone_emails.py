"""Automated journey/milestone emails for students.

Each milestone maps to a (subject, template) pair. `send_milestone_email`
sends it via the shared branded-email helper, exactly ONCE per student per
milestone (dedup via `admins.models.MilestoneEmailLog`) — so callers can be
invoked repeatedly (ranking recompute, daily cron, admin save) without ever
double-sending.

Trigger points:
- top400 / top100 / school_winner  -> ai_assistant/evaluator.py:update_rankings()
- idea_reminder / idea_published / resubmit_reminder -> students/management/
  commands/send_scheduled_emails.py (daily cron; see that file for setup)
- top12 / zonal_pitch -> ai_assistant/signals.py (fires when an admin flips
  the corresponding AIEvaluation flag to True in Django admin — there is no
  scoring formula for these two stages, so a human selection is unavoidable;
  only the *sending* is automatic)
"""
import threading

MILESTONE_EMAILS = {
    'payment_reminder': {
        'subject': "You're One Step Away from Starting Your IFT Journey!",
        'template': 'students/email_payment_reminder.html',
    },
    'idea_reminder': {
        'subject': 'Submit your IFT idea today!',
        'template': 'students/email_idea_reminder.html',
    },
    'idea_published': {
        'subject': 'Your IFT Idea Is Now Published!',
        'template': 'students/email_idea_published.html',
    },
    'top400': {
        'subject': "Congratulations! You've Made It To The TOP 400",
        'template': 'students/email_top400.html',
    },
    'resubmit_reminder': {
        'subject': 'Refine & Resubmit Your Idea Before 15th November',
        'template': 'students/email_resubmit_reminder.html',
    },
    'school_winner': {
        'subject': "Congratulations! You've Been Selected As The Best Idea From Your School.",
        'template': 'students/email_school_winner.html',
    },
    'top100': {
        'subject': "Congratulations! You've Reached The TOP 100",
        'template': 'students/email_top100.html',
    },
    'zonal_pitch': {
        'subject': "You're Invited To The IFT Zonal Pitch Fest!",
        'template': 'students/email_zonal_pitch_invite.html',
    },
    'top12': {
        'subject': "Congratulations! You've Entered The TOP 12",
        'template': 'students/email_top12.html',
    },
    'hall_of_fame': {
        'subject': "Claim Your Pitch Ticket! You're Officially A Part Of IFT's Hall Of Fame",
        'template': 'students/email_hall_of_fame.html',
    },
}


def _send_now(student, milestone):
    """Send synchronously. Returns True if sent, False if skipped
    (already sent / no email), never raises."""
    try:
        from admins.models import MilestoneEmailLog
        from accounts.emails import send_branded_email

        if MilestoneEmailLog.objects.filter(student=student, milestone=milestone).exists():
            return False
        email = (student.user.email or '').strip()
        if not email:
            return False
        cfg = MILESTONE_EMAILS[milestone]
        send_branded_email(cfg['subject'], email, cfg['template'], {'user': student.user})
        MilestoneEmailLog.objects.get_or_create(student=student, milestone=milestone)
        return True
    except Exception:
        return False


def send_milestone_email(student, milestone, background=True):
    """Send `milestone` email to `student` once (dedup). By default runs in a
    background daemon thread so callers (ranking recompute, admin save) never
    block or fail because of email issues. Pass background=False (e.g. from a
    management command) to get a definite sent/skipped result synchronously.
    """
    if background:
        threading.Thread(target=_send_now, args=(student, milestone), daemon=True).start()
        return None
    return _send_now(student, milestone)


def _school_email(school):
    return (school.contact_email or school.principal_email
            or (school.user.email if school.user else '') or '').strip()


def send_once_school_email(school, email_key, subject, template, context=None):
    """Send a school-facing email at most ONCE ever (dedup via RecurringEmailLog,
    ignoring the date column) — for one-time nudges like the payment reminder.
    Returns True if sent, False if skipped. Never raises."""
    from django.utils import timezone
    from admins.models import RecurringEmailLog
    from accounts.emails import send_branded_email

    if RecurringEmailLog.objects.filter(school=school, email_key=email_key).exists():
        return False
    email = _school_email(school)
    if not email:
        return False
    try:
        send_branded_email(subject, email, template, {'school': school, **(context or {})})
        RecurringEmailLog.objects.get_or_create(
            school=school, email_key=email_key, sent_date=timezone.localdate())
        return True
    except Exception:
        return False


def send_weekly_school_email(school, email_key, subject, template, context=None):
    """Send a recurring broadcast email to `school`, once per calendar day
    (dedup via RecurringEmailLog keyed by (school, email_key, today)) — so a
    weekly cron naturally re-sends next week, but a same-day double-run of the
    cron never double-sends. Always synchronous (called from a management
    command, which wants a definite sent/skipped count).
    """
    from django.utils import timezone
    from admins.models import RecurringEmailLog
    from accounts.emails import send_branded_email

    today = timezone.localdate()
    if RecurringEmailLog.objects.filter(
            school=school, email_key=email_key, sent_date=today).exists():
        return False
    email = _school_email(school)
    if not email:
        return False
    try:
        send_branded_email(subject, email, template, {'school': school, **(context or {})})
        RecurringEmailLog.objects.get_or_create(
            school=school, email_key=email_key, sent_date=today)
        return True
    except Exception:
        return False
