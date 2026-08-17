from django.contrib.auth.signals import user_logged_in
from django.dispatch import receiver


@receiver(user_logged_in)
def ensure_profile(sender, user, request, **kwargs):
    from .models import UserProfile
    # Infer role from linked profiles instead of defaulting everyone to
    # 'student' — a school/jury user with a missing UserProfile was otherwise
    # recreated as a student on login and mis-routed.
    if user.is_superuser:
        role = 'superadmin'
    elif hasattr(user, 'school_profile'):
        role = 'school'
    elif hasattr(user, 'jury_profile'):
        role = 'jury'
    else:
        role = 'student'
    UserProfile.objects.get_or_create(user=user, defaults={'role': role})
