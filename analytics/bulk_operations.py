"""
Bulk operations utilities for performance optimization
Handles bulk database operations to reduce N+1 queries and improve performance
"""
from typing import Dict, List, Optional, Union, Any, QuerySet
from datetime import date, datetime, timedelta
from django.utils import timezone
from django.db.models import Sum, Count, Avg, Q, F, Max, Min, Prefetch
from django.db import transaction
from django.contrib.auth import get_user_model
import logging

from .models import DailyStats, WeeklyStats, MonthlyStats, RealTimeMetrics
from timer.models import TimerSession, BreakRecord, UserTimerSettings, TimerInterval
from accounts.models import UserStreakData, UserLevel, UserBadge, Achievement

User = get_user_model()
logger = logging.getLogger(__name__)


class BulkStatsService:
    """Service for bulk statistics operations"""

    @staticmethod
    def update_daily_stats_bulk(users: List[User], target_date: date) -> None:
        """
        Bulk update daily statistics for multiple users to improve performance
        Uses batch processing to minimize database queries
        """
        stats_to_create = []
        stats_to_update = []

        # Get existing stats for the target date
        existing_stats = {
            stat.user_id: stat for stat in DailyStats.objects.filter(
                user__in=users,
                date=target_date
            ).select_related('user')
        }

        # Bulk query for session data
        session_data = TimerSession.objects.filter(
            user__in=users,
            start_time__date=target_date,
            is_active=False
        ).values('user_id').annotate(
            total_work_minutes=Sum('total_work_minutes'),
            total_intervals=Sum('total_intervals_completed'),
            total_breaks=Sum('total_breaks_taken'),
            session_count=Count('id')
        )

        # Bulk query for break compliance data
        break_data = BreakRecord.objects.filter(
            user__in=users,
            break_start_time__date=target_date,
            break_completed=True
        ).values('user_id').annotate(
            total_breaks=Count('id'),
            compliant_breaks=Count(
                'id',
                filter=Q(break_duration_seconds__gte=20, looked_at_distance=True)
            ),
            avg_duration=Avg('break_duration_seconds')
        )

        # Convert to dictionaries for efficient lookup
        session_lookup = {item['user_id']: item for item in session_data}
        break_lookup = {item['user_id']: item for item in break_data}

        for user in users:
            user_session_data = session_lookup.get(user.id, {})
            user_break_data = break_lookup.get(user.id, {})

            total_work_minutes = user_session_data.get('total_work_minutes', 0) or 0
            total_intervals = user_session_data.get('total_intervals', 0) or 0
            total_breaks = user_session_data.get('total_breaks', 0) or 0
            session_count = user_session_data.get('session_count', 0) or 0

            breaks_compliant = user_break_data.get('compliant_breaks', 0) or 0
            avg_break_duration = user_break_data.get('avg_duration', 0.0) or 0.0

            # Calculate compliance rate
            total_breaks_taken = user_break_data.get('total_breaks', 0) or 0
            compliance_rate = (breaks_compliant / total_breaks_taken * 100) if total_breaks_taken > 0 else 0.0

            if user.id in existing_stats:
                # Update existing stats
                stats = existing_stats[user.id]
                stats.total_work_minutes = total_work_minutes
                stats.total_intervals_completed = total_intervals
                stats.total_breaks_taken = total_breaks
                stats.total_sessions = session_count
                stats.breaks_compliant = breaks_compliant
                stats.average_break_duration = avg_break_duration
                stats_to_update.append(stats)
            else:
                # Create new stats
                stats_to_create.append(DailyStats(
                    user=user,
                    date=target_date,
                    total_work_minutes=total_work_minutes,
                    total_intervals_completed=total_intervals,
                    total_breaks_taken=total_breaks,
                    total_sessions=session_count,
                    breaks_compliant=breaks_compliant,
                    average_break_duration=avg_break_duration
                ))

        # Bulk create and update
        with transaction.atomic():
            if stats_to_create:
                DailyStats.objects.bulk_create(stats_to_create, batch_size=100)

            if stats_to_update:
                DailyStats.objects.bulk_update(
                    stats_to_update,
                    ['total_work_minutes', 'total_intervals_completed', 'total_breaks_taken',
                     'total_sessions', 'breaks_compliant', 'average_break_duration'],
                    batch_size=100
                )

    @staticmethod
    def calculate_weekly_stats_bulk(users: List[User], week_start: date) -> None:
        """Bulk calculate weekly statistics for multiple users"""
        week_end = week_start + timedelta(days=6)

        # Get daily stats for the week for all users
        daily_stats = DailyStats.objects.filter(
            user__in=users,
            date__gte=week_start,
            date__lte=week_end
        ).values('user_id').annotate(
            total_work_minutes=Sum('total_work_minutes'),
            total_intervals=Sum('total_intervals_completed'),
            total_breaks=Sum('total_breaks_taken'),
            total_sessions=Sum('total_sessions'),
            total_breaks_compliant=Sum('breaks_compliant'),
            active_days=Count('id', filter=Q(total_sessions__gt=0))
        )

        weekly_stats_to_create = []
        weekly_stats_to_update = []

        # Get existing weekly stats
        existing_weekly = {
            stat.user_id: stat for stat in WeeklyStats.objects.filter(
                user__in=users,
                week_start_date=week_start
            )
        }

        for stats_data in daily_stats:
            user_id = stats_data['user_id']
            total_work_minutes = stats_data['total_work_minutes'] or 0
            total_breaks = stats_data['total_breaks_taken'] or 0
            compliant_breaks = stats_data['total_breaks_compliant'] or 0
            active_days = stats_data['active_days'] or 0

            # Calculate weekly metrics
            avg_daily_work = total_work_minutes / 7.0
            avg_daily_breaks = total_breaks / 7.0
            compliance_rate = (compliant_breaks / total_breaks * 100) if total_breaks > 0 else 0.0

            weekly_data = {
                'total_work_minutes': total_work_minutes,
                'total_intervals_completed': stats_data['total_intervals'] or 0,
                'total_breaks_taken': total_breaks,
                'total_sessions': stats_data['total_sessions'] or 0,
                'active_days': active_days,
                'average_daily_work_minutes': avg_daily_work,
                'average_daily_breaks': avg_daily_breaks,
                'total_breaks_compliant': compliant_breaks,
                'weekly_compliance_rate': compliance_rate
            }

            if user_id in existing_weekly:
                # Update existing
                weekly_stat = existing_weekly[user_id]
                for key, value in weekly_data.items():
                    setattr(weekly_stat, key, value)
                weekly_stats_to_update.append(weekly_stat)
            else:
                # Create new
                user = next((u for u in users if u.id == user_id), None)
                if user:
                    weekly_stats_to_create.append(WeeklyStats(
                        user=user,
                        week_start_date=week_start,
                        week_end_date=week_end,
                        **weekly_data
                    ))

        # Bulk operations
        with transaction.atomic():
            if weekly_stats_to_create:
                WeeklyStats.objects.bulk_create(weekly_stats_to_create, batch_size=50)

            if weekly_stats_to_update:
                WeeklyStats.objects.bulk_update(
                    weekly_stats_to_update,
                    list(weekly_data.keys()),
                    batch_size=50
                )


class BulkGamificationService:
    """Service for bulk gamification operations"""

    @staticmethod
    def update_user_levels_bulk(users: List[User], experience_data: Dict[int, int]) -> None:
        """
        Bulk update user levels and experience points

        Args:
            users: List of User objects
            experience_data: Dict mapping user_id to experience points to add
        """
        # Get existing level data
        existing_levels = {
            level.user_id: level for level in UserLevel.objects.filter(
                user__in=users
            )
        }

        levels_to_create = []
        levels_to_update = []

        for user in users:
            experience_to_add = experience_data.get(user.id, 0)
            if experience_to_add <= 0:
                continue

            if user.id in existing_levels:
                level_data = existing_levels[user.id]
                level_data.add_experience(experience_to_add)
                levels_to_update.append(level_data)
            else:
                # Create new level data
                level_data = UserLevel(
                    user=user,
                    total_experience_points=experience_to_add
                )
                level_data.add_experience(0)  # This will handle level calculations
                levels_to_create.append(level_data)

        # Bulk operations
        with transaction.atomic():
            if levels_to_create:
                UserLevel.objects.bulk_create(levels_to_create, batch_size=100)

            if levels_to_update:
                UserLevel.objects.bulk_update(
                    levels_to_update,
                    ['current_level', 'total_experience_points', 'experience_to_next_level'],
                    batch_size=100
                )

    @staticmethod
    def check_badge_requirements_bulk(users: List[User]) -> Dict[int, List[int]]:
        """
        Bulk check badge requirements for multiple users

        Returns:
            Dict mapping user_id to list of badge_ids they should receive
        """
        from accounts.models import Badge

        # Get all active badges
        badges = Badge.objects.filter(is_active=True)

        # Get existing user badges
        existing_badges = UserBadge.objects.filter(
            user__in=users
        ).values_list('user_id', 'badge_id')

        user_existing_badges = {}
        for user_id, badge_id in existing_badges:
            if user_id not in user_existing_badges:
                user_existing_badges[user_id] = set()
            user_existing_badges[user_id].add(badge_id)

        # Bulk get user statistics for badge checking
        user_stats_bulk = BulkGamificationService._get_user_stats_bulk(users)

        # Check requirements for each user
        new_badges = {}
        for user in users:
            user_stats = user_stats_bulk.get(user.id, {})
            existing_badge_ids = user_existing_badges.get(user.id, set())

            qualified_badges = []
            for badge in badges:
                if badge.id in existing_badge_ids:
                    continue

                if BulkGamificationService._check_badge_requirements(badge, user_stats):
                    qualified_badges.append(badge.id)

            if qualified_badges:
                new_badges[user.id] = qualified_badges

        return new_badges

    @staticmethod
    def _get_user_stats_bulk(users: List[User]) -> Dict[int, Dict[str, Any]]:
        """Get user statistics in bulk for badge checking"""
        # Get streak data
        streak_data = {
            streak.user_id: streak for streak in UserStreakData.objects.filter(
                user__in=users
            )
        }

        # Get session statistics
        session_stats = TimerSession.objects.filter(
            user__in=users,
            is_active=False
        ).values('user_id').annotate(
            total_sessions=Count('id'),
            total_breaks=Count('breaks__id', filter=Q(breaks__break_completed=True)),
            compliant_breaks=Count(
                'breaks__id',
                filter=Q(
                    breaks__break_completed=True,
                    breaks__break_duration_seconds__gte=20,
                    breaks__looked_at_distance=True
                )
            )
        )

        # Get perfect days count
        perfect_days = DailyStats.objects.filter(
            user__in=users,
            compliance_rate=100.0
        ).values('user_id').annotate(
            perfect_count=Count('id')
        )

        # Combine all data
        user_stats = {}
        session_lookup = {item['user_id']: item for item in session_stats}
        perfect_lookup = {item['user_id']: item['perfect_count'] for item in perfect_days}

        for user in users:
            streak = streak_data.get(user.id)
            session_data = session_lookup.get(user.id, {})

            total_sessions = session_data.get('total_sessions', 0) or 0
            total_breaks = session_data.get('total_breaks', 0) or 0
            compliant_breaks = session_data.get('compliant_breaks', 0) or 0

            compliance_rate = (compliant_breaks / total_breaks * 100) if total_breaks > 0 else 0

            user_stats[user.id] = {
                'user': user,
                'current_streak': streak.current_daily_streak if streak else 0,
                'total_sessions': total_sessions,
                'total_breaks': total_breaks,
                'compliant_breaks': compliant_breaks,
                'compliance_rate': compliance_rate,
                'perfect_days': perfect_lookup.get(user.id, 0)
            }

        return user_stats

    @staticmethod
    def _check_badge_requirements(badge, user_stats: Dict[str, Any]) -> bool:
        """Check if user meets badge requirements"""
        # This is the same logic as in BadgeService but optimized for bulk operations
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

        return True


class BulkQueryOptimizer:
    """Utility class for optimizing common bulk query patterns"""

    @staticmethod
    def get_user_dashboard_data_bulk(users: List[User]) -> Dict[int, Dict[str, Any]]:
        """Get dashboard data for multiple users in optimized bulk queries"""
        user_ids = [user.id for user in users]

        # Bulk query for user settings
        settings_data = {
            setting.user_id: setting for setting in UserTimerSettings.objects.filter(
                user__in=users
            )
        }

        # Bulk query for today's stats
        today = date.today()
        today_stats_data = {
            stat.user_id: stat for stat in DailyStats.objects.filter(
                user__in=users,
                date=today
            )
        }

        # Bulk query for active sessions
        active_sessions_data = {
            session.user_id: session for session in TimerSession.objects.filter(
                user__in=users,
                is_active=True
            ).select_related('user')
        }

        # Bulk query for streak data
        streak_data = {
            streak.user_id: streak for streak in UserStreakData.objects.filter(
                user__in=users
            )
        }

        # Combine data for each user
        result = {}
        for user in users:
            result[user.id] = {
                'user': user,
                'settings': settings_data.get(user.id),
                'today_stats': today_stats_data.get(user.id),
                'active_session': active_sessions_data.get(user.id),
                'streak_data': streak_data.get(user.id),
            }

        return result

    @staticmethod
    def prefetch_session_relationships(sessions_queryset: QuerySet) -> QuerySet:
        """Add optimized prefetching for session relationships"""
        return sessions_queryset.select_related('user').prefetch_related(
            Prefetch(
                'intervals',
                queryset=TimerInterval.objects.select_related().order_by('interval_number')
            ),
            Prefetch(
                'breaks',
                queryset=BreakRecord.objects.select_related().order_by('-break_start_time')
            )
        )

    @staticmethod
    def get_user_analytics_bulk(users: List[User], days: int = 30) -> Dict[int, Dict[str, Any]]:
        """Get analytics data for multiple users efficiently"""
        end_date = date.today()
        start_date = end_date - timedelta(days=days)

        # Bulk query for period statistics
        period_stats = DailyStats.objects.filter(
            user__in=users,
            date__gte=start_date,
            date__lte=end_date
        ).values('user_id').annotate(
            total_work_minutes=Sum('total_work_minutes'),
            total_sessions=Sum('total_sessions'),
            total_breaks=Sum('total_breaks_taken'),
            compliant_breaks=Sum('breaks_compliant'),
            active_days=Count('id', filter=Q(total_sessions__gt=0))
        )

        # Convert to user-keyed dictionary
        result = {}
        for stat in period_stats:
            user_id = stat['user_id']
            total_breaks = stat['total_breaks'] or 0
            compliant_breaks = stat['compliant_breaks'] or 0

            compliance_rate = (compliant_breaks / total_breaks * 100) if total_breaks > 0 else 0.0

            result[user_id] = {
                'total_work_hours': (stat['total_work_minutes'] or 0) / 60.0,
                'total_sessions': stat['total_sessions'] or 0,
                'total_breaks': total_breaks,
                'compliance_rate': compliance_rate,
                'active_days': stat['active_days'] or 0,
                'period_days': days
            }

        return result