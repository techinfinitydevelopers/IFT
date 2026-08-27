"""IFT Idea Booster Masterclass — reminder email sent the MORNING BEFORE each
session (subject says "...Masterclass Tomorrow at 11 AM").

Meant to run on a Railway cron DAILY, any time in the morning, e.g. 9:00 AM
IST (3:30 UTC):
    cron:  30 3 * * *
    start: python manage.py send_idea_booster_reminder

The command self-checks the date: it only sends when tomorrow is a session
date (below), so a daily cron is safe — on other days it does nothing. Each
student gets a given session's reminder at most once (dedup via
MilestoneEmailLog), throttled, and retry-safe (only a successful send is
logged, so a failed one retries).

    python manage.py send_idea_booster_reminder             # send if a session is tomorrow
    python manage.py send_idea_booster_reminder --test EMAIL # preview to one address
    python manage.py send_idea_booster_reminder --force MMDD # force a specific session (testing)
"""
import time
from datetime import date, timedelta

from django.core.management.base import BaseCommand
from django.utils import timezone

SUBJECT = 'Gentle Reminder: IFT Idea Booster Masterclass Tomorrow at 11 AM'
TEMPLATE = 'students/email_idea_booster_reminder.html'
THROTTLE_SECONDS = 0.4

# (session date, human label, zoom register link). Reminder fires the MORNING
# BEFORE this date (11 AM session, "tomorrow" in the email copy).
SESSIONS = [
    (date(2026, 8, 15), '15th August 2026', 'https://zoom.us/meeting/register/PdB4J6T5RAmN-vm0M5_zJw'),
    (date(2026, 8, 29), '29th August 2026', 'https://zoom.us/meeting/register/NlQpHzRsQGiwG2LPQvd16w'),
    (date(2026, 9, 19), '19th September 2026', 'https://zoom.us/meeting/register/XdcZlUkqSFCZVc3xr_XhUw'),
    (date(2026, 10, 3), '3rd October 2026', 'https://zoom.us/meeting/register/jaR6nKpRQK-GQaW1D1T-7A'),
]


class Command(BaseCommand):
    help = 'Send the Idea Booster Masterclass reminder to students (the morning before a session).'

    def add_arguments(self, parser):
        parser.add_argument('--test', help='Send a single preview email to this address only.')
        parser.add_argument('--force', help='Force a specific session by MMDD (e.g. 0815) — testing only.')

    def handle(self, *args, **options):
        from students.models import Student
        from admins.models import MilestoneEmailLog
        from accounts.emails import send_branded_email

        test_to = options.get('test')
        if test_to:
            d, label, link = SESSIONS[0]
            send_branded_email(SUBJECT, test_to, TEMPLATE, {'session_date': label, 'session_link': link})
            self.stdout.write(self.style.SUCCESS(f'Preview sent to {test_to}.'))
            return

        force = options.get('force')
        session = None
        if force:
            session = next((s for s in SESSIONS if f'{s[0]:%m%d}' == force), None)
        else:
            tomorrow = timezone.localdate() + timedelta(days=1)
            session = next((s for s in SESSIONS if s[0] == tomorrow), None)

        if not session:
            self.stdout.write('No Idea Booster session tomorrow — nothing to send.')
            return

        d, label, link = session
        key = f'ib_{d.isoformat()}'  # <=30 chars, unique per session
        ctx = {'session_date': label, 'session_link': link}

        sent = failed = skipped = 0
        students = Student.objects.select_related('user').all()
        for st in students:
            email = (st.user.email if st.user else '').strip()
            if not email:
                skipped += 1
                continue
            if MilestoneEmailLog.objects.filter(student=st, milestone=key).exists():
                skipped += 1
                continue
            result = send_branded_email(SUBJECT, email, TEMPLATE, ctx)
            if result:
                MilestoneEmailLog.objects.get_or_create(student=st, milestone=key)
                sent += 1
            else:
                failed += 1  # not logged -> retried on next run
            time.sleep(THROTTLE_SECONDS)

        self.stdout.write(self.style.SUCCESS(
            f'Idea Booster reminder ({label}): sent={sent} failed={failed} skipped={skipped}.'))
