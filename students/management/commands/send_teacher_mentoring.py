"""Weekly Teacher Mentoring & Training invite to all registered (active) schools.

Schedule this on its OWN Railway cron service, Thursday AND Friday 11:00 AM IST:
    cron:  30 5 * * 4,5    (05:30 UTC = 11:00 IST, Thursday & Friday)
    start: python manage.py send_teacher_mentoring

The cron enforces the day/time; this command just sends to every active school
(deduped once per calendar day via RecurringEmailLog, so Thursday and Friday
each send once) and stops after the last session date. Safe to run repeatedly.
"""
from datetime import date

from django.core.management.base import BaseCommand
from django.utils import timezone

# Emails stop after the last Friday session.
LAST_SESSION_DATE = date(2026, 9, 26)
SUBJECT = 'Weekly IFT Teacher Mentoring & Training Session'


class Command(BaseCommand):
    help = 'Send the weekly Teacher Mentoring invite to all active schools (Thu & Fri 11 AM cron).'

    def handle(self, *args, **options):
        from students.models import School
        from students.milestone_emails import send_weekly_school_email

        today = timezone.localdate()
        if today > LAST_SESSION_DATE:
            self.stdout.write(f'Past the last session date ({LAST_SESSION_DATE}); nothing sent.')
            return

        sent = 0
        for school in School.objects.filter(status='active'):
            if send_weekly_school_email(
                    school, 'teacher_mentoring', SUBJECT,
                    'students/email_teacher_mentorship.html'):
                sent += 1
        self.stdout.write(self.style.SUCCESS(f'Teacher mentoring: sent {sent} emails (date={today}).'))
