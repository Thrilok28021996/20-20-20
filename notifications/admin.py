from django.contrib import admin
from django.utils.html import format_html
from .models import (
    NotificationTemplate, Notification, BreakReminder,
    EmailCampaign, NotificationPreference
)


@admin.register(NotificationTemplate)
class NotificationTemplateAdmin(admin.ModelAdmin):
    """
    Admin interface for NotificationTemplate model
    """
    list_display = (
        'name', 'notification_type', 'is_active', 'updated_at'
    )
    list_filter = ('notification_type', 'is_active', 'target_subscription_types')
    search_fields = ('name', 'subject_template', 'title_template')
    readonly_fields = ('created_at', 'updated_at')
    
    fieldsets = (
        ('Template Details', {
            'fields': ('name', 'notification_type', 'is_active')
        }),
        ('Email Templates', {
            'fields': ('subject_template', 'html_template', 'text_template')
        }),
        ('In-App Templates', {
            'fields': ('title_template', 'message_template')
        }),
        ('Targeting', {
            'fields': ('target_subscription_types',)
        }),
        ('Timestamps', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )


@admin.register(Notification)
class NotificationAdmin(admin.ModelAdmin):
    """
    Admin interface for Notification model
    """
    list_display = (
        'user', 'title', 'notification_type', 'channel',
        'status', 'created_at', 'sent_at'
    )
    list_filter = ('notification_type', 'channel', 'status', 'created_at')
    search_fields = ('user__email', 'title', 'message')
    readonly_fields = (
        'created_at', 'sent_at', 'delivered_at', 'read_at', 'clicked_at'
    )
    date_hierarchy = 'created_at'
    
    fieldsets = (
        ('Notification Details', {
            'fields': ('user', 'template', 'title', 'message')
        }),
        ('Delivery', {
            'fields': ('notification_type', 'channel', 'status')
        }),
        ('Action', {
            'fields': ('action_url', 'metadata')
        }),
        ('Tracking', {
            'fields': (
                'delivery_attempts', 'last_attempt_at', 'error_message'
            )
        }),
        ('Timestamps', {
            'fields': (
                'created_at', 'sent_at', 'delivered_at', 'read_at', 'clicked_at'
            ),
            'classes': ('collapse',)
        }),
    )
    
    actions = ['mark_as_sent', 'resend_failed_notifications']
    
    def mark_as_sent(self, request, queryset):
        updated = queryset.update(status='sent')
        self.message_user(request, f'{updated} notifications marked as sent.')
    mark_as_sent.short_description = "Mark selected notifications as sent"
    
    def resend_failed_notifications(self, request, queryset):
        failed_notifications = queryset.filter(status='failed')
        for notification in failed_notifications:
            notification.status = 'pending'
            notification.save()
        self.message_user(
            request, 
            f'{failed_notifications.count()} failed notifications queued for retry.'
        )
    resend_failed_notifications.short_description = "Retry failed notifications"


@admin.register(BreakReminder)
class BreakReminderAdmin(admin.ModelAdmin):
    """
    Admin interface for BreakReminder model
    """
    list_display = (
        'user', 'interval_number', 'reminder_type', 'scheduled_time',
        'user_response', 'snooze_count'
    )
    list_filter = ('reminder_type', 'user_response', 'scheduled_time')
    search_fields = ('user__email', 'notification__title')
    readonly_fields = ('created_at', 'response_time')
    date_hierarchy = 'scheduled_time'
    
    fieldsets = (
        ('Reminder Details', {
            'fields': (
                'user', 'notification', 'timer_session_id', 'interval_number'
            )
        }),
        ('Scheduling', {
            'fields': ('scheduled_time', 'reminder_type')
        }),
        ('User Response', {
            'fields': ('user_response', 'response_time')
        }),
        ('Snooze', {
            'fields': ('snooze_count', 'snooze_until')
        }),
        ('Timestamp', {
            'fields': ('created_at',)
        }),
    )


@admin.register(EmailCampaign)
class EmailCampaignAdmin(admin.ModelAdmin):
    """
    Admin interface for EmailCampaign model
    """
    list_display = (
        'name', 'status', 'scheduled_at', 'total_recipients',
        'open_rate', 'click_rate'
    )
    list_filter = ('status', 'scheduled_at', 'sent_at')
    search_fields = ('name', 'description')
    readonly_fields = (
        'created_at', 'updated_at', 'sent_at', 'open_rate', 'click_rate'
    )
    date_hierarchy = 'scheduled_at'
    
    fieldsets = (
        ('Campaign Details', {
            'fields': ('name', 'description', 'template', 'target_audience')
        }),
        ('Scheduling', {
            'fields': ('status', 'scheduled_at', 'sent_at')
        }),
        ('Metrics', {
            'fields': (
                'total_recipients', 'emails_sent', 'emails_delivered',
                'emails_opened', 'emails_clicked', 'open_rate', 'click_rate'
            )
        }),
        ('Timestamps', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )
    
    def open_rate(self, obj):
        rate = obj.open_rate
        if rate > 20:
            color = 'green'
        elif rate > 10:
            color = 'orange'
        else:
            color = 'red'
        return format_html(f'<span style="color: {color};">{rate:.1f}%</span>')
    open_rate.short_description = 'Open Rate'
    
    def click_rate(self, obj):
        rate = obj.click_rate
        if rate > 5:
            color = 'green'
        elif rate > 2:
            color = 'orange'
        else:
            color = 'red'
        return format_html(f'<span style="color: {color};">{rate:.1f}%</span>')
    click_rate.short_description = 'Click Rate'


@admin.register(NotificationPreference)
class NotificationPreferenceAdmin(admin.ModelAdmin):
    """
    Admin interface for NotificationPreference model
    """
    list_display = (
        'user', 'email_enabled', 'in_app_enabled', 'break_reminders',
        'daily_summaries', 'weekly_reports'
    )
    list_filter = (
        'email_enabled', 'in_app_enabled', 'break_reminders',
        'daily_summaries', 'weekly_reports', 'weekend_notifications'
    )
    search_fields = ('user__email', 'user__username')
    readonly_fields = ('created_at', 'updated_at')
    
    fieldsets = (
        ('User', {
            'fields': ('user',)
        }),
        ('Channels', {
            'fields': (
                'email_enabled', 'in_app_enabled', 'browser_push_enabled',
                'desktop_enabled'
            )
        }),
        ('Notification Types', {
            'fields': (
                'break_reminders', 'daily_summaries', 'weekly_reports',
                'streak_milestones', 'tips_and_advice', 'promotional_emails'
            )
        }),
        ('Timing', {
            'fields': (
                'quiet_hours_start', 'quiet_hours_end', 'weekend_notifications'
            )
        }),
        ('Break Settings', {
            'fields': (
                'break_reminder_advance_seconds', 'max_snooze_count',
                'snooze_duration_minutes'
            )
        }),
        ('Timestamps', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )