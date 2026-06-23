import requests
from django.conf import settings
from django.core.mail.backends.base import BaseEmailBackend


class ZeptoMailBackend(BaseEmailBackend):
    """Custom email backend using Zepto Mail Send Email API (HTTP, not SMTP)."""

    API_URL = 'https://api.zeptomail.in/v1.1/email'

    def __init__(self, fail_silently=False, **kwargs):
        super().__init__(fail_silently=fail_silently, **kwargs)
        self.api_key = getattr(settings, 'ZEPTOMAIL_API_KEY', '') or settings.EMAIL_HOST_PASSWORD

    def send_messages(self, email_messages):
        if not email_messages:
            return 0

        sent = 0
        for message in email_messages:
            try:
                if self._send(message):
                    sent += 1
            except Exception:
                if not self.fail_silently:
                    raise
        return sent

    def _send(self, message):
        from_email = message.from_email or settings.DEFAULT_FROM_EMAIL
        # Parse "Name <email>" format
        if '<' in from_email and '>' in from_email:
            from_name = from_email.split('<')[0].strip().strip('"')
            from_addr = from_email.split('<')[1].strip('>')
        else:
            from_name = 'IFT Platform'
            from_addr = from_email

        to_list = []
        for recipient in message.to:
            if '<' in recipient and '>' in recipient:
                to_name = recipient.split('<')[0].strip().strip('"')
                to_addr = recipient.split('<')[1].strip('>')
            else:
                to_name = recipient.split('@')[0]
                to_addr = recipient
            to_list.append({'email_address': {'address': to_addr, 'name': to_name}})

        payload = {
            'from': {'address': from_addr, 'name': from_name},
            'to': to_list,
            'subject': message.subject,
            'textbody': message.body,
        }

        # If HTML content exists
        if message.content_subtype == 'html':
            payload['htmlbody'] = message.body
        elif hasattr(message, 'alternatives') and message.alternatives:
            for content, mimetype in message.alternatives:
                if mimetype == 'text/html':
                    payload['htmlbody'] = content

        headers = {
            'Authorization': self.api_key,
            'Content-Type': 'application/json',
            'Accept': 'application/json',
        }

        response = requests.post(self.API_URL, json=payload, headers=headers, timeout=30)

        if response.status_code in (200, 201):
            return True
        else:
            if not self.fail_silently:
                raise Exception(f'Zepto Mail API error: {response.status_code} - {response.text}')
            return False
