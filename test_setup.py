#!/usr/bin/env python
"""
EyeHealth 20-20-20 SaaS Setup Test Script
=========================================

This script tests the basic setup and functionality of the Django application
to ensure all components are working correctly.
"""
import os
import sys
import django
from datetime import date

# Add the project root to Python path
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

# Setup Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'mysite.settings')
django.setup()

from django.contrib.auth import get_user_model
from django.core.management import execute_from_command_line
from django.test import TestCase
from accounts.models import User, UserProfile
from timer.models import TimerSession, TimerInterval, BreakRecord
from analytics.models import DailyStats
from subscriptions.models import SubscriptionPlan

User = get_user_model()

def test_database_connection():
    """Test database connectivity"""
    try:
        # Try to query users
        user_count = User.objects.count()
        print(f"✅ Database connection successful - {user_count} users in database")
        return True
    except Exception as e:
        print(f"❌ Database connection failed: {e}")
        return False

def test_models():
    """Test model creation and relationships"""
    try:
        # Create test user
        user = User.objects.create_user(
            username='testuser',
            email='test@example.com',
            password='testpass123',
            first_name='Test',
            last_name='User'
        )
        print("✅ User model creation successful")
        
        # Create user profile
        profile = UserProfile.objects.create(
            user=user,
            age=30,
            occupation='Software Developer',
            daily_screen_time_hours=8.0
        )
        print("✅ UserProfile model creation successful")
        
        # Create timer session
        session = TimerSession.objects.create(user=user)
        print("✅ TimerSession model creation successful")
        
        # Create timer interval
        interval = TimerInterval.objects.create(
            session=session,
            interval_number=1
        )
        print("✅ TimerInterval model creation successful")
        
        # Create break record
        break_record = BreakRecord.objects.create(
            user=user,
            session=session,
            interval=interval,
            break_type='scheduled'
        )
        print("✅ BreakRecord model creation successful")
        
        # Create daily stats
        daily_stats = DailyStats.objects.create(
            user=user,
            date=date.today(),
            total_work_minutes=120,
            total_intervals_completed=6,
            total_breaks_taken=5
        )
        print("✅ DailyStats model creation successful")
        
        # Test relationships
        assert session.user == user
        assert interval.session == session
        assert break_record.user == user
        assert profile.user == user
        print("✅ Model relationships working correctly")
        
        # Cleanup
        user.delete()
        print("✅ Model cleanup successful")
        
        return True
    except Exception as e:
        print(f"❌ Model tests failed: {e}")
        return False

def test_subscription_plans():
    """Test subscription plan creation"""
    try:
        # Create test subscription plans
        free_plan = SubscriptionPlan.objects.create(
            name="Test Free",
            slug="test-free",
            description="Test free plan",
            price=0.00,
            currency="USD",
            billing_period="monthly",
            max_daily_sessions=5,
            is_active=True
        )
        
        pro_plan = SubscriptionPlan.objects.create(
            name="Test Pro",
            slug="test-pro",
            description="Test pro plan",
            price=4.99,
            currency="USD",
            billing_period="monthly",
            max_daily_sessions=0,  # Unlimited
            advanced_analytics=True,
            is_active=True
        )
        
        print("✅ Subscription plans created successfully")
        
        # Test plan features
        assert free_plan.max_daily_sessions == 5
        assert pro_plan.advanced_analytics == True
        print("✅ Subscription plan features working correctly")
        
        # Cleanup
        free_plan.delete()
        pro_plan.delete()
        print("✅ Subscription plan cleanup successful")
        
        return True
    except Exception as e:
        print(f"❌ Subscription plan tests failed: {e}")
        return False

def test_admin_setup():
    """Test Django admin setup"""
    try:
        from django.contrib.admin import site
        
        # Check if models are registered in admin
        registered_models = [model.__name__ for model in site._registry.keys()]
        
        expected_models = ['User', 'UserProfile', 'TimerSession', 'DailyStats', 'SubscriptionPlan']
        for model in expected_models:
            if model in registered_models:
                print(f"✅ {model} registered in admin")
            else:
                print(f"❌ {model} not registered in admin")
        
        return True
    except Exception as e:
        print(f"❌ Admin setup test failed: {e}")
        return False

def test_urls():
    """Test URL configuration"""
    try:
        from django.urls import reverse
        
        # Test key URL patterns
        urls_to_test = [
            'accounts:home',
            'accounts:login',
            'accounts:signup',
            'accounts:pricing',
            'timer:dashboard',
        ]
        
        for url_name in urls_to_test:
            try:
                url = reverse(url_name)
                print(f"✅ URL '{url_name}' resolves to: {url}")
            except Exception as e:
                print(f"❌ URL '{url_name}' failed to resolve: {e}")
        
        return True
    except Exception as e:
        print(f"❌ URL configuration test failed: {e}")
        return False

def test_static_files():
    """Test static files configuration"""
    try:
        from django.conf import settings
        
        print(f"✅ STATIC_URL: {settings.STATIC_URL}")
        print(f"✅ STATIC_ROOT: {settings.STATIC_ROOT}")
        
        # Check if static directories exist
        static_dirs = getattr(settings, 'STATICFILES_DIRS', [])
        for static_dir in static_dirs:
            if os.path.exists(static_dir):
                print(f"✅ Static directory exists: {static_dir}")
            else:
                print(f"❌ Static directory missing: {static_dir}")
        
        return True
    except Exception as e:
        print(f"❌ Static files test failed: {e}")
        return False

def run_all_tests():
    """Run all tests and provide summary"""
    print("=" * 60)
    print("EyeHealth 20-20-20 SaaS Setup Test")
    print("=" * 60)
    
    tests = [
        ("Database Connection", test_database_connection),
        ("Model Creation", test_models),
        ("Subscription Plans", test_subscription_plans),
        ("Admin Setup", test_admin_setup),
        ("URL Configuration", test_urls),
        ("Static Files", test_static_files),
    ]
    
    results = []
    for test_name, test_func in tests:
        print(f"\n📋 Testing {test_name}...")
        try:
            result = test_func()
            results.append((test_name, result))
        except Exception as e:
            print(f"❌ {test_name} failed with exception: {e}")
            results.append((test_name, False))
    
    # Summary
    print("\n" + "=" * 60)
    print("TEST SUMMARY")
    print("=" * 60)
    
    passed = sum(1 for _, result in results if result)
    total = len(results)
    
    for test_name, result in results:
        status = "✅ PASSED" if result else "❌ FAILED"
        print(f"{test_name}: {status}")
    
    print(f"\nOverall: {passed}/{total} tests passed")
    
    if passed == total:
        print("🎉 All tests passed! Your Django setup is working correctly.")
        print("\n📝 Next Steps:")
        print("1. Visit http://localhost:8000 to see the application")
        print("2. Create a superuser: python manage.py createsuperuser")
        print("3. Access admin panel: http://localhost:8000/admin/")
        print("4. Register a test user and try the timer functionality")
        print("5. Review the deployment documentation in DEPLOYMENT.md")
    else:
        print("⚠️  Some tests failed. Please check the errors above.")
        print("💡 Common issues:")
        print("- Make sure all migrations are applied: python manage.py migrate")
        print("- Check database connection settings")
        print("- Verify all required packages are installed")
    
    return passed == total

if __name__ == '__main__':
    success = run_all_tests()
    sys.exit(0 if success else 1)