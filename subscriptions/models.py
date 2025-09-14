from django.db import models
from django.conf import settings
from django.utils import timezone
from decimal import Decimal


class SubscriptionPlan(models.Model):
    """
    Different subscription plans available
    """
    name = models.CharField(max_length=100)
    slug = models.SlugField(unique=True)
    description = models.TextField()
    
    # Pricing
    price = models.DecimalField(max_digits=10, decimal_places=2)
    currency = models.CharField(max_length=3, default='USD')
    
    # Billing
    BILLING_PERIODS = [
        ('monthly', 'Monthly'),
        ('yearly', 'Yearly'),
        ('lifetime', 'Lifetime'),
    ]
    billing_period = models.CharField(max_length=20, choices=BILLING_PERIODS)
    
    # Features
    max_daily_sessions = models.PositiveIntegerField(default=0)  # 0 = unlimited
    advanced_analytics = models.BooleanField(default=False)
    custom_break_messages = models.BooleanField(default=False)
    priority_support = models.BooleanField(default=False)
    api_access = models.BooleanField(default=False)
    white_labeling = models.BooleanField(default=False)
    team_management = models.BooleanField(default=False)
    
    # Stripe integration
    stripe_price_id = models.CharField(max_length=100, blank=True)
    stripe_product_id = models.CharField(max_length=100, blank=True)
    
    # Plan status
    is_active = models.BooleanField(default=True)
    is_featured = models.BooleanField(default=False)
    sort_order = models.PositiveIntegerField(default=0)
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        db_table = 'subscriptions_plan'
        verbose_name = 'Subscription Plan'
        verbose_name_plural = 'Subscription Plans'
        ordering = ['sort_order', 'price']
    
    def __str__(self):
        return f"{self.name} - {self.price} {self.currency}/{self.billing_period}"
    
    @property
    def monthly_price(self):
        """Convert price to monthly equivalent for comparison"""
        if self.billing_period == 'yearly':
            return self.price / 12
        return self.price


class UserSubscription(models.Model):
    """
    User's current subscription
    """
    user = models.OneToOneField(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='subscription')
    plan = models.ForeignKey(SubscriptionPlan, on_delete=models.CASCADE, related_name='subscriptions')
    
    # Subscription status
    STATUS_CHOICES = [
        ('trialing', 'Trial Period'),
        ('active', 'Active'),
        ('past_due', 'Past Due'),
        ('canceled', 'Canceled'),
        ('unpaid', 'Unpaid'),
        ('incomplete', 'Incomplete'),
        ('incomplete_expired', 'Incomplete Expired'),
        ('paused', 'Paused'),
    ]
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='trialing')
    
    # Subscription periods
    start_date = models.DateTimeField(default=timezone.now)
    end_date = models.DateTimeField(null=True, blank=True)
    trial_end = models.DateTimeField(null=True, blank=True)
    current_period_start = models.DateTimeField(default=timezone.now)
    current_period_end = models.DateTimeField()
    
    # Billing
    cancel_at_period_end = models.BooleanField(default=False)
    canceled_at = models.DateTimeField(null=True, blank=True)
    
    # Stripe integration
    stripe_subscription_id = models.CharField(max_length=100, blank=True)
    stripe_customer_id = models.CharField(max_length=100, blank=True)
    
    # Usage tracking
    sessions_this_period = models.PositiveIntegerField(default=0)
    api_calls_this_period = models.PositiveIntegerField(default=0)
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        db_table = 'subscriptions_user_subscription'
        verbose_name = 'User Subscription'
        verbose_name_plural = 'User Subscriptions'
    
    def __str__(self):
        return f"{self.user.email} - {self.plan.name} ({self.status})"
    
    @property
    def is_active(self):
        return self.status in ['trialing', 'active'] and self.current_period_end > timezone.now()
    
    @property
    def is_trial(self):
        return self.status == 'trialing' and self.trial_end and self.trial_end > timezone.now()
    
    @property
    def days_remaining(self):
        if self.current_period_end:
            return (self.current_period_end - timezone.now()).days
        return 0
    
    def cancel_subscription(self):
        """Mark subscription for cancellation at period end"""
        self.cancel_at_period_end = True
        self.canceled_at = timezone.now()
        self.save()


class PaymentMethod(models.Model):
    """
    User's payment methods
    """
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='payment_methods')
    
    # Payment method details
    stripe_payment_method_id = models.CharField(max_length=100)
    
    # Card details (for display purposes)
    card_brand = models.CharField(max_length=20, blank=True)  # visa, mastercard, etc.
    card_last4 = models.CharField(max_length=4, blank=True)
    card_exp_month = models.PositiveIntegerField(null=True, blank=True)
    card_exp_year = models.PositiveIntegerField(null=True, blank=True)
    
    # Status
    is_default = models.BooleanField(default=False)
    is_active = models.BooleanField(default=True)
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        db_table = 'subscriptions_payment_method'
        verbose_name = 'Payment Method'
        verbose_name_plural = 'Payment Methods'
    
    def __str__(self):
        return f"{self.user.email} - {self.card_brand} ****{self.card_last4}"


class Invoice(models.Model):
    """
    Subscription invoices
    """
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='invoices')
    subscription = models.ForeignKey(UserSubscription, on_delete=models.CASCADE, related_name='invoices')
    
    # Invoice details
    invoice_number = models.CharField(max_length=100, unique=True)
    stripe_invoice_id = models.CharField(max_length=100, blank=True)
    
    # Amounts
    subtotal = models.DecimalField(max_digits=10, decimal_places=2)
    tax_amount = models.DecimalField(max_digits=10, decimal_places=2, default=Decimal('0.00'))
    total = models.DecimalField(max_digits=10, decimal_places=2)
    amount_paid = models.DecimalField(max_digits=10, decimal_places=2, default=Decimal('0.00'))
    currency = models.CharField(max_length=3, default='USD')
    
    # Status
    STATUS_CHOICES = [
        ('draft', 'Draft'),
        ('open', 'Open'),
        ('paid', 'Paid'),
        ('void', 'Void'),
        ('uncollectible', 'Uncollectible'),
    ]
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='draft')
    
    # Dates
    created_date = models.DateTimeField(default=timezone.now)
    due_date = models.DateTimeField()
    paid_at = models.DateTimeField(null=True, blank=True)
    
    # Period covered
    period_start = models.DateTimeField()
    period_end = models.DateTimeField()
    
    # PDF
    pdf_url = models.URLField(blank=True)
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        db_table = 'subscriptions_invoice'
        verbose_name = 'Invoice'
        verbose_name_plural = 'Invoices'
        ordering = ['-created_date']
    
    def __str__(self):
        return f"Invoice {self.invoice_number} - {self.user.email}"
    
    @property
    def is_overdue(self):
        return self.status == 'open' and self.due_date < timezone.now()


class SubscriptionEvent(models.Model):
    """
    Track subscription lifecycle events
    """
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='subscription_events')
    subscription = models.ForeignKey(UserSubscription, on_delete=models.CASCADE, related_name='events', null=True, blank=True)
    
    # Event details
    EVENT_TYPES = [
        ('subscription_created', 'Subscription Created'),
        ('trial_started', 'Trial Started'),
        ('trial_ending', 'Trial Ending Soon'),
        ('trial_ended', 'Trial Ended'),
        ('subscription_activated', 'Subscription Activated'),
        ('payment_succeeded', 'Payment Succeeded'),
        ('payment_failed', 'Payment Failed'),
        ('subscription_upgraded', 'Subscription Upgraded'),
        ('subscription_downgraded', 'Subscription Downgraded'),
        ('subscription_canceled', 'Subscription Canceled'),
        ('subscription_reactivated', 'Subscription Reactivated'),
        ('invoice_created', 'Invoice Created'),
        ('invoice_paid', 'Invoice Paid'),
        ('card_updated', 'Payment Method Updated'),
    ]
    event_type = models.CharField(max_length=30, choices=EVENT_TYPES)
    
    # Event data
    event_data = models.JSONField(default=dict, blank=True)
    
    # Source
    source = models.CharField(max_length=50, default='system')  # system, stripe, manual, etc.
    
    timestamp = models.DateTimeField(default=timezone.now)
    
    class Meta:
        db_table = 'subscriptions_event'
        verbose_name = 'Subscription Event'
        verbose_name_plural = 'Subscription Events'
        ordering = ['-timestamp']
        indexes = [
            models.Index(fields=['user', 'event_type']),
            models.Index(fields=['timestamp']),
        ]
    
    def __str__(self):
        return f"{self.user.email} - {self.get_event_type_display()}"


class SubscriptionUsage(models.Model):
    """
    Track usage for metered billing or limits
    """
    subscription = models.ForeignKey(UserSubscription, on_delete=models.CASCADE, related_name='usage_records')
    
    # Usage period
    period_start = models.DateTimeField()
    period_end = models.DateTimeField()
    
    # Usage metrics
    sessions_count = models.PositiveIntegerField(default=0)
    total_work_minutes = models.PositiveIntegerField(default=0)
    api_calls = models.PositiveIntegerField(default=0)
    
    # Usage by feature
    advanced_analytics_views = models.PositiveIntegerField(default=0)
    custom_messages_sent = models.PositiveIntegerField(default=0)
    
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        db_table = 'subscriptions_usage'
        verbose_name = 'Subscription Usage'
        verbose_name_plural = 'Subscription Usage Records'
        unique_together = ['subscription', 'period_start']
        ordering = ['-period_start']
    
    def __str__(self):
        return f"Usage - {self.subscription.user.email} - {self.period_start.date()}"