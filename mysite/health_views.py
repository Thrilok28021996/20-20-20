"""
Health monitoring and system status views.
"""
from django.http import JsonResponse, HttpRequest
from django.shortcuts import render
from django.contrib.admin.views.decorators import staff_member_required
from django.views.decorators.cache import cache_page
from django.views.decorators.http import require_http_methods
from django.utils import timezone

from .monitoring import error_monitor, performance_monitor, health_checker
from .decorators import api_error_handler, require_staff_user


@require_http_methods(["GET"])
def health_check_view(request: HttpRequest) -> JsonResponse:
    """
    Basic health check endpoint for load balancers and monitoring systems.

    Returns a simple OK response if the system is operational.
    """
    try:
        # Run basic health checks
        health_results = health_checker.run_checks()

        # Determine if system is healthy
        all_healthy = all(
            result['check_passed'] for result in health_results.values()
        )

        status_code = 200 if all_healthy else 503

        return JsonResponse({
            'status': 'ok' if all_healthy else 'degraded',
            'timestamp': timezone.now().isoformat(),
            'version': '1.0.0',  # You might want to make this dynamic
        }, status=status_code)

    except Exception as e:
        return JsonResponse({
            'status': 'error',
            'message': 'Health check failed',
            'timestamp': timezone.now().isoformat(),
        }, status=503)


@require_staff_user
@api_error_handler
def detailed_health_view(request: HttpRequest) -> JsonResponse:
    """
    Detailed health check endpoint for administrators.

    Provides comprehensive system health information.
    """
    overall_health = health_checker.get_overall_health()

    return {
        'health_status': overall_health,
        'system_info': {
            'django_version': _get_django_version(),
            'python_version': _get_python_version(),
            'database_status': _get_database_status(),
            'cache_status': _get_cache_status(),
        },
        'timestamp': timezone.now().isoformat()
    }


@require_staff_user
@api_error_handler
@cache_page(60)  # Cache for 1 minute
def error_metrics_view(request: HttpRequest) -> JsonResponse:
    """
    Error metrics endpoint for monitoring dashboard.
    """
    hours = int(request.GET.get('hours', 24))

    error_summary = error_monitor.get_error_summary(hours=hours)

    return {
        'error_metrics': error_summary,
        'timestamp': timezone.now().isoformat()
    }


@require_staff_user
@api_error_handler
@cache_page(60)  # Cache for 1 minute
def performance_metrics_view(request: HttpRequest) -> JsonResponse:
    """
    Performance metrics endpoint for monitoring dashboard.
    """
    hours = int(request.GET.get('hours', 24))

    performance_summary = performance_monitor.get_performance_summary(hours=hours)
    slow_requests = performance_monitor.get_slow_requests(threshold=1.0)

    return {
        'performance_metrics': performance_summary,
        'slow_requests': slow_requests,
        'timestamp': timezone.now().isoformat()
    }


@staff_member_required
def system_status_view(request: HttpRequest):
    """
    System status dashboard for administrators.

    Provides a web interface for monitoring system health and metrics.
    """
    # Get health status
    health_status = health_checker.get_overall_health()

    # Get recent error metrics
    error_summary = error_monitor.get_error_summary(hours=24)

    # Get performance metrics
    performance_summary = performance_monitor.get_performance_summary(hours=24)
    slow_requests = performance_monitor.get_slow_requests(threshold=1.0)

    context = {
        'health_status': health_status,
        'error_summary': error_summary,
        'performance_summary': performance_summary,
        'slow_requests': slow_requests,
        'last_updated': timezone.now(),
    }

    return render(request, 'health/system_status.html', context)


def _get_django_version() -> str:
    """Get Django version."""
    try:
        import django
        return django.get_version()
    except Exception:
        return 'unknown'


def _get_python_version() -> str:
    """Get Python version."""
    try:
        import sys
        return f"{sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro}"
    except Exception:
        return 'unknown'


def _get_database_status() -> dict:
    """Get database connection status."""
    try:
        from django.db import connection
        with connection.cursor() as cursor:
            cursor.execute("SELECT 1")
            return {'status': 'connected', 'vendor': connection.vendor}
    except Exception as e:
        return {'status': 'error', 'error': str(e)}


def _get_cache_status() -> dict:
    """Get cache connection status."""
    try:
        from django.core.cache import cache
        test_key = "health_check_cache_test"
        cache.set(test_key, "test_value", 30)
        if cache.get(test_key) == "test_value":
            return {'status': 'connected'}
        else:
            return {'status': 'error', 'error': 'Cache write/read failed'}
    except Exception as e:
        return {'status': 'error', 'error': str(e)}