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
CMD ["sh", "-c", "python manage.py migrate --noinput && gunicorn ift_platform.wsgi --bind 0.0.0.0:8000 --timeout 60"]
