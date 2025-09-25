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
from django.test.utils import override_settings
from django.db.models import Count, Sum, Avg
from freezegun import freeze_time
import json

from analytics.models import (
    DailyStats, WeeklyStats, MonthlyStats, UserBehaviorEvent,
    EngagementMetrics, UserSession, UserSatisfactionRating,
    RealTimeMetrics, LiveActivityFeed, PremiumAnalyticsReport, PremiumInsight
)
from accounts.models import User, UserProfile, UserLevel, UserStreakData
from timer.models import TimerSession, TimerInterval, BreakRecord, UserTimerSettings

User = get_user_model()


# ===== ANALYTICS MODELS TESTS =====

@pytest.mark.analytics
@pytest.mark.unit
class TestDailyStatsModel(TestCase):
    """Test DailyStats model functionality"""

    def setUp(self):
        self.user = User.objects.create_user(
            username='testuser',
            email='test@example.com',
            password='testpass123'
        )
        UserProfile.objects.create(user=self.user)

    def test_create_daily_stats(self):
        """Test creating daily statistics"""
        today = date.today()
        stats = DailyStats.objects.create(
            user=self.user,
            date=today,
            total_work_minutes=120,
            total_intervals_completed=6,
            total_breaks_taken=5,
            total_sessions=2,
            breaks_on_time=4,
            breaks_compliant=4,
            average_break_duration=22.5,
            streak_maintained=True,
            productivity_score=85.0
        )

        assert stats.user == self.user
        assert stats.date == today
        assert stats.total_work_minutes == 120
        assert stats.total_intervals_completed == 6
        assert stats.total_breaks_taken == 5
        assert stats.total_sessions == 2
        assert stats.breaks_on_time == 4
        assert stats.breaks_compliant == 4
        assert stats.average_break_duration == 22.5
        assert stats.streak_maintained is True
        assert stats.productivity_score == 85.0

    def test_compliance_rate_property(self):
        """Test compliance rate calculation"""
        stats = DailyStats.objects.create(
            user=self.user,
            date=date.today(),
            total_breaks_taken=10,
            breaks_compliant=8
        )

        assert stats.compliance_rate == 80.0

        # Test zero breaks
        stats.total_breaks_taken = 0
        stats.breaks_compliant = 0
        stats.save()
        assert stats.compliance_rate == 0.0

    def test_daily_stats_unique_constraint(self):
        """Test unique constraint on user and date"""
        today = date.today()
        DailyStats.objects.create(
            user=self.user,
            date=today,
            total_work_minutes=60
        )

        # Creating another stats record for same user and date should fail
        with self.assertRaises(IntegrityError):
            DailyStats.objects.create(
                user=self.user,
                date=today,
                total_work_minutes=120
            )

    def test_daily_stats_ordering(self):
        """Test default ordering by date descending"""
        # Create stats for multiple days
        dates = [
            date.today() - timedelta(days=2),
            date.today() - timedelta(days=1),
            date.today()
        ]

        stats_objects = []
        for d in dates:
            stats = DailyStats.objects.create(
                user=self.user,
                date=d,
                total_work_minutes=60
            )
            stats_objects.append(stats)

        # Get all stats and verify ordering
        all_stats = list(DailyStats.objects.filter(user=self.user))

        # Should be ordered by date descending (newest first)
        assert all_stats[0].date == dates[2]  # Today
        assert all_stats[1].date == dates[1]  # Yesterday
        assert all_stats[2].date == dates[0]  # Two days ago


@pytest.mark.analytics
@pytest.mark.unit
class TestWeeklyStatsModel(TestCase):
    """Test WeeklyStats model functionality"""

    def setUp(self):
        self.user = User.objects.create_user(
            username='testuser',
            email='test@example.com',
            password='testpass123'
        )

    def test_create_weekly_stats(self):
        """Test creating weekly statistics"""
        week_start = date.today() - timedelta(days=date.today().weekday())
        week_end = week_start + timedelta(days=6)

        weekly_stats = WeeklyStats.objects.create(
            user=self.user,
            week_start_date=week_start,
            week_end_date=week_end,
            total_work_minutes=600,
            total_intervals_completed=30,
            total_breaks_taken=25,
            total_sessions=10,
            active_days=5,
            average_daily_work_minutes=120.0,
            average_daily_breaks=5.0,
            total_breaks_compliant=20,
            weekly_compliance_rate=80.0,
            weekly_productivity_score=82.5
        )

        assert weekly_stats.user == self.user
        assert weekly_stats.week_start_date == week_start
        assert weekly_stats.week_end_date == week_end
        assert weekly_stats.total_work_minutes == 600
        assert weekly_stats.active_days == 5
        assert weekly_stats.weekly_compliance_rate == 80.0
        assert weekly_stats.weekly_productivity_score == 82.5

    def test_weekly_stats_unique_constraint(self):
        """Test unique constraint on user and week_start_date"""
        week_start = date.today() - timedelta(days=date.today().weekday())
        week_end = week_start + timedelta(days=6)

        WeeklyStats.objects.create(
            user=self.user,
            week_start_date=week_start,
            week_end_date=week_end
        )

        # Creating another record for same user and week should fail
        with self.assertRaises(IntegrityError):
            WeeklyStats.objects.create(
                user=self.user,
                week_start_date=week_start,
                week_end_date=week_end
            )


@pytest.mark.analytics
@pytest.mark.unit
class TestUserBehaviorEventModel(TestCase):
    """Test UserBehaviorEvent model functionality"""

    def setUp(self):
        self.user = User.objects.create_user(
            username='testuser',
            email='test@example.com',
            password='testpass123'
        )

    def test_create_behavior_event(self):
        """Test creating user behavior event"""
        event = UserBehaviorEvent.objects.create(
            user=self.user,
            event_type='session_start',
            event_data={'session_id': 123, 'work_interval': 20},
            session_id='session_abc123',
            user_agent='Mozilla/5.0 Test',
            ip_address='192.168.1.1'
        )

        assert event.user == self.user
        assert event.event_type == 'session_start'
        assert event.event_data['session_id'] == 123
        assert event.event_data['work_interval'] == 20
        assert event.session_id == 'session_abc123'
        assert event.user_agent == 'Mozilla/5.0 Test'
        assert event.ip_address == '192.168.1.1'
        assert event.timestamp is not None

    def test_behavior_event_types(self):
        """Test all available event types"""
        event_types = [
            'login', 'logout', 'session_start', 'session_end',
            'break_reminder_shown', 'break_taken', 'break_skipped',
            'settings_changed', 'subscription_upgraded', 'email_opened',
            'feature_used'
        ]

        for event_type in event_types:
            event = UserBehaviorEvent.objects.create(
                user=self.user,
                event_type=event_type,
                timestamp=timezone.now()
            )
            assert event.event_type == event_type


@pytest.mark.analytics
@pytest.mark.unit
class TestUserSessionModel(TestCase):
    """Test UserSession model for real-time tracking"""

    def setUp(self):
        self.user = User.objects.create_user(
            username='testuser',
            email='test@example.com',
            password='testpass123'
        )

    def test_create_user_session(self):
        """Test creating user session"""
        user_session = UserSession.objects.create(
            user=self.user,
            session_key='session_key_123',
            login_time=timezone.now() - timedelta(hours=1),
            last_activity=timezone.now(),
            is_active=True,
            ip_address='192.168.1.1',
            user_agent='Mozilla/5.0 Test',
            device_type='desktop',
            timer_sessions_started=3,
            breaks_taken_in_session=5,
            pages_viewed=15
        )

        assert user_session.user == self.user
        assert user_session.session_key == 'session_key_123'
        assert user_session.is_active is True
        assert user_session.device_type == 'desktop'
        assert user_session.timer_sessions_started == 3
        assert user_session.breaks_taken_in_session == 5
        assert user_session.pages_viewed == 15

    def test_user_session_duration_property(self):
        """Test session duration calculation"""
        login_time = timezone.now() - timedelta(hours=2)
        user_session = UserSession.objects.create(
            user=self.user,
            session_key='test_session',
            login_time=login_time,
            last_activity=timezone.now()
        )

        # Duration should be approximately 120 minutes
        duration = user_session.session_duration
        assert 115 <= duration <= 125  # Allow some variance

        # Test with logout time
        user_session.logout_time = login_time + timedelta(hours=1)
        user_session.save()
        assert user_session.session_duration == 60

    def test_get_active_users_count(self):
        """Test class method for counting active users"""
        # Create active sessions
        for i in range(3):
            UserSession.objects.create(
                user=self.user,
                session_key=f'session_{i}',
                is_active=True,
                last_activity=timezone.now()
            )

        # Create inactive session
        UserSession.objects.create(
            user=self.user,
            session_key='inactive_session',
            is_active=False,
            last_activity=timezone.now()
        )

        # Create old active session (should not count)
        UserSession.objects.create(
            user=self.user,
            session_key='old_session',
            is_active=True,
            last_activity=timezone.now() - timedelta(minutes=10)
        )

        active_count = UserSession.get_active_users_count()
        assert active_count == 3  # Only recent active sessions


@pytest.mark.analytics
@pytest.mark.unit
class TestUserSatisfactionRatingModel(TestCase):
    """Test UserSatisfactionRating model functionality"""

    def setUp(self):
        self.user = User.objects.create_user(
            username='testuser',
            email='test@example.com',
            password='testpass123'
        )

    def test_create_satisfaction_rating(self):
        """Test creating satisfaction rating"""
        rating = UserSatisfactionRating.objects.create(
            user=self.user,
            rating=4,
            context='session_end',
            feedback_text='Great app, very helpful!',
            ease_of_use_rating=5,
            effectiveness_rating=4,
            reminder_helpfulness=4,
            would_recommend=True,
            recommendation_score=8,
            session_id='session_123',
            break_count_when_rated=5,
            days_since_signup=30
        )

        assert rating.user == self.user
        assert rating.rating == 4
        assert rating.context == 'session_end'
        assert rating.feedback_text == 'Great app, very helpful!'
        assert rating.ease_of_use_rating == 5
        assert rating.effectiveness_rating == 4
        assert rating.would_recommend is True
        assert rating.recommendation_score == 8
        assert rating.days_since_signup == 30

    def test_get_average_satisfaction(self):
        """Test class method for average satisfaction"""
        # Create ratings from last 30 days
        ratings_data = [5, 4, 3, 4, 5, 3, 4]
        for i, rating_value in enumerate(ratings_data):
            UserSatisfactionRating.objects.create(
                user=self.user,
                rating=rating_value,
                rating_date=timezone.now() - timedelta(days=i)
            )

        # Create old rating (should not be included)
        UserSatisfactionRating.objects.create(
            user=self.user,
            rating=1,
            rating_date=timezone.now() - timedelta(days=40)
        )

        avg_satisfaction = UserSatisfactionRating.get_average_satisfaction(30)
        expected_avg = sum(ratings_data) / len(ratings_data)
        assert abs(avg_satisfaction - expected_avg) < 0.1

    def test_get_nps_score(self):
        """Test Net Promoter Score calculation"""
        # Create ratings with recommendation scores
        # Promoters (9-10): 2 ratings
        # Passives (7-8): 1 rating
        # Detractors (0-6): 2 ratings
        recommendation_scores = [10, 9, 8, 6, 5]

        for score in recommendation_scores:
            UserSatisfactionRating.objects.create(
                user=self.user,
                rating=4,
                recommendation_score=score,
                rating_date=timezone.now()
            )

        nps = UserSatisfactionRating.get_nps_score(30)
        # NPS = (Promoters - Detractors) / Total * 100
        # NPS = (2 - 2) / 5 * 100 = 0
        assert nps == 0.0


@pytest.mark.analytics
@pytest.mark.unit
class TestRealTimeMetricsModel(TestCase):
    """Test RealTimeMetrics model functionality"""

    def setUp(self):
        self.user = User.objects.create_user(
            username='testuser',
            email='test@example.com',
            password='testpass123'
        )

    def test_create_real_time_metrics(self):
        """Test creating real-time metrics"""
        metrics = RealTimeMetrics.objects.create(
            active_users_count=25,
            active_sessions_count=30,
            users_in_break=5,
            users_working=20,
            total_breaks_today=150,
            total_work_minutes_today=2400,
            total_sessions_today=75,
            average_satisfaction_rating=4.2,
            nps_score=45.5,
            server_response_time_ms=150,
            database_query_time_ms=25
        )

        assert metrics.active_users_count == 25
        assert metrics.active_sessions_count == 30
        assert metrics.users_in_break == 5
        assert metrics.users_working == 20
        assert metrics.total_breaks_today == 150
        assert metrics.total_work_minutes_today == 2400
        assert metrics.total_sessions_today == 75
        assert metrics.average_satisfaction_rating == 4.2
        assert metrics.nps_score == 45.5
        assert metrics.server_response_time_ms == 150
        assert metrics.database_query_time_ms == 25

    def test_get_latest_metrics(self):
        """Test getting latest metrics"""
        # Create multiple metrics records
        old_metrics = RealTimeMetrics.objects.create(
            active_users_count=10,
            timestamp=timezone.now() - timedelta(hours=1)
        )

        latest_metrics = RealTimeMetrics.objects.create(
            active_users_count=25,
            timestamp=timezone.now()
        )

        retrieved_metrics = RealTimeMetrics.get_latest_metrics()
        assert retrieved_metrics.active_users_count == 25
        assert retrieved_metrics.id == latest_metrics.id


@pytest.mark.analytics
@pytest.mark.unit
class TestPremiumAnalyticsReportModel(TestCase):
    """Test PremiumAnalyticsReport model functionality"""

    def setUp(self):
        self.user = User.objects.create_user(
            username='testuser',
            email='test@example.com',
            password='testpass123',
            subscription_type='premium'
        )

    def test_create_premium_report(self):
        """Test creating premium analytics report"""
        start_date = date.today() - timedelta(days=30)
        end_date = date.today()

        report = PremiumAnalyticsReport.objects.create(
            user=self.user,
            report_type='monthly',
            report_period_start=start_date,
            report_period_end=end_date,
            total_sessions=45,
            total_work_hours=90.0,
            total_breaks=180,
            compliance_rate=82.5,
            productivity_score=85.0,
            peak_productivity_hours=[9, 10, 14],
            most_productive_days=['Monday', 'Tuesday'],
            break_patterns={'morning': 0.3, 'afternoon': 0.7},
            improvement_suggestions=[
                {'type': 'timing', 'message': 'Consider morning sessions'}
            ],
            estimated_eye_strain_reduction=75.0,
            estimated_productivity_boost=12.5,
            health_score=88.0,
            vs_previous_period={'sessions': 15.2, 'compliance': 5.1},
            is_generated=True,
            generated_at=timezone.now(),
            generation_time_seconds=3
        )

        assert report.user == self.user
        assert report.report_type == 'monthly'
        assert report.report_period_start == start_date
        assert report.report_period_end == end_date
        assert report.total_sessions == 45
        assert report.total_work_hours == 90.0
        assert report.compliance_rate == 82.5
        assert report.productivity_score == 85.0
        assert report.peak_productivity_hours == [9, 10, 14]
        assert report.most_productive_days == ['Monday', 'Tuesday']
        assert report.health_score == 88.0
        assert report.is_generated is True


@pytest.mark.analytics
@pytest.mark.unit
class TestPremiumInsightModel(TestCase):
    """Test PremiumInsight model functionality"""

    def setUp(self):
        self.user = User.objects.create_user(
            username='testuser',
            email='test@example.com',
            password='testpass123',
            subscription_type='premium'
        )

    def test_create_premium_insight(self):
        """Test creating premium insight"""
        insight = PremiumInsight.objects.create(
            user=self.user,
            insight_type='pattern',
            title='You work best in the morning',
            description='Your productivity peaks between 9-11 AM with 85% compliance rate.',
            action_suggestion='Schedule important tasks during morning hours.',
            supporting_data={
                'morning_compliance': 0.85,
                'afternoon_compliance': 0.65,
                'peak_hours': [9, 10, 11]
            },
            confidence_score=0.92,
            priority='high',
            expires_at=timezone.now() + timedelta(days=7)
        )

        assert insight.user == self.user
        assert insight.insight_type == 'pattern'
        assert insight.title == 'You work best in the morning'
        assert insight.confidence_score == 0.92
        assert insight.priority == 'high'
        assert insight.supporting_data['morning_compliance'] == 0.85
        assert insight.is_active is True
        assert insight.viewed_at is None
        assert insight.dismissed_at is None

    def test_mark_as_viewed(self):
        """Test marking insight as viewed"""
        insight = PremiumInsight.objects.create(
            user=self.user,
            insight_type='achievement',
            title='Test insight',
            description='Test description'
        )

        assert insight.viewed_at is None

        insight.mark_as_viewed()

        assert insight.viewed_at is not None

        # Calling again should not change the viewed_at time
        first_viewed_at = insight.viewed_at
        insight.mark_as_viewed()
        assert insight.viewed_at == first_viewed_at

    def test_dismiss_insight(self):
        """Test dismissing insight"""
        insight = PremiumInsight.objects.create(
            user=self.user,
            insight_type='recommendation',
            title='Test insight',
            description='Test description',
            is_active=True
        )

        assert insight.is_active is True
        assert insight.dismissed_at is None

        insight.dismiss()

        assert insight.is_active is False
        assert insight.dismissed_at is not None


# ===== ANALYTICS INTEGRATION TESTS =====

@pytest.mark.analytics
@pytest.mark.integration
class TestAnalyticsIntegration(TestCase):
    """Test analytics integration with timer functionality"""

    def setUp(self):
        self.user = User.objects.create_user(
            username='testuser',
            email='test@example.com',
            password='testpass123'
        )
        UserProfile.objects.create(user=self.user)
        UserTimerSettings.objects.create(user=self.user)

    def test_daily_stats_update_on_session_completion(self):
        """Test that daily stats are updated when session is completed"""
        # Create timer session
        session = TimerSession.objects.create(
            user=self.user,
            start_time=timezone.now() - timedelta(hours=2),
            end_time=timezone.now(),
            is_active=False,
            total_work_minutes=120,
            total_intervals_completed=6,
            total_breaks_taken=5
        )

        # Create intervals and breaks
        for i in range(6):
            interval = TimerInterval.objects.create(
                session=session,
                interval_number=i + 1,
                status='completed'
            )

            if i < 5:  # 5 breaks for 6 intervals
                BreakRecord.objects.create(
                    user=self.user,
                    session=session,
                    interval=interval,
                    break_completed=True,
                    break_duration_seconds=25,
                    looked_at_distance=True
                )

        # Check if daily stats exist or create them
        today = timezone.now().date()
        daily_stats, created = DailyStats.objects.get_or_create(
            user=self.user,
            date=today,
            defaults={
                'total_work_minutes': session.total_work_minutes,
                'total_intervals_completed': session.total_intervals_completed,
                'total_breaks_taken': session.total_breaks_taken,
                'total_sessions': 1
            }
        )

        if not created:
            # Update existing stats
            daily_stats.total_work_minutes += session.total_work_minutes
            daily_stats.total_intervals_completed += session.total_intervals_completed
            daily_stats.total_breaks_taken += session.total_breaks_taken
            daily_stats.total_sessions += 1
            daily_stats.save()

        # Verify stats were updated
        daily_stats.refresh_from_db()
        assert daily_stats.total_work_minutes >= 120
        assert daily_stats.total_intervals_completed >= 6
        assert daily_stats.total_breaks_taken >= 5
        assert daily_stats.total_sessions >= 1

    def test_real_time_metrics_calculation(self):
        """Test real-time metrics calculation"""
        # Create active sessions
        active_session = TimerSession.objects.create(
            user=self.user,
            is_active=True
        )

        # Create user session
        user_session = UserSession.objects.create(
            user=self.user,
            session_key='test_session',
            is_active=True,
            last_activity=timezone.now(),
            timer_sessions_started=1,
            breaks_taken_in_session=2
        )

        # Create break records for today
        today = timezone.now().date()
        interval = TimerInterval.objects.create(
            session=active_session,
            interval_number=1
        )

        BreakRecord.objects.create(
            user=self.user,
            session=active_session,
            interval=interval,
            break_start_time=timezone.now(),
            break_completed=True
        )

        # Create real-time metrics
        metrics = RealTimeMetrics.objects.create()

        # Update metrics manually (would be done by background task)
        metrics.active_users_count = UserSession.get_active_users_count()
        metrics.total_breaks_today = BreakRecord.objects.filter(
            break_start_time__date=today
        ).count()
        metrics.save()

        assert metrics.active_users_count >= 1
        assert metrics.total_breaks_today >= 1

    def test_premium_analytics_report_generation(self):
        """Test premium analytics report generation"""
        # Make user premium
        self.user.subscription_type = 'premium'
        self.user.save()

        # Create session data for report
        start_date = date.today() - timedelta(days=7)
        end_date = date.today()

        for i in range(7):
            day = start_date + timedelta(days=i)
            session_start = timezone.make_aware(
                datetime.combine(day, datetime.min.time()) + timedelta(hours=9)
            )

            session = TimerSession.objects.create(
                user=self.user,
                start_time=session_start,
                end_time=session_start + timedelta(hours=2),
                is_active=False,
                total_work_minutes=120,
                total_intervals_completed=6,
                total_breaks_taken=5
            )

        # Create report
        report = PremiumAnalyticsReport.objects.create(
            user=self.user,
            report_type='weekly',
            report_period_start=start_date,
            report_period_end=end_date
        )

        # Generate report
        report.generate_report()

        # Verify report was generated
        assert report.is_generated is True
        assert report.total_sessions >= 7
        assert report.total_work_hours >= 14.0
        assert report.productivity_score >= 0


# ===== ANALYTICS PERFORMANCE TESTS =====

@pytest.mark.analytics
@pytest.mark.performance
@pytest.mark.slow
class TestAnalyticsPerformance(TestCase):
    """Test analytics performance with large datasets"""

    def setUp(self):
        self.user = User.objects.create_user(
            username='testuser',
            email='test@example.com',
            password='testpass123'
        )
        UserProfile.objects.create(user=self.user)

    def test_daily_stats_aggregation_performance(self):
        """Test performance of daily stats aggregation"""
        # Create large dataset (30 days of data)
        for i in range(30):
            day = date.today() - timedelta(days=i)
            DailyStats.objects.create(
                user=self.user,
                date=day,
                total_work_minutes=120 + (i % 60),
                total_intervals_completed=6 + (i % 3),
                total_breaks_taken=5 + (i % 2),
                total_sessions=2,
                breaks_compliant=4 + (i % 2),
                productivity_score=80.0 + (i % 20)
            )

        # Test aggregation query performance
        import time
        start_time = time.time()

        # Aggregate stats for last 30 days
        stats = DailyStats.objects.filter(
            user=self.user,
            date__gte=date.today() - timedelta(days=30)
        ).aggregate(
            total_work_minutes=Sum('total_work_minutes'),
            total_intervals=Sum('total_intervals_completed'),
            total_breaks=Sum('total_breaks_taken'),
            total_sessions=Sum('total_sessions'),
            avg_productivity=Avg('productivity_score')
        )

        end_time = time.time()
        query_time = end_time - start_time

        # Should complete quickly
        assert query_time < 0.5  # Less than 500ms
        assert stats['total_work_minutes'] > 3000  # Should have substantial data
        assert stats['avg_productivity'] is not None

    def test_user_behavior_events_query_performance(self):
        """Test performance of user behavior events queries"""
        # Create many behavior events
        event_types = ['login', 'session_start', 'break_taken', 'session_end']

        for i in range(1000):
            UserBehaviorEvent.objects.create(
                user=self.user,
                event_type=event_types[i % len(event_types)],
                timestamp=timezone.now() - timedelta(hours=i % 24)
            )

        # Test query performance
        import time
        start_time = time.time()

        # Query recent events with aggregation
        event_counts = UserBehaviorEvent.objects.filter(
            user=self.user,
            timestamp__gte=timezone.now() - timedelta(days=7)
        ).values('event_type').annotate(
            count=Count('id')
        ).order_by('-count')

        # Force evaluation
        list(event_counts)

        end_time = time.time()
        query_time = end_time - start_time

        # Should complete quickly even with many records
        assert query_time < 1.0  # Less than 1 second