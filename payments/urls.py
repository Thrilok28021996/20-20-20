from django.urls import path
from . import views

app_name = 'payments'

urlpatterns = [
    # Stripe payments
    path('upgrade/', views.upgrade_to_premium_view, name='upgrade_premium'),
    path('create-checkout-session/', views.create_checkout_session_view, name='create_checkout_session'),
    path('success/', views.subscription_success_view, name='subscription_success'),
    path('cancelled/', views.subscription_cancelled_view, name='subscription_cancelled'),
    path('manage/', views.manage_subscription_view, name='manage_subscription'),
    path('cancel/', views.cancel_subscription_view, name='cancel_subscription'),
    path('reactivate/', views.reactivate_subscription_view, name='reactivate_subscription'),
    path('stripe/webhook/', views.stripe_webhook_view, name='stripe_webhook'),
    
    # PayPal payments
    path('upgrade-paypal/', views.upgrade_to_premium_paypal_view, name='upgrade_premium_paypal'),
    path('paypal-success/', views.paypal_subscription_success_view, name='paypal_success'),
    path('manage-paypal/', views.manage_paypal_subscription_view, name='manage_paypal_subscription'),
    path('paypal/ipn/', views.paypal_ipn_view, name='paypal_ipn'),
]