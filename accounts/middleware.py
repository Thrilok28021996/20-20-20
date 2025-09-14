"""
Middleware for handling user timezones
"""
import pytz
from django.utils import timezone
from django.contrib.auth import get_user_model
from .timezone_utils import get_user_timezone

User = get_user_model()

class TimezoneMiddleware:
    """
    Middleware to activate user's timezone for each request
    """
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        if request.user.is_authenticated:
            user_tz = get_user_timezone(request.user)
            timezone.activate(user_tz)
        else:
            timezone.deactivate()
        
        response = self.get_response(request)
        return response