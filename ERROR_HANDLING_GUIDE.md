# Error Handling Framework Documentation

## Overview

The EyeHealth 20-20-20 SaaS application implements a comprehensive error handling framework that provides:

- Standardized exception hierarchy
- Consistent error response formats
- Security-focused error sanitization
- Comprehensive logging and monitoring
- User-friendly error pages
- Developer-friendly debugging tools

## Architecture

### Exception Hierarchy

```
BaseApplicationError
├── TimerError
│   ├── SessionCreationError
│   ├── SessionNotFoundError
│   ├── SessionAlreadyActiveError
│   ├── SessionNotActiveError
│   ├── IntervalNotFoundError
│   ├── IntervalStateError
│   └── DailyLimitExceededError
├── BreakError
│   ├── BreakCreationError
│   ├── BreakNotFoundError
│   ├── BreakAlreadyCompletedError
│   └── BreakValidationError
├── AnalyticsError
│   ├── DataCalculationError
│   ├── InsufficientDataError
│   └── MetricsUpdateError
├── GamificationError
│   ├── AchievementError
│   ├── LevelProgressError
│   ├── BadgeError
│   └── ChallengeError
├── UserError
│   ├── UserNotFoundError
│   ├── UserNotAuthenticatedError
│   ├── InsufficientPermissionsError
│   ├── PremiumFeatureError
│   └── ProfileUpdateError
├── APIError
│   ├── InvalidRequestDataError
│   ├── MissingRequiredFieldError
│   ├── InvalidJSONError
│   └── RequestTooLargeError
├── RateLimitError
│   ├── APIRateLimitError
│   └── UserActionRateLimitError
├── ExternalServiceError
│   ├── PaymentServiceError
│   ├── EmailServiceError
│   └── CalendarServiceError
└── BusinessLogicError
    ├── SubscriptionError
    ├── SettingsValidationError
    └── DataIntegrityError
```

### Core Components

1. **Exception Classes** (`mysite/exceptions.py`)
   - Standardized exception hierarchy
   - Built-in logging and context management
   - Security-focused error message sanitization

2. **Error Handling Middleware** (`mysite/middleware.py`)
   - Comprehensive error processing
   - API vs web request differentiation
   - Security headers and CORS handling

3. **Decorators** (`mysite/decorators.py`)
   - Common error handling patterns
   - Authentication and authorization checks
   - Rate limiting and validation

4. **Monitoring System** (`mysite/monitoring.py`)
   - Error tracking and metrics
   - Performance monitoring
   - Health checks and alerting

5. **Validation Framework** (`mysite/validation.py`)
   - Input validation and sanitization
   - Security vulnerability prevention
   - Type conversion and format validation

## Usage Guide

### 1. Raising Exceptions

```python
# Service layer example
from mysite.exceptions import SessionCreationError, get_error_context

def create_session(user):
    try:
        # Business logic here
        pass
    except Exception as e:
        raise SessionCreationError(
            message=f"Failed to create session for user {user.email}",
            context={
                'user_id': user.id,
                'error_details': str(e)
            },
            cause=e
        )
```

### 2. Using Decorators

```python
# API view with comprehensive error handling
from mysite.decorators import api_view

@api_view(
    authentication_required=True,
    required_fields=['session_id', 'interval_id'],
    rate_limit='20/m',
    use_transaction=True,
    log_calls=True
)
def take_break_view(request):
    data = request.validated_data
    # Business logic here
    return {'success': True, 'data': result}
```

### 3. Service Layer Pattern

```python
# Timer service with proper error handling
from mysite.exceptions import TimerError, SessionNotFoundError

class TimerSessionService:
    @staticmethod
    def get_active_session(user):
        try:
            return TimerSession.objects.filter(
                user=user,
                is_active=True
            ).first()
        except Exception as e:
            raise SessionNotFoundError(
                message=f"Failed to get active session for user {user.email}",
                context={'user_id': user.id, 'error_details': str(e)},
                cause=e
            )
```

### 4. Input Validation

```python
from mysite.validation import InputValidator
from mysite.exceptions import InvalidRequestDataError

# Validate and sanitize input
try:
    data = InputValidator.validate_json_data(request.body)
    InputValidator.validate_required_fields(data, ['email', 'password'])

    email = InputValidator.validate_email_address(data['email'])
    age = InputValidator.validate_integer(data.get('age'), min_value=13, max_value=120)

except Exception as e:
    # Appropriate exception is raised automatically
    raise
```

### 5. Custom Error Pages

Error pages are automatically rendered based on request type:

- **API Requests**: JSON responses with standardized format
- **Web Requests**: HTML templates with user-friendly messages

Templates located in `templates/errors/`:
- `403.html` - Permission denied
- `404.html` - Page not found
- `500.html` - Server error
- `rate_limit.html` - Rate limit exceeded
- `service_unavailable.html` - Service unavailable

### 6. Monitoring and Alerting

```python
from mysite.monitoring import error_monitor, health_checker

# Error monitoring is automatic, but you can also record manually
error_monitor.record_error(
    error=exception,
    user_id=user.id,
    request_path=request.path,
    additional_context={'custom_data': 'value'}
)

# Health checks
health_status = health_checker.get_overall_health()
```

## Configuration

### Settings Configuration

Add to `settings.py`:

```python
# Error Handling Configuration
SUPPORT_EMAIL = 'support@eyehealth2020.com'
ERROR_REPORTING_ENABLED = True

# API Configuration
API_DEFAULT_RATE_LIMIT = '100/h'
API_AUTHENTICATED_RATE_LIMIT = '1000/h'
API_PREMIUM_RATE_LIMIT = '5000/h'

# Error Pages Configuration
ERROR_PAGE_TEMPLATES = {
    400: 'errors/error.html',
    403: 'errors/403.html',
    404: 'errors/404.html',
    429: 'errors/rate_limit.html',
    500: 'errors/500.html',
    503: 'errors/service_unavailable.html',
}
```

### Middleware Order

Ensure proper middleware order in `settings.py`:

```python
MIDDLEWARE = [
    'django.middleware.security.SecurityMiddleware',
    'whitenoise.middleware.WhiteNoiseMiddleware',
    'corsheaders.middleware.CorsMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'axes.middleware.AxesMiddleware',
    'accounts.middleware.TimezoneMiddleware',
    'csp.middleware.CSPMiddleware',
    'mysite.middleware.RequestLoggingMiddleware',
    'mysite.middleware.SecurityHeadersMiddleware',
    'mysite.middleware.ErrorHandlingMiddleware',
    'mysite.middleware.APIErrorResponseMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
]
```

### URL Configuration

Add to main `urls.py`:

```python
# Custom error handlers
handler400 = 'mysite.error_views.bad_request'
handler403 = 'mysite.error_views.permission_denied'
handler404 = 'mysite.error_views.page_not_found'
handler500 = 'mysite.error_views.server_error'

# Health monitoring
urlpatterns = [
    # ... other patterns ...
    path('health/', include('mysite.health_urls')),
]
```

## Error Response Formats

### API Error Response

```json
{
  "success": false,
  "error_code": "SESSION_NOT_FOUND",
  "message": "Timer session not found",
  "details": {
    "user_id": 123,
    "session_id": 456
  },
  "timestamp": "2024-01-15T10:30:00Z"
}
```

### Validation Error Response

```json
{
  "success": false,
  "error_code": "MISSING_REQUIRED_FIELD",
  "message": "Missing required fields: email, password",
  "details": {
    "missing_fields": ["email", "password"],
    "provided_fields": ["username"]
  },
  "timestamp": "2024-01-15T10:30:00Z"
}
```

## Security Considerations

### 1. Error Message Sanitization

- Sensitive information is automatically removed from error messages
- Stack traces are only shown in DEBUG mode
- User-facing messages are generic and safe

### 2. Rate Limiting

- Automatic rate limiting on all API endpoints
- Configurable limits based on user type
- Proper error responses for rate limit violations

### 3. Input Validation

- Comprehensive input sanitization
- SQL injection prevention
- XSS attack prevention
- File upload validation

### 4. Logging Security

- Structured logging with context
- Sensitive data filtering
- Separate error log files
- Automated log rotation

## Monitoring and Alerting

### Health Check Endpoints

- `/health/` - Basic health check for load balancers
- `/health/detailed/` - Comprehensive health information (admin only)
- `/health/errors/` - Error metrics (admin only)
- `/health/performance/` - Performance metrics (admin only)
- `/health/status/` - Web dashboard (admin only)

### Automated Alerting

The system automatically sends alerts when:

- Error frequency exceeds thresholds
- Critical errors occur multiple times
- System health checks fail
- Performance degrades significantly

### Metrics Collection

- Error counts and patterns
- Response time measurements
- User impact analysis
- System resource utilization

## Best Practices

### 1. Service Layer Error Handling

```python
# DO: Use specific exceptions with context
raise SessionCreationError(
    message="Failed to create session",
    context={'user_id': user.id, 'reason': 'daily_limit_exceeded'},
    cause=original_exception
)

# DON'T: Use generic exceptions
raise Exception("Something went wrong")
```

### 2. Controller Layer

```python
# DO: Use decorators for common patterns
@api_view(authentication_required=True, required_fields=['data'])
def my_view(request):
    # Business logic here
    return {'success': True}

# DON'T: Manual error handling in every view
def my_view(request):
    try:
        if not request.user.is_authenticated:
            return JsonResponse({'error': 'Not authenticated'}, status=401)
        # ... more boilerplate
    except Exception as e:
        return JsonResponse({'error': str(e)}, status=500)
```

### 3. Error Context

```python
# DO: Provide useful context
context = {
    'user_id': user.id,
    'session_id': session.id,
    'operation': 'create_break',
    'timestamp': timezone.now().isoformat()
}

# DON'T: Include sensitive information
context = {
    'password': user_password,  # ❌ Security risk
    'api_key': secret_key       # ❌ Security risk
}
```

### 4. User Messages

```python
# DO: User-friendly messages
user_message = "Your session could not be started. Please try again."

# DON'T: Technical details to users
user_message = "DatabaseError: relation 'timer_session' does not exist"
```

## Testing Error Handling

### Unit Tests

```python
from mysite.exceptions import SessionCreationError
from mysite.decorators import api_error_handler

class TestErrorHandling(TestCase):
    def test_session_creation_error(self):
        with self.assertRaises(SessionCreationError) as cm:
            # Code that should raise the exception
            pass

        self.assertEqual(cm.exception.error_code, 'SESSION_CREATION_FAILED')
        self.assertIn('user_id', cm.exception.context)

    def test_api_error_response(self):
        response = self.client.post('/api/invalid-endpoint/')
        self.assertEqual(response.status_code, 404)
        data = response.json()
        self.assertFalse(data['success'])
        self.assertEqual(data['error_code'], 'NOT_FOUND')
```

### Integration Tests

```python
class TestErrorPagesIntegration(TestCase):
    def test_404_page_rendering(self):
        response = self.client.get('/nonexistent-page/')
        self.assertEqual(response.status_code, 404)
        self.assertContains(response, '404', status_code=404)
        self.assertTemplateUsed(response, 'errors/404.html')

    def test_api_404_response(self):
        response = self.client.get(
            '/api/nonexistent-endpoint/',
            HTTP_ACCEPT='application/json'
        )
        self.assertEqual(response.status_code, 404)
        data = response.json()
        self.assertEqual(data['error_code'], 'NOT_FOUND')
```

## Troubleshooting

### Common Issues

1. **Middleware Order**: Ensure error handling middleware is in the correct position
2. **Template Not Found**: Check that error templates exist in `templates/errors/`
3. **Missing Context**: Ensure error context is properly passed to templates
4. **Rate Limiting**: Check rate limit configuration for API endpoints

### Debug Mode Considerations

In DEBUG mode:
- Full stack traces are shown
- Error details are included in responses
- Additional logging is enabled
- Security restrictions are relaxed

In production:
- Generic error messages only
- Stack traces are hidden
- Sensitive information is filtered
- Enhanced security measures

### Log Analysis

Monitor logs for:
- Error frequency patterns
- User impact analysis
- Performance degradation
- Security incidents

## Extending the Framework

### Adding New Exception Types

1. Create exception class inheriting from appropriate base class
2. Add specific error code and user message
3. Update documentation
4. Add unit tests

### Custom Error Pages

1. Create template in `templates/errors/`
2. Update `ERROR_PAGE_TEMPLATES` setting
3. Add context variables as needed
4. Test rendering and user experience

### Additional Monitoring

1. Register new health checks with `health_checker`
2. Add custom metrics to monitoring system
3. Configure alerting rules
4. Update monitoring dashboard

This error handling framework provides a robust foundation for maintaining system reliability while ensuring excellent user experience and developer productivity.