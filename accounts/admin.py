from django.contrib import admin
from django.contrib.auth.admin import UserAdmin
from django.utils.html import format_html
from .models import User, UserProfile


@admin.register(User)
class CustomUserAdmin(UserAdmin):
    """
    Custom admin interface for User model
    """
    list_display = (
        'email', 'username', 'first_name', 'last_name', 
        'subscription_type', 'is_verified', 'is_active', 
        'date_joined', 'subscription_status'
    )
    list_filter = (
        'subscription_type', 'is_verified', 'is_active', 
        'email_notifications', 'break_reminders', 'date_joined'
    )
    search_fields = ('email', 'username', 'first_name', 'last_name')
    ordering = ('-date_joined',)
    
    # Add subscription fields to the user form
    fieldsets = UserAdmin.fieldsets + (
        ('Subscription Info', {
            'fields': (
                'subscription_type', 'subscription_start_date', 
                'subscription_end_date', 'stripe_customer_id'
            )
        }),
        ('Notifications', {
            'fields': (
                'email_notifications', 'break_reminders', 
                'daily_summary', 'weekly_report'
            )
        }),
        ('Preferences', {
            'fields': (
                'work_start_time', 'work_end_time', 
                'break_duration', 'reminder_sound'
            )
        }),
    )
    
    def subscription_status(self, obj):
        if obj.is_subscription_active:
            return format_html(
                '<span style="color: green;">Active</span>'
            )
        return format_html(
            '<span style="color: red;">Inactive</span>'
        )
    subscription_status.short_description = 'Subscription Status'
    
    actions = ['make_pro_users', 'send_welcome_email']
    
    def make_pro_users(self, request, queryset):
        updated = queryset.update(subscription_type='premium')
        self.message_user(request, f'{updated} users upgraded to Premium.')
    make_pro_users.short_description = "Upgrade selected users to Premium"


@admin.register(UserProfile)
class UserProfileAdmin(admin.ModelAdmin):
    """
    Admin interface for UserProfile model
    """
    list_display = (
        'user', 'occupation', 'daily_screen_time_hours',
        'total_breaks_taken', 'current_streak_days', 
        'longest_streak_days', 'updated_at'
    )
    list_filter = (
        'wears_glasses', 'has_eye_strain', 'occupation',
        'daily_screen_time_hours'
    )
    search_fields = ('user__email', 'user__username', 'occupation')
    readonly_fields = ('created_at', 'updated_at', 'total_breaks_taken')
    
    fieldsets = (
        ('User', {
            'fields': ('user',)
        }),
        ('Demographics', {
            'fields': ('age', 'occupation', 'daily_screen_time_hours')
        }),
        ('Eye Health', {
            'fields': ('wears_glasses', 'has_eye_strain', 'last_eye_checkup')
        }),
        ('Statistics', {
            'fields': (
                'total_breaks_taken', 'total_screen_time_minutes',
                'longest_streak_days', 'current_streak_days'
            )
        }),
        ('Settings', {
            'fields': ('timezone', 'preferred_language')
        }),
        ('Timestamps', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )