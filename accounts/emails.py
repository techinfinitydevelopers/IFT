from django.conf import settings
from django.contrib.staticfiles.storage import staticfiles_storage
from django.core.mail import EmailMultiAlternatives
from django.template.loader import render_to_string, TemplateDoesNotExist
from django.utils.html import strip_tags


def _base_context():
    """Shared context every branded email needs (logo + login URL)."""
    site_url = getattr(settings, 'SITE_URL', '') or ''
    return {
        'site_url': site_url,
        'login_url': f"{site_url}/accounts/sign-in/",
        'logo_url': f"{site_url}{staticfiles_storage.url('images/email_logo.png')}",
    }


def send_branded_email(subject, to, template, context=None, attachments=None):
    """Send an email rendered from a template that extends email_onboard_base.html.

    All outgoing IFT emails should go through here so they share the one
    standard branded template. Only the dynamic `context` changes.

    - subject: email subject line
    - to: single address (str) or list of addresses
    - template: path to an html template extending the base
    - context: dynamic vars for that template
    - attachments: optional list of (filename, content_bytes, mimetype)
    """
    ctx = _base_context()
    ctx['subject'] = subject
    ctx.update(context or {})

    recipients = [to] if isinstance(to, str) else list(to)

    html_message = render_to_string(template, ctx)
    text_message = strip_tags(html_message)

    try:
        email = EmailMultiAlternatives(subject, text_message, settings.DEFAULT_FROM_EMAIL, recipients)
        email.attach_alternative(html_message, 'text/html')
        for att in (attachments or []):
            email.attach(*att)
        result = email.send(fail_silently=False)
        print(f"[EMAIL] Sent '{subject}' to {recipients}, result={result}")
        return result
    except Exception as e:
        print(f"[EMAIL] Failed to send '{subject}' to {recipients}: {e}")
        import traceback
        traceback.print_exc()
        return 0


def send_password_reset_by_admin(user, temp_password, role):
    """Notify a user their password was reset by an admin (distinct wording
    from the onboarding email, which says 'account has been created')."""
    return send_branded_email(
        f'Your IFT Password Has Been Reset',
        user.email,
        'accounts/email_password_reset_by_admin.html',
        {'user': user, 'temp_password': temp_password, 'role': role},
    )


def send_onboard_credentials(user, temp_password, role, extra_context=None):
    site_url = getattr(settings, 'SITE_URL', '') or ''
    context = {
        'user': user,
        'temp_password': temp_password,
        'role': role,
        'login_url': f"{site_url}/accounts/sign-in/",
        'logo_url': f"{site_url}{staticfiles_storage.url('images/email_logo.png')}",
        **(extra_context or {}),
    }
    role_slug = role.lower()
    ONBOARD_SUBJECTS = {
        'school': "Welcome to IFT! Your School Is Successfully Registered",
    }
    subject = ONBOARD_SUBJECTS.get(role_slug, f'Welcome to IFT Platform - Your {role.title()} Account')

    try:
        html_message = render_to_string(f'accounts/email_onboard_{role_slug}.html', context)
    except TemplateDoesNotExist:
        html_message = None

    try:
        text_message = render_to_string(f'accounts/email_onboard_{role_slug}.txt', context)
    except TemplateDoesNotExist:
        if html_message:
            text_message = strip_tags(html_message)
        else:
            text_message = render_to_string('accounts/email_onboard_credentials.txt', context)

    try:
        email = EmailMultiAlternatives(subject, text_message, settings.DEFAULT_FROM_EMAIL, [user.email])
        if html_message:
            email.attach_alternative(html_message, 'text/html')
        result = email.send(fail_silently=False)
        print(f"[EMAIL] Sent to {user.email}, result={result}")
    except Exception as e:
        print(f"[EMAIL] Failed to send to {user.email}: {e}")
        import traceback
        traceback.print_exc()

    # In-app / push notification for the new account.
    try:
        from students.push import notify
        notify(user, 'system', f'Your {role.title()} account is ready',
               'Log in to get started on the IFT platform.', 'account_circle',
               '/accounts/sign-in/', 'Log In')
    except Exception:
        pass
