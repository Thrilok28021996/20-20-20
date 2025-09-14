from django.shortcuts import render, redirect
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.conf import settings
from django.urls import reverse
from django.views.decorators.csrf import csrf_exempt, ensure_csrf_cookie
from django.views.decorators.http import require_POST
from django.http import JsonResponse, HttpResponse
from django.utils import timezone
from django.core.exceptions import PermissionDenied, ValidationError
from django.middleware.csrf import get_token
from django_ratelimit.decorators import ratelimit
import logging
import stripe
import json
import bleach

from .models import StripeSubscription, StripePayment, PayPalSubscription, PayPalPayment

logger = logging.getLogger(__name__)
stripe.api_key = getattr(settings, 'STRIPE_SECRET_KEY', '')

@login_required
def upgrade_to_premium_view(request):
    """
    Stripe subscription upgrade page
    """
    # Check if user already has active subscription
    try:
        existing_subscription = StripeSubscription.objects.get(user=request.user)
        if existing_subscription.is_active:
            messages.info(request, 'You already have an active Premium subscription.')
            return redirect('timer:dashboard')
    except StripeSubscription.DoesNotExist:
        pass
    
    context = {
        'stripe_public_key': getattr(settings, 'STRIPE_PUBLISHABLE_KEY', ''),
        'price_id': getattr(settings, 'STRIPE_PRICE_ID', ''),  # Your Stripe price ID for $0.99/month
    }
    
    return render(request, 'payments/upgrade_premium.html', context)


@login_required
@ratelimit(key='user', rate='5/m', method='POST')
@require_POST
@ensure_csrf_cookie
def create_checkout_session_view(request):
    """
    Create Stripe Checkout Session for subscription
    """
    if request.method == 'POST':
        try:
            # Check if user already has active subscription
            try:
                existing_subscription = StripeSubscription.objects.get(user=request.user)
                if existing_subscription.is_active:
                    return JsonResponse({
                        'error': 'You already have an active Premium subscription.'
                    })
            except StripeSubscription.DoesNotExist:
                pass
            
            # Create or get Stripe customer
            stripe_customer = None
            if request.user.stripe_customer_id:
                try:
                    stripe_customer = stripe.Customer.retrieve(request.user.stripe_customer_id)
                except stripe.error.InvalidRequestError:
                    stripe_customer = None
            
            if not stripe_customer:
                stripe_customer = stripe.Customer.create(
                    email=request.user.email,
                    name=request.user.get_full_name(),
                )
                # Save customer ID to user
                request.user.stripe_customer_id = stripe_customer.id
                request.user.save()
            
            # Create checkout session
            checkout_session = stripe.checkout.Session.create(
                customer=stripe_customer.id,
                payment_method_types=['card'],
                line_items=[{
                    'price': getattr(settings, 'STRIPE_PRICE_ID', ''),  # Your $0.99/month price ID
                    'quantity': 1,
                }],
                mode='subscription',
                success_url=request.build_absolute_uri(reverse('payments:subscription_success')) + '?session_id={CHECKOUT_SESSION_ID}',
                cancel_url=request.build_absolute_uri(reverse('payments:subscription_cancelled')),
                metadata={
                    'user_id': request.user.id,
                }
            )
            
            return JsonResponse({
                'checkout_session_id': checkout_session.id
            })
            
        except Exception as e:
            logger.error(f"Error creating checkout session: {e}")
            return JsonResponse({
                'error': 'Unable to create checkout session. Please try again.'
            })
    
    return JsonResponse({'error': 'Invalid request method'})


@login_required
def subscription_success_view(request):
    """
    Stripe subscription success page
    """
    session_id = request.GET.get('session_id')
    
    if session_id:
        try:
            # Retrieve the checkout session
            session = stripe.checkout.Session.retrieve(session_id)
            
            if session.payment_status == 'paid':
                # Get subscription details
                subscription = stripe.Subscription.retrieve(session.subscription)
                
                # Create or update subscription record
                stripe_subscription, created = StripeSubscription.objects.get_or_create(
                    user=request.user,
                    defaults={
                        'stripe_subscription_id': subscription.id,
                        'stripe_customer_id': subscription.customer,
                        'status': 'active',
                        'activated_at': timezone.now(),
                        'amount': 0.99,
                    }
                )
                
                if created:
                    stripe_subscription.activate_subscription()
                
                messages.success(request, 'Your Premium subscription is now active! Welcome to Premium!')
            
        except Exception as e:
            logger.error(f"Error processing successful subscription: {e}")
            messages.warning(request, 'There was an issue confirming your subscription. Please contact support.')
    
    return render(request, 'payments/subscription_success.html')


@login_required
def subscription_cancelled_view(request):
    """
    Stripe subscription cancelled page
    """
    messages.warning(request, 'Subscription upgrade was cancelled. You can upgrade anytime from your dashboard.')
    return redirect('timer:dashboard')


@login_required
def manage_subscription_view(request):
    """
    Manage existing subscription (Stripe or PayPal)
    """
    stripe_subscription = None
    paypal_subscription = None
    recent_payments = []
    payment_method = None
    
    # Check for Stripe subscription with optimized query
    try:
        stripe_subscription = StripeSubscription.objects.select_related('user').get(user=request.user)
        if stripe_subscription.is_active:
            payment_method = 'Stripe'
            recent_payments = StripePayment.objects.select_related('user', 'subscription').filter(
                user=request.user
            ).order_by('-payment_date')[:10]
    except StripeSubscription.DoesNotExist:
        pass
    
    # Check for PayPal subscription with optimized query
    try:
        paypal_subscription = PayPalSubscription.objects.select_related('user').get(user=request.user)
        if paypal_subscription.is_active and not payment_method:  # Prefer active subscription
            payment_method = 'PayPal'
            recent_payments = PayPalPayment.objects.select_related('user', 'subscription').filter(
                user=request.user
            ).order_by('-payment_date')[:10]
        elif paypal_subscription.is_active and payment_method == 'Stripe':
            # User has both - show warning
            messages.warning(request, 'You have multiple active subscriptions. Please contact support to resolve this.')
    except PayPalSubscription.DoesNotExist:
        pass
    
    # Determine which subscription to show
    subscription = stripe_subscription if payment_method == 'Stripe' else paypal_subscription
    
    if not subscription:
        messages.error(request, 'No subscription found.')
        return redirect('accounts:pricing')
    
    # Get Stripe subscription details if needed
    stripe_subscription_data = None
    if payment_method == 'Stripe' and subscription.stripe_subscription_id:
        try:
            stripe_subscription_data = stripe.Subscription.retrieve(subscription.stripe_subscription_id)
        except Exception as e:
            logger.error(f"Error retrieving Stripe subscription: {e}")
    
    context = {
        'subscription': subscription,
        'recent_payments': recent_payments,
        'payment_method': payment_method,
        'stripe_subscription': stripe_subscription_data,
        'paypal_subscription': paypal_subscription,
        'stripe_subscription_obj': stripe_subscription,
    }
    
    return render(request, 'payments/manage_subscription.html', context)


@login_required
@ratelimit(key='user', rate='3/m', method='POST')
@require_POST
def cancel_subscription_view(request):
    """
    Cancel Stripe subscription
    """
    if request.method == 'POST':
        try:
            # Validate user owns the subscription
            subscription = StripeSubscription.objects.get(user=request.user)
            
            # Validate and sanitize input
            cancel_type = bleach.clean(request.POST.get('cancel_type', 'at_period_end'))
            if cancel_type not in ['immediately', 'at_period_end']:
                cancel_type = 'at_period_end'
            
            if subscription.stripe_subscription_id:
                if cancel_type == 'immediately':
                    # Cancel the subscription immediately
                    stripe.Subscription.cancel(subscription.stripe_subscription_id)
                    subscription.cancel_subscription()
                    messages.success(request, 'Your subscription has been cancelled immediately. You now have access to free features only.')
                else:
                    # Cancel the subscription at period end (default)
                    stripe.Subscription.modify(
                        subscription.stripe_subscription_id,
                        cancel_at_period_end=True
                    )
                    messages.success(request, 'Your subscription will be cancelled at the end of your billing period. You\'ll keep Premium access until then.')
                
            return redirect('payments:manage_subscription')
            
        except StripeSubscription.DoesNotExist:
            messages.error(request, 'No subscription found to cancel.')
        except Exception as e:
            logger.error(f"Error cancelling subscription: {e}")
            messages.error(request, 'Unable to cancel subscription. Please contact support.')
    
    return redirect('payments:manage_subscription')


@login_required
@ratelimit(key='user', rate='3/m', method='POST')
@require_POST
def reactivate_subscription_view(request):
    """
    Reactivate a cancelled Stripe subscription
    """
    if request.method == 'POST':
        try:
            # Validate user owns the subscription
            subscription = StripeSubscription.objects.get(user=request.user)
            
            if subscription.stripe_subscription_id and subscription.status == 'cancelled':
                # Try to reactivate the subscription in Stripe
                stripe.Subscription.modify(
                    subscription.stripe_subscription_id,
                    cancel_at_period_end=False
                )
                
                # Update local subscription status
                subscription.status = 'active'
                subscription.cancelled_at = None
                subscription.save()
                
                # Reactivate user premium status
                subscription.user.subscription_type = 'premium'
                subscription.user.save()
                
                messages.success(request, 'Your Premium subscription has been reactivated successfully!')
                
            else:
                messages.error(request, 'Unable to reactivate subscription. Please contact support.')
                
            return redirect('payments:manage_subscription')
            
        except StripeSubscription.DoesNotExist:
            messages.error(request, 'No subscription found to reactivate.')
        except Exception as e:
            logger.error(f"Error reactivating subscription: {e}")
            messages.error(request, 'Unable to reactivate subscription. Please contact support.')
    
    return redirect('payments:manage_subscription')


@csrf_exempt
@require_POST
def stripe_webhook_view(request):
    """
    Stripe webhook handler
    Handle subscription events from Stripe
    """
    payload = request.body
    sig_header = request.META.get('HTTP_STRIPE_SIGNATURE')
    endpoint_secret = getattr(settings, 'STRIPE_WEBHOOK_SECRET', '')
    
    try:
        event = stripe.Webhook.construct_event(
            payload, sig_header, endpoint_secret
        )
    except ValueError:
        logger.error("Invalid payload")
        return HttpResponse(status=400)
    except stripe.error.SignatureVerificationError:
        logger.error("Invalid signature")
        return HttpResponse(status=400)
    
    # Handle the event
    if event['type'] == 'customer.subscription.created':
        subscription = event['data']['object']
        handle_subscription_created(subscription)
        
    elif event['type'] == 'customer.subscription.updated':
        subscription = event['data']['object']
        handle_subscription_updated(subscription)
        
    elif event['type'] == 'customer.subscription.deleted':
        subscription = event['data']['object']
        handle_subscription_cancelled(subscription)
        
    elif event['type'] == 'invoice.payment_succeeded':
        invoice = event['data']['object']
        handle_payment_succeeded(invoice)
        
    elif event['type'] == 'invoice.payment_failed':
        invoice = event['data']['object']
        handle_payment_failed(invoice)
    
    else:
        logger.info(f'Unhandled event type: {event["type"]}')
    
    return HttpResponse(status=200)


def handle_subscription_created(stripe_subscription):
    """Handle subscription creation webhook"""
    try:
        # Find user by customer ID
        from django.contrib.auth import get_user_model
        User = get_user_model()
        user = User.objects.get(stripe_customer_id=stripe_subscription['customer'])
        
        # Create or update subscription record
        subscription, created = StripeSubscription.objects.get_or_create(
            user=user,
            defaults={
                'stripe_subscription_id': stripe_subscription['id'],
                'stripe_customer_id': stripe_subscription['customer'],
                'status': 'active' if stripe_subscription['status'] == 'active' else stripe_subscription['status'],
                'activated_at': timezone.now() if stripe_subscription['status'] == 'active' else None,
            }
        )
        
        if stripe_subscription['status'] == 'active':
            subscription.activate_subscription()
            
        logger.info(f"Created subscription for user {user.email}")
        
    except Exception as e:
        logger.error(f"Error handling subscription creation: {e}")


def handle_subscription_updated(stripe_subscription):
    """Handle subscription update webhook"""
    try:
        subscription = StripeSubscription.objects.get(
            stripe_subscription_id=stripe_subscription['id']
        )
        
        # Update status
        subscription.status = stripe_subscription['status']
        
        if stripe_subscription['status'] == 'active' and not subscription.activated_at:
            subscription.activate_subscription()
        elif stripe_subscription['cancel_at_period_end']:
            subscription.status = 'cancelled'
            subscription.cancelled_at = timezone.now()
            
        subscription.save()
        logger.info(f"Updated subscription {subscription.stripe_subscription_id}")
        
    except StripeSubscription.DoesNotExist:
        logger.error(f"Subscription not found: {stripe_subscription['id']}")


def handle_subscription_cancelled(stripe_subscription):
    """Handle subscription cancellation webhook"""
    try:
        subscription = StripeSubscription.objects.get(
            stripe_subscription_id=stripe_subscription['id']
        )
        subscription.cancel_subscription()
        logger.info(f"Cancelled subscription {subscription.stripe_subscription_id}")
        
    except StripeSubscription.DoesNotExist:
        logger.error(f"Subscription not found for cancellation: {stripe_subscription['id']}")


def handle_payment_succeeded(invoice):
    """Handle successful payment webhook"""
    try:
        if invoice['subscription']:
            subscription = StripeSubscription.objects.get(
                stripe_subscription_id=invoice['subscription']
            )
            
            # Create payment record
            StripePayment.objects.get_or_create(
                stripe_payment_intent_id=invoice['payment_intent'] or f"invoice_{invoice['id']}",
                defaults={
                    'user': subscription.user,
                    'subscription': subscription,
                    'payment_status': 'completed',
                    'amount': invoice['amount_paid'] / 100,  # Convert from cents
                    'currency': invoice['currency'].upper(),
                    'stripe_customer_id': invoice['customer'],
                    'stripe_invoice_id': invoice['id'],
                    'payment_date': timezone.now(),
                }
            )
            
            # Update subscription
            subscription.last_payment_date = timezone.now()
            subscription.save()
            
            logger.info(f"Recorded payment for subscription {subscription.stripe_subscription_id}")
            
    except Exception as e:
        logger.error(f"Error handling payment success: {e}")


def handle_payment_failed(invoice):
    """Handle failed payment webhook"""
    try:
        if invoice['subscription']:
            subscription = StripeSubscription.objects.get(
                stripe_subscription_id=invoice['subscription']
            )
            
            logger.info(f"Payment failed for subscription {subscription.stripe_subscription_id}")
            # Could send notification to user here
            
    except Exception as e:
        logger.error(f"Error handling payment failure: {e}")


# PayPal Payment Views
@login_required
def upgrade_to_premium_paypal_view(request):
    """
    PayPal subscription upgrade page
    """
    # Check if user already has active subscription
    try:
        existing_stripe_subscription = StripeSubscription.objects.get(user=request.user)
        if existing_stripe_subscription.is_active:
            messages.info(request, 'You already have an active Premium subscription.')
            return redirect('timer:dashboard')
    except StripeSubscription.DoesNotExist:
        pass
    
    try:
        existing_paypal_subscription = PayPalSubscription.objects.get(user=request.user)
        if existing_paypal_subscription.is_active:
            messages.info(request, 'You already have an active Premium subscription.')
            return redirect('timer:dashboard')
    except PayPalSubscription.DoesNotExist:
        pass
    
    # PayPal subscription button data
    paypal_dict = {
        "business": getattr(settings, 'PAYPAL_RECEIVER_EMAIL', ''),
        "cmd": "_xclick-subscriptions",
        "a3": "0.99",  # Monthly price
        "p3": 1,       # Duration of each unit (1 month)
        "t3": "M",     # Type of unit (M = month)
        "src": "1",    # Recurring payments
        "sra": "1",    # Reattempt on failure
        "no_note": "1",
        "item_name": "EyeHealth 20-20-20 Premium Subscription",
        "item_number": "premium_monthly_paypal",
        "custom": request.user.id,
        "currency_code": "USD",
        "return": request.build_absolute_uri(reverse('payments:paypal_success')),
        "cancel_return": request.build_absolute_uri(reverse('payments:subscription_cancelled')),
        "notify_url": request.build_absolute_uri(reverse('payments:paypal_ipn')),
    }
    
    context = {
        'paypal_dict': paypal_dict,
        'paypal_action_url': getattr(settings, 'PAYPAL_TEST', True) and "https://www.sandbox.paypal.com/cgi-bin/webscr" or "https://www.paypal.com/cgi-bin/webscr",
    }
    
    return render(request, 'payments/upgrade_premium_paypal.html', context)


@login_required
def paypal_subscription_success_view(request):
    """
    PayPal subscription success page
    """
    messages.success(request, 'Thank you! Your Premium subscription via PayPal is being activated. You\'ll receive email confirmation shortly.')
    return render(request, 'payments/subscription_success.html', {'payment_method': 'PayPal'})


@login_required
def manage_paypal_subscription_view(request):
    """
    Manage existing PayPal subscription
    """
    try:
        subscription = PayPalSubscription.objects.get(user=request.user)
    except PayPalSubscription.DoesNotExist:
        messages.error(request, 'No PayPal subscription found.')
        return redirect('accounts:pricing')
    
    # Get recent payments
    recent_payments = PayPalPayment.objects.filter(user=request.user).order_by('-payment_date')[:10]
    
    context = {
        'subscription': subscription,
        'recent_payments': recent_payments,
        'payment_method': 'PayPal',
    }
    
    return render(request, 'payments/manage_subscription.html', context)


@csrf_exempt
@require_POST
def paypal_ipn_view(request):
    """
    PayPal Instant Payment Notification (IPN) handler
    This is where PayPal sends subscription updates
    """
    try:
        # Get IPN data
        ipn_data = request.POST.copy()
        logger.info(f"PayPal IPN received: {ipn_data}")
        
        # In production, you would verify IPN with PayPal
        # For now, we'll process it directly
        
        txn_type = ipn_data.get('txn_type', '')
        payment_status = ipn_data.get('payment_status', '')
        subscr_id = ipn_data.get('subscr_id', '')
        
        # Handle subscription signup
        if txn_type == 'subscr_signup':
            custom = ipn_data.get('custom')
            if custom:
                try:
                    from django.contrib.auth import get_user_model
                    User = get_user_model()
                    user = User.objects.get(id=custom)
                    
                    subscription, created = PayPalSubscription.objects.get_or_create(
                        user=user,
                        defaults={
                            'paypal_subscription_id': subscr_id,
                            'paypal_payer_id': ipn_data.get('payer_id', ''),
                            'paypal_payer_email': ipn_data.get('payer_email', ''),
                            'amount': ipn_data.get('amount3', '0.99'),
                            'status': 'active',
                            'activated_at': timezone.now(),
                        }
                    )
                    
                    if created:
                        subscription.activate_subscription()
                        logger.info(f"Activated PayPal premium subscription for user {user.email}")
                        
                except Exception as e:
                    logger.error(f"Error processing PayPal subscription signup: {e}")
        
        # Handle successful payment
        elif txn_type == 'subscr_payment' and payment_status == 'Completed':
            txn_id = ipn_data.get('txn_id', '')
            
            try:
                subscription = PayPalSubscription.objects.get(paypal_subscription_id=subscr_id)
                
                # Create payment record
                PayPalPayment.objects.get_or_create(
                    paypal_transaction_id=txn_id,
                    defaults={
                        'user': subscription.user,
                        'subscription': subscription,
                        'payment_status': 'completed',
                        'amount': ipn_data.get('mc_gross', '0.99'),
                        'currency': ipn_data.get('mc_currency', 'USD'),
                        'paypal_payer_id': ipn_data.get('payer_id', ''),
                        'paypal_payer_email': ipn_data.get('payer_email', ''),
                        'paypal_receiver_email': ipn_data.get('receiver_email', ''),
                        'payment_date': timezone.now(),
                        'ipn_track_id': ipn_data.get('ipn_track_id', ''),
                    }
                )
                
                # Update subscription
                subscription.last_payment_date = timezone.now()
                subscription.save()
                
                logger.info(f"Recorded PayPal payment {txn_id} for subscription {subscr_id}")
                
            except PayPalSubscription.DoesNotExist:
                logger.error(f"PayPal subscription not found for ID: {subscr_id}")
        
        # Handle subscription cancellation
        elif txn_type == 'subscr_cancel':
            try:
                subscription = PayPalSubscription.objects.get(paypal_subscription_id=subscr_id)
                subscription.cancel_subscription()
                logger.info(f"Cancelled PayPal subscription {subscr_id}")
                
            except PayPalSubscription.DoesNotExist:
                logger.error(f"PayPal subscription not found for cancellation: {subscr_id}")
        
        return HttpResponse("OK")
        
    except Exception as e:
        logger.error(f"PayPal IPN processing error: {e}")
        return HttpResponse("Error", status=500)