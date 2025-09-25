from django.db import models
from django.conf import settings
from django.utils import timezone
import json


class CalendarProvider(models.Model):
    """
    Supported calendar providers
    """
    PROVIDER_CHOICES = [
        ('google', 'Google Calendar'),
        ('outlook', 'Microsoft Outlook/Office 365'),
        ('apple', 'Apple Calendar (iCloud)'),
        ('exchange', 'Microsoft Exchange'),
    ]

    name = models.CharField(max_length=20, choices=PROVIDER_CHOICES, unique=True)
    display_name = models.CharField(max_length=100)
    is_active = models.BooleanField(default=True)
    requires_oauth = models.BooleanField(default=True)
    api_endpoint = models.URLField(blank=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'calendar_provider'
        verbose_name = 'Calendar Provider'
        verbose_name_plural = 'Calendar Providers'

    def __str__(self):
        return self.display_name


class UserCalendarConnection(models.Model):
    """
    User's connection to a calendar provider
    """
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='calendar_connections')
    provider = models.ForeignKey(CalendarProvider, on_delete=models.CASCADE)

    # Authentication tokens
    access_token = models.TextField(blank=True)  # Encrypted in production
    refresh_token = models.TextField(blank=True)  # Encrypted in production
    token_expires_at = models.DateTimeField(null=True, blank=True)

    # Calendar specific settings
    calendar_id = models.CharField(max_length=255, blank=True)  # Primary calendar ID
    calendar_name = models.CharField(max_length=255, blank=True)

    # User preferences
    is_active = models.BooleanField(default=True)
    check_busy_periods = models.BooleanField(default=True)
    respect_focus_time = models.BooleanField(default=True)
    minimum_meeting_gap_minutes = models.PositiveIntegerField(default=5)

    # Smart interruption settings
    INTERRUPTION_RULES = [
        ('never', 'Never interrupt during meetings'),
        ('low_priority', 'Only interrupt for low priority meetings'),
        ('before_end', 'Interrupt 5 minutes before meeting ends'),
        ('between_meetings', 'Only interrupt between meetings'),
    ]
    interruption_rule = models.CharField(
        max_length=20,
        choices=INTERRUPTION_RULES,
        default='between_meetings'
    )

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    last_sync_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        db_table = 'user_calendar_connection'
        verbose_name = 'User Calendar Connection'
        verbose_name_plural = 'User Calendar Connections'
        unique_together = ['user', 'provider']

    def __str__(self):
        return f"{self.user.email} - {self.provider.display_name}"

    @property
    def is_token_expired(self):
        if not self.token_expires_at:
            return True
        return timezone.now() >= self.token_expires_at

    def needs_refresh(self):
        """Check if token needs refresh (expires in next 10 minutes)"""
        if not self.token_expires_at:
            return True
        return timezone.now() >= self.token_expires_at - timezone.timedelta(minutes=10)
