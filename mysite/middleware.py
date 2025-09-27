"""
Error handling middleware for the EyeHealth 20-20-20 SaaS application.

This middleware provides consistent error response formatting, security
headers, and comprehensive error logging for both API and web requests.
"""
import json
import logging
import traceback
from typing import Dict, Any, Optional, Union
from django.http import JsonResponse, HttpResponse, HttpRequest
from django.utils.deprecation import MiddlewareMixin
from django.conf import settings
from django.core.exceptions import ValidationError, PermissionDenied
from django.http import Http404
from django.template.response import TemplateResponse
from django.shortcuts import render
from django.contrib import messages
from django.urls import reverse
from django.utils import timezone

from .exceptions import (
    BaseApplicationError, RateLimitError, ExternalServiceError,
    UserNotAuthenticatedError, InsufficientPermissionsError,
    InvalidRequestDataError, APIError, TimerError, BreakError,
    AnalyticsError, GamificationError, UserError, BusinessLogicError,
    sanitize_error_message, get_error_context
)


logger = logging.getLogger(__name__)


class ErrorHandlingMiddleware(MiddlewareMixin):
    """
    Comprehensive error handling middleware that provides:
    - Consistent error response formatting
    - Security-focused error sanitization
    - Detailed logging for debugging
    - Appropriate HTTP status codes
    - User-friendly error pages
    """

    def __init__(self, get_response):
        """Initialize the middleware."""
        self.get_response = get_response
        super().__init__(get_response)

    def process_exception(self, request: HttpRequest, exception: Exception) -> Optional[HttpResponse]:
        """
        Process exceptions and return appropriate responses.

        Args:
            request: Django request object
            exception: The exception that was raised

        Returns:
            HttpResponse object or None to continue normal processing
        """
        # Get error context for logging
        error_context = get_error_context(
            user=getattr(request, 'user', None),
            request=request
        )

        # Determine if this is an API request
        is_api_request = self._is_api_request(request)

        # Handle different types of exceptions
        if isinstance(exception, BaseApplicationError):
            return self._handle_application_error(request, exception, is_api_request, error_context)
        elif isinstance(exception, ValidationError):
            return self._handle_validation_error(request, exception, is_api_request, error_context)
        elif isinstance(exception, PermissionDenied):
            return self._handle_permission_denied(request, exception, is_api_request, error_context)
        elif isinstance(exception, Http404):
            return self._handle_not_found(request, exception, is_api_request, error_context)
        else:
            return self._handle_unexpected_error(request, exception, is_api_request, error_context)

    def _is_api_request(self, request: HttpRequest) -> bool:
        """
        Determine if the request is an API request.

        Args:
            request: Django request object

        Returns:
            True if API request, False otherwise
        """
        # Check URL patterns
        if request.path.startswith('/api/'):
            return True

        # Check Accept header
        accept_header = request.META.get('HTTP_ACCEPT', '')
        if 'application/json' in accept_header:
            return True

        # Check Content-Type for POST/PUT requests
        if request.method in ['POST', 'PUT', 'PATCH']:
            content_type = request.META.get('CONTENT_TYPE', '')
            if 'application/json' in content_type:
                return True

        # Check for AJAX requests
        if request.META.get('HTTP_X_REQUESTED_WITH') == 'XMLHttpRequest':
            return True

        return False

    def _handle_application_error(
        self,
        request: HttpRequest,
        exception: BaseApplicationError,
        is_api_request: bool,
        error_context: Dict[str, Any]
    ) -> HttpResponse:
        """
        Handle application-specific errors.

        Args:
            request: Django request object
            exception: Application exception
            is_api_request: Whether this is an API request
            error_context: Error context for logging

        Returns:
            Appropriate HTTP response
        """
        # Log the error with context
        logger.error(
            f"Application error: {exception.error_code} - {exception.message}",
            extra={
                'exception': exception,
                'error_context': error_context,
                'stack_trace': traceback.format_exc() if settings.DEBUG else None
            }
        )

        if is_api_request:
            return self._create_api_error_response(exception)
        else:
            return self._create_web_error_response(request, exception)

    def _handle_validation_error(
        self,
        request: HttpRequest,
        exception: ValidationError,
        is_api_request: bool,
        error_context: Dict[str, Any]
    ) -> HttpResponse:
        """Handle Django validation errors."""
        logger.warning(
            f"Validation error: {str(exception)}",
            extra={
                'exception': exception,
                'error_context': error_context
            }
        )

        app_exception = InvalidRequestDataError(
            message=f"Validation error: {str(exception)}",
            context={'validation_errors': exception.message_dict if hasattr(exception, 'message_dict') else str(exception)},
            cause=exception
        )

        if is_api_request:
            return self._create_api_error_response(app_exception)
        else:
            return self._create_web_error_response(request, app_exception)

    def _handle_permission_denied(
        self,
        request: HttpRequest,
        exception: PermissionDenied,
        is_api_request: bool,
        error_context: Dict[str, Any]
    ) -> HttpResponse:
        """Handle Django permission denied errors."""
        logger.warning(
            f"Permission denied: {str(exception)}",
            extra={
                'exception': exception,
                'error_context': error_context
            }
        )

        app_exception = InsufficientPermissionsError(
            message=f"Permission denied: {str(exception)}",
            cause=exception
        )

        if is_api_request:
            return self._create_api_error_response(app_exception)
        else:
            return self._create_web_error_response(request, app_exception)

    def _handle_not_found(
        self,
        request: HttpRequest,
        exception: Http404,
        is_api_request: bool,
        error_context: Dict[str, Any]
    ) -> HttpResponse:
        """Handle Django 404 errors."""
        logger.info(
            f"Not found: {request.path}",
            extra={
                'exception': exception,
                'error_context': error_context
            }
        )

        if is_api_request:
            return JsonResponse(
                {
                    'success': False,
                    'error_code': 'NOT_FOUND',
                    'message': 'Resource not found'
                },
                status=404
            )
        else:
            # Let Django handle 404s for web requests normally
            return None

    def _handle_unexpected_error(
        self,
        request: HttpRequest,
        exception: Exception,
        is_api_request: bool,
        error_context: Dict[str, Any]
    ) -> HttpResponse:
        """Handle unexpected errors."""
        # Log the full error with stack trace
        logger.exception(
            f"Unexpected error: {type(exception).__name__}: {str(exception)}",
            extra={
                'exception': exception,
                'error_context': error_context,
                'stack_trace': traceback.format_exc()
            }
        )

        # Create sanitized error for response
        if settings.DEBUG:
            error_message = f"{type(exception).__name__}: {str(exception)}"
        else:
            error_message = "An unexpected error occurred"

        if is_api_request:
            return JsonResponse(
                {
                    'success': False,
                    'error_code': 'INTERNAL_SERVER_ERROR',
                    'message': error_message,
                    'details': traceback.format_exc() if settings.DEBUG else None
                },
                status=500
            )
        else:
            # Return a user-friendly error page
            return render(
                request,
                'errors/500.html',
                {
                    'error_message': error_message,
                    'error_details': traceback.format_exc() if settings.DEBUG else None,
                    'support_email': getattr(settings, 'SUPPORT_EMAIL', 'thriloke96@gmail.com')
                },
                status=500
            )

    def _create_api_error_response(self, exception: BaseApplicationError) -> JsonResponse:
        """
        Create standardized API error response.

        Args:
            exception: Application exception

        Returns:
            JSON response with error details
        """
        response_data = {
            'success': False,
            'error_code': exception.error_code,
            'message': sanitize_error_message(exception.user_message),
            'timestamp': timezone.now().isoformat()
        }

        # Add context/details if available and in debug mode
        if exception.context and (settings.DEBUG or exception.log_level <= logging.WARNING):
            response_data['details'] = exception.context

        # Add request ID if available
        request_id = getattr(exception, 'request_id', None)
        if request_id:
            response_data['request_id'] = request_id

        return JsonResponse(response_data, status=exception.status_code)

    def _create_web_error_response(
        self,
        request: HttpRequest,
        exception: BaseApplicationError
    ) -> HttpResponse:
        """
        Create user-friendly web error response.

        Args:
            request: Django request object
            exception: Application exception

        Returns:
            HTTP response with error page or redirect
        """
        # For authentication errors, redirect to login
        if isinstance(exception, UserNotAuthenticatedError):
            from django.contrib.auth.views import redirect_to_login
            return redirect_to_login(request.get_full_path())

        # For rate limit errors, show rate limit page
        if isinstance(exception, RateLimitError):
            return render(
                request,
                'errors/rate_limit.html',
                {
                    'error_message': exception.user_message,
                    'retry_after': getattr(exception, 'retry_after', 60)
                },
                status=exception.status_code
            )

        # For external service errors, show service unavailable page
        if isinstance(exception, ExternalServiceError):
            return render(
                request,
                'errors/service_unavailable.html',
                {
                    'error_message': exception.user_message,
                    'service_name': getattr(exception, 'service_name', 'External Service')
                },
                status=exception.status_code
            )

        # For validation errors, redirect back with error message
        if exception.status_code < 500:
            messages.error(request, exception.user_message)

            # Try to redirect to a sensible page
            referer = request.META.get('HTTP_REFERER')
            if referer and referer.startswith(request.get_host()):
                from django.http import HttpResponseRedirect
                return HttpResponseRedirect(referer)

            # Fallback redirects based on exception type
            if isinstance(exception, (TimerError, BreakError)):
                try:
                    from django.urls import reverse
                    return HttpResponseRedirect(reverse('timer:dashboard'))
                except:
                    pass
            elif isinstance(exception, UserError):
                try:
                    from django.urls import reverse
                    return HttpResponseRedirect(reverse('accounts:profile'))
                except:
                    pass

        # For server errors, show error page
        template_name = 'errors/error.html'
        if exception.status_code == 403:
            template_name = 'errors/403.html'
        elif exception.status_code == 404:
            template_name = 'errors/404.html'
        elif exception.status_code >= 500:
            template_name = 'errors/500.html'

        return render(
            request,
            template_name,
            {
                'error_message': exception.user_message,
                'error_code': exception.error_code,
                'support_email': getattr(settings, 'SUPPORT_EMAIL', 'thriloke96@gmail.com'),
                'error_details': str(exception) if settings.DEBUG else None
            },
            status=exception.status_code
        )


class SecurityHeadersMiddleware(MiddlewareMixin):
    """
    Middleware to add security headers to all responses.
    """

    def process_response(self, request: HttpRequest, response: HttpResponse) -> HttpResponse:
        """
        Add security headers to response.

        Args:
            request: Django request object
            response: Django response object

        Returns:
            Response with security headers added
        """
        # Add security headers
        if not settings.DEBUG:
            response['X-Content-Type-Options'] = 'nosniff'
            response['X-Frame-Options'] = 'DENY'
            response['X-XSS-Protection'] = '1; mode=block'
            response['Referrer-Policy'] = 'strict-origin-when-cross-origin'

        # Add CORS headers for API requests
        if request.path.startswith('/api/'):
            response['Access-Control-Allow-Credentials'] = 'true'

            # Get allowed origins from settings
            allowed_origins = getattr(settings, 'CORS_ALLOWED_ORIGINS', [])
            origin = request.META.get('HTTP_ORIGIN')

            if origin in allowed_origins:
                response['Access-Control-Allow-Origin'] = origin

            response['Access-Control-Allow-Methods'] = 'GET, POST, PUT, DELETE, OPTIONS'
            response['Access-Control-Allow-Headers'] = 'Content-Type, Authorization, X-Requested-With'

        return response


class RequestLoggingMiddleware(MiddlewareMixin):
    """
    Middleware to log requests for monitoring and debugging.
    """

    def __init__(self, get_response):
        """Initialize the middleware."""
        self.get_response = get_response
        super().__init__(get_response)

    def process_request(self, request: HttpRequest) -> None:
        """
        Log incoming requests.

        Args:
            request: Django request object
        """
        # Only log API requests and POST requests in production
        if settings.DEBUG or request.path.startswith('/api/') or request.method in ['POST', 'PUT', 'DELETE']:
            user_id = getattr(request.user, 'id', None) if hasattr(request, 'user') and request.user.is_authenticated else None

            logger.info(
                f"{request.method} {request.path}",
                extra={
                    'user_id': user_id,
                    'ip_address': self._get_client_ip(request),
                    'user_agent': request.META.get('HTTP_USER_AGENT', ''),
                    'content_type': request.META.get('CONTENT_TYPE', ''),
                    'request_size': len(request.body) if hasattr(request, 'body') else 0
                }
            )

    def process_response(self, request: HttpRequest, response: HttpResponse) -> HttpResponse:
        """
        Log response details.

        Args:
            request: Django request object
            response: Django response object

        Returns:
            Response object
        """
        # Log responses for API requests or error responses
        if settings.DEBUG or request.path.startswith('/api/') or response.status_code >= 400:
            user_id = getattr(request.user, 'id', None) if hasattr(request, 'user') and request.user.is_authenticated else None

            logger.info(
                f"{request.method} {request.path} -> {response.status_code}",
                extra={
                    'user_id': user_id,
                    'status_code': response.status_code,
                    'response_size': len(response.content) if hasattr(response, 'content') else 0,
                    'content_type': response.get('Content-Type', '')
                }
            )

        return response

    def _get_client_ip(self, request: HttpRequest) -> str:
        """Get client IP address from request."""
        x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
        if x_forwarded_for:
            ip = x_forwarded_for.split(',')[0]
        else:
            ip = request.META.get('REMOTE_ADDR', 'unknown')
        return ip


class APIErrorResponseMiddleware(MiddlewareMixin):
    """
    Specific middleware for API error response standardization.
    """

    def process_response(self, request: HttpRequest, response: HttpResponse) -> HttpResponse:
        """
        Standardize API error responses.

        Args:
            request: Django request object
            response: Django response object

        Returns:
            Standardized response
        """
        # Only process API responses
        if not request.path.startswith('/api/'):
            return response

        # Only process error responses
        if response.status_code < 400:
            return response

        # Try to parse existing response content
        try:
            if hasattr(response, 'content') and response.content:
                data = json.loads(response.content.decode('utf-8'))
            else:
                data = {}
        except (json.JSONDecodeError, UnicodeDecodeError):
            data = {}

        # Ensure standardized format
        if not isinstance(data, dict):
            data = {'message': str(data)}

        # Add missing fields
        if 'success' not in data:
            data['success'] = False

        if 'error_code' not in data:
            data['error_code'] = self._get_error_code_from_status(response.status_code)

        if 'message' not in data:
            data['message'] = self._get_default_message_from_status(response.status_code)

        if 'timestamp' not in data:
            data['timestamp'] = timezone.now().isoformat()

        # Create new response with standardized data
        return JsonResponse(data, status=response.status_code)

    def _get_error_code_from_status(self, status_code: int) -> str:
        """Get error code from HTTP status code."""
        error_codes = {
            400: 'BAD_REQUEST',
            401: 'UNAUTHORIZED',
            403: 'FORBIDDEN',
            404: 'NOT_FOUND',
            405: 'METHOD_NOT_ALLOWED',
            409: 'CONFLICT',
            413: 'PAYLOAD_TOO_LARGE',
            422: 'UNPROCESSABLE_ENTITY',
            429: 'TOO_MANY_REQUESTS',
            500: 'INTERNAL_SERVER_ERROR',
            502: 'BAD_GATEWAY',
            503: 'SERVICE_UNAVAILABLE',
            504: 'GATEWAY_TIMEOUT'
        }
        return error_codes.get(status_code, 'UNKNOWN_ERROR')

    def _get_default_message_from_status(self, status_code: int) -> str:
        """Get default message from HTTP status code."""
        messages = {
            400: 'Bad request',
            401: 'Authentication required',
            403: 'Access denied',
            404: 'Resource not found',
            405: 'Method not allowed',
            409: 'Resource conflict',
            413: 'Request payload too large',
            422: 'Unprocessable entity',
            429: 'Too many requests',
            500: 'Internal server error',
            502: 'Bad gateway',
            503: 'Service unavailable',
            504: 'Gateway timeout'
        }
        return messages.get(status_code, 'An error occurred')