# Railway deployment - v4 (run migrations on startup)
FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends \
    libpq-dev gcc \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Cache bust - force fresh copy
ADD . /app/

RUN python manage.py collectstatic --noinput 2>/dev/null || true

EXPOSE 8000

# Apply migrations for real, then serve. No makemigrations at runtime and no
# blind --fake fallback: faking marks migrations applied WITHOUT creating the
# columns/tables, which silently drifts the DB schema and causes 500s
# ("no such column") on any query touching the missing column.
#
# gthread (not the default sync worker): with sync, one slow client draining a
# large static file blocks the worker inside sock.sendall until --timeout fires
# and the arbiter SIGKILLs it, which took the whole site down every ~60s while
# the 38MB landing promo video was being served. gthread's timeout is a worker
# heartbeat, not a request-duration cap, so a slow response no longer kills the
# worker, and the other threads keep serving while one drains a big file.
#
# Deliberately kept at --workers 1: PROGRESS_TRACKER (admins/views.py) is an
# in-memory dict shared by the rankings bulk-upload and batch-evaluate progress
# bars. With 2+ workers the get_progress poll can land on a worker that never
# saw the task and 404s, so move that state to the DB/cache before scaling up.
CMD ["sh", "-c", "python manage.py migrate --noinput && gunicorn ift_platform.wsgi --bind 0.0.0.0:8000 --worker-class gthread --workers 1 --threads 8 --timeout 120"]
