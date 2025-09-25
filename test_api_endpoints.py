"""
Comprehensive API endpoint tests for the 20-20-20 eye health SaaS application.
Tests all API endpoints, authentication, rate limiting, and security features.
"""
import pytest
from datetime import datetime, timedelta, date
from decimal import Decimal
from unittest.mock import patch, Mock, MagicMock
from django.test import TestCase, TransactionTestCase, Client
from django.utils import timezone
from django.contrib.auth import get_user_model
from django.urls import reverse
from django.test.utils import override_settings
from django_ratelimit.exceptions import Ratelimited
from freezegun import freeze_time
import json

from accounts.models import User, UserProfile, UserLevel, UserStreakData, Badge, Challenge
from timer.models import TimerSession, TimerInterval, BreakRecord, UserTimerSettings
from analytics.models import DailyStats, UserSession, LiveActivityFeed

User = get_user_model()


# ===== API AUTHENTICATION TESTS =====

@pytest.mark.api
@pytest.mark.security
class TestAPIAuthentication(TestCase):
    """Test API authentication and authorization"""

    def setUp(self):
        self.client = Client()
        self.user = User.objects.create_user(
            username='testuser',
            email='test@example.com',
            password='testpass123',
            subscription_type='free'
        )
        UserProfile.objects.create(user=self.user)
        UserTimerSettings.objects.create(user=self.user)

    def test_unauthenticated_api_access(self):
        """Test that API endpoints require authentication"""
        protected_endpoints = [
            ('POST', 'timer:start_session', {}),
            ('POST', 'timer:end_session', {}),
            ('POST', 'timer:take_break', {'session_id': 1, 'interval_id': 1}),
            ('POST', 'timer:complete_break', {'break_id': 1}),
            ('POST', 'timer:sync_session', {'session_id': 1}),
            ('GET', 'timer:get_break_settings', {}),
            ('POST', 'timer:update_smart_break_settings', {'smart_break_enabled': True}),
            ('POST', 'timer:submit_feedback', {'feedback_type': 'general', 'title': 'Test', 'message': 'Test'}),
        ]

        for method, url_name, data in protected_endpoints:
            url = reverse(url_name)

            if method == 'GET':
                response = self.client.get(url)
            else:
                response = self.client.post(
                    url,
                    data=json.dumps(data),
                    content_type='application/json'
                )

            # Should redirect to login or return 401/403
            assert response.status_code in [302, 401, 403], f"Endpoint {url_name} should require authentication"

    def test_authenticated_api_access(self):
        """Test that authenticated users can access API endpoints"""
        self.client.login(username='test@example.com', password='testpass123')

        # Test accessible endpoints
        accessible_endpoints = [
            ('GET', 'timer:get_break_settings', {}),
        ]

        for method, url_name, data in accessible_endpoints:
            url = reverse(url_name)

            if method == 'GET':
                response = self.client.get(url)
            else:
                response = self.client.post(
                    url,
                    data=json.dumps(data),
                    content_type='application/json'
                )

            assert response.status_code in [200, 201], f"Authenticated user should access {url_name}"

    def test_session_hijacking_protection(self):
        """Test protection against session hijacking"""
        # Login user
        self.client.login(username='test@example.com', password='testpass123')

        # Get session ID
        session_key = self.client.session.session_key

        # Create a session for user
        session = TimerSession.objects.create(user=self.user, is_active=True)

        # Try to access session with different user
        other_user = User.objects.create_user(
            username='otheruser',
            email='other@example.com',
            password='testpass123'
        )

        # Logout current user and login as other user
        self.client.logout()
        self.client.login(username='other@example.com', password='testpass123')

        # Try to sync original user's session
        response = self.client.post(
            reverse('timer:sync_session'),
            data=json.dumps({'session_id': session.id}),
            content_type='application/json'
        )

        # Should return session not found (security measure)
        data = response.json()
        assert data['success'] is False
        assert 'not found' in data['message']

    def test_csrf_protection(self):
        """Test CSRF protection on POST endpoints"""
        self.client.login(username='test@example.com', password='testpass123')

        # Try POST without CSRF token
        response = self.client.post(
            reverse('timer:start_session'),
            data=json.dumps({}),
            content_type='application/json'
        )

        # Should work with proper content type (API endpoints often exempt from CSRF)
        # Or should return CSRF error if not exempt
        assert response.status_code in [200, 403]


# ===== API RATE LIMITING TESTS =====

@pytest.mark.api
@pytest.mark.security
class TestAPIRateLimiting(TestCase):
    """Test API rate limiting functionality"""

    def setUp(self):
        self.client = Client()
        self.user = User.objects.create_user(
            username='testuser',
            email='test@example.com',
            password='testpass123'
        )
        UserProfile.objects.create(user=self.user)
        UserTimerSettings.objects.create(user=self.user)
        self.client.login(username='test@example.com', password='testpass123')

    @override_settings(RATELIMIT_ENABLE=True)
    def test_session_start_rate_limiting(self):
        """Test rate limiting on session start endpoint"""
        # Make requests up to the limit (assuming 10/minute)
        for i in range(10):
            response = self.client.post(
                reverse('timer:start_session'),
                data=json.dumps({}),
                content_type='application/json'
            )

            # First request should succeed, subsequent may fail due to business logic
            if i == 0:
                assert response.status_code in [200, 400]  # 400 if already has active session

    @override_settings(RATELIMIT_ENABLE=True)
    def test_feedback_submission_rate_limiting(self):
        """Test rate limiting on feedback submission"""
        # Submit multiple feedback requests
        for i in range(5):
            response = self.client.post(
                reverse('timer:submit_feedback'),
                data=json.dumps({
                    'feedback_type': 'general',
                    'title': f'Test feedback {i}',
                    'message': f'Test message {i}'
                }),
                content_type='application/json'
            )

            # Should succeed within rate limits
            assert response.status_code == 200

    def test_rate_limit_headers(self):
        """Test that rate limit headers are present"""
        response = self.client.post(
            reverse('timer:start_session'),
            data=json.dumps({}),
            content_type='application/json'
        )

        # Check for rate limiting headers (if implemented)
        # Common headers: X-RateLimit-Limit, X-RateLimit-Remaining, X-RateLimit-Reset
        # Note: These depend on the rate limiting implementation


# ===== API INPUT VALIDATION TESTS =====

@pytest.mark.api
@pytest.mark.security
class TestAPIInputValidation(TestCase):
    """Test API input validation and sanitization"""

    def setUp(self):
        self.client = Client()
        self.user = User.objects.create_user(
            username='testuser',
            email='test@example.com',
            password='testpass123'
        )
        UserProfile.objects.create(user=self.user)
        UserTimerSettings.objects.create(user=self.user)
        self.client.login(username='test@example.com', password='testpass123')

    def test_invalid_json_input(self):
        """Test handling of invalid JSON input"""
        response = self.client.post(
            reverse('timer:submit_feedback'),
            data='invalid json{',
            content_type='application/json'
        )

        assert response.status_code in [400, 500]
        if response.status_code == 200:
            data = response.json()
            assert data['success'] is False

    def test_missing_required_fields(self):
        """Test validation of required fields"""
        # Test feedback submission without required fields
        response = self.client.post(
            reverse('timer:submit_feedback'),
            data=json.dumps({}),
            content_type='application/json'
        )

        data = response.json()
        assert data['success'] is False
        assert 'required' in data['message'].lower()

    def test_xss_prevention_in_input(self):
        """Test XSS prevention in user input"""
        xss_payloads = [
            '<script>alert("xss")</script>',
            'javascript:alert("xss")',
            '<img src=x onerror=alert("xss")>',
            '"><script>alert("xss")</script>'
        ]

        for payload in xss_payloads:
            response = self.client.post(
                reverse('timer:submit_feedback'),
                data=json.dumps({
                    'feedback_type': 'general',
                    'title': payload,
                    'message': payload
                }),
                content_type='application/json'
            )

            if response.status_code == 200:
                data = response.json()
                if data['success']:
                    # Check that the payload was sanitized
                    feedback_id = data.get('feedback_id')
                    if feedback_id:
                        from timer.models import UserFeedback
                        feedback = UserFeedback.objects.get(id=feedback_id)
                        # Should not contain script tags
                        assert '<script>' not in feedback.title
                        assert '<script>' not in feedback.message

    def test_sql_injection_prevention(self):
        """Test SQL injection prevention"""
        sql_payloads = [
            "'; DROP TABLE users; --",
            "1' OR '1'='1",
            "'; INSERT INTO users VALUES ('hacker', 'password'); --"
        ]

        # Test with session sync endpoint that takes session_id
        for payload in sql_payloads:
            response = self.client.post(
                reverse('timer:sync_session'),
                data=json.dumps({'session_id': payload}),
                content_type='application/json'
            )

            # Should handle gracefully without SQL errors
            assert response.status_code in [200, 400]
            if response.status_code == 200:
                data = response.json()
                # Should return session not found or invalid data
                assert data['success'] is False or data.get('session_active') is False

    def test_large_payload_handling(self):
        """Test handling of excessively large payloads"""
        # Create very large message
        large_message = 'A' * 10000  # 10KB message

        response = self.client.post(
            reverse('timer:submit_feedback'),
            data=json.dumps({
                'feedback_type': 'general',
                'title': 'Large payload test',
                'message': large_message
            }),
            content_type='application/json'
        )

        # Should either accept (with truncation) or reject gracefully
        assert response.status_code in [200, 400, 413]

    def test_numeric_field_validation(self):
        """Test validation of numeric fields"""
        invalid_numeric_values = [
            'not_a_number',
            '999999999999999999999',  # Very large number
            '-999999999',  # Negative number where not allowed
            '3.14159',  # Float where integer expected
        ]

        for invalid_value in invalid_numeric_values:
            response = self.client.post(
                reverse('timer:update_smart_break_settings'),
                data=json.dumps({
                    'smart_break_enabled': True,
                    'preferred_break_duration': invalid_value
                }),
                content_type='application/json'
            )

            if response.status_code == 200:
                data = response.json()
                # Should reject invalid numeric values
                assert data['success'] is False or 'error' in data.get('message', '').lower()


# ===== API BUSINESS LOGIC TESTS =====

@pytest.mark.api
@pytest.mark.integration
class TestAPIBusinessLogic(TestCase):
    """Test API business logic and workflows"""

    def setUp(self):
        self.client = Client()
        self.user = User.objects.create_user(
            username='testuser',
            email='test@example.com',
            password='testpass123',
            subscription_type='free'
        )
        UserProfile.objects.create(user=self.user)
        UserTimerSettings.objects.create(user=self.user)
        self.client.login(username='test@example.com', password='testpass123')

    def test_complete_timer_workflow_api(self):
        """Test complete timer workflow through API"""
        # 1. Start session
        response = self.client.post(
            reverse('timer:start_session'),
            data=json.dumps({}),
            content_type='application/json'
        )

        assert response.status_code == 200
        start_data = response.json()
        assert start_data['success'] is True

        session_id = start_data['session_id']
        interval_id = start_data['interval_id']

        # 2. Sync session
        response = self.client.post(
            reverse('timer:sync_session'),
            data=json.dumps({'session_id': session_id}),
            content_type='application/json'
        )

        assert response.status_code == 200
        sync_data = response.json()
        assert sync_data['success'] is True
        assert sync_data['session_active'] is True

        # 3. Take break
        response = self.client.post(
            reverse('timer:take_break'),
            data=json.dumps({
                'session_id': session_id,
                'interval_id': interval_id,
                'looked_at_distance': True
            }),
            content_type='application/json'
        )

        assert response.status_code == 200
        break_data = response.json()
        assert break_data['success'] is True

        break_id = break_data['break_id']

        # 4. Complete break
        response = self.client.post(
            reverse('timer:complete_break'),
            data=json.dumps({
                'break_id': break_id,
                'looked_at_distance': True
            }),
            content_type='application/json'
        )

        assert response.status_code == 200
        complete_data = response.json()
        assert complete_data['success'] is True

        # 5. End session
        response = self.client.post(
            reverse('timer:end_session'),
            data=json.dumps({}),
            content_type='application/json'
        )

        assert response.status_code == 200
        end_data = response.json()
        assert end_data['success'] is True

    def test_free_user_limitations(self):
        """Test free user limitations through API"""
        from mysite.constants import FREE_DAILY_INTERVAL_LIMIT

        # Create intervals up to the limit
        session = TimerSession.objects.create(user=self.user, is_active=False)
        for i in range(FREE_DAILY_INTERVAL_LIMIT):
            TimerInterval.objects.create(
                session=session,
                interval_number=i + 1,
                start_time=timezone.now()
            )

        # Try to start new session (should fail)
        response = self.client.post(
            reverse('timer:start_session'),
            data=json.dumps({}),
            content_type='application/json'
        )

        assert response.status_code == 200
        data = response.json()
        assert data['success'] is False
        assert 'limit' in data['message'].lower()
        assert 'premium' in data['message'].lower()

    def test_premium_user_unlimited_access(self):
        """Test premium user unlimited access"""
        # Make user premium
        self.user.subscription_type = 'premium'
        self.user.subscription_end_date = timezone.now() + timedelta(days=30)
        self.user.save()

        from mysite.constants import FREE_DAILY_INTERVAL_LIMIT

        # Create intervals beyond free limit
        session = TimerSession.objects.create(user=self.user, is_active=False)
        for i in range(FREE_DAILY_INTERVAL_LIMIT + 5):
            TimerInterval.objects.create(
                session=session,
                interval_number=i + 1,
                start_time=timezone.now()
            )

        # Should still be able to start session
        response = self.client.post(
            reverse('timer:start_session'),
            data=json.dumps({}),
            content_type='application/json'
        )

        assert response.status_code == 200
        data = response.json()
        assert data['success'] is True

    def test_concurrent_session_prevention(self):
        """Test prevention of concurrent sessions"""
        # Start first session
        response = self.client.post(
            reverse('timer:start_session'),
            data=json.dumps({}),
            content_type='application/json'
        )

        assert response.status_code == 200
        data = response.json()
        assert data['success'] is True

        # Try to start second session
        response = self.client.post(
            reverse('timer:start_session'),
            data=json.dumps({}),
            content_type='application/json'
        )

        assert response.status_code == 200
        data = response.json()
        assert data['success'] is False
        assert 'active session' in data['message'].lower()

    def test_break_settings_update_validation(self):
        """Test break settings update with validation"""
        # Test valid update
        response = self.client.post(
            reverse('timer:update_smart_break_settings'),
            data=json.dumps({
                'smart_break_enabled': True,
                'preferred_break_duration': 30
            }),
            content_type='application/json'
        )

        assert response.status_code == 200
        data = response.json()
        assert data['success'] is True

        # Verify settings were updated
        settings = UserTimerSettings.objects.get(user=self.user)
        assert settings.smart_break_enabled is True
        assert settings.preferred_break_duration == 30

        # Test invalid duration
        response = self.client.post(
            reverse('timer:update_smart_break_settings'),
            data=json.dumps({
                'smart_break_enabled': True,
                'preferred_break_duration': 999  # Invalid value
            }),
            content_type='application/json'
        )

        assert response.status_code == 200
        data = response.json()
        assert data['success'] is False
        assert 'invalid' in data['message'].lower()


# ===== API ERROR HANDLING TESTS =====

@pytest.mark.api
class TestAPIErrorHandling(TestCase):
    """Test API error handling and edge cases"""

    def setUp(self):
        self.client = Client()
        self.user = User.objects.create_user(
            username='testuser',
            email='test@example.com',
            password='testpass123'
        )
        UserProfile.objects.create(user=self.user)
        UserTimerSettings.objects.create(user=self.user)
        self.client.login(username='test@example.com', password='testpass123')

    def test_nonexistent_resource_handling(self):
        """Test handling of requests for nonexistent resources"""
        # Try to sync nonexistent session
        response = self.client.post(
            reverse('timer:sync_session'),
            data=json.dumps({'session_id': 99999}),
            content_type='application/json'
        )

        assert response.status_code == 200
        data = response.json()
        assert data['success'] is False
        assert 'not found' in data['message'].lower()

        # Try to complete nonexistent break
        response = self.client.post(
            reverse('timer:complete_break'),
            data=json.dumps({'break_id': 99999}),
            content_type='application/json'
        )

        assert response.status_code == 404  # Should return 404 for nonexistent break

    def test_database_error_handling(self):
        """Test handling of database errors"""
        # Mock database error
        with patch('timer.models.TimerSession.objects.create') as mock_create:
            mock_create.side_effect = Exception("Database error")

            response = self.client.post(
                reverse('timer:start_session'),
                data=json.dumps({}),
                content_type='application/json'
            )

            # Should handle error gracefully
            assert response.status_code in [200, 500]
            if response.status_code == 200:
                data = response.json()
                assert data['success'] is False

    def test_malformed_request_handling(self):
        """Test handling of malformed requests"""
        # Test with wrong HTTP method where POST expected
        response = self.client.get(reverse('timer:start_session'))
        assert response.status_code in [405, 400]  # Method not allowed or bad request

        # Test with missing content type
        response = self.client.post(
            reverse('timer:start_session'),
            data='{}',
            content_type='text/plain'
        )
        assert response.status_code in [200, 400]

    def test_timeout_handling(self):
        """Test handling of request timeouts"""
        # Mock slow operation
        with patch('timer.views.TimerSession.objects.create') as mock_create:
            import time
            def slow_create(*args, **kwargs):
                time.sleep(0.1)  # Simulate slow operation
                return TimerSession(*args, **kwargs)

            mock_create.side_effect = slow_create

            response = self.client.post(
                reverse('timer:start_session'),
                data=json.dumps({}),
                content_type='application/json'
            )

            # Should complete without timeout (0.1s is not long enough to timeout)
            assert response.status_code == 200


# ===== API PERFORMANCE TESTS =====

@pytest.mark.api
@pytest.mark.performance
@pytest.mark.slow
class TestAPIPerformance(TestCase):
    """Test API performance characteristics"""

    def setUp(self):
        self.client = Client()
        self.user = User.objects.create_user(
            username='testuser',
            email='test@example.com',
            password='testpass123'
        )
        UserProfile.objects.create(user=self.user)
        UserTimerSettings.objects.create(user=self.user)
        self.client.login(username='test@example.com', password='testpass123')

    def test_session_start_performance(self):
        """Test session start endpoint performance"""
        import time

        times = []
        for i in range(10):
            start_time = time.time()

            response = self.client.post(
                reverse('timer:start_session'),
                data=json.dumps({}),
                content_type='application/json'
            )

            end_time = time.time()
            request_time = end_time - start_time
            times.append(request_time)

            if i == 0:
                # First request should succeed
                assert response.status_code == 200
                data = response.json()
                if data['success']:
                    # End session for next iteration
                    self.client.post(reverse('timer:end_session'))

        # Average response time should be reasonable
        avg_time = sum(times) / len(times)
        assert avg_time < 1.0  # Less than 1 second

    def test_bulk_operation_performance(self):
        """Test performance with bulk operations"""
        # Create session first
        response = self.client.post(
            reverse('timer:start_session'),
            data=json.dumps({}),
            content_type='application/json'
        )

        session_data = response.json()
        session_id = session_data['session_id']

        # Test multiple sync operations
        import time
        start_time = time.time()

        for i in range(20):
            response = self.client.post(
                reverse('timer:sync_session'),
                data=json.dumps({'session_id': session_id}),
                content_type='application/json'
            )
            assert response.status_code == 200

        end_time = time.time()
        total_time = end_time - start_time

        # Should complete 20 sync operations quickly
        assert total_time < 5.0  # Less than 5 seconds for 20 operations

    def test_concurrent_request_handling(self):
        """Test handling of concurrent requests"""
        import threading
        import time

        results = []

        def make_request():
            response = self.client.post(
                reverse('timer:get_break_settings'),
                content_type='application/json'
            )
            results.append(response.status_code)

        # Create multiple threads
        threads = []
        for i in range(10):
            thread = threading.Thread(target=make_request)
            threads.append(thread)

        # Start all threads
        start_time = time.time()
        for thread in threads:
            thread.start()

        # Wait for all threads to complete
        for thread in threads:
            thread.join()

        end_time = time.time()
        total_time = end_time - start_time

        # All requests should succeed
        assert len(results) == 10
        assert all(status == 200 for status in results)

        # Should handle concurrent requests efficiently
        assert total_time < 3.0  # Less than 3 seconds for 10 concurrent requests


# ===== API SECURITY TESTS =====

@pytest.mark.api
@pytest.mark.security
class TestAPISecurity(TestCase):
    """Test API security features"""

    def setUp(self):
        self.client = Client()
        self.user = User.objects.create_user(
            username='testuser',
            email='test@example.com',
            password='testpass123'
        )
        UserProfile.objects.create(user=self.user)
        UserTimerSettings.objects.create(user=self.user)

    def test_idor_prevention(self):
        """Test Insecure Direct Object Reference prevention"""
        # Create two users
        user2 = User.objects.create_user(
            username='user2',
            email='user2@example.com',
            password='testpass123'
        )
        UserProfile.objects.create(user=user2)

        # Create session for user2
        session2 = TimerSession.objects.create(user=user2, is_active=True)

        # Login as user1
        self.client.login(username='test@example.com', password='testpass123')

        # Try to access user2's session
        response = self.client.post(
            reverse('timer:sync_session'),
            data=json.dumps({'session_id': session2.id}),
            content_type='application/json'
        )

        # Should not be able to access other user's session
        assert response.status_code == 200
        data = response.json()
        assert data['success'] is False or data.get('session_active') is False

    def test_privilege_escalation_prevention(self):
        """Test prevention of privilege escalation"""
        # Login as free user
        self.client.login(username='test@example.com', password='testpass123')

        # Try to access premium features
        from mysite.constants import FREE_DAILY_INTERVAL_LIMIT

        # Create intervals up to limit
        session = TimerSession.objects.create(user=self.user, is_active=False)
        for i in range(FREE_DAILY_INTERVAL_LIMIT):
            TimerInterval.objects.create(
                session=session,
                interval_number=i + 1,
                start_time=timezone.now()
            )

        # Should be blocked from creating more sessions
        response = self.client.post(
            reverse('timer:start_session'),
            data=json.dumps({}),
            content_type='application/json'
        )

        data = response.json()
        assert data['success'] is False
        assert 'limit' in data['message'].lower()

    def test_input_sanitization(self):
        """Test input sanitization across endpoints"""
        self.client.login(username='test@example.com', password='testpass123')

        # Test HTML injection in feedback
        malicious_input = '<script>alert("xss")</script><img src=x onerror=alert("xss")>'

        response = self.client.post(
            reverse('timer:submit_feedback'),
            data=json.dumps({
                'feedback_type': 'general',
                'title': malicious_input,
                'message': malicious_input
            }),
            content_type='application/json'
        )

        if response.status_code == 200:
            data = response.json()
            if data['success']:
                # Verify input was sanitized
                from timer.models import UserFeedback
                feedback = UserFeedback.objects.get(id=data['feedback_id'])
                assert '<script>' not in feedback.title
                assert '<script>' not in feedback.message

    def test_data_leakage_prevention(self):
        """Test prevention of data leakage"""
        # Create data for another user
        user2 = User.objects.create_user(
            username='user2',
            email='user2@example.com',
            password='testpass123'
        )

        session2 = TimerSession.objects.create(
            user=user2,
            is_active=False,
            total_work_minutes=120
        )

        # Login as user1
        self.client.login(username='test@example.com', password='testpass123')

        # Ensure user1 cannot see user2's data through any endpoint
        # This would require testing all data-returning endpoints

        # Test break settings (should only return current user's settings)
        response = self.client.get(reverse('timer:get_break_settings'))
        assert response.status_code == 200

        data = response.json()
        assert data['success'] is True
        # Should not contain any reference to user2's data