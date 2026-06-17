web: gunicorn ift_platform.wsgi --bind 0.0.0.0:$PORT
release: python manage.py migrate --noinput && python manage.py collectstatic --noinput
