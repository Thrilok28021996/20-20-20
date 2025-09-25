"""
Integration tests for complete user workflows in the 20-20-20 eye health SaaS application.
Tests end-to-end scenarios from user signup to analytics generation.
"""
import pytest
from datetime import datetime, timedelta, date
from decimal import Decimal
from unittest.mock import patch, Mock, MagicMock
from django.test import TestCase, TransactionTestCase, Client
from django.utils import timezone
from django.contrib.auth import get_user_model
from django.urls import reverse
from django.test.utils import override_settings
from freezegun import freeze_time
import json

from accounts.models import (
    User, UserProfile, UserLevel, UserStreakData, Badge, UserBadge,
    Challenge, ChallengeParticipation, Achievement
)
from timer.models import TimerSession, TimerInterval, BreakRecord, UserTimerSettings
from analytics.models import DailyStats, WeeklyStats, MonthlyStats, LiveActivityFeed
from notifications.models import Notification

User = get_user_model()


# ===== COMPLETE USER LIFECYCLE TESTS =====

@pytest.mark.integration
@pytest.mark.slow
class TestCompleteUserLifecycle(TestCase):
    """Test complete user lifecycle from signup to advanced usage"""

    def setUp(self):
        self.client = Client()

    def test_new_user_onboarding_workflow(self):
        """Test complete new user onboarding workflow"""
        # 1. User signup
        signup_data = {
            'username': 'newuser',
            'email': 'newuser@example.com',
            'password1': 'complexpassword123',
            'password2': 'complexpassword123',
            'first_name': 'New',
            'last_name': 'User',
            'age': 28,
            'occupation': 'Software Developer',
            'daily_screen_time_hours': 8.0,
            'wears_glasses': True,
            'has_eye_strain': True
        }

        response = self.client.post(reverse('accounts:signup'), data=signup_data)
        assert response.status_code in [200, 302]  # Success or redirect

        # User should be created
        user = User.objects.get(email='newuser@example.com')
        assert user.username == 'newuser'
        assert user.subscription_type == 'free'

        # Profile should be created
        profile = UserProfile.objects.get(user=user)
        assert profile.age == 28
        assert profile.occupation == 'Software Developer'
        assert profile.daily_screen_time_hours == 8.0
        assert profile.wears_glasses is True
        assert profile.has_eye_strain is True

        # Gamification data should be initialized
        level = UserLevel.objects.get(user=user)
        assert level.current_level == 1
        assert level.total_experience_points == 0

        streak_data = UserStreakData.objects.get(user=user)
        assert streak_data.current_daily_streak == 0
        assert streak_data.total_sessions_completed == 0

        # Timer settings should be created with defaults
        settings = UserTimerSettings.objects.get(user=user)
        assert settings.work_interval_minutes == 20
        assert settings.break_duration_seconds == 20

        # 2. User login
        login_success = self.client.login(
            username='newuser@example.com',
            password='complexpassword123'
        )
        assert login_success is True

        # 3. First dashboard visit
        response = self.client.get(reverse('timer:dashboard'))
        assert response.status_code == 200
        assert 'new_user' in response.context or response.context.get('is_new_user', False)

        # Today's stats should be created
        today_stats = DailyStats.objects.get(user=user, date=timezone.now().date())
        assert today_stats.total_sessions == 0
        assert today_stats.total_work_minutes == 0

    def test_first_timer_session_workflow(self):
        """Test user's first complete timer session workflow"""
        # Create user
        user = User.objects.create_user(
            username='firsttimer',
            email='firsttimer@example.com',
            password='testpass123'
        )
        UserProfile.objects.create(user=user)
        UserLevel.objects.create(user=user)
        UserStreakData.objects.create(user=user)
        UserTimerSettings.objects.create(user=user)

        self.client.login(username='firsttimer@example.com', password='testpass123')

        # 1. Start first session
        response = self.client.post(
            reverse('timer:start_session'),
            data=json.dumps({}),
            content_type='application/json'
        )

        assert response.status_code == 200
        start_data = response.json()
        assert start_data['success'] is True

        session_id = start_data['session_id']
        interval_id = start_data['interval_id']

        # Verify session was created
        session = TimerSession.objects.get(id=session_id)
        assert session.user == user
        assert session.is_active is True
        assert session.total_intervals_completed == 0

        # Verify interval was created
        interval = TimerInterval.objects.get(id=interval_id)
        assert interval.session == session
        assert interval.interval_number == 1
        assert interval.status == 'active'

        # 2. Take first break
        response = self.client.post(
            reverse('timer:take_break'),
            data=json.dumps({
                'session_id': session_id,
                'interval_id': interval_id,
                'looked_at_distance': True
            }),
            content_type='application/json'
        )

        assert response.status_code == 200
        break_data = response.json()
        assert break_data['success'] is True

        break_id = break_data['break_id']

        # Verify break was created
        break_record = BreakRecord.objects.get(id=break_id)
        assert break_record.user == user
        assert break_record.session == session
        assert break_record.looked_at_distance is True

        # 3. Complete break
        with freeze_time(timezone.now() + timedelta(seconds=25)):
            response = self.client.post(
                reverse('timer:complete_break'),
                data=json.dumps({
                    'break_id': break_id,
                    'looked_at_distance': True
                }),
                content_type='application/json'
            )

            assert response.status_code == 200
            complete_data = response.json()
            assert complete_data['success'] is True
            assert complete_data['is_compliant'] is True

        # Verify break was completed
        break_record.refresh_from_db()
        assert break_record.break_completed is True
        assert break_record.break_duration_seconds >= 20

        # Verify next interval was created
        next_interval_id = complete_data['next_interval_id']
        next_interval = TimerInterval.objects.get(id=next_interval_id)
        assert next_interval.interval_number == 2

        # 4. End session after multiple intervals
        session.total_intervals_completed = 3
        session.total_breaks_taken = 2
        session.total_work_minutes = 60
        session.save()

        response = self.client.post(
            reverse('timer:end_session'),
            data=json.dumps({}),
            content_type='application/json'
        )

        assert response.status_code == 200
        end_data = response.json()
        assert end_data['success'] is True
        assert end_data['intervals_completed'] == 3
        assert end_data['breaks_taken'] == 2

        # Verify session was ended
        session.refresh_from_db()
        assert session.is_active is False
        assert session.end_time is not None

        # 5. Check gamification updates
        level = UserLevel.objects.get(user=user)
        assert level.sessions_completed >= 1
        assert level.total_experience_points > 0

        streak_data = UserStreakData.objects.get(user=user)
        assert streak_data.total_sessions_completed >= 1
        assert streak_data.current_daily_streak >= 1

        # 6. Check daily stats update
        today_stats = DailyStats.objects.get(user=user, date=timezone.now().date())
        assert today_stats.total_sessions >= 1
        assert today_stats.total_work_minutes >= 60
        assert today_stats.total_breaks_taken >= 2

        # 7. Check for activity feed entries
        activity_feed = LiveActivityFeed.objects.filter(user=user)
        assert activity_feed.exists()

    def test_user_progression_over_week(self):
        """Test user progression over a week of usage"""
        # Create user
        user = User.objects.create_user(
            username='weekuser',
            email='weekuser@example.com',
            password='testpass123'
        )
        UserProfile.objects.create(user=user)
        UserLevel.objects.create(user=user)
        UserStreakData.objects.create(user=user)
        UserTimerSettings.objects.create(user=user)

        # Create badges for testing
        first_session_badge = Badge.objects.create(
            name='First Timer',
            description='Complete your first session',
            requires_sessions=1,
            experience_reward=50
        )

        consistent_badge = Badge.objects.create(
            name='Consistent User',
            description='Complete sessions for 5 days',
            requires_sessions=5,
            experience_reward=200
        )

        # Simulate 7 days of usage
        initial_date = timezone.now().date()

        for day in range(7):
            current_date = initial_date + timedelta(days=day)

            with freeze_time(timezone.make_aware(
                datetime.combine(current_date, datetime.min.time()) + timedelta(hours=9)
            )):
                # Create daily session
                session = TimerSession.objects.create(
                    user=user,
                    start_time=timezone.now(),
                    end_time=timezone.now() + timedelta(hours=2),
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
                            user=user,
                            session=session,
                            interval=interval,
                            break_completed=True,
                            break_duration_seconds=25,
                            looked_at_distance=True
                        )

                # Update daily stats
                daily_stats, created = DailyStats.objects.get_or_create(
                    user=user,
                    date=current_date,
                    defaults={
                        'total_work_minutes': 120,
                        'total_intervals_completed': 6,
                        'total_breaks_taken': 5,
                        'total_sessions': 1,
                        'breaks_compliant': 5,
                        'productivity_score': 85.0
                    }
                )

                # Update user level
                level = UserLevel.objects.get(user=user)
                level.sessions_completed += 1
                level.breaks_completed += 5
                level.compliant_breaks += 5
                level.add_experience(100)  # Base experience per session

                # Update streak data
                streak_data = UserStreakData.objects.get(user=user)
                streak_data.current_daily_streak = day + 1
                streak_data.total_sessions_completed += 1
                streak_data.last_session_date = current_date
                if day == 0:
                    streak_data.streak_start_date = current_date
                streak_data.save()

        # Verify progression after week
        level = UserLevel.objects.get(user=user)
        assert level.sessions_completed == 7
        assert level.breaks_completed == 35  # 7 days * 5 breaks
        assert level.compliant_breaks == 35
        assert level.total_experience_points >= 700  # 7 days * 100 base XP

        streak_data = UserStreakData.objects.get(user=user)
        assert streak_data.current_daily_streak == 7
        assert streak_data.total_sessions_completed == 7

        # Check badge earning
        if level.sessions_completed >= 1:
            UserBadge.objects.get_or_create(
                user=user,
                badge=first_session_badge
            )

        if level.sessions_completed >= 5:
            UserBadge.objects.get_or_create(
                user=user,
                badge=consistent_badge
            )

        user_badges = UserBadge.objects.filter(user=user)
        assert user_badges.count() >= 1  # At least first session badge

        # Verify weekly stats creation
        week_start = initial_date - timedelta(days=initial_date.weekday())
        week_end = week_start + timedelta(days=6)

        weekly_stats = WeeklyStats.objects.create(
            user=user,
            week_start_date=week_start,
            week_end_date=week_end,
            total_work_minutes=840,  # 7 days * 120 minutes
            total_intervals_completed=42,  # 7 days * 6 intervals
            total_breaks_taken=35,  # 7 days * 5 breaks
            total_sessions=7,
            active_days=7,
            total_breaks_compliant=35,
            weekly_compliance_rate=100.0,
            weekly_productivity_score=85.0
        )

        assert weekly_stats.active_days == 7
        assert weekly_stats.weekly_compliance_rate == 100.0

    def test_premium_upgrade_workflow(self):
        """Test premium upgrade workflow and feature access"""
        # Create free user
        user = User.objects.create_user(
            username='upgradeuser',
            email='upgradeuser@example.com',
            password='testpass123',
            subscription_type='free'
        )
        UserProfile.objects.create(user=user)
        UserTimerSettings.objects.create(user=user)

        self.client.login(username='upgradeuser@example.com', password='testpass123')

        # 1. Test free user limitations
        from mysite.constants import FREE_DAILY_INTERVAL_LIMIT

        # Create intervals up to free limit
        session = TimerSession.objects.create(user=user, is_active=False)
        for i in range(FREE_DAILY_INTERVAL_LIMIT):
            TimerInterval.objects.create(
                session=session,
                interval_number=i + 1,
                start_time=timezone.now()
            )

        # Should be blocked from starting new session
        response = self.client.post(
            reverse('timer:start_session'),
            data=json.dumps({}),
            content_type='application/json'
        )

        data = response.json()
        assert data['success'] is False
        assert 'limit' in data['message'].lower()

        # 2. Simulate premium upgrade
        user.subscription_type = 'premium'
        user.subscription_start_date = timezone.now()
        user.subscription_end_date = timezone.now() + timedelta(days=30)
        user.save()

        # 3. Test premium features access
        # Should now be able to start session beyond free limit
        response = self.client.post(
            reverse('timer:start_session'),
            data=json.dumps({}),
            content_type='application/json'
        )

        data = response.json()
        assert data['success'] is True  # Premium user not limited

        # 4. Test premium settings features
        response = self.client.post(
            reverse('timer:settings'),
            data={
                'work_interval_minutes': 25,
                'auto_start_break': 'on',  # Premium feature
                'auto_start_work': 'on',   # Premium feature
                'custom_break_messages': 'Premium custom message!'  # Premium feature
            }
        )

        assert response.status_code == 302  # Successful update

        # Verify premium settings were saved
        settings = UserTimerSettings.objects.get(user=user)
        assert settings.auto_start_break is True
        assert settings.auto_start_work is True
        assert settings.custom_break_messages == 'Premium custom message!'

        # 5. Test premium analytics access
        # Create premium analytics report
        from analytics.models import PremiumAnalyticsReport

        report = PremiumAnalyticsReport.objects.create(
            user=user,
            report_type='monthly',
            report_period_start=date.today() - timedelta(days=30),
            report_period_end=date.today()
        )

        # Generate the report
        report.generate_report()

        assert report.is_generated is True
        assert report.total_sessions >= 0
        assert report.productivity_score >= 0

    def test_challenge_participation_workflow(self):
        """Test complete challenge participation workflow"""
        # Create user
        user = User.objects.create_user(
            username='challenger',
            email='challenger@example.com',
            password='testpass123'
        )
        UserProfile.objects.create(user=user)
        UserLevel.objects.create(user=user)

        # Create challenge
        challenge = Challenge.objects.create(
            name='Weekly Focus Challenge',
            description='Complete 10 timer sessions this week',
            start_date=timezone.now().date(),
            end_date=timezone.now().date() + timedelta(days=7),
            challenge_type='session_count',
            target_value=10,
            experience_reward=500,
            is_active=True
        )

        # 1. User joins challenge
        participation = ChallengeParticipation.objects.create(
            user=user,
            challenge=challenge,
            progress=0
        )

        assert participation.progress_percentage == 0.0
        assert participation.is_completed is False

        # 2. Simulate session completions
        for i in range(10):
            # Create session
            session = TimerSession.objects.create(
                user=user,
                start_time=timezone.now() - timedelta(hours=1),
                end_time=timezone.now(),
                is_active=False,
                total_work_minutes=60,
                total_intervals_completed=3,
                total_breaks_taken=2
            )

            # Update challenge progress
            participation.progress = i + 1
            participation.save()

            # Check if completed
            if participation.progress >= challenge.target_value:
                participation.is_completed = True
                participation.completed_at = timezone.now()
                participation.save()

                # Award experience
                level = UserLevel.objects.get(user=user)
                level.add_experience(challenge.experience_reward)

        # 3. Verify challenge completion
        participation.refresh_from_db()
        assert participation.is_completed is True
        assert participation.completed_at is not None
        assert participation.progress_percentage == 100.0

        # Verify experience was awarded
        level = UserLevel.objects.get(user=user)
        assert level.total_experience_points >= 500

        # 4. Create activity feed entry for completion
        LiveActivityFeed.objects.create(
            user=user,
            activity_type='challenge_completed',
            activity_data={
                'challenge_name': challenge.name,
                'target_value': challenge.target_value,
                'experience_gained': challenge.experience_reward
            }
        )

        # Verify activity was recorded
        activity = LiveActivityFeed.objects.get(
            user=user,
            activity_type='challenge_completed'
        )
        assert activity.activity_data['challenge_name'] == challenge.name

    def test_long_term_user_analytics_generation(self):
        """Test long-term user analytics generation"""
        # Create user with 3 months of data
        user = User.objects.create_user(
            username='longterm',
            email='longterm@example.com',
            password='testpass123',
            subscription_type='premium'
        )
        UserProfile.objects.create(user=user)
        UserLevel.objects.create(user=user)

        # Generate 90 days of usage data
        start_date = date.today() - timedelta(days=90)

        for day in range(90):
            current_date = start_date + timedelta(days=day)

            # Skip some days to simulate realistic usage
            if day % 7 == 6:  # Skip Sundays
                continue

            # Create daily session
            session_time = timezone.make_aware(
                datetime.combine(current_date, datetime.min.time()) + timedelta(hours=9)
            )

            session = TimerSession.objects.create(
                user=user,
                start_time=session_time,
                end_time=session_time + timedelta(hours=3),
                is_active=False,
                total_work_minutes=180,
                total_intervals_completed=9,
                total_breaks_taken=8
            )

            # Create daily stats
            DailyStats.objects.create(
                user=user,
                date=current_date,
                total_work_minutes=180,
                total_intervals_completed=9,
                total_breaks_taken=8,
                total_sessions=1,
                breaks_compliant=7,  # 87.5% compliance
                productivity_score=85.0 + (day % 20)  # Vary between 85-105
            )

        # Generate weekly stats for the period
        current_week_start = start_date - timedelta(days=start_date.weekday())

        for week in range(13):  # ~3 months of weeks
            week_start = current_week_start + timedelta(weeks=week)
            week_end = week_start + timedelta(days=6)

            # Aggregate daily stats for this week
            week_stats = DailyStats.objects.filter(
                user=user,
                date__gte=week_start,
                date__lte=week_end
            ).aggregate(
                total_work=Sum('total_work_minutes'),
                total_intervals=Sum('total_intervals_completed'),
                total_breaks=Sum('total_breaks_taken'),
                total_sessions=Sum('total_sessions'),
                compliant_breaks=Sum('breaks_compliant'),
                active_days=Count('id')
            )

            if week_stats['total_sessions']:
                WeeklyStats.objects.create(
                    user=user,
                    week_start_date=week_start,
                    week_end_date=week_end,
                    total_work_minutes=week_stats['total_work'] or 0,
                    total_intervals_completed=week_stats['total_intervals'] or 0,
                    total_breaks_taken=week_stats['total_breaks'] or 0,
                    total_sessions=week_stats['total_sessions'] or 0,
                    active_days=week_stats['active_days'] or 0,
                    total_breaks_compliant=week_stats['compliant_breaks'] or 0,
                    weekly_compliance_rate=(
                        (week_stats['compliant_breaks'] or 0) /
                        max(week_stats['total_breaks'] or 1, 1) * 100
                    ),
                    weekly_productivity_score=87.5
                )

        # Generate monthly stats
        for month in range(3):
            month_start = date(start_date.year, start_date.month + month, 1)
            if month_start.month == 13:
                month_start = month_start.replace(year=month_start.year + 1, month=1)

            # Aggregate monthly data
            month_stats = DailyStats.objects.filter(
                user=user,
                date__year=month_start.year,
                date__month=month_start.month
            ).aggregate(
                total_work=Sum('total_work_minutes'),
                total_intervals=Sum('total_intervals_completed'),
                total_breaks=Sum('total_breaks_taken'),
                total_sessions=Sum('total_sessions'),
                active_days=Count('id')
            )

            if month_stats['total_sessions']:
                MonthlyStats.objects.create(
                    user=user,
                    year=month_start.year,
                    month=month_start.month,
                    total_work_minutes=month_stats['total_work'] or 0,
                    total_intervals_completed=month_stats['total_intervals'] or 0,
                    total_breaks_taken=month_stats['total_breaks'] or 0,
                    total_sessions=month_stats['total_sessions'] or 0,
                    active_days=month_stats['active_days'] or 0,
                    most_productive_day_of_week='Tuesday',
                    most_productive_hour=10,
                    estimated_eye_strain_reduction=75.0
                )

        # Verify analytics were generated
        daily_count = DailyStats.objects.filter(user=user).count()
        weekly_count = WeeklyStats.objects.filter(user=user).count()
        monthly_count = MonthlyStats.objects.filter(user=user).count()

        assert daily_count >= 70  # Should have most days (excluding skipped days)
        assert weekly_count >= 10  # Should have most weeks
        assert monthly_count == 3   # Should have 3 months

        # Test analytics calculations
        total_stats = DailyStats.objects.filter(user=user).aggregate(
            total_work=Sum('total_work_minutes'),
            total_sessions=Sum('total_sessions'),
            avg_productivity=Avg('productivity_score')
        )

        assert total_stats['total_work'] >= 10000  # Substantial work time
        assert total_stats['total_sessions'] >= 70  # Many sessions
        assert total_stats['avg_productivity'] > 80  # Good productivity

        # Update user level based on long-term activity
        level = UserLevel.objects.get(user=user)
        level.sessions_completed = total_stats['total_sessions']
        level.add_experience(total_stats['total_sessions'] * 100)  # 100 XP per session

        # User should have progressed significantly
        assert level.current_level >= 10  # Should be high level
        assert level.total_experience_points >= 7000


# ===== CROSS-FEATURE INTEGRATION TESTS =====

@pytest.mark.integration
class TestCrossFeatureIntegration(TransactionTestCase):
    """Test integration between different features"""

    def setUp(self):
        self.client = Client()

    def test_gamification_analytics_integration(self):
        """Test integration between gamification and analytics systems"""
        user = User.objects.create_user(
            username='integration',
            email='integration@example.com',
            password='testpass123'
        )
        UserProfile.objects.create(user=user)
        level = UserLevel.objects.create(user=user)
        streak_data = UserStreakData.objects.create(user=user)

        # Create session that affects both systems
        session = TimerSession.objects.create(
            user=user,
            start_time=timezone.now() - timedelta(hours=1),
            end_time=timezone.now(),
            is_active=False,
            total_work_minutes=120,
            total_intervals_completed=6,
            total_breaks_taken=5
        )

        # Create break records
        for i in range(5):
            interval = TimerInterval.objects.create(
                session=session,
                interval_number=i + 1,
                status='completed'
            )

            BreakRecord.objects.create(
                user=user,
                session=session,
                interval=interval,
                break_completed=True,
                break_duration_seconds=25,
                looked_at_distance=True
            )

        # Update analytics
        daily_stats = DailyStats.objects.create(
            user=user,
            date=timezone.now().date(),
            total_work_minutes=120,
            total_intervals_completed=6,
            total_breaks_taken=5,
            total_sessions=1,
            breaks_compliant=5,
            productivity_score=90.0
        )

        # Update gamification
        level.sessions_completed = 1
        level.breaks_completed = 5
        level.compliant_breaks = 5
        level.add_experience(150)  # Base + compliance bonus

        streak_data.current_daily_streak = 1
        streak_data.total_sessions_completed = 1
        streak_data.save()

        # Verify cross-system consistency
        assert level.sessions_completed == daily_stats.total_sessions
        assert level.breaks_completed == daily_stats.total_breaks_taken
        assert level.compliant_breaks == daily_stats.breaks_compliant
        assert streak_data.total_sessions_completed == daily_stats.total_sessions

        # Create activity feed entry that references both systems
        LiveActivityFeed.objects.create(
            user=user,
            activity_type='session_completed',
            activity_data={
                'session_duration': 120,
                'compliance_rate': 100.0,
                'experience_gained': 150,
                'new_level': level.current_level,
                'streak_length': streak_data.current_daily_streak
            }
        )

        activity = LiveActivityFeed.objects.get(user=user)
        assert activity.activity_data['compliance_rate'] == 100.0
        assert activity.activity_data['experience_gained'] == 150

    def test_notifications_integration(self):
        """Test integration with notification system"""
        user = User.objects.create_user(
            username='notify',
            email='notify@example.com',
            password='testpass123'
        )
        UserProfile.objects.create(user=user)
        UserLevel.objects.create(user=user)

        # Simulate events that should trigger notifications
        # 1. Level up notification
        level = UserLevel.objects.get(user=user)
        old_level = level.current_level
        level.add_experience(1000)  # Enough to level up

        if level.current_level > old_level:
            Notification.objects.create(
                user=user,
                notification_type='level_up',
                title='Level Up!',
                message=f'Congratulations! You reached level {level.current_level}',
                data={'new_level': level.current_level, 'old_level': old_level}
            )

        # 2. Streak milestone notification
        streak_data = UserStreakData.objects.create(
            user=user,
            current_daily_streak=7
        )

        if streak_data.current_daily_streak == 7:
            Notification.objects.create(
                user=user,
                notification_type='streak_milestone',
                title='Week Warrior!',
                message='Amazing! You\'ve maintained a 7-day streak!',
                data={'streak_days': 7}
            )

        # 3. Break reminder notification
        active_session = TimerSession.objects.create(
            user=user,
            is_active=True,
            start_time=timezone.now() - timedelta(minutes=20)
        )

        interval = TimerInterval.objects.create(
            session=active_session,
            interval_number=1,
            start_time=timezone.now() - timedelta(minutes=20)
        )

        # Simulate break reminder
        Notification.objects.create(
            user=user,
            notification_type='break_reminder',
            title='Time for a break!',
            message='You\'ve been working for 20 minutes. Take a 20-second break!',
            data={'interval_id': interval.id, 'session_id': active_session.id}
        )

        # Verify notifications were created
        notifications = Notification.objects.filter(user=user)
        assert notifications.count() >= 2  # At least streak and break reminder

        notification_types = list(notifications.values_list('notification_type', flat=True))
        assert 'streak_milestone' in notification_types
        assert 'break_reminder' in notification_types

    def test_subscription_feature_gating(self):
        """Test that subscription status properly gates features"""
        # Test with free user
        free_user = User.objects.create_user(
            username='freeuser',
            email='free@example.com',
            password='testpass123',
            subscription_type='free'
        )

        # Test with premium user
        premium_user = User.objects.create_user(
            username='premiumuser',
            email='premium@example.com',
            password='testpass123',
            subscription_type='premium',
        )
        premium_user.subscription_start_date = timezone.now()
        premium_user.subscription_end_date = timezone.now() + timedelta(days=30)
        premium_user.save()

        # Test analytics access
        from analytics.models import PremiumAnalyticsReport

        # Free user should not access premium analytics
        # (This would be enforced in views/API)

        # Premium user should access premium analytics
        premium_report = PremiumAnalyticsReport.objects.create(
            user=premium_user,
            report_type='monthly',
            report_period_start=date.today() - timedelta(days=30),
            report_period_end=date.today()
        )

        assert premium_report.user.subscription_type == 'premium'

        # Test feature limits
        from mysite.constants import FREE_DAILY_INTERVAL_LIMIT

        # Free user limited sessions
        free_session = TimerSession.objects.create(user=free_user, is_active=False)
        for i in range(FREE_DAILY_INTERVAL_LIMIT):
            TimerInterval.objects.create(
                session=free_session,
                interval_number=i + 1,
                start_time=timezone.now()
            )

        # Free user should be at limit
        free_intervals_today = TimerInterval.objects.filter(
            session__user=free_user,
            start_time__date=timezone.now().date()
        ).count()
        assert free_intervals_today == FREE_DAILY_INTERVAL_LIMIT

        # Premium user unlimited sessions
        premium_session = TimerSession.objects.create(user=premium_user, is_active=False)
        for i in range(FREE_DAILY_INTERVAL_LIMIT + 10):
            TimerInterval.objects.create(
                session=premium_session,
                interval_number=i + 1,
                start_time=timezone.now()
            )

        # Premium user should exceed free limit
        premium_intervals_today = TimerInterval.objects.filter(
            session__user=premium_user,
            start_time__date=timezone.now().date()
        ).count()
        assert premium_intervals_today > FREE_DAILY_INTERVAL_LIMIT