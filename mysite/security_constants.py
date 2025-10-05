"""
Security constants for the EyeHealth 20-20-20 application.

This module contains security-related constants including:
- Stripe webhook trusted IPs
- PayPal IPN verification endpoints
- Security headers
- Rate limit configurations
"""

# ================================
# Stripe Webhook Security
# ================================
# Stripe webhook IPs (as of 2024)
# Source: https://stripe.com/docs/ips
STRIPE_WEBHOOK_IPS = [
    # Stripe webhook IPv4 addresses
    '3.18.12.63',
    '3.130.192.231',
    '13.235.14.237',
    '13.235.122.149',
    '18.211.135.69',
    '35.154.171.200',
    '52.15.183.38',
    '54.88.130.119',
    '54.88.130.237',
    '54.187.174.169',
    '54.187.205.235',
    '54.187.216.72',

    # Localhost for development
    '127.0.0.1',
    'localhost',
]

# ================================
# PayPal IPN Verification
# ================================
PAYPAL_IPN_VERIFY_URL = {
    'sandbox': 'https://ipnpb.sandbox.paypal.com/cgi-bin/webscr',
    'live': 'https://ipnpb.paypal.com/cgi-bin/webscr'
}

# PayPal trusted IPs (for additional validation)
PAYPAL_IPN_IPS = [
    # PayPal's IP ranges - these should be verified and updated regularly
    # Source: https://www.paypal.com/us/smarthelp/article/what-are-the-ip-addresses-for-the-paypal-servers-ts1056
    '173.0.80.0/20',
    '64.4.240.0/20',
    '66.211.160.0/19',
    '147.75.0.0/16',

    # Localhost for development
    '127.0.0.1',
    'localhost',
]

# ================================
# Security Headers
# ================================
SECURITY_HEADERS = {
    'X-Content-Type-Options': 'nosniff',
    'X-Frame-Options': 'DENY',
    'X-XSS-Protection': '1; mode=block',
    'Referrer-Policy': 'strict-origin-when-cross-origin',
    'Permissions-Policy': 'geolocation=(), microphone=(), camera=()',
    'Cross-Origin-Opener-Policy': 'same-origin',
    'Cross-Origin-Embedder-Policy': 'require-corp',
    'Cross-Origin-Resource-Policy': 'same-origin',
}

# ================================
# Rate Limiting Constants
# ================================
RATE_LIMITS = {
    'login': '5/h',
    'password_reset': '3/h',
    'api_default': '100/h',
    'api_authenticated': '1000/h',
    'api_premium': '5000/h',
    'webhook': '100/h',
    'session_create': '10/m',
    'break_record': '20/m',
}

# ================================
# Error Messages (User-Facing)
# ================================
ERROR_MESSAGES = {
    # Authentication errors
    'auth_required': 'Authentication is required to access this resource.',
    'invalid_credentials': 'Invalid email or password.',
    'account_locked': 'Your account has been locked due to too many failed login attempts. Please try again later.',
    'session_expired': 'Your session has expired. Please log in again.',

    # Authorization errors
    'permission_denied': 'You do not have permission to perform this action.',
    'premium_required': 'This feature requires a Premium subscription.',

    # Validation errors
    'invalid_input': 'Invalid input data provided.',
    'missing_required_field': 'Required field is missing: {field}',
    'invalid_json': 'Invalid JSON data in request body.',

    # Session errors
    'session_not_found': 'Timer session not found.',
    'session_already_active': 'You already have an active timer session.',
    'session_not_active': 'No active timer session found.',
    'daily_limit_exceeded': 'You have reached your daily limit for free tier.',

    # Payment errors
    'payment_failed': 'Payment processing failed. Please try again.',
    'subscription_not_found': 'Subscription not found.',
    'subscription_already_active': 'You already have an active subscription.',

    # Rate limiting
    'rate_limit_exceeded': 'Too many requests. Please try again later.',

    # Generic errors
    'server_error': 'An unexpected error occurred. Please try again later.',
    'service_unavailable': 'Service temporarily unavailable. Please try again later.',
}

# ================================
# URL Constants
# ================================
URL_PATTERNS = {
    'dashboard': '/timer/dashboard/',
    'login': '/accounts/login/',
    'pricing': '/accounts/pricing/',
    'profile': '/accounts/profile/',
    'settings': '/accounts/settings/',
}

# ================================
# Email Configuration Validation
# ================================
ALLOWED_EMAIL_BACKENDS = [
    'django.core.mail.backends.smtp.EmailBackend',
    'django.core.mail.backends.console.EmailBackend',
    'django.core.mail.backends.filebased.EmailBackend',
]

REQUIRED_EMAIL_SETTINGS = [
    'EMAIL_HOST',
    'EMAIL_PORT',
    'EMAIL_HOST_USER',
    'DEFAULT_FROM_EMAIL',
]

# ================================
# Cache Versioning
# ================================
CACHE_VERSION = 1
CACHE_KEY_PREFIXES = {
    'user_stats': 'stats:user',
    'dashboard': 'dashboard',
    'analytics': 'analytics',
    'session': 'session',
}

# ================================
# Database Connection Monitoring
# ================================
DB_CONNECTION_THRESHOLDS = {
    'warning': 0.7,  # 70% of max connections
    'critical': 0.9,  # 90% of max connections
}

DB_QUERY_THRESHOLDS = {
    'slow_query_ms': 1000,  # Queries slower than 1 second
    'n_plus_one_threshold': 10,  # More than 10 queries in a view
}
