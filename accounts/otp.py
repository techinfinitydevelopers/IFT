"""Phone OTP verification via the Sevenomedia SMS gateway.

Session-backed (reliable across gunicorn workers, unlike locmem cache) and
fail-safe. The OTP message MUST match the DLT-approved template exactly:

    Your OTP for India Future Tycoons verification is {#var#}. Valid for 10
    minutes. Do not share it with anyone. - ENLEARNING
"""
import random
import re
import time

import requests
from django.conf import settings

_SESSION_KEY = 'phone_otp'
_MAX_ATTEMPTS = 5          # wrong-code guesses allowed before the OTP is voided
_RESEND_COOLDOWN = 30      # seconds a user must wait between OTP requests
_OTP_MESSAGE = (
    "Your OTP for India Future Tycoons verification is {otp}. "
    "Valid for 10 minutes. Do not share it with anyone. - ENLEARNING"
)


def normalize_mobile(phone):
    """Strip to a bare 10-digit Indian mobile (drops +91 / 0 / spaces)."""
    m = re.sub(r'\D', '', phone or '')
    if len(m) == 12 and m.startswith('91'):
        m = m[2:]
    elif len(m) == 11 and m.startswith('0'):
        m = m[1:]
    return m


def is_configured():
    return bool(settings.SMS_API_KEY and settings.SMS_OTP_TEMPLATE_ID and settings.SMS_ENTITY_ID)


def generate_and_send(request, phone):
    """Generate a 6-digit OTP, stash it in the session, and SMS it.

    Returns (ok: bool, error_message: str | None).
    """
    phone = normalize_mobile(phone)
    if len(phone) != 10 or phone[0] not in '6789':
        return False, 'Enter a valid 10-digit Indian mobile number.'
    if not is_configured():
        return False, 'SMS service is not configured yet. Please try later.'

    # Resend throttle — block rapid re-requests for the same number
    existing = request.session.get(_SESSION_KEY)
    if existing and existing.get('phone') == phone:
        elapsed = int(time.time()) - int(existing.get('ts', 0))
        if 0 <= elapsed < _RESEND_COOLDOWN:
            return False, f'Please wait {_RESEND_COOLDOWN - elapsed}s before requesting another OTP.'

    otp = f"{random.randint(0, 999999):06d}"
    params = {
        'apikey': settings.SMS_API_KEY,
        'type': 'TEXT',
        'sender': settings.SMS_SENDER,
        'entityId': settings.SMS_ENTITY_ID,
        'templateId': settings.SMS_OTP_TEMPLATE_ID,
        'mobile': phone,
        'message': _OTP_MESSAGE.format(otp=otp),
    }
    try:
        resp = requests.get(settings.SMS_API_URL, params=params, timeout=15)
        body = (resp.text or '').strip()
        print(f"[OTP] send -> {phone}: http={resp.status_code} body={body[:200]}", flush=True)
        # Gateway returns "SUCCESS | <message-id> | <mobile>" on success, or an
        # error token (e.g. "1305 | ..." / "ERR_INTERNAL | ...") on failure.
        # Only the FIRST token decides success — the message-id is a random UUID
        # that can coincidentally contain a 13xx error-code substring, so we must
        # NOT substring-match error codes against the whole body.
        first_token = body.split('|', 1)[0].strip().upper()
        ok = resp.status_code == 200 and first_token == 'SUCCESS'
        if ok:
            request.session[_SESSION_KEY] = {'phone': phone, 'otp': otp, 'ts': int(time.time())}
            request.session.modified = True
            return True, None
        return False, 'Could not send OTP right now. Please check the number and try again.'
    except Exception as e:
        print(f"[OTP] send error: {e}", flush=True)
        return False, 'Could not send OTP. Please try again.'


def verify(request, phone, code):
    """Check a submitted OTP against the session. Returns (ok, error)."""
    phone = normalize_mobile(phone)
    data = request.session.get(_SESSION_KEY)
    if not data:
        return False, 'Please request an OTP first.'
    if data.get('phone') != phone:
        return False, 'Mobile number changed. Please request a new OTP.'
    if int(time.time()) - int(data.get('ts', 0)) > settings.OTP_EXPIRY_SECONDS:
        return False, 'OTP expired. Please request a new one.'
    if data.get('attempts', 0) >= _MAX_ATTEMPTS:
        clear(request)
        return False, 'Too many incorrect attempts. Please request a new OTP.'
    if str(code).strip() != str(data.get('otp')):
        data['attempts'] = data.get('attempts', 0) + 1
        request.session[_SESSION_KEY] = data
        request.session.modified = True
        return False, 'Incorrect OTP. Please try again.'
    return True, None


def clear(request):
    request.session.pop(_SESSION_KEY, None)
    request.session.modified = True
