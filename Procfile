web: python manage.py migrate --noinput && gunicorn ift_platform.wsgi --bind 0.0.0.0:$PORT --worker-class gthread --workers 1 --threads 8 --timeout 120
release: python manage.py migrate --noinput && python manage.py collectstatic --noinput
