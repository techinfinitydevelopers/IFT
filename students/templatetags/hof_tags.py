import re
from django import template

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
