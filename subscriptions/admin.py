from django.contrib import admin
from django.utils.html import format_html
from django.urls import reverse
from django.utils.safestring import mark_safe
from .models import (
    SubscriptionPlan, UserSubscription, PaymentMethod,
    Invoice, SubscriptionEvent, SubscriptionUsage
)


@admin.register(SubscriptionPlan)
class SubscriptionPlanAdmin(admin.ModelAdmin):
    """
    Admin interface for SubscriptionPlan model
    """
    list_display = (
        'name', 'price', 'currency', 'billing_period',
        'is_active', 'is_featured', 'subscription_count'
    )
    list_filter = ('billing_period', 'is_active', 'is_featured', 'currency')
    search_fields = ('name', 'description')
    readonly_fields = ('created_at', 'updated_at', 'subscription_count')
    prepopulated_fields = {'slug': ('name',)}
    
    fieldsets = (
        ('Plan Details', {
            'fields': ('name', 'slug', 'description', 'sort_order')
        }),
        ('Pricing', {
            'fields': ('price', 'currency', 'billing_period')
        }),
        ('Features', {
            'fields': (
                'max_daily_sessions', 'advanced_analytics', 'custom_break_messages',
                'priority_support', 'api_access', 'white_labeling', 'team_management'
            )
        }),
        ('Stripe Integration', {
            'fields': ('stripe_price_id', 'stripe_product_id')
        }),
        ('Status', {
            'fields': ('is_active', 'is_featured')
        }),
        ('Timestamps', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )
    
    def subscription_count(self, obj):
        count = obj.subscriptions.filter(status__in=['active', 'trialing']).count()
        return count
    subscription_count.short_description = 'Active Subscriptions'


class SubscriptionEventInline(admin.TabularInline):
    model = SubscriptionEvent
    extra = 0
    readonly_fields = ('timestamp',)
    fields = ('event_type', 'source', 'timestamp')


@admin.register(UserSubscription)
class UserSubscriptionAdmin(admin.ModelAdmin):
    """
    Admin interface for UserSubscription model
    """
    list_display = (
        'user', 'plan', 'status', 'start_date', 'current_period_end',
        'days_remaining', 'cancel_at_period_end'
    )
    list_filter = (
        'status', 'plan', 'cancel_at_period_end', 'start_date'
    )
    search_fields = ('user__email', 'user__username', 'stripe_subscription_id')
    readonly_fields = (
        'created_at', 'updated_at', 'days_remaining', 'is_active', 'is_trial'
    )
    date_hierarchy = 'start_date'
    
    inlines = [SubscriptionEventInline]
    
    fieldsets = (
        ('Subscription Details', {
            'fields': ('user', 'plan', 'status')
        }),
        ('Period', {
            'fields': (
                'start_date', 'end_date', 'trial_end',
                'current_period_start', 'current_period_end', 'days_remaining'
            )
        }),
        ('Cancellation', {
            'fields': ('cancel_at_period_end', 'canceled_at')
        }),
        ('Stripe Integration', {
            'fields': ('stripe_subscription_id', 'stripe_customer_id')
        }),
        ('Usage Tracking', {
            'fields': ('sessions_this_period', 'api_calls_this_period')
        }),
        ('Status Info', {
            'fields': ('is_active', 'is_trial')
        }),
        ('Timestamps', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )
    
    actions = ['cancel_subscriptions', 'reactivate_subscriptions']
    
    def cancel_subscriptions(self, request, queryset):
        for subscription in queryset:
            subscription.cancel_subscription()
        self.message_user(request, f'{queryset.count()} subscriptions marked for cancellation.')
    cancel_subscriptions.short_description = "Cancel selected subscriptions"
    
    def reactivate_subscriptions(self, request, queryset):
        updated = queryset.update(cancel_at_period_end=False)
        self.message_user(request, f'{updated} subscriptions reactivated.')
    reactivate_subscriptions.short_description = "Reactivate selected subscriptions"


@admin.register(PaymentMethod)
class PaymentMethodAdmin(admin.ModelAdmin):
    """
    Admin interface for PaymentMethod model
    """
    list_display = (
        'user', 'card_brand', 'card_last4', 'card_exp_month',
        'card_exp_year', 'is_default', 'is_active'
    )
    list_filter = ('card_brand', 'is_default', 'is_active', 'card_exp_year')
    search_fields = ('user__email', 'card_last4', 'stripe_payment_method_id')
    readonly_fields = ('created_at', 'updated_at')
    
    fieldsets = (
        ('User', {
            'fields': ('user',)
        }),
        ('Card Details', {
            'fields': (
                'card_brand', 'card_last4', 'card_exp_month', 'card_exp_year'
            )
        }),
        ('Stripe', {
            'fields': ('stripe_payment_method_id',)
        }),
        ('Status', {
            'fields': ('is_default', 'is_active')
        }),
        ('Timestamps', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )


@admin.register(Invoice)
class InvoiceAdmin(admin.ModelAdmin):
    """
    Admin interface for Invoice model
    """
    list_display = (
        'invoice_number', 'user', 'subscription', 'total',
        'status', 'created_date', 'due_date', 'is_overdue'
    )
    list_filter = ('status', 'currency', 'created_date', 'due_date')
    search_fields = ('invoice_number', 'user__email', 'stripe_invoice_id')
    readonly_fields = (
        'created_at', 'updated_at', 'is_overdue', 'invoice_link'
    )
    date_hierarchy = 'created_date'
    
    fieldsets = (
        ('Invoice Details', {
            'fields': ('user', 'subscription', 'invoice_number', 'stripe_invoice_id')
        }),
        ('Amounts', {
            'fields': ('subtotal', 'tax_amount', 'total', 'amount_paid', 'currency')
        }),
        ('Status', {
            'fields': ('status', 'is_overdue')
        }),
        ('Dates', {
            'fields': ('created_date', 'due_date', 'paid_at')
        }),
        ('Period', {
            'fields': ('period_start', 'period_end')
        }),
        ('PDF', {
            'fields': ('pdf_url', 'invoice_link')
        }),
        ('Timestamps', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )
    
    def invoice_link(self, obj):
        if obj.pdf_url:
            return format_html(
                '<a href="{}" target="_blank">View PDF</a>',
                obj.pdf_url
            )
        return '-'
    invoice_link.short_description = 'PDF Link'


@admin.register(SubscriptionEvent)
class SubscriptionEventAdmin(admin.ModelAdmin):
    """
    Admin interface for SubscriptionEvent model
    """
    list_display = (
        'user', 'event_type', 'source', 'timestamp'
    )
    list_filter = ('event_type', 'source', 'timestamp')
    search_fields = ('user__email', 'event_type')
    readonly_fields = ('timestamp',)
    date_hierarchy = 'timestamp'
    
    fieldsets = (
        ('Event Details', {
            'fields': ('user', 'subscription', 'event_type', 'source')
        }),
        ('Data', {
            'fields': ('event_data',)
        }),
        ('Timestamp', {
            'fields': ('timestamp',)
        }),
    )
    
    def has_add_permission(self, request):
        return False  # Events are created programmatically
    
    def has_change_permission(self, request, obj=None):
        return False  # Events should not be modified


@admin.register(SubscriptionUsage)
class SubscriptionUsageAdmin(admin.ModelAdmin):
    """
    Admin interface for SubscriptionUsage model
    """
    list_display = (
        'subscription', 'period_start', 'period_end',
        'sessions_count', 'total_work_minutes', 'api_calls'
    )
    list_filter = ('period_start',)
    search_fields = ('subscription__user__email',)
    readonly_fields = ('created_at',)
    date_hierarchy = 'period_start'
    
    fieldsets = (
        ('Subscription', {
            'fields': ('subscription',)
        }),
        ('Period', {
            'fields': ('period_start', 'period_end')
        }),
        ('Usage Metrics', {
            'fields': (
                'sessions_count', 'total_work_minutes', 'api_calls'
            )
        }),
        ('Feature Usage', {
            'fields': (
                'advanced_analytics_views', 'custom_messages_sent'
            )
        }),
        ('Timestamp', {
            'fields': ('created_at',)
        }),
    )