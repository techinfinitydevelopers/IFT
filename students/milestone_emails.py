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
