"""
Rate limiting middleware for password reset and sensitive operations.
"""
import logging
import time
from django.core.cache import cache
from django.http import HttpResponse
from django.utils.deprecation import MiddlewareMixin
from django.conf import settings

logger = logging.getLogger(__name__)


class PasswordResetRateLimitMiddleware(MiddlewareMixin):
    """
    Additional rate limiting for password reset operations at the email level.

    This provides an extra layer of protection beyond the view-level rate limiting
    to prevent email enumeration and abuse.
    """

    def process_request(self, request):
        """
        Check rate limits for password reset requests.
        """
        # Only apply to password reset paths
        if not request.path.startswith('/accounts/password_reset/'):
            return None

        if request.method != 'POST':
            return None

        # Get email from POST data
        email = request.POST.get('email', '').lower().strip()
        if not email:
            return None

        # Create cache key for this email
        cache_key = f'password_reset_email_{email}'

        # Check current count
        attempts = cache.get(cache_key, 0)

        # Allow 5 attempts per day per email
        if attempts >= 5:
            logger.warning(
                f"Password reset rate limit exceeded for email: {email[:3]}***",
                extra={'email_prefix': email[:3], 'attempts': attempts}
            )
            return HttpResponse(
                "Too many password reset requests for this email address. "
                "Please try again in 24 hours or contact support.",
                status=429
            )

        # Increment attempt counter (24 hour expiry)
        cache.set(cache_key, attempts + 1, 86400)  # 24 hours

        return None
