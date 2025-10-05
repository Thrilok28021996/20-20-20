# Procfile for Railway deployment
# This file defines the processes to run

# Web server - Uses start.sh which handles migrations and collectstatic
# then starts Gunicorn
web: ./start.sh

# Celery worker (for background tasks)
worker: celery -A mysite worker --loglevel=info --concurrency=2

# Celery beat (for scheduled tasks)
beat: celery -A mysite beat --loglevel=info --scheduler django_celery_beat.schedulers:DatabaseScheduler

# NOTE: NO "release:" command here!
# Nixpacks treats "release:" as a BUILD phase command, but database
# is not available during build. Migrations run in start.sh instead.
