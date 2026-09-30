from datetime import date

from django.core.management.base import BaseCommand

from admins.models import Phase

# IFT Season 6 official pathway (2026, revised — deadline extended). Single-date
# milestones use the same start and end date. Order = chronological.
PHASES = [
    (1, 'Registration, Coaching & Idea Submission', date(2026, 7, 29), date(2026, 11, 15),
     'Register, learn through coaching sessions, and submit your idea.'),
    (2, 'Top 400 Ideas', date(2026, 11, 20), date(2026, 11, 20),
     'The Top 400 ideas are announced.'),
    (3, 'Online Mentoring', date(2026, 11, 25), date(2026, 11, 30),
     'Online mentoring sessions for shortlisted participants.'),
    (4, 'Top 100 Ideas', date(2026, 12, 10), date(2026, 12, 10),
     'The Top 100 ideas are announced.'),
    (5, 'Zonal Evaluation', date(2026, 12, 22), date(2026, 12, 23),
     'Zonal-level evaluation of the shortlisted ideas.'),
    (6, 'Hall of Fame (Top 12 Ideas)', date(2026, 12, 28), date(2026, 12, 28),
     'The Top 12 ideas enter the IFT Hall of Fame.'),
    (7, '2-Day Bootcamp', date(2027, 1, 8), date(2027, 1, 9),
     'A two-day bootcamp for the finalists.'),
    (8, 'Grand Finale & National Recognition', date(2027, 1, 10), date(2027, 1, 10),
     'The Grand Finale and National Recognition ceremony.'),
]


class Command(BaseCommand):
    help = 'Load IFT Season 6 phases/timeline (idempotent — replaces existing).'

    def handle(self, *args, **options):
        Phase.objects.all().delete()
        for order, name, start, end, desc in PHASES:
            Phase.objects.create(
                order=order, name=name, start_date=start, end_date=end,
                description=desc, status='upcoming',
            )
            self.stdout.write(f'  #{order} {name} ({start} -> {end})')
        self.stdout.write(self.style.SUCCESS(f'Loaded {len(PHASES)} phases.'))
