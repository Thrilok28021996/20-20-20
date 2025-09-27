from typing import Dict, List, Optional, Union, Any
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.http import JsonResponse, HttpRequest, HttpResponse
from django.views.decorators.csrf import ensure_csrf_cookie
from django.views.decorators.http import require_POST
from django.utils import timezone
from django.db.models import Sum, Count, Avg, QuerySet
from django.core.exceptions import PermissionDenied
from django_ratelimit.decorators import ratelimit
from django.contrib.auth import get_user_model
from datetime import date, timedelta
import json
import logging
import bleach

# Import new error handling framework
from mysite.exceptions import (
    TimerError, SessionCreationError, SessionNotFoundError, SessionAlreadyActiveError,
    SessionNotActiveError, IntervalNotFoundError, IntervalStateError,
    DailyLimitExceededError, BreakError, BreakCreationError, BreakNotFoundError,
    BreakAlreadyCompletedError, BreakValidationError, InvalidRequestDataError,
    InvalidJSONError, MissingRequiredFieldError, UserNotFoundError,
    get_error_context, sanitize_error_message
)
from mysite.decorators import (
    api_error_handler, require_authenticated_user, validate_json_request,
    rate_limit_api, atomic_transaction, log_api_call, api_view
)

User = get_user_model()
logger = logging.getLogger(__name__)

from .models import TimerSession, TimerInterval, BreakRecord, UserTimerSettings, UserFeedback, BreakPreferenceAnalytics
from analytics.models import DailyStats
from accounts.models import Achievement, UserStreakData
from accounts.premium_features import PREMIUM_TIMER_PRESETS, EYE_EXERCISES, can_access_feature
from accounts.timezone_utils import user_today, user_now, user_localtime
from mysite.constants import (
    FREE_DAILY_INTERVAL_LIMIT, FREE_DAILY_SESSION_LIMIT, DEFAULT_WORK_INTERVAL_MINUTES,
    DEFAULT_BREAK_DURATION_SECONDS, STREAK_ACHIEVEMENTS,
    SESSION_MASTER_THRESHOLD, EARLY_BIRD_START_HOUR, EARLY_BIRD_END_HOUR,
    NIGHT_OWL_START_HOUR, NIGHT_OWL_END_HOUR, EARLY_BIRD_SESSIONS_REQUIRED,
    NIGHT_OWL_SESSIONS_REQUIRED, MAX_RECENT_SESSIONS, DEFAULT_STATISTICS_DAYS
)


@login_required
def dashboard_view(request: HttpRequest) -> HttpResponse:
    """
    Main dashboard view with timer interface and statistics
    Refactored to use service layer for better maintainability
    """
    from .services import StatisticsService
    from accounts.services import UserService

    # Get comprehensive dashboard context using service layer
    context = UserService.get_user_dashboard_context(request.user)

    # Get recent sessions using optimized service method
    context['recent_sessions'] = StatisticsService.get_optimized_recent_sessions(
        request.user, MAX_RECENT_SESSIONS
    )

    # Add premium feature checks
    context.update({
        'can_use_guided_exercises': can_access_feature(request.user, 'guided_exercises'),
    })

    return render(request, 'timer/dashboard.html', context)


@api_view(
    authentication_required=True,
    rate_limit='10/m',
    use_transaction=True,
    log_calls=True
)
def start_session_view(request: HttpRequest) -> JsonResponse:
    """
    Start a new timer session using service layer with comprehensive error handling
    """
    from .services import TimerSessionService

    # Validate input data if provided
    if request.body:
        try:
            data = json.loads(request.body)
        except json.JSONDecodeError:
            raise InvalidJSONError(
                message="Invalid JSON in request body",
                context={'method': request.method, 'path': request.path}
            )

    # Create new session using service layer
    # All exceptions are handled by the service layer and api_error_handler decorator
    session = TimerSessionService.create_session(request.user)
    first_interval = TimerSessionService.get_active_interval(session)

    return {
        'session_id': session.id,
        'interval_id': first_interval.id if first_interval else None,
        'message': 'Timer session started successfully!',
        'work_interval_minutes': session.work_interval_minutes,
        'break_duration_seconds': session.break_duration_seconds
    }


@api_view(
    authentication_required=True,
    rate_limit='10/m',
    use_transaction=True,
    log_calls=True
)
def end_session_view(request: HttpRequest) -> JsonResponse:
    """
    End the current timer session using service layer with comprehensive error handling
    """
    from .services import TimerSessionService

    # Get active session
    active_session = TimerSessionService.get_active_session(request.user)
    if not active_session:
        raise SessionNotFoundError(
            message="No active session found for user",
            context={'user_id': request.user.id}
        )

    # End session and get summary using service layer
    # All exceptions are handled by the service layer and api_error_handler decorator
    session_summary = TimerSessionService.end_session(active_session)

    return {
        'message': 'Session ended successfully!',
        **session_summary
    }


@api_view(
    authentication_required=True,
    required_fields=['session_id', 'interval_id'],
    rate_limit='20/m',
    use_transaction=True,
    log_calls=True
)
def take_break_view(request: HttpRequest) -> JsonResponse:
    """
    Record a break taken by the user using service layer with comprehensive error handling
    """
    from .services import BreakService

    data = request.validated_data
    session_id = data['session_id']
    interval_id = data['interval_id']
    looked_at_distance = data.get('looked_at_distance', False)

    # Get session and interval with proper error handling
    try:
        session = TimerSession.objects.get(id=session_id, user=request.user)
    except TimerSession.DoesNotExist:
        raise SessionNotFoundError(
            message=f"Session {session_id} not found for user",
            context={'session_id': session_id, 'user_id': request.user.id}
        )

    try:
        interval = TimerInterval.objects.get(id=interval_id, session=session)
    except TimerInterval.DoesNotExist:
        raise IntervalNotFoundError(
            message=f"Interval {interval_id} not found for session {session_id}",
            context={
                'interval_id': interval_id,
                'session_id': session_id,
                'user_id': request.user.id
            }
        )

    # Create break record using service layer
    # All exceptions are handled by the service layer and api_error_handler decorator
    break_record = BreakService.start_break(
        request.user, session, interval, looked_at_distance
    )

    # Get user settings for display
    try:
        user_settings = UserTimerSettings.objects.filter(user=request.user).first()
        duration_text = (
            user_settings.get_break_duration_display_text() if user_settings
            else '20 seconds'
        )
    except Exception as e:
        logger.warning(f"Failed to get user settings for duration text: {e}")
        duration_text = '20 seconds'

    return {
        'break_id': break_record.id,
        'expected_duration_seconds': break_record.break_duration_seconds,
        'duration_text': duration_text,
        'message': 'Break started successfully!'
    }


@login_required
@ratelimit(key='user', rate='30/m', method='POST')
@require_POST
def sync_session_view(request: HttpRequest) -> JsonResponse:
    """
    Sync timer session state for webapp persistence using service layer
    """
    from .services import TimerSessionService

    try:
        data = json.loads(request.body)
        session_id = data.get('session_id')

        session = get_object_or_404(TimerSession, id=session_id, user=request.user)

        # Get session state using service layer
        session_state = TimerSessionService.sync_session_state(session)

        return JsonResponse({
            'success': True,
            **session_state
        })

    except json.JSONDecodeError:
        return JsonResponse({
            'success': False,
            'message': 'Invalid JSON data'
        }, status=400)
    except Exception as e:
        logger.error(f"Error syncing session: {e}")
        return JsonResponse({
            'success': False,
            'message': 'Failed to sync session'
        }, status=500)


@login_required
@ratelimit(key='user', rate='20/m', method='POST')
@require_POST
def complete_break_view(request):
    """
    Complete a break - Optimized version using service layer
    """
    if request.method == 'POST':
        data = json.loads(request.body)
        break_id = data.get('break_id')
        looked_at_distance = data.get('looked_at_distance', False)

        # Get break record with select_related to avoid additional queries
        break_record = get_object_or_404(
            BreakRecord.objects.select_related('session', 'interval', 'user'),
            id=break_id,
            user=request.user
        )

        # Use service layer for optimized break completion
        from .services import BreakService
        result = BreakService.complete_break(break_record, looked_at_distance)

        # Return the service result directly
        return JsonResponse({
            'success': True,
            **result
        })

    return JsonResponse({'success': False, 'message': 'Invalid request method'})


@login_required
def timer_settings_view(request):
    """
    Timer settings configuration
    """
    settings, created = UserTimerSettings.objects.get_or_create(user=request.user)
    
    if request.method == 'POST':
        # Update timer settings
        settings.work_interval_minutes = int(request.POST.get('work_interval_minutes', 20))
        settings.break_duration_seconds = int(request.POST.get('break_duration_seconds', 20))
        settings.sound_notification = request.POST.get('sound_notification') == 'on'
        settings.desktop_notification = request.POST.get('desktop_notification') == 'on'
        settings.show_progress_bar = request.POST.get('show_progress_bar') == 'on'
        settings.dark_mode = request.POST.get('dark_mode') == 'on'

        # Smart break duration settings
        settings.smart_break_enabled = request.POST.get('smart_break_enabled') == 'on'
        preferred_duration = request.POST.get('preferred_break_duration')
        if preferred_duration and preferred_duration.isdigit():
            duration_value = int(preferred_duration)
            # Validate against available choices
            valid_durations = [choice[0] for choice in UserTimerSettings.BREAK_DURATION_CHOICES]
            if duration_value in valid_durations:
                settings.preferred_break_duration = duration_value
        
        # Sound settings
        settings.notification_sound_type = request.POST.get('notification_sound_type', 'gentle')
        try:
            sound_volume = float(request.POST.get('sound_volume', 0.5))
            settings.sound_volume = max(0.0, min(1.0, sound_volume))  # Clamp between 0 and 1
        except (ValueError, TypeError):
            settings.sound_volume = 0.5  # Default fallback
        
        # Premium features
        if request.user.is_premium_user:
            settings.auto_start_break = request.POST.get('auto_start_break') == 'on'
            settings.auto_start_work = request.POST.get('auto_start_work') == 'on'
            settings.custom_break_messages = request.POST.get('custom_break_messages', '')
        
        settings.save()
        messages.success(request, 'Timer settings updated successfully!')
        return redirect('timer:settings')
    
    return render(request, 'timer/settings.html', {'settings': settings})


@login_required
def statistics_view(request):
    """
    Detailed statistics and analytics view
    """
    # Get date range from query parameters (using user's local date)
    days = int(request.GET.get('days', DEFAULT_STATISTICS_DAYS))
    end_date = user_today(request.user)
    start_date = end_date - timedelta(days=days)
    
    # Get daily statistics for the period
    daily_stats = DailyStats.objects.filter(
        user=request.user,
        date__gte=start_date,
        date__lte=end_date
    ).order_by('date')
    
    # Calculate aggregated statistics
    total_stats = daily_stats.aggregate(
        total_work_minutes=Sum('total_work_minutes'),
        total_intervals=Sum('total_intervals_completed'),
        total_breaks=Sum('total_breaks_taken'),
        total_sessions=Sum('total_sessions'),
        total_breaks_compliant=Sum('breaks_compliant'),
        total_breaks_taken_agg=Sum('total_breaks_taken')
    )

    # Calculate compliance rate manually
    if total_stats['total_breaks_taken_agg'] and total_stats['total_breaks_taken_agg'] > 0:
        avg_compliance = (total_stats['total_breaks_compliant'] / total_stats['total_breaks_taken_agg']) * 100
    else:
        avg_compliance = 0.0

    total_stats['avg_compliance'] = avg_compliance
    
    # Get recent sessions for detailed view - Use optimized utility function
    from .utils import get_optimized_recent_sessions
    recent_sessions = get_optimized_recent_sessions(request.user, MAX_RECENT_SESSIONS)
    
    # Prepare chart data
    chart_data = {
        'dates': [stat.date.strftime('%Y-%m-%d') for stat in daily_stats],
        'work_minutes': [stat.total_work_minutes for stat in daily_stats],
        'breaks_taken': [stat.total_breaks_taken for stat in daily_stats],
        'compliance_rates': [stat.compliance_rate for stat in daily_stats]
    }
    
    context = {
        'daily_stats': daily_stats,
        'total_stats': total_stats,
        'recent_sessions': recent_sessions,
        'chart_data': chart_data,
        'days': days,
        'date_range': f"{start_date} to {end_date}"
    }
    
    return render(request, 'timer/statistics.html', context)


def real_time_dashboard_view(request):
    """
    Real-time dashboard with live metrics - ADMIN ONLY
    """
    from analytics.decorators import admin_required
    
    @admin_required
    def _admin_dashboard_view(request):
        return render(request, 'timer/real_time_dashboard.html')
    
    return _admin_dashboard_view(request)


def _check_and_award_achievements(user: User, streak_data: UserStreakData) -> List[Achievement]:
    """
    Check and award achievements for premium users

    Args:
        user: User instance
        streak_data: User's streak data

    Returns:
        List of newly awarded Achievement instances
    """
    # Use the service layer for achievement processing
    from accounts.services import AchievementService
    return AchievementService.check_and_award_achievements(user, streak_data)


@login_required
def premium_exercises_view(request):
    """
    Premium guided eye exercises view
    """
    if not can_access_feature(request.user, 'guided_exercises'):
        messages.error(request, 'This feature requires a Premium subscription.')
        return redirect('accounts:pricing')
    
    context = {
        'exercises': EYE_EXERCISES,
        'is_premium_user': request.user.is_premium_user,
    }
    return render(request, 'timer/premium_exercises.html', context)




@login_required
def get_break_settings_view(request):
    """
    API endpoint to get user's current break settings
    """
    settings, created = UserTimerSettings.objects.get_or_create(user=request.user)

    return JsonResponse({
        'success': True,
        'smart_break_enabled': settings.smart_break_enabled,
        'preferred_break_duration': settings.preferred_break_duration,
        'effective_break_duration': settings.get_effective_break_duration(),
        'duration_display_text': settings.get_break_duration_display_text(),
        'break_duration_choices': UserTimerSettings.BREAK_DURATION_CHOICES
    })


@login_required
@require_POST
def update_smart_break_settings_view(request):
    """
    API endpoint to update smart break settings
    """
    if request.method == 'POST':
        try:
            data = json.loads(request.body)
            settings, created = UserTimerSettings.objects.get_or_create(user=request.user)

            # Update smart break settings
            if 'smart_break_enabled' in data:
                settings.smart_break_enabled = bool(data['smart_break_enabled'])

            if 'preferred_break_duration' in data:
                duration = int(data['preferred_break_duration'])
                valid_durations = [choice[0] for choice in UserTimerSettings.BREAK_DURATION_CHOICES]
                if duration in valid_durations:
                    settings.preferred_break_duration = duration
                else:
                    return JsonResponse({'success': False, 'message': 'Invalid break duration'})

            settings.save()

            return JsonResponse({
                'success': True,
                'effective_break_duration': settings.get_effective_break_duration(),
                'duration_display_text': settings.get_break_duration_display_text(),
                'message': 'Smart break settings updated successfully!'
            })

        except (json.JSONDecodeError, ValueError, KeyError) as e:
            return JsonResponse({'success': False, 'message': 'Invalid request data'})

    return JsonResponse({'success': False, 'message': 'Invalid request method'})


@login_required
def update_dark_mode_view(request):
    """
    AJAX endpoint to update user's dark mode preference
    """
    if request.method == 'POST':
        dark_mode = request.POST.get('dark_mode') == 'on'

        # Get or create timer settings for the user
        settings, created = TimerSettings.objects.get_or_create(user=request.user)
        settings.dark_mode = dark_mode
        settings.save()

        return JsonResponse({'success': True, 'dark_mode': dark_mode})

    return JsonResponse({'success': False, 'error': 'Invalid request method'})


@login_required
@require_POST
def submit_feedback_view(request):
    """
    Submit user feedback
    """
    if request.method == 'POST':
        try:
            data = json.loads(request.body)

            # Validate required fields
            feedback_type = data.get('feedback_type')
            title = data.get('title', '').strip()
            message = data.get('message', '').strip()

            if not feedback_type or not title or not message:
                return JsonResponse({
                    'success': False,
                    'message': 'Feedback type, title, and message are required'
                })

            # Validate feedback type
            valid_types = [choice[0] for choice in UserFeedback.FEEDBACK_TYPES]
            if feedback_type not in valid_types:
                return JsonResponse({
                    'success': False,
                    'message': 'Invalid feedback type'
                })

            # Sanitize input
            title = bleach.clean(title)
            message = bleach.clean(message)

            # Create feedback entry
            feedback = UserFeedback.objects.create(
                user=request.user,
                feedback_type=feedback_type,
                title=title[:200],  # Enforce max length
                message=message,
                rating=data.get('rating'),
                timer_session_id=data.get('session_id'),
                break_record_id=data.get('break_id'),
                context_data=data.get('context', {}),
                user_agent=request.META.get('HTTP_USER_AGENT', ''),
                page_url=data.get('page_url', ''),
                screen_resolution=data.get('screen_resolution', '')
            )

            return JsonResponse({
                'success': True,
                'feedback_id': feedback.id,
                'message': 'Thank you for your feedback! We appreciate your input.'
            })

        except json.JSONDecodeError:
            return JsonResponse({
                'success': False,
                'message': 'Invalid JSON data'
            })
        except Exception as e:
            logger.error(f"Error submitting feedback: {e}")
            return JsonResponse({
                'success': False,
                'message': 'An error occurred while submitting your feedback'
            })

    return JsonResponse({'success': False, 'message': 'Invalid request method'})


@login_required
def feedback_dashboard_view(request):
    """
    User's feedback dashboard
    """
    user_feedback = UserFeedback.objects.filter(user=request.user).order_by('-created_at')[:20]

    context = {
        'feedback_entries': user_feedback,
        'feedback_types': UserFeedback.FEEDBACK_TYPES,
    }
    return render(request, 'timer/feedback_dashboard.html', context)


@login_required
def break_insights_view(request):
    """
    Show user insights about their break patterns and suggestions
    """
    # Get or create latest analytics
    from datetime import date, timedelta
    end_date = date.today()
    start_date = end_date - timedelta(days=30)

    analytics, created = BreakPreferenceAnalytics.objects.get_or_create(
        user=request.user,
        analysis_start_date=start_date,
        analysis_end_date=end_date,
        defaults={
            'preferred_break_duration': 20,
            'total_sessions_analyzed': 0
        }
    )

    if created or not analytics.total_sessions_analyzed:
        # Calculate analytics if new or empty
        _calculate_break_analytics(request.user, analytics, start_date, end_date)

    # Get smart break suggestion
    suggested_duration = analytics.calculate_smart_break_suggestion()
    current_settings = UserTimerSettings.objects.filter(user=request.user).first()

    # Check if suggestion differs from current setting
    settings_update_needed = False
    if current_settings and suggested_duration != current_settings.preferred_break_duration:
        settings_update_needed = True

    context = {
        'analytics': analytics,
        'suggested_duration': suggested_duration,
        'current_settings': current_settings,
        'settings_update_needed': settings_update_needed,
        'break_duration_choices': UserTimerSettings.BREAK_DURATION_CHOICES,
    }
    return render(request, 'timer/break_insights.html', context)


@login_required
@require_POST
def apply_break_suggestion_view(request):
    """
    Apply suggested break duration to user settings
    """
    if request.method == 'POST':
        try:
            data = json.loads(request.body)
            suggested_duration = int(data.get('suggested_duration', 20))

            # Validate duration
            valid_durations = [choice[0] for choice in UserTimerSettings.BREAK_DURATION_CHOICES]
            if suggested_duration not in valid_durations:
                return JsonResponse({
                    'success': False,
                    'message': 'Invalid break duration'
                })

            # Update user settings
            settings, created = UserTimerSettings.objects.get_or_create(user=request.user)
            settings.preferred_break_duration = suggested_duration
            settings.smart_break_enabled = True
            settings.save()

            return JsonResponse({
                'success': True,
                'message': f'Break duration updated to {suggested_duration} seconds!',
                'new_duration': suggested_duration,
                'duration_text': settings.get_break_duration_display_text()
            })

        except (json.JSONDecodeError, ValueError) as e:
            return JsonResponse({
                'success': False,
                'message': 'Invalid request data'
            })

    return JsonResponse({'success': False, 'message': 'Invalid request method'})


def _calculate_break_analytics(user: User, analytics: BreakPreferenceAnalytics, start_date: date, end_date: date) -> None:
    """
    Calculate break preference analytics for a user

    Args:
        user: User instance
        analytics: BreakPreferenceAnalytics instance to update
        start_date: Analysis start date
        end_date: Analysis end date
    """
    # Use the service layer for break analytics calculation
    from timer.services import BreakAnalyticsService
    BreakAnalyticsService.calculate_break_analytics(user, analytics, start_date, end_date)