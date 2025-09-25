from django.db import models
from django.conf import settings
from django.utils import timezone


class NotificationTemplate(models.Model):
    """
    Templates for different types of notifications
    """
    NOTIFICATION_TYPES = [
        ('break_reminder', 'Break Reminder'),
        ('daily_summary', 'Daily Summary'),
        ('weekly_report', 'Weekly Report'),
        ('streak_milestone', 'Streak Milestone'),
        ('subscription_expiring', 'Subscription Expiring'),
        ('welcome', 'Welcome Message'),
        ('tips', 'Eye Health Tips'),
    ]
    
    name = models.CharField(max_length=100)
    notification_type = models.CharField(max_length=30, choices=NOTIFICATION_TYPES)
    
    # Email template fields
    subject_template = models.CharField(max_length=200)
    html_template = models.TextField()
    text_template = models.TextField()
    
    # In-app notification template
    title_template = models.CharField(max_length=100)
    message_template = models.TextField()
    
    # Targeting
    target_subscription_types = models.JSONField(default=list)  # ['free', 'premium']
    is_active = models.BooleanField(default=True)
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        db_table = 'notifications_template'
        verbose_name = 'Notification Template'
        verbose_name_plural = 'Notification Templates'
    
    def __str__(self):
        return f"{self.name} ({self.get_notification_type_display()})"


class Notification(models.Model):
    """
    Individual notifications sent to users
    """
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='notifications')
    template = models.ForeignKey(NotificationTemplate, on_delete=models.CASCADE, null=True, blank=True)
    
    # Notification content
    title = models.CharField(max_length=200)
    message = models.TextField()
    
    # Notification details
    NOTIFICATION_TYPES = NotificationTemplate.NOTIFICATION_TYPES
    notification_type = models.CharField(max_length=30, choices=NOTIFICATION_TYPES)
    
    CHANNELS = [
        ('in_app', 'In-App Notification'),
        ('email', 'Email'),
        ('browser_push', 'Browser Push'),
        ('desktop', 'Desktop Notification'),
    ]
    channel = models.CharField(max_length=20, choices=CHANNELS)
    
    # Status
    STATUS_CHOICES = [
        ('pending', 'Pending'),
        ('sent', 'Sent'),
        ('delivered', 'Delivered'),
        ('read', 'Read'),
        ('clicked', 'Clicked'),
        ('failed', 'Failed'),
    ]
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending')
    
    # Timestamps
    created_at = models.DateTimeField(auto_now_add=True)
    sent_at = models.DateTimeField(null=True, blank=True)
    delivered_at = models.DateTimeField(null=True, blank=True)
    read_at = models.DateTimeField(null=True, blank=True)
    clicked_at = models.DateTimeField(null=True, blank=True)
    
    # Additional data
    action_url = models.URLField(blank=True)  # URL to redirect when clicked
    metadata = models.JSONField(default=dict, blank=True)  # Additional context data
    
    # Delivery tracking
    delivery_attempts = models.PositiveIntegerField(default=0)
    last_attempt_at = models.DateTimeField(null=True, blank=True)
    error_message = models.TextField(blank=True)
    
    class Meta:
        db_table = 'notifications_notification'
        verbose_name = 'Notification'
        verbose_name_plural = 'Notifications'
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['user', 'status']),
            models.Index(fields=['notification_type', 'created_at']),
        ]
    
    def __str__(self):
        return f"{self.title} - {self.user.email} ({self.status})"
    
    def mark_as_sent(self):
        self.status = 'sent'
        self.sent_at = timezone.now()
        self.save()
    
    def mark_as_read(self):
        if self.status != 'read':
            self.status = 'read'
            self.read_at = timezone.now()
            self.save()
    
    def mark_as_clicked(self):
        self.status = 'clicked'
        self.clicked_at = timezone.now()
        self.save()


class BreakReminder(models.Model):
    """
    Specific break reminder notifications with timer context
    """
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='user_break_reminders')
    notification = models.OneToOneField(Notification, on_delete=models.CASCADE, related_name='break_reminder')
    
    # Timer context
    timer_session_id = models.PositiveIntegerField(null=True, blank=True)
    interval_number = models.PositiveIntegerField()
    
    # Reminder details
    scheduled_time = models.DateTimeField()
    reminder_type = models.CharField(
        max_length=20,
        choices=[
            ('pre_break', 'Pre-Break Warning'),
            ('break_time', 'Break Time'),
            ('break_ending', 'Break Ending Soon'),
        ],
        default='break_time'
    )
    
    # User response
    USER_RESPONSES = [
        ('taken', 'Break Taken'),
        ('snoozed', 'Snoozed'),
        ('dismissed', 'Dismissed'),
        ('ignored', 'Ignored'),
    ]
    user_response = models.CharField(max_length=20, choices=USER_RESPONSES, blank=True)
    response_time = models.DateTimeField(null=True, blank=True)
    
    # Snooze functionality
    snooze_count = models.PositiveIntegerField(default=0)
    snooze_until = models.DateTimeField(null=True, blank=True)
    
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        db_table = 'notifications_break_reminder'
        verbose_name = 'Break Reminder'
        verbose_name_plural = 'Break Reminders'
        ordering = ['-scheduled_time']
    
    def __str__(self):
        return f"Break Reminder - {self.user.email} - Interval {self.interval_number}"
    
    def snooze_reminder(self, minutes=5):
        """Snooze the reminder for specified minutes"""
        self.snooze_count += 1
        self.snooze_until = timezone.now() + timezone.timedelta(minutes=minutes)
        self.user_response = 'snoozed'
        self.response_time = timezone.now()
        self.save()


class EmailCampaign(models.Model):
    """
    Email campaigns for user engagement and retention
    """
    name = models.CharField(max_length=200)
    description = models.TextField(blank=True)
    
    # Campaign details
    template = models.ForeignKey(NotificationTemplate, on_delete=models.CASCADE)
    target_audience = models.JSONField(default=dict)  # Filtering criteria
    
    # Scheduling
    STATUS_CHOICES = [
        ('draft', 'Draft'),
        ('scheduled', 'Scheduled'),
        ('sending', 'Sending'),
        ('sent', 'Sent'),
        ('paused', 'Paused'),
        ('cancelled', 'Cancelled'),
    ]
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='draft')
    
    scheduled_at = models.DateTimeField(null=True, blank=True)
    sent_at = models.DateTimeField(null=True, blank=True)
    
    # Campaign metrics
    total_recipients = models.PositiveIntegerField(default=0)
    emails_sent = models.PositiveIntegerField(default=0)
    emails_delivered = models.PositiveIntegerField(default=0)
    emails_opened = models.PositiveIntegerField(default=0)
    emails_clicked = models.PositiveIntegerField(default=0)
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        db_table = 'notifications_email_campaign'
        verbose_name = 'Email Campaign'
        verbose_name_plural = 'Email Campaigns'
        ordering = ['-created_at']
    
    def __str__(self):
        return f"{self.name} ({self.status})"
    
    @property
    def open_rate(self):
        if self.emails_delivered == 0:
            return 0.0
        return (self.emails_opened / self.emails_delivered) * 100
    
    @property
    def click_rate(self):
        if self.emails_delivered == 0:
            return 0.0
        return (self.emails_clicked / self.emails_delivered) * 100


class NotificationPreference(models.Model):
    """
    User preferences for notifications
    """
    user = models.OneToOneField(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='notification_preferences')
    
    # Channel preferences
    email_enabled = models.BooleanField(default=True)
    in_app_enabled = models.BooleanField(default=True)
    browser_push_enabled = models.BooleanField(default=False)
    desktop_enabled = models.BooleanField(default=True)
    
    # Notification type preferences
    break_reminders = models.BooleanField(default=True)
    daily_summaries = models.BooleanField(default=True)
    weekly_reports = models.BooleanField(default=True)
    streak_milestones = models.BooleanField(default=True)
    tips_and_advice = models.BooleanField(default=False)
    promotional_emails = models.BooleanField(default=False)
    
    # Timing preferences
    quiet_hours_start = models.TimeField(null=True, blank=True)  # No notifications during these hours
    quiet_hours_end = models.TimeField(null=True, blank=True)
    weekend_notifications = models.BooleanField(default=False)
    
    # Break reminder specific settings
    break_reminder_advance_seconds = models.PositiveIntegerField(default=30)  # Warn X seconds before break
    max_snooze_count = models.PositiveIntegerField(default=3)
    snooze_duration_minutes = models.PositiveIntegerField(default=5)
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        db_table = 'notifications_preference'
        verbose_name = 'Notification Preference'
        verbose_name_plural = 'Notification Preferences'
    
    def __str__(self):
        return f"Notification Preferences - {self.user.email}"