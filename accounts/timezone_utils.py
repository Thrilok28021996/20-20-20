"""
Timezone utilities for handling user-specific timezones
"""
import pytz
from django.utils import timezone
from django.contrib.auth import get_user_model
from datetime import datetime

def get_user_timezone(user):
    """
    Get the user's timezone or default to UTC
    """
    if hasattr(user, 'profile') and user.profile.timezone:
        try:
            return pytz.timezone(user.profile.timezone)
        except pytz.exceptions.UnknownTimeZoneError:
            pass
    return pytz.UTC

def user_localtime(user, dt=None):
    """
    Convert datetime to user's local time
    If dt is None, return current time in user's timezone
    """
    if dt is None:
        dt = timezone.now()
    
    # Ensure dt is timezone-aware
    if timezone.is_naive(dt):
        dt = timezone.make_aware(dt, timezone.utc)
    
    user_tz = get_user_timezone(user)
    return dt.astimezone(user_tz)

def user_now(user):
    """
    Get current time in user's timezone
    """
    return user_localtime(user)

def user_today(user):
    """
    Get today's date in user's timezone
    """
    return user_now(user).date()

def parse_user_datetime(user, date_string, time_string=None):
    """
    Parse date/time string in user's timezone and return UTC datetime
    """
    user_tz = get_user_timezone(user)
    
    if time_string:
        dt_string = f"{date_string} {time_string}"
        dt = datetime.strptime(dt_string, "%Y-%m-%d %H:%M:%S")
    else:
        dt = datetime.strptime(date_string, "%Y-%m-%d")
    
    # Localize to user's timezone then convert to UTC
    localized_dt = user_tz.localize(dt)
    return localized_dt.astimezone(pytz.UTC)

def format_user_datetime(user, dt, format_string="%Y-%m-%d %H:%M:%S"):
    """
    Format datetime in user's local time
    """
    if dt is None:
        return None
    
    local_dt = user_localtime(user, dt)
    return local_dt.strftime(format_string)

def get_available_timezones():
    """
    Get list of common timezones for user selection
    """
    common_timezones = [
        'US/Eastern',
        'US/Central', 
        'US/Mountain',
        'US/Pacific',
        'US/Alaska',
        'US/Hawaii',
        'Europe/London',
        'Europe/Paris',
        'Europe/Berlin',
        'Asia/Tokyo',
        'Asia/Shanghai',
        'Asia/Kolkata',
        'Australia/Sydney',
        'Australia/Melbourne',
        'UTC',
    ]
    
    # Add all pytz timezones for comprehensive list
    all_timezones = [(tz, tz) for tz in sorted(pytz.common_timezones)]
    return all_timezones