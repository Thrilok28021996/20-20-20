from django.shortcuts import render
from django.http import JsonResponse
from django.contrib.auth.decorators import login_required
from django.views.decorators.csrf import ensure_csrf_cookie
from django.views.decorators.http import require_POST
from django.utils import timezone
from django.db.models import Sum, Count, Avg
from django.core.exceptions import PermissionDenied
from django_ratelimit.decorators import ratelimit
from datetime import date, timedelta
import json
import bleach

from .models import (
    DailyStats, WeeklyStats, MonthlyStats, UserBehaviorEvent,
    EngagementMetrics, UserSession, UserSatisfactionRating,
    RealTimeMetrics, LiveActivityFeed
)
from timer.models import TimerSession, BreakRecord
from .decorators import admin_required
from accounts.timezone_utils import user_today, user_now


@login_required
def real_time_metrics_api(request):
    """
    API endpoint for real-time metrics
    Global metrics only for admin users, personal metrics for all users
    """
    metrics = RealTimeMetrics.get_latest_metrics()
    
    # Get user-specific metrics
    user_today_stats = DailyStats.objects.filter(
        user=request.user,
        date=user_today(request.user)
    ).first()
    
    # Only show global metrics to admin users, personal metrics to everyone
    if request.user.is_staff:
        data = {
            'global_metrics': {
                'active_users': metrics.active_users_count,
                'users_working': metrics.users_working,
                'users_in_break': metrics.users_in_break,
                'total_breaks_today': metrics.total_breaks_today,
                'total_work_minutes_today': metrics.total_work_minutes_today,
                'total_sessions_today': metrics.total_sessions_today,
                'average_satisfaction': round(metrics.average_satisfaction_rating, 1),
                'nps_score': metrics.nps_score,
            },
            'user_metrics': {
                'work_minutes_today': user_today_stats.total_work_minutes if user_today_stats else 0,
                'breaks_today': user_today_stats.total_breaks_taken if user_today_stats else 0,
                'intervals_today': user_today_stats.total_intervals_completed if user_today_stats else 0,
                'compliance_rate': user_today_stats.compliance_rate if user_today_stats else 0.0,
            },
            'timestamp': metrics.timestamp.isoformat(),
            'last_updated': timezone.now().isoformat(),
        }
    else:
        # Regular users only see their personal metrics
        data = {
            'user_metrics': {
                'work_minutes_today': user_today_stats.total_work_minutes if user_today_stats else 0,
                'breaks_today': user_today_stats.total_breaks_taken if user_today_stats else 0,
                'intervals_today': user_today_stats.total_intervals_completed if user_today_stats else 0,
                'compliance_rate': user_today_stats.compliance_rate if user_today_stats else 0.0,
            },
            'last_updated': timezone.now().isoformat(),
        }
    
    return JsonResponse(data)


@login_required
@ratelimit(key='user', rate='50/m', method='POST')
@require_POST
def track_user_activity(request):
    """
    Track user activity events
    """
    if request.method == 'POST':
        try:
            data = json.loads(request.body)
            event_type = data.get('event_type')
            event_data = data.get('event_data', {})
            
            # Create behavior event
            UserBehaviorEvent.objects.create(
                user=request.user,
                event_type=event_type,
                event_data=event_data,
                session_id=request.session.session_key,
                user_agent=request.META.get('HTTP_USER_AGENT', ''),
                ip_address=request.META.get('REMOTE_ADDR')
            )
            
            # Update user session activity
            session_key = request.session.session_key
            if session_key:
                user_session, created = UserSession.objects.get_or_create(
                    session_key=session_key,
                    defaults={
                        'user': request.user,
                        'ip_address': request.META.get('REMOTE_ADDR'),
                        'user_agent': request.META.get('HTTP_USER_AGENT', ''),
                    }
                )
                user_session.last_activity = timezone.now()
                user_session.pages_viewed += 1
                
                # Update activity counters based on event type
                if event_type == 'session_start':
                    user_session.timer_sessions_started += 1
                elif event_type == 'break_taken':
                    user_session.breaks_taken_in_session += 1
                
                user_session.save()
            
            return JsonResponse({'success': True})
            
        except Exception as e:
            return JsonResponse({'success': False, 'error': str(e)})
    
    return JsonResponse({'success': False, 'error': 'Invalid request method'})


@login_required
@ratelimit(key='user', rate='5/m', method='POST')
@require_POST
def submit_satisfaction_rating(request):
    """
    Submit user satisfaction rating
    """
    if request.method == 'POST':
        try:
            data = json.loads(request.body)
            
            rating = int(data.get('rating'))
            context = data.get('context', 'general')
            feedback_text = data.get('feedback', '')
            recommendation_score = data.get('recommendation_score')
            
            # Validate rating
            if rating < 1 or rating > 5:
                return JsonResponse({'success': False, 'error': 'Rating must be between 1 and 5'})
            
            # Get user's current break count
            user_stats = DailyStats.objects.filter(
                user=request.user,
                date=user_today(request.user)
            ).first()
            
            break_count = user_stats.total_breaks_taken if user_stats else 0
            days_since_signup = (timezone.now().date() - request.user.date_joined.date()).days
            
            # Create satisfaction rating
            satisfaction = UserSatisfactionRating.objects.create(
                user=request.user,
                rating=rating,
                context=context,
                feedback_text=feedback_text,
                recommendation_score=recommendation_score if recommendation_score is not None else None,
                session_id=request.session.session_key,
                break_count_when_rated=break_count,
                days_since_signup=days_since_signup
            )
            
            # Create activity feed entry
            LiveActivityFeed.objects.create(
                user=request.user,
                activity_type='satisfaction_rating',
                activity_data={
                    'rating': rating,
                    'context': context,
                    'has_feedback': bool(feedback_text),
                },
                is_public=rating >= 4  # Only show good ratings publicly
            )
            
            return JsonResponse({
                'success': True,
                'message': 'Thank you for your feedback!',
                'rating_id': satisfaction.id
            })
            
        except Exception as e:
            return JsonResponse({'success': False, 'error': str(e)})
    
    return JsonResponse({'success': False, 'error': 'Invalid request method'})


@require_POST
@ratelimit(key='ip', rate='100/h', method='POST')
def track_conversion(request):
    """
    Track conversion events for monetization analytics (donations, enterprise requests)
    """
    try:
        data = json.loads(request.body)
        event_name = bleach.clean(data.get('event', ''))
        event_data = data.get('data', {})
        timestamp = data.get('timestamp')
        url = bleach.clean(data.get('url', ''))

        # Validate event name
        allowed_events = [
            'donation_click',
            'enterprise_demo_request',
            'support_modal_opened'
        ]

        if event_name not in allowed_events:
            return JsonResponse({'success': False, 'error': 'Invalid event type'}, status=400)

        # Log conversion event
        user = request.user if request.user.is_authenticated else None

        # Store in UserBehaviorEvent for tracking
        UserBehaviorEvent.objects.create(
            user=user,
            event_type=event_name,
            event_metadata={
                'data': event_data,
                'url': url,
                'timestamp': timestamp
            }
        )

        return JsonResponse({
            'success': True,
            'message': 'Conversion tracked successfully'
        })

    except Exception as e:
        return JsonResponse({
            'success': False,
            'error': str(e)
        }, status=400)


@admin_required
def live_activity_feed_api(request):
    """
    API endpoint for live activity feed - ADMIN ONLY
    """
    activities = LiveActivityFeed.get_recent_public_activities(limit=20)
    
    activity_data = []
    for activity in activities:
        activity_data.append({
            'user': activity.user.get_full_name() or activity.user.username,
            'activity_type': activity.get_activity_type_display(),
            'activity_data': activity.activity_data,
            'timestamp': activity.timestamp.isoformat(),
            'time_ago': time_ago_string(activity.timestamp),
        })
    
    return JsonResponse({'activities': activity_data})


@login_required
def user_dashboard_metrics_api(request):
    """
    API endpoint for user's personal dashboard metrics
    """
    today = user_today(request.user)
    week_start = today - timedelta(days=today.weekday())
    
    # Today's stats
    today_stats = DailyStats.objects.filter(user=request.user, date=today).first()
    
    # This week's stats
    week_stats = DailyStats.objects.filter(
        user=request.user,
        date__gte=week_start,
        date__lte=today
    ).aggregate(
        total_work_minutes=Sum('total_work_minutes'),
        total_breaks=Sum('total_breaks_taken'),
        total_intervals=Sum('total_intervals_completed'),
        total_sessions=Sum('total_sessions'),
        total_breaks_compliant=Sum('breaks_compliant')
    )

    # Calculate average compliance rate
    total_breaks = week_stats['total_breaks'] or 0
    total_compliant = week_stats['total_breaks_compliant'] or 0
    avg_compliance = (total_compliant / total_breaks * 100) if total_breaks > 0 else 0
    
    # Current streak
    profile = request.user.profile if hasattr(request.user, 'profile') else None
    current_streak = profile.current_streak_days if profile else 0
    
    # Active session info
    active_session = TimerSession.objects.filter(user=request.user, is_active=True).first()
    
    # Calculate today's compliance rate
    today_compliance = 0.0
    if today_stats and today_stats.total_breaks_taken > 0:
        today_compliance = (today_stats.breaks_compliant / today_stats.total_breaks_taken * 100)

    data = {
        'today': {
            'work_minutes': today_stats.total_work_minutes if today_stats else 0,
            'breaks_taken': today_stats.total_breaks_taken if today_stats else 0,
            'intervals_completed': today_stats.total_intervals_completed if today_stats else 0,
            'compliance_rate': round(today_compliance, 1),
            'sessions': today_stats.total_sessions if today_stats else 0,
        },
        'this_week': {
            'work_minutes': week_stats['total_work_minutes'] or 0,
            'breaks_taken': week_stats['total_breaks'] or 0,
            'intervals_completed': week_stats['total_intervals'] or 0,
            'avg_compliance': round(avg_compliance, 1),
            'sessions': week_stats['total_sessions'] or 0,
        },
        'streaks': {
            'current_days': current_streak,
            'longest_days': profile.longest_streak_days if profile else 0,
        },
        'active_session': {
            'is_active': bool(active_session),
            'session_id': active_session.id if active_session else None,
            'start_time': active_session.start_time.isoformat() if active_session else None,
            'intervals_completed': active_session.total_intervals_completed if active_session else 0,
            'breaks_taken': active_session.total_breaks_taken if active_session else 0,
        },
        'last_updated': timezone.now().isoformat(),
    }
    
    return JsonResponse(data)


def time_ago_string(timestamp):
    """
    Convert timestamp to human-readable "time ago" string
    """
    now = timezone.now()
    diff = now - timestamp
    
    if diff.days > 0:
        return f"{diff.days} day{'s' if diff.days != 1 else ''} ago"
    elif diff.seconds > 3600:
        hours = diff.seconds // 3600
        return f"{hours} hour{'s' if hours != 1 else ''} ago"
    elif diff.seconds > 60:
        minutes = diff.seconds // 60
        return f"{minutes} minute{'s' if minutes != 1 else ''} ago"
    else:
        return "Just now"


# Background task to update real-time metrics (called by Celery)
def update_real_time_metrics():
    """
    Update real-time metrics - called periodically by Celery
    """
    metrics = RealTimeMetrics.get_latest_metrics()
    metrics.update_metrics()
    return metrics


# Admin dashboard view
@admin_required
def admin_dashboard_view(request):
    """
    Admin dashboard with real-time metrics
    """
    
    metrics = RealTimeMetrics.get_latest_metrics()
    
    # Recent activity
    recent_activities = LiveActivityFeed.objects.all()[:10]
    
    # User satisfaction trend (last 7 days) - using system date for global metrics
    satisfaction_trend = []
    for i in range(7):
        day = date.today() - timedelta(days=i)  # System date for global satisfaction
        avg_rating = UserSatisfactionRating.objects.filter(
            rating_date__date=day
        ).aggregate(avg=Avg('rating'))['avg'] or 0
        satisfaction_trend.append({
            'date': day.isoformat(),
            'rating': round(avg_rating, 1)
        })
    
    context = {
        'metrics': metrics,
        'recent_activities': recent_activities,
        'satisfaction_trend': satisfaction_trend,
    }
    
    return render(request, 'analytics/admin_dashboard.html', context)