from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.http import JsonResponse
from django.views.decorators.csrf import ensure_csrf_cookie
from django.views.decorators.http import require_POST
from django.utils import timezone
from django.db.models import Sum, Count, Avg
from django.core.exceptions import PermissionDenied
from django_ratelimit.decorators import ratelimit
from datetime import date, timedelta
import json
import logging
import bleach

logger = logging.getLogger(__name__)

from .models import TimerSession, TimerInterval, BreakRecord, UserTimerSettings
from analytics.models import DailyStats
from accounts.models import Achievement, UserStreakData
from accounts.premium_features import PREMIUM_TIMER_PRESETS, EYE_EXERCISES, can_access_feature
from accounts.timezone_utils import user_today, user_now, user_localtime
from mysite.constants import (
    FREE_DAILY_SESSION_LIMIT, DEFAULT_WORK_INTERVAL_MINUTES,
    DEFAULT_BREAK_DURATION_SECONDS, STREAK_ACHIEVEMENTS,
    SESSION_MASTER_THRESHOLD, EARLY_BIRD_START_HOUR, EARLY_BIRD_END_HOUR,
    NIGHT_OWL_START_HOUR, NIGHT_OWL_END_HOUR, EARLY_BIRD_SESSIONS_REQUIRED,
    NIGHT_OWL_SESSIONS_REQUIRED, MAX_RECENT_SESSIONS, DEFAULT_STATISTICS_DAYS
)


@login_required
def dashboard_view(request):
    """
    Main dashboard view with timer interface and statistics
    """
    # Get or create user timer settings
    settings, created = UserTimerSettings.objects.get_or_create(user=request.user)
    
    # Get current active session
    active_session = TimerSession.objects.filter(
        user=request.user, 
        is_active=True
    ).first()
    
    # Get current active interval if session exists
    active_interval = None
    if active_session:
        active_interval = TimerInterval.objects.filter(
            session=active_session,
            status='active'
        ).order_by('-interval_number').first()
    
    # Get today's statistics (using user's local date)
    user_date_today = user_today(request.user)
    today_stats, created = DailyStats.objects.get_or_create(
        user=request.user,
        date=user_date_today
    )
    
    # Get recent sessions with optimized query
    recent_sessions = TimerSession.objects.select_related('user').prefetch_related('intervals', 'breaks').filter(
        user=request.user
    ).order_by('-start_time')[:MAX_RECENT_SESSIONS]
    
    # Check subscription limits (using user's local date)
    daily_limit = FREE_DAILY_SESSION_LIMIT if request.user.subscription_type == 'free' else 0  # 0 means unlimited
    sessions_today = TimerSession.objects.filter(
        user=request.user,
        start_time__date=user_date_today
    ).count()
    
    can_start_session = daily_limit == 0 or sessions_today < daily_limit
    
    # Get premium features for user
    premium_features = []
    if can_access_feature(request.user, 'smart_timer_presets'):
        premium_features.extend(PREMIUM_TIMER_PRESETS)
    
    # Get user streak data
    streak_data = None
    if request.user.is_premium_user:
        streak_data, created = UserStreakData.objects.get_or_create(user=request.user)
    
    # Get user achievements
    user_achievements = []
    if request.user.is_premium_user:
        user_achievements = Achievement.objects.filter(user=request.user).order_by('-earned_at')[:5]
    
    context = {
        'active_session': active_session,
        'active_interval': active_interval,
        'settings': settings,
        'today_stats': today_stats,
        'recent_sessions': recent_sessions,
        'can_start_session': can_start_session,
        'sessions_today': sessions_today,
        'daily_limit': daily_limit,
        'is_premium_user': request.user.is_premium_user,
        'premium_timer_presets': premium_features,
        'streak_data': streak_data,
        'user_achievements': user_achievements,
        'can_use_premium_themes': can_access_feature(request.user, 'custom_themes'),
        'can_use_guided_exercises': can_access_feature(request.user, 'guided_exercises'),
    }
    return render(request, 'timer/dashboard.html', context)


@login_required
@ratelimit(key='user', rate='10/m', method='POST')
@require_POST
def start_session_view(request):
    """
    Start a new timer session
    """
    if request.method == 'POST':
        try:
            from accounts.security_utils import validate_and_sanitize_json_data, log_security_event
            
            # Validate and sanitize input data
            data = validate_and_sanitize_json_data(request)
            
            # Check if user has an active session
            active_session = TimerSession.objects.filter(
                user=request.user, 
                is_active=True
            ).first()
            
            if active_session:
                log_security_event(request.user, 'duplicate_session_attempt')
                return JsonResponse({
                    'success': False, 
                    'message': 'You already have an active session.'
                })
        except Exception as e:
            logger.error(f"Error validating session start: {e}")
            return JsonResponse({
                'success': False, 
                'message': 'Invalid request data'
            }, status=400)
        
        # Check daily limits for free users (using user's local date)
        if request.user.subscription_type == 'free':
            user_date_today = user_today(request.user)
            sessions_today = TimerSession.objects.filter(
                user=request.user,
                start_time__date=user_date_today
            ).count()
            
            if sessions_today >= FREE_DAILY_SESSION_LIMIT:
                return JsonResponse({
                    'success': False,
                    'message': 'Daily session limit reached. Upgrade to Premium for unlimited sessions.'
                })
        
        # Create new session
        session = TimerSession.objects.create(user=request.user)
        
        # Create first interval
        interval = TimerInterval.objects.create(
            session=session,
            interval_number=1
        )
        
        # Track activity
        from analytics.models import UserSession, LiveActivityFeed
        session_key = request.session.session_key
        if session_key:
            user_session, created = UserSession.objects.get_or_create(
                session_key=session_key,
                defaults={'user': request.user}
            )
            user_session.timer_sessions_started += 1
            user_session.last_activity = timezone.now()
            user_session.save()
        
        # Create activity feed entry
        LiveActivityFeed.objects.create(
            user=request.user,
            activity_type='session_started',
            activity_data={
                'session_id': session.id,
                'interval_number': 1,
            }
        )
        
        return JsonResponse({
            'success': True,
            'session_id': session.id,
            'interval_id': interval.id,
            'message': 'Timer session started successfully!'
        })
    
    return JsonResponse({'success': False, 'message': 'Invalid request method'})


@login_required
@ratelimit(key='user', rate='10/m', method='POST')
@require_POST
def end_session_view(request):
    """
    End the current timer session
    """
    if request.method == 'POST':
        active_session = TimerSession.objects.filter(
            user=request.user, 
            is_active=True
        ).first()
        
        if not active_session:
            return JsonResponse({
                'success': False, 
                'message': 'No active session found.'
            })
        
        active_session.end_session()
        
        # Update daily statistics (using user's local date)
        user_date_today = user_today(request.user)
        today_stats, created = DailyStats.objects.get_or_create(
            user=request.user,
            date=user_date_today
        )
        today_stats.total_work_minutes += active_session.total_work_minutes
        today_stats.total_intervals_completed += active_session.total_intervals_completed
        today_stats.total_breaks_taken += active_session.total_breaks_taken
        today_stats.total_sessions += 1
        today_stats.save()
        
        # Update streak data and check achievements for premium users
        if request.user.is_premium_user:
            streak_data, created = UserStreakData.objects.get_or_create(user=request.user)
            streak_data.total_sessions_completed += 1
            streak_data.total_break_time_minutes += active_session.total_breaks_taken * (active_session.total_breaks_taken * 20)  # Assume 20s per break
            
            # Update daily streak (using user's local date)
            user_date_today = user_today(request.user)
            if streak_data.last_session_date == user_date_today:
                # Already had a session today, no streak change
                pass
            elif streak_data.last_session_date == user_date_today - timedelta(days=1):
                # Consecutive day
                streak_data.current_daily_streak += 1
                if streak_data.current_daily_streak > streak_data.best_daily_streak:
                    streak_data.best_daily_streak = streak_data.current_daily_streak
            elif streak_data.last_session_date is None or streak_data.last_session_date < user_date_today - timedelta(days=1):
                # Streak broken or first time
                streak_data.current_daily_streak = 1
                streak_data.streak_start_date = user_date_today
            
            streak_data.last_session_date = user_date_today
            streak_data.save()
            
            # Check for achievements
            _check_and_award_achievements(request.user, streak_data)
        
        return JsonResponse({
            'success': True,
            'session_duration': active_session.duration_minutes,
            'intervals_completed': active_session.total_intervals_completed,
            'breaks_taken': active_session.total_breaks_taken,
            'message': 'Session ended successfully!'
        })
    
    return JsonResponse({'success': False, 'message': 'Invalid request method'})


@login_required
@ratelimit(key='user', rate='20/m', method='POST')
@require_POST
def take_break_view(request):
    """
    Record a break taken by the user
    """
    if request.method == 'POST':
        data = json.loads(request.body)
        session_id = data.get('session_id')
        interval_id = data.get('interval_id')
        looked_at_distance = data.get('looked_at_distance', False)
        
        session = get_object_or_404(TimerSession, id=session_id, user=request.user)
        interval = get_object_or_404(TimerInterval, id=interval_id, session=session)
        
        # Create break record
        break_record = BreakRecord.objects.create(
            user=request.user,
            session=session,
            interval=interval,
            break_type='scheduled',
            looked_at_distance=looked_at_distance
        )
        
        return JsonResponse({
            'success': True,
            'break_id': break_record.id,
            'message': 'Break started successfully!'
        })
    
    return JsonResponse({'success': False, 'message': 'Invalid request method'})


@login_required
@ratelimit(key='user', rate='30/m', method='POST')
@require_POST
def sync_session_view(request):
    """
    Sync timer session state for webapp persistence
    """
    if request.method == 'POST':
        data = json.loads(request.body)
        session_id = data.get('session_id')
        
        try:
            session = TimerSession.objects.get(id=session_id, user=request.user)
            
            if not session.is_active:
                return JsonResponse({
                    'success': True,
                    'session_active': False,
                    'message': 'Session has ended'
                })
            
            # Get current active interval
            current_interval = TimerInterval.objects.filter(
                session=session,
                status='active'
            ).order_by('-interval_number').first()
            
            if current_interval:
                # Calculate elapsed time for current interval
                elapsed_time = timezone.now() - current_interval.start_time
                elapsed_seconds = int(elapsed_time.total_seconds())
                
                return JsonResponse({
                    'success': True,
                    'session_active': True,
                    'interval_id': current_interval.id,
                    'interval_number': current_interval.interval_number,
                    'interval_elapsed_seconds': elapsed_seconds,
                    'interval_duration_minutes': session.work_interval_minutes,
                    'total_intervals_completed': session.total_intervals_completed,
                    'total_breaks_taken': session.total_breaks_taken
                })
            else:
                return JsonResponse({
                    'success': True,
                    'session_active': True,
                    'message': 'No active interval found'
                })
                
        except TimerSession.DoesNotExist:
            return JsonResponse({
                'success': False,
                'session_active': False,
                'message': 'Session not found'
            })
    
    return JsonResponse({'success': False, 'message': 'Invalid request method'})


@login_required
@ratelimit(key='user', rate='20/m', method='POST')
@require_POST
def complete_break_view(request):
    """
    Complete a break
    """
    if request.method == 'POST':
        data = json.loads(request.body)
        break_id = data.get('break_id')
        looked_at_distance = data.get('looked_at_distance', False)
        
        break_record = get_object_or_404(BreakRecord, id=break_id, user=request.user)
        break_record.complete_break(looked_at_distance=looked_at_distance)
        
        # Update session statistics
        session = break_record.session
        session.total_breaks_taken += 1
        session.total_intervals_completed += 1  # Increment completed intervals
        session.save()
        
        # Mark interval as completed
        interval = break_record.interval
        interval.complete_interval()
        
        # Track real-time activity
        from analytics.models import UserSession, LiveActivityFeed
        session_key = request.session.session_key
        if session_key:
            user_session = UserSession.objects.filter(session_key=session_key).first()
            if user_session:
                user_session.breaks_taken_in_session += 1
                user_session.last_activity = timezone.now()
                user_session.save()
        
        # Create activity feed entry
        LiveActivityFeed.objects.create(
            user=request.user,
            activity_type='break_taken',
            activity_data={
                'session_id': session.id,
                'interval_number': interval.interval_number,
                'compliant': break_record.is_compliant,
                'duration_seconds': break_record.break_duration_seconds,
            }
        )
        
        # Create next interval if session is still active
        if session.is_active:
            next_interval = TimerInterval.objects.create(
                session=session,
                interval_number=interval.interval_number + 1
            )
            
            return JsonResponse({
                'success': True,
                'next_interval_id': next_interval.id,
                'is_compliant': break_record.is_compliant,
                'message': 'Break completed! Starting next interval.'
            })
        
        return JsonResponse({
            'success': True,
            'is_compliant': break_record.is_compliant,
            'message': 'Break completed!'
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
    
    # Get recent sessions for detailed view
    recent_sessions = TimerSession.objects.select_related('user').prefetch_related('intervals', 'breaks').filter(
        user=request.user
    ).order_by('-start_time')[:MAX_RECENT_SESSIONS]
    
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


def _check_and_award_achievements(user, streak_data):
    """
    Check and award achievements for premium users
    """
    achievements_to_award = []
    
    # Streak achievements
    for achievement_type, required_days in STREAK_ACHIEVEMENTS.items():
        if streak_data.current_daily_streak >= required_days:
            achievements_to_award.append(achievement_type)
    
    # Session count achievements
    if streak_data.total_sessions_completed >= SESSION_MASTER_THRESHOLD:
        achievements_to_award.append('session_master')
    
    # Time-based achievements (check current hour in user's timezone)
    user_current_time = user_now(user)
    current_hour = user_current_time.hour
    if EARLY_BIRD_START_HOUR <= current_hour <= EARLY_BIRD_END_HOUR:
        # Early bird - need to check if they have 10 morning sessions
        morning_sessions = TimerSession.objects.filter(
            user=user,
            start_time__hour__gte=EARLY_BIRD_START_HOUR,
            start_time__hour__lte=EARLY_BIRD_END_HOUR
        ).count()
        if morning_sessions >= EARLY_BIRD_SESSIONS_REQUIRED:
            achievements_to_award.append('early_bird')
    
    if NIGHT_OWL_START_HOUR <= current_hour <= NIGHT_OWL_END_HOUR:
        # Night owl - need to check if they have 10 evening sessions
        evening_sessions = TimerSession.objects.filter(
            user=user,
            start_time__hour__gte=NIGHT_OWL_START_HOUR,
            start_time__hour__lte=NIGHT_OWL_END_HOUR
        ).count()
        if evening_sessions >= NIGHT_OWL_SESSIONS_REQUIRED:
            achievements_to_award.append('night_owl')
    
    # Award achievements that don't exist yet
    for achievement_type in achievements_to_award:
        achievement, created = Achievement.objects.get_or_create(
            user=user,
            achievement_type=achievement_type,
            defaults={
                'description': f'Earned on {user_today(user)}'
            }
        )
        if created:
            # Could add notification logic here
            pass


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
def premium_themes_view(request):
    """
    Premium theme selection view
    """
    from accounts.premium_features import PREMIUM_THEMES
    
    if not can_access_feature(request.user, 'custom_themes'):
        messages.error(request, 'This feature requires a Premium subscription.')
        return redirect('accounts:pricing')
    
    if request.method == 'POST':
        theme_name = request.POST.get('theme')
        # Save theme preference to user profile
        profile = request.user.profile
        # You would add a theme field to UserProfile model
        messages.success(request, f'Theme "{theme_name}" applied successfully!')
        return redirect('timer:dashboard')
    
    context = {
        'themes': PREMIUM_THEMES,
        'is_premium_user': request.user.is_premium_user,
    }
    return render(request, 'timer/premium_themes.html', context)


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