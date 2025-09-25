"""
Error handling decorators for the EyeHealth 20-20-20 SaaS application.

This module provides decorators for common error handling patterns,
including authentication, permissions, rate limiting, and API validation.
"""
import functools
import json
import logging
from typing import Callable, Any, Dict, Optional, Union, List
from django.http import JsonResponse, HttpRequest, HttpResponse
from django.contrib.auth.decorators import login_required
from django.core.exceptions import ValidationError
from django.views.decorators.csrf import csrf_exempt
from django.utils.decorators import method_decorator
from django.db import transaction
from django_ratelimit.decorators import ratelimit

from .exceptions import (
    BaseApplicationError, UserNotAuthenticatedError, InsufficientPermissionsError,
    PremiumFeatureError, InvalidRequestDataError, InvalidJSONError,
    MissingRequiredFieldError, RateLimitError, APIRateLimitError,
    handle_django_exceptions, get_error_context, sanitize_error_message
)


logger = logging.getLogger(__name__)


def api_error_handler(view_func: Callable) -> Callable:
    """
    Decorator to handle errors in API views with consistent JSON responses.

    Args:
        view_func: View function to wrap

    Returns:
        Wrapped view function
    """
    @functools.wraps(view_func)
    def wrapper(request: HttpRequest, *args, **kwargs) -> JsonResponse:
        try:
            # Get error context for potential logging
            error_context = get_error_context(
                user=getattr(request, 'user', None),
                request=request
            )

            result = view_func(request, *args, **kwargs)

            # If result is already a JsonResponse, return it
            if isinstance(result, JsonResponse):
                return result

            # If result is a dict, convert to JsonResponse
            if isinstance(result, dict):
                return JsonResponse({
                    'success': True,
                    **result
                })

            # If result is HttpResponse but not JsonResponse, convert
            if isinstance(result, HttpResponse):
                return JsonResponse({
                    'success': True,
                    'message': 'Operation completed successfully'
                })

            # For other return types, wrap in success response
            return JsonResponse({
                'success': True,
                'data': result
            })

        except BaseApplicationError as e:
            logger.error(
                f"API error in {view_func.__name__}: {e.error_code} - {e.message}",
                extra={'error_context': error_context, 'exception': e}
            )
            return JsonResponse(e.to_dict(), status=e.status_code)

        except Exception as e:
            logger.exception(
                f"Unexpected error in API view {view_func.__name__}: {str(e)}",
                extra={'error_context': error_context, 'exception': e}
            )
            return JsonResponse({
                'success': False,
                'error_code': 'INTERNAL_SERVER_ERROR',
                'message': 'An unexpected error occurred'
            }, status=500)

    return wrapper


def require_authenticated_user(view_func: Callable) -> Callable:
    """
    Decorator to require authenticated user with proper error handling.

    Args:
        view_func: View function to wrap

    Returns:
        Wrapped view function
    """
    @functools.wraps(view_func)
    def wrapper(request: HttpRequest, *args, **kwargs):
        if not request.user.is_authenticated:
            raise UserNotAuthenticatedError(
                message=f"Authentication required for {view_func.__name__}",
                context={'view': view_func.__name__, 'path': request.path}
            )
        return view_func(request, *args, **kwargs)

    return wrapper


def require_premium_user(view_func: Callable) -> Callable:
    """
    Decorator to require premium user subscription.

    Args:
        view_func: View function to wrap

    Returns:
        Wrapped view function
    """
    @functools.wraps(view_func)
    def wrapper(request: HttpRequest, *args, **kwargs):
        if not request.user.is_authenticated:
            raise UserNotAuthenticatedError(
                message=f"Authentication required for premium feature {view_func.__name__}",
                context={'view': view_func.__name__, 'path': request.path}
            )

        if not getattr(request.user, 'is_premium_user', False):
            raise PremiumFeatureError(
                message=f"Premium subscription required for {view_func.__name__}",
                context={
                    'view': view_func.__name__,
                    'user_id': request.user.id,
                    'subscription_type': getattr(request.user, 'subscription_type', 'free')
                }
            )

        return view_func(request, *args, **kwargs)

    return wrapper


def require_staff_user(view_func: Callable) -> Callable:
    """
    Decorator to require staff user permissions.

    Args:
        view_func: View function to wrap

    Returns:
        Wrapped view function
    """
    @functools.wraps(view_func)
    def wrapper(request: HttpRequest, *args, **kwargs):
        if not request.user.is_authenticated:
            raise UserNotAuthenticatedError(
                message=f"Authentication required for staff view {view_func.__name__}",
                context={'view': view_func.__name__, 'path': request.path}
            )

        if not (request.user.is_staff or request.user.is_superuser):
            raise InsufficientPermissionsError(
                message=f"Staff permissions required for {view_func.__name__}",
                context={
                    'view': view_func.__name__,
                    'user_id': request.user.id,
                    'is_staff': request.user.is_staff,
                    'is_superuser': request.user.is_superuser
                }
            )

        return view_func(request, *args, **kwargs)

    return wrapper


def validate_json_request(required_fields: List[str] = None, optional_fields: List[str] = None) -> Callable:
    """
    Decorator to validate JSON request data.

    Args:
        required_fields: List of required field names
        optional_fields: List of optional field names

    Returns:
        Decorator function
    """
    def decorator(view_func: Callable) -> Callable:
        @functools.wraps(view_func)
        def wrapper(request: HttpRequest, *args, **kwargs):
            # Check content type
            content_type = request.META.get('CONTENT_TYPE', '')
            if 'application/json' not in content_type and request.method in ['POST', 'PUT', 'PATCH']:
                raise InvalidRequestDataError(
                    message="Content-Type must be application/json",
                    context={'content_type': content_type, 'method': request.method}
                )

            # Parse JSON data
            try:
                if request.body:
                    data = json.loads(request.body.decode('utf-8'))
                else:
                    data = {}
            except json.JSONDecodeError as e:
                raise InvalidJSONError(
                    message=f"Invalid JSON data: {str(e)}",
                    context={'json_error': str(e)},
                    cause=e
                )

            # Validate required fields
            if required_fields:
                missing_fields = []
                for field in required_fields:
                    if field not in data or data[field] is None or data[field] == '':
                        missing_fields.append(field)

                if missing_fields:
                    raise MissingRequiredFieldError(
                        message=f"Missing required fields: {', '.join(missing_fields)}",
                        context={'missing_fields': missing_fields, 'provided_fields': list(data.keys())}
                    )

            # Add validated data to request
            request.validated_data = data

            return view_func(request, *args, **kwargs)

        return wrapper
    return decorator


def rate_limit_api(key: str = 'user', rate: str = '100/h', method: str = 'ALL') -> Callable:
    """
    Decorator for API rate limiting with proper error handling.

    Args:
        key: Rate limiting key (user, ip, etc.)
        rate: Rate limit (e.g., '100/h', '10/m')
        method: HTTP methods to limit

    Returns:
        Decorator function
    """
    def decorator(view_func: Callable) -> Callable:
        @ratelimit(key=key, rate=rate, method=method)
        @functools.wraps(view_func)
        def wrapper(request: HttpRequest, *args, **kwargs):
            # Check if rate limited
            if getattr(request, 'limited', False):
                # Extract rate info for error message
                rate_parts = rate.split('/')
                limit_count = rate_parts[0]
                limit_period = rate_parts[1] if len(rate_parts) > 1 else 'hour'

                period_map = {
                    's': 'second', 'm': 'minute', 'h': 'hour', 'd': 'day'
                }
                period_name = period_map.get(limit_period, limit_period)

                raise APIRateLimitError(
                    message=f"Rate limit exceeded: {limit_count} requests per {period_name}",
                    context={
                        'rate_limit': rate,
                        'key': key,
                        'method': method,
                        'user_id': getattr(request.user, 'id', None) if hasattr(request, 'user') else None
                    }
                )

            return view_func(request, *args, **kwargs)

        return wrapper
    return decorator


def atomic_transaction(view_func: Callable) -> Callable:
    """
    Decorator to wrap view in atomic transaction with error handling.

    Args:
        view_func: View function to wrap

    Returns:
        Wrapped view function
    """
    @functools.wraps(view_func)
    def wrapper(request: HttpRequest, *args, **kwargs):
        try:
            with transaction.atomic():
                return view_func(request, *args, **kwargs)
        except Exception as e:
            logger.error(
                f"Transaction rolled back in {view_func.__name__}: {str(e)}",
                extra={
                    'view': view_func.__name__,
                    'user_id': getattr(request.user, 'id', None) if hasattr(request, 'user') else None,
                    'exception': e
                }
            )
            raise

    return wrapper


def log_api_call(log_request: bool = True, log_response: bool = False) -> Callable:
    """
    Decorator to log API calls for monitoring and debugging.

    Args:
        log_request: Whether to log request data
        log_response: Whether to log response data

    Returns:
        Decorator function
    """
    def decorator(view_func: Callable) -> Callable:
        @functools.wraps(view_func)
        def wrapper(request: HttpRequest, *args, **kwargs):
            start_time = logger.info(f"API call started: {view_func.__name__}")

            # Log request data if enabled
            if log_request:
                request_data = {
                    'method': request.method,
                    'path': request.path,
                    'user_id': getattr(request.user, 'id', None) if hasattr(request, 'user') else None,
                    'content_type': request.META.get('CONTENT_TYPE', ''),
                    'content_length': request.META.get('CONTENT_LENGTH', 0)
                }

                logger.info(
                    f"API request: {view_func.__name__}",
                    extra={'request_data': request_data}
                )

            try:
                response = view_func(request, *args, **kwargs)

                # Log response data if enabled
                if log_response and isinstance(response, JsonResponse):
                    logger.info(
                        f"API response: {view_func.__name__}",
                        extra={
                            'status_code': response.status_code,
                            'response_size': len(response.content) if hasattr(response, 'content') else 0
                        }
                    )

                logger.info(f"API call completed: {view_func.__name__}")
                return response

            except Exception as e:
                logger.error(
                    f"API call failed: {view_func.__name__} - {str(e)}",
                    extra={'exception': e}
                )
                raise

        return wrapper
    return decorator


def sanitize_input_data(fields_to_sanitize: List[str] = None) -> Callable:
    """
    Decorator to sanitize input data for security.

    Args:
        fields_to_sanitize: List of field names to sanitize

    Returns:
        Decorator function
    """
    def decorator(view_func: Callable) -> Callable:
        @functools.wraps(view_func)
        def wrapper(request: HttpRequest, *args, **kwargs):
            # Sanitize request data if available
            if hasattr(request, 'validated_data') and fields_to_sanitize:
                import bleach

                for field in fields_to_sanitize:
                    if field in request.validated_data:
                        value = request.validated_data[field]
                        if isinstance(value, str):
                            # Basic HTML sanitization
                            request.validated_data[field] = bleach.clean(
                                value,
                                tags=[],  # No HTML tags allowed
                                strip=True
                            )

            return view_func(request, *args, **kwargs)

        return wrapper
    return decorator


def cache_response(timeout: int = 300, key_prefix: str = None) -> Callable:
    """
    Decorator to cache API responses.

    Args:
        timeout: Cache timeout in seconds
        key_prefix: Cache key prefix

    Returns:
        Decorator function
    """
    def decorator(view_func: Callable) -> Callable:
        @functools.wraps(view_func)
        def wrapper(request: HttpRequest, *args, **kwargs):
            # Only cache GET requests
            if request.method != 'GET':
                return view_func(request, *args, **kwargs)

            from django.core.cache import cache
            import hashlib

            # Generate cache key
            cache_key_parts = [
                key_prefix or view_func.__name__,
                request.path,
                str(getattr(request.user, 'id', 'anonymous')),
                hashlib.md5(request.GET.urlencode().encode()).hexdigest()
            ]
            cache_key = ':'.join(filter(None, cache_key_parts))

            # Try to get from cache
            cached_response = cache.get(cache_key)
            if cached_response:
                logger.debug(f"Cache hit for {view_func.__name__}: {cache_key}")
                return cached_response

            # Execute view and cache result
            response = view_func(request, *args, **kwargs)

            # Only cache successful responses
            if isinstance(response, JsonResponse) and response.status_code == 200:
                cache.set(cache_key, response, timeout)
                logger.debug(f"Cached response for {view_func.__name__}: {cache_key}")

            return response

        return wrapper
    return decorator


# Convenience decorators combining multiple decorators
def api_view(
    authentication_required: bool = True,
    premium_required: bool = False,
    staff_required: bool = False,
    required_fields: List[str] = None,
    rate_limit: str = '100/h',
    use_transaction: bool = False,
    log_calls: bool = False
) -> Callable:
    """
    Convenience decorator that combines common API view decorators.

    Args:
        authentication_required: Whether authentication is required
        premium_required: Whether premium subscription is required
        staff_required: Whether staff permissions are required
        required_fields: List of required JSON fields
        rate_limit: Rate limit string (e.g., '100/h')
        use_transaction: Whether to use atomic transaction
        log_calls: Whether to log API calls

    Returns:
        Combined decorator function
    """
    def decorator(view_func: Callable) -> Callable:
        # Build decorator chain from innermost to outermost
        decorated_func = view_func

        # Add transaction wrapper if requested
        if use_transaction:
            decorated_func = atomic_transaction(decorated_func)

        # Add JSON validation if required fields specified
        if required_fields:
            decorated_func = validate_json_request(required_fields)(decorated_func)

        # Add rate limiting
        if rate_limit:
            decorated_func = rate_limit_api(rate=rate_limit)(decorated_func)

        # Add permission checks
        if staff_required:
            decorated_func = require_staff_user(decorated_func)
        elif premium_required:
            decorated_func = require_premium_user(decorated_func)
        elif authentication_required:
            decorated_func = require_authenticated_user(decorated_func)

        # Add logging if requested
        if log_calls:
            decorated_func = log_api_call()(decorated_func)

        # Add error handling (outermost)
        decorated_func = api_error_handler(decorated_func)

        return decorated_func

    return decorator


# Class-based view decorators
class APIViewMixin:
    """
    Mixin for class-based views that adds error handling.
    """

    @method_decorator(api_error_handler)
    def dispatch(self, request, *args, **kwargs):
        return super().dispatch(request, *args, **kwargs)


class AuthenticatedAPIViewMixin(APIViewMixin):
    """
    Mixin for authenticated API views.
    """

    @method_decorator(require_authenticated_user)
    def dispatch(self, request, *args, **kwargs):
        return super().dispatch(request, *args, **kwargs)


class PremiumAPIViewMixin(AuthenticatedAPIViewMixin):
    """
    Mixin for premium API views.
    """

    @method_decorator(require_premium_user)
    def dispatch(self, request, *args, **kwargs):
        return super().dispatch(request, *args, **kwargs)


class StaffAPIViewMixin(AuthenticatedAPIViewMixin):
    """
    Mixin for staff API views.
    """

    @method_decorator(require_staff_user)
    def dispatch(self, request, *args, **kwargs):
        return super().dispatch(request, *args, **kwargs)