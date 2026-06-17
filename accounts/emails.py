from django.core.mail import send_mail
from django.conf import settings
from django.template.loader import render_to_string


def send_onboard_credentials(user, temp_password, role, extra_context=None):
    context = {
        'user': user,
        'temp_password': temp_password,
        'role': role,
        'login_url': f"{settings.SITE_URL}/accounts/sign-in/" if hasattr(settings, 'SITE_URL') else '/accounts/sign-in/',
        **(extra_context or {}),
    }
    subject = f'Welcome to IFT Platform - Your {role.title()} Account'
    message = render_to_string('accounts/email_onboard_credentials.txt', context)
    try:
        send_mail(subject, message, settings.DEFAULT_FROM_EMAIL, [user.email], fail_silently=True)
    except Exception as e:
        print(f"[EMAIL] Failed to send to {user.email}: {e}")
