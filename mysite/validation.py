"""
Input validation and sanitization utilities for the EyeHealth 20-20-20 SaaS application.

This module provides comprehensive input validation, sanitization, and security
utilities to prevent common security vulnerabilities and ensure data integrity.
"""
import re
import json
import bleach
import logging
from typing import Dict, Any, List, Optional, Union, Tuple
from django.core.exceptions import ValidationError
from django.core.validators import validate_email, URLValidator
from django.utils.html import escape
from django.conf import settings
from datetime import datetime, date, time
from decimal import Decimal, InvalidOperation

from .exceptions import (
    InvalidRequestDataError, InvalidJSONError, MissingRequiredFieldError,
    ValidationErrorMixin, sanitize_error_message
)


logger = logging.getLogger(__name__)


class InputValidator:
    """
    Comprehensive input validation and sanitization service.

    Provides methods to validate and sanitize various types of user input
    while maintaining security and data integrity.
    """

    # Common validation patterns
    PATTERNS = {
        'username': re.compile(r'^[a-zA-Z0-9_.-]{3,30}$'),
        'password': re.compile(r'^(?=.*[A-Za-z])(?=.*\d)[A-Za-z\d@$!%*#?&]{8,}$'),
        'phone': re.compile(r'^\+?1?\d{9,15}$'),
        'slug': re.compile(r'^[-a-zA-Z0-9_]+$'),
        'hex_color': re.compile(r'^#([A-Fa-f0-9]{6}|[A-Fa-f0-9]{3})$'),
        'version': re.compile(r'^\d+\.\d+\.\d+$'),
    }

    # Allowed HTML tags for rich text content
    ALLOWED_TAGS = [
        'p', 'br', 'strong', 'em', 'u', 'ol', 'ul', 'li',
        'a', 'span', 'div', 'h1', 'h2', 'h3', 'h4', 'h5', 'h6'
    ]

    ALLOWED_ATTRIBUTES = {
        'a': ['href', 'title'],
        'span': ['class'],
        'div': ['class'],
    }

    @classmethod
    def validate_json_data(cls, json_string: str) -> Dict[str, Any]:
        """
        Validate and parse JSON data safely.

        Args:
            json_string: JSON string to validate

        Returns:
            Parsed JSON data as dictionary

        Raises:
            InvalidJSONError: If JSON is malformed or invalid
        """
        try:
            if not json_string or not json_string.strip():
                return {}

            # Limit JSON size to prevent DoS attacks
            max_size = getattr(settings, 'MAX_JSON_SIZE', 1024 * 1024)  # 1MB default
            if len(json_string.encode('utf-8')) > max_size:
                raise InvalidJSONError(
                    message="JSON data too large",
                    context={'size': len(json_string), 'max_size': max_size}
                )

            data = json.loads(json_string)

            # Ensure it's a dictionary for most API endpoints
            if not isinstance(data, dict):
                raise InvalidJSONError(
                    message="JSON data must be an object",
                    context={'type': type(data).__name__}
                )

            return data

        except json.JSONDecodeError as e:
            raise InvalidJSONError(
                message=f"Invalid JSON format: {str(e)}",
                context={'json_error': str(e), 'line': e.lineno, 'column': e.colno},
                cause=e
            )
        except Exception as e:
            raise InvalidJSONError(
                message=f"JSON validation failed: {str(e)}",
                context={'error_details': str(e)},
                cause=e
            )

    @classmethod
    def validate_required_fields(cls, data: Dict[str, Any], required_fields: List[str]) -> None:
        """
        Validate that all required fields are present in data.

        Args:
            data: Dictionary to validate
            required_fields: List of required field names

        Raises:
            MissingRequiredFieldError: If any required fields are missing
        """
        missing_fields = []
        empty_fields = []

        for field in required_fields:
            if field not in data:
                missing_fields.append(field)
            elif data[field] is None or (isinstance(data[field], str) and not data[field].strip()):
                empty_fields.append(field)

        if missing_fields or empty_fields:
            all_missing = missing_fields + empty_fields
            raise MissingRequiredFieldError(
                message=f"Missing or empty required fields: {', '.join(all_missing)}",
                context={
                    'missing_fields': missing_fields,
                    'empty_fields': empty_fields,
                    'provided_fields': list(data.keys())
                }
            )

    @classmethod
    def sanitize_html(cls, html_content: str, strip_tags: bool = False) -> str:
        """
        Sanitize HTML content to prevent XSS attacks.

        Args:
            html_content: HTML content to sanitize
            strip_tags: Whether to strip all HTML tags

        Returns:
            Sanitized HTML content
        """
        if not html_content:
            return ""

        if strip_tags:
            return bleach.clean(html_content, tags=[], strip=True)

        return bleach.clean(
            html_content,
            tags=cls.ALLOWED_TAGS,
            attributes=cls.ALLOWED_ATTRIBUTES,
            strip=True
        )

    @classmethod
    def sanitize_string(cls, value: str, max_length: Optional[int] = None) -> str:
        """
        Sanitize a string value for safe storage and display.

        Args:
            value: String to sanitize
            max_length: Maximum allowed length

        Returns:
            Sanitized string
        """
        if not isinstance(value, str):
            value = str(value)

        # Remove null bytes and other control characters
        value = value.replace('\x00', '').strip()

        # Escape HTML entities
        value = escape(value)

        # Truncate if too long
        if max_length and len(value) > max_length:
            value = value[:max_length].strip()

        return value

    @classmethod
    def validate_email_address(cls, email: str) -> str:
        """
        Validate and normalize email address.

        Args:
            email: Email address to validate

        Returns:
            Normalized email address

        Raises:
            InvalidRequestDataError: If email is invalid
        """
        if not email:
            raise InvalidRequestDataError(
                message="Email address is required",
                context={'field': 'email'}
            )

        try:
            email = email.strip().lower()
            validate_email(email)

            # Additional security checks
            if len(email) > 254:  # RFC 5321 limit
                raise InvalidRequestDataError(
                    message="Email address too long",
                    context={'email_length': len(email), 'max_length': 254}
                )

            # Block obviously fake domains in production
            if not settings.DEBUG:
                blocked_domains = ['example.com', 'test.com', 'localhost']
                domain = email.split('@')[1]
                if domain in blocked_domains:
                    raise InvalidRequestDataError(
                        message="Invalid email domain",
                        context={'domain': domain}
                    )

            return email

        except ValidationError as e:
            raise InvalidRequestDataError(
                message=f"Invalid email format: {str(e)}",
                context={'email': email[:50], 'validation_error': str(e)},
                cause=e
            )

    @classmethod
    def validate_url(cls, url: str, allowed_schemes: List[str] = None) -> str:
        """
        Validate URL format and scheme.

        Args:
            url: URL to validate
            allowed_schemes: List of allowed URL schemes

        Returns:
            Validated URL

        Raises:
            InvalidRequestDataError: If URL is invalid
        """
        if not url:
            raise InvalidRequestDataError(
                message="URL is required",
                context={'field': 'url'}
            )

        if allowed_schemes is None:
            allowed_schemes = ['http', 'https']

        try:
            url = url.strip()
            validator = URLValidator(schemes=allowed_schemes)
            validator(url)

            # Additional security checks
            if len(url) > 2048:  # Common browser limit
                raise InvalidRequestDataError(
                    message="URL too long",
                    context={'url_length': len(url), 'max_length': 2048}
                )

            return url

        except ValidationError as e:
            raise InvalidRequestDataError(
                message=f"Invalid URL format: {str(e)}",
                context={'url': url[:100], 'validation_error': str(e)},
                cause=e
            )

    @classmethod
    def validate_integer(
        cls,
        value: Union[int, str],
        min_value: Optional[int] = None,
        max_value: Optional[int] = None,
        field_name: str = "value"
    ) -> int:
        """
        Validate and convert value to integer.

        Args:
            value: Value to validate
            min_value: Minimum allowed value
            max_value: Maximum allowed value
            field_name: Name of the field for error reporting

        Returns:
            Validated integer value

        Raises:
            InvalidRequestDataError: If value is invalid
        """
        try:
            if isinstance(value, str):
                value = value.strip()
                if not value:
                    raise InvalidRequestDataError(
                        message=f"{field_name} cannot be empty",
                        context={'field': field_name}
                    )

            int_value = int(value)

            if min_value is not None and int_value < min_value:
                raise InvalidRequestDataError(
                    message=f"{field_name} must be at least {min_value}",
                    context={'field': field_name, 'value': int_value, 'min_value': min_value}
                )

            if max_value is not None and int_value > max_value:
                raise InvalidRequestDataError(
                    message=f"{field_name} must be at most {max_value}",
                    context={'field': field_name, 'value': int_value, 'max_value': max_value}
                )

            return int_value

        except (ValueError, TypeError) as e:
            raise InvalidRequestDataError(
                message=f"Invalid integer value for {field_name}",
                context={'field': field_name, 'value': str(value)[:50], 'error': str(e)},
                cause=e
            )

    @classmethod
    def validate_float(
        cls,
        value: Union[float, str],
        min_value: Optional[float] = None,
        max_value: Optional[float] = None,
        field_name: str = "value"
    ) -> float:
        """
        Validate and convert value to float.

        Args:
            value: Value to validate
            min_value: Minimum allowed value
            max_value: Maximum allowed value
            field_name: Name of the field for error reporting

        Returns:
            Validated float value

        Raises:
            InvalidRequestDataError: If value is invalid
        """
        try:
            if isinstance(value, str):
                value = value.strip()
                if not value:
                    raise InvalidRequestDataError(
                        message=f"{field_name} cannot be empty",
                        context={'field': field_name}
                    )

            float_value = float(value)

            # Check for NaN and infinity
            if not (float_value == float_value):  # NaN check
                raise InvalidRequestDataError(
                    message=f"{field_name} cannot be NaN",
                    context={'field': field_name}
                )

            if float_value == float('inf') or float_value == float('-inf'):
                raise InvalidRequestDataError(
                    message=f"{field_name} cannot be infinite",
                    context={'field': field_name}
                )

            if min_value is not None and float_value < min_value:
                raise InvalidRequestDataError(
                    message=f"{field_name} must be at least {min_value}",
                    context={'field': field_name, 'value': float_value, 'min_value': min_value}
                )

            if max_value is not None and float_value > max_value:
                raise InvalidRequestDataError(
                    message=f"{field_name} must be at most {max_value}",
                    context={'field': field_name, 'value': float_value, 'max_value': max_value}
                )

            return float_value

        except (ValueError, TypeError) as e:
            raise InvalidRequestDataError(
                message=f"Invalid float value for {field_name}",
                context={'field': field_name, 'value': str(value)[:50], 'error': str(e)},
                cause=e
            )

    @classmethod
    def validate_boolean(cls, value: Union[bool, str, int], field_name: str = "value") -> bool:
        """
        Validate and convert value to boolean.

        Args:
            value: Value to validate
            field_name: Name of the field for error reporting

        Returns:
            Validated boolean value

        Raises:
            InvalidRequestDataError: If value is invalid
        """
        if isinstance(value, bool):
            return value

        if isinstance(value, str):
            value = value.strip().lower()
            if value in ('true', '1', 'yes', 'on'):
                return True
            elif value in ('false', '0', 'no', 'off', ''):
                return False

        if isinstance(value, int):
            return bool(value)

        raise InvalidRequestDataError(
            message=f"Invalid boolean value for {field_name}",
            context={'field': field_name, 'value': str(value)[:50]}
        )

    @classmethod
    def validate_choice(
        cls,
        value: str,
        choices: List[str],
        field_name: str = "value",
        case_sensitive: bool = True
    ) -> str:
        """
        Validate that value is one of allowed choices.

        Args:
            value: Value to validate
            choices: List of allowed choices
            field_name: Name of the field for error reporting
            case_sensitive: Whether comparison should be case sensitive

        Returns:
            Validated choice value

        Raises:
            InvalidRequestDataError: If value is not in choices
        """
        if not isinstance(value, str):
            value = str(value)

        value = value.strip()

        if not case_sensitive:
            value = value.lower()
            choices = [choice.lower() for choice in choices]

        if value not in choices:
            raise InvalidRequestDataError(
                message=f"Invalid choice for {field_name}",
                context={
                    'field': field_name,
                    'value': value,
                    'allowed_choices': choices[:10]  # Limit choices in error for security
                }
            )

        return value

    @classmethod
    def validate_date(cls, date_string: str, field_name: str = "date") -> date:
        """
        Validate date string in ISO format.

        Args:
            date_string: Date string to validate (YYYY-MM-DD)
            field_name: Name of the field for error reporting

        Returns:
            Validated date object

        Raises:
            InvalidRequestDataError: If date is invalid
        """
        try:
            if not date_string:
                raise InvalidRequestDataError(
                    message=f"{field_name} is required",
                    context={'field': field_name}
                )

            date_string = date_string.strip()

            # Parse ISO date format
            parsed_date = datetime.strptime(date_string, '%Y-%m-%d').date()

            # Additional validation
            current_year = datetime.now().year
            if parsed_date.year < 1900 or parsed_date.year > current_year + 10:
                raise InvalidRequestDataError(
                    message=f"Invalid year for {field_name}",
                    context={'field': field_name, 'year': parsed_date.year}
                )

            return parsed_date

        except ValueError as e:
            raise InvalidRequestDataError(
                message=f"Invalid date format for {field_name}. Use YYYY-MM-DD",
                context={'field': field_name, 'value': date_string, 'error': str(e)},
                cause=e
            )

    @classmethod
    def validate_time(cls, time_string: str, field_name: str = "time") -> time:
        """
        Validate time string in HH:MM format.

        Args:
            time_string: Time string to validate
            field_name: Name of the field for error reporting

        Returns:
            Validated time object

        Raises:
            InvalidRequestDataError: If time is invalid
        """
        try:
            if not time_string:
                raise InvalidRequestDataError(
                    message=f"{field_name} is required",
                    context={'field': field_name}
                )

            time_string = time_string.strip()

            # Parse time format HH:MM or HH:MM:SS
            if ':' not in time_string:
                raise ValueError("Time must include colon separator")

            parts = time_string.split(':')
            if len(parts) == 2:
                time_string += ':00'  # Add seconds if not provided
            elif len(parts) != 3:
                raise ValueError("Invalid time format")

            parsed_time = datetime.strptime(time_string, '%H:%M:%S').time()
            return parsed_time

        except ValueError as e:
            raise InvalidRequestDataError(
                message=f"Invalid time format for {field_name}. Use HH:MM or HH:MM:SS",
                context={'field': field_name, 'value': time_string, 'error': str(e)},
                cause=e
            )

    @classmethod
    def validate_pattern(cls, value: str, pattern_name: str, field_name: str = "value") -> str:
        """
        Validate value against a predefined pattern.

        Args:
            value: Value to validate
            pattern_name: Name of the pattern to use
            field_name: Name of the field for error reporting

        Returns:
            Validated value

        Raises:
            InvalidRequestDataError: If value doesn't match pattern
        """
        if pattern_name not in cls.PATTERNS:
            raise InvalidRequestDataError(
                message=f"Unknown validation pattern: {pattern_name}",
                context={'pattern_name': pattern_name}
            )

        if not isinstance(value, str):
            value = str(value)

        value = value.strip()

        if not cls.PATTERNS[pattern_name].match(value):
            raise InvalidRequestDataError(
                message=f"Invalid format for {field_name}",
                context={'field': field_name, 'pattern': pattern_name, 'value': value[:50]}
            )

        return value

    @classmethod
    def sanitize_data_dict(cls, data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Recursively sanitize all string values in a dictionary.

        Args:
            data: Dictionary to sanitize

        Returns:
            Sanitized dictionary
        """
        sanitized = {}

        for key, value in data.items():
            # Sanitize the key itself
            clean_key = cls.sanitize_string(str(key), max_length=100)

            if isinstance(value, str):
                sanitized[clean_key] = cls.sanitize_string(value, max_length=1000)
            elif isinstance(value, dict):
                sanitized[clean_key] = cls.sanitize_data_dict(value)
            elif isinstance(value, list):
                sanitized[clean_key] = [
                    cls.sanitize_string(item, max_length=1000) if isinstance(item, str) else item
                    for item in value[:100]  # Limit list size
                ]
            else:
                sanitized[clean_key] = value

        return sanitized


class SecurityValidator:
    """
    Security-focused validation utilities.
    """

    @staticmethod
    def check_sql_injection_patterns(value: str) -> bool:
        """
        Check for common SQL injection patterns.

        Args:
            value: String to check

        Returns:
            True if potentially dangerous patterns found
        """
        if not isinstance(value, str):
            return False

        # Common SQL injection patterns
        dangerous_patterns = [
            r"(\b(union|select|insert|update|delete|drop|create|alter|exec|execute)\b)",
            r"(--|\/\*|\*\/|;)",
            r"(\bor\b.*\b1\s*=\s*1\b)",
            r"(\band\b.*\b1\s*=\s*1\b)",
            r"(\bxp_cmdshell\b)",
            r"(\bsp_executesql\b)",
        ]

        value_lower = value.lower()
        for pattern in dangerous_patterns:
            if re.search(pattern, value_lower, re.IGNORECASE):
                logger.warning(f"Potential SQL injection detected: {pattern}")
                return True

        return False

    @staticmethod
    def check_xss_patterns(value: str) -> bool:
        """
        Check for common XSS patterns.

        Args:
            value: String to check

        Returns:
            True if potentially dangerous patterns found
        """
        if not isinstance(value, str):
            return False

        # Common XSS patterns
        dangerous_patterns = [
            r"<script[^>]*>",
            r"javascript:",
            r"on\w+\s*=",
            r"<iframe[^>]*>",
            r"<object[^>]*>",
            r"<embed[^>]*>",
            r"vbscript:",
            r"data:text/html",
        ]

        value_lower = value.lower()
        for pattern in dangerous_patterns:
            if re.search(pattern, value_lower, re.IGNORECASE):
                logger.warning(f"Potential XSS detected: {pattern}")
                return True

        return False

    @staticmethod
    def validate_file_upload(
        file_data: bytes,
        allowed_types: List[str],
        max_size: int = 5 * 1024 * 1024  # 5MB default
    ) -> Tuple[bool, str]:
        """
        Validate uploaded file data.

        Args:
            file_data: Raw file data
            allowed_types: List of allowed MIME types
            max_size: Maximum file size in bytes

        Returns:
            Tuple of (is_valid, error_message)
        """
        try:
            import magic

            # Check file size
            if len(file_data) > max_size:
                return False, f"File too large. Maximum size: {max_size // (1024*1024)}MB"

            # Check MIME type
            mime_type = magic.from_buffer(file_data, mime=True)
            if mime_type not in allowed_types:
                return False, f"File type not allowed. Allowed types: {', '.join(allowed_types)}"

            # Additional security checks
            if b'<?php' in file_data[:1024]:
                return False, "PHP code detected in file"

            if b'<script' in file_data[:1024]:
                return False, "Script tags detected in file"

            return True, "File is valid"

        except ImportError:
            logger.warning("python-magic not available for file type detection")
            return True, "File validation skipped"
        except Exception as e:
            logger.error(f"File validation error: {e}")
            return False, "File validation failed"