"""
Global pytest fixtures and configuration for the 20-20-20 eye health SaaS application.
This file contains shared fixtures that can be used across all test modules.
"""
import pytest
from datetime import datetime, date, timedelta
from decimal import Decimal
from django.utils import timezone
from django.contrib.auth import get_user_model
from django.test import TestCase, TransactionTestCase
from django.db import transaction

# Import models for fixtures
from accounts.models import (
    User, UserProfile, UserLevel, Badge, UserBadge, Challenge,
    ChallengeParticipation, Achievement, UserStreakData
)
from timer.models import (
    TimerSession, TimerInterval, BreakRecord, UserTimerSettings,
    UserFeedback, BreakPreferenceAnalytics
)
from analytics.models import (
    DailyStats, WeeklyStats, MonthlyStats, UserBehaviorEvent,
    EngagementMetrics, UserSession, UserSatisfactionRating,
    RealTimeMetrics, LiveActivityFeed, PremiumAnalyticsReport, PremiumInsight
)
from payments.models import (
    StripeSubscription, StripePayment, PayPalSubscription, PayPalPayment
)


# ===== USER FIXTURES =====

@pytest.fixture
def user_factory():
    """Factory for creating test users"""
    def create_user(
        email="testuser@example.com",
        username="testuser",
        password="testpass123",
        subscription_type="free",
        is_verified=True,
        **kwargs
    ):
        user_defaults = {
            'email': email,
            'username': username,
            'subscription_type': subscription_type,
            'is_verified': is_verified,
            'first_name': 'Test',
            'last_name': 'User',
            'is_active': True,
            **kwargs
        }
        user = User.objects.create_user(password=password, **user_defaults)
        return user
    return create_user


@pytest.fixture
def free_user(user_factory):
    """Create a free tier user"""
    return user_factory(
        email="freeuser@example.com",
        username="freeuser",
        subscription_type="free"
    )


@pytest.fixture
def premium_user(user_factory):
    """Create a premium user with active subscription"""
    user = user_factory(
        email="premiumuser@example.com",
        username="premiumuser",
        subscription_type="premium"
    )
    user.subscription_start_date = timezone.now() - timedelta(days=30)
    user.subscription_end_date = timezone.now() + timedelta(days=30)
    user.save()
    return user


@pytest.fixture
def expired_premium_user(user_factory):
    """Create a user with expired premium subscription"""
    user = user_factory(
        email="expireduser@example.com",
        username="expireduser",
        subscription_type="premium"
    )
    user.subscription_start_date = timezone.now() - timedelta(days=60)
    user.subscription_end_date = timezone.now() - timedelta(days=1)
    user.save()
    return user


@pytest.fixture
def user_profile_factory():
    """Factory for creating user profiles"""
    def create_profile(user, **kwargs):
        profile_defaults = {
            'age': 30,
            'occupation': 'Software Developer',
            'daily_screen_time_hours': 8.0,
            'wears_glasses': False,
            'has_eye_strain': True,
            'total_breaks_taken': 0,
            'total_screen_time_minutes': 0,
            'longest_streak_days': 0,
            'current_streak_days': 0,
            'timezone': 'UTC',
            'preferred_language': 'en',
            **kwargs
        }
        profile, created = UserProfile.objects.get_or_create(
            user=user, defaults=profile_defaults
        )
        return profile
    return create_profile


# ===== TIMER FIXTURES =====

@pytest.fixture
def timer_session_factory():
    """Factory for creating timer sessions"""
    def create_session(user, **kwargs):
        session_defaults = {
            'start_time': timezone.now() - timedelta(hours=1),
            'end_time': timezone.now(),
            'is_active': False,
            'work_interval_minutes': 20,
            'break_duration_seconds': 20,
            'total_intervals_completed': 3,
            'total_breaks_taken': 2,
            'total_work_minutes': 60,
            **kwargs
        }
        return TimerSession.objects.create(user=user, **session_defaults)
    return create_session


@pytest.fixture
def active_timer_session(user_factory, timer_session_factory):
    """Create an active timer session"""
    user = user_factory()
    return timer_session_factory(
        user=user,
        start_time=timezone.now() - timedelta(minutes=10),
        end_time=None,
        is_active=True,
        total_intervals_completed=0,
        total_breaks_taken=0,
        total_work_minutes=0
    )


@pytest.fixture
def timer_interval_factory():
    """Factory for creating timer intervals"""
    def create_interval(session, **kwargs):
        interval_defaults = {
            'interval_number': 1,
            'start_time': timezone.now() - timedelta(minutes=20),
            'end_time': timezone.now(),
            'status': 'completed',
            'reminder_sent': True,
            'reminder_sent_at': timezone.now() - timedelta(minutes=20),
            **kwargs
        }
        return TimerInterval.objects.create(session=session, **interval_defaults)
    return create_interval


@pytest.fixture
def break_record_factory():
    """Factory for creating break records"""
    def create_break(user, session, **kwargs):
        # Create interval if not provided
        interval = kwargs.pop('interval', None)
        if not interval:
            interval = TimerInterval.objects.create(
                session=session,
                interval_number=1,
                status='completed'
            )

        break_defaults = {
            'break_start_time': timezone.now() - timedelta(minutes=1),
            'break_end_time': timezone.now(),
            'break_duration_seconds': 25,
            'looked_at_distance': True,
            'break_completed': True,
            'break_type': 'scheduled',
            **kwargs
        }
        return BreakRecord.objects.create(
            user=user, session=session, interval=interval, **break_defaults
        )
    return create_break


@pytest.fixture
def compliant_break_record(free_user, timer_session_factory, break_record_factory):
    """Create a compliant break record"""
    session = timer_session_factory(user=free_user)
    return break_record_factory(
        user=free_user,
        session=session,
        break_duration_seconds=25,
        looked_at_distance=True,
        break_completed=True
    )


@pytest.fixture
def non_compliant_break_record(free_user, timer_session_factory, break_record_factory):
    """Create a non-compliant break record"""
    session = timer_session_factory(user=free_user)
    return break_record_factory(
        user=free_user,
        session=session,
        break_duration_seconds=10,  # Too short
        looked_at_distance=False,   # Didn't look at distance
        break_completed=True
    )


@pytest.fixture
def user_timer_settings_factory():
    """Factory for creating user timer settings"""
    def create_settings(user, **kwargs):
        settings_defaults = {
            'work_interval_minutes': 20,
            'break_duration_seconds': 20,
            'long_break_minutes': 5,
            'smart_break_enabled': False,
            'preferred_break_duration': 20,
            'sound_notification': True,
            'desktop_notification': True,
            'email_notification': False,
            'notification_sound_type': 'gentle',
            'sound_volume': 0.5,
            'show_progress_bar': True,
            'show_time_remaining': True,
            'dark_mode': False,
            'auto_start_break': False,
            'auto_start_work': False,
            'custom_break_messages': '',
            **kwargs
        }
        settings, created = UserTimerSettings.objects.get_or_create(
            user=user, defaults=settings_defaults
        )
        return settings
    return create_settings


# ===== GAMIFICATION FIXTURES =====

@pytest.fixture
def user_level_factory():
    """Factory for creating user levels"""
    def create_level(user, **kwargs):
        level_defaults = {
            'current_level': 1,
            'total_experience_points': 100,
            'experience_to_next_level': 200,
            'sessions_completed': 10,
            'breaks_completed': 8,
            'compliant_breaks': 6,
            'achievements_earned': 2,
            'perfect_days': 1,
            **kwargs
        }
        level, created = UserLevel.objects.get_or_create(
            user=user, defaults=level_defaults
        )
        return level
    return create_level


@pytest.fixture
def badge_factory():
    """Factory for creating badges"""
    def create_badge(**kwargs):
        badge_defaults = {
            'name': 'Test Badge',
            'description': 'A test badge for testing purposes',
            'icon': '🏆',
            'category': 'test',
            'requires_sessions': 10,
            'is_active': True,
            'rarity': 'common',
            'experience_reward': 50,
            **kwargs
        }
        return Badge.objects.create(**badge_defaults)
    return create_badge


@pytest.fixture
def common_badge(badge_factory):
    """Create a common badge"""
    return badge_factory(
        name='First Steps',
        description='Complete your first timer session',
        requires_sessions=1,
        rarity='common',
        experience_reward=25
    )


@pytest.fixture
def rare_badge(badge_factory):
    """Create a rare badge"""
    return badge_factory(
        name='Dedicated Worker',
        description='Complete 100 timer sessions',
        requires_sessions=100,
        rarity='rare',
        experience_reward=200
    )


@pytest.fixture
def streak_badge(badge_factory):
    """Create a streak-based badge"""
    return badge_factory(
        name='Week Warrior',
        description='Maintain a 7-day streak',
        requires_streak_days=7,
        requires_sessions=None,
        rarity='common',
        experience_reward=100
    )


@pytest.fixture
def challenge_factory():
    """Factory for creating challenges"""
    def create_challenge(**kwargs):
        now = timezone.now()
        challenge_defaults = {
            'name': 'Test Challenge',
            'description': 'A test challenge for testing purposes',
            'start_date': now,
            'end_date': now + timedelta(days=7),
            'challenge_type': 'session_count',
            'target_value': 50,
            'experience_reward': 200,
            'is_active': True,
            'is_premium_only': False,
            **kwargs
        }
        return Challenge.objects.create(**challenge_defaults)
    return create_challenge


@pytest.fixture
def user_streak_data_factory():
    """Factory for creating user streak data"""
    def create_streak_data(user, **kwargs):
        streak_defaults = {
            'current_daily_streak': 5,
            'current_weekly_streak': 1,
            'best_daily_streak': 15,
            'best_weekly_streak': 3,
            'last_session_date': date.today(),
            'streak_start_date': date.today() - timedelta(days=5),
            'total_sessions_completed': 25,
            'total_break_time_minutes': 500,
            'average_session_length': 45.0,
            **kwargs
        }
        streak_data, created = UserStreakData.objects.get_or_create(
            user=user, defaults=streak_defaults
        )
        return streak_data
    return create_streak_data


# ===== ANALYTICS FIXTURES =====

@pytest.fixture
def daily_stats_factory():
    """Factory for creating daily statistics"""
    def create_daily_stats(user, **kwargs):
        stats_defaults = {
            'date': date.today(),
            'total_work_minutes': 120,
            'total_intervals_completed': 6,
            'total_breaks_taken': 5,
            'total_sessions': 2,
            'breaks_on_time': 4,
            'breaks_compliant': 4,
            'average_break_duration': 22.5,
            'streak_maintained': True,
            'productivity_score': 85.0,
            **kwargs
        }
        stats, created = DailyStats.objects.get_or_create(
            user=user, date=stats_defaults['date'], defaults=stats_defaults
        )
        return stats
    return create_daily_stats


@pytest.fixture
def user_behavior_event_factory():
    """Factory for creating user behavior events"""
    def create_event(user, **kwargs):
        event_defaults = {
            'event_type': 'session_start',
            'timestamp': timezone.now(),
            'event_data': {'test': True},
            'session_id': 'test_session_123',
            'user_agent': 'Test Agent',
            'ip_address': '127.0.0.1',
            **kwargs
        }
        return UserBehaviorEvent.objects.create(user=user, **event_defaults)
    return create_event


@pytest.fixture
def user_session_factory():
    """Factory for creating user sessions"""
    def create_user_session(user, **kwargs):
        session_defaults = {
            'session_key': 'test_session_key',
            'login_time': timezone.now() - timedelta(hours=1),
            'last_activity': timezone.now(),
            'is_active': True,
            'ip_address': '127.0.0.1',
            'user_agent': 'Test Agent',
            'device_type': 'desktop',
            'timer_sessions_started': 2,
            'breaks_taken_in_session': 3,
            'pages_viewed': 10,
            **kwargs
        }
        return UserSession.objects.create(user=user, **session_defaults)
    return create_user_session


# ===== PAYMENT FIXTURES =====

@pytest.fixture
def stripe_subscription_factory():
    """Factory for creating Stripe subscriptions"""
    def create_subscription(user, **kwargs):
        subscription_defaults = {
            'stripe_subscription_id': 'sub_test123',
            'stripe_customer_id': 'cus_test123',
            'amount': Decimal('9.99'),
            'currency': 'USD',
            'status': 'active',
            'activated_at': timezone.now(),
            'next_payment_date': timezone.now() + timedelta(days=30),
            'card_brand': 'visa',
            'card_last4': '4242',
            'card_exp_month': 12,
            'card_exp_year': 2025,
            **kwargs
        }
        subscription, created = StripeSubscription.objects.get_or_create(
            user=user, defaults=subscription_defaults
        )
        return subscription
    return create_subscription


@pytest.fixture
def stripe_payment_factory():
    """Factory for creating Stripe payments"""
    def create_payment(user, subscription=None, **kwargs):
        payment_defaults = {
            'stripe_payment_intent_id': 'pi_test123',
            'payment_status': 'completed',
            'amount': Decimal('9.99'),
            'currency': 'USD',
            'stripe_customer_id': 'cus_test123',
            'card_brand': 'visa',
            'card_last4': '4242',
            'payment_date': timezone.now(),
            **kwargs
        }
        return StripePayment.objects.create(
            user=user, subscription=subscription, **payment_defaults
        )
    return create_payment


# ===== UTILITY FIXTURES =====

@pytest.fixture
def mock_now():
    """Mock timezone.now() for consistent testing"""
    return timezone.now().replace(
        year=2024, month=1, day=15, hour=10, minute=0, second=0, microsecond=0
    )


@pytest.fixture
def test_data_creator():
    """Helper to create comprehensive test data scenarios"""
    class TestDataCreator:
        def __init__(self):
            self.users = {}
            self.sessions = {}
            self.breaks = {}

        def create_user_with_history(self, email="testuser@example.com", days=7):
            """Create a user with session and break history"""
            user = User.objects.create_user(
                username=email.split('@')[0],
                email=email,
                password="testpass123",
                subscription_type="free"
            )

            UserProfile.objects.create(user=user)
            UserLevel.objects.create(user=user)
            UserStreakData.objects.create(user=user, current_daily_streak=days)

            # Create daily sessions for the past 'days' days
            for i in range(days):
                day = date.today() - timedelta(days=i)
                session_start = timezone.make_aware(
                    datetime.combine(day, datetime.min.time()) + timedelta(hours=9)
                )

                session = TimerSession.objects.create(
                    user=user,
                    start_time=session_start,
                    end_time=session_start + timedelta(hours=2),
                    is_active=False,
                    total_intervals_completed=6,
                    total_breaks_taken=5,
                    total_work_minutes=120
                )

                # Create break records for this session
                for j in range(5):
                    interval = TimerInterval.objects.create(
                        session=session,
                        interval_number=j + 1,
                        status='completed'
                    )

                    BreakRecord.objects.create(
                        user=user,
                        session=session,
                        interval=interval,
                        break_start_time=session_start + timedelta(minutes=20 * (j + 1)),
                        break_end_time=session_start + timedelta(minutes=20 * (j + 1), seconds=25),
                        break_duration_seconds=25,
                        looked_at_distance=True,
                        break_completed=True
                    )

                # Create daily stats
                DailyStats.objects.create(
                    user=user,
                    date=day,
                    total_work_minutes=120,
                    total_intervals_completed=6,
                    total_breaks_taken=5,
                    total_sessions=1,
                    breaks_compliant=5,
                    productivity_score=90.0
                )

            return user

        def create_premium_user_with_analytics(self, email="premium@example.com"):
            """Create a premium user with comprehensive analytics data"""
            user = self.create_user_with_history(email, days=30)
            user.subscription_type = "premium"
            user.subscription_start_date = timezone.now() - timedelta(days=30)
            user.subscription_end_date = timezone.now() + timedelta(days=30)
            user.save()

            # Create premium analytics report
            PremiumAnalyticsReport.objects.create(
                user=user,
                report_type='monthly',
                report_period_start=date.today() - timedelta(days=30),
                report_period_end=date.today(),
                total_sessions=30,
                total_work_hours=60.0,
                total_breaks=150,
                compliance_rate=85.0,
                productivity_score=88.5,
                is_generated=True,
                generated_at=timezone.now()
            )

            return user

    return TestDataCreator()


# ===== DATABASE ISOLATION =====

@pytest.fixture
def transactional_db():
    """Use transactional database for tests that need transaction testing"""
    pass


# ===== MARKS AND CONFIGURATIONS =====

# Define custom pytest marks
def pytest_configure(config):
    """Configure custom pytest marks"""
    config.addinivalue_line("markers", "slow: mark test as slow running")
    config.addinivalue_line("markers", "integration: mark test as integration test")
    config.addinivalue_line("markers", "unit: mark test as unit test")
    config.addinivalue_line("markers", "security: mark test as security test")
    config.addinivalue_line("markers", "performance: mark test as performance test")


# ===== CLEANUP =====

@pytest.fixture(autouse=True)
def cleanup_test_data():
    """Cleanup test data after each test"""
    yield
    # Any cleanup code would go here if needed
    pass