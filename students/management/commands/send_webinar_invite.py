"""IFT School Webinar invitation to all active schools.

Per-CALENDAR-DAY dedup (RecurringEmailLog key 'webinar_invite'), THROTTLED to
avoid the gateway's rate limit, and RETRY-SAFE: a school is only marked sent
when the send actually succeeds, so a failed send is retried on the next run
(no "logged but never delivered" gap).

    python manage.py send_webinar_invite            # send to all active schools
    python manage.py send_webinar_invite --test EMAIL
"""
import time

from django.core.management.base import BaseCommand
from django.utils import timezone

SUBJECT = 'Invitation: IFT School Webinar | 11th August | 4:30 PM'
TEMPLATE = 'students/email_webinar_invite.html'
EMAIL_KEY = 'webinar_invite'
THROTTLE_SECONDS = 0.5  # ~2/sec — stays under the gateway's burst limit


class Command(BaseCommand):
    help = 'Email the IFT School Webinar invite to all active schools (throttled, retry-safe).'

    def add_arguments(self, parser):
        parser.add_argument('--test', help='Send a single preview email to this address only.')

    def handle(self, *args, **options):
        from students.models import School
        from admins.models import RecurringEmailLog
        from accounts.emails import send_branded_email
        from students.milestone_emails import _school_email

        test_to = options.get('test')
        if test_to:
            send_branded_email(SUBJECT, test_to, TEMPLATE, {'school': None})
            self.stdout.write(self.style.SUCCESS(f'Preview sent to {test_to}.'))
            return

        today = timezone.localdate()
        sent = failed = skipped = 0
        for school in School.objects.filter(status='active'):
            if RecurringEmailLog.objects.filter(school=school, email_key=EMAIL_KEY, sent_date=today).exists():
                skipped += 1
                continue
            email = _school_email(school)
            if not email:
                skipped += 1
                continue
            result = send_branded_email(SUBJECT, email, TEMPLATE, {'school': school})
            if result:
                RecurringEmailLog.objects.get_or_create(school=school, email_key=EMAIL_KEY, sent_date=today)
                sent += 1
            else:
                failed += 1  # not logged -> will be retried on the next run
            time.sleep(THROTTLE_SECONDS)
        self.stdout.write(self.style.SUCCESS(
            f'Webinar invite: sent={sent} failed={failed} skipped={skipped} (date={today}).'))
