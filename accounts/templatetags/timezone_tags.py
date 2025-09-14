"""
Template filters for timezone handling
"""
from django import template
from django.utils import timezone
from accounts.timezone_utils import user_localtime, format_user_datetime, user_now

register = template.Library()

@register.filter
def user_timezone(dt, user):
    """
    Convert datetime to user's timezone
    Usage: {{ some_datetime|user_timezone:request.user }}
    """
    if not dt or not user:
        return dt
    return user_localtime(user, dt)

@register.filter
def user_date_format(dt, user):
    """
    Format datetime in user's timezone 
    Usage: {{ some_datetime|user_date_format:request.user }}
    """
    if not dt or not user:
        return dt
    return format_user_datetime(user, dt, "%Y-%m-%d %H:%M")

@register.filter
def user_time_format(dt, user):
    """
    Format time in user's timezone
    Usage: {{ some_datetime|user_time_format:request.user }}
    """
    if not dt or not user:
        return dt
    return format_user_datetime(user, dt, "%H:%M")

@register.simple_tag
def user_current_time(user):
    """
    Get current time in user's timezone
    Usage: {% user_current_time request.user %}
    """
    if not user:
        return timezone.now()
    return user_now(user)

@register.filter
def relative_time(dt, user):
    """
    Show relative time in user's timezone (e.g., "2 hours ago")
    """
    if not dt or not user:
        return dt
    
    user_dt = user_localtime(user, dt)
    current_time = user_now(user)
    
    diff = current_time - user_dt
    
    if diff.days > 0:
        return f"{diff.days} day{'s' if diff.days > 1 else ''} ago"
    elif diff.seconds > 3600:
        hours = diff.seconds // 3600
        return f"{hours} hour{'s' if hours > 1 else ''} ago"
    elif diff.seconds > 60:
        minutes = diff.seconds // 60
        return f"{minutes} minute{'s' if minutes > 1 else ''} ago"
    else:
        return "Just now"

@register.filter
def div(value, divisor):
    """
    Divide value by divisor
    Usage: {{ value|div:divisor }}
    """
    try:
        return float(value) / float(divisor)
    except (ValueError, ZeroDivisionError, TypeError):
        return 0

@register.filter
def mul(value, multiplier):
    """
    Multiply value by multiplier
    Usage: {{ value|mul:multiplier }}
    """
    try:
        return float(value) * float(multiplier)
    except (ValueError, TypeError):
        return 0