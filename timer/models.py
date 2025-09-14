from django.db import models
from django.conf import settings
from django.utils import timezone
from django.core import validators


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
    
    def __str__(self):
        status = "Active" if self.is_active else "Completed"
        return f"{self.user.email} - {self.start_time.date()} ({status})"
    
    @property
    def duration_minutes(self):
        end = self.end_time or timezone.now()
        return int((end - self.start_time).total_seconds() / 60)
    
    def end_session(self):
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
    
    def __str__(self):
        return f"Interval {self.interval_number} - {self.session.user.email}"
    
    @property
    def duration_minutes(self):
        end = self.end_time or timezone.now()
        return int((end - self.start_time).total_seconds() / 60)
    
    def complete_interval(self):
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
    
    def __str__(self):
        return f"Break - {self.user.email} - {self.break_start_time.date()}"
    
    def complete_break(self, looked_at_distance=False):
        """Mark break as completed"""
        self.break_end_time = timezone.now()
        self.break_duration_seconds = int((self.break_end_time - self.break_start_time).total_seconds())
        self.looked_at_distance = looked_at_distance
        self.break_completed = True
        self.save()
    
    @property
    def is_compliant(self):
        """Check if break meets 20-20-20 rule criteria"""
        return self.break_duration_seconds >= 20 and self.looked_at_distance


class UserTimerSettings(models.Model):
    """
    Customizable timer settings per user
    """
    user = models.OneToOneField(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='timer_settings')
    
    # Timer intervals
    work_interval_minutes = models.PositiveIntegerField(default=20)
    break_duration_seconds = models.PositiveIntegerField(default=20)
    long_break_minutes = models.PositiveIntegerField(default=5)  # Every 4 intervals
    
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
    
    # Advanced settings (Pro users)
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