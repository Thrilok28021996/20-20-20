"""
Utility functions for gamification calculations and badge/achievement management
"""
from typing import Dict, List, Optional, Tuple, Union, Any
from django.utils import timezone
from django.db.models import Count, Sum, Avg, Q
from django.contrib.auth import get_user_model
from datetime import datetime, timedelta, date
from .models import (
    UserLevel, Badge, UserBadge, Challenge, ChallengeParticipation,
    Achievement, UserStreakData
)
from timer.models import TimerSession, BreakRecord
from analytics.models import DailyStats


User = get_user_model()


def update_user_level_progress(user: User, experience_points: int) -> UserLevel:
    """
    Update user's level progress and handle level ups

    Args:
        user: User instance to update
        experience_points: Points to add (must be positive)

    Returns:
        Updated UserLevel instance

    Raises:
        ValueError: If experience_points is negative
    """
    if experience_points < 0:
        raise ValueError("Experience points must be positive")

    level_data, created = UserLevel.objects.get_or_create(user=user)
    initial_level = level_data.current_level

    if experience_points > 0:
        level_data.add_experience(experience_points)

        # Create activity feed entry if level increased
        if level_data.current_level > initial_level:
            from analytics.models import LiveActivityFeed
            LiveActivityFeed.objects.create(
                user=user,
                activity_type='level_up',
                activity_data={
                    'new_level': level_data.current_level,
                    'previous_level': initial_level,
                    'level_title': level_data.get_level_title(),
                    'experience_gained': experience_points
                }
            )

    return level_data


def check_and_award_badges(user: User) -> List[UserBadge]:
    """
    Check user progress against all available badges and award new ones - Optimized queries
    """
    # Single query to get all user's earned badge IDs
    user_badge_ids = set(UserBadge.objects.filter(user=user).values_list('badge_id', flat=True))

    # Prefetch all available badges with their requirements
    available_badges = Badge.objects.filter(
        is_active=True
    ).exclude(
        id__in=user_badge_ids
    ).select_related()  # Use select_related for any foreign keys

    # Get user statistics once for all badge checks
    user_stats = _get_user_statistics(user)

    newly_awarded = []
    activity_entries = []  # Batch create activity entries

    for badge in available_badges:
        if _check_badge_requirements_optimized(user, badge, user_stats):
            user_badge = UserBadge.objects.create(user=user, badge=badge)
            newly_awarded.append(user_badge)

            # Award experience for earning badge
            if badge.experience_reward > 0:
                update_user_level_progress(user, badge.experience_reward)

            # Prepare activity feed entry for batch creation
            from analytics.models import LiveActivityFeed
            activity_entries.append(LiveActivityFeed(
                user=user,
                activity_type='badge_earned',
                activity_data={
                    'badge_name': badge.name,
                    'badge_rarity': badge.get_rarity_display(),
                    'experience_reward': badge.experience_reward
                }
            ))

    # Batch create activity feed entries
    if activity_entries:
        from analytics.models import LiveActivityFeed
        LiveActivityFeed.objects.bulk_create(activity_entries)

    return newly_awarded


def _check_badge_requirements_optimized(user: User, badge: Badge, user_stats: Dict[str, Any]) -> bool:
    """
    Check if user meets the requirements for a specific badge - Optimized version that reuses user_stats
    """
    # Check simple numeric requirements using pre-calculated stats
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
        return _check_special_badge_requirements(user, badge.special_requirements, user_stats)

    return True


def _check_badge_requirements(user: User, badge: Badge) -> bool:
    """
    Check if user meets the requirements for a specific badge - Legacy method for backward compatibility
    """
    user_stats = _get_user_statistics(user)
    return _check_badge_requirements_optimized(user, badge, user_stats)


def _check_special_badge_requirements(user: User, requirements: Dict[str, Any], user_stats: Dict[str, Any]) -> bool:
    """
    Check complex badge requirements defined in JSON
    """
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
                start_time__week_day__in=[1, 7],  # Sunday=1, Saturday=7
                is_active=False
            ).count()
            if weekend_sessions < req_value:
                return False

        elif req_type == 'consecutive_compliant_breaks':
            # Check for consecutive compliant breaks
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


def _get_user_statistics(user: User) -> Dict[str, Any]:
    """
    Get comprehensive user statistics for badge checking - Optimized to reduce N+1 queries
    """
    # Get streak data
    try:
        streak_data = UserStreakData.objects.get(user=user)
        current_streak = streak_data.current_daily_streak
        total_sessions = streak_data.total_sessions_completed
    except UserStreakData.DoesNotExist:
        current_streak = 0
        total_sessions = 0

    # Get session and break statistics in single optimized queries
    session_stats = TimerSession.objects.filter(
        user=user,
        is_active=False
    ).aggregate(
        session_count=Count('id')
    )

    break_stats = BreakRecord.objects.filter(
        user=user,
        break_completed=True
    ).aggregate(
        total_breaks=Count('id'),
        compliant_breaks=Count(
            'id',
            filter=Q(break_duration_seconds__gte=20, looked_at_distance=True)
        )
    )

    # Use the higher count between streak data and actual query
    total_sessions = max(total_sessions, session_stats['session_count'] or 0)
    total_breaks = break_stats['total_breaks'] or 0
    compliant_breaks = break_stats['compliant_breaks'] or 0

    compliance_rate = (compliant_breaks / total_breaks * 100) if total_breaks > 0 else 0

    # Calculate perfect days (days with 100% compliance) - Using database fields
    # A perfect day is when all breaks are compliant
    from django.db.models import F
    perfect_days = DailyStats.objects.filter(
        user=user,
        total_breaks_taken__gt=0
    ).extra(
        where=["breaks_compliant = total_breaks_taken"]
    ).count()

    return {
        'current_streak': current_streak,
        'total_sessions': total_sessions,
        'total_breaks': total_breaks,
        'compliant_breaks': compliant_breaks,
        'compliance_rate': compliance_rate,
        'perfect_days': perfect_days
    }


def update_challenge_progress(user: User, challenge_type: Optional[str] = None) -> None:
    """
    Update user's progress in all active challenges
    """
    now = timezone.now()
    active_challenges = Challenge.objects.filter(
        is_active=True,
        start_date__lte=now,
        end_date__gte=now
    )

    user_participations = ChallengeParticipation.objects.filter(
        user=user,
        challenge__in=active_challenges,
        is_completed=False
    )

    for participation in user_participations:
        challenge = participation.challenge
        current_progress = _calculate_challenge_progress(user, challenge)
        participation.update_progress(current_progress)


def _calculate_challenge_progress(user: User, challenge: Challenge) -> int:
    """
    Calculate user's current progress for a specific challenge
    """
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
        # Community challenges could be based on total community progress
        # For now, return user's individual contribution
        return TimerSession.objects.filter(
            user=user,
            start_time__gte=challenge_start,
            start_time__lte=challenge_end,
            is_active=False
        ).count()

    return 0


def create_default_badges() -> List[Badge]:
    """
    Create default badges for the application
    """
    default_badges = [
        {
            'name': 'First Steps',
            'description': 'Complete your first timer session',
            'icon': '👶',
            'category': 'beginner',
            'requires_sessions': 1,
            'rarity': 'common',
            'experience_reward': 25
        },
        {
            'name': 'Getting Started',
            'description': 'Complete 10 timer sessions',
            'icon': '🚀',
            'category': 'progress',
            'requires_sessions': 10,
            'rarity': 'common',
            'experience_reward': 50
        },
        {
            'name': 'Dedicated Worker',
            'description': 'Complete 100 timer sessions',
            'icon': '💪',
            'category': 'progress',
            'requires_sessions': 100,
            'rarity': 'rare',
            'experience_reward': 200
        },
        {
            'name': 'Eye Health Champion',
            'description': 'Complete 1000 timer sessions',
            'icon': '🏆',
            'category': 'progress',
            'requires_sessions': 1000,
            'rarity': 'epic',
            'experience_reward': 500
        },
        {
            'name': 'Week Warrior',
            'description': 'Maintain a 7-day streak',
            'icon': '📅',
            'category': 'streaks',
            'requires_streak_days': 7,
            'rarity': 'common',
            'experience_reward': 100
        },
        {
            'name': 'Month Master',
            'description': 'Maintain a 30-day streak',
            'icon': '🗓️',
            'category': 'streaks',
            'requires_streak_days': 30,
            'rarity': 'rare',
            'experience_reward': 300
        },
        {
            'name': 'Centurion',
            'description': 'Maintain a 100-day streak',
            'icon': '💯',
            'category': 'streaks',
            'requires_streak_days': 100,
            'rarity': 'epic',
            'experience_reward': 1000
        },
        {
            'name': 'Break Compliance Expert',
            'description': 'Take 100 compliant breaks',
            'icon': '✅',
            'category': 'compliance',
            'requires_compliant_breaks': 100,
            'rarity': 'rare',
            'experience_reward': 250
        },
        {
            'name': 'Perfect Day',
            'description': 'Achieve 100% compliance for one day',
            'icon': '🌟',
            'category': 'compliance',
            'requires_perfect_days': 1,
            'rarity': 'common',
            'experience_reward': 75
        },
        {
            'name': 'Perfect Week',
            'description': 'Achieve 100% compliance for 7 consecutive days',
            'icon': '⭐',
            'category': 'compliance',
            'requires_perfect_days': 7,
            'rarity': 'epic',
            'experience_reward': 500
        },
        {
            'name': 'Early Bird',
            'description': 'Complete 20 sessions between 5 AM - 9 AM',
            'icon': '🌅',
            'category': 'timing',
            'special_requirements': {'early_bird_sessions': 20},
            'rarity': 'rare',
            'experience_reward': 200
        },
        {
            'name': 'Night Owl',
            'description': 'Complete 20 sessions between 6 PM - 12 AM',
            'icon': '🦉',
            'category': 'timing',
            'special_requirements': {'night_owl_sessions': 20},
            'rarity': 'rare',
            'experience_reward': 200
        },
        {
            'name': 'Weekend Warrior',
            'description': 'Complete 10 sessions on weekends',
            'icon': '🏖️',
            'category': 'timing',
            'special_requirements': {'weekend_sessions': 10},
            'rarity': 'rare',
            'experience_reward': 150
        },
        {
            'name': 'Consistency King',
            'description': 'Take 10 consecutive compliant breaks',
            'icon': '👑',
            'category': 'compliance',
            'special_requirements': {'consecutive_compliant_breaks': 10},
            'rarity': 'epic',
            'experience_reward': 400
        }
    ]

    created_badges = []
    for badge_data in default_badges:
        badge, created = Badge.objects.get_or_create(
            name=badge_data['name'],
            defaults=badge_data
        )
        if created:
            created_badges.append(badge)

    return created_badges


def award_session_completion_rewards(user: User, session: 'TimerSession') -> Dict[str, Any]:
    """
    Award experience and check badges when a session is completed - Optimized queries
    """
    # Base experience for completing a session
    base_experience = 10

    # Bonus experience for break compliance - Single optimized query
    compliance_bonus = 0
    if session.total_breaks_taken > 0:
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
            compliance_bonus = int(compliance_rate * 20)  # Up to 20 bonus XP

    # Length bonus for longer sessions
    length_bonus = min(session.total_intervals_completed * 2, 20)  # Up to 20 bonus XP

    total_experience = base_experience + compliance_bonus + length_bonus

    # Update user level
    update_user_level_progress(user, total_experience)

    # Check for new badges
    newly_awarded = check_and_award_badges(user)

    # Update challenge progress
    update_challenge_progress(user)

    return {
        'experience_gained': total_experience,
        'breakdown': {
            'base': base_experience,
            'compliance_bonus': compliance_bonus,
            'length_bonus': length_bonus
        },
        'badges_earned': [badge.badge.name for badge in newly_awarded]
    }


def calculate_experience_points(user: User, action_type: str = 'session_complete', **kwargs) -> int:
    """
    Calculate experience points for various user actions

    Args:
        user: User instance
        action_type: Type of action ('session_complete', 'break_compliance', 'streak_bonus', etc.)
        **kwargs: Additional parameters for calculation

    Returns:
        int: Experience points earned
    """
    base_experience = {
        'session_complete': 10,
        'break_compliance': 5,
        'streak_bonus': 15,
        'challenge_complete': 50,
        'badge_earned': 25,
        'level_up': 100
    }

    experience = base_experience.get(action_type, 0)

    # Apply multipliers based on user level
    try:
        level_data = UserLevel.objects.get(user=user)
        level_multiplier = 1.0 + (level_data.current_level * 0.1)  # 10% bonus per level
        experience = int(experience * level_multiplier)
    except UserLevel.DoesNotExist:
        pass

    # Apply specific bonuses
    if action_type == 'session_complete':
        session_length = kwargs.get('session_length', 1)
        experience += min(session_length * 2, 20)  # Up to 20 bonus XP for longer sessions

        compliance_rate = kwargs.get('compliance_rate', 0.0)
        experience += int(compliance_rate * 20)  # Up to 20 bonus XP for compliance

    elif action_type == 'streak_bonus':
        streak_days = kwargs.get('streak_days', 0)
        experience = min(streak_days * 5, 100)  # Up to 100 XP for streaks

    return max(experience, 0)


def check_badge_eligibility(user: User, badge_id: Optional[int] = None) -> List[Badge]:
    """
    Check which badges the user is eligible for

    Args:
        user: User instance to check
        badge_id: Optional specific badge ID to check

    Returns:
        List of Badge instances user is eligible for
    """
    # Get badges user doesn't have yet
    user_badge_ids = set(UserBadge.objects.filter(user=user).values_list('badge_id', flat=True))

    available_badges = Badge.objects.filter(is_active=True)
    if badge_id:
        available_badges = available_badges.filter(id=badge_id)
    else:
        available_badges = available_badges.exclude(id__in=user_badge_ids)

    # Get user statistics once
    user_stats = _get_user_statistics(user)

    eligible_badges = []
    for badge in available_badges:
        if _check_badge_requirements_optimized(user, badge, user_stats):
            eligible_badges.append(badge)

    return eligible_badges


def update_user_level(user: User, experience_points: int = 0) -> UserLevel:
    """
    Update user level based on experience points

    Args:
        user: User instance to update
        experience_points: Experience points to add (optional)

    Returns:
        Updated UserLevel instance
    """
    return update_user_level_progress(user, experience_points)


def calculate_streak_bonus(user: User) -> int:
    """
    Calculate streak bonus experience points

    Args:
        user: User instance

    Returns:
        int: Bonus experience points for current streak
    """
    try:
        streak_data = UserStreakData.objects.get(user=user)
        current_streak = streak_data.current_daily_streak

        # Bonus scaling: 5 XP per day for first 7 days, then 10 XP per day
        if current_streak <= 7:
            bonus = current_streak * 5
        else:
            bonus = (7 * 5) + ((current_streak - 7) * 10)

        # Cap the bonus at 200 XP
        return min(bonus, 200)
    except UserStreakData.DoesNotExist:
        return 0


def get_user_gamification_summary(user: User) -> Dict[str, Any]:
    """
    Get a comprehensive summary of user's gamification progress - Optimized queries
    """
    # Level data
    level_data, _ = UserLevel.objects.get_or_create(user=user)

    # Badges - Single query with aggregation
    badge_stats = Badge.objects.filter(is_active=True).aggregate(
        total_badges=Count('id'),
        user_badges=Count('id', filter=Q(userbadge__user=user))
    )
    user_badges = badge_stats['user_badges'] or 0
    total_badges = badge_stats['total_badges'] or 0

    # Recent achievements - Optimized query
    recent_achievements = Achievement.objects.select_related().filter(
        user=user
    ).order_by('-earned_at')[:5]

    # Active challenges - Optimized with select_related
    now = timezone.now()
    active_participations = ChallengeParticipation.objects.select_related(
        'challenge'
    ).filter(
        user=user,
        challenge__is_active=True,
        challenge__start_date__lte=now,
        challenge__end_date__gte=now
    )

    # Streak data
    try:
        streak_data = UserStreakData.objects.get(user=user)
    except UserStreakData.DoesNotExist:
        streak_data = None

    return {
        'level': {
            'current_level': level_data.current_level,
            'level_title': level_data.get_level_title(),
            'experience_points': level_data.total_experience_points,
            'experience_to_next': level_data.experience_to_next_level,
            'progress_percentage': (level_data.total_experience_points / level_data.experience_to_next_level) * 100 if level_data.experience_to_next_level > 0 else 100
        },
        'badges': {
            'earned': user_badges,
            'total': total_badges,
            'completion_percentage': (user_badges / total_badges) * 100 if total_badges > 0 else 0
        },
        'streaks': {
            'current_daily': streak_data.current_daily_streak if streak_data else 0,
            'best_daily': streak_data.best_daily_streak if streak_data else 0,
            'current_weekly': streak_data.current_weekly_streak if streak_data else 0,
            'best_weekly': streak_data.best_weekly_streak if streak_data else 0
        },
        'recent_achievements': [
            {
                'type': achievement.get_achievement_type_display(),
                'earned_at': achievement.earned_at,
                'description': achievement.description
            }
            for achievement in recent_achievements
        ],
        'active_challenges': [
            {
                'name': participation.challenge.name,
                'progress': participation.current_progress,
                'target': participation.challenge.target_value,
                'progress_percentage': participation.progress_percentage,
                'ends_at': participation.challenge.end_date
            }
            for participation in active_participations
        ]
    }