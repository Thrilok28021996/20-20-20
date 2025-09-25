"""
Standardized exception hierarchy for the EyeHealth 20-20-20 SaaS application.

This module provides a comprehensive exception framework that ensures consistent
error handling across all application components while maintaining security
and providing clear error reporting for developers and users.
"""
from typing import Dict, Any, Optional, Union
import logging
from django.http import Http404
from django.core.exceptions import ValidationError, PermissionDenied


logger = logging.getLogger(__name__)


class BaseApplicationError(Exception):
    """
    Base exception class for all application-specific errors.

    Provides common error handling functionality including error codes,
    user-friendly messages, and logging integration.
    """

    # Default error properties
    error_code: str = "UNKNOWN_ERROR"
    user_message: str = "An unexpected error occurred"
    log_level: int = logging.ERROR
    status_code: int = 500

    def __init__(
        self,
        message: str = None,
        error_code: str = None,
        user_message: str = None,
        context: Dict[str, Any] = None,
        cause: Exception = None
    ):
        """
        Initialize base application error.

        Args:
            message: Technical error message for logging
            error_code: Unique error identifier
            user_message: User-friendly error message
            context: Additional context data
            cause: Original exception that caused this error
        """
        self.message = message or str(self)
        self.error_code = error_code or self.error_code
        self.user_message = user_message or self.user_message
        self.context = context or {}
        self.cause = cause

        # Set the exception message
        super().__init__(self.message)

        # Log the error
        self._log_error()

    def _log_error(self) -> None:
        """Log the error with appropriate level and context."""
        log_data = {
            'error_code': self.error_code,
            'message': self.message,
            'context': self.context,
            'cause': str(self.cause) if self.cause else None
        }

        logger.log(
            self.log_level,
            f"[{self.error_code}] {self.message}",
            extra=log_data
        )

    def to_dict(self) -> Dict[str, Any]:
        """Convert error to dictionary for API responses."""
        return {
            'error_code': self.error_code,
            'message': self.user_message,
            'details': self.context if self.context else None
        }


class ValidationErrorMixin:
    """Mixin for validation-related errors."""
    status_code = 400
    log_level = logging.WARNING


class AuthenticationErrorMixin:
    """Mixin for authentication-related errors."""
    status_code = 401
    log_level = logging.WARNING


class AuthorizationErrorMixin:
    """Mixin for authorization-related errors."""
    status_code = 403
    log_level = logging.WARNING


class NotFoundErrorMixin:
    """Mixin for resource not found errors."""
    status_code = 404
    log_level = logging.INFO


class ConflictErrorMixin:
    """Mixin for resource conflict errors."""
    status_code = 409
    log_level = logging.WARNING


class RateLimitErrorMixin:
    """Mixin for rate limiting errors."""
    status_code = 429
    log_level = logging.WARNING


# =============================================================================
# TIMER-RELATED EXCEPTIONS
# =============================================================================

class TimerError(BaseApplicationError):
    """Base class for timer-related errors."""
    error_code = "TIMER_ERROR"
    user_message = "Timer operation failed"


class SessionCreationError(TimerError):
    """Error when creating a timer session fails."""
    error_code = "SESSION_CREATION_FAILED"
    user_message = "Failed to start timer session"


class SessionNotFoundError(TimerError, NotFoundErrorMixin):
    """Error when requested session is not found."""
    error_code = "SESSION_NOT_FOUND"
    user_message = "Timer session not found"


class SessionAlreadyActiveError(TimerError, ConflictErrorMixin):
    """Error when trying to start a session while one is already active."""
    error_code = "SESSION_ALREADY_ACTIVE"
    user_message = "You already have an active timer session"


class SessionNotActiveError(TimerError, ValidationErrorMixin):
    """Error when trying to operate on an inactive session."""
    error_code = "SESSION_NOT_ACTIVE"
    user_message = "Timer session is not active"


class IntervalNotFoundError(TimerError, NotFoundErrorMixin):
    """Error when requested interval is not found."""
    error_code = "INTERVAL_NOT_FOUND"
    user_message = "Timer interval not found"


class IntervalStateError(TimerError, ValidationErrorMixin):
    """Error when interval is in invalid state for operation."""
    error_code = "INTERVAL_INVALID_STATE"
    user_message = "Timer interval is in invalid state"


class DailyLimitExceededError(TimerError, ValidationErrorMixin):
    """Error when user exceeds daily usage limits."""
    error_code = "DAILY_LIMIT_EXCEEDED"
    user_message = "Daily interval limit reached. Upgrade to Premium for unlimited access."


# =============================================================================
# BREAK-RELATED EXCEPTIONS
# =============================================================================

class BreakError(BaseApplicationError):
    """Base class for break-related errors."""
    error_code = "BREAK_ERROR"
    user_message = "Break operation failed"


class BreakCreationError(BreakError):
    """Error when creating a break record fails."""
    error_code = "BREAK_CREATION_FAILED"
    user_message = "Failed to start break"


class BreakNotFoundError(BreakError, NotFoundErrorMixin):
    """Error when requested break is not found."""
    error_code = "BREAK_NOT_FOUND"
    user_message = "Break record not found"


class BreakAlreadyCompletedError(BreakError, ConflictErrorMixin):
    """Error when trying to complete an already completed break."""
    error_code = "BREAK_ALREADY_COMPLETED"
    user_message = "Break is already completed"


class BreakValidationError(BreakError, ValidationErrorMixin):
    """Error when break data validation fails."""
    error_code = "BREAK_VALIDATION_FAILED"
    user_message = "Break data is invalid"


# =============================================================================
# ANALYTICS-RELATED EXCEPTIONS
# =============================================================================

class AnalyticsError(BaseApplicationError):
    """Base class for analytics-related errors."""
    error_code = "ANALYTICS_ERROR"
    user_message = "Analytics operation failed"


class DataCalculationError(AnalyticsError):
    """Error when analytics calculation fails."""
    error_code = "DATA_CALCULATION_FAILED"
    user_message = "Failed to calculate analytics data"


class InsufficientDataError(AnalyticsError, ValidationErrorMixin):
    """Error when insufficient data for analytics."""
    error_code = "INSUFFICIENT_DATA"
    user_message = "Not enough data for analytics calculation"


class MetricsUpdateError(AnalyticsError):
    """Error when updating metrics fails."""
    error_code = "METRICS_UPDATE_FAILED"
    user_message = "Failed to update metrics"


# =============================================================================
# GAMIFICATION-RELATED EXCEPTIONS
# =============================================================================

class GamificationError(BaseApplicationError):
    """Base class for gamification-related errors."""
    error_code = "GAMIFICATION_ERROR"
    user_message = "Gamification operation failed"


class AchievementError(GamificationError):
    """Error when processing achievements."""
    error_code = "ACHIEVEMENT_ERROR"
    user_message = "Failed to process achievement"


class LevelProgressError(GamificationError):
    """Error when updating level progress."""
    error_code = "LEVEL_PROGRESS_ERROR"
    user_message = "Failed to update level progress"


class BadgeError(GamificationError):
    """Error when processing badges."""
    error_code = "BADGE_ERROR"
    user_message = "Failed to process badge"


class ChallengeError(GamificationError):
    """Error when processing challenges."""
    error_code = "CHALLENGE_ERROR"
    user_message = "Failed to process challenge"


# =============================================================================
# USER & AUTHENTICATION EXCEPTIONS
# =============================================================================

class UserError(BaseApplicationError):
    """Base class for user-related errors."""
    error_code = "USER_ERROR"
    user_message = "User operation failed"


class UserNotFoundError(UserError, NotFoundErrorMixin):
    """Error when user is not found."""
    error_code = "USER_NOT_FOUND"
    user_message = "User not found"


class UserNotAuthenticatedError(UserError, AuthenticationErrorMixin):
    """Error when user is not authenticated."""
    error_code = "USER_NOT_AUTHENTICATED"
    user_message = "Authentication required"


class InsufficientPermissionsError(UserError, AuthorizationErrorMixin):
    """Error when user lacks required permissions."""
    error_code = "INSUFFICIENT_PERMISSIONS"
    user_message = "You don't have permission to perform this action"


class PremiumFeatureError(UserError, AuthorizationErrorMixin):
    """Error when non-premium user tries to access premium features."""
    error_code = "PREMIUM_FEATURE_REQUIRED"
    user_message = "This feature requires a Premium subscription"


class ProfileUpdateError(UserError, ValidationErrorMixin):
    """Error when updating user profile fails."""
    error_code = "PROFILE_UPDATE_FAILED"
    user_message = "Failed to update profile"


# =============================================================================
# API & VALIDATION EXCEPTIONS
# =============================================================================

class APIError(BaseApplicationError):
    """Base class for API-related errors."""
    error_code = "API_ERROR"
    user_message = "API request failed"


class InvalidRequestDataError(APIError, ValidationErrorMixin):
    """Error when request data is invalid."""
    error_code = "INVALID_REQUEST_DATA"
    user_message = "Request data is invalid"


class MissingRequiredFieldError(APIError, ValidationErrorMixin):
    """Error when required field is missing."""
    error_code = "MISSING_REQUIRED_FIELD"
    user_message = "Required field is missing"


class InvalidJSONError(APIError, ValidationErrorMixin):
    """Error when JSON data is invalid."""
    error_code = "INVALID_JSON"
    user_message = "Invalid JSON data"


class RequestTooLargeError(APIError, ValidationErrorMixin):
    """Error when request payload is too large."""
    error_code = "REQUEST_TOO_LARGE"
    user_message = "Request payload is too large"
    status_code = 413


# =============================================================================
# RATE LIMITING EXCEPTIONS
# =============================================================================

class RateLimitError(BaseApplicationError, RateLimitErrorMixin):
    """Base class for rate limiting errors."""
    error_code = "RATE_LIMIT_EXCEEDED"
    user_message = "Rate limit exceeded. Please try again later."


class APIRateLimitError(RateLimitError):
    """Error when API rate limit is exceeded."""
    error_code = "API_RATE_LIMIT_EXCEEDED"
    user_message = "API rate limit exceeded. Please wait before making more requests."


class UserActionRateLimitError(RateLimitError):
    """Error when user action rate limit is exceeded."""
    error_code = "USER_ACTION_RATE_LIMIT_EXCEEDED"
    user_message = "Too many actions performed. Please wait a moment."


# =============================================================================
# EXTERNAL SERVICE EXCEPTIONS
# =============================================================================

class ExternalServiceError(BaseApplicationError):
    """Base class for external service errors."""
    error_code = "EXTERNAL_SERVICE_ERROR"
    user_message = "External service is temporarily unavailable"
    status_code = 503


class PaymentServiceError(ExternalServiceError):
    """Error when payment service fails."""
    error_code = "PAYMENT_SERVICE_ERROR"
    user_message = "Payment service is temporarily unavailable"


class EmailServiceError(ExternalServiceError):
    """Error when email service fails."""
    error_code = "EMAIL_SERVICE_ERROR"
    user_message = "Email service is temporarily unavailable"


class CalendarServiceError(ExternalServiceError):
    """Error when calendar integration fails."""
    error_code = "CALENDAR_SERVICE_ERROR"
    user_message = "Calendar service is temporarily unavailable"


# =============================================================================
# BUSINESS LOGIC EXCEPTIONS
# =============================================================================

class BusinessLogicError(BaseApplicationError):
    """Base class for business logic violations."""
    error_code = "BUSINESS_LOGIC_ERROR"
    user_message = "Business rule violation"
    status_code = 422


class SubscriptionError(BusinessLogicError):
    """Error related to subscription logic."""
    error_code = "SUBSCRIPTION_ERROR"
    user_message = "Subscription operation failed"


class SettingsValidationError(BusinessLogicError):
    """Error when user settings validation fails."""
    error_code = "SETTINGS_VALIDATION_ERROR"
    user_message = "Settings validation failed"


class DataIntegrityError(BusinessLogicError):
    """Error when data integrity is compromised."""
    error_code = "DATA_INTEGRITY_ERROR"
    user_message = "Data integrity violation detected"


# =============================================================================
# UTILITY FUNCTIONS
# =============================================================================

def handle_django_exceptions(func):
    """
    Decorator to convert Django exceptions to application exceptions.

    Args:
        func: Function to wrap

    Returns:
        Wrapped function that converts Django exceptions
    """
    def wrapper(*args, **kwargs):
        try:
            return func(*args, **kwargs)
        except ValidationError as e:
            raise InvalidRequestDataError(
                message=f"Django validation error: {str(e)}",
                context={'validation_errors': e.message_dict if hasattr(e, 'message_dict') else str(e)},
                cause=e
            )
        except PermissionDenied as e:
            raise InsufficientPermissionsError(
                message=f"Django permission denied: {str(e)}",
                cause=e
            )
        except Http404 as e:
            raise UserNotFoundError(
                message=f"Django 404: {str(e)}",
                cause=e
            )
        except Exception as e:
            # Log unexpected exceptions
            logger.exception(f"Unexpected exception in {func.__name__}: {str(e)}")
            raise BaseApplicationError(
                message=f"Unexpected error in {func.__name__}: {str(e)}",
                cause=e
            )

    return wrapper


def get_error_context(user: Any = None, request: Any = None) -> Dict[str, Any]:
    """
    Get standardized error context for logging.

    Args:
        user: User instance
        request: Django request object

    Returns:
        Dictionary with error context
    """
    context = {}

    if user:
        context['user_id'] = getattr(user, 'id', None)
        context['user_email'] = getattr(user, 'email', None)
        context['user_premium'] = getattr(user, 'is_premium_user', False)

    if request:
        context['method'] = getattr(request, 'method', None)
        context['path'] = getattr(request, 'path', None)
        context['user_agent'] = request.META.get('HTTP_USER_AGENT', '') if hasattr(request, 'META') else ''
        context['ip_address'] = get_client_ip(request)

    return context


def get_client_ip(request: Any) -> str:
    """
    Get client IP address from request.

    Args:
        request: Django request object

    Returns:
        Client IP address
    """
    if not hasattr(request, 'META'):
        return 'unknown'

    x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
    if x_forwarded_for:
        ip = x_forwarded_for.split(',')[0]
    else:
        ip = request.META.get('REMOTE_ADDR', 'unknown')
    return ip


def sanitize_error_message(message: str, max_length: int = 1000) -> str:
    """
    Sanitize error message for safe display.

    Args:
        message: Original error message
        max_length: Maximum allowed length

    Returns:
        Sanitized error message
    """
    if not message:
        return "An error occurred"

    # Remove sensitive patterns
    import re
    sensitive_patterns = [
        r'password[=:]\s*\S+',
        r'token[=:]\s*\S+',
        r'key[=:]\s*\S+',
        r'secret[=:]\s*\S+',
    ]

    sanitized = message
    for pattern in sensitive_patterns:
        sanitized = re.sub(pattern, '[REDACTED]', sanitized, flags=re.IGNORECASE)

    # Truncate if too long
    if len(sanitized) > max_length:
        sanitized = sanitized[:max_length - 3] + '...'

    return sanitized