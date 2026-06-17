from django.contrib.auth.signals import user_logged_in
from django.dispatch import receiver


@receiver(user_logged_in)
def ensure_profile(sender, user, request, **kwargs):
    from .models import UserProfile
    UserProfile.objects.get_or_create(
        user=user,
        defaults={'role': 'superadmin' if user.is_superuser else 'student'}
    )
