"""Set the school Marketing Collaterals display order + per-asset summary
(and cleaner titles) for the curated activation sequence. Matches existing
uploads by filename so it works on prod without touching the files. Assets not
in the curated list are pushed below (kept visible)."""
from django.db import migrations

# (filename fragment, order, title, summary/description)
CURATED = [
    ('Weekly_Communication', 1, 'Weekly communication',
     'Send these whatsapp/in-app messages to parents & students to encourage participation'),
    ('PROMO_1', 2, 'Promo Video 1', 'Send video with message given in the weekly communication plan'),
    ('PROMO_2', 3, 'Promo Video 2', 'Send video with message given in the weekly communication plan'),
    ('PROMO_3', 4, 'Promo Video 3', 'Send video with message given in the weekly communication plan'),
    ('Register_Now', 5, 'Register Now Video', 'Send video with message given in the weekly communication plan'),
    ('IFTPoster_01', 6, 'Poster 1', 'Send poster with message given in the weekly communication plan'),
    ('IFTPoster_02', 7, 'Poster 2', 'Send poster with message given in the weekly communication plan'),
    ('IFTPoster_03', 8, 'Poster 3', 'Send poster with message given in the weekly communication plan'),
    ('IFT_Standee', 9, 'Standee', 'Display standee in the school premises'),
]
EXTRAS_START = 20


def apply(apps, schema_editor):
    DR = apps.get_model('admins', 'DigitalResource')
    curated_ids = set()
    for frag, order, title, desc in CURATED:
        for r in DR.objects.filter(file__icontains=frag):
            r.order = order
            r.title = title
            r.description = desc
            r.save(update_fields=['order', 'title', 'description'])
            curated_ids.add(r.id)
    # Keep non-curated assets visible, just after the curated 9.
    i = EXTRAS_START
    for r in DR.objects.exclude(id__in=curated_ids).order_by('title'):
        r.order = i
        r.save(update_fields=['order'])
        i += 1


def reverse(apps, schema_editor):
    pass


class Migration(migrations.Migration):
    dependencies = [
        ('admins', '0015_alter_digitalresource_options_digitalresource_order'),
    ]
    operations = [migrations.RunPython(apply, reverse)]
