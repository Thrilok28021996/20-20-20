"""
Security utilities for input validation and authorization checks
"""
import bleach
import re
from django.core.exceptions import ValidationError, PermissionDenied
from django.contrib.auth import get_user_model
from django.http import JsonResponse
from django.utils.html import escape
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