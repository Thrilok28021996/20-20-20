#!/usr/bin/env python
"""
Simple health check script for debugging Railway deployment
"""
import os
import sys

# Add the project directory to Python path
sys.path.insert(0, '/app')

# Set Django settings module
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'mysite.settings')

try:
    import django
    django.setup()

    from django.http import JsonResponse
    from django.utils import timezone

    print("✅ Django setup successful")

    # Test database connection
    from django.db import connection
    with connection.cursor() as cursor:
        cursor.execute("SELECT 1")
        result = cursor.fetchone()
        print(f"✅ Database connection successful: {result}")

    # Test basic health endpoint
    from mysite.health_views import health_check_view
    from django.test import RequestFactory

    factory = RequestFactory()
    request = factory.get('/health/')
    response = health_check_view(request)

    print(f"✅ Health check response: {response.status_code}")
    print(f"   Content: {response.content.decode()}")

except Exception as e:
    print(f"❌ Error: {e}")
    import traceback
    traceback.print_exc()
    sys.exit(1)

print("🎉 All checks passed!")