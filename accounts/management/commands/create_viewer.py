"""Create (or update) a read-only Viewer login.

Usage:
    python manage.py create_viewer <email> <password> [--name "Full Name"]

The account can open every admin page but cannot make any change
(enforced by ReadOnlyViewerMiddleware).
"""
from django.core.management.base import BaseCommand
from django.contrib.auth.models import User

from accounts.models import UserProfile


class Command(BaseCommand):
    help = 'Create or update a read-only Viewer account.'

    def add_arguments(self, parser):
        parser.add_argument('email')
        parser.add_argument('password')
        parser.add_argument('--name', default='Viewer', help='Full name (optional)')

    def handle(self, *args, **opts):
        email = opts['email'].strip().lower()
        password = opts['password']
        name_parts = opts['name'].split(' ', 1)
        first = name_parts[0]
        last = name_parts[1] if len(name_parts) > 1 else ''

        user, created = User.objects.get_or_create(
            username=email, defaults={'email': email, 'first_name': first, 'last_name': last},
        )
        user.email = email
        user.first_name = first
        user.last_name = last
        user.is_staff = False
        user.is_superuser = False
        user.set_password(password)
        user.save()

        UserProfile.objects.update_or_create(user=user, defaults={'role': 'viewer'})

        action = 'Created' if created else 'Updated'
        self.stdout.write(self.style.SUCCESS(
            f'{action} read-only viewer login: {email}'
        ))
