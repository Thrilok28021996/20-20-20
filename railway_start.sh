#!/bin/bash
set -e

echo "🚀 Railway deployment started at $(date)"
echo "🔍 PORT: ${PORT}"
echo "🔍 DATABASE_URL: ${DATABASE_URL:0:20}..."

# Run migrations
echo "🔄 Running migrations..."
python manage.py migrate --noinput

# Collect static files
echo "📦 Collecting static files..."
python manage.py collectstatic --noinput

# Start Gunicorn
echo "🌟 Starting Gunicorn on 0.0.0.0:${PORT}..."
exec gunicorn \
    --bind 0.0.0.0:${PORT} \
    --workers 2 \
    --worker-class sync \
    --timeout 120 \
    --keep-alive 5 \
    --max-requests 1000 \
    --max-requests-jitter 100 \
    --access-logfile - \
    --error-logfile - \
    --log-level info \
    mysite.wsgi:application