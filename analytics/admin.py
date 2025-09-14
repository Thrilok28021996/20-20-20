from django.contrib import admin
from django.utils.html import format_html
from django.db.models import Sum, Avg
from .models import (
    DailyStats, WeeklyStats, MonthlyStats, 
    UserBehaviorEvent, EngagementMetrics
)


@admin.register(DailyStats)
class DailyStatsAdmin(admin.ModelAdmin):
    """
    Admin interface for DailyStats model
    """
    list_display = (
        'user', 'date', 'total_work_minutes', 'total_intervals_completed',
        'total_breaks_taken', 'compliance_rate', 'productivity_score',
        'streak_maintained'
    )
    list_filter = ('date', 'streak_maintained')
    search_fields = ('user__email', 'user__username')
    readonly_fields = ('created_at', 'updated_at', 'compliance_rate')
    date_hierarchy = 'date'
    
    fieldsets = (
        ('User & Date', {
            'fields': ('user', 'date')
        }),
        ('Work Statistics', {
            'fields': (
                'total_work_minutes', 'total_intervals_completed', 
                'total_sessions'
            )
        }),
        ('Break Statistics', {
            'fields': (
                'total_breaks_taken', 'breaks_on_time', 'breaks_compliant',
                'average_break_duration', 'compliance_rate'
            )
        }),
        ('Performance', {
            'fields': ('streak_maintained', 'productivity_score')
        }),
        ('Timestamps', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )
    
    def get_queryset(self, request):
        return super().get_queryset(request).select_related('user')


@admin.register(WeeklyStats)
class WeeklyStatsAdmin(admin.ModelAdmin):
    """
    Admin interface for WeeklyStats model
    """
    list_display = (
        'user', 'week_start_date', 'week_end_date', 'active_days',
        'total_work_minutes', 'total_breaks_taken', 'weekly_compliance_rate',
        'weekly_productivity_score'
    )
    list_filter = ('week_start_date', 'active_days')
    search_fields = ('user__email', 'user__username')
    readonly_fields = ('created_at', 'updated_at')
    date_hierarchy = 'week_start_date'
    
    fieldsets = (
        ('User & Period', {
            'fields': ('user', 'week_start_date', 'week_end_date', 'active_days')
        }),
        ('Work Statistics', {
            'fields': (
                'total_work_minutes', 'total_intervals_completed', 
                'total_sessions'
            )
        }),
        ('Averages', {
            'fields': (
                'average_daily_work_minutes', 'average_daily_breaks'
            )
        }),
        ('Performance', {
            'fields': (
                'total_breaks_compliant', 'weekly_compliance_rate',
                'weekly_productivity_score'
            )
        }),
        ('Timestamps', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )


@admin.register(MonthlyStats)
class MonthlyStatsAdmin(admin.ModelAdmin):
    """
    Admin interface for MonthlyStats model
    """
    list_display = (
        'user', 'year', 'month', 'active_days', 'total_work_minutes',
        'most_productive_day_of_week', 'goal_achieved',
        'estimated_eye_strain_reduction'
    )
    list_filter = ('year', 'month', 'goal_achieved', 'most_productive_day_of_week')
    search_fields = ('user__email', 'user__username')
    readonly_fields = ('created_at', 'updated_at')
    
    fieldsets = (
        ('User & Period', {
            'fields': ('user', 'year', 'month', 'active_days')
        }),
        ('Work Statistics', {
            'fields': (
                'total_work_minutes', 'total_intervals_completed', 
                'total_sessions'
            )
        }),
        ('Patterns', {
            'fields': (
                'most_productive_day_of_week', 'most_productive_hour'
            )
        }),
        ('Goals & Health', {
            'fields': (
                'monthly_goal_minutes', 'goal_achieved',
                'estimated_eye_strain_reduction'
            )
        }),
        ('Timestamps', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )


@admin.register(UserBehaviorEvent)
class UserBehaviorEventAdmin(admin.ModelAdmin):
    """
    Admin interface for UserBehaviorEvent model
    """
    list_display = (
        'user', 'event_type', 'timestamp', 'session_id', 'ip_address'
    )
    list_filter = ('event_type', 'timestamp')
    search_fields = ('user__email', 'event_type', 'session_id')
    readonly_fields = ('timestamp',)
    date_hierarchy = 'timestamp'
    
    fieldsets = (
        ('Event Details', {
            'fields': ('user', 'event_type', 'timestamp', 'event_data')
        }),
        ('Context', {
            'fields': ('session_id', 'user_agent', 'ip_address')
        }),
    )
    
    def has_add_permission(self, request):
        return False  # Events are created programmatically
    
    def has_change_permission(self, request, obj=None):
        return False  # Events should not be modified


@admin.register(EngagementMetrics)
class EngagementMetricsAdmin(admin.ModelAdmin):
    """
    Admin interface for EngagementMetrics model
    """
    list_display = (
        'user', 'date', 'daily_active', 'session_duration_minutes',
        'pages_visited', 'features_used', 'risk_of_churn_display'
    )
    list_filter = ('daily_active', 'date')
    search_fields = ('user__email', 'user__username')
    readonly_fields = ('created_at', 'days_since_last_active')
    date_hierarchy = 'date'
    
    fieldsets = (
        ('User & Date', {
            'fields': ('user', 'date', 'daily_active')
        }),
        ('Engagement', {
            'fields': (
                'session_duration_minutes', 'pages_visited', 'features_used'
            )
        }),
        ('Interaction Quality', {
            'fields': (
                'breaks_interaction_score', 'settings_customization_score'
            )
        }),
        ('Retention', {
            'fields': (
                'days_since_last_active', 'risk_of_churn'
            )
        }),
        ('Timestamp', {
            'fields': ('created_at',)
        }),
    )
    
    def risk_of_churn_display(self, obj):
        if obj.risk_of_churn > 0.7:
            return format_html('<span style="color: red;">High Risk</span>')
        elif obj.risk_of_churn > 0.4:
            return format_html('<span style="color: orange;">Medium Risk</span>')
        return format_html('<span style="color: green;">Low Risk</span>')
    risk_of_churn_display.short_description = 'Churn Risk'