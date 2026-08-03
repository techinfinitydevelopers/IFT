"""Detect DB schema drift — tables/columns the models expect but the database
is missing (usually caused by a faked migration).

Run on the affected server (e.g. Railway):

    python manage.py db_doctor

For every model it runs a lightweight query that selects all columns. If the
database is missing a column/table you get the exact error (e.g.
"no such column: ai_evaluation.is_top_12"), which tells you precisely what to
fix. It also lists any unapplied migrations.
"""
from django.core.management.base import BaseCommand
from django.apps import apps
from django.db import connection
from django.db.utils import OperationalError, ProgrammingError


class Command(BaseCommand):
    help = 'Report DB columns/tables the models expect but the database lacks.'

    def handle(self, *args, **opts):
        w = self.stdout.write
        ok = self.style.SUCCESS
        bad = self.style.ERROR
        line = '-' * 64

        w(line)
        w('SCHEMA CHECK — querying every model (all columns)')
        w(line)
        problems = []
        for model in apps.get_models():
            label = f'{model._meta.app_label}.{model.__name__}'
            try:
                # Forces a SELECT of every column on the table.
                list(model.objects.all()[:1].values())
                w(ok(f'  OK   {label}'))
            except (OperationalError, ProgrammingError) as e:
                msg = str(e).splitlines()[0]
                w(bad(f'  FAIL {label}  ->  {msg}'))
                problems.append((label, msg))
            except Exception as e:
                # Non-DB error (e.g. abstract) — ignore.
                pass

        w('')
        w(line)
        w('UNAPPLIED MIGRATIONS')
        w(line)
        try:
            from django.db.migrations.executor import MigrationExecutor
            executor = MigrationExecutor(connection)
            plan = executor.migration_plan(executor.loader.graph.leaf_nodes())
            if plan:
                for migration, _ in plan:
                    w(bad(f'  PENDING  {migration.app_label}.{migration.name}'))
            else:
                w(ok('  None — all migrations are marked applied.'))
        except Exception as e:
            w(bad(f'  could not read migration state: {e}'))

        w('')
        w(line)
        if problems:
            w(bad(f'{len(problems)} table(s) have missing columns/tables.'))
            w('These were likely marked applied via a faked migration but never '
              'actually created. To fix on this server:')
            w('  1. Find the migration that adds the missing column:')
            w('       python manage.py showmigrations <app>')
            w('  2. Un-fake it, then apply for real:')
            w('       python manage.py migrate <app> <prev_migration> --fake')
            w('       python manage.py migrate <app>')
            w('  (Replace <app>/<prev_migration> based on the FAIL lines above.)')
        else:
            w(ok('No schema drift detected — every model matches the database.'))
