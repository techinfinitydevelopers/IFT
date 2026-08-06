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
- Teacher Mentorship Session: fires every Wednesday between
  TEACHER_SESSION_START and TEACHER_SESSION_END (the live sessions themselves
  are every Friday; the reminder goes out the Wednesday before).

Also sends in-app/push notifications for scheduled Content (announcements/
FAQs/training) — see admins/content_notifications.py: one reminder 2 days
before scheduled_at, one on scheduled_at's date (which also auto-publishes it).
"""
from datetime import date, timedelta

from django.core.management.base import BaseCommand
from django.utils import timezone

IDEA_DEADLINE = date(2026, 10, 15)
RESUBMIT_DEADLINE = date(2026, 11, 15)

TEACHER_SESSION_START = date(2026, 8, 7)   # first Friday session
TEACHER_SESSION_END = date(2026, 9, 25)    # last Friday session
WEDNESDAY = 2  # date.weekday(): Monday=0 ... Sunday=6


class Command(BaseCommand):
    help = 'Send date-gated milestone emails (idea reminder, idea published, resubmit reminder). Run daily via cron.'

    def handle(self, *args, **options):
        from students.models import Student, IdeaSubmission, School
        from ai_assistant.models import AIEvaluation
        from students.milestone_emails import (
            send_milestone_email, send_weekly_school_email, send_once_school_email)
        from admins.content_notifications import send_content_notifications

        today = timezone.localdate()
        sent = {'idea_reminder': 0, 'idea_published': 0, 'resubmit_reminder': 0,
                 'teacher_mentorship': 0, 'payment_reminder': 0,
                 'school_payment_reminder': 0}

        # Payment reminder -> students who registered >= 2 days ago and still
        # haven't paid. Once per student (MilestoneEmailLog dedup).
        payment_cutoff = timezone.now() - timedelta(days=2)
        for s in (Student.objects.filter(is_paid=False, created_at__lte=payment_cutoff)
                  .select_related('user')):
            if send_milestone_email(s, 'payment_reminder', background=False):
                sent['payment_reminder'] += 1

        # School payment reminder -> active schools that have at least one
        # unpaid student. Once per school (dedup ignoring date).
        unpaid_school_ids = set(
            Student.objects.filter(is_paid=False, school__isnull=False)
            .values_list('school_id', flat=True)
        )
        if unpaid_school_ids:
            for school in School.objects.filter(status='active', id__in=unpaid_school_ids):
                if send_once_school_email(
                        school, 'school_payment_reminder',
                        'Help Your Students Start Their IFT Journey',
                        'students/email_school_payment_reminder.html'):
                    sent['school_payment_reminder'] += 1

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

        if (today.weekday() == WEDNESDAY
                and TEACHER_SESSION_START - timedelta(days=7) <= today <= TEACHER_SESSION_END):
            subject = "IFT Teacher Mentorship Session Reminder"
            for school in School.objects.filter(status='active'):
                if send_weekly_school_email(
                        school, 'teacher_mentorship', subject,
                        'students/email_teacher_mentorship.html'):
                    sent['teacher_mentorship'] += 1

        content_counts = send_content_notifications()

        self.stdout.write(self.style.SUCCESS(
            f"send_scheduled_emails: {sent} | content_notifications: {content_counts} (date={today})"
        ))
