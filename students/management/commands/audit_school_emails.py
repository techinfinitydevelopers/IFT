"""Read-only audit of school email / login-account consistency.

    python manage.py audit_school_emails            # report only
    python manage.py audit_school_emails --sync     # set School.user email/username
                                                    # to School.contact_email (no clashes)
Orphan school accounts are only reported, never deleted.
"""
from django.contrib.auth.models import User
from django.core.management.base import BaseCommand
from django.db.models import Q

from students.models import School


class Command(BaseCommand):
    help = 'Audit school contact emails vs login accounts; find orphans.'

    def add_arguments(self, parser):
        parser.add_argument('--sync', action='store_true')

    def handle(self, *a, **o):
        self.stdout.write('== Schools whose login email differs from contact_email ==')
        for s in School.objects.select_related('user').exclude(contact_email=''):
            if s.user and (s.user.email or '').lower() != s.contact_email.lower():
                self.stdout.write(f'  [{s.id}] {s.name}: contact={s.contact_email} login={s.user.email}')
                if o['sync']:
                    clash = User.objects.filter(Q(email__iexact=s.contact_email) |
                                                Q(username__iexact=s.contact_email)).exclude(pk=s.user.pk).exists()
                    if clash:
                        self.stdout.write('     -> SKIPPED (email used by another account)')
                    else:
                        s.user.email = s.user.username = s.contact_email
                        s.user.save(update_fields=['email', 'username'])
                        self.stdout.write('     -> synced')
        self.stdout.write('== Schools with no login account ==')
        for s in School.objects.filter(user__isnull=True):
            self.stdout.write(f'  [{s.id}] {s.name} ({s.contact_email})')
        self.stdout.write("== Orphan 'school' accounts (no School row) ==")
        for u in User.objects.filter(profile__role='school', school_profile__isnull=True):
            self.stdout.write(f'  user {u.id} {u.email} active={u.is_active}')
        self.stdout.write('== Students whose login email equals a school email ==')
        emails = set(School.objects.values_list('contact_email', flat=True)) | \
            set(School.objects.values_list('principal_email', flat=True))
        emails = {e.lower() for e in emails if e}
        for u in User.objects.filter(student_profile__isnull=False):
            if (u.email or '').lower() in emails:
                self.stdout.write(f'  student user {u.id} {u.email}')
