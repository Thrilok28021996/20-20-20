"""
Account service layer for user management and gamification business logic
Handles user operations, gamification calculations, and achievement management
"""
from typing import Dict, List, Optional, Tuple, Union, Any
from django.db.models import QuerySet
from datetime import date, datetime, timedelta
from django.utils import timezone
from django.db.models import Sum, Count, Avg, Q, F
from django.contrib.auth import get_user_model
import logging

from .models import (
    User, UserProfile, Achievement, UserStreakData, UserLevel,
    Badge, UserBadge, Challenge, ChallengeParticipation
)
from timer.models import TimerSession, BreakRecord
from analytics.models import DailyStats

logger = logging.getLogger(__name__)
User = get_user_model()


class UserService:
    """Service class for user management operations"""

    @staticmethod
    def create_user_profile(user: User, profile_data: Dict[str, Any]) -> UserProfile:
        """Create or update user profile with provided data"""
        profile, created = UserProfile.objects.get_or_create(user=user)

        # Update profile fields - SECURITY FIX: Explicit whitelist to prevent mass assignment
        ALLOWED_PROFILE_FIELDS = {
            'age', 'occupation', 'daily_screen_time_hours', 'wears_glasses',
            'has_eye_strain', 'last_eye_checkup', 'timezone', 'preferred_language'
        }

        for field in ALLOWED_PROFILE_FIELDS:
            if field in profile_data:
                setattr(profile, field, profile_data[field])

        profile.save()
        return profile

    @staticmethod
    def update_subscription(user: User, subscription_type: str,
                          subscription_data: Dict[str, Any]) -> User:
        """Update user subscription information"""
        user.subscription_type = subscription_type

        if 'stripe_customer_id' in subscription_data:
            user.stripe_customer_id = subscription_data['stripe_customer_id']

        if subscription_type == 'premium':
            user.subscription_start_date = subscription_data.get(
                'start_date', timezone.now()
            )
            user.subscription_end_date = subscription_data.get('end_date')
        else:
            user.subscription_start_date = None
            user.subscription_end_date = None

        user.save()
        return user

    @staticmethod
    def get_user_dashboard_context(user: User) -> Dict[str, Any]:
        """Get comprehensive dashboard context for user - Optimized with minimal DB queries"""
        from .gamification_utils import get_user_gamification_summary
        from accounts.timezone_utils import user_today

        # Get user timer settings
        from timer.models import UserTimerSettings
        settings, created = UserTimerSettings.objects.get_or_create(user=user)

        # Get active session with prefetched interval data
        from timer.services import TimerSessionService
        active_session = TimerSessionService.get_active_session(user)
        active_interval = TimerSessionService.get_active_interval(active_session)

        # Get today's statistics and session count in single query
        user_date_today = user_today(user)
        today_stats, created = DailyStats.objects.get_or_create(
            user=user,
            date=user_date_today
        )

        # Check subscription limits
        can_start, intervals_today, daily_limit = TimerSessionService.check_daily_limits(user)

        # Get session count for backward compatibility (already queried in check_daily_limits for intervals)
        sessions_today = TimerSession.objects.filter(
            user=user,
            start_time__date=user_date_today
        ).count()

        # Get premium features (cached method)
        premium_features = PremiumFeatureService.get_user_premium_features(user)

        # Get streak data and recent achievements in optimized way
        streak_data, created = UserStreakData.objects.get_or_create(user=user)

        # Get recent achievements with select_related optimization
        user_achievements = Achievement.objects.filter(
            user=user
        ).order_by('-earned_at')[:5]

        # Get gamification summary (this method is already optimized)
        gamification_data = get_user_gamification_summary(user)

        return {
            'active_session': active_session,
            'active_interval': active_interval,
            'settings': settings,
            'today_stats': today_stats,
            'can_start_session': can_start,
            'intervals_today': intervals_today,
            'daily_interval_limit': daily_limit,
            'sessions_today': sessions_today,
            'is_premium_user': user.is_premium_user,
            'premium_timer_presets': premium_features.get('timer_presets', []),
            'streak_data': streak_data,
            'user_achievements': user_achievements,
            'gamification_data': gamification_data,
            'premium_features': premium_features,
        }


class GamificationService:
    """Service class for gamification logic and calculations"""

    @staticmethod
    def update_user_level(user: User, experience_points: int) -> Tuple[UserLevel, bool]:
        """
        Update user's level and experience points
        Returns: (user_level, level_up_occurred)
        """
        level_data, created = UserLevel.objects.get_or_create(user=user)
        initial_level = level_data.current_level

        if experience_points > 0:
            level_data.add_experience(experience_points)

        level_up_occurred = level_data.current_level > initial_level
        return level_data, level_up_occurred

    @staticmethod
    def calculate_session_rewards(user: User, session: TimerSession) -> Dict[str, Any]:
        """Calculate experience and rewards for session completion"""
        base_experience = 10

        # Bonus experience for break compliance
        compliance_bonus = GamificationService._calculate_compliance_bonus(session)

        # Length bonus for longer sessions
        length_bonus = min(session.total_intervals_completed * 2, 20)

        total_experience = base_experience + compliance_bonus + length_bonus

        return {
            'experience_gained': total_experience,
            'breakdown': {
                'base': base_experience,
                'compliance_bonus': compliance_bonus,
                'length_bonus': length_bonus
            }
        }

    @staticmethod
    def _calculate_compliance_bonus(session: TimerSession) -> int:
        """Calculate compliance bonus for session"""
        if session.total_breaks_taken == 0:
            return 0

        break_stats = BreakRecord.objects.filter(
            session=session,
            break_completed=True
        ).aggregate(
            total_breaks=Count('id'),
            compliant_breaks=Count(
                'id',
                filter=Q(break_duration_seconds__gte=20, looked_at_distance=True)
            )
        )

        total_breaks = break_stats['total_breaks'] or 0
        compliant_breaks = break_stats['compliant_breaks'] or 0

        if total_breaks > 0:
            compliance_rate = compliant_breaks / total_breaks
            return int(compliance_rate * 20)  # Up to 20 bonus XP

        return 0

    @staticmethod
    def get_gamification_summary(user: User) -> Dict[str, Any]:
        """Get comprehensive gamification summary for user"""
        # Level data
        level_data, _ = UserLevel.objects.get_or_create(user=user)

        # Badge statistics
        badge_stats = GamificationService._get_badge_statistics(user)

        # Recent achievements
        recent_achievements = GamificationService._get_recent_achievements(user)

        # Active challenges
        active_challenges = GamificationService._get_active_challenges(user)

        # Streak data
        streak_data = GamificationService._get_streak_data(user)

        return {
            'level': GamificationService._format_level_data(level_data),
            'badges': badge_stats,
            'streaks': streak_data,
            'recent_achievements': recent_achievements,
            'active_challenges': active_challenges
        }

    @staticmethod
    def _get_badge_statistics(user: User) -> Dict[str, Any]:
        """Get badge statistics for user"""
        badge_stats = Badge.objects.filter(is_active=True).aggregate(
            total_badges=Count('id'),
            user_badges=Count('id', filter=Q(userbadge__user=user))
        )

        user_badges = badge_stats['user_badges'] or 0
        total_badges = badge_stats['total_badges'] or 0

        return {
            'earned': user_badges,
            'total': total_badges,
            'completion_percentage': (user_badges / total_badges) * 100 if total_badges > 0 else 0
        }

    @staticmethod
    def _get_recent_achievements(user: User) -> List[Dict[str, Any]]:
        """Get recent achievements for user"""
        recent_achievements = Achievement.objects.select_related().filter(
            user=user
        ).order_by('-earned_at')[:5]

        return [
            {
                'type': achievement.get_achievement_type_display(),
                'earned_at': achievement.earned_at,
                'description': achievement.description
            }
            for achievement in recent_achievements
        ]

    @staticmethod
    def _get_active_challenges(user: User) -> List[Dict[str, Any]]:
        """Get active challenges for user"""
        now = timezone.now()
        active_participations = ChallengeParticipation.objects.select_related(
            'challenge'
        ).filter(
            user=user,
            challenge__is_active=True,
            challenge__start_date__lte=now,
            challenge__end_date__gte=now
        )

        return [
            {
                'name': participation.challenge.name,
                'progress': participation.current_progress,
                'target': participation.challenge.target_value,
                'progress_percentage': participation.progress_percentage,
                'ends_at': participation.challenge.end_date
            }
            for participation in active_participations
        ]

    @staticmethod
    def _get_streak_data(user: User) -> Dict[str, int]:
        """Get streak data for user"""
        try:
            streak_data = UserStreakData.objects.get(user=user)
            return {
                'current_daily': streak_data.current_daily_streak,
                'best_daily': streak_data.best_daily_streak,
                'current_weekly': streak_data.current_weekly_streak,
                'best_weekly': streak_data.best_weekly_streak
            }
        except UserStreakData.DoesNotExist:
            return {
                'current_daily': 0,
                'best_daily': 0,
                'current_weekly': 0,
                'best_weekly': 0
            }

    @staticmethod
    def _format_level_data(level_data: UserLevel) -> Dict[str, Any]:
        """Format level data for frontend consumption"""
        progress_percentage = (
            (level_data.total_experience_points / level_data.experience_to_next_level) * 100
            if level_data.experience_to_next_level > 0 else 100
        )

        return {
            'current_level': level_data.current_level,
            'level_title': level_data.get_level_title(),
            'experience_points': level_data.total_experience_points,
            'experience_to_next': level_data.experience_to_next_level,
            'progress_percentage': progress_percentage
        }


class BadgeService:
    """Service class for badge management and checking"""

    @staticmethod
    def check_and_award_badges(user: User) -> List[UserBadge]:
        """Check and award new badges to user"""
        # Get user's earned badge IDs
        user_badge_ids = set(
            UserBadge.objects.filter(user=user).values_list('badge_id', flat=True)
        )

        # Get available badges
        available_badges = Badge.objects.filter(
            is_active=True
        ).exclude(id__in=user_badge_ids)

        # Get user statistics once
        user_stats = BadgeService._get_user_statistics(user)

        newly_awarded = []
        for badge in available_badges:
            if BadgeService._check_badge_requirements(badge, user_stats):
                user_badge = UserBadge.objects.create(user=user, badge=badge)
                newly_awarded.append(user_badge)

                # Award experience
                if badge.experience_reward > 0:
                    GamificationService.update_user_level(user, badge.experience_reward)

                # Create activity feed entry
                BadgeService._create_badge_activity(user, badge)

        return newly_awarded

    @staticmethod
    def _check_badge_requirements(badge: Badge, user_stats: Dict[str, Any]) -> bool:
        """Check if user meets badge requirements"""
        # Check numeric requirements
        if badge.requires_streak_days:
            if user_stats['current_streak'] < badge.requires_streak_days:
                return False

        if badge.requires_sessions:
            if user_stats['total_sessions'] < badge.requires_sessions:
                return False

        if badge.requires_compliant_breaks:
            if user_stats['compliant_breaks'] < badge.requires_compliant_breaks:
                return False

        if badge.requires_perfect_days:
            if user_stats['perfect_days'] < badge.requires_perfect_days:
                return False

        # Check special requirements
        if badge.special_requirements:
            return BadgeService._check_special_requirements(
                badge.special_requirements, user_stats
            )

        return True

    @staticmethod
    def _check_special_requirements(requirements: Dict[str, Any],
                                  user_stats: Dict[str, Any]) -> bool:
        """Check special badge requirements"""
        user = user_stats['user']

        for req_type, req_value in requirements.items():
            if req_type == 'early_bird_sessions':
                early_sessions = TimerSession.objects.filter(
                    user=user,
                    start_time__hour__gte=5,
                    start_time__hour__lte=9,
                    is_active=False
                ).count()
                if early_sessions < req_value:
                    return False

            elif req_type == 'night_owl_sessions':
                night_sessions = TimerSession.objects.filter(
                    user=user,
                    start_time__hour__gte=18,
                    start_time__hour__lte=23,
                    is_active=False
                ).count()
                if night_sessions < req_value:
                    return False

            elif req_type == 'weekend_sessions':
                weekend_sessions = TimerSession.objects.filter(
                    user=user,
                    start_time__week_day__in=[1, 7],
                    is_active=False
                ).count()
                if weekend_sessions < req_value:
                    return False

            elif req_type == 'consecutive_compliant_breaks':
                recent_breaks = BreakRecord.objects.filter(
                    user=user,
                    break_completed=True
                ).order_by('-break_start_time')[:req_value]

                if len(recent_breaks) < req_value:
                    return False

                for break_record in recent_breaks:
                    if not break_record.is_compliant:
                        return False

            elif req_type == 'minimum_compliance_rate':
                if user_stats['compliance_rate'] < req_value:
                    return False

        return True

    @staticmethod
    def _get_user_statistics(user: User) -> Dict[str, Any]:
        """Get comprehensive user statistics for badge checking - Optimized"""
        # Get streak data with fallback defaults
        streak_defaults = {
            'current_daily_streak': 0,
            'total_sessions_completed': 0
        }

        try:
            streak_data = UserStreakData.objects.get(user=user)
            current_streak = streak_data.current_daily_streak
            total_sessions_from_streak = streak_data.total_sessions_completed
        except UserStreakData.DoesNotExist:
            current_streak = 0
            total_sessions_from_streak = 0

        # Single optimized query for session and break statistics
        from django.db.models import Case, When, IntegerField

        # Combined query for all user statistics
        combined_stats = TimerSession.objects.filter(
            user=user,
            is_active=False
        ).aggregate(
            session_count=Count('id'),
            total_break_records=Count('breaks__id', filter=Q(breaks__break_completed=True)),
            compliant_breaks=Count(
                'breaks__id',
                filter=Q(
                    breaks__break_completed=True,
                    breaks__break_duration_seconds__gte=20,
                    breaks__looked_at_distance=True
                )
            )
        )

        # Single query for perfect days count
        perfect_days = DailyStats.objects.filter(
            user=user,
            compliance_rate=100.0
        ).count()

        # Use the maximum of sessions from streak data and session count
        total_sessions = max(total_sessions_from_streak, combined_stats['session_count'] or 0)
        total_breaks = combined_stats['total_break_records'] or 0
        compliant_breaks = combined_stats['compliant_breaks'] or 0

        compliance_rate = (compliant_breaks / total_breaks * 100) if total_breaks > 0 else 0

        return {
            'user': user,
            'current_streak': current_streak,
            'total_sessions': total_sessions,
            'total_breaks': total_breaks,
            'compliant_breaks': compliant_breaks,
            'compliance_rate': compliance_rate,
            'perfect_days': perfect_days
        }

    @staticmethod
    def _create_badge_activity(user: User, badge: Badge) -> None:
        """Create activity feed entry for badge earned"""
        try:
            from analytics.models import LiveActivityFeed
            LiveActivityFeed.objects.create(
                user=user,
                activity_type='badge_earned',
                activity_data={
                    'badge_name': badge.name,
                    'badge_rarity': badge.get_rarity_display(),
                    'experience_reward': badge.experience_reward
                }
            )
        except Exception as e:
            logger.warning(f"Failed to create badge activity: {e}")


class ChallengeService:
    """Service class for challenge management"""

    @staticmethod
    def update_challenge_progress(user: User, challenge_type: Optional[str] = None) -> None:
        """Update user progress in all active challenges"""
        now = timezone.now()
        active_challenges = Challenge.objects.filter(
            is_active=True,
            start_date__lte=now,
            end_date__gte=now
        )

        if challenge_type:
            active_challenges = active_challenges.filter(challenge_type=challenge_type)

        user_participations = ChallengeParticipation.objects.filter(
            user=user,
            challenge__in=active_challenges,
            is_completed=False
        )

        for participation in user_participations:
            current_progress = ChallengeService._calculate_challenge_progress(
                user, participation.challenge
            )
            participation.update_progress(current_progress)

    @staticmethod
    def _calculate_challenge_progress(user: User, challenge: Challenge) -> int:
        """Calculate user's current progress for a specific challenge"""
        challenge_start = challenge.start_date
        challenge_end = challenge.end_date

        if challenge.challenge_type == 'daily_streak':
            try:
                streak_data = UserStreakData.objects.get(user=user)
                return streak_data.current_daily_streak
            except UserStreakData.DoesNotExist:
                return 0

        elif challenge.challenge_type == 'session_count':
            return TimerSession.objects.filter(
                user=user,
                start_time__gte=challenge_start,
                start_time__lte=challenge_end,
                is_active=False
            ).count()

        elif challenge.challenge_type == 'compliance_rate':
            breaks = BreakRecord.objects.filter(
                user=user,
                break_start_time__gte=challenge_start,
                break_start_time__lte=challenge_end,
                break_completed=True
            )

            if breaks.count() == 0:
                return 0

            compliant_breaks = breaks.filter(
                break_duration_seconds__gte=20,
                looked_at_distance=True
            ).count()

            return int((compliant_breaks / breaks.count()) * 100)

        elif challenge.challenge_type == 'community':
            return TimerSession.objects.filter(
                user=user,
                start_time__gte=challenge_start,
                start_time__lte=challenge_end,
                is_active=False
            ).count()

        return 0

    @staticmethod
    def join_challenge(user: User, challenge: Challenge) -> ChallengeParticipation:
        """Join a user to a challenge"""
        participation, created = ChallengeParticipation.objects.get_or_create(
            user=user,
            challenge=challenge
        )

        if created:
            # Calculate initial progress
            current_progress = ChallengeService._calculate_challenge_progress(user, challenge)
            participation.update_progress(current_progress)

        return participation


class PremiumFeatureService:
    """Service class for premium feature management"""

    @staticmethod
    def get_user_premium_features(user: User) -> Dict[str, Any]:
        """Get available features for user - all features are now free"""
        features = {
            'timer_presets': [],
            'eye_exercises': [],
            'custom_themes': True,
            'advanced_analytics': True,
            'guided_exercises': True,
        }
        return features

    @staticmethod
    def check_feature_access(user: User, feature_name: str) -> bool:
        """Check if user has access to specific feature - always True (all features free)"""
        return True


class AchievementService:
    """Service class for achievement management"""

    @staticmethod
    def check_and_award_achievements(user: User, streak_data: UserStreakData) -> List[Achievement]:
        """Check and award achievements for user"""
        from mysite.constants import (
            STREAK_ACHIEVEMENTS, SESSION_MASTER_THRESHOLD,
            EARLY_BIRD_START_HOUR, EARLY_BIRD_END_HOUR, NIGHT_OWL_START_HOUR,
            NIGHT_OWL_END_HOUR, EARLY_BIRD_SESSIONS_REQUIRED, NIGHT_OWL_SESSIONS_REQUIRED
        )
        from accounts.timezone_utils import user_now, user_today

        achievements_to_award = []

        # Streak achievements
        for achievement_type, required_days in STREAK_ACHIEVEMENTS.items():
            if streak_data.current_daily_streak >= required_days:
                achievements_to_award.append(achievement_type)

        # Session count achievements
        if streak_data.total_sessions_completed >= SESSION_MASTER_THRESHOLD:
            achievements_to_award.append('session_master')

        # Time-based achievements
        user_current_time = user_now(user)
        current_hour = user_current_time.hour

        if EARLY_BIRD_START_HOUR <= current_hour <= EARLY_BIRD_END_HOUR:
            morning_sessions = TimerSession.objects.filter(
                user=user,
                start_time__hour__gte=EARLY_BIRD_START_HOUR,
                start_time__hour__lte=EARLY_BIRD_END_HOUR
            ).count()
            if morning_sessions >= EARLY_BIRD_SESSIONS_REQUIRED:
                achievements_to_award.append('early_bird')

        if NIGHT_OWL_START_HOUR <= current_hour <= NIGHT_OWL_END_HOUR:
            evening_sessions = TimerSession.objects.filter(
                user=user,
                start_time__hour__gte=NIGHT_OWL_START_HOUR,
                start_time__hour__lte=NIGHT_OWL_END_HOUR
            ).count()
            if evening_sessions >= NIGHT_OWL_SESSIONS_REQUIRED:
                achievements_to_award.append('night_owl')

        # Award achievements that don't exist yet
        awarded_achievements = []
        for achievement_type in achievements_to_award:
            achievement, created = Achievement.objects.get_or_create(
                user=user,
                achievement_type=achievement_type,
                defaults={
                    'description': f'Earned on {user_today(user)}'
                }
            )
            if created:
                awarded_achievements.append(achievement)

        return awarded_achievements