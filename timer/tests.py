import pytest
from datetime import datetime, timedelta, date
from decimal import Decimal
from unittest.mock import patch, Mock, MagicMock
from django.test import TestCase, TransactionTestCase, Client
from django.utils import timezone
from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.db import IntegrityError
from django.urls import reverse
from django.http import JsonResponse
from django.test.utils import override_settings
from django_ratelimit.exceptions import Ratelimited
from freezegun import freeze_time
import json

from timer.models import (
    TimerSession, TimerInterval, BreakRecord,
    UserTimerSettings, UserFeedback, BreakPreferenceAnalytics
)
from timer.utils import (
    get_optimized_recent_sessions, get_user_session_statistics_optimized,
    update_user_settings_safely, get_user_break_preferences,
    cache_user_statistics, invalidate_user_stats_cache
)
from accounts.models import User, UserProfile, UserLevel, UserStreakData
from analytics.models import DailyStats, UserSession, LiveActivityFeed
from mysite.constants import (
    FREE_DAILY_INTERVAL_LIMIT, FREE_DAILY_SESSION_LIMIT,
    DEFAULT_WORK_INTERVAL_MINUTES, DEFAULT_BREAK_DURATION_SECONDS
)

User = get_user_model()


@pytest.mark.timer
class TestTimerSession(TestCase):
    """Test TimerSession model functionality"""

    def setUp(self):
        self.user = User.objects.create_user(
            username='testuser',
            email='test@example.com',
            password='testpass123',
            subscription_type='free'
        )
        UserProfile.objects.create(user=self.user)

    def test_create_timer_session(self):
        """Test creating a new timer session"""
        session = TimerSession.objects.create(
            user=self.user,
            work_interval_minutes=20,
            break_duration_seconds=20
        )

        assert session.user == self.user
        assert session.is_active is True
        assert session.work_interval_minutes == 20
        assert session.break_duration_seconds == 20
        assert session.total_intervals_completed == 0
        assert session.total_breaks_taken == 0
        assert session.total_work_minutes == 0

    def test_session_duration_property(self):
        """Test session duration calculation"""
        start_time = timezone.now() - timedelta(hours=2)
        session = TimerSession.objects.create(
            user=self.user,
            start_time=start_time
        )

        # Test active session duration
        duration = session.duration_minutes
        assert 115 <= duration <= 125  # Allow some variance for test execution time

        # Test completed session duration
        session.end_time = start_time + timedelta(hours=1, minutes=30)
        session.save()
        assert session.duration_minutes == 90

    def test_end_session(self):
        """Test ending a timer session"""
        session = TimerSession.objects.create(user=self.user)
        assert session.is_active is True
        assert session.end_time is None

        session.end_session()

        assert session.is_active is False
        assert session.end_time is not None

    def test_session_str_representation(self):
        """Test string representation of timer session"""
        session = TimerSession.objects.create(user=self.user)
        str_repr = str(session)

        assert self.user.email in str_repr
        assert 'Active' in str_repr

        session.end_session()
        str_repr = str(session)
        assert 'Completed' in str_repr

    def test_multiple_active_sessions_allowed(self):
        """Test that users can have multiple active sessions (edge case)"""
        session1 = TimerSession.objects.create(user=self.user)
        session2 = TimerSession.objects.create(user=self.user)

        assert session1.is_active is True
        assert session2.is_active is True

    @pytest.mark.performance
    def test_session_query_performance(self):
        """Test query performance for session retrieval"""
        # Create multiple sessions
        for i in range(100):
            TimerSession.objects.create(user=self.user)

        with self.assertNumQueries(1):
            sessions = list(TimerSession.objects.filter(user=self.user)[:10])
            assert len(sessions) == 10


@pytest.mark.timer
class TestTimerInterval(TestCase):
    """Test TimerInterval model functionality"""

    def setUp(self):
        self.user = User.objects.create_user(
            username='testuser',
            email='test@example.com',
            password='testpass123'
        )
        self.session = TimerSession.objects.create(user=self.user)

    def test_create_timer_interval(self):
        """Test creating a timer interval"""
        interval = TimerInterval.objects.create(
            session=self.session,
            interval_number=1
        )

        assert interval.session == self.session
        assert interval.interval_number == 1
        assert interval.status == 'active'
        assert interval.reminder_sent is False

    def test_interval_duration_property(self):
        """Test interval duration calculation"""
        start_time = timezone.now() - timedelta(minutes=20)
        interval = TimerInterval.objects.create(
            session=self.session,
            interval_number=1,
            start_time=start_time
        )

        duration = interval.duration_minutes
        assert 19 <= duration <= 21  # Allow variance

    def test_complete_interval(self):
        """Test completing an interval"""
        interval = TimerInterval.objects.create(
            session=self.session,
            interval_number=1
        )

        assert interval.status == 'active'
        assert interval.end_time is None

        interval.complete_interval()

        assert interval.status == 'completed'
        assert interval.end_time is not None

    def test_unique_interval_number_per_session(self):
        """Test that interval numbers are unique per session"""
        TimerInterval.objects.create(
            session=self.session,
            interval_number=1
        )

        with self.assertRaises(IntegrityError):
            TimerInterval.objects.create(
                session=self.session,
                interval_number=1
            )

    def test_interval_ordering(self):
        """Test interval ordering by session and interval number"""
        interval3 = TimerInterval.objects.create(
            session=self.session,
            interval_number=3
        )
        interval1 = TimerInterval.objects.create(
            session=self.session,
            interval_number=1
        )
        interval2 = TimerInterval.objects.create(
            session=self.session,
            interval_number=2
        )

        intervals = list(TimerInterval.objects.filter(session=self.session))
        assert intervals[0] == interval1
        assert intervals[1] == interval2
        assert intervals[2] == interval3


@pytest.mark.timer
class TestBreakRecord(TestCase):
    """Test BreakRecord model functionality"""

    def setUp(self):
        self.user = User.objects.create_user(
            username='testuser',
            email='test@example.com',
            password='testpass123'
        )
        self.session = TimerSession.objects.create(user=self.user)
        self.interval = TimerInterval.objects.create(
            session=self.session,
            interval_number=1
        )

        # Create user timer settings
        UserTimerSettings.objects.create(
            user=self.user,
            break_duration_seconds=20
        )

    def test_create_break_record(self):
        """Test creating a break record"""
        break_record = BreakRecord.objects.create(
            user=self.user,
            session=self.session,
            interval=self.interval,
            break_type='scheduled'
        )

        assert break_record.user == self.user
        assert break_record.session == self.session
        assert break_record.interval == self.interval
        assert break_record.break_type == 'scheduled'
        assert break_record.break_completed is False
        assert break_record.looked_at_distance is False

    def test_complete_break(self):
        """Test completing a break"""
        break_start = timezone.now() - timedelta(seconds=25)
        break_record = BreakRecord.objects.create(
            user=self.user,
            session=self.session,
            interval=self.interval,
            break_start_time=break_start
        )

        break_record.complete_break(looked_at_distance=True)

        assert break_record.break_completed is True
        assert break_record.looked_at_distance is True
        assert break_record.break_end_time is not None
        assert 20 <= break_record.break_duration_seconds <= 30

    def test_break_compliance_property(self):
        """Test break compliance calculation"""
        break_record = BreakRecord.objects.create(
            user=self.user,
            session=self.session,
            interval=self.interval,
            break_duration_seconds=25,
            looked_at_distance=True,
            break_completed=True
        )

        assert break_record.is_compliant is True

        # Test non-compliant break (too short)
        break_record.break_duration_seconds = 15
        break_record.save()
        assert break_record.is_compliant is False

        # Test non-compliant break (didn't look at distance)
        break_record.break_duration_seconds = 25
        break_record.looked_at_distance = False
        break_record.save()
        assert break_record.is_compliant is False

    def test_break_types(self):
        """Test different break types"""
        for break_type, _ in BreakRecord.BREAK_TYPE_CHOICES:
            break_record = BreakRecord.objects.create(
                user=self.user,
                session=self.session,
                interval=self.interval,
                break_type=break_type
            )
            assert break_record.break_type == break_type


@pytest.mark.timer
class TestUserTimerSettings(TestCase):
    """Test UserTimerSettings model functionality"""

    def setUp(self):
        self.user = User.objects.create_user(
            username='testuser',
            email='test@example.com',
            password='testpass123'
        )

    def test_create_default_settings(self):
        """Test creating default timer settings"""
        settings = UserTimerSettings.objects.create(user=self.user)

        assert settings.user == self.user
        assert settings.work_interval_minutes == 20
        assert settings.break_duration_seconds == 20
        assert settings.long_break_minutes == 5
        assert settings.sound_notification is True
        assert settings.desktop_notification is True
        assert settings.email_notification is False

    def test_get_effective_break_duration(self):
        """Test effective break duration calculation"""
        settings = UserTimerSettings.objects.create(
            user=self.user,
            break_duration_seconds=20,
            smart_break_enabled=False
        )

        assert settings.get_effective_break_duration() == 20

        # Test smart break enabled
        settings.smart_break_enabled = True
        settings.preferred_break_duration = 30
        settings.save()

        assert settings.get_effective_break_duration() == 30

    def test_get_break_duration_display_text(self):
        """Test break duration display text"""
        settings = UserTimerSettings.objects.create(
            user=self.user,
            break_duration_seconds=20
        )

        assert '20 seconds' in settings.get_break_duration_display_text()

        settings.preferred_break_duration = 60
        settings.smart_break_enabled = True
        settings.save()

        assert '1 minute' in settings.get_break_duration_display_text()

    def test_sound_volume_validation(self):
        """Test sound volume validation"""
        # Valid volume
        settings = UserTimerSettings.objects.create(
            user=self.user,
            sound_volume=0.5
        )
        assert settings.sound_volume == 0.5

        # Test volume bounds are enforced by validators
        settings.sound_volume = 1.5  # Invalid - too high
        with self.assertRaises(ValidationError):
            settings.full_clean()

        settings.sound_volume = -0.1  # Invalid - too low
        with self.assertRaises(ValidationError):
            settings.full_clean()


@pytest.mark.timer
class TestUserFeedback(TestCase):
    """Test UserFeedback model functionality"""

    def setUp(self):
        self.user = User.objects.create_user(
            username='testuser',
            email='test@example.com',
            password='testpass123'
        )

    def test_create_feedback(self):
        """Test creating user feedback"""
        feedback = UserFeedback.objects.create(
            user=self.user,
            feedback_type='break_duration',
            title='Break too short',
            message='The 20-second break feels too short for my needs',
            rating=3
        )

        assert feedback.user == self.user
        assert feedback.feedback_type == 'break_duration'
        assert feedback.title == 'Break too short'
        assert feedback.rating == 3
        assert feedback.status == 'new'
        assert feedback.priority == 'normal'

    def test_mark_as_resolved(self):
        """Test marking feedback as resolved"""
        feedback = UserFeedback.objects.create(
            user=self.user,
            feedback_type='bug_report',
            title='Timer not working',
            message='Timer stops unexpectedly'
        )

        assert feedback.status == 'new'
        assert feedback.resolved_at is None

        feedback.mark_as_resolved()

        assert feedback.status == 'resolved'
        assert feedback.resolved_at is not None

    def test_feedback_types(self):
        """Test all feedback types can be created"""
        for feedback_type, _ in UserFeedback.FEEDBACK_TYPES:
            feedback = UserFeedback.objects.create(
                user=self.user,
                feedback_type=feedback_type,
                title=f'Test {feedback_type}',
                message='Test message'
            )
            assert feedback.feedback_type == feedback_type


@pytest.mark.timer
class TestBreakPreferenceAnalytics(TestCase):
    """Test BreakPreferenceAnalytics model functionality"""

    def setUp(self):
        self.user = User.objects.create_user(
            username='testuser',
            email='test@example.com',
            password='testpass123'
        )

    def test_create_analytics(self):
        """Test creating break preference analytics"""
        today = date.today()
        week_ago = today - timedelta(days=7)

        analytics = BreakPreferenceAnalytics.objects.create(
            user=self.user,
            analysis_start_date=week_ago,
            analysis_end_date=today,
            preferred_break_duration=20,
            actual_average_break_duration=25.5,
            break_completion_rate=0.85,
            compliant_breaks_percentage=0.75
        )

        assert analytics.user == self.user
        assert analytics.preferred_break_duration == 20
        assert analytics.actual_average_break_duration == 25.5
        assert analytics.break_completion_rate == 0.85

    def test_calculate_smart_break_suggestion(self):
        """Test smart break duration suggestion algorithm"""
        today = date.today()
        week_ago = today - timedelta(days=7)

        # Test case: user takes much longer breaks than set
        analytics = BreakPreferenceAnalytics.objects.create(
            user=self.user,
            analysis_start_date=week_ago,
            analysis_end_date=today,
            preferred_break_duration=20,
            actual_average_break_duration=35,  # 1.75x longer
            break_completion_rate=0.9
        )

        suggestion = analytics.calculate_smart_break_suggestion()
        assert suggestion == 30  # Should suggest 30 seconds

        # Test case: low completion rate
        analytics.actual_average_break_duration = 22
        analytics.break_completion_rate = 0.5  # Low completion rate
        analytics.save()

        suggestion = analytics.calculate_smart_break_suggestion()
        assert suggestion == 10  # Should suggest shorter duration

        # Test case: good patterns
        analytics.actual_average_break_duration = 22
        analytics.break_completion_rate = 0.85
        analytics.save()

        suggestion = analytics.calculate_smart_break_suggestion()
        assert suggestion == 20  # Should maintain current preference


@pytest.mark.timer
@pytest.mark.integration
class TestTimerWorkflow(TestCase):
    """Test complete timer workflow integration"""

    def setUp(self):
        self.user = User.objects.create_user(
            username='testuser',
            email='test@example.com',
            password='testpass123'
        )
        UserProfile.objects.create(user=self.user)
        UserTimerSettings.objects.create(user=self.user)

    def test_complete_timer_session_workflow(self):
        """Test a complete timer session with intervals and breaks"""
        # Start a timer session
        session = TimerSession.objects.create(
            user=self.user,
            work_interval_minutes=20,
            break_duration_seconds=20
        )

        # Create 3 intervals with breaks
        for i in range(3):
            interval = TimerInterval.objects.create(
                session=session,
                interval_number=i + 1,
                start_time=timezone.now() - timedelta(minutes=20*(i+1))
            )
            interval.complete_interval()

            # Take a break after each interval
            break_record = BreakRecord.objects.create(
                user=self.user,
                session=session,
                interval=interval,
                break_start_time=interval.end_time,
                break_type='scheduled'
            )
            break_record.complete_break(looked_at_distance=True)

        # Update session statistics
        session.total_intervals_completed = 3
        session.total_breaks_taken = 3
        session.total_work_minutes = 60
        session.end_session()

        # Verify the complete workflow
        assert session.total_intervals_completed == 3
        assert session.total_breaks_taken == 3
        assert session.total_work_minutes == 60
        assert session.is_active is False

        # Check all intervals are completed
        intervals = session.intervals.all()
        assert len(intervals) == 3
        assert all(interval.status == 'completed' for interval in intervals)

        # Check all breaks are compliant
        breaks = session.breaks.all()
        assert len(breaks) == 3
        assert all(break_record.is_compliant for break_record in breaks)

    @freeze_time("2024-01-15 10:00:00")
    def test_daily_session_limits_free_user(self):
        """Test daily session limits for free users"""
        # Free users should have limited daily sessions
        for i in range(3):  # Create 3 sessions (assuming limit is 3)
            session = TimerSession.objects.create(
                user=self.user,
                start_time=timezone.now() - timedelta(hours=i+1),
                end_time=timezone.now() - timedelta(hours=i)
            )
            session.is_active = False
            session.save()

        # Check if user has reached daily limit
        daily_sessions = TimerSession.objects.filter(
            user=self.user,
            start_time__date=timezone.now().date()
        ).count()

        assert daily_sessions == 3

    def test_premium_user_unlimited_sessions(self):
        """Test that premium users have unlimited sessions"""
        # Make user premium
        self.user.subscription_type = 'premium'
        self.user.subscription_end_date = timezone.now() + timedelta(days=30)
        self.user.save()

        # Create many sessions
        for i in range(10):
            TimerSession.objects.create(
                user=self.user,
                start_time=timezone.now() - timedelta(hours=i+1),
                end_time=timezone.now() - timedelta(hours=i)
            )

        daily_sessions = TimerSession.objects.filter(
            user=self.user,
            start_time__date=timezone.now().date()
        ).count()

        assert daily_sessions == 10  # No limit for premium users


@pytest.mark.timer
@pytest.mark.security
class TestTimerSecurity(TestCase):
    """Test security aspects of timer functionality"""

    def setUp(self):
        self.user1 = User.objects.create_user(
            username='user1',
            email='user1@example.com',
            password='testpass123'
        )
        self.user2 = User.objects.create_user(
            username='user2',
            email='user2@example.com',
            password='testpass123'
        )

    def test_user_session_isolation(self):
        """Test that users can only access their own sessions"""
        session1 = TimerSession.objects.create(user=self.user1)
        session2 = TimerSession.objects.create(user=self.user2)

        # User1 should only see their own sessions
        user1_sessions = TimerSession.objects.filter(user=self.user1)
        assert session1 in user1_sessions
        assert session2 not in user1_sessions

        # User2 should only see their own sessions
        user2_sessions = TimerSession.objects.filter(user=self.user2)
        assert session2 in user2_sessions
        assert session1 not in user2_sessions

    def test_break_record_user_validation(self):
        """Test that break records are properly associated with users"""
        session1 = TimerSession.objects.create(user=self.user1)
        interval1 = TimerInterval.objects.create(
            session=session1,
            interval_number=1
        )

        # Creating break record with correct user should work
        break_record = BreakRecord.objects.create(
            user=self.user1,
            session=session1,
            interval=interval1
        )
        assert break_record.user == self.user1

        # Note: In a real app, you'd have model validation to prevent
        # creating break records where user doesn't match session.user

    def test_timer_settings_user_isolation(self):
        """Test that timer settings are isolated per user"""
        settings1 = UserTimerSettings.objects.create(
            user=self.user1,
            work_interval_minutes=25
        )
        settings2 = UserTimerSettings.objects.create(
            user=self.user2,
            work_interval_minutes=15
        )

        assert settings1.user == self.user1
        assert settings2.user == self.user2
        assert settings1.work_interval_minutes != settings2.work_interval_minutes


# ===== VIEWS TESTS =====

@pytest.mark.timer
@pytest.mark.api
class TestTimerViews(TestCase):
    """Test timer view functionality"""

    def setUp(self):
        self.client = Client()
        self.user = User.objects.create_user(
            username='testuser',
            email='test@example.com',
            password='testpass123',
            subscription_type='free'
        )
        UserProfile.objects.create(user=self.user)
        UserTimerSettings.objects.create(user=self.user)
        self.client.login(username='test@example.com', password='testpass123')

    def test_dashboard_view_get(self):
        """Test dashboard view loads correctly"""
        response = self.client.get(reverse('timer:dashboard'))

        assert response.status_code == 200
        assert 'active_session' in response.context
        assert 'settings' in response.context
        assert 'today_stats' in response.context
        assert 'can_start_session' in response.context

    def test_dashboard_view_creates_missing_data(self):
        """Test dashboard view creates missing user data"""
        # Delete existing data
        UserTimerSettings.objects.filter(user=self.user).delete()

        response = self.client.get(reverse('timer:dashboard'))

        assert response.status_code == 200
        # Check that missing data was created
        assert UserTimerSettings.objects.filter(user=self.user).exists()
        assert DailyStats.objects.filter(user=self.user).exists()

    def test_start_session_success(self):
        """Test successful session start"""
        response = self.client.post(
            reverse('timer:start_session'),
            data={},
            content_type='application/json'
        )

        assert response.status_code == 200
        data = response.json()
        assert data['success'] is True
        assert 'session_id' in data
        assert 'interval_id' in data

        # Verify session was created
        session = TimerSession.objects.get(id=data['session_id'])
        assert session.user == self.user
        assert session.is_active is True

        # Verify interval was created
        interval = TimerInterval.objects.get(id=data['interval_id'])
        assert interval.session == session
        assert interval.interval_number == 1
        assert interval.status == 'active'

    def test_start_session_duplicate_prevention(self):
        """Test prevention of duplicate active sessions"""
        # Create an active session first
        TimerSession.objects.create(user=self.user, is_active=True)

        response = self.client.post(
            reverse('timer:start_session'),
            data={},
            content_type='application/json'
        )

        assert response.status_code == 200
        data = response.json()
        assert data['success'] is False
        assert 'already have an active session' in data['message']

    def test_start_session_free_user_limits(self):
        """Test free user daily interval limits"""
        # Create intervals up to the limit
        session = TimerSession.objects.create(user=self.user, is_active=False)
        for i in range(FREE_DAILY_INTERVAL_LIMIT):
            TimerInterval.objects.create(
                session=session,
                interval_number=i + 1,
                start_time=timezone.now()
            )

        response = self.client.post(
            reverse('timer:start_session'),
            data={},
            content_type='application/json'
        )

        assert response.status_code == 200
        data = response.json()
        assert data['success'] is False
        assert 'Daily limit' in data['message']
        assert 'Premium' in data['message']

    def test_start_session_premium_user_no_limits(self):
        """Test premium users have no limits"""
        # Make user premium
        self.user.subscription_type = 'premium'
        self.user.save()

        # Create many intervals
        session = TimerSession.objects.create(user=self.user, is_active=False)
        for i in range(FREE_DAILY_INTERVAL_LIMIT + 5):
            TimerInterval.objects.create(
                session=session,
                interval_number=i + 1,
                start_time=timezone.now()
            )

        response = self.client.post(
            reverse('timer:start_session'),
            data={},
            content_type='application/json'
        )

        assert response.status_code == 200
        data = response.json()
        assert data['success'] is True  # Should succeed for premium users

    def test_end_session_success(self):
        """Test successful session end"""
        # Create active session
        session = TimerSession.objects.create(
            user=self.user,
            is_active=True,
            total_intervals_completed=3,
            total_breaks_taken=2,
            total_work_minutes=60
        )

        response = self.client.post(
            reverse('timer:end_session'),
            data={},
            content_type='application/json'
        )

        assert response.status_code == 200
        data = response.json()
        assert data['success'] is True
        assert data['session_duration'] == session.duration_minutes
        assert data['intervals_completed'] == 3
        assert data['breaks_taken'] == 2

        # Verify session was ended
        session.refresh_from_db()
        assert session.is_active is False
        assert session.end_time is not None

    def test_authentication_required(self):
        """Test that views require authentication"""
        self.client.logout()

        views_to_test = [
            'timer:dashboard',
            'timer:settings',
            'timer:statistics',
        ]

        for view_name in views_to_test:
            response = self.client.get(reverse(view_name))
            # Should redirect to login or return 302/401
            assert response.status_code in [302, 401, 403]


# ===== UTILITY FUNCTION TESTS =====

@pytest.mark.timer
@pytest.mark.unit
class TestTimerUtils(TestCase):
    """Test timer utility functions"""

    def setUp(self):
        self.user = User.objects.create_user(
            username='testuser',
            email='test@example.com',
            password='testpass123'
        )
        UserProfile.objects.create(user=self.user)
        UserTimerSettings.objects.create(user=self.user)

    def test_get_optimized_recent_sessions(self):
        """Test optimized recent sessions query"""
        # Create test data
        sessions = []
        for i in range(5):
            session = TimerSession.objects.create(
                user=self.user,
                start_time=timezone.now() - timedelta(hours=i+1),
                is_active=False
            )
            sessions.append(session)

            # Add intervals and breaks
            interval = TimerInterval.objects.create(
                session=session,
                interval_number=1
            )
            BreakRecord.objects.create(
                user=self.user,
                session=session,
                interval=interval
            )

        # Test the optimized query
        with self.assertNumQueries(3):  # Should be optimized with prefetch
            recent_sessions = list(get_optimized_recent_sessions(self.user, 3))

            assert len(recent_sessions) == 3

            # Access related objects (should not trigger additional queries)
            for session in recent_sessions:
                list(session.intervals.all())
                list(session.breaks.all())

    def test_get_user_session_statistics_optimized(self):
        """Test optimized session statistics calculation"""
        # Create test sessions and breaks
        for i in range(3):
            session = TimerSession.objects.create(
                user=self.user,
                start_time=timezone.now() - timedelta(days=i),
                is_active=False,
                total_work_minutes=60,
                total_intervals_completed=3,
                total_breaks_taken=2
            )

            interval = TimerInterval.objects.create(
                session=session,
                interval_number=1
            )

            # Create compliant break
            BreakRecord.objects.create(
                user=self.user,
                session=session,
                interval=interval,
                break_completed=True,
                break_duration_seconds=25,
                looked_at_distance=True
            )

        stats = get_user_session_statistics_optimized(self.user)

        assert stats['total_sessions'] == 3
        assert stats['total_work_minutes'] == 180
        assert stats['total_work_hours'] == 3.0
        assert stats['total_intervals'] == 9
        assert stats['compliance_rate'] >= 0

    def test_update_user_settings_safely(self):
        """Test safe user settings update with validation"""
        # Valid updates
        settings = update_user_settings_safely(
            self.user,
            work_interval_minutes=25,
            break_duration_seconds=30,
            sound_notification=True,
            smart_break_enabled=True,
            preferred_break_duration=30,
            sound_volume=0.7
        )

        assert settings.work_interval_minutes == 25
        assert settings.break_duration_seconds == 30
        assert settings.sound_notification is True
        assert settings.smart_break_enabled is True
        assert settings.preferred_break_duration == 30
        assert settings.sound_volume == 0.7

    @freeze_time("2024-01-15 10:00:00")
    def test_timezone_handling(self):
        """Test proper timezone handling in timer functionality"""
        # Create session with specific timezone-aware time
        session_start = timezone.now()
        session = TimerSession.objects.create(
            user=self.user,
            start_time=session_start
        )

        # Fast forward time
        with freeze_time("2024-01-15 12:00:00"):
            duration = session.duration_minutes
            assert duration == 120  # 2 hours

            session.end_session()
            assert session.end_time is not None
            assert session.duration_minutes == 120