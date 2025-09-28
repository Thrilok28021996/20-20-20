"""
Security utilities for input validation and authorization checks
"""
import bleach
import re
from django.core.exceptions import ValidationError, PermissionDenied
from django.contrib.auth import get_user_model
from django.http import JsonResponse
from django.utils.html import escape
from typing import Dict, Any, Tuple, Optional
import logging

logger = logging.getLogger(__name__)

# Allowed HTML tags and attributes for user content
ALLOWED_TAGS = [
    'p', 'br', 'strong', 'em', 'u', 'ol', 'ul', 'li', 'blockquote', 
    'h1', 'h2', 'h3', 'h4', 'h5', 'h6'
]

ALLOWED_ATTRIBUTES = {
    '*': ['class']
}

def sanitize_html_input(text):
    """
    Sanitize HTML input to prevent XSS attacks
    """
    if not text:
        return text
    
    # Clean HTML using bleach
    cleaned = bleach.clean(
        text, 
        tags=ALLOWED_TAGS, 
        attributes=ALLOWED_ATTRIBUTES,
        strip=True
    )
    
    return cleaned

def validate_and_sanitize_json_data(request):
    """
    Validate and sanitize JSON data from request
    """
    try:
        import json
        data = json.loads(request.body)
        
        # Sanitize string values
        sanitized_data = {}
        for key, value in data.items():
            if isinstance(value, str):
                sanitized_data[key] = bleach.clean(value, tags=[], strip=True)
            elif isinstance(value, (int, float, bool)):
                sanitized_data[key] = value
            elif isinstance(value, list):
                # Sanitize list elements if they are strings
                sanitized_data[key] = [
                    bleach.clean(item, tags=[], strip=True) if isinstance(item, str) else item
                    for item in value
                ]
            else:
                sanitized_data[key] = value
        
        return sanitized_data
    except (json.JSONDecodeError, ValueError) as e:
        logger.warning(f"Invalid JSON data received: {e}")
        raise ValidationError("Invalid JSON data")

def validate_user_owns_object(user, obj, user_field='user'):
    """
    Validate that a user owns a specific object to prevent IDOR
    """
    if not hasattr(obj, user_field):
        raise ValueError(f"Object does not have {user_field} attribute")
    
    obj_user = getattr(obj, user_field)
    if obj_user != user:
        logger.warning(f"IDOR attempt: User {user.id} tried to access object owned by {obj_user.id}")
        raise PermissionDenied("You don't have permission to access this resource")

def validate_numeric_input(value, min_val=None, max_val=None, field_name="field"):
    """
    Validate numeric input with range checking
    """
    if value is None:
        raise ValidationError(f"{field_name} is required")
    
    try:
        num_value = float(value)
    except (ValueError, TypeError):
        raise ValidationError(f"{field_name} must be a valid number")
    
    if min_val is not None and num_value < min_val:
        raise ValidationError(f"{field_name} must be at least {min_val}")
    
    if max_val is not None and num_value > max_val:
        raise ValidationError(f"{field_name} must be at most {max_val}")
    
    return num_value

def validate_string_input(value, min_length=None, max_length=None, 
                         pattern=None, field_name="field"):
    """
    Validate string input with length and pattern checking
    """
    if value is None or value == '':
        raise ValidationError(f"{field_name} is required")
    
    # Sanitize the string
    sanitized_value = bleach.clean(value, tags=[], strip=True)
    
    if min_length is not None and len(sanitized_value) < min_length:
        raise ValidationError(f"{field_name} must be at least {min_length} characters")
    
    if max_length is not None and len(sanitized_value) > max_length:
        raise ValidationError(f"{field_name} must be at most {max_length} characters")
    
    if pattern is not None and not re.match(pattern, sanitized_value):
        raise ValidationError(f"{field_name} format is invalid")
    
    return sanitized_value

def validate_email_input(email):
    """
    Validate email input
    """
    from django.core.validators import validate_email as django_validate_email
    
    if not email:
        raise ValidationError("Email is required")
    
    sanitized_email = bleach.clean(email.strip().lower(), tags=[], strip=True)
    
    try:
        django_validate_email(sanitized_email)
    except ValidationError:
        raise ValidationError("Please enter a valid email address")
    
    return sanitized_email

def rate_limit_exceeded_response(request):
    """
    Return a JSON response for rate limit exceeded
    """
    return JsonResponse({
        'error': 'Rate limit exceeded. Please try again later.',
        'retry_after': 60
    }, status=429)

def check_subscription_access(user, feature='basic'):
    """
    Check if user has access to specific features based on subscription
    """
    if not hasattr(user, 'subscription_type'):
        user.subscription_type = 'free'
    
    if feature == 'premium' and user.subscription_type not in ['premium', 'trial']:
        raise PermissionDenied("Premium subscription required")
    
    return True

def log_security_event(user, event_type, details=None):
    """
    Log security-related events for monitoring
    """
    logger.info(f"Security Event - User: {user.id}, Type: {event_type}, Details: {details}")

class SecurityValidationMixin:
    """
    Mixin class for adding security validation to views
    """
    
    def validate_user_access(self, obj, user_field='user'):
        """
        Validate user has access to the object
        """
        validate_user_owns_object(self.request.user, obj, user_field)
    
    def get_sanitized_data(self):
        """
        Get sanitized data from request
        """
        return validate_and_sanitize_json_data(self.request)
    
    def validate_form_data(self, data, validation_rules):
        """
        Validate form data according to rules
        
        validation_rules = {
            'field_name': {
                'type': 'string|numeric|email',
                'required': True,
                'min_length': 1,
                'max_length': 100,
                'min_val': 0,
                'max_val': 1000,
                'pattern': r'^[a-zA-Z0-9]+$'
            }
        }
        """
        validated_data = {}
        
        for field_name, rules in validation_rules.items():
            value = data.get(field_name)
            field_type = rules.get('type', 'string')
            required = rules.get('required', False)
            
            if not value and required:
                raise ValidationError(f"{field_name} is required")
            
            if not value and not required:
                validated_data[field_name] = None
                continue
            
            try:
                if field_type == 'string':
                    validated_data[field_name] = validate_string_input(
                        value,
                        min_length=rules.get('min_length'),
                        max_length=rules.get('max_length'),
                        pattern=rules.get('pattern'),
                        field_name=field_name
                    )
                elif field_type == 'numeric':
                    validated_data[field_name] = validate_numeric_input(
                        value,
                        min_val=rules.get('min_val'),
                        max_val=rules.get('max_val'),
                        field_name=field_name
                    )
                elif field_type == 'email':
                    validated_data[field_name] = validate_email_input(value)
                else:
                    validated_data[field_name] = bleach.clean(str(value), tags=[], strip=True)
            except ValidationError as e:
                raise ValidationError(f"{field_name}: {str(e)}")
        
        return validated_data


def validate_user_access(user, obj, action='read', user_field='user'):
    """
    Validate that a user has access to perform an action on an object

    Args:
        user: User instance
        obj: Object to check access for
        action: Type of action ('read', 'write', 'delete')
        user_field: Field name that contains the owner user

    Raises:
        PermissionDenied: If user doesn't have access
    """
    if not user.is_authenticated:
        raise PermissionDenied("Authentication required")

    # Admin users have access to everything
    if user.is_staff or user.is_superuser:
        return True

    # Check object ownership
    validate_user_owns_object(user, obj, user_field)

    # Additional action-specific checks can be added here
    log_security_event(user, f'access_check_{action}', {
        'object_type': obj.__class__.__name__,
        'object_id': getattr(obj, 'id', None),
        'action': action
    })

    return True


def prevent_idor_attack(user, obj, user_field='user'):
    """
    Prevent Insecure Direct Object Reference (IDOR) attacks

    Args:
        user: User instance making the request
        obj: Object being accessed
        user_field: Field name that contains the owner user

    Raises:
        PermissionDenied: If IDOR attack detected
    """
    validate_user_owns_object(user, obj, user_field)
    log_security_event(user, 'idor_check', {
        'object_type': obj.__class__.__name__,
        'object_id': getattr(obj, 'id', None)
    })


def validate_input_data(data, validation_rules, strict=True):
    """
    Validate input data against a set of rules

    Args:
        data: Dictionary of data to validate
        validation_rules: Dictionary of validation rules
        strict: If True, raise error for unknown fields

    Returns:
        Dictionary of validated and sanitized data

    Raises:
        ValidationError: If validation fails
    """
    if not isinstance(data, dict):
        raise ValidationError("Data must be a dictionary")

    validated_data = {}

    # Check for unknown fields in strict mode
    if strict:
        unknown_fields = set(data.keys()) - set(validation_rules.keys())
        if unknown_fields:
            raise ValidationError(f"Unknown fields: {', '.join(unknown_fields)}")

    # Validate each field
    for field_name, rules in validation_rules.items():
        value = data.get(field_name)
        field_type = rules.get('type', 'string')
        required = rules.get('required', False)

        if not value and required:
            raise ValidationError(f"{field_name} is required")

        if not value and not required:
            validated_data[field_name] = None
            continue

        try:
            if field_type == 'string':
                validated_data[field_name] = validate_string_input(
                    value,
                    min_length=rules.get('min_length'),
                    max_length=rules.get('max_length'),
                    pattern=rules.get('pattern'),
                    field_name=field_name
                )
            elif field_type == 'numeric':
                validated_data[field_name] = validate_numeric_input(
                    value,
                    min_val=rules.get('min_val'),
                    max_val=rules.get('max_val'),
                    field_name=field_name
                )
            elif field_type == 'email':
                validated_data[field_name] = validate_email_input(value)
            elif field_type == 'boolean':
                validated_data[field_name] = bool(value)
            elif field_type == 'list':
                if not isinstance(value, list):
                    raise ValidationError(f"{field_name} must be a list")
                validated_data[field_name] = value
            else:
                validated_data[field_name] = bleach.clean(str(value), tags=[], strip=True)
        except ValidationError as e:
            raise ValidationError(f"{field_name}: {str(e)}")

    return validated_data


def check_rate_limits(user, action='api_call', limit_per_hour=100):
    """
    Check if user has exceeded rate limits

    Args:
        user: User instance
        action: Type of action being rate limited
        limit_per_hour: Maximum actions per hour

    Returns:
        tuple: (allowed: bool, remaining: int, reset_time: datetime)

    Raises:
        PermissionDenied: If rate limit exceeded
    """
    from django.core.cache import cache
    from django.utils import timezone
    import datetime

    # Create cache key
    cache_key = f"rate_limit:{user.id}:{action}:{timezone.now().strftime('%Y%m%d%H')}"

    # Get current count
    current_count = cache.get(cache_key, 0)

    # Check if limit exceeded
    if current_count >= limit_per_hour:
        log_security_event(user, 'rate_limit_exceeded', {
            'action': action,
            'count': current_count,
            'limit': limit_per_hour
        })
        reset_time = timezone.now().replace(minute=0, second=0, microsecond=0) + datetime.timedelta(hours=1)
        raise PermissionDenied(f"Rate limit exceeded for {action}. Try again after {reset_time}")

    # Increment counter
    cache.set(cache_key, current_count + 1, 3600)  # 1 hour timeout

    remaining = limit_per_hour - (current_count + 1)
    reset_time = timezone.now().replace(minute=0, second=0, microsecond=0) + datetime.timedelta(hours=1)

    return True, remaining, reset_time