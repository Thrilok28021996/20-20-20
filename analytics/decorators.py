"""
Custom decorators for analytics views
"""
from functools import wraps
from django.http import JsonResponse, HttpResponseForbidden
from django.contrib.auth.decorators import login_required


def admin_required(view_func):
    """
    Decorator that requires the user to be logged in and be a staff member (admin)
    """
    @wraps(view_func)
    def _wrapped_view(request, *args, **kwargs):
        if not request.user.is_authenticated:
            # Redirect to login if not authenticated
            from django.contrib.auth.decorators import login_required
            return login_required(view_func)(request, *args, **kwargs)
        
        if not request.user.is_staff:
            # Check if this is an API request (JSON response expected)
            if request.path.startswith('/analytics/api/') or 'api' in request.path:
                return JsonResponse({'error': 'Admin access required'}, status=403)
            else:
                return HttpResponseForbidden(
                    "<h1>Access Denied</h1>"
                    "<p>Admin privileges required to access this resource.</p>"
                    "<p><a href='/timer/dashboard/'>Return to Dashboard</a></p>"
                )
        
        return view_func(request, *args, **kwargs)
    return _wrapped_view


def staff_or_superuser_required(view_func):
    """
    Decorator that requires the user to be staff or superuser
    """
    @wraps(view_func)
    def _wrapped_view(request, *args, **kwargs):
        if not request.user.is_authenticated:
            from django.contrib.auth.decorators import login_required
            return login_required(view_func)(request, *args, **kwargs)
        
        if not (request.user.is_staff or request.user.is_superuser):
            if request.path.startswith('/analytics/api/') or 'api' in request.path:
                return JsonResponse({'error': 'Staff access required'}, status=403)
            else:
                return HttpResponseForbidden(
                    "<h1>Access Denied</h1>"
                    "<p>Staff privileges required to access this resource.</p>"
                    "<p><a href='/timer/dashboard/'>Return to Dashboard</a></p>"
                )
        
        return view_func(request, *args, **kwargs)
    return _wrapped_view