"""Reproduce the /super-admin/submissions/ page server-side and print the exact
traceback of the 500 (instead of the generic error page).

    python manage.py debug_submissions

Runs the real view + template render as a superadmin and dumps the full
Python traceback so the failing line is visible.
"""
import traceback

from django.conf import settings
from django.core.management.base import BaseCommand
from django.contrib.auth.models import User
from django.test import Client


class Command(BaseCommand):
    help = 'Render the submissions page and print the real 500 traceback.'

    def add_arguments(self, parser):
        parser.add_argument('--path', default='/super-admin/submissions/')

    def handle(self, *args, **o):
        w = self.stdout.write
        admin = (User.objects.filter(is_superuser=True).first()
                 or User.objects.filter(profile__role='superadmin').first())
        if not admin:
            w(self.style.ERROR('No superadmin/staff user found to log in with.'))
            return

        host = (settings.ALLOWED_HOSTS[0] if settings.ALLOWED_HOSTS
                and settings.ALLOWED_HOSTS[0] not in ('*',) else 'testserver')
        c = Client(raise_request_exception=True, HTTP_HOST=host)
        c.force_login(admin)

        w(f'Rendering {o["path"]} as {admin.username} (host={host}) ...')
        try:
            r = c.get(o['path'])
            w(self.style.SUCCESS(f'OK — status {r.status_code} (no crash).'))
        except Exception:
            w(self.style.ERROR('CRASH — traceback below:'))
            w('=' * 70)
            w(traceback.format_exc())
            w('=' * 70)
            w('The last "File .../ ... line N, in ..." above your code is the '
              'failing line — share it and I will fix it.')
