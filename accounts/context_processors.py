def vapid_public_key(request):
    """Expose the VAPID public key to templates for Web Push subscription."""
    from django.conf import settings
    return {'vapid_public_key': getattr(settings, 'VAPID_PUBLIC_KEY', '')}


def launch_confetti(request):
    """Show launch-day celebratory confetti from 29 Jul 2026 11:00 AM IST onwards.

    Server-side gate so all users get a consistent trigger regardless of their
    device clock. The once-per-user behaviour is handled client-side via
    localStorage in templates/partials/launch_confetti.html.
    """
    from datetime import datetime
    from django.utils import timezone
    try:
        launch = timezone.make_aware(datetime(2026, 7, 29, 11, 0, 0))
        return {'launch_confetti_active': timezone.now() >= launch}
    except Exception:
        return {'launch_confetti_active': False}


def _visibility_for_role(role):
    role_map = {
        'student': 'students',
        'school': 'schools',
        'jury': 'evaluators',
        'superadmin': 'admins',
    }
    vis = role_map.get(role, 'students')
    return ['all', vis]


def unread_notification_count(request):
    if request.user.is_authenticated:
        try:
            from students.models import Notification
            from admins.models import Content
            profile = getattr(request.user, 'profile', None)
            role = getattr(profile, 'role', 'student')
            read_at = getattr(profile, 'announcements_read_at', None)
            vis = _visibility_for_role(role)
            notif_count = Notification.objects.filter(user=request.user, is_read=False).count()
            # Only count announcements the user hasn't cleared yet.
            content_qs = Content.objects.filter(status='published', visibility__in=vis)
            # A newly-registered user must not see announcements posted before they
            # joined — floor everything by their account creation time.
            joined = getattr(request.user, 'date_joined', None)
            if joined:
                content_qs = content_qs.filter(created_at__gte=joined)
            unread_content_qs = content_qs
            if read_at:
                unread_content_qs = content_qs.filter(created_at__gt=read_at)
            content_count = unread_content_qs.count()
            recent_notifs = list(Notification.objects.filter(user=request.user).order_by('-created_at')[:5])
            recent_content = list(content_qs.order_by('-created_at')[:5])
            combined = []
            for n in recent_notifs:
                combined.append({'type': 'notif', 'title': n.title, 'message': n.message, 'icon': n.icon or 'notifications', 'is_read': n.is_read, 'created_at': n.created_at, 'notif_type': n.notification_type})
            icon_map = {'announcement': 'campaign', 'training': 'event', 'faq': 'quiz'}
            for c in recent_content:
                c_read = bool(read_at and c.created_at <= read_at)
                combined.append({'type': 'content', 'title': c.title, 'message': c.body or c.subtitle or '', 'icon': icon_map.get(c.content_type, 'campaign'), 'is_read': c_read, 'created_at': c.created_at, 'notif_type': c.content_type})
            combined.sort(key=lambda x: x['created_at'], reverse=True)
            return {
                'unread_notification_count': notif_count + content_count,
                'header_notifications_combined': combined[:5],
            }
        except Exception:
            pass
    return {'unread_notification_count': 0, 'header_notifications_combined': []}


def user_role(request):
    if request.user.is_authenticated:
        try:
            return {'user_role': request.user.profile.role}
        except Exception:
            return {'user_role': 'student'}
    return {'user_role': None}


def student_has_submission(request):
    if request.user.is_authenticated:
        try:
            profile = request.user.profile
            if profile.role == 'student':
                from students.models import IdeaSubmission
                has_sub = IdeaSubmission.objects.filter(student=request.user.student_profile).exists()
                return {'student_has_submission': has_sub}
        except Exception:
            pass
    return {'student_has_submission': False}
