from typing import Optional, Union, Dict, Any
from django.db import models
from django.conf import settings
from django.utils import timezone
from django.core import validators
from datetime import datetime, timedelta


class TimerSession(models.Model):
    """
    Represents a work session with timer functionality
    Tracks 20-minute intervals and break periods
    """
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='timer_sessions')

    # Session details
    start_time = models.DateTimeField(default=timezone.now)
    end_time = models.DateTimeField(null=True, blank=True)
    is_active = models.BooleanField(default=True)

    # Timer settings for this session
    work_interval_minutes = models.PositiveIntegerField(default=20)
    break_duration_seconds = models.PositiveIntegerField(default=20)

    # Session statistics
    total_intervals_completed = models.PositiveIntegerField(default=0)
    total_breaks_taken = models.PositiveIntegerField(default=0)
    total_work_minutes = models.PositiveIntegerField(default=0)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'timer_session'
        verbose_name = 'Timer Session'
        verbose_name_plural = 'Timer Sessions'
        ordering = ['-start_time']
        indexes = [
            models.Index(fields=['user', 'start_time']),
            models.Index(fields=['user', 'is_active']),
            models.Index(fields=['start_time']),
        ]
        constraints = [
            # Prevent multiple active sessions per user
            models.UniqueConstraint(
                fields=['user'],
                condition=models.Q(is_active=True),
                name='unique_active_session_per_user'
            )
        ]

    def __str__(self) -> str:
        status = "Active" if self.is_active else "Completed"
        return f"{self.user.email} - {self.start_time.date()} ({status})"

    @property
    def duration_minutes(self) -> int:
        """Calculate session duration in minutes"""
        end = self.end_time or timezone.now()
        return int((end - self.start_time).total_seconds() / 60)

    def end_session(self) -> None:
        """End the current timer session"""
        self.end_time = timezone.now()
        self.is_active = False
        self.save()


class TimerInterval(models.Model):
    """
    Represents individual 20-minute work intervals within a session
    """
    session = models.ForeignKey(TimerSession, on_delete=models.CASCADE, related_name='intervals')

    # Interval details
    interval_number = models.PositiveIntegerField()  # 1st, 2nd, 3rd interval in session
    start_time = models.DateTimeField(default=timezone.now)
    end_time = models.DateTimeField(null=True, blank=True)

    # Status
    STATUS_CHOICES = [
        ('active', 'Active'),
        ('completed', 'Completed'),
        ('skipped', 'Skipped'),
        ('paused', 'Paused'),
    ]
    status = models.CharField(max_length=10, choices=STATUS_CHOICES, default='active')

    # Tracking
    reminder_sent = models.BooleanField(default=False)
    reminder_sent_at = models.DateTimeField(null=True, blank=True)

    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'timer_interval'
        verbose_name = 'Timer Interval'
        verbose_name_plural = 'Timer Intervals'
        ordering = ['session', 'interval_number']
        unique_together = ['session', 'interval_number']
        indexes = [
            models.Index(fields=['session', 'status']),
            models.Index(fields=['start_time', 'status']),
            models.Index(fields=['session', 'interval_number']),
        ]

    def __str__(self) -> str:
        return f"Interval {self.interval_number} - {self.session.user.email}"

    @property
    def duration_minutes(self) -> int:
        """Calculate interval duration in minutes"""
        end = self.end_time or timezone.now()
        return int((end - self.start_time).total_seconds() / 60)

    def complete_interval(self) -> None:
        """Mark interval as completed"""
        self.end_time = timezone.now()
        self.status = 'completed'
        self.save()


class BreakRecord(models.Model):
    """
    Records when users take breaks following the 20-20-20 rule
    """
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='break_records')
    session = models.ForeignKey(TimerSession, on_delete=models.CASCADE, related_name='breaks')
    interval = models.ForeignKey(TimerInterval, on_delete=models.CASCADE, related_name='break_taken')
    
    # Break details
    break_start_time = models.DateTimeField(default=timezone.now)
    break_end_time = models.DateTimeField(null=True, blank=True)
    
    # Break compliance
    break_duration_seconds = models.PositiveIntegerField(default=0)
    looked_at_distance = models.BooleanField(default=False)  # User confirmation
    break_completed = models.BooleanField(default=False)
    
    # Break type
    BREAK_TYPE_CHOICES = [
        ('scheduled', 'Scheduled 20-20-20 Break'),
        ('manual', 'Manual Break'),
        ('extended', 'Extended Break'),
    ]
    break_type = models.CharField(max_length=10, choices=BREAK_TYPE_CHOICES, default='scheduled')
    
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        db_table = 'timer_break_record'
        verbose_name = 'Break Record'
        verbose_name_plural = 'Break Records'
        ordering = ['-break_start_time']
        indexes = [
            models.Index(fields=['user', 'break_start_time']),
            models.Index(fields=['session', 'break_completed']),
            models.Index(fields=['break_start_time', 'break_completed']),
            models.Index(fields=['user', 'break_completed', 'break_duration_seconds']),
        ]
    
    def __str__(self):
        return f"Break - {self.user.email} - {self.break_start_time.date()}"
    
    def complete_break(self, looked_at_distance: bool = False) -> None:
        """
        Mark break as completed and calculate duration

        Args:
            looked_at_distance: Whether user looked at distance during break
        """
        self.break_end_time = timezone.now()
        self.break_duration_seconds = int((self.break_end_time - self.break_start_time).total_seconds())
        self.looked_at_distance = looked_at_distance
        self.break_completed = True
        self.save()
    
    @property
    def is_compliant(self) -> bool:
        """
        Check if break meets duration criteria and distance look requirement

        Handles None/null values safely to prevent crashes
        """
        import logging
        logger = logging.getLogger(__name__)

        try:
            # Get user's expected break duration with error handling
            user_settings = getattr(self.user, 'timer_settings', None)
            if user_settings:
                try:
                    expected_duration = user_settings.get_effective_break_duration()
                except Exception as e:
                    logger.warning(f"Failed to get break duration for user {self.user.id}: {e}")
                    expected_duration = 20
            else:
                expected_duration = 20

            # Ensure break_duration_seconds is valid (handle None/null)
            duration = self.break_duration_seconds or 0

            # Break is compliant if it meets expected duration and user looked at distance
            return duration >= expected_duration and bool(self.looked_at_distance)

        except Exception as e:
            logger.error(f"Error checking break compliance for break {self.id}: {e}")
            return False


class UserTimerSettings(models.Model):
    """
    Customizable timer settings per user
    """
    user = models.OneToOneField(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='timer_settings')
    
    # Timer intervals
    work_interval_minutes = models.PositiveIntegerField(default=20)
    break_duration_seconds = models.PositiveIntegerField(default=20)
    long_break_minutes = models.PositiveIntegerField(default=5)  # Every 4 intervals

    # Smart break duration options
    BREAK_DURATION_CHOICES = [
        (10, '10 seconds - Quick break'),
        (20, '20 seconds - Standard 20-20-20'),
        (30, '30 seconds - Extended break'),
        (60, '1 minute - Long break'),
    ]
    smart_break_enabled = models.BooleanField(default=False)
    preferred_break_duration = models.PositiveIntegerField(
        choices=BREAK_DURATION_CHOICES,
        default=20,
        help_text='Preferred break duration for smart break system'
    )
    
    # Notification settings
    sound_notification = models.BooleanField(default=True)
    desktop_notification = models.BooleanField(default=True)
    email_notification = models.BooleanField(default=False)
    
    # Sound type choices
    SOUND_TYPE_CHOICES = [
        ('gentle', 'Gentle Tone'),
        ('chime', 'Chime'),
        ('beep', 'Beep'),
        ('bell', 'Bell'),
    ]
    notification_sound_type = models.CharField(
        max_length=10, 
        choices=SOUND_TYPE_CHOICES, 
        default='gentle',
        help_text='Type of sound to play when timer reaches zero'
    )
    sound_volume = models.FloatField(
        default=0.5, 
        validators=[validators.MinValueValidator(0.0), validators.MaxValueValidator(1.0)],
        help_text='Sound volume (0.0 to 1.0)'
    )
    
    # Visual settings
    show_progress_bar = models.BooleanField(default=True)
    show_time_remaining = models.BooleanField(default=True)
    dark_mode = models.BooleanField(default=False)
    
    # Advanced settings (Premium users)
    auto_start_break = models.BooleanField(default=False)
    auto_start_work = models.BooleanField(default=False)
    custom_break_messages = models.TextField(blank=True)
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        db_table = 'timer_user_settings'
        verbose_name = 'User Timer Settings'
        verbose_name_plural = 'User Timer Settings'
    
    def __str__(self):
        return f"Timer Settings - {self.user.email}"

    def get_effective_break_duration(self) -> int:
        """
        Returns the effective break duration based on smart break settings
        """
        if self.smart_break_enabled:
            return self.preferred_break_duration
        return self.break_duration_seconds

    def get_break_duration_display_text(self) -> str:
        """
        Returns user-friendly text for the current break duration
        """
        duration = self.get_effective_break_duration()
        if duration < 60:
            return f"{duration} seconds"
        else:
            return f"{duration // 60} minute{'s' if duration > 60 else ''}"


class UserFeedback(models.Model):
    """
    User feedback collection for break preferences and app improvement
    """
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='feedback_entries')

    # Feedback type and context
    FEEDBACK_TYPES = [
        ('break_duration', 'Break Duration Preference'),
        ('interruption_timing', 'Interruption Timing Feedback'),
        ('feature_request', 'Feature Request'),
        ('bug_report', 'Bug Report'),
        ('general', 'General Feedback'),
        ('break_compliance', 'Break Compliance Feedback'),
    ]
    feedback_type = models.CharField(max_length=20, choices=FEEDBACK_TYPES)

    # Feedback content
    title = models.CharField(max_length=200)
    message = models.TextField()
    rating = models.PositiveIntegerField(null=True, blank=True, help_text="1-5 rating scale")

    # Context information
    timer_session_id = models.PositiveIntegerField(null=True, blank=True)
    break_record_id = models.PositiveIntegerField(null=True, blank=True)
    context_data = models.JSONField(default=dict, blank=True)

    # Priority and status
    PRIORITY_CHOICES = [
        ('low', 'Low Priority'),
        ('normal', 'Normal Priority'),
        ('high', 'High Priority'),
        ('urgent', 'Urgent'),
    ]
    priority = models.CharField(max_length=10, choices=PRIORITY_CHOICES, default='normal')

    STATUS_CHOICES = [
        ('new', 'New'),
        ('acknowledged', 'Acknowledged'),
        ('in_progress', 'In Progress'),
        ('resolved', 'Resolved'),
        ('closed', 'Closed'),
    ]
    status = models.CharField(max_length=15, choices=STATUS_CHOICES, default='new')

    # User experience data
    user_agent = models.TextField(blank=True)
    page_url = models.URLField(blank=True)
    screen_resolution = models.CharField(max_length=20, blank=True)

    # Timestamps
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    resolved_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        db_table = 'user_feedback'
        verbose_name = 'User Feedback'
        verbose_name_plural = 'User Feedback Entries'
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['user', 'feedback_type']),
            models.Index(fields=['feedback_type', 'status']),
            models.Index(fields=['created_at']),
        ]

    def __str__(self):
        return f"{self.user.email} - {self.get_feedback_type_display()} - {self.title[:50]}"

    def mark_as_resolved(self) -> None:
        """
        Mark feedback as resolved with timestamp

        Updates:
            status: Set to 'resolved'
            resolved_at: Current timestamp
        """
        self.status = 'resolved'
        self.resolved_at = timezone.now()
        self.save()


class BreakPreferenceAnalytics(models.Model):
    """
    Analytics for break preferences to improve smart break suggestions
    """
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='break_analytics')

    # Break behavior patterns
    preferred_break_duration = models.PositiveIntegerField(default=20)
    actual_average_break_duration = models.FloatField(default=0.0)
    break_completion_rate = models.FloatField(default=0.0)  # Percentage

    # Timing preferences
    preferred_break_times = models.JSONField(default=list)  # [{'hour': 10, 'minute': 30}, ...]
    most_skipped_times = models.JSONField(default=list)

    # Compliance patterns
    compliant_breaks_percentage = models.FloatField(default=0.0)
    looks_at_distance_rate = models.FloatField(default=0.0)

    # Effectiveness metrics
    reported_eye_strain_reduction = models.FloatField(null=True, blank=True)
    productivity_impact_rating = models.PositiveIntegerField(null=True, blank=True)  # 1-5 scale

    # Data collection period
    analysis_start_date = models.DateField()
    analysis_end_date = models.DateField()
    total_sessions_analyzed = models.PositiveIntegerField(default=0)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'break_preference_analytics'
        verbose_name = 'Break Preference Analytics'
        verbose_name_plural = 'Break Preference Analytics'
        unique_together = ['user', 'analysis_start_date', 'analysis_end_date']

    def __str__(self):
        return f"{self.user.email} - Analytics {self.analysis_start_date} to {self.analysis_end_date}"

    def calculate_smart_break_suggestion(self) -> int:
        """
        Calculate suggested break duration based on user patterns
        """
        # If user consistently takes longer breaks than set, suggest longer duration
        if self.actual_average_break_duration > self.preferred_break_duration * 1.5:
            if self.actual_average_break_duration <= 30:
                return 30
            elif self.actual_average_break_duration <= 60:
                return 60
            else:
                return 60  # Cap at 60 seconds

        # If user has low completion rate, suggest shorter duration
        if self.break_completion_rate < 0.6:
            return 10

        # Default to current preference if patterns are good
        return self.preferred_break_duration