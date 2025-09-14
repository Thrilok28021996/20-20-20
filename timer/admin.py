from django.contrib import admin
from django.utils.html import format_html
from .models import TimerSession, TimerInterval, BreakRecord, UserTimerSettings


class TimerIntervalInline(admin.TabularInline):
    model = TimerInterval
    extra = 0
    readonly_fields = ('created_at', 'duration_minutes')
    fields = ('interval_number', 'start_time', 'end_time', 'status', 'reminder_sent', 'duration_minutes')


class BreakRecordInline(admin.TabularInline):
    model = BreakRecord
    extra = 0
    readonly_fields = ('created_at', 'break_duration_seconds')
    fields = ('break_start_time', 'break_end_time', 'break_type', 'break_completed', 'looked_at_distance')


@admin.register(TimerSession)
class TimerSessionAdmin(admin.ModelAdmin):
    """
    Admin interface for TimerSession model
    """
    list_display = (
        'user', 'start_time', 'end_time', 'is_active',
        'total_intervals_completed', 'total_breaks_taken',
        'duration_minutes', 'session_status'
    )
    list_filter = ('is_active', 'start_time', 'work_interval_minutes')
    search_fields = ('user__email', 'user__username')
    readonly_fields = ('created_at', 'updated_at', 'duration_minutes')
    date_hierarchy = 'start_time'
    
    inlines = [TimerIntervalInline, BreakRecordInline]
    
    fieldsets = (
        ('Session Details', {
            'fields': ('user', 'start_time', 'end_time', 'is_active')
        }),
        ('Timer Settings', {
            'fields': ('work_interval_minutes', 'break_duration_seconds')
        }),
        ('Statistics', {
            'fields': (
                'total_intervals_completed', 'total_breaks_taken', 
                'total_work_minutes', 'duration_minutes'
            )
        }),
        ('Timestamps', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )
    
    def session_status(self, obj):
        if obj.is_active:
            return format_html('<span style="color: green;">Active</span>')
        return format_html('<span style="color: gray;">Completed</span>')
    session_status.short_description = 'Status'
    
    actions = ['end_selected_sessions']
    
    def end_selected_sessions(self, request, queryset):
        active_sessions = queryset.filter(is_active=True)
        for session in active_sessions:
            session.end_session()
        self.message_user(request, f'{active_sessions.count()} sessions ended.')
    end_selected_sessions.short_description = "End selected active sessions"


@admin.register(TimerInterval)
class TimerIntervalAdmin(admin.ModelAdmin):
    """
    Admin interface for TimerInterval model
    """
    list_display = (
        'session', 'interval_number', 'start_time', 'end_time',
        'status', 'reminder_sent', 'duration_minutes'
    )
    list_filter = ('status', 'reminder_sent', 'start_time')
    search_fields = ('session__user__email',)
    readonly_fields = ('created_at', 'duration_minutes')
    
    fieldsets = (
        ('Interval Details', {
            'fields': ('session', 'interval_number', 'start_time', 'end_time', 'status')
        }),
        ('Reminders', {
            'fields': ('reminder_sent', 'reminder_sent_at')
        }),
        ('Info', {
            'fields': ('duration_minutes', 'created_at')
        }),
    )


@admin.register(BreakRecord)
class BreakRecordAdmin(admin.ModelAdmin):
    """
    Admin interface for BreakRecord model
    """
    list_display = (
        'user', 'session', 'break_start_time', 'break_end_time',
        'break_type', 'break_completed', 'is_compliant',
        'break_duration_seconds'
    )
    list_filter = ('break_type', 'break_completed', 'looked_at_distance', 'break_start_time')
    search_fields = ('user__email', 'session__id')
    readonly_fields = ('created_at', 'break_duration_seconds', 'is_compliant')
    date_hierarchy = 'break_start_time'
    
    fieldsets = (
        ('Break Details', {
            'fields': ('user', 'session', 'interval', 'break_type')
        }),
        ('Timing', {
            'fields': ('break_start_time', 'break_end_time', 'break_duration_seconds')
        }),
        ('Compliance', {
            'fields': ('break_completed', 'looked_at_distance', 'is_compliant')
        }),
        ('Timestamp', {
            'fields': ('created_at',)
        }),
    )


@admin.register(UserTimerSettings)
class UserTimerSettingsAdmin(admin.ModelAdmin):
    """
    Admin interface for UserTimerSettings model
    """
    list_display = (
        'user', 'work_interval_minutes', 'break_duration_seconds',
        'sound_notification', 'desktop_notification', 'dark_mode'
    )
    list_filter = (
        'sound_notification', 'desktop_notification', 'email_notification',
        'dark_mode', 'auto_start_break', 'auto_start_work'
    )
    search_fields = ('user__email', 'user__username')
    readonly_fields = ('created_at', 'updated_at')
    
    fieldsets = (
        ('User', {
            'fields': ('user',)
        }),
        ('Timer Intervals', {
            'fields': (
                'work_interval_minutes', 'break_duration_seconds', 'long_break_minutes'
            )
        }),
        ('Notifications', {
            'fields': (
                'sound_notification', 'desktop_notification', 'email_notification'
            )
        }),
        ('Visual Settings', {
            'fields': (
                'show_progress_bar', 'show_time_remaining', 'dark_mode'
            )
        }),
        ('Advanced Settings', {
            'fields': (
                'auto_start_break', 'auto_start_work', 'custom_break_messages'
            ),
            'classes': ('collapse',)
        }),
        ('Timestamps', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )