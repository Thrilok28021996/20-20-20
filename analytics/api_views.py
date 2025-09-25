"""
API views for real-time analytics and metrics
"""
from django.http import JsonResponse
from django.contrib.auth.decorators import login_required
from django.views.decorators.http import require_http_methods
from django.utils import timezone
from django.db.models import Sum, Count, Avg, Q
from datetime import datetime, timedelta, date
import json

from .models import (
    RealTimeMetrics, UserSession, LiveActivityFeed,
    DailyStats, UserSatisfactionRating
)
from timer.models import TimerSession, BreakRecord
from accounts.models import User


@login_required
@require_http_methods(["GET"])
def real_time_metrics_api(request):
    """
    API endpoint for real-time dashboard metrics
    """
    # Check if user is admin for global metrics
    if request.user.is_staff or request.user.is_superuser:
        # Get or create latest real-time metrics
        metrics = RealTimeMetrics.get_latest_metrics()

        return JsonResponse({
            'success': True,
            'global_metrics': {
                'active_users': metrics.active_users_count,
                'total_breaks_today': metrics.total_breaks_today,
                'total_work_minutes_today': metrics.total_work_minutes_today,
                'users_working': metrics.users_working,
                'users_in_break': metrics.users_in_break,
                'average_satisfaction': metrics.average_satisfaction_rating,
                'nps_score': metrics.nps_score,
                'last_updated': metrics.timestamp.isoformat()
            }
        })
    else:
        return JsonResponse({
            'success': False,
            'error': 'Admin access required for global metrics'
        })


@login_required
@require_http_methods(["GET"])
def dashboard_metrics_api(request):
    """
    API endpoint for user's personal dashboard metrics
    """
    today = date.today()

    # Get today's stats for the user
    today_stats, created = DailyStats.objects.get_or_create(
        user=request.user,
        date=today
    )

    # Calculate real-time metrics for today
    today_sessions = TimerSession.objects.filter(
        user=request.user,
        start_time__date=today
    )

    today_breaks = BreakRecord.objects.filter(
        user=request.user,
        break_start_time__date=today,
        break_completed=True
    )

    # Calculate compliance rate
    total_breaks = today_breaks.count()
    compliant_breaks = today_breaks.filter(
        break_duration_seconds__gte=20,
        looked_at_distance=True
    ).count()

    compliance_rate = (compliant_breaks / total_breaks * 100) if total_breaks > 0 else 0

    # Get week stats for comparison
    week_start = today - timedelta(days=7)
    week_sessions = TimerSession.objects.filter(
        user=request.user,
        start_time__date__gte=week_start,
        start_time__date__lte=today
    )

    week_work_minutes = sum(session.total_work_minutes for session in week_sessions)
    week_breaks = BreakRecord.objects.filter(
        user=request.user,
        break_start_time__date__gte=week_start,
        break_start_time__date__lte=today,
        break_completed=True
    ).count()

    return JsonResponse({
        'success': True,
        'today': {
            'work_minutes': today_stats.total_work_minutes,
            'breaks_taken': today_stats.total_breaks_taken,
            'intervals_completed': today_stats.total_intervals_completed,
            'sessions': today_stats.total_sessions,
            'compliance_rate': compliance_rate
        },
        'week': {
            'work_minutes': week_work_minutes,
            'breaks_taken': week_breaks,
            'sessions': week_sessions.count()
        },
        'streaks': _get_user_streak_data(request.user),
        'achievements': _get_recent_achievements(request.user)
    })


@login_required
@require_http_methods(["GET"])
def live_feed_api(request):
    """
    API endpoint for live activity feed
    """
    # Get recent public activities
    activities = LiveActivityFeed.get_recent_public_activities(limit=15)

    activity_data = []
    for activity in activities:
        # Calculate time ago
        time_diff = timezone.now() - activity.timestamp
        if time_diff.days > 0:
            time_ago = f"{time_diff.days}d ago"
        elif time_diff.seconds > 3600:
            hours = time_diff.seconds // 3600
            time_ago = f"{hours}h ago"
        elif time_diff.seconds > 60:
            minutes = time_diff.seconds // 60
            time_ago = f"{minutes}m ago"
        else:
            time_ago = "Just now"

        activity_data.append({
            'user': activity.user.first_name or activity.user.username,
            'activity_type': activity.get_activity_type_display(),
            'timestamp': activity.timestamp.isoformat(),
            'time_ago': time_ago,
            'activity_data': activity.activity_data
        })

    return JsonResponse({
        'success': True,
        'activities': activity_data
    })


@login_required
@require_http_methods(["POST"])
def submit_rating_api(request):
    """
    API endpoint to submit user satisfaction rating
    """
    try:
        data = json.loads(request.body)
        rating = int(data.get('rating', 0))
        context = data.get('context', 'general')

        if rating < 1 or rating > 5:
            return JsonResponse({
                'success': False,
                'error': 'Rating must be between 1 and 5'
            })

        # Create satisfaction rating
        satisfaction_rating = UserSatisfactionRating.objects.create(
            user=request.user,
            rating=rating,
            context=context,
            session_id=request.session.session_key or '',
            days_since_signup=(timezone.now().date() - request.user.date_joined.date()).days
        )

        # Update real-time metrics
        metrics = RealTimeMetrics.get_latest_metrics()
        metrics.update_metrics()

        return JsonResponse({
            'success': True,
            'message': 'Rating submitted successfully',
            'rating_id': satisfaction_rating.id
        })

    except (json.JSONDecodeError, ValueError, KeyError) as e:
        return JsonResponse({
            'success': False,
            'error': 'Invalid request data'
        })


@login_required
@require_http_methods(["POST"])
def track_activity_api(request):
    """
    API endpoint to track user activity events
    """
    try:
        data = json.loads(request.body)
        event_type = data.get('event_type')
        event_data = data.get('event_data', {})

        # Import here to avoid circular imports
        from .models import UserBehaviorEvent

        # Create behavior event
        UserBehaviorEvent.objects.create(
            user=request.user,
            event_type=event_type,
            event_data=event_data,
            session_id=request.session.session_key or '',
            user_agent=request.META.get('HTTP_USER_AGENT', ''),
            ip_address=_get_client_ip(request)
        )

        return JsonResponse({'success': True})

    except (json.JSONDecodeError, ValueError, KeyError) as e:
        return JsonResponse({
            'success': False,
            'error': 'Invalid request data'
        })


@login_required
@require_http_methods(["GET"])
def user_stats_summary_api(request):
    """
    API endpoint for user statistics summary
    """
    days = int(request.GET.get('days', 30))
    end_date = date.today()
    start_date = end_date - timedelta(days=days)

    # Get daily stats for the period
    daily_stats = DailyStats.objects.filter(
        user=request.user,
        date__gte=start_date,
        date__lte=end_date
    ).order_by('date')

    # Calculate totals and averages
    total_work_minutes = sum(stat.total_work_minutes for stat in daily_stats)
    total_breaks = sum(stat.total_breaks_taken for stat in daily_stats)
    total_sessions = sum(stat.total_sessions for stat in daily_stats)

    active_days = daily_stats.filter(total_sessions__gt=0).count()
    avg_compliance = sum(stat.compliance_rate for stat in daily_stats) / max(1, len(daily_stats))

    # Prepare chart data
    chart_data = {
        'dates': [stat.date.strftime('%Y-%m-%d') for stat in daily_stats],
        'work_minutes': [stat.total_work_minutes for stat in daily_stats],
        'breaks_taken': [stat.total_breaks_taken for stat in daily_stats],
        'compliance_rates': [stat.compliance_rate for stat in daily_stats],
        'productivity_scores': [stat.productivity_score for stat in daily_stats]
    }

    # Get productivity insights
    insights = _generate_productivity_insights(request.user, daily_stats)

    return JsonResponse({
        'success': True,
        'summary': {
            'period_days': days,
            'active_days': active_days,
            'total_work_hours': round(total_work_minutes / 60, 1),
            'total_breaks': total_breaks,
            'total_sessions': total_sessions,
            'avg_compliance_rate': round(avg_compliance, 1),
            'consistency_score': round((active_days / days) * 100, 1)
        },
        'chart_data': chart_data,
        'insights': insights
    })


def _get_user_streak_data(user):
    """Helper function to get user's streak data"""
    try:
        from accounts.models import UserStreakData
        streak_data = UserStreakData.objects.get(user=user)
        return {
            'current_daily_streak': streak_data.current_daily_streak,
            'best_daily_streak': streak_data.best_daily_streak,
            'current_weekly_streak': streak_data.current_weekly_streak,
            'total_sessions': streak_data.total_sessions_completed
        }
    except UserStreakData.DoesNotExist:
        return {
            'current_daily_streak': 0,
            'best_daily_streak': 0,
            'current_weekly_streak': 0,
            'total_sessions': 0
        }


def _get_recent_achievements(user, limit=5):
    """Helper function to get user's recent achievements"""
    try:
        from accounts.models import Achievement
        achievements = Achievement.objects.filter(user=user).order_by('-earned_at')[:limit]
        return [
            {
                'type': achievement.get_achievement_type_display(),
                'earned_at': achievement.earned_at.isoformat(),
                'description': achievement.description
            }
            for achievement in achievements
        ]
    except:
        return []


def _generate_productivity_insights(user, daily_stats):
    """Generate productivity insights based on user's data"""
    insights = []

    if not daily_stats:
        insights.append({
            'type': 'welcome',
            'title': 'Welcome to EyeHealth 20-20-20!',
            'message': 'Start your first timer session to begin tracking your eye health progress.',
            'priority': 'high'
        })
        return insights

    # Calculate averages
    avg_work_minutes = sum(stat.total_work_minutes for stat in daily_stats) / len(daily_stats)
    avg_breaks = sum(stat.total_breaks_taken for stat in daily_stats) / len(daily_stats)
    avg_compliance = sum(stat.compliance_rate for stat in daily_stats) / len(daily_stats)

    # Generate insights based on patterns
    if avg_compliance < 60:
        insights.append({
            'type': 'improvement',
            'title': 'Improve Break Compliance',
            'message': f'Your break compliance is {avg_compliance:.1f}%. Try shorter breaks to build the habit.',
            'priority': 'high'
        })

    if avg_work_minutes > 480:  # More than 8 hours
        insights.append({
            'type': 'health',
            'title': 'Long Work Sessions Detected',
            'message': 'Consider taking longer breaks or reducing daily screen time for better eye health.',
            'priority': 'medium'
        })

    if avg_breaks < 3:
        insights.append({
            'type': 'reminder',
            'title': 'Take More Breaks',
            'message': 'Aim for at least one break every 20 minutes during work sessions.',
            'priority': 'medium'
        })

    # Positive reinforcement
    if avg_compliance > 80:
        insights.append({
            'type': 'achievement',
            'title': 'Excellent Break Compliance!',
            'message': f'Your {avg_compliance:.1f}% compliance rate is helping protect your eye health.',
            'priority': 'low'
        })

    return insights


def _get_client_ip(request):
    """Helper function to get client IP address"""
    x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
    if x_forwarded_for:
        ip = x_forwarded_for.split(',')[0]
    else:
        ip = request.META.get('REMOTE_ADDR')
    return ip