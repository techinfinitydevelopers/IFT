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
_OTP_MESSAGE = (
    "Your OTP for India Future Tycoons verification is {otp}. "
    "Valid for 10 minutes. Do not share it with anyone. - ENLEARNING"
)
# Sevenomedia response codes that mean the send failed (13xx). 1300 = success.
_ERROR_CODES = {
    '1301', '1302', '1303', '1304', '1305', '1306', '1307', '1308', '1309',
    '1310', '1311', '1312', '1313', '1314', '1315', '1316', '1325', '1326',
}


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
        # Gateway returns "SUCCESS | <message-id> | <mobile>" on success,
        # or a 13xx error code on failure.
        ok = resp.status_code == 200 and 'SUCCESS' in body.upper() \
            and not any(code in body for code in _ERROR_CODES)
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
    if str(code).strip() != str(data.get('otp')):
        return False, 'Incorrect OTP. Please try again.'
    return True, None


def clear(request):
    request.session.pop(_SESSION_KEY, None)
    request.session.modified = True
