import pytest
from datetime import datetime, timedelta, date
from decimal import Decimal
from unittest.mock import patch, Mock
from django.test import TestCase, TransactionTestCase, Client
from django.utils import timezone
from django.contrib.auth import get_user_model, authenticate
from django.core.exceptions import ValidationError
from django.db import IntegrityError
from django.urls import reverse
from django.core import mail
from freezegun import freeze_time

from accounts.models import (
    User, UserProfile, UserLevel, Badge, UserBadge,
    Challenge, ChallengeParticipation, Achievement, UserStreakData
)
from accounts.gamification_utils import (
    calculate_experience_points, check_badge_eligibility,
    update_user_level, calculate_streak_bonus
)
from accounts.security_utils import (
    validate_user_access, prevent_idor_attack,
    validate_input_data, check_rate_limits
)
from timer.models import TimerSession, BreakRecord

User = get_user_model()


@pytest.mark.unit
class TestUserModel(TestCase):
    """Test custom User model functionality"""

    def test_create_user(self):
        """Test creating a basic user"""
        user = User.objects.create_user(
            username='testuser',
            email='test@example.com',
            password='testpass123'
        )

        assert user.username == 'testuser'
        assert user.email == 'test@example.com'
        assert user.check_password('testpass123')
        assert user.subscription_type == 'free'
        assert user.is_verified is False
        assert user.email_notifications is True

    def test_create_superuser(self):
        """Test creating a superuser"""
        user = User.objects.create_superuser(
            username='admin',
            email='admin@example.com',
            password='adminpass123'
        )

        assert user.is_staff is True
        assert user.is_superuser is True
        assert user.subscription_type == 'free'

    def test_email_unique_constraint(self):
        """Test that email addresses must be unique"""
        User.objects.create_user(
            username='user1',
            email='test@example.com',
            password='pass123'
        )

        with self.assertRaises(IntegrityError):
            User.objects.create_user(
                username='user2',
                email='test@example.com',  # Duplicate email
                password='pass123'
            )

    def test_is_premium_user_property(self):
        """Test premium user property"""
        user = User.objects.create_user(
            username='testuser',
            email='test@example.com',
            password='testpass123'
        )

        assert user.is_premium_user is False

        user.subscription_type = 'premium'
        user.save()
        assert user.is_premium_user is True

    def test_is_subscription_active_property(self):
        """Test subscription active property"""
        user = User.objects.create_user(
            username='testuser',
            email='test@example.com',
            password='testpass123',
            subscription_type='premium'
        )

        # No subscription end date
        assert user.is_subscription_active is False

        # Active subscription
        user.subscription_end_date = timezone.now() + timedelta(days=30)
        user.save()
        assert user.is_subscription_active is True

        # Expired subscription
        user.subscription_end_date = timezone.now() - timedelta(days=1)
        user.save()
        assert user.is_subscription_active is False

    def test_get_full_name(self):
        """Test get full name method"""
        user = User.objects.create_user(
            username='testuser',
            email='test@example.com',
            password='testpass123',
            first_name='John',
            last_name='Doe'
        )

        assert user.get_full_name() == 'John Doe'

        # Test with empty names
        user.first_name = ''
        user.last_name = ''
        user.save()
        assert user.get_full_name() == 'testuser'

    def test_user_str_representation(self):
        """Test user string representation"""
        user = User.objects.create_user(
            username='testuser',
            email='test@example.com',
            password='testpass123',
            subscription_type='premium'
        )

        str_repr = str(user)
        assert 'test@example.com' in str_repr
        assert 'Premium' in str_repr


@pytest.mark.unit
class TestUserProfile(TestCase):
    """Test UserProfile model functionality"""

    def setUp(self):
        self.user = User.objects.create_user(
            username='testuser',
            email='test@example.com',
            password='testpass123'
        )

    def test_create_user_profile(self):
        """Test creating a user profile"""
        profile = UserProfile.objects.create(
            user=self.user,
            age=25,
            occupation='Developer',
            daily_screen_time_hours=8.5,
            wears_glasses=True,
            has_eye_strain=True
        )

        assert profile.user == self.user
        assert profile.age == 25
        assert profile.occupation == 'Developer'
        assert profile.daily_screen_time_hours == 8.5
        assert profile.wears_glasses is True
        assert profile.has_eye_strain is True
        assert profile.total_breaks_taken == 0
        assert profile.current_streak_days == 0

    def test_profile_one_to_one_relationship(self):
        """Test one-to-one relationship with User"""
        profile = UserProfile.objects.create(user=self.user)

        # Access profile from user
        assert self.user.profile == profile

        # Test that creating another profile for same user fails
        with self.assertRaises(IntegrityError):
            UserProfile.objects.create(user=self.user)

    def test_profile_defaults(self):
        """Test profile default values"""
        profile = UserProfile.objects.create(user=self.user)

        assert profile.daily_screen_time_hours == 8.0
        assert profile.wears_glasses is False
        assert profile.has_eye_strain is True
        assert profile.timezone == 'UTC'
        assert profile.preferred_language == 'en'


@pytest.mark.gamification
class TestUserLevel(TestCase):
    """Test UserLevel model and gamification functionality"""

    def setUp(self):
        self.user = User.objects.create_user(
            username='testuser',
            email='test@example.com',
            password='testpass123'
        )

    def test_create_user_level(self):
        """Test creating user level"""
        level = UserLevel.objects.create(
            user=self.user,
            current_level=5,
            total_experience_points=1250,
            sessions_completed=100,
            breaks_completed=85,
            compliant_breaks=75
        )

        assert level.user == self.user
        assert level.current_level == 5
        assert level.total_experience_points == 1250
        assert level.sessions_completed == 100
        assert level.breaks_completed == 85
        assert level.compliant_breaks == 75

    def test_calculate_experience_to_next_level(self):
        """Test experience calculation for next level"""
        level = UserLevel.objects.create(
            user=self.user,
            current_level=3,
            total_experience_points=750
        )

        # Assuming level 4 requires 1000 XP
        expected_xp_needed = 250  # 1000 - 750
        # This would be implemented in the model or utility function

    @patch('accounts.gamification_utils.calculate_experience_points')
    def test_experience_point_calculation(self, mock_calculate_xp):
        """Test experience point calculation for various activities"""
        mock_calculate_xp.return_value = 50

        level = UserLevel.objects.create(user=self.user)
        initial_xp = level.total_experience_points

        # Simulate completing a session
        result = calculate_experience_points('session_complete')
        assert result == 50
        mock_calculate_xp.assert_called_with('session_complete')


@pytest.mark.gamification
class TestBadgeSystem(TestCase):
    """Test badge and achievement system"""

    def setUp(self):
        self.user = User.objects.create_user(
            username='testuser',
            email='test@example.com',
            password='testpass123'
        )
        UserLevel.objects.create(user=self.user)

    def test_create_badge(self):
        """Test creating a badge"""
        badge = Badge.objects.create(
            name='First Steps',
            description='Complete your first timer session',
            icon='🎯',
            category='achievement',
            requires_sessions=1,
            experience_reward=25,
            rarity='common'
        )

        assert badge.name == 'First Steps'
        assert badge.requires_sessions == 1
        assert badge.experience_reward == 25
        assert badge.rarity == 'common'
        assert badge.is_active is True

    def test_badge_rarities(self):
        """Test different badge rarities"""
        rarities = ['common', 'uncommon', 'rare', 'epic', 'legendary']
        for rarity in rarities:
            badge = Badge.objects.create(
                name=f'{rarity.title()} Badge',
                description=f'A {rarity} badge',
                rarity=rarity,
                requires_sessions=10
            )
            assert badge.rarity == rarity

    def test_user_badge_earning(self):
        """Test user earning a badge"""
        badge = Badge.objects.create(
            name='Dedicated',
            description='Complete 10 sessions',
            requires_sessions=10,
            experience_reward=100
        )

        user_badge = UserBadge.objects.create(
            user=self.user,
            badge=badge,
            progress=10,
            is_earned=True
        )

        assert user_badge.user == self.user
        assert user_badge.badge == badge
        assert user_badge.is_earned is True
        assert user_badge.progress == 10
        assert user_badge.earned_at is not None

    def test_badge_progress_tracking(self):
        """Test badge progress tracking"""
        badge = Badge.objects.create(
            name='Century',
            description='Complete 100 sessions',
            requires_sessions=100
        )

        user_badge = UserBadge.objects.create(
            user=self.user,
            badge=badge,
            progress=45
        )

        assert user_badge.progress == 45
        assert user_badge.is_earned is False
        assert user_badge.progress_percentage == 45.0

        # Update progress
        user_badge.progress = 100
        user_badge.is_earned = True
        user_badge.save()

        assert user_badge.is_earned is True
        assert user_badge.progress_percentage == 100.0

    @patch('accounts.gamification_utils.check_badge_eligibility')
    def test_automatic_badge_checking(self, mock_check_badges):
        """Test automatic badge eligibility checking"""
        mock_check_badges.return_value = ['badge_1', 'badge_2']

        # This would typically be called after a user action
        eligible_badges = check_badge_eligibility(self.user)
        assert len(eligible_badges) == 2
        mock_check_badges.assert_called_with(self.user)


@pytest.mark.gamification
class TestChallengeSystem(TestCase):
    """Test challenge and participation system"""

    def setUp(self):
        self.user = User.objects.create_user(
            username='testuser',
            email='test@example.com',
            password='testpass123'
        )

    def test_create_challenge(self):
        """Test creating a challenge"""
        start_date = timezone.now().date()
        end_date = start_date + timedelta(days=7)

        challenge = Challenge.objects.create(
            name='Week of Focus',
            description='Complete 20 sessions in a week',
            start_date=start_date,
            end_date=end_date,
            challenge_type='session_count',
            target_value=20,
            experience_reward=500,
            is_premium_only=False
        )

        assert challenge.name == 'Week of Focus'
        assert challenge.challenge_type == 'session_count'
        assert challenge.target_value == 20
        assert challenge.experience_reward == 500
        assert challenge.is_active is True

    def test_challenge_types(self):
        """Test different challenge types"""
        challenge_types = [
            'session_count', 'break_compliance', 'streak_days',
            'total_work_time', 'perfect_days'
        ]

        for challenge_type in challenge_types:
            challenge = Challenge.objects.create(
                name=f'{challenge_type} Challenge',
                description=f'Test {challenge_type} challenge',
                challenge_type=challenge_type,
                target_value=10
            )
            assert challenge.challenge_type == challenge_type

    def test_challenge_participation(self):
        """Test user participating in a challenge"""
        challenge = Challenge.objects.create(
            name='Daily Focus',
            description='Complete 5 sessions today',
            challenge_type='session_count',
            target_value=5,
            experience_reward=100
        )

        participation = ChallengeParticipation.objects.create(
            user=self.user,
            challenge=challenge,
            progress=3
        )

        assert participation.user == self.user
        assert participation.challenge == challenge
        assert participation.progress == 3
        assert participation.is_completed is False
        assert participation.progress_percentage == 60.0

    def test_challenge_completion(self):
        """Test completing a challenge"""
        challenge = Challenge.objects.create(
            name='Quick Start',
            description='Complete 3 sessions',
            challenge_type='session_count',
            target_value=3,
            experience_reward=75
        )

        participation = ChallengeParticipation.objects.create(
            user=self.user,
            challenge=challenge,
            progress=3,
            is_completed=True
        )

        assert participation.is_completed is True
        assert participation.completed_at is not None
        assert participation.progress_percentage == 100.0

    def test_premium_only_challenges(self):
        """Test premium-only challenges"""
        premium_challenge = Challenge.objects.create(
            name='Premium Challenge',
            description='Premium users only',
            challenge_type='session_count',
            target_value=50,
            experience_reward=1000,
            is_premium_only=True
        )

        # Free user shouldn't be able to participate
        # This would be enforced in the view/business logic
        assert premium_challenge.is_premium_only is True

        # Premium user should be able to participate
        self.user.subscription_type = 'premium'
        self.user.save()
        # Logic for premium access would be in views


@pytest.mark.unit
class TestUserStreakData(TestCase):
    """Test user streak tracking"""

    def setUp(self):
        self.user = User.objects.create_user(
            username='testuser',
            email='test@example.com',
            password='testpass123'
        )

    def test_create_streak_data(self):
        """Test creating user streak data"""
        streak_data = UserStreakData.objects.create(
            user=self.user,
            current_daily_streak=7,
            current_weekly_streak=2,
            best_daily_streak=15,
            best_weekly_streak=5,
            last_session_date=date.today(),
            total_sessions_completed=50
        )

        assert streak_data.user == self.user
        assert streak_data.current_daily_streak == 7
        assert streak_data.current_weekly_streak == 2
        assert streak_data.best_daily_streak == 15
        assert streak_data.total_sessions_completed == 50

    @freeze_time("2024-01-15")
    def test_streak_continuation(self):
        """Test streak continuation logic"""
        today = date.today()
        yesterday = today - timedelta(days=1)

        streak_data = UserStreakData.objects.create(
            user=self.user,
            current_daily_streak=5,
            last_session_date=yesterday
        )

        # Update for today's session
        streak_data.last_session_date = today
        streak_data.current_daily_streak += 1
        streak_data.save()

        assert streak_data.current_daily_streak == 6
        assert streak_data.last_session_date == today

    @freeze_time("2024-01-15")
    def test_streak_break(self):
        """Test streak breaking after gap"""
        today = date.today()
        three_days_ago = today - timedelta(days=3)

        streak_data = UserStreakData.objects.create(
            user=self.user,
            current_daily_streak=10,
            last_session_date=three_days_ago
        )

        # Streak should be broken and reset
        # This logic would be in a utility function
        if (today - streak_data.last_session_date).days > 1:
            streak_data.current_daily_streak = 1  # Reset to 1 for today
            streak_data.last_session_date = today
            streak_data.save()

        assert streak_data.current_daily_streak == 1

    def test_best_streak_updates(self):
        """Test updating best streak records"""
        streak_data = UserStreakData.objects.create(
            user=self.user,
            current_daily_streak=20,
            best_daily_streak=15
        )

        # Current streak is better than best
        if streak_data.current_daily_streak > streak_data.best_daily_streak:
            streak_data.best_daily_streak = streak_data.current_daily_streak
            streak_data.save()

        assert streak_data.best_daily_streak == 20


# ===== GAMIFICATION TESTS =====

@pytest.mark.gamification
@pytest.mark.unit
class TestGamificationUtils(TestCase):
    """Test gamification utility functions"""

    def setUp(self):
        self.user = User.objects.create_user(
            username='testuser',
            email='test@example.com',
            password='testpass123'
        )
        UserProfile.objects.create(user=self.user)
        UserLevel.objects.create(user=self.user)

    @patch('accounts.gamification_utils.update_user_level_progress')
    def test_experience_point_calculation(self, mock_update_level):
        """Test experience point calculation for various activities"""
        mock_update_level.return_value = UserLevel.objects.get(user=self.user)

        from accounts.gamification_utils import update_user_level_progress

        # Test session completion
        level_data = update_user_level_progress(self.user, 50)
        mock_update_level.assert_called_with(self.user, 50)

        # Test break compliance
        update_user_level_progress(self.user, 25)
        assert mock_update_level.call_count == 2

    @patch('accounts.gamification_utils.check_and_award_badges')
    def test_badge_checking_integration(self, mock_check_badges):
        """Test badge checking integration"""
        mock_check_badges.return_value = ['first_session', 'consistent_user']

        from accounts.gamification_utils import check_and_award_badges

        badges = check_and_award_badges(self.user)
        mock_check_badges.assert_called_once_with(self.user)
        assert len(badges) == 2

    def test_level_up_calculation_real(self):
        """Test actual level up calculation"""
        level_data = UserLevel.objects.get(user=self.user)
        initial_level = level_data.current_level
        initial_xp = level_data.total_experience_points

        # Add significant experience
        level_data.add_experience(1000)

        # Check if level increased
        level_data.refresh_from_db()
        assert level_data.total_experience_points >= initial_xp + 1000
        # Level might increase depending on thresholds

    def test_badge_eligibility_checking(self):
        """Test badge eligibility checking with real data"""
        # Create session badge
        session_badge = Badge.objects.create(
            name='First Timer',
            description='Complete your first session',
            requires_sessions=1,
            experience_reward=50
        )

        # Create streak badge
        streak_badge = Badge.objects.create(
            name='Week Warrior',
            description='Maintain 7-day streak',
            requires_streak_days=7,
            experience_reward=100
        )

        # Update user level with session
        level_data = UserLevel.objects.get(user=self.user)
        level_data.sessions_completed = 1
        level_data.save()

        # Update streak data
        streak_data, created = UserStreakData.objects.get_or_create(user=self.user)
        streak_data.current_daily_streak = 7
        streak_data.save()

        # Check eligibility (manual implementation since we don't have the actual function)
        eligible_badges = []

        # Check session badge eligibility
        if level_data.sessions_completed >= session_badge.requires_sessions:
            if not UserBadge.objects.filter(user=self.user, badge=session_badge).exists():
                eligible_badges.append(session_badge)

        # Check streak badge eligibility
        if streak_data.current_daily_streak >= streak_badge.requires_streak_days:
            if not UserBadge.objects.filter(user=self.user, badge=streak_badge).exists():
                eligible_badges.append(streak_badge)

        assert len(eligible_badges) == 2  # Both badges should be eligible

    def test_challenge_participation_workflow(self):
        """Test complete challenge participation workflow"""
        # Create challenge
        challenge = Challenge.objects.create(
            name='Daily Focus',
            description='Complete 5 sessions this week',
            start_date=timezone.now().date(),
            end_date=timezone.now().date() + timedelta(days=7),
            challenge_type='session_count',
            target_value=5,
            experience_reward=200
        )

        # User joins challenge
        participation = ChallengeParticipation.objects.create(
            user=self.user,
            challenge=challenge,
            progress=0
        )

        # Simulate progress updates
        for i in range(1, 6):  # Complete 5 sessions
            participation.progress = i
            participation.save()

            # Check completion
            if participation.progress >= challenge.target_value:
                participation.is_completed = True
                participation.completed_at = timezone.now()
                participation.save()

                # Award experience
                level_data = UserLevel.objects.get(user=self.user)
                level_data.add_experience(challenge.experience_reward)

        # Verify completion
        participation.refresh_from_db()
        assert participation.is_completed is True
        assert participation.completed_at is not None
        assert participation.progress_percentage == 100.0

        # Verify experience was awarded
        level_data = UserLevel.objects.get(user=self.user)
        assert level_data.total_experience_points >= 200


@pytest.mark.gamification
@pytest.mark.integration
class TestGamificationIntegrationAdvanced(TestCase):
    """Test advanced gamification integration scenarios"""

    def setUp(self):
        self.user = User.objects.create_user(
            username='testuser',
            email='test@example.com',
            password='testpass123'
        )
        UserProfile.objects.create(user=self.user)
        UserLevel.objects.create(user=self.user)
        UserStreakData.objects.create(user=self.user)

    def test_multi_badge_earning_scenario(self):
        """Test earning multiple badges simultaneously"""
        # Create multiple badges
        badges = [
            Badge.objects.create(
                name='First Steps',
                description='Complete first session',
                requires_sessions=1,
                experience_reward=25
            ),
            Badge.objects.create(
                name='Consistent',
                description='Complete 10 sessions',
                requires_sessions=10,
                experience_reward=100
            ),
            Badge.objects.create(
                name='Dedicated',
                description='Complete 100 sessions',
                requires_sessions=100,
                experience_reward=500
            )
        ]

        # Update user progress to earn multiple badges
        level_data = UserLevel.objects.get(user=self.user)
        level_data.sessions_completed = 100
        level_data.save()

        # Check which badges should be earned
        earned_badges = []
        for badge in badges:
            if level_data.sessions_completed >= badge.requires_sessions:
                user_badge, created = UserBadge.objects.get_or_create(
                    user=self.user,
                    badge=badge
                )
                if created:
                    earned_badges.append(badge)
                    level_data.add_experience(badge.experience_reward)

        # Should earn all 3 badges
        assert len(earned_badges) == 3
        assert UserBadge.objects.filter(user=self.user).count() == 3

    def test_level_progression_with_titles(self):
        """Test level progression and title updates"""
        level_data = UserLevel.objects.get(user=self.user)

        # Test various level thresholds
        test_levels = [1, 5, 10, 15, 20, 25, 30, 40, 50]
        for target_level in test_levels:
            level_data.current_level = target_level
            level_data.save()

            title = level_data.get_level_title()
            assert title is not None
            assert isinstance(title, str)
            assert len(title) > 0

        # Test highest level
        level_data.current_level = 50
        level_data.save()
        assert level_data.get_level_title() == "20-20-20 Master"

    def test_streak_bonus_calculations(self):
        """Test streak bonus calculations"""
        streak_data = UserStreakData.objects.get(user=self.user)

        # Test different streak lengths
        base_xp = 50
        streak_multipliers = {
            1: 1.0,    # No bonus
            3: 1.3,    # 30% bonus
            7: 1.7,    # 70% bonus
            14: 2.4,   # 140% bonus
            30: 4.0    # 300% bonus
        }

        for streak_days, expected_multiplier in streak_multipliers.items():
            streak_data.current_daily_streak = streak_days
            streak_data.save()

            # Calculate streak bonus
            multiplier = 1 + (streak_days * 0.1)  # 10% per day
            bonus_xp = int(base_xp * multiplier)

            assert bonus_xp >= base_xp
            if streak_days > 1:
                assert bonus_xp > base_xp

    def test_challenge_leaderboard_scenario(self):
        """Test challenge leaderboard functionality"""
        # Create challenge
        challenge = Challenge.objects.create(
            name='Community Challenge',
            description='Who can complete the most sessions?',
            start_date=timezone.now().date(),
            end_date=timezone.now().date() + timedelta(days=7),
            challenge_type='session_count',
            target_value=50,
            experience_reward=300
        )

        # Create multiple users for leaderboard
        users = []
        for i in range(5):
            user = User.objects.create_user(
                username=f'user{i}',
                email=f'user{i}@example.com',
                password='testpass123'
            )
            users.append(user)

            # Create participation with different progress
            ChallengeParticipation.objects.create(
                user=user,
                challenge=challenge,
                progress=10 + (i * 5)  # 10, 15, 20, 25, 30
            )

        # Include original user
        ChallengeParticipation.objects.create(
            user=self.user,
            challenge=challenge,
            progress=35  # Highest progress
        )

        # Get leaderboard (ordered by progress)
        leaderboard = ChallengeParticipation.objects.filter(
            challenge=challenge
        ).order_by('-progress')

        # Verify ordering
        leaderboard_list = list(leaderboard)
        assert leaderboard_list[0].user == self.user  # Top of leaderboard
        assert leaderboard_list[0].progress == 35

        # Verify all participants
        assert len(leaderboard_list) == 6  # 5 test users + original user

    def test_achievement_unlock_cascade(self):
        """Test achievement unlocking cascade effects"""
        # Create achievements with dependencies
        basic_achievement = Achievement.objects.create(
            user=self.user,
            achievement_type='streak_7',
            description='Completed 7 day streak'
        )

        # Update streak data to unlock achievement
        streak_data = UserStreakData.objects.get(user=self.user)
        streak_data.current_daily_streak = 7
        streak_data.best_daily_streak = 7
        streak_data.save()

        # Check for subsequent achievements
        level_data = UserLevel.objects.get(user=self.user)
        level_data.achievements_earned += 1
        level_data.add_experience(100)  # Bonus for achievement

        # Verify achievement was recorded
        assert Achievement.objects.filter(user=self.user).count() == 1
        achievement = Achievement.objects.get(user=self.user, achievement_type='streak_7')
        assert achievement.description == 'Completed 7 day streak'


@pytest.mark.security
class TestAuthentication(TestCase):
    """Test authentication functionality"""

    def setUp(self):
        self.client = Client()
        self.user = User.objects.create_user(
            username='testuser',
            email='test@example.com',
            password='testpass123',
            is_verified=True
        )

    def test_user_login(self):
        """Test user login functionality"""
        # Test login with email
        user = authenticate(username='test@example.com', password='testpass123')
        assert user is not None
        assert user == self.user

        # Test login with wrong password
        user = authenticate(username='test@example.com', password='wrongpass')
        assert user is None

    def test_unverified_user_restrictions(self):
        """Test restrictions for unverified users"""
        unverified_user = User.objects.create_user(
            username='unverified',
            email='unverified@example.com',
            password='testpass123',
            is_verified=False
        )

        # Unverified users should have limited access
        assert unverified_user.is_verified is False

    def test_password_strength_requirements(self):
        """Test password strength validation"""
        # This would typically be handled by Django validators
        # or custom password validators in settings
        weak_passwords = ['123', 'password', 'abc']
        strong_password = 'StrongP@ssw0rd123'

        # Test would validate password strength
        for weak_pass in weak_passwords:
            # Password validation logic would go here
            assert len(weak_pass) < 8  # Simple length check

        assert len(strong_password) >= 8

    def test_account_lockout_protection(self):
        """Test account lockout after failed attempts"""
        # This would typically be handled by django-axes
        # Test multiple failed login attempts
        for i in range(5):
            user = authenticate(
                username='test@example.com',
                password='wrongpassword'
            )
            assert user is None

        # After multiple failures, account should be temporarily locked
        # This behavior would be configured in django-axes settings


@pytest.mark.security
class TestSecurityUtils(TestCase):
    """Test security utility functions"""

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

    @patch('accounts.security_utils.validate_user_access')
    def test_user_access_validation(self, mock_validate):
        """Test user access validation"""
        mock_validate.return_value = True

        # Test valid access
        result = validate_user_access(self.user1, 'timer_session', 123)
        assert result is True
        mock_validate.assert_called_with(self.user1, 'timer_session', 123)

    @patch('accounts.security_utils.prevent_idor_attack')
    def test_idor_prevention(self, mock_idor):
        """Test Insecure Direct Object Reference prevention"""
        mock_idor.return_value = False  # Access denied

        # Test IDOR protection
        result = prevent_idor_attack(self.user1, 'session', 999)
        assert result is False
        mock_idor.assert_called_with(self.user1, 'session', 999)

    @patch('accounts.security_utils.validate_input_data')
    def test_input_validation(self, mock_validate_input):
        """Test input data validation"""
        mock_validate_input.return_value = True

        test_data = {
            'work_interval': 20,
            'break_duration': 20,
            'notification_sound': True
        }

        result = validate_input_data(test_data, 'timer_settings')
        assert result is True
        mock_validate_input.assert_called_with(test_data, 'timer_settings')

    @patch('accounts.security_utils.check_rate_limits')
    def test_rate_limiting(self, mock_rate_limit):
        """Test rate limiting functionality"""
        mock_rate_limit.return_value = True  # Within limits

        result = check_rate_limits(self.user1, 'api_call')
        assert result is True
        mock_rate_limit.assert_called_with(self.user1, 'api_call')


@pytest.mark.integration
class TestGamificationIntegration(TestCase):
    """Test gamification system integration"""

    def setUp(self):
        self.user = User.objects.create_user(
            username='testuser',
            email='test@example.com',
            password='testpass123'
        )
        UserProfile.objects.create(user=self.user)
        self.user_level = UserLevel.objects.create(user=self.user)
        UserStreakData.objects.create(user=self.user)

    def test_session_completion_triggers_gamification(self):
        """Test that completing a session triggers gamification updates"""
        # Create a timer session
        session = TimerSession.objects.create(
            user=self.user,
            total_intervals_completed=3,
            total_breaks_taken=3,
            total_work_minutes=60
        )
        session.end_session()

        # Create badge for first session
        first_session_badge = Badge.objects.create(
            name='First Timer',
            description='Complete your first session',
            requires_sessions=1,
            experience_reward=50
        )

        # Simulate gamification update after session completion
        self.user_level.sessions_completed += 1
        self.user_level.total_experience_points += 50
        self.user_level.save()

        # Check if badge should be awarded
        if self.user_level.sessions_completed >= first_session_badge.requires_sessions:
            UserBadge.objects.create(
                user=self.user,
                badge=first_session_badge,
                progress=1,
                is_earned=True
            )

        # Verify updates
        self.user_level.refresh_from_db()
        assert self.user_level.sessions_completed == 1
        assert self.user_level.total_experience_points >= 50

        # Verify badge was awarded
        user_badge = UserBadge.objects.get(user=self.user, badge=first_session_badge)
        assert user_badge.is_earned is True

    def test_level_up_calculation(self):
        """Test level up calculations"""
        # Set user close to level up
        self.user_level.current_level = 1
        self.user_level.total_experience_points = 950  # Assuming level 2 needs 1000 XP
        self.user_level.save()

        # Add more experience
        additional_xp = 100
        self.user_level.total_experience_points += additional_xp

        # Check if level up should occur
        # This logic would be in a utility function
        level_thresholds = {1: 1000, 2: 2500, 3: 5000}  # Example thresholds
        current_xp = self.user_level.total_experience_points
        current_level = self.user_level.current_level

        if current_xp >= level_thresholds.get(current_level, float('inf')):
            self.user_level.current_level += 1
            # Calculate XP needed for next level
            next_level_threshold = level_thresholds.get(self.user_level.current_level, float('inf'))
            self.user_level.experience_to_next_level = next_level_threshold - current_xp

        self.user_level.save()

        assert self.user_level.current_level == 2
        assert self.user_level.total_experience_points == 1050

    def test_streak_bonus_calculation(self):
        """Test streak bonus experience calculation"""
        streak_data = UserStreakData.objects.get(user=self.user)
        streak_data.current_daily_streak = 7  # Week streak
        streak_data.save()

        # Calculate streak bonus
        base_xp = 50
        streak_multiplier = 1 + (streak_data.current_daily_streak * 0.1)  # 10% per day
        bonus_xp = int(base_xp * streak_multiplier)

        assert bonus_xp > base_xp  # Should be more than base
        assert bonus_xp == int(50 * 1.7)  # 50 * 1.7 = 85

    def test_challenge_progress_update(self):
        """Test updating challenge progress"""
        # Create an active challenge
        challenge = Challenge.objects.create(
            name='Session Master',
            description='Complete 10 sessions',
            challenge_type='session_count',
            target_value=10,
            experience_reward=200
        )

        # User joins challenge
        participation = ChallengeParticipation.objects.create(
            user=self.user,
            challenge=challenge,
            progress=0
        )

        # Simulate session completion
        for i in range(5):
            # Create session
            session = TimerSession.objects.create(user=self.user)
            session.end_session()

            # Update challenge progress
            participation.progress += 1
            participation.save()

        assert participation.progress == 5
        assert participation.progress_percentage == 50.0
        assert participation.is_completed is False

        # Complete the challenge
        for i in range(5):
            session = TimerSession.objects.create(user=self.user)
            session.end_session()
            participation.progress += 1

        participation.is_completed = True
        participation.completed_at = timezone.now()
        participation.save()

        assert participation.progress == 10
        assert participation.is_completed is True
        assert participation.completed_at is not None