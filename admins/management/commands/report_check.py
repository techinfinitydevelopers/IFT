"""Quick console report to verify live/production data feeds the Reports page.

Run on Railway (or locally) to confirm the report reflects real data:

    python manage.py report_check
    python manage.py report_check --rows 15      # show more sample rows
    python manage.py report_check --grade 8 --zone West --paid true   # test filters

Prints overall counts, filter breakdowns, and a sample of the exact rows the
Students Excel export would contain - no login or file download needed.
"""
from django.core.management.base import BaseCommand
from django.db.models import Count, Q

from students.models import Student, School, IdeaSubmission
from ai_assistant.models import AIEvaluation
from admins.views import _state_to_zone, _submission_state, _evaluator_for

PUBLISHED = ['submitted', 'under_review', 'evaluated', 'reviewed']


class Command(BaseCommand):
    help = 'Print a summary + sample of the report data (verifies live data).'

    def add_arguments(self, parser):
        parser.add_argument('--rows', type=int, default=8, help='Sample rows to show')
        parser.add_argument('--grade', default='')
        parser.add_argument('--gender', default='')
        parser.add_argument('--zone', default='')
        parser.add_argument('--paid', default='')
        parser.add_argument('--top', default='')

    def handle(self, *args, **o):
        w = self.stdout.write
        line = '-' * 60

        w(line)
        w('OVERALL DATA (proves the report has real data to show)')
        w(line)
        w(f'  Students        : {Student.objects.count()}')
        w(f'  Schools         : {School.objects.count()}')
        w(f'  Ideas (all)     : {IdeaSubmission.objects.count()}')
        w(f'  Ideas published : {IdeaSubmission.objects.filter(status__in=PUBLISHED).count()}')
        w(f'  Ideas draft     : {IdeaSubmission.objects.filter(status="draft").count()}')
        w(f'  AI evaluations  : {AIEvaluation.objects.count()}')
        w(f'  Paid students   : {Student.objects.filter(is_paid=True).count()}')
        w(f'  Unpaid students : {Student.objects.filter(is_paid=False).count()}')
        w(f'  Top 400         : {AIEvaluation.objects.filter(is_top_400=True).count()}')
        w(f'  Top 100 (rank)  : {AIEvaluation.objects.filter(rank__gt=0, rank__lte=100).count()}')
        w(f'  Top 12          : {AIEvaluation.objects.filter(is_top_12=True).count()}')

        w('')
        w('BREAKDOWNS')
        w(line)
        for label, qs in [
            ('By grade', Student.objects.values('grade').annotate(n=Count('id')).order_by('grade')),
            ('By gender', Student.objects.values('gender').annotate(n=Count('id')).order_by('gender')),
            ('By board', School.objects.values('board').annotate(n=Count('id')).order_by('board')),
        ]:
            parts = ', '.join(f"{r[list(r)[0]] or '(blank)'}:{r['n']}" for r in qs)
            w(f'  {label:<10}: {parts or "(none)"}')
        # zone breakdown (python-side)
        zones = {}
        for s in School.objects.all():
            z = _state_to_zone(s.state)
            zones[z] = zones.get(z, 0) + 1
        w(f'  By zone   : ' + (', '.join(f'{k}:{v}' for k, v in sorted(zones.items())) or '(none)'))

        # ---- sample rows exactly as the Students export builds them ----
        subs = IdeaSubmission.objects.select_related(
            'student', 'student__user', 'student__school').prefetch_related('ai_evaluation')
        if o['grade']:
            subs = subs.filter(student__grade=o['grade'])
        if o['gender']:
            subs = subs.filter(student__gender=o['gender'])
        if o['paid'] in ('true', 'false'):
            subs = subs.filter(student__is_paid=(o['paid'] == 'true'))
        if o['top'] == '400':
            subs = subs.filter(ai_evaluation__is_top_400=True)
        elif o['top'] == '12':
            subs = subs.filter(ai_evaluation__is_top_12=True)
        elif o['top'] == '100':
            subs = subs.filter(ai_evaluation__rank__gt=0, ai_evaluation__rank__lte=100)
        subs = list(subs.order_by('-ai_evaluation__final_score', '-submitted_at'))
        if o['zone']:
            want = o['zone'].strip().lower()
            subs = [s for s in subs if _state_to_zone(_submission_state(s)).lower() == want]

        w('')
        w(f'SAMPLE ROWS (Students export) - filters: '
          f"grade={o['grade'] or 'any'} gender={o['gender'] or 'any'} "
          f"zone={o['zone'] or 'any'} paid={o['paid'] or 'any'} top={o['top'] or 'any'}")
        w(line)
        w(f'  Matched rows: {len(subs)}')
        for s in subs[:o['rows']]:
            st = s.student
            try:
                ev = s.ai_evaluation
            except Exception:
                ev = None
            ev_name, ev_score = _evaluator_for(s)
            w(f"  - {st.user.get_full_name() or st.user.username} | "
              f"G{st.grade} | {st.school_display_name} | "
              f"{_state_to_zone(_submission_state(s))} | "
              f"{'Paid' if st.is_paid else 'Unpaid'} | "
              f"AI:{ev.final_score if ev else '-'} | "
              f"Eval:{ev_name or '-'} | "
              f"{s.get_status_display()}")
        w(line)
        w('If the numbers above match your platform, the Reports page + Excel '
          'export are pulling this exact live data.')
