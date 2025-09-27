#!/bin/bash
set -e

echo "🚀 Starting Railway deployment..."

# Check environment variables
echo "🔍 Checking environment variables..."
python check_env.py

# Wait for database to be ready
echo "⏳ Waiting for database..."
until python manage.py check --database default; do
  echo "Database is unavailable - sleeping"
  sleep 2
done

echo "✅ Database is ready!"

# Run migrations
echo "🔄 Running migrations..."
python manage.py migrate --noinput

# Create superuser if it doesn't exist (optional)
echo "👤 Creating superuser if needed..."
python manage.py shell -c "
from django.contrib.auth import get_user_model
User = get_user_model()
if not User.objects.filter(is_superuser=True).exists():
    User.objects.create_superuser('admin', 'admin@example.com', 'admin123')
    print('Superuser created')
else:
    print('Superuser already exists')
"

# Test Django setup
echo "🏥 Testing Django setup..."
python -c "
import os
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'mysite.settings')
import django
django.setup()
print('✅ Django setup successful')
from django.db import connection
connection.ensure_connection()
print('✅ Database connection successful')
"

# Start the server
echo "🌟 Starting Gunicorn server on port ${PORT:-8000}..."
echo "🔍 Environment: PORT=${PORT}, ALLOWED_HOSTS=${ALLOWED_HOSTS}"
exec gunicorn --bind 0.0.0.0:${PORT:-8000} --workers 3 --timeout 120 --access-logfile - --error-logfile - --log-level info mysite.wsgi:application