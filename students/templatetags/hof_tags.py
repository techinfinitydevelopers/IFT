import re
from django import template
from django.utils.safestring import mark_safe

register = template.Library()


@register.filter
def person_initials(name):
    """
    Extract initials from first name of each person.
    Split by '&' and ',' to identify individuals.
    'Adarsh Sharma & Jay Kumar Roy' -> 'AJ'
    'Advit Ranawade, Anisha Jani & Rahil Chadha' -> 'AAR'
    """
    if not name:
        return ''
    # Split by & and ,
    parts = re.split(r'[&,]', name)
    initials = ''
    for part in parts:
        part = part.strip()
        if part:
            # Take first letter of first word (the person's first name)
            initials += part[0].upper()
    return initials


@register.filter
def md_to_html(text):
    """
    Convert basic markdown to HTML.
    **bold** -> <b>bold</b>
    [text](url) -> <a href="url">text</a>
    [email](url) -> <a href="mailto:email">email</a>
    Newlines -> <br>
    """
    if not text:
        return ''
    # Links: [text](url)
    text = re.sub(r'\[([^\]]+)\]\(([^)]+)\)', lambda m: '<a href="{}" style="color:var(--primary);text-decoration:underline;">{}</a>'.format(
        'mailto:' + m.group(1) if '@' in m.group(1) and m.group(2) == 'url' else m.group(2),
        m.group(1)
    ), text)
    # Bold: **text**
    text = re.sub(r'\*\*(.+?)\*\*', r'<b>\1</b>', text)
    # Newlines
    text = text.replace('\n', '<br>')
    return mark_safe(text)
