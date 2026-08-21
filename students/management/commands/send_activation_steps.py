"""One-time '6 Key Steps to Activate Your IFT School Journey' email to all
active schools.

SEND-ONCE-EVER dedup (RecurringEmailLog key 'activation_steps', date ignored),
THROTTLED to stay under the gateway rate limit, and RETRY-SAFE: a school is only
marked sent when the send actually succeeds, so a failed one is retried on the
next run (no "logged but never delivered" gap).

    python manage.py send_activation_steps               # send to all active schools (once each)
    python manage.py send_activation_steps --test EMAIL  # send a single preview to EMAIL
"""
import time

from django.core.management.base import BaseCommand

SUBJECT = '6 Key Steps to Activate Your IFT School Journey'
TEMPLATE = 'students/email_activation_steps.html'
EMAIL_KEY = 'activation_steps'
THROTTLE_SECONDS = 0.5  # ~2/sec — stays under the gateway's burst limit


class Command(BaseCommand):
    help = 'Email the 6-step IFT School Activation Journey to all active schools (once each, throttled, retry-safe).'

    def add_arguments(self, parser):
        parser.add_argument('--test', help='Send a single preview email to this address only.')

    def handle(self, *args, **options):
        from students.models import School
        from admins.models import RecurringEmailLog
        from accounts.emails import send_branded_email
        from students.milestone_emails import _school_email
        from django.utils import timezone

        test_to = options.get('test')
        if test_to:
            send_branded_email(SUBJECT, test_to, TEMPLATE, {'school': None})
            self.stdout.write(self.style.SUCCESS(f'Preview sent to {test_to}.'))
            return

        today = timezone.localdate()
        sent = failed = skipped = 0
        for school in School.objects.filter(status='active'):
            # send-once-ever: skip if this school already got it on any date
            if RecurringEmailLog.objects.filter(school=school, email_key=EMAIL_KEY).exists():
                skipped += 1
                continue
            email = _school_email(school)
            if not email:
                skipped += 1
                continue
            result = send_branded_email(SUBJECT, email, TEMPLATE, {'school': school})
            if result:
                RecurringEmailLog.objects.get_or_create(
                    school=school, email_key=EMAIL_KEY, sent_date=today)
                sent += 1
            else:
                failed += 1  # not logged -> retried on the next run
            time.sleep(THROTTLE_SECONDS)
        self.stdout.write(self.style.SUCCESS(
            f'Activation steps email: sent={sent} failed={failed} skipped={skipped}.'))
