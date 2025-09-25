"""
Timer service layer for business logic separation
Handles timer session management, break processing, and statistics with comprehensive type hints
"""
from typing import Dict, List, Optional, Tuple, Union, Any, Type
from datetime import date, datetime, timedelta
from django.utils import timezone
from django.db.models import Sum, Count, Avg, Q, QuerySet
from django.contrib.auth import get_user_model
from django.db import transaction
import logging

from .models import (
    TimerSession, TimerInterval, BreakRecord, UserTimerSettings,
    UserFeedback, BreakPreferenceAnalytics
)
from analytics.models import DailyStats, UserSession, LiveActivityFeed
from accounts.models import UserStreakData, Achievement
from accounts.timezone_utils import user_today, user_now
from mysite.constants import (
    FREE_DAILY_INTERVAL_LIMIT, DEFAULT_WORK_INTERVAL_MINUTES,
    DEFAULT_BREAK_DURATION_SECONDS, MAX_RECENT_SESSIONS
)
from mysite.exceptions import (
    TimerError, SessionCreationError, SessionNotFoundError, SessionAlreadyActiveError,
    SessionNotActiveError, IntervalNotFoundError, IntervalStateError,
    DailyLimitExceededError, BreakError, BreakCreationError, BreakNotFoundError,
    BreakAlreadyCompletedError, BreakValidationError, DataCalculationError,
    UserNotFoundError, InvalidRequestDataError, get_error_context
)

User = get_user_model()
logger = logging.getLogger(__name__)


class TimerSessionService:
    """
    Service class for timer session management
    Handles session lifecycle, validation, and state management
    """

    @staticmethod
    def get_active_session(user: User) -> Optional[TimerSession]:
        """
        Get user's currently active timer session

        Args:
            user: User instance

        Returns:
            Active TimerSession instance or None if no active session exists

        Raises:
            SessionNotFoundError: If database query fails
        """
        try:
            if not user or not user.is_authenticated:
                raise UserNotFoundError(
                    message="Invalid user for session query",
                    context={'user_id': getattr(user, 'id', None)}
                )

            return TimerSession.objects.filter(
                user=user,
                is_active=True
            ).first()
        except UserNotFoundError:
            raise
        except Exception as e:
            raise SessionNotFoundError(
                message=f"Failed to get active session for user {user.email}",
                context={'user_id': user.id, 'error_details': str(e)},
                cause=e
            )

    @staticmethod
    def get_active_interval(session: Optional[TimerSession]) -> Optional[TimerInterval]:
        """
        Get current active interval for a session

        Args:
            session: TimerSession instance or None

        Returns:
            Active TimerInterval instance or None

        Raises:
            IntervalNotFoundError: If database query fails
        """
        if not session:
            return None

        try:
            return TimerInterval.objects.filter(
                session=session,
                status='active'
            ).order_by('-interval_number').first()
        except Exception as e:
            raise IntervalNotFoundError(
                message=f"Failed to get active interval for session {session.id}",
                context={'session_id': session.id, 'error_details': str(e)},
                cause=e
            )

    @staticmethod
    def check_daily_limits(user: User) -> Tuple[bool, int, Union[int, float]]:
        """
        Check if user can start new session based on daily limits

        Args:
            user: User instance

        Returns:
            Tuple of (can_start: bool, intervals_today: int, daily_limit: int|float)

        Raises:
            DailyLimitExceededError: If user has exceeded daily limits
            DataCalculationError: If calculation fails
        """
        try:
            if not user or not user.is_authenticated:
                raise UserNotFoundError(
                    message="Invalid user for daily limits check",
                    context={'user_id': getattr(user, 'id', None)}
                )

            # Premium users have unlimited access
            if hasattr(user, 'is_premium_user') and user.is_premium_user:
                return True, 0, float('inf')

            user_date_today = user_today(user)
            intervals_today = TimerInterval.objects.filter(
                session__user=user,
                start_time__date=user_date_today
            ).count()

            can_start = intervals_today < FREE_DAILY_INTERVAL_LIMIT

            if not can_start:
                raise DailyLimitExceededError(
                    message=f"Daily limit of {FREE_DAILY_INTERVAL_LIMIT} intervals exceeded",
                    context={
                        'user_id': user.id,
                        'intervals_today': intervals_today,
                        'daily_limit': FREE_DAILY_INTERVAL_LIMIT,
                        'subscription_type': getattr(user, 'subscription_type', 'free')
                    }
                )

            return can_start, intervals_today, FREE_DAILY_INTERVAL_LIMIT

        except (UserNotFoundError, DailyLimitExceededError):
            raise
        except Exception as e:
            raise DataCalculationError(
                message=f"Failed to check daily limits for user {user.email}",
                context={'user_id': user.id, 'error_details': str(e)},
                cause=e
            )

    @staticmethod
    @transaction.atomic
    def create_session(user: User) -> TimerSession:
        """
        Create a new timer session with first interval

        Args:
            user: User instance

        Returns:
            New TimerSession instance

        Raises:
            SessionAlreadyActiveError: If user already has an active session
            SessionCreationError: If session creation fails
            DailyLimitExceededError: If user has exceeded daily limits
        """
        try:
            if not user or not user.is_authenticated:
                raise UserNotFoundError(
                    message="Invalid user for session creation",
                    context={'user_id': getattr(user, 'id', None)}
                )

            # Check daily limits first
            can_start, intervals_today, daily_limit = TimerSessionService.check_daily_limits(user)
            if not can_start:
                # This will raise DailyLimitExceededError
                pass

            # Check for existing active session
            existing_session = TimerSessionService.get_active_session(user)
            if existing_session:
                raise SessionAlreadyActiveError(
                    message=f"User {user.email} already has an active session",
                    context={
                        'user_id': user.id,
                        'existing_session_id': existing_session.id,
                        'session_start_time': existing_session.start_time.isoformat()
                    }
                )

            # Get user settings for session configuration
            try:
                user_settings = UserTimerSettings.objects.filter(user=user).first()
                work_minutes = (
                    user_settings.work_interval_minutes if user_settings
                    else DEFAULT_WORK_INTERVAL_MINUTES
                )
                break_seconds = (
                    user_settings.get_effective_break_duration() if user_settings
                    else DEFAULT_BREAK_DURATION_SECONDS
                )
            except Exception as e:
                # Use defaults if settings can't be retrieved
                work_minutes = DEFAULT_WORK_INTERVAL_MINUTES
                break_seconds = DEFAULT_BREAK_DURATION_SECONDS
                logger.warning(
                    f"Failed to get user settings for {user.email}, using defaults: {e}"
                )

            # Create session
            session = TimerSession.objects.create(
                user=user,
                work_interval_minutes=work_minutes,
                break_duration_seconds=break_seconds,
                is_active=True
            )

            # Create first interval
            TimerInterval.objects.create(
                session=session,
                interval_number=1,
                status='active'
            )

            # Track activity for analytics
            try:
                TimerSessionService._track_session_activity(user, session, 'session_started')
            except Exception as e:
                logger.warning(f"Failed to track session activity: {e}")

            logger.info(f"Created timer session {session.id} for user {user.email}")
            return session

        except (UserNotFoundError, SessionAlreadyActiveError, DailyLimitExceededError):
            raise
        except Exception as e:
            raise SessionCreationError(
                message=f"Failed to create session for user {user.email}",
                context={
                    'user_id': user.id,
                    'error_details': str(e)
                },
                cause=e
            )

    @staticmethod
    @transaction.atomic
    def end_session(session: TimerSession) -> Dict[str, Any]:
        """
        End a timer session and update all related statistics

        Args:
            session: TimerSession instance to end

        Returns:
            Dictionary containing session completion summary

        Raises:
            ValueError: If session is already inactive
            Exception: If session ending fails
        """
        try:
            if not session.is_active:
                raise ValueError("Session is already inactive")

            user = session.user

            # Calculate session statistics before ending
            session.end_session()

            # Update session totals based on actual data
            intervals = TimerInterval.objects.filter(session=session)
            completed_intervals = intervals.filter(status='completed')
            session.total_intervals_completed = completed_intervals.count()
            session.total_work_minutes = session.duration_minutes

            # Count breaks taken during session
            breaks_count = BreakRecord.objects.filter(session=session).count()
            session.total_breaks_taken = breaks_count
            session.save()

            # Update daily statistics
            daily_stats = DailyStatsService.update_daily_stats(user, session)

            # Update streak data
            streak_data = StreakService.update_streak_data(user, session)

            # Award gamification rewards for premium users
            gamification_rewards = {}
            if hasattr(user, 'is_premium_user') and user.is_premium_user:
                try:
                    from accounts.gamification_utils import award_session_completion_rewards
                    gamification_rewards = award_session_completion_rewards(user, session)
                except ImportError:
                    logger.warning("Gamification utilities not available")

            # Track session completion activity
            TimerSessionService._track_session_activity(user, session, 'session_ended')

            logger.info(f"Ended session {session.id} for user {user.email}")

            return {
                'session_duration': session.duration_minutes,
                'intervals_completed': session.total_intervals_completed,
                'breaks_taken': session.total_breaks_taken,
                'work_minutes': session.total_work_minutes,
                'gamification': gamification_rewards,
                'streak': {
                    'current_daily': streak_data.current_daily_streak,
                    'best_daily': streak_data.best_daily_streak,
                    'total_sessions': streak_data.total_sessions_completed
                },
                'daily_stats': {
                    'compliance_rate': daily_stats.compliance_rate,
                    'productivity_score': daily_stats.productivity_score
                }
            }

        except ValueError:
            raise
        except Exception as e:
            logger.error(f"Failed to end session {session.id}: {e}")
            raise Exception(f"Session ending failed: {str(e)}")

    @staticmethod
    def sync_session_state(session: TimerSession) -> Dict[str, Any]:
        """
        Get current session state for frontend synchronization

        Args:
            session: TimerSession instance

        Returns:
            Dictionary containing current session state
        """
        try:
            if not session.is_active:
                return {
                    'session_active': False,
                    'message': 'Session has ended',
                    'session_id': session.id
                }

            current_interval = TimerSessionService.get_active_interval(session)

            if current_interval:
                elapsed_time = timezone.now() - current_interval.start_time
                elapsed_seconds = int(elapsed_time.total_seconds())
                remaining_seconds = max(0, (session.work_interval_minutes * 60) - elapsed_seconds)

                return {
                    'session_active': True,
                    'session_id': session.id,
                    'interval_id': current_interval.id,
                    'interval_number': current_interval.interval_number,
                    'interval_elapsed_seconds': elapsed_seconds,
                    'interval_remaining_seconds': remaining_seconds,
                    'interval_duration_minutes': session.work_interval_minutes,
                    'total_intervals_completed': session.total_intervals_completed,
                    'total_breaks_taken': session.total_breaks_taken,
                    'break_duration_seconds': session.break_duration_seconds
                }
            else:
                return {
                    'session_active': True,
                    'session_id': session.id,
                    'message': 'No active interval found',
                    'total_intervals_completed': session.total_intervals_completed,
                    'total_breaks_taken': session.total_breaks_taken
                }

        except Exception as e:
            logger.error(f"Failed to sync session state for session {session.id}: {e}")
            return {
                'session_active': False,
                'error': 'Failed to sync session state'
            }

    @staticmethod
    def _track_session_activity(user: User, session: TimerSession, activity_type: str) -> None:
        """
        Track session activity for analytics and user engagement metrics

        Args:
            user: User instance
            session: TimerSession instance
            activity_type: Type of activity being tracked
        """
        try:
            # Update user session tracking if session key available
            session_key = getattr(user, '_session_key', None)

            if session_key:
                user_session, created = UserSession.objects.get_or_create(
                    session_key=session_key,
                    defaults={
                        'user': user,
                        'ip_address': None,
                        'user_agent': ''
                    }
                )

                if activity_type == 'session_started':
                    user_session.timer_sessions_started += 1
                elif activity_type == 'session_ended':
                    # Update pages viewed metric if available
                    user_session.pages_viewed += 1

                user_session.last_activity = timezone.now()
                user_session.save()

            # Create activity feed entry for live dashboard
            activity_data = {
                'session_id': session.id,
                'session_duration': session.duration_minutes if activity_type == 'session_ended' else 0
            }

            if activity_type == 'session_started':
                activity_data['interval_number'] = 1
            elif activity_type == 'session_ended':
                activity_data['intervals_completed'] = session.total_intervals_completed
                activity_data['breaks_taken'] = session.total_breaks_taken

            LiveActivityFeed.objects.create(
                user=user,
                activity_type=activity_type,
                activity_data=activity_data,
                is_public=True  # Show in public activity feed
            )

            logger.debug(f"Tracked {activity_type} activity for user {user.email}")

        except Exception as e:
            logger.warning(f"Failed to track session activity for user {user.email}: {e}")
            # Don't raise exception as activity tracking is non-critical


class BreakService:
    """
    Service class for break management
    Handles break creation, completion, and compliance tracking
    """

    @staticmethod
    @transaction.atomic
    def start_break(
        user: User,
        session: TimerSession,
        interval: TimerInterval,
        looked_at_distance: bool = False
    ) -> BreakRecord:
        """
        Start a new break record for user

        Args:
            user: User taking the break
            session: Current timer session
            interval: Current interval
            looked_at_distance: Whether user looked at distance

        Returns:
            New BreakRecord instance

        Raises:
            SessionNotActiveError: If session is not active
            IntervalStateError: If interval is invalid
            BreakCreationError: If break creation fails
        """
        try:
            # Validate user
            if not user or not user.is_authenticated:
                raise UserNotFoundError(
                    message="Invalid user for break creation",
                    context={'user_id': getattr(user, 'id', None)}
                )

            # Validate session and interval
            if not session or not session.is_active:
                raise SessionNotActiveError(
                    message="Cannot start break on inactive session",
                    context={
                        'session_id': getattr(session, 'id', None),
                        'session_active': getattr(session, 'is_active', False)
                    }
                )

            if not interval or interval.session != session:
                raise IntervalStateError(
                    message="Interval does not belong to the specified session",
                    context={
                        'interval_id': getattr(interval, 'id', None),
                        'session_id': session.id,
                        'interval_session_id': getattr(interval, 'session_id', None)
                    }
                )

            if interval.status != 'active':
                raise IntervalStateError(
                    message="Cannot start break on non-active interval",
                    context={
                        'interval_id': interval.id,
                        'interval_status': interval.status,
                        'required_status': 'active'
                    }
                )

            # Get user's effective break duration
            try:
                user_settings = UserTimerSettings.objects.filter(user=user).first()
                effective_duration = (
                    user_settings.get_effective_break_duration() if user_settings
                    else DEFAULT_BREAK_DURATION_SECONDS
                )
            except Exception as e:
                logger.warning(f"Failed to get user settings, using default duration: {e}")
                effective_duration = DEFAULT_BREAK_DURATION_SECONDS

            # Create break record
            break_record = BreakRecord.objects.create(
                user=user,
                session=session,
                interval=interval,
                break_type='scheduled',
                looked_at_distance=looked_at_distance,
                break_duration_seconds=effective_duration
            )

            # Track break activity
            try:
                BreakService._track_break_activity(user, break_record, 'break_started')
            except Exception as e:
                logger.warning(f"Failed to track break activity: {e}")

            logger.info(f"Started break {break_record.id} for user {user.email}")
            return break_record

        except (UserNotFoundError, SessionNotActiveError, IntervalStateError):
            raise
        except Exception as e:
            raise BreakCreationError(
                message=f"Failed to start break for user {user.email}",
                context={
                    'user_id': user.id,
                    'session_id': getattr(session, 'id', None),
                    'interval_id': getattr(interval, 'id', None),
                    'error_details': str(e)
                },
                cause=e
            )

    @staticmethod
    @transaction.atomic
    def complete_break(break_record: BreakRecord, looked_at_distance: bool = False) -> Dict[str, Any]:
        """
        Complete a break and handle interval progression

        Args:
            break_record: BreakRecord instance to complete
            looked_at_distance: Whether user looked at distance during break

        Returns:
            Dictionary with break completion data

        Raises:
            ValueError: If break is already completed
            Exception: If break completion fails
        """
        try:
            if break_record.break_completed:
                raise ValueError("Break is already completed")

            # Complete the break record
            break_record.complete_break(looked_at_distance=looked_at_distance)

            session = break_record.session
            interval = break_record.interval

            # Update session statistics
            session.total_breaks_taken = BreakRecord.objects.filter(session=session).count()
            session.save()

            # Mark current interval as completed
            interval.complete_interval()

            # Award experience for compliant breaks (premium users only)
            experience_gained = 0
            if break_record.is_compliant and hasattr(break_record.user, 'is_premium_user') and break_record.user.is_premium_user:
                try:
                    from accounts.gamification_utils import update_user_level_progress
                    experience_gained = 5  # Base XP for compliant break
                    update_user_level_progress(break_record.user, experience_gained)
                except ImportError:
                    logger.warning("Gamification utilities not available")

            # Track break completion activity
            BreakService._track_break_activity(break_record.user, break_record, 'break_completed')

            result = {
                'break_id': break_record.id,
                'duration_seconds': break_record.break_duration_seconds,
                'is_compliant': break_record.is_compliant,
                'looked_at_distance': break_record.looked_at_distance,
                'experience_gained': experience_gained,
                'message': 'Break completed successfully!'
            }

            # Create next interval if session is still active
            if session.is_active:
                next_interval = TimerInterval.objects.create(
                    session=session,
                    interval_number=interval.interval_number + 1,
                    status='active'
                )
                result['next_interval_id'] = next_interval.id
                result['next_interval_number'] = next_interval.interval_number
                result['message'] = 'Break completed! Starting next interval.'

            logger.info(f"Completed break {break_record.id} - compliant: {break_record.is_compliant}")
            return result

        except ValueError:
            raise
        except Exception as e:
            logger.error(f"Failed to complete break {break_record.id}: {e}")
            raise Exception(f"Break completion failed: {str(e)}")

    @staticmethod
    def _track_break_activity(user: User, break_record: BreakRecord, activity_type: str) -> None:
        """
        Track break activity for analytics and engagement metrics

        Args:
            user: User instance
            break_record: BreakRecord instance
            activity_type: Type of activity ('break_started' or 'break_completed')
        """
        try:
            session = break_record.session
            interval = break_record.interval

            # Update user session tracking
            session_key = getattr(user, '_session_key', None)

            if session_key:
                user_session = UserSession.objects.filter(session_key=session_key).first()
                if user_session:
                    if activity_type == 'break_completed':
                        user_session.breaks_taken_in_session += 1
                    user_session.last_activity = timezone.now()
                    user_session.save()

            # Create activity feed entry
            activity_data = {
                'session_id': session.id,
                'interval_number': interval.interval_number,
                'break_id': break_record.id,
                'duration_seconds': break_record.break_duration_seconds,
            }

            if activity_type == 'break_completed':
                activity_data.update({
                    'compliant': break_record.is_compliant,
                    'looked_at_distance': break_record.looked_at_distance
                })

            LiveActivityFeed.objects.create(
                user=user,
                activity_type='break_taken' if activity_type == 'break_completed' else 'break_started',
                activity_data=activity_data,
                is_public=True
            )

            logger.debug(f"Tracked break {activity_type} for user {user.email}")

        except Exception as e:
            logger.warning(f"Failed to track break activity for user {user.email}: {e}")
            # Don't raise exception as activity tracking is non-critical


class UserSettingsService:
    """Service class for user timer settings management"""

    @staticmethod
    def get_or_create_settings(user: User) -> UserTimerSettings:
        """Get or create user timer settings"""
        settings, created = UserTimerSettings.objects.get_or_create(user=user)
        return settings

    @staticmethod
    def update_settings(user: User, settings_data: Dict[str, Any]) -> UserTimerSettings:
        """Update user timer settings with validation"""
        settings = UserSettingsService.get_or_create_settings(user)

        # Basic timer settings
        if 'work_interval_minutes' in settings_data:
            settings.work_interval_minutes = int(settings_data['work_interval_minutes'])

        if 'break_duration_seconds' in settings_data:
            settings.break_duration_seconds = int(settings_data['break_duration_seconds'])

        # Notification settings
        boolean_fields = [
            'sound_notification', 'desktop_notification', 'show_progress_bar',
            'dark_mode', 'smart_break_enabled'
        ]

        for field in boolean_fields:
            if field in settings_data:
                setattr(settings, field, bool(settings_data[field]))

        # Smart break duration with validation
        if 'preferred_break_duration' in settings_data:
            duration_value = int(settings_data['preferred_break_duration'])
            valid_durations = [choice[0] for choice in UserTimerSettings.BREAK_DURATION_CHOICES]
            if duration_value in valid_durations:
                settings.preferred_break_duration = duration_value

        # Sound settings
        if 'notification_sound_type' in settings_data:
            settings.notification_sound_type = settings_data['notification_sound_type']

        if 'sound_volume' in settings_data:
            try:
                sound_volume = float(settings_data['sound_volume'])
                settings.sound_volume = max(0.0, min(1.0, sound_volume))
            except (ValueError, TypeError):
                settings.sound_volume = 0.5

        # Premium features
        if user.is_premium_user:
            premium_fields = ['auto_start_break', 'auto_start_work', 'custom_break_messages']
            for field in premium_fields:
                if field in settings_data:
                    if field == 'custom_break_messages':
                        setattr(settings, field, str(settings_data[field]))
                    else:
                        setattr(settings, field, bool(settings_data[field]))

        settings.save()
        return settings


class DailyStatsService:
    """Service class for daily statistics management"""

    @staticmethod
    def update_daily_stats(user: User, session: TimerSession) -> DailyStats:
        """Update daily statistics after session completion"""
        user_date_today = user_today(user)
        today_stats, created = DailyStats.objects.get_or_create(
            user=user,
            date=user_date_today
        )

        today_stats.total_work_minutes += session.total_work_minutes
        today_stats.total_intervals_completed += session.total_intervals_completed
        today_stats.total_breaks_taken += session.total_breaks_taken
        today_stats.total_sessions += 1

        # Update break compliance statistics
        DailyStatsService._update_break_compliance(today_stats, session)

        today_stats.save()
        return today_stats

    @staticmethod
    def _update_break_compliance(daily_stats: DailyStats, session: TimerSession) -> None:
        """Update break compliance statistics for daily stats - Optimized"""
        # Use single aggregation query for compliance calculation
        break_stats = BreakRecord.objects.filter(
            session=session,
            break_completed=True
        ).aggregate(
            compliant_breaks=Count(
                'id',
                filter=Q(break_duration_seconds__gte=20, looked_at_distance=True)
            )
        )

        daily_stats.breaks_compliant += break_stats['compliant_breaks'] or 0


class StreakService:
    """Service class for streak management"""

    @staticmethod
    def update_streak_data(user: User, session: TimerSession) -> UserStreakData:
        """Update user streak data after session completion"""
        streak_data, created = UserStreakData.objects.get_or_create(user=user)
        streak_data.total_sessions_completed += 1

        # Calculate break time from break records
        total_break_seconds = BreakRecord.objects.filter(
            session=session,
            break_completed=True
        ).aggregate(
            total_seconds=Sum('break_duration_seconds')
        )['total_seconds'] or 0

        streak_data.total_break_time_minutes += total_break_seconds // 60

        # Update average session length
        StreakService._update_average_session_length(streak_data, session)

        # Update daily streak
        StreakService._update_daily_streak(streak_data, user)

        streak_data.save()
        return streak_data

    @staticmethod
    def _update_average_session_length(streak_data: UserStreakData, session: TimerSession) -> None:
        """Update average session length calculation"""
        if streak_data.total_sessions_completed > 0:
            streak_data.average_session_length = (
                (streak_data.average_session_length * (streak_data.total_sessions_completed - 1) +
                 session.duration_minutes) / streak_data.total_sessions_completed
            )
        else:
            streak_data.average_session_length = session.duration_minutes

    @staticmethod
    def _update_daily_streak(streak_data: UserStreakData, user: User) -> None:
        """Update daily streak logic"""
        user_date_today = user_today(user)

        if streak_data.last_session_date == user_date_today:
            # Already had a session today, no streak change
            pass
        elif streak_data.last_session_date == user_date_today - timedelta(days=1):
            # Consecutive day
            streak_data.current_daily_streak += 1
            if streak_data.current_daily_streak > streak_data.best_daily_streak:
                streak_data.best_daily_streak = streak_data.current_daily_streak
        elif (streak_data.last_session_date is None or
              streak_data.last_session_date < user_date_today - timedelta(days=1)):
            # Streak broken or first time
            streak_data.current_daily_streak = 1
            streak_data.streak_start_date = user_date_today

        streak_data.last_session_date = user_date_today


class FeedbackService:
    """Service class for user feedback management"""

    @staticmethod
    def submit_feedback(user: User, feedback_data: Dict[str, Any],
                       request_meta: Dict[str, str]) -> UserFeedback:
        """Submit user feedback with validation and sanitization"""
        import bleach

        # Validate required fields
        feedback_type = feedback_data.get('feedback_type')
        title = feedback_data.get('title', '').strip()
        message = feedback_data.get('message', '').strip()

        if not all([feedback_type, title, message]):
            raise ValueError('Feedback type, title, and message are required')

        # Validate feedback type
        valid_types = [choice[0] for choice in UserFeedback.FEEDBACK_TYPES]
        if feedback_type not in valid_types:
            raise ValueError('Invalid feedback type')

        # Sanitize input
        title = bleach.clean(title)
        message = bleach.clean(message)

        # Create feedback entry
        feedback = UserFeedback.objects.create(
            user=user,
            feedback_type=feedback_type,
            title=title[:200],  # Enforce max length
            message=message,
            rating=feedback_data.get('rating'),
            timer_session_id=feedback_data.get('session_id'),
            break_record_id=feedback_data.get('break_id'),
            context_data=feedback_data.get('context', {}),
            user_agent=request_meta.get('HTTP_USER_AGENT', ''),
            page_url=feedback_data.get('page_url', ''),
            screen_resolution=feedback_data.get('screen_resolution', '')
        )

        return feedback


class BreakAnalyticsService:
    """Service class for break preference analytics"""

    @staticmethod
    def calculate_break_analytics(user: User, analytics: BreakPreferenceAnalytics,
                                start_date: date, end_date: date) -> None:
        """Calculate break preference analytics for a user"""
        breaks = BreakRecord.objects.filter(
            user=user,
            break_start_time__date__gte=start_date,
            break_start_time__date__lte=end_date,
            break_completed=True
        )

        if not breaks.exists():
            return

        # Calculate metrics using database aggregation for better performance
        break_stats = breaks.aggregate(
            total_breaks=Count('id'),
            compliant_breaks=Count(
                'id',
                filter=Q(break_duration_seconds__gte=20, looked_at_distance=True)
            ),
            looks_at_distance_count=Count('id', filter=Q(looked_at_distance=True)),
            avg_duration=Avg('break_duration_seconds')
        )

        total_breaks = break_stats['total_breaks']
        compliant_breaks = break_stats['compliant_breaks']
        looks_at_distance_count = break_stats['looks_at_distance_count']
        avg_duration = break_stats['avg_duration'] or 0

        # Get session count for the period
        analytics.total_sessions_analyzed = TimerSession.objects.filter(
            user=user,
            start_time__date__gte=start_date,
            start_time__date__lte=end_date
        ).count()

        analytics.actual_average_break_duration = round(avg_duration, 1)
        analytics.break_completion_rate = (
            round(total_breaks / analytics.total_sessions_analyzed, 2)
            if analytics.total_sessions_analyzed > 0 else 0
        )
        analytics.compliant_breaks_percentage = round((compliant_breaks / total_breaks) * 100, 1)
        analytics.looks_at_distance_rate = round((looks_at_distance_count / total_breaks) * 100, 1)

        # Analyze preferred break times (limit to top 10 for performance)
        break_times = list(breaks.values_list(
            'break_start_time__hour', 'break_start_time__minute'
        )[:10])

        analytics.preferred_break_times = [
            {'hour': hour, 'minute': minute} for hour, minute in break_times
        ]

        analytics.save()

    @staticmethod
    def get_break_insights(user: User, days: int = 30) -> Tuple[BreakPreferenceAnalytics, int, bool]:
        """Get break insights and suggestions for user"""
        end_date = date.today()
        start_date = end_date - timedelta(days=days)

        analytics, created = BreakPreferenceAnalytics.objects.get_or_create(
            user=user,
            analysis_start_date=start_date,
            analysis_end_date=end_date,
            defaults={
                'preferred_break_duration': 20,
                'total_sessions_analyzed': 0
            }
        )

        if created or not analytics.total_sessions_analyzed:
            BreakAnalyticsService.calculate_break_analytics(user, analytics, start_date, end_date)

        suggested_duration = analytics.calculate_smart_break_suggestion()
        current_settings = UserTimerSettings.objects.filter(user=user).first()

        settings_update_needed = (
            current_settings and
            suggested_duration != current_settings.preferred_break_duration
        )

        return analytics, suggested_duration, settings_update_needed


class StatisticsService:
    """Service class for statistics and analytics"""

    @staticmethod
    def get_period_statistics(user: User, days: int) -> Dict[str, Any]:
        """Get comprehensive statistics for a time period"""
        end_date = user_today(user)
        start_date = end_date - timedelta(days=days)

        # Get daily statistics for the period
        daily_stats = DailyStats.objects.filter(
            user=user,
            date__gte=start_date,
            date__lte=end_date
        ).order_by('date')

        # Calculate aggregated statistics using database aggregation
        total_stats = daily_stats.aggregate(
            total_work_minutes=Sum('total_work_minutes'),
            total_intervals=Sum('total_intervals_completed'),
            total_breaks=Sum('total_breaks_taken'),
            total_sessions=Sum('total_sessions'),
            total_breaks_compliant=Sum('breaks_compliant'),
            total_breaks_taken_agg=Sum('total_breaks_taken')
        )

        # Calculate compliance rate
        total_breaks = total_stats['total_breaks_taken_agg'] or 0
        compliant_breaks = total_stats['total_breaks_compliant'] or 0

        avg_compliance = (
            (compliant_breaks / total_breaks) * 100
            if total_breaks > 0 else 0.0
        )

        total_stats['avg_compliance'] = avg_compliance

        # Prepare chart data
        chart_data = {
            'dates': [stat.date.strftime('%Y-%m-%d') for stat in daily_stats],
            'work_minutes': [stat.total_work_minutes for stat in daily_stats],
            'breaks_taken': [stat.total_breaks_taken for stat in daily_stats],
            'compliance_rates': [stat.compliance_rate for stat in daily_stats]
        }

        return {
            'daily_stats': daily_stats,
            'total_stats': total_stats,
            'chart_data': chart_data,
            'days': days,
            'date_range': f"{start_date} to {end_date}"
        }

    @staticmethod
    def get_optimized_recent_sessions(user: User, limit: int) -> QuerySet[TimerSession]:
        """Get recent sessions with optimized queries to avoid N+1"""
        return TimerSession.objects.select_related('user').prefetch_related(
            'intervals', 'breaks'
        ).filter(
            user=user
        ).order_by('-start_time')[:limit]