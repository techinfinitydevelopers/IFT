"""In-app + push notifications for scheduled Content (announcements/FAQs/training).

Two notifications per scheduled item, each sent at most once (dedup via the
Content.reminder_notification_sent / live_notification_sent flags):
- A reminder 2 days before `scheduled_at`.
- The go-live notification on `scheduled_at`'s date, which also flips the
  content to 'published' (same auto-publish this admin panel already did on
  page load — now it happens for real via cron regardless of anyone opening
  the admin panel).

Call send_content_notifications() daily (see students/management/commands/
send_scheduled_emails.py, which already runs once a day).
"""
from datetime import timedelta

from django.contrib.auth.models import User
from django.utils import timezone

_AUDIENCE_ROLES = {
    'students': ['student'],
    'evaluators': ['jury'],
    'schools': ['school'],
    'admins': ['superadmin', 'viewer'],
}


def _audience_for(content):
    if content.visibility == 'all':
        return User.objects.filter(profile__isnull=False)
    roles = _AUDIENCE_ROLES.get(content.visibility, [])
    return User.objects.filter(profile__role__in=roles)


def send_content_notifications():
    from admins.models import Content
    from students.push import notify

    today = timezone.localdate()
    counts = {'reminder': 0, 'live': 0}

    reminder_targets = Content.objects.filter(
        status='scheduled',
        reminder_notification_sent=False,
        scheduled_at__date=today + timedelta(days=2),
    )
    for content in reminder_targets:
        for user in _audience_for(content):
            notify(
                user, 'announcement',
                title=f"Upcoming: {content.title}",
                message=content.subtitle or content.body[:200],
                icon='event_upcoming',
                action_url='/notifications/',
                action_label='View',
            )
        content.reminder_notification_sent = True
        content.save(update_fields=['reminder_notification_sent'])
        counts['reminder'] += 1

    live_targets = Content.objects.filter(
        status='scheduled',
        live_notification_sent=False,
        scheduled_at__date=today,
    )
    for content in live_targets:
        for user in _audience_for(content):
            notify(
                user, 'announcement',
                title=content.title,
                message=content.subtitle or content.body[:200],
                icon='notifications_active',
                action_url='/notifications/',
                action_label='View',
            )
        content.status = 'published'
        content.live_notification_sent = True
        content.save(update_fields=['status', 'live_notification_sent'])
        counts['live'] += 1

    return counts
