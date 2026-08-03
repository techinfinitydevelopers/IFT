"""Daily cron job for date-gated milestone emails.

⚠️ This command does nothing on its own — something has to RUN it daily.
Locally you can run it by hand (`python manage.py send_scheduled_emails`).
On Railway, add a Cron Job service (or a scheduled deploy) that runs:

    python manage.py send_scheduled_emails

once a day (any time after midnight IST is fine). This is an infrastructure
setting outside the codebase — ask whoever manages the Railway project to add
it; it is NOT wired up by this command existing.

Each email is sent at most once per student (dedup via MilestoneEmailLog), so
running this command daily/repeatedly is always safe.

Dates (edit here if the season's deadlines change):
- Idea Submission Reminder + Idea Published: fire from IDEA_DEADLINE onward.
- Resubmit Reminder: fires from RESUBMIT_DEADLINE onward.
"""
from datetime import date

from django.core.management.base import BaseCommand
from django.utils import timezone

IDEA_DEADLINE = date(2026, 10, 15)
RESUBMIT_DEADLINE = date(2026, 11, 15)


class Command(BaseCommand):
    help = 'Send date-gated milestone emails (idea reminder, idea published, resubmit reminder). Run daily via cron.'

    def handle(self, *args, **options):
        from students.models import Student, IdeaSubmission
        from ai_assistant.models import AIEvaluation
        from students.milestone_emails import send_milestone_email

        today = timezone.localdate()
        sent = {'idea_reminder': 0, 'idea_published': 0, 'resubmit_reminder': 0}

        if today >= IDEA_DEADLINE:
            submitted_student_ids = set(
                IdeaSubmission.objects.exclude(status='draft')
                .values_list('student_id', flat=True)
            )
            # Reminder -> everyone who has NOT submitted by the deadline.
            for s in Student.objects.exclude(id__in=submitted_student_ids).select_related('user'):
                if send_milestone_email(s, 'idea_reminder', background=False):
                    sent['idea_reminder'] += 1
            # Published -> everyone who HAS submitted.
            for s in Student.objects.filter(id__in=submitted_student_ids).select_related('user'):
                if send_milestone_email(s, 'idea_published', background=False):
                    sent['idea_published'] += 1

        if today >= RESUBMIT_DEADLINE:
            evals = (AIEvaluation.objects.filter(is_top_400=True, rank__gt=100)
                     .select_related('submission__student__user'))
            for e in evals:
                if send_milestone_email(e.submission.student, 'resubmit_reminder', background=False):
                    sent['resubmit_reminder'] += 1

        self.stdout.write(self.style.SUCCESS(
            f"send_scheduled_emails: {sent} (date={today})"
        ))
