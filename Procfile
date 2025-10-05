# Procfile for Railway deployment
# This file defines the processes to run

# Web server (Gunicorn with production-optimized settings)
web: gunicorn mysite.wsgi:application --bind 0.0.0.0:$PORT --workers 4 --threads 2 --worker-class gthread --worker-tmp-dir /dev/shm --access-logfile - --error-logfile - --log-level info --timeout 120

# Celery worker (for background tasks)
worker: celery -A mysite worker --loglevel=info --concurrency=2

# Celery beat (for scheduled tasks)
beat: celery -A mysite beat --loglevel=info --scheduler django_celery_beat.schedulers:DatabaseScheduler

# Database migration (run once before deploying)
release: python manage.py migrate --noinput && python manage.py collectstatic --noinput
