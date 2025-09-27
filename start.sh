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
python manage.py shell << EOF
from django.contrib.auth import get_user_model
User = get_user_model()
if not User.objects.filter(is_superuser=True).exists():
    User.objects.create_superuser('admin', 'admin@example.com', 'admin123')
    print('Superuser created')
else:
    print('Superuser already exists')
EOF

# Test health endpoint
echo "🏥 Testing health endpoint..."
python simple_health.py

# Start the server
echo "🌟 Starting Gunicorn server..."
exec gunicorn --bind 0.0.0.0:${PORT:-8000} --workers 3 --timeout 120 mysite.wsgi:application