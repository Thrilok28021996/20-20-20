"""
Custom error views for the EyeHealth 20-20-20 SaaS application.

These views handle HTTP error responses and provide user-friendly error pages
while maintaining security and proper error logging.
"""
from django.shortcuts import render
from django.http import HttpRequest, HttpResponse, JsonResponse
from django.conf import settings
from django.utils import timezone
import logging

from .exceptions import get_error_context, sanitize_error_message


logger = logging.getLogger(__name__)


def bad_request(request: HttpRequest, exception=None) -> HttpResponse:
    """
    Handle 400 Bad Request errors.

    Args:
        request: Django request object
        exception: Exception that caused the error

    Returns:
        Appropriate error response
    """
    error_context = get_error_context(
        user=getattr(request, 'user', None),
        request=request
    )

    logger.warning(
        f"400 Bad Request: {request.path}",
        extra={
            'status_code': 400,
            'error_context': error_context,
            'exception': str(exception) if exception else None
        }
    )

    # Check if this is an API request
    if _is_api_request(request):
        return JsonResponse({
            'success': False,
            'error_code': 'BAD_REQUEST',
            'message': 'Bad request',
            'timestamp': timezone.now().isoformat()
        }, status=400)

    # Render web error page
    context = {
        'error_message': 'The request could not be understood by the server.',
        'error_code': 'BAD_REQUEST',
        'support_email': getattr(settings, 'SUPPORT_EMAIL', 'thriloke96@gmail.com'),
        'error_details': str(exception) if exception and settings.DEBUG else None
    }

    return render(request, 'errors/error.html', context, status=400)


def permission_denied(request: HttpRequest, exception=None) -> HttpResponse:
    """
    Handle 403 Permission Denied errors.

    Args:
        request: Django request object
        exception: Exception that caused the error

    Returns:
        Appropriate error response
    """
    error_context = get_error_context(
        user=getattr(request, 'user', None),
        request=request
    )

    logger.warning(
        f"403 Permission Denied: {request.path}",
        extra={
            'status_code': 403,
            'error_context': error_context,
            'exception': str(exception) if exception else None
        }
    )

    # Check if this is an API request
    if _is_api_request(request):
        return JsonResponse({
            'success': False,
            'error_code': 'PERMISSION_DENIED',
            'message': 'Permission denied',
            'timestamp': timezone.now().isoformat()
        }, status=403)

    # Render web error page
    context = {
        'error_message': 'You don\'t have permission to access this resource.',
        'error_code': 'PERMISSION_DENIED',
        'support_email': getattr(settings, 'SUPPORT_EMAIL', 'thriloke96@gmail.com'),
        'error_details': str(exception) if exception and settings.DEBUG else None
    }

    return render(request, 'errors/403.html', context, status=403)


def page_not_found(request: HttpRequest, exception=None) -> HttpResponse:
    """
    Handle 404 Page Not Found errors.

    Args:
        request: Django request object
        exception: Exception that caused the error

    Returns:
        Appropriate error response
    """
    error_context = get_error_context(
        user=getattr(request, 'user', None),
        request=request
    )

    logger.info(
        f"404 Page Not Found: {request.path}",
        extra={
            'status_code': 404,
            'error_context': error_context,
            'exception': str(exception) if exception else None
        }
    )

    # Check if this is an API request
    if _is_api_request(request):
        return JsonResponse({
            'success': False,
            'error_code': 'NOT_FOUND',
            'message': 'Resource not found',
            'timestamp': timezone.now().isoformat()
        }, status=404)

    # Render web error page
    context = {
        'error_message': 'The page you\'re looking for doesn\'t exist.',
        'error_code': 'NOT_FOUND',
        'support_email': getattr(settings, 'SUPPORT_EMAIL', 'thriloke96@gmail.com'),
        'error_details': str(exception) if exception and settings.DEBUG else None
    }

    return render(request, 'errors/404.html', context, status=404)


def server_error(request: HttpRequest) -> HttpResponse:
    """
    Handle 500 Internal Server Error.

    Args:
        request: Django request object

    Returns:
        Appropriate error response
    """
    error_context = get_error_context(
        user=getattr(request, 'user', None),
        request=request
    )

    logger.error(
        f"500 Internal Server Error: {request.path}",
        extra={
            'status_code': 500,
            'error_context': error_context
        }
    )

    # Check if this is an API request
    if _is_api_request(request):
        error_message = "Internal server error" if not settings.DEBUG else "An unexpected error occurred"
        return JsonResponse({
            'success': False,
            'error_code': 'INTERNAL_SERVER_ERROR',
            'message': error_message,
            'timestamp': timezone.now().isoformat()
        }, status=500)

    # Render web error page
    context = {
        'error_message': 'An unexpected error occurred on our end.',
        'error_code': 'INTERNAL_SERVER_ERROR',
        'support_email': getattr(settings, 'SUPPORT_EMAIL', 'thriloke96@gmail.com'),
        'error_details': None  # Never show server error details to users
    }

    return render(request, 'errors/500.html', context, status=500)


def rate_limit_exceeded(request: HttpRequest, exception=None) -> HttpResponse:
    """
    Handle 429 Rate Limit Exceeded errors.

    Args:
        request: Django request object
        exception: Exception that caused the error

    Returns:
        Appropriate error response
    """
    error_context = get_error_context(
        user=getattr(request, 'user', None),
        request=request
    )

    logger.warning(
        f"429 Rate Limit Exceeded: {request.path}",
        extra={
            'status_code': 429,
            'error_context': error_context,
            'exception': str(exception) if exception else None
        }
    )

    # Get retry after time from exception if available
    retry_after = getattr(exception, 'retry_after', 60)

    # Check if this is an API request
    if _is_api_request(request):
        response = JsonResponse({
            'success': False,
            'error_code': 'RATE_LIMIT_EXCEEDED',
            'message': 'Rate limit exceeded. Please try again later.',
            'retry_after': retry_after,
            'timestamp': timezone.now().isoformat()
        }, status=429)

        # Add Retry-After header
        response['Retry-After'] = str(retry_after)
        return response

    # Render web error page
    context = {
        'error_message': 'You\'ve made too many requests. Please slow down!',
        'error_code': 'RATE_LIMIT_EXCEEDED',
        'retry_after': retry_after,
        'support_email': getattr(settings, 'SUPPORT_EMAIL', 'thriloke96@gmail.com'),
        'error_details': str(exception) if exception and settings.DEBUG else None
    }

    response = render(request, 'errors/rate_limit.html', context, status=429)
    response['Retry-After'] = str(retry_after)
    return response


def service_unavailable(request: HttpRequest, exception=None) -> HttpResponse:
    """
    Handle 503 Service Unavailable errors.

    Args:
        request: Django request object
        exception: Exception that caused the error

    Returns:
        Appropriate error response
    """
    error_context = get_error_context(
        user=getattr(request, 'user', None),
        request=request
    )

    logger.error(
        f"503 Service Unavailable: {request.path}",
        extra={
            'status_code': 503,
            'error_context': error_context,
            'exception': str(exception) if exception else None
        }
    )

    # Get service name from exception if available
    service_name = getattr(exception, 'service_name', 'Service')

    # Check if this is an API request
    if _is_api_request(request):
        return JsonResponse({
            'success': False,
            'error_code': 'SERVICE_UNAVAILABLE',
            'message': f'{service_name} is temporarily unavailable',
            'timestamp': timezone.now().isoformat()
        }, status=503)

    # Render web error page
    context = {
        'error_message': f'{service_name} is temporarily unavailable.',
        'error_code': 'SERVICE_UNAVAILABLE',
        'service_name': service_name,
        'support_email': getattr(settings, 'SUPPORT_EMAIL', 'thriloke96@gmail.com'),
        'error_details': str(exception) if exception and settings.DEBUG else None
    }

    return render(request, 'errors/service_unavailable.html', context, status=503)


def _is_api_request(request: HttpRequest) -> bool:
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
    if 'application/json' in accept_header and 'text/html' not in accept_header:
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