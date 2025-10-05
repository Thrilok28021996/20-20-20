"""
Health check endpoint for Railway and monitoring services.

Provides:
- Basic health status
- Database connectivity check
- Redis/Cache connectivity check
- Application readiness status
"""
import logging
from django.http import JsonResponse
from django.core.cache import cache
from django.db import connection
from django.utils import timezone
from django.views.decorators.http import require_http_methods
from django.views.decorators.csrf import csrf_exempt

logger = logging.getLogger(__name__)


@csrf_exempt
@require_http_methods(["GET", "HEAD"])
def health_check(request):
    """
    Basic health check endpoint.

    Returns:
        JSON response with health status
    """
    return JsonResponse({
        'status': 'healthy',
        'timestamp': timezone.now().isoformat(),
        'service': 'EyeHealth 20-20-20'
    })


@csrf_exempt
@require_http_methods(["GET"])
def detailed_health_check(request):
    """
    Detailed health check with database and cache connectivity.

    Returns:
        JSON response with detailed health status
    """
    health_status = {
        'status': 'healthy',
        'timestamp': timezone.now().isoformat(),
        'service': 'EyeHealth 20-20-20',
        'checks': {}
    }

    # Check database connectivity
    try:
        with connection.cursor() as cursor:
            cursor.execute("SELECT 1")
            cursor.fetchone()
        health_status['checks']['database'] = {
            'status': 'healthy',
            'message': 'Database connection successful'
        }
    except Exception as e:
        logger.error(f"Database health check failed: {e}")
        health_status['checks']['database'] = {
            'status': 'unhealthy',
            'message': f'Database connection failed: {str(e)}'
        }
        health_status['status'] = 'unhealthy'

    # Check cache connectivity (Redis/LocMem)
    try:
        cache_key = 'health_check_test'
        cache.set(cache_key, 'test_value', 10)
        retrieved_value = cache.get(cache_key)
        if retrieved_value == 'test_value':
            health_status['checks']['cache'] = {
                'status': 'healthy',
                'message': 'Cache connection successful'
            }
        else:
            health_status['checks']['cache'] = {
                'status': 'degraded',
                'message': 'Cache read/write mismatch'
            }
    except Exception as e:
        logger.error(f"Cache health check failed: {e}")
        health_status['checks']['cache'] = {
            'status': 'unhealthy',
            'message': f'Cache connection failed: {str(e)}'
        }
        # Cache failure is not critical, mark as degraded
        if health_status['status'] == 'healthy':
            health_status['status'] = 'degraded'

    # Return appropriate HTTP status code
    status_code = 200 if health_status['status'] == 'healthy' else 503

    return JsonResponse(health_status, status=status_code)


@csrf_exempt
@require_http_methods(["GET"])
def readiness_check(request):
    """
    Readiness check for load balancers.

    Returns 200 if application is ready to serve traffic.
    """
    try:
        # Check critical dependencies
        with connection.cursor() as cursor:
            cursor.execute("SELECT 1")
            cursor.fetchone()

        return JsonResponse({
            'status': 'ready',
            'timestamp': timezone.now().isoformat()
        })
    except Exception as e:
        logger.error(f"Readiness check failed: {e}")
        return JsonResponse({
            'status': 'not_ready',
            'timestamp': timezone.now().isoformat(),
            'error': str(e)
        }, status=503)


@csrf_exempt
@require_http_methods(["GET"])
def liveness_check(request):
    """
    Liveness check for container orchestration.

    Returns 200 if application is alive (not deadlocked).
    """
    return JsonResponse({
        'status': 'alive',
        'timestamp': timezone.now().isoformat()
    })
