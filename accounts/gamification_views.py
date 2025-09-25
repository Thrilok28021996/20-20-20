"""
Views for gamification features
"""
from django.shortcuts import render, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.http import JsonResponse
from django.views.decorators.http import require_POST
from django.db.models import Count, Avg, Q
from django.utils import timezone
from datetime import datetime, timedelta
import json

from .models import (
    UserLevel, Badge, UserBadge, Challenge, ChallengeParticipation,
    Achievement, UserStreakData
)
from timer.models import TimerSession, BreakRecord
from analytics.models import DailyStats


@login_required
def gamification_dashboard_view(request):
    """
    Main gamification dashboard showing user's progress, achievements, and challenges
    """
    # Get or create user level data
    level_data, created = UserLevel.objects.get_or_create(user=request.user)

    # Get user badges (latest 12)
    recent_badges = UserBadge.objects.filter(user=request.user).order_by('-earned_at')[:12]

    # Get available badges user hasn't earned yet
    earned_badge_ids = UserBadge.objects.filter(user=request.user).values_list('badge_id', flat=True)
    available_badges = Badge.objects.filter(is_active=True).exclude(id__in=earned_badge_ids)[:6]

    # Get active challenges
    current_time = timezone.now()
    active_challenges = Challenge.objects.filter(
        is_active=True,
        start_date__lte=current_time,
        end_date__gte=current_time
    )

    # Get user's challenge participations
    user_participations = ChallengeParticipation.objects.filter(
        user=request.user,
        challenge__in=active_challenges
    ).select_related('challenge')

    # Get streak data
    streak_data, created = UserStreakData.objects.get_or_create(user=request.user)

    # Calculate progress toward next level
    level_progress_percentage = 0
    if level_data.experience_to_next_level > 0:
        level_progress_percentage = (level_data.total_experience_points / level_data.experience_to_next_level) * 100

    # Get recent achievements (last 10)
    recent_achievements = Achievement.objects.filter(user=request.user).order_by('-earned_at')[:10]

    context = {
        'level_data': level_data,
        'level_progress_percentage': level_progress_percentage,
        'recent_badges': recent_badges,
        'available_badges': available_badges,
        'active_challenges': active_challenges,
        'user_participations': user_participations,
        'streak_data': streak_data,
        'recent_achievements': recent_achievements,
        'total_badges_earned': recent_badges.count(),
    }

    return render(request, 'accounts/gamification_dashboard.html', context)


@login_required
def leaderboard_view(request):
    """
    Show leaderboards for various metrics
    """
    # Top users by level
    top_by_level = UserLevel.objects.select_related('user').order_by('-current_level', '-total_experience_points')[:10]

    # Top streak holders
    top_streaks = UserStreakData.objects.select_related('user').order_by('-current_daily_streak', '-best_daily_streak')[:10]

    # Most sessions completed (last 30 days)
    thirty_days_ago = timezone.now() - timedelta(days=30)
    top_sessions = UserLevel.objects.select_related('user').annotate(
        recent_sessions=Count(
            'user__timer_sessions',
            filter=Q(user__timer_sessions__start_time__gte=thirty_days_ago)
        )
    ).order_by('-recent_sessions')[:10]

    # Most badges earned
    top_badges = UserLevel.objects.select_related('user').annotate(
        badge_count=Count('user__earned_badges')
    ).order_by('-badge_count')[:10]

    # Find current user's ranks
    user_level_rank = UserLevel.objects.filter(
        Q(current_level__gt=request.user.level_data.current_level) |
        Q(current_level=request.user.level_data.current_level,
          total_experience_points__gt=request.user.level_data.total_experience_points)
    ).count() + 1

    user_streak_rank = UserStreakData.objects.filter(
        Q(current_daily_streak__gt=request.user.streak_data.current_daily_streak) |
        Q(current_daily_streak=request.user.streak_data.current_daily_streak,
          best_daily_streak__gt=request.user.streak_data.best_daily_streak)
    ).count() + 1

    context = {
        'top_by_level': top_by_level,
        'top_streaks': top_streaks,
        'top_sessions': top_sessions,
        'top_badges': top_badges,
        'user_level_rank': user_level_rank,
        'user_streak_rank': user_streak_rank,
    }

    return render(request, 'accounts/leaderboard.html', context)


@login_required
def badges_view(request):
    """
    Show all badges - earned and available
    """
    # Get all badges organized by category
    earned_badges = UserBadge.objects.filter(user=request.user).select_related('badge').order_by('-earned_at')
    earned_badge_ids = earned_badges.values_list('badge_id', flat=True)

    available_badges = Badge.objects.filter(is_active=True).exclude(id__in=earned_badge_ids).order_by('category', 'name')

    # Organize by category
    badges_by_category = {}
    for badge in available_badges:
        if badge.category not in badges_by_category:
            badges_by_category[badge.category] = []
        badges_by_category[badge.category].append(badge)

    earned_badges_by_category = {}
    for user_badge in earned_badges:
        category = user_badge.badge.category
        if category not in earned_badges_by_category:
            earned_badges_by_category[category] = []
        earned_badges_by_category[category].append(user_badge)

    context = {
        'earned_badges': earned_badges,
        'earned_badges_by_category': earned_badges_by_category,
        'badges_by_category': badges_by_category,
        'total_earned': earned_badges.count(),
        'total_available': Badge.objects.filter(is_active=True).count(),
    }

    return render(request, 'accounts/badges.html', context)


@login_required
def challenges_view(request):
    """
    Show available challenges and user's participation
    """
    current_time = timezone.now()

    # Active challenges
    active_challenges = Challenge.objects.filter(
        is_active=True,
        start_date__lte=current_time,
        end_date__gte=current_time
    ).annotate(participant_count=Count('participants'))

    # Upcoming challenges
    upcoming_challenges = Challenge.objects.filter(
        is_active=True,
        start_date__gt=current_time
    ).order_by('start_date')[:5]

    # Completed challenges
    completed_challenges = Challenge.objects.filter(
        end_date__lt=current_time
    ).order_by('-end_date')[:10]

    # User's participations
    user_participations = ChallengeParticipation.objects.filter(
        user=request.user
    ).select_related('challenge').order_by('-joined_at')

    context = {
        'active_challenges': active_challenges,
        'upcoming_challenges': upcoming_challenges,
        'completed_challenges': completed_challenges,
        'user_participations': user_participations,
    }

    return render(request, 'accounts/challenges.html', context)


@login_required
@require_POST
def join_challenge_view(request):
    """
    Join a challenge
    """
    try:
        data = json.loads(request.body)
        challenge_id = data.get('challenge_id')

        challenge = get_object_or_404(Challenge, id=challenge_id, is_active=True)

        # Check if challenge is currently joinable
        current_time = timezone.now()
        if not (challenge.start_date <= current_time <= challenge.end_date):
            return JsonResponse({
                'success': False,
                'message': 'This challenge is not currently available to join.'
            })

        # Check if user already joined
        if ChallengeParticipation.objects.filter(user=request.user, challenge=challenge).exists():
            return JsonResponse({
                'success': False,
                'message': 'You are already participating in this challenge.'
            })

        # Check premium requirements
        if challenge.is_premium_only and request.user.subscription_type != 'premium':
            return JsonResponse({
                'success': False,
                'message': 'This challenge requires a Premium subscription.'
            })

        # Check participant limit
        if challenge.max_participants:
            current_participants = challenge.participants.count()
            if current_participants >= challenge.max_participants:
                return JsonResponse({
                    'success': False,
                    'message': 'This challenge is full.'
                })

        # Create participation
        participation = ChallengeParticipation.objects.create(
            user=request.user,
            challenge=challenge
        )

        # Calculate initial progress based on challenge type
        initial_progress = _calculate_challenge_progress(request.user, challenge)
        participation.update_progress(initial_progress)

        return JsonResponse({
            'success': True,
            'message': f'Successfully joined "{challenge.name}"!',
            'participation_id': participation.id,
            'current_progress': participation.current_progress,
            'target_value': challenge.target_value
        })

    except json.JSONDecodeError:
        return JsonResponse({'success': False, 'message': 'Invalid request data'})
    except Exception as e:
        return JsonResponse({'success': False, 'message': 'An error occurred while joining the challenge'})


@login_required
def challenge_progress_api(request, challenge_id):
    """
    API endpoint to get user's progress in a specific challenge
    """
    try:
        challenge = get_object_or_404(Challenge, id=challenge_id)
        participation = ChallengeParticipation.objects.filter(
            user=request.user,
            challenge=challenge
        ).first()

        if not participation:
            return JsonResponse({
                'success': False,
                'message': 'You are not participating in this challenge'
            })

        # Update progress
        current_progress = _calculate_challenge_progress(request.user, challenge)
        participation.update_progress(current_progress)

        return JsonResponse({
            'success': True,
            'current_progress': participation.current_progress,
            'target_value': challenge.target_value,
            'progress_percentage': participation.progress_percentage,
            'is_completed': participation.is_completed,
            'completed_at': participation.completed_at.isoformat() if participation.completed_at else None
        })

    except Exception as e:
        return JsonResponse({'success': False, 'message': 'An error occurred'})


def _calculate_challenge_progress(user, challenge):
    """
    Calculate user's current progress for a challenge
    """
    if challenge.challenge_type == 'daily_streak':
        streak_data, created = UserStreakData.objects.get_or_create(user=user)
        return streak_data.current_daily_streak

    elif challenge.challenge_type == 'session_count':
        # Count sessions during challenge period
        return TimerSession.objects.filter(
            user=user,
            start_time__gte=challenge.start_date,
            start_time__lte=challenge.end_date,
            is_active=False
        ).count()

    elif challenge.challenge_type == 'compliance_rate':
        # Calculate compliance rate during challenge period
        breaks = BreakRecord.objects.filter(
            user=user,
            break_start_time__gte=challenge.start_date,
            break_start_time__lte=challenge.end_date,
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
        # Custom logic for community challenges
        return 0

    return 0


@login_required
def user_progress_api(request):
    """
    API endpoint to get user's overall gamification progress
    """
    level_data, created = UserLevel.objects.get_or_create(user=request.user)
    streak_data, created = UserStreakData.objects.get_or_create(user=request.user)

    # Calculate recent progress (last 7 days)
    week_ago = timezone.now() - timedelta(days=7)
    recent_sessions = TimerSession.objects.filter(
        user=request.user,
        start_time__gte=week_ago,
        is_active=False
    ).count()

    recent_breaks = BreakRecord.objects.filter(
        user=request.user,
        break_start_time__gte=week_ago,
        break_completed=True
    ).count()

    return JsonResponse({
        'success': True,
        'level': level_data.current_level,
        'level_title': level_data.get_level_title(),
        'experience_points': level_data.total_experience_points,
        'experience_to_next': level_data.experience_to_next_level,
        'current_streak': streak_data.current_daily_streak,
        'best_streak': streak_data.best_daily_streak,
        'recent_sessions': recent_sessions,
        'recent_breaks': recent_breaks,
        'badges_earned': UserBadge.objects.filter(user=request.user).count()
    })