from django.db import models
from django.conf import settings
from django.utils import timezone


class StripeSubscription(models.Model):
    """
    Track Stripe subscription payments
    """
    SUBSCRIPTION_STATUS = [
        ('active', 'Active'),
        ('cancelled', 'Cancelled'),
        ('suspended', 'Suspended'),
        ('expired', 'Expired'),
        ('pending', 'Pending'),
    ]
    
    user = models.OneToOneField(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='stripe_subscription')
    
    # Stripe subscription details
    stripe_subscription_id = models.CharField(max_length=100, unique=True, null=True, blank=True)
    stripe_customer_id = models.CharField(max_length=100, blank=True)
    stripe_payment_method_id = models.CharField(max_length=100, blank=True)
    
    # Subscription details
    amount = models.DecimalField(max_digits=10, decimal_places=2, default=0.99)
    currency = models.CharField(max_length=3, default='USD')
    status = models.CharField(max_length=20, choices=SUBSCRIPTION_STATUS, default='pending')
    
    # Dates
    created_at = models.DateTimeField(auto_now_add=True)
    activated_at = models.DateTimeField(null=True, blank=True)
    next_payment_date = models.DateTimeField(null=True, blank=True)
    cancelled_at = models.DateTimeField(null=True, blank=True)
    
    # Stripe webhook tracking
    last_event_id = models.CharField(max_length=255, blank=True)
    last_payment_date = models.DateTimeField(null=True, blank=True)
    
    # Card details (for display purposes)
    card_brand = models.CharField(max_length=20, blank=True)  # visa, mastercard, etc.
    card_last4 = models.CharField(max_length=4, blank=True)
    card_exp_month = models.PositiveIntegerField(null=True, blank=True)
    card_exp_year = models.PositiveIntegerField(null=True, blank=True)
    
    class Meta:
        db_table = 'payments_stripe_subscription'
        verbose_name = 'Stripe Subscription'
        verbose_name_plural = 'Stripe Subscriptions'
    
    def __str__(self):
        return f"{self.user.email} - {self.status} (${self.amount}/month)"
    
    @property
    def is_active(self):
        return self.status == 'active'
    
    def activate_subscription(self):
        """Activate the subscription"""
        self.status = 'active'
        self.activated_at = timezone.now()
        self.save()
        
        # Update user subscription type
        self.user.subscription_type = 'premium'
        self.user.subscription_start_date = timezone.now()
        self.user.save()
    
    def cancel_subscription(self):
        """Cancel the subscription"""
        self.status = 'cancelled'
        self.cancelled_at = timezone.now()
        self.save()
        
        # Revert user to free plan
        self.user.subscription_type = 'free'
        self.user.subscription_end_date = timezone.now()
        self.user.save()


class StripePayment(models.Model):
    """
    Track individual Stripe payments
    """
    PAYMENT_STATUS = [
        ('completed', 'Completed'),
        ('pending', 'Pending'),
        ('failed', 'Failed'),
        ('cancelled', 'Cancelled'),
        ('refunded', 'Refunded'),
    ]
    
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='stripe_payments')
    subscription = models.ForeignKey(StripeSubscription, on_delete=models.CASCADE, related_name='payments', null=True, blank=True)
    
    # Payment details
    stripe_payment_intent_id = models.CharField(max_length=100, unique=True)
    payment_status = models.CharField(max_length=20, choices=PAYMENT_STATUS)
    amount = models.DecimalField(max_digits=10, decimal_places=2)
    currency = models.CharField(max_length=3, default='USD')
    
    # Stripe specific fields
    stripe_customer_id = models.CharField(max_length=100, blank=True)
    stripe_invoice_id = models.CharField(max_length=100, blank=True)
    
    # Card details
    card_brand = models.CharField(max_length=20, blank=True)
    card_last4 = models.CharField(max_length=4, blank=True)
    
    # Webhook data
    stripe_event_id = models.CharField(max_length=255, blank=True)
    payment_date = models.DateTimeField()
    
    # Metadata
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        db_table = 'payments_stripe_payment'
        verbose_name = 'Stripe Payment'
        verbose_name_plural = 'Stripe Payments'
        ordering = ['-payment_date']
    
    def __str__(self):
        return f"Payment {self.stripe_payment_intent_id} - {self.user.email} - ${self.amount}"


class PayPalSubscription(models.Model):
    """
    Track PayPal subscription payments
    """
    SUBSCRIPTION_STATUS = [
        ('active', 'Active'),
        ('cancelled', 'Cancelled'),
        ('suspended', 'Suspended'),
        ('expired', 'Expired'),
        ('pending', 'Pending'),
    ]
    
    user = models.OneToOneField(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='paypal_subscription')
    
    # PayPal subscription details
    paypal_subscription_id = models.CharField(max_length=100, unique=True, null=True, blank=True)
    paypal_payer_id = models.CharField(max_length=100, blank=True)
    paypal_payer_email = models.EmailField(blank=True)
    
    # Subscription details
    amount = models.DecimalField(max_digits=10, decimal_places=2, default=0.99)
    currency = models.CharField(max_length=3, default='USD')
    status = models.CharField(max_length=20, choices=SUBSCRIPTION_STATUS, default='pending')
    
    # Dates
    created_at = models.DateTimeField(auto_now_add=True)
    activated_at = models.DateTimeField(null=True, blank=True)
    next_payment_date = models.DateTimeField(null=True, blank=True)
    cancelled_at = models.DateTimeField(null=True, blank=True)
    
    # PayPal IPN tracking
    ipn_track_id = models.CharField(max_length=255, blank=True)
    last_payment_date = models.DateTimeField(null=True, blank=True)
    
    class Meta:
        db_table = 'payments_paypal_subscription'
        verbose_name = 'PayPal Subscription'
        verbose_name_plural = 'PayPal Subscriptions'
    
    def __str__(self):
        return f"{self.user.email} - PayPal {self.status} (${self.amount}/month)"
    
    @property
    def is_active(self):
        return self.status == 'active'
    
    def activate_subscription(self):
        """Activate the subscription"""
        self.status = 'active'
        self.activated_at = timezone.now()
        self.save()
        
        # Update user subscription type
        self.user.subscription_type = 'premium'
        self.user.subscription_start_date = timezone.now()
        self.user.save()
    
    def cancel_subscription(self):
        """Cancel the subscription"""
        self.status = 'cancelled'
        self.cancelled_at = timezone.now()
        self.save()
        
        # Revert user to free plan
        self.user.subscription_type = 'free'
        self.user.subscription_end_date = timezone.now()
        self.user.save()


class PayPalPayment(models.Model):
    """
    Track individual PayPal payments
    """
    PAYMENT_STATUS = [
        ('completed', 'Completed'),
        ('pending', 'Pending'),
        ('failed', 'Failed'),
        ('cancelled', 'Cancelled'),
        ('refunded', 'Refunded'),
    ]
    
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='paypal_payments')
    subscription = models.ForeignKey(PayPalSubscription, on_delete=models.CASCADE, related_name='payments', null=True, blank=True)
    
    # Payment details
    paypal_transaction_id = models.CharField(max_length=100, unique=True)
    payment_status = models.CharField(max_length=20, choices=PAYMENT_STATUS)
    amount = models.DecimalField(max_digits=10, decimal_places=2)
    currency = models.CharField(max_length=3, default='USD')
    
    # PayPal specific fields
    paypal_payer_id = models.CharField(max_length=100, blank=True)
    paypal_payer_email = models.EmailField(blank=True)
    paypal_receiver_email = models.EmailField(blank=True)
    
    # IPN data
    ipn_track_id = models.CharField(max_length=255, blank=True)
    payment_date = models.DateTimeField()
    
    # Metadata
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        db_table = 'payments_paypal_payment'
        verbose_name = 'PayPal Payment'
        verbose_name_plural = 'PayPal Payments'
        ordering = ['-payment_date']
    
    def __str__(self):
        return f"PayPal Payment {self.paypal_transaction_id} - {self.user.email} - ${self.amount}"