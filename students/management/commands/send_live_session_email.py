"""One-time broadcast: "IFT Teacher Mentoring Session is LIVE" to all active schools.

Sent once per school (dedup via RecurringEmailLog, key 'live_session_invite').
Run manually when the client asks:  python manage.py send_live_session_email
Add --test EMAIL to send a single preview to yourself first.
"""
from django.core.management.base import BaseCommand

SUBJECT = 'The IFT Teacher Mentoring Session Is Live – Join Now!'
TEMPLATE = 'students/email_live_session.html'
EMAIL_KEY = 'live_session_invite'


class Command(BaseCommand):
    help = 'One-time: email all active schools that the mentoring session is live.'

    def add_arguments(self, parser):
        parser.add_argument('--test', help='Send a single preview email to this address only.')

    def handle(self, *args, **options):
        from students.models import School
        from accounts.emails import send_branded_email

        test_to = options.get('test')
        if test_to:
            send_branded_email(SUBJECT, test_to, TEMPLATE, {'school': None})
            self.stdout.write(self.style.SUCCESS(f'Preview sent to {test_to}.'))
            return

        from students.milestone_emails import send_once_school_email
        sent = 0
        for school in School.objects.filter(status='active'):
            if send_once_school_email(school, EMAIL_KEY, SUBJECT, TEMPLATE):
                sent += 1
        self.stdout.write(self.style.SUCCESS(f'Live-session email: sent {sent} (once per school).'))
