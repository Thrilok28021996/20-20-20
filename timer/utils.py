"""
Utility functions for timer functionality and data management
Includes optimized database query utilities to reduce N+1 queries and improve performance
"""
from django.utils import timezone
from django.db.models import Count, Sum, Avg, Q, Prefetch
from datetime import date, timedelta
from .models import TimerSession, BreakRecord, UserTimerSettings, TimerInterval
from analytics.models import DailyStats
from accounts.models import UserProfile, UserStreakData


def get_user_dashboard_data(user):
    """
    Get comprehensive dashboard data for a user, handling new user scenarios gracefully
    """
    # Ensure user profile exists
    profile, created = UserProfile.objects.get_or_create(user=user)

    # Ensure streak data exists
    streak_data, created = UserStreakData.objects.get_or_create(user=user)

    # Get or create today's stats
    today = date.today()
    today_stats, created = DailyStats.objects.get_or_create(
        user=user,
        date=today,
        defaults={
            'total_work_minutes': 0,
            'total_intervals_completed': 0,
            'total_breaks_taken': 0,
            'total_sessions': 0,
            'breaks_on_time': 0,
            'breaks_compliant': 0,
            'average_break_duration': 0.0,
            'streak_maintained': False,
            'productivity_score': 0.0
        }
    )

    # Calculate real-time stats for today - Optimized with aggregation
    today_session_stats = TimerSession.objects.filter(
        user=user,
        start_time__date=today
    ).aggregate(
        total_work_minutes=Sum('total_work_minutes'),
        total_intervals=Sum('total_intervals_completed'),
        total_breaks=Sum('total_breaks_taken'),
        total_sessions=Count('id')
    )

    total_work_minutes = today_session_stats['total_work_minutes'] or 0
    total_intervals = today_session_stats['total_intervals'] or 0
    total_breaks = today_session_stats['total_breaks'] or 0
    total_sessions_count = today_session_stats['total_sessions'] or 0

    # Update today's stats if they differ from real-time calculation
    if (today_stats.total_work_minutes != total_work_minutes or
        today_stats.total_intervals_completed != total_intervals or
        today_stats.total_breaks_taken != total_breaks or
        today_stats.total_sessions != total_sessions_count):

        today_stats.total_work_minutes = total_work_minutes
        today_stats.total_intervals_completed = total_intervals
        today_stats.total_breaks_taken = total_breaks
        today_stats.total_sessions = total_sessions_count

        # Calculate compliance - Optimized with aggregation
        today_break_stats = BreakRecord.objects.filter(
            user=user,
            break_start_time__date=today,
            break_completed=True
        ).aggregate(
            compliant_breaks=Count(
                'id',
                filter=Q(break_duration_seconds__gte=20, looked_at_distance=True)
            ),
            avg_duration=Avg('break_duration_seconds')
        )

        today_stats.breaks_compliant = today_break_stats['compliant_breaks'] or 0

        if total_breaks > 0:
            today_stats.average_break_duration = today_break_stats['avg_duration'] or 0

        today_stats.save()

    return {
        'profile': profile,
        'streak_data': streak_data,
        'today_stats': today_stats,
        'is_new_user': _is_new_user(user)
    }


def _is_new_user(user):
    """
    Determine if this is a new user (no completed sessions)
    """
    return not TimerSession.objects.filter(user=user, is_active=False).exists()


def get_user_statistics_summary(user, days=30):
    """
    Get user statistics summary with graceful handling for no data
    """
    end_date = date.today()
    start_date = end_date - timedelta(days=days)

    # Get daily stats for the period
    daily_stats = DailyStats.objects.filter(
        user=user,
        date__gte=start_date,
        date__lte=end_date
    ).order_by('date')

    if not daily_stats.exists():
        return _get_empty_statistics_summary(days)

    # Calculate aggregated statistics
    total_work_minutes = sum(stat.total_work_minutes for stat in daily_stats)
    total_intervals = sum(stat.total_intervals_completed for stat in daily_stats)
    total_breaks = sum(stat.total_breaks_taken for stat in daily_stats)
    total_sessions = sum(stat.total_sessions for stat in daily_stats)
    total_compliant_breaks = sum(stat.breaks_compliant for stat in daily_stats)

    active_days = daily_stats.filter(total_sessions__gt=0).count()
    avg_compliance = (sum(stat.compliance_rate for stat in daily_stats) /
                     len(daily_stats)) if daily_stats else 0

    # Calculate productivity score
    consistency_score = (active_days / days) * 100 if days > 0 else 0
    productivity_score = (avg_compliance * 0.6 + consistency_score * 0.4)

    return {
        'period_days': days,
        'active_days': active_days,
        'total_work_hours': round(total_work_minutes / 60, 1),
        'total_intervals': total_intervals,
        'total_breaks': total_breaks,
        'total_sessions': total_sessions,
        'avg_compliance_rate': round(avg_compliance, 1),
        'consistency_score': round(consistency_score, 1),
        'productivity_score': round(productivity_score, 1),
        'chart_data': _prepare_chart_data(daily_stats),
        'insights': _generate_insights(user, daily_stats)
    }


def _get_empty_statistics_summary(days):
    """
    Return empty statistics summary for new users
    """
    return {
        'period_days': days,
        'active_days': 0,
        'total_work_hours': 0.0,
        'total_intervals': 0,
        'total_breaks': 0,
        'total_sessions': 0,
        'avg_compliance_rate': 0.0,
        'consistency_score': 0.0,
        'productivity_score': 0.0,
        'chart_data': {
            'dates': [],
            'work_minutes': [],
            'breaks_taken': [],
            'compliance_rates': []
        },
        'insights': [{
            'type': 'welcome',
            'title': 'Welcome to EyeHealth 20-20-20!',
            'message': 'Start your first timer session to begin tracking your eye health progress.',
            'priority': 'high'
        }]
    }


def _prepare_chart_data(daily_stats):
    """
    Prepare chart data from daily statistics
    """
    return {
        'dates': [stat.date.strftime('%Y-%m-%d') for stat in daily_stats],
        'work_minutes': [stat.total_work_minutes for stat in daily_stats],
        'breaks_taken': [stat.total_breaks_taken for stat in daily_stats],
        'compliance_rates': [stat.compliance_rate for stat in daily_stats],
        'productivity_scores': [stat.productivity_score for stat in daily_stats]
    }


def _generate_insights(user, daily_stats):
    """
    Generate insights based on user data
    """
    if not daily_stats:
        return [{
            'type': 'welcome',
            'title': 'Get Started',
            'message': 'Complete your first timer session to start tracking your progress!',
            'priority': 'high'
        }]

    insights = []

    # Calculate averages
    avg_work_minutes = sum(stat.total_work_minutes for stat in daily_stats) / len(daily_stats)
    avg_breaks = sum(stat.total_breaks_taken for stat in daily_stats) / len(daily_stats)
    avg_compliance = sum(stat.compliance_rate for stat in daily_stats) / len(daily_stats)

    # Work time insights
    if avg_work_minutes > 480:  # More than 8 hours
        insights.append({
            'type': 'health',
            'title': 'Long Work Sessions',
            'message': 'You\'re working long hours. Consider taking more frequent breaks to protect your eyes.',
            'priority': 'medium'
        })
    elif avg_work_minutes < 120:  # Less than 2 hours
        insights.append({
            'type': 'engagement',
            'title': 'Light Usage',
            'message': 'Try using the timer for more of your screen time to maximize eye health benefits.',
            'priority': 'low'
        })

    # Compliance insights
    if avg_compliance > 80:
        insights.append({
            'type': 'achievement',
            'title': 'Excellent Compliance!',
            'message': f'Your {avg_compliance:.1f}% compliance rate is outstanding! Keep up the great work.',
            'priority': 'low'
        })
    elif avg_compliance > 60:
        insights.append({
            'type': 'improvement',
            'title': 'Good Progress',
            'message': 'You\'re doing well with breaks. Try to be more consistent for even better results.',
            'priority': 'medium'
        })
    else:
        insights.append({
            'type': 'reminder',
            'title': 'Focus on Breaks',
            'message': 'Remember to take regular breaks every 20 minutes. Your eyes will thank you!',
            'priority': 'high'
        })

    # Break frequency insights
    if avg_breaks < 3:
        insights.append({
            'type': 'reminder',
            'title': 'Take More Breaks',
            'message': 'Aim for at least one break every 20 minutes during work sessions.',
            'priority': 'medium'
        })

    return insights


def update_user_settings_safely(user, **kwargs):
    """
    Safely update user timer settings with validation
    """
    settings, created = UserTimerSettings.objects.get_or_create(user=user)

    # Validate and update settings
    if 'work_interval_minutes' in kwargs:
        value = int(kwargs['work_interval_minutes'])
        if 5 <= value <= 60:  # Reasonable range
            settings.work_interval_minutes = value

    if 'break_duration_seconds' in kwargs:
        value = int(kwargs['break_duration_seconds'])
        if 10 <= value <= 300:  # 10 seconds to 5 minutes
            settings.break_duration_seconds = value

    if 'sound_notification' in kwargs:
        settings.sound_notification = bool(kwargs['sound_notification'])

    if 'desktop_notification' in kwargs:
        settings.desktop_notification = bool(kwargs['desktop_notification'])

    if 'smart_break_enabled' in kwargs:
        settings.smart_break_enabled = bool(kwargs['smart_break_enabled'])

    if 'preferred_break_duration' in kwargs:
        value = int(kwargs['preferred_break_duration'])
        valid_durations = [choice[0] for choice in UserTimerSettings.BREAK_DURATION_CHOICES]
        if value in valid_durations:
            settings.preferred_break_duration = value

    if 'sound_volume' in kwargs:
        value = float(kwargs['sound_volume'])
        if 0.0 <= value <= 1.0:
            settings.sound_volume = value

    settings.save()
    return settings


def get_user_break_preferences(user):
    """
    Get user's break preferences with intelligent defaults
    """
    settings, created = UserTimerSettings.objects.get_or_create(user=user)

    # Calculate smart break duration based on user's history
    if settings.smart_break_enabled:
        recent_breaks = BreakRecord.objects.filter(
            user=user,
            break_completed=True,
            break_start_time__gte=timezone.now() - timedelta(days=30)
        ).order_by('-break_start_time')[:50]

        if recent_breaks:
            avg_duration = sum(br.break_duration_seconds for br in recent_breaks) / len(recent_breaks)
            completion_rate = sum(1 for br in recent_breaks if br.is_compliant) / len(recent_breaks)

            # Adjust preferred duration based on user behavior
            if completion_rate < 0.5 and avg_duration > settings.preferred_break_duration:
                # User struggles with current duration, suggest shorter
                suggested_duration = max(10, int(avg_duration * 0.8))
            elif completion_rate > 0.8 and avg_duration > settings.preferred_break_duration * 1.2:
                # User consistently takes longer breaks, suggest longer
                suggested_duration = min(60, int(avg_duration))
            else:
                suggested_duration = settings.preferred_break_duration
        else:
            suggested_duration = settings.preferred_break_duration
    else:
        suggested_duration = settings.break_duration_seconds

    return {
        'current_duration': settings.get_effective_break_duration(),
        'suggested_duration': suggested_duration,
        'smart_enabled': settings.smart_break_enabled,
        'user_average': _get_user_average_break_duration(user),
        'completion_rate': _get_user_break_completion_rate(user)
    }


def _get_user_average_break_duration(user):
    """
    Calculate user's average break duration from recent history
    """
    recent_breaks = BreakRecord.objects.filter(
        user=user,
        break_completed=True,
        break_start_time__gte=timezone.now() - timedelta(days=30)
    )

    if recent_breaks:
        return sum(br.break_duration_seconds for br in recent_breaks) / recent_breaks.count()
    return 0


def _get_user_break_completion_rate(user):
    """
    Calculate user's break completion rate from recent history
    """
    recent_breaks = BreakRecord.objects.filter(
        user=user,
        break_start_time__gte=timezone.now() - timedelta(days=30)
    )

    if recent_breaks:
        completed_breaks = recent_breaks.filter(break_completed=True).count()
        return (completed_breaks / recent_breaks.count()) * 100
    return 0


# ===== OPTIMIZED DATABASE QUERY UTILITIES =====

def get_optimized_recent_sessions(user, limit=10):
    """
    Get recent timer sessions with optimized prefetching to avoid N+1 queries

    Args:
        user: The user object
        limit: Number of recent sessions to retrieve

    Returns:
        QuerySet of TimerSession objects with optimized prefetching
    """
    return TimerSession.objects.select_related('user').prefetch_related(
        # Prefetch intervals and their related break records
        Prefetch(
            'intervals',
            queryset=TimerInterval.objects.select_related().order_by('interval_number')
        ),
        # Prefetch break records with relevant fields
        Prefetch(
            'breaks',
            queryset=BreakRecord.objects.select_related().order_by('-break_start_time')
        )
    ).filter(
        user=user
    ).order_by('-start_time')[:limit]


def get_user_session_statistics_optimized(user, start_date=None, end_date=None):
    """
    Get comprehensive session statistics for a user with optimized queries

    Args:
        user: The user object
        start_date: Optional start date for filtering
        end_date: Optional end date for filtering

    Returns:
        Dictionary containing session statistics
    """
    # Default to last 30 days if no dates provided
    if not end_date:
        end_date = date.today()
    if not start_date:
        start_date = end_date - timedelta(days=30)

    # Single query to get all session statistics
    session_stats = TimerSession.objects.filter(
        user=user,
        start_time__date__gte=start_date,
        start_time__date__lte=end_date,
        is_active=False
    ).aggregate(
        total_sessions=Count('id'),
        total_work_minutes=Sum('total_work_minutes'),
        total_intervals=Sum('total_intervals_completed'),
        total_breaks=Sum('total_breaks_taken'),
        avg_session_length=Avg('total_work_minutes')
    )

    # Single query to get break compliance statistics
    break_stats = BreakRecord.objects.filter(
        user=user,
        break_start_time__date__gte=start_date,
        break_start_time__date__lte=end_date,
        break_completed=True
    ).aggregate(
        total_breaks_taken=Count('id'),
        compliant_breaks=Count(
            'id',
            filter=Q(break_duration_seconds__gte=20, looked_at_distance=True)
        ),
        avg_break_duration=Avg('break_duration_seconds')
    )

    # Calculate compliance rate
    total_breaks = break_stats['total_breaks_taken'] or 0
    compliant_breaks = break_stats['compliant_breaks'] or 0
    compliance_rate = (compliant_breaks / total_breaks * 100) if total_breaks > 0 else 0

    return {
        'total_sessions': session_stats['total_sessions'] or 0,
        'total_work_minutes': session_stats['total_work_minutes'] or 0,
        'total_work_hours': (session_stats['total_work_minutes'] or 0) / 60.0,
        'total_intervals': session_stats['total_intervals'] or 0,
        'total_breaks': total_breaks,
        'compliant_breaks': compliant_breaks,
        'compliance_rate': round(compliance_rate, 1),
        'avg_session_length': round(session_stats['avg_session_length'] or 0, 1),
        'avg_break_duration': round(break_stats['avg_break_duration'] or 0, 1)
    }


def bulk_update_daily_stats(users_data):
    """
    Bulk update daily statistics for multiple users to improve performance

    Args:
        users_data: List of dictionaries containing user stats data

    Example:
        users_data = [
            {
                'user': user_obj,
                'date': date_obj,
                'total_work_minutes': 120,
                'total_intervals_completed': 6,
                'total_breaks_taken': 5,
                'total_sessions': 2
            },
            ...
        ]
    """
    daily_stats_to_create = []
    daily_stats_to_update = []

    for data in users_data:
        stats, created = DailyStats.objects.get_or_create(
            user=data['user'],
            date=data['date'],
            defaults={
                'total_work_minutes': data.get('total_work_minutes', 0),
                'total_intervals_completed': data.get('total_intervals_completed', 0),
                'total_breaks_taken': data.get('total_breaks_taken', 0),
                'total_sessions': data.get('total_sessions', 0),
            }
        )

        if not created:
            # Update existing stats
            stats.total_work_minutes += data.get('total_work_minutes', 0)
            stats.total_intervals_completed += data.get('total_intervals_completed', 0)
            stats.total_breaks_taken += data.get('total_breaks_taken', 0)
            stats.total_sessions += data.get('total_sessions', 0)
            daily_stats_to_update.append(stats)

    # Bulk update existing records
    if daily_stats_to_update:
        DailyStats.objects.bulk_update(
            daily_stats_to_update,
            ['total_work_minutes', 'total_intervals_completed', 'total_breaks_taken', 'total_sessions']
        )


def calculate_session_compliance_rate_optimized(session):
    """
    Calculate compliance rate for a specific session using optimized query

    Args:
        session: TimerSession object

    Returns:
        Float: Compliance rate as percentage (0-100)
    """
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

    return (compliant_breaks / total_breaks * 100) if total_breaks > 0 else 0


def get_user_productivity_patterns_optimized(user, days=30):
    """
    Analyze user productivity patterns with optimized database queries

    Args:
        user: The user object
        days: Number of days to analyze

    Returns:
        Dictionary containing productivity pattern analysis
    """
    from django.db.models.functions import Extract

    end_date = date.today()
    start_date = end_date - timedelta(days=days)

    # Hourly patterns using database aggregation
    hourly_patterns = TimerSession.objects.filter(
        user=user,
        start_time__date__gte=start_date,
        start_time__date__lte=end_date,
        is_active=False
    ).annotate(
        hour=Extract('start_time', 'hour')
    ).values('hour').annotate(
        sessions=Count('id'),
        work_minutes=Sum('total_work_minutes')
    ).order_by('hour')

    # Daily patterns using database aggregation
    daily_patterns = TimerSession.objects.filter(
        user=user,
        start_time__date__gte=start_date,
        start_time__date__lte=end_date,
        is_active=False
    ).annotate(
        weekday=Extract('start_time', 'week_day')
    ).values('weekday').annotate(
        sessions=Count('id'),
        work_minutes=Sum('total_work_minutes')
    ).order_by('weekday')

    # Convert to more readable format
    weekday_names = {
        1: 'Sunday', 2: 'Monday', 3: 'Tuesday', 4: 'Wednesday',
        5: 'Thursday', 6: 'Friday', 7: 'Saturday'
    }

    return {
        'hourly_patterns': list(hourly_patterns),
        'daily_patterns': [
            {
                'day': weekday_names[pattern['weekday']],
                'sessions': pattern['sessions'],
                'work_minutes': pattern['work_minutes']
            }
            for pattern in daily_patterns
        ],
        'analysis_period': f"{start_date} to {end_date}",
        'total_days': days
    }


def optimize_break_preferences_analysis(user):
    """
    Optimized analysis of user's break taking preferences

    Args:
        user: The user object

    Returns:
        Dictionary containing break preference analysis
    """
    from django.db.models.functions import Extract

    # Get break statistics for last 30 days
    end_date = date.today()
    start_date = end_date - timedelta(days=30)

    # Single query to get comprehensive break statistics
    break_stats = BreakRecord.objects.filter(
        user=user,
        break_start_time__date__gte=start_date,
        break_start_time__date__lte=end_date,
        break_completed=True
    ).aggregate(
        total_breaks=Count('id'),
        avg_duration=Avg('break_duration_seconds'),
        compliant_breaks=Count(
            'id',
            filter=Q(break_duration_seconds__gte=20, looked_at_distance=True)
        ),
        looks_at_distance_count=Count(
            'id',
            filter=Q(looked_at_distance=True)
        )
    )

    # Get preferred break times using database aggregation
    preferred_times = BreakRecord.objects.filter(
        user=user,
        break_start_time__date__gte=start_date,
        break_start_time__date__lte=end_date,
        break_completed=True
    ).annotate(
        hour=Extract('break_start_time', 'hour')
    ).values('hour').annotate(
        count=Count('id')
    ).order_by('-count')[:5]  # Top 5 preferred hours

    total_breaks = break_stats['total_breaks'] or 0
    compliant_breaks = break_stats['compliant_breaks'] or 0

    return {
        'total_breaks': total_breaks,
        'average_duration': round(break_stats['avg_duration'] or 0, 1),
        'compliance_rate': round((compliant_breaks / total_breaks * 100) if total_breaks > 0 else 0, 1),
        'distance_look_rate': round((break_stats['looks_at_distance_count'] or 0) / total_breaks * 100 if total_breaks > 0 else 0, 1),
        'preferred_hours': [
            {
                'hour': time_data['hour'],
                'count': time_data['count'],
                'percentage': round(time_data['count'] / total_breaks * 100, 1) if total_breaks > 0 else 0
            }
            for time_data in preferred_times
        ],
        'analysis_period': f"{start_date} to {end_date}"
    }


def cache_user_statistics(user, cache_key_prefix='user_stats'):
    """
    Cache user statistics to reduce database queries for frequently accessed data

    Args:
        user: The user object
        cache_key_prefix: Prefix for cache key

    Returns:
        Dictionary containing cached statistics
    """
    from django.core.cache import cache

    cache_key = f"{cache_key_prefix}_{user.id}"
    cached_stats = cache.get(cache_key)

    if cached_stats is None:
        # Calculate and cache statistics
        cached_stats = get_user_session_statistics_optimized(user)
        # Cache for 15 minutes
        cache.set(cache_key, cached_stats, 15 * 60)

    return cached_stats


def invalidate_user_stats_cache(user, cache_key_prefix='user_stats'):
    """
    Invalidate cached user statistics when data changes

    Args:
        user: The user object
        cache_key_prefix: Prefix for cache key
    """
    from django.core.cache import cache

    cache_key = f"{cache_key_prefix}_{user.id}"
    cache.delete(cache_key)