"""
Performance and load tests for the 20-20-20 eye health SaaS application.
Tests database performance, concurrent user handling, and scalability.
"""
import pytest
from datetime import datetime, timedelta, date
from decimal import Decimal
from unittest.mock import patch, Mock
from django.test import TestCase, TransactionTestCase, Client
from django.utils import timezone
from django.contrib.auth import get_user_model
from django.urls import reverse
from django.test.utils import override_settings
from django.db import transaction, connection
from django.db.models import Count, Sum, Avg
from concurrent.futures import ThreadPoolExecutor, as_completed
import threading
import time
import random

from accounts.models import User, UserProfile, UserLevel, UserStreakData
from timer.models import TimerSession, TimerInterval, BreakRecord, UserTimerSettings
from analytics.models import DailyStats, UserBehaviorEvent, UserSession
from timer.utils import (
    get_optimized_recent_sessions, get_user_session_statistics_optimized,
    cache_user_statistics
)

User = get_user_model()


# ===== DATABASE PERFORMANCE TESTS =====

@pytest.mark.performance
@pytest.mark.slow
class TestDatabasePerformance(TestCase):
    """Test database query performance and optimization"""

    def setUp(self):
        self.user = User.objects.create_user(
            username='perftest',
            email='perftest@example.com',
            password='testpass123'
        )
        UserProfile.objects.create(user=self.user)
        UserTimerSettings.objects.create(user=self.user)

    def test_large_dataset_query_performance(self):
        """Test query performance with large datasets"""
        # Create large dataset: 1000 sessions with intervals and breaks
        sessions = []
        intervals = []
        breaks = []

        print("Creating large dataset for performance testing...")
        start_time = time.time()

        # Bulk create sessions
        for i in range(1000):
            session_time = timezone.now() - timedelta(days=i % 365)
            sessions.append(TimerSession(
                user=self.user,
                start_time=session_time,
                end_time=session_time + timedelta(hours=2),
                is_active=False,
                total_work_minutes=120,
                total_intervals_completed=6,
                total_breaks_taken=5
            ))

        TimerSession.objects.bulk_create(sessions, batch_size=100)

        created_sessions = TimerSession.objects.filter(user=self.user)

        # Bulk create intervals
        for session in created_sessions:
            for j in range(6):
                intervals.append(TimerInterval(
                    session=session,
                    interval_number=j + 1,
                    start_time=session.start_time + timedelta(minutes=j * 20),
                    status='completed'
                ))

        TimerInterval.objects.bulk_create(intervals, batch_size=500)

        created_intervals = TimerInterval.objects.filter(session__user=self.user)

        # Bulk create breaks
        for interval in created_intervals[:5000]:  # Limit for memory
            breaks.append(BreakRecord(
                user=self.user,
                session=interval.session,
                interval=interval,
                break_start_time=interval.start_time + timedelta(minutes=20),
                break_end_time=interval.start_time + timedelta(minutes=20, seconds=25),
                break_duration_seconds=25,
                break_completed=True,
                looked_at_distance=True
            ))

        BreakRecord.objects.bulk_create(breaks, batch_size=500)

        creation_time = time.time() - start_time
        print(f"Data creation took: {creation_time:.2f} seconds")

        # Test optimized queries
        test_queries = [
            ("Recent sessions", lambda: list(get_optimized_recent_sessions(self.user, 10))),
            ("Session statistics", lambda: get_user_session_statistics_optimized(self.user)),
            ("User dashboard data", lambda: self._get_dashboard_data()),
            ("Break compliance stats", lambda: self._get_compliance_stats()),
            ("Recent activity", lambda: self._get_recent_activity())
        ]

        for query_name, query_func in test_queries:
            start_time = time.time()

            # Execute query
            result = query_func()

            end_time = time.time()
            query_time = end_time - start_time

            print(f"{query_name} took: {query_time:.3f} seconds")

            # Performance assertions
            assert query_time < 2.0, f"{query_name} took too long: {query_time:.3f}s"
            assert result is not None

        # Test query count optimization
        with self.assertNumQueries(3):  # Should be optimized with prefetch
            recent_sessions = list(get_optimized_recent_sessions(self.user, 5))

            # Access related objects (should not trigger additional queries)
            for session in recent_sessions:
                list(session.intervals.all())
                list(session.breaks.all())

    def _get_dashboard_data(self):
        """Simulate dashboard data gathering"""
        today = timezone.now().date()

        # Get today's stats
        today_stats = DailyStats.objects.filter(
            user=self.user,
            date=today
        ).first()

        # Get recent sessions
        recent_sessions = TimerSession.objects.filter(
            user=self.user
        ).order_by('-start_time')[:5]

        # Get user level
        user_level = UserLevel.objects.filter(user=self.user).first()

        return {
            'today_stats': today_stats,
            'recent_sessions': list(recent_sessions),
            'user_level': user_level
        }

    def _get_compliance_stats(self):
        """Get break compliance statistics"""
        return BreakRecord.objects.filter(
            user=self.user,
            break_start_time__gte=timezone.now() - timedelta(days=30)
        ).aggregate(
            total_breaks=Count('id'),
            compliant_breaks=Count(
                'id',
                filter=Q(break_duration_seconds__gte=20, looked_at_distance=True)
            ),
            avg_duration=Avg('break_duration_seconds')
        )

    def _get_recent_activity(self):
        """Get recent user activity"""
        return UserBehaviorEvent.objects.filter(
            user=self.user
        ).order_by('-timestamp')[:10]

    def test_database_index_effectiveness(self):
        """Test that database indexes are effective"""
        # Create test data
        for i in range(100):
            session = TimerSession.objects.create(
                user=self.user,
                start_time=timezone.now() - timedelta(days=i),
                is_active=False
            )

        # Test queries that should use indexes
        queries_with_indexes = [
            # User-based queries (should use user foreign key index)
            ("User sessions", lambda: TimerSession.objects.filter(user=self.user).count()),

            # Date-based queries (should use date index)
            ("Recent sessions", lambda: TimerSession.objects.filter(
                user=self.user,
                start_time__gte=timezone.now() - timedelta(days=7)
            ).count()),

            # Status-based queries (should use compound index)
            ("Active sessions", lambda: TimerSession.objects.filter(
                user=self.user,
                is_active=True
            ).count()),
        ]

        for query_name, query_func in queries_with_indexes:
            start_time = time.time()

            result = query_func()

            end_time = time.time()
            query_time = end_time - start_time

            print(f"{query_name} (indexed) took: {query_time:.3f} seconds")

            # Indexed queries should be fast
            assert query_time < 0.1, f"Indexed query {query_name} too slow: {query_time:.3f}s"

    def test_bulk_operations_performance(self):
        """Test bulk operations performance"""
        # Test bulk create performance
        bulk_sessions = []
        for i in range(1000):
            bulk_sessions.append(TimerSession(
                user=self.user,
                start_time=timezone.now() - timedelta(hours=i),
                is_active=False,
                total_work_minutes=60
            ))

        start_time = time.time()
        TimerSession.objects.bulk_create(bulk_sessions, batch_size=100)
        bulk_create_time = time.time() - start_time

        print(f"Bulk create 1000 sessions took: {bulk_create_time:.3f} seconds")
        assert bulk_create_time < 5.0  # Should complete within 5 seconds

        # Test bulk update performance
        sessions_to_update = TimerSession.objects.filter(user=self.user)[:500]
        for session in sessions_to_update:
            session.total_work_minutes = 90

        start_time = time.time()
        TimerSession.objects.bulk_update(
            sessions_to_update,
            ['total_work_minutes'],
            batch_size=100
        )
        bulk_update_time = time.time() - start_time

        print(f"Bulk update 500 sessions took: {bulk_update_time:.3f} seconds")
        assert bulk_update_time < 3.0  # Should complete within 3 seconds

    def test_aggregation_performance(self):
        """Test aggregation query performance"""
        # Create test data
        for i in range(500):
            session = TimerSession.objects.create(
                user=self.user,
                start_time=timezone.now() - timedelta(days=i % 30),
                is_active=False,
                total_work_minutes=120,
                total_intervals_completed=6,
                total_breaks_taken=5
            )

        # Test complex aggregations
        aggregation_queries = [
            ("Monthly totals", lambda: TimerSession.objects.filter(
                user=self.user,
                start_time__gte=timezone.now() - timedelta(days=30)
            ).aggregate(
                total_work=Sum('total_work_minutes'),
                total_sessions=Count('id'),
                avg_session_length=Avg('total_work_minutes')
            )),

            ("Daily breakdown", lambda: TimerSession.objects.filter(
                user=self.user,
                start_time__gte=timezone.now() - timedelta(days=7)
            ).extra(
                select={'day': 'date(start_time)'}
            ).values('day').annotate(
                daily_sessions=Count('id'),
                daily_work=Sum('total_work_minutes')
            ).order_by('day')),
        ]

        for query_name, query_func in aggregation_queries:
            start_time = time.time()

            result = query_func()
            # Force evaluation
            list(result) if hasattr(result, '__iter__') else result

            end_time = time.time()
            query_time = end_time - start_time

            print(f"{query_name} aggregation took: {query_time:.3f} seconds")
            assert query_time < 1.0  # Should complete within 1 second


# ===== CONCURRENT USER TESTS =====

@pytest.mark.performance
@pytest.mark.slow
class TestConcurrentUsers(TransactionTestCase):
    """Test concurrent user handling"""

    def setUp(self):
        self.users = []
        for i in range(10):
            user = User.objects.create_user(
                username=f'user{i}',
                email=f'user{i}@example.com',
                password='testpass123'
            )
            UserProfile.objects.create(user=user)
            UserTimerSettings.objects.create(user=user)
            self.users.append(user)

    def test_concurrent_session_creation(self):
        """Test concurrent timer session creation"""
        results = []
        errors = []

        def create_session(user):
            try:
                with transaction.atomic():
                    session = TimerSession.objects.create(
                        user=user,
                        start_time=timezone.now(),
                        is_active=True
                    )

                    interval = TimerInterval.objects.create(
                        session=session,
                        interval_number=1,
                        start_time=timezone.now(),
                        status='active'
                    )

                    return {'session_id': session.id, 'interval_id': interval.id}
            except Exception as e:
                errors.append(str(e))
                return None

        # Create sessions concurrently
        start_time = time.time()

        with ThreadPoolExecutor(max_workers=10) as executor:
            futures = [executor.submit(create_session, user) for user in self.users]

            for future in as_completed(futures):
                result = future.result()
                if result:
                    results.append(result)

        end_time = time.time()
        total_time = end_time - start_time

        print(f"Concurrent session creation took: {total_time:.3f} seconds")
        print(f"Successful sessions: {len(results)}")
        print(f"Errors: {len(errors)}")

        # All sessions should be created successfully
        assert len(results) == len(self.users)
        assert len(errors) == 0
        assert total_time < 5.0  # Should complete within 5 seconds

    def test_concurrent_break_recording(self):
        """Test concurrent break recording"""
        # Create sessions for all users first
        sessions = []
        for user in self.users:
            session = TimerSession.objects.create(
                user=user,
                start_time=timezone.now(),
                is_active=True
            )
            interval = TimerInterval.objects.create(
                session=session,
                interval_number=1,
                start_time=timezone.now(),
                status='active'
            )
            sessions.append((session, interval))

        results = []
        errors = []

        def record_break(session_data):
            session, interval = session_data
            try:
                with transaction.atomic():
                    break_record = BreakRecord.objects.create(
                        user=session.user,
                        session=session,
                        interval=interval,
                        break_start_time=timezone.now(),
                        break_end_time=timezone.now() + timedelta(seconds=25),
                        break_duration_seconds=25,
                        break_completed=True,
                        looked_at_distance=True
                    )
                    return break_record.id
            except Exception as e:
                errors.append(str(e))
                return None

        # Record breaks concurrently
        start_time = time.time()

        with ThreadPoolExecutor(max_workers=10) as executor:
            futures = [executor.submit(record_break, session_data) for session_data in sessions]

            for future in as_completed(futures):
                result = future.result()
                if result:
                    results.append(result)

        end_time = time.time()
        total_time = end_time - start_time

        print(f"Concurrent break recording took: {total_time:.3f} seconds")
        print(f"Successful breaks: {len(results)}")
        print(f"Errors: {len(errors)}")

        assert len(results) == len(sessions)
        assert len(errors) == 0
        assert total_time < 3.0

    def test_concurrent_statistics_calculation(self):
        """Test concurrent statistics calculation"""
        # Create data for all users
        for user in self.users:
            for i in range(50):
                session = TimerSession.objects.create(
                    user=user,
                    start_time=timezone.now() - timedelta(hours=i),
                    is_active=False,
                    total_work_minutes=60,
                    total_intervals_completed=3
                )

        results = []
        errors = []

        def calculate_stats(user):
            try:
                stats = get_user_session_statistics_optimized(user)
                return stats
            except Exception as e:
                errors.append(str(e))
                return None

        # Calculate statistics concurrently
        start_time = time.time()

        with ThreadPoolExecutor(max_workers=10) as executor:
            futures = [executor.submit(calculate_stats, user) for user in self.users]

            for future in as_completed(futures):
                result = future.result()
                if result:
                    results.append(result)

        end_time = time.time()
        total_time = end_time - start_time

        print(f"Concurrent statistics calculation took: {total_time:.3f} seconds")
        print(f"Successful calculations: {len(results)}")
        print(f"Errors: {len(errors)}")

        assert len(results) == len(self.users)
        assert len(errors) == 0
        assert total_time < 10.0

        # Verify results are consistent
        for stats in results:
            assert stats['total_sessions'] == 50
            assert stats['total_work_minutes'] == 3000  # 50 sessions * 60 minutes

    def test_concurrent_api_requests(self):
        """Test concurrent API requests"""
        clients = []
        for user in self.users[:5]:  # Use 5 users for API testing
            client = Client()
            client.login(username=user.username, password='testpass123')
            clients.append((client, user))

        results = []
        errors = []

        def make_api_request(client_user_pair):
            client, user = client_user_pair
            try:
                # Test session start endpoint
                response = client.post(
                    reverse('timer:start_session'),
                    data='{}',
                    content_type='application/json'
                )

                return {
                    'status_code': response.status_code,
                    'user_id': user.id
                }
            except Exception as e:
                errors.append(str(e))
                return None

        # Make API requests concurrently
        start_time = time.time()

        with ThreadPoolExecutor(max_workers=5) as executor:
            futures = [executor.submit(make_api_request, client_pair) for client_pair in clients]

            for future in as_completed(futures):
                result = future.result()
                if result:
                    results.append(result)

        end_time = time.time()
        total_time = end_time - start_time

        print(f"Concurrent API requests took: {total_time:.3f} seconds")
        print(f"Successful requests: {len(results)}")
        print(f"Errors: {len(errors)}")

        assert len(results) == len(clients)
        assert len(errors) == 0
        assert total_time < 5.0

        # All requests should succeed
        for result in results:
            assert result['status_code'] == 200


# ===== MEMORY AND RESOURCE TESTS =====

@pytest.mark.performance
@pytest.mark.slow
class TestMemoryAndResources(TestCase):
    """Test memory usage and resource consumption"""

    def setUp(self):
        self.user = User.objects.create_user(
            username='memtest',
            email='memtest@example.com',
            password='testpass123'
        )
        UserProfile.objects.create(user=self.user)

    def test_memory_usage_with_large_querysets(self):
        """Test memory usage with large querysets"""
        import psutil
        import os

        # Get initial memory usage
        process = psutil.Process(os.getpid())
        initial_memory = process.memory_info().rss / 1024 / 1024  # MB

        # Create large dataset
        sessions = []
        for i in range(5000):
            sessions.append(TimerSession(
                user=self.user,
                start_time=timezone.now() - timedelta(hours=i),
                is_active=False,
                total_work_minutes=60
            ))

        TimerSession.objects.bulk_create(sessions, batch_size=500)

        # Test memory usage with different query approaches
        memory_tests = [
            ("All at once", lambda: list(TimerSession.objects.filter(user=self.user))),
            ("Iterator", lambda: list(TimerSession.objects.filter(user=self.user).iterator(chunk_size=100))),
            ("Values only", lambda: list(TimerSession.objects.filter(user=self.user).values('id', 'total_work_minutes'))),
            ("Optimized recent", lambda: list(get_optimized_recent_sessions(self.user, 100))),
        ]

        for test_name, test_func in memory_tests:
            # Measure memory before
            before_memory = process.memory_info().rss / 1024 / 1024

            # Execute query
            start_time = time.time()
            result = test_func()
            end_time = time.time()

            # Measure memory after
            after_memory = process.memory_info().rss / 1024 / 1024
            memory_increase = after_memory - before_memory

            print(f"{test_name}:")
            print(f"  Time: {end_time - start_time:.3f} seconds")
            print(f"  Memory increase: {memory_increase:.2f} MB")
            print(f"  Records: {len(result)}")

            # Memory increase should be reasonable
            assert memory_increase < 100, f"{test_name} used too much memory: {memory_increase:.2f} MB"

            # Clean up references
            del result

    def test_database_connection_usage(self):
        """Test database connection usage patterns"""
        from django.db import connections

        # Get initial connection count
        db_connections = connections.all()
        initial_queries = sum(conn.queries_logged for conn in db_connections)

        # Test query efficiency
        test_operations = [
            ("Create session", lambda: TimerSession.objects.create(
                user=self.user,
                start_time=timezone.now(),
                is_active=True
            )),
            ("Get user stats", lambda: get_user_session_statistics_optimized(self.user)),
            ("Recent sessions", lambda: list(get_optimized_recent_sessions(self.user, 5))),
        ]

        for operation_name, operation_func in test_operations:
            # Reset query count
            for conn in db_connections:
                conn.queries_logged = 0

            # Execute operation
            result = operation_func()

            # Count queries
            total_queries = sum(conn.queries_logged for conn in db_connections)

            print(f"{operation_name} used {total_queries} database queries")

            # Operations should be efficient
            assert total_queries <= 5, f"{operation_name} used too many queries: {total_queries}"

    def test_caching_effectiveness(self):
        """Test caching effectiveness for performance"""
        # Create test data
        for i in range(100):
            TimerSession.objects.create(
                user=self.user,
                start_time=timezone.now() - timedelta(hours=i),
                is_active=False,
                total_work_minutes=60
            )

        # Test without cache
        start_time = time.time()
        stats1 = get_user_session_statistics_optimized(self.user)
        no_cache_time = time.time() - start_time

        # Test with cache
        start_time = time.time()
        stats2 = cache_user_statistics(self.user)
        first_cache_time = time.time() - start_time

        # Test cache hit
        start_time = time.time()
        stats3 = cache_user_statistics(self.user)
        cache_hit_time = time.time() - start_time

        print(f"No cache: {no_cache_time:.3f} seconds")
        print(f"First cache: {first_cache_time:.3f} seconds")
        print(f"Cache hit: {cache_hit_time:.3f} seconds")

        # Cache hit should be much faster
        assert cache_hit_time < first_cache_time / 2
        assert cache_hit_time < 0.01  # Should be very fast

        # Results should be consistent
        assert stats1['total_sessions'] == stats2['total_sessions'] == stats3['total_sessions']


# ===== SCALABILITY TESTS =====

@pytest.mark.performance
@pytest.mark.slow
class TestScalability(TestCase):
    """Test application scalability characteristics"""

    def test_user_growth_simulation(self):
        """Simulate application behavior with growing user base"""
        user_counts = [10, 50, 100, 500]
        performance_results = []

        for user_count in user_counts:
            print(f"\nTesting with {user_count} users...")

            # Create users
            users = []
            for i in range(user_count):
                user = User.objects.create_user(
                    username=f'scale_user_{i}',
                    email=f'scale_user_{i}@example.com',
                    password='testpass123'
                )
                UserProfile.objects.create(user=user)
                users.append(user)

            # Create data for each user
            start_time = time.time()

            sessions_per_user = 10
            for user in users:
                sessions = []
                for j in range(sessions_per_user):
                    sessions.append(TimerSession(
                        user=user,
                        start_time=timezone.now() - timedelta(hours=j),
                        is_active=False,
                        total_work_minutes=60
                    ))
                TimerSession.objects.bulk_create(sessions, batch_size=50)

            data_creation_time = time.time() - start_time

            # Test query performance at this scale
            start_time = time.time()

            # Simulate common operations
            for user in users[:10]:  # Test with subset to avoid timeout
                get_user_session_statistics_optimized(user)
                list(get_optimized_recent_sessions(user, 5))

            query_time = time.time() - start_time

            # Test aggregation performance
            start_time = time.time()

            total_stats = TimerSession.objects.aggregate(
                total_sessions=Count('id'),
                total_work=Sum('total_work_minutes')
            )

            aggregation_time = time.time() - start_time

            performance_results.append({
                'user_count': user_count,
                'data_creation_time': data_creation_time,
                'query_time': query_time,
                'aggregation_time': aggregation_time,
                'total_sessions': total_stats['total_sessions']
            })

            print(f"  Data creation: {data_creation_time:.3f}s")
            print(f"  Query time: {query_time:.3f}s")
            print(f"  Aggregation time: {aggregation_time:.3f}s")
            print(f"  Total sessions: {total_stats['total_sessions']}")

        # Analyze scalability
        print("\nScalability Analysis:")
        for result in performance_results:
            user_count = result['user_count']
            sessions_per_second = result['total_sessions'] / max(result['data_creation_time'], 0.001)

            print(f"Users: {user_count:3d} | "
                  f"Sessions/sec: {sessions_per_second:6.1f} | "
                  f"Query time: {result['query_time']:.3f}s | "
                  f"Agg time: {result['aggregation_time']:.3f}s")

        # Performance should not degrade linearly with user count
        # (due to optimizations and proper indexing)
        largest_result = performance_results[-1]
        assert largest_result['query_time'] < 5.0  # Should handle 500 users reasonably
        assert largest_result['aggregation_time'] < 1.0  # Aggregations should be fast

    def test_data_volume_scalability(self):
        """Test scalability with increasing data volume"""
        user = User.objects.create_user(
            username='volume_test',
            email='volume_test@example.com',
            password='testpass123'
        )
        UserProfile.objects.create(user=user)

        data_sizes = [100, 500, 1000, 5000]
        performance_results = []

        for data_size in data_sizes:
            print(f"\nTesting with {data_size} sessions...")

            # Create sessions
            sessions = []
            for i in range(data_size):
                sessions.append(TimerSession(
                    user=user,
                    start_time=timezone.now() - timedelta(hours=i),
                    is_active=False,
                    total_work_minutes=random.randint(30, 180)
                ))

            start_time = time.time()
            TimerSession.objects.bulk_create(sessions, batch_size=100)
            creation_time = time.time() - start_time

            # Test query performance
            query_tests = [
                ("Recent sessions", lambda: list(get_optimized_recent_sessions(user, 10))),
                ("Statistics", lambda: get_user_session_statistics_optimized(user)),
                ("Count query", lambda: TimerSession.objects.filter(user=user).count()),
            ]

            query_times = {}
            for test_name, test_func in query_tests:
                start_time = time.time()
                result = test_func()
                query_times[test_name] = time.time() - start_time

            performance_results.append({
                'data_size': data_size,
                'creation_time': creation_time,
                'query_times': query_times
            })

            print(f"  Creation time: {creation_time:.3f}s")
            for test_name, query_time in query_times.items():
                print(f"  {test_name}: {query_time:.3f}s")

        # Verify performance characteristics
        print("\nData Volume Scalability Analysis:")
        for result in performance_results:
            size = result['data_size']
            print(f"Size: {size:4d} | Creation: {result['creation_time']:.3f}s | "
                  f"Recent: {result['query_times']['Recent sessions']:.3f}s | "
                  f"Stats: {result['query_times']['Statistics']:.3f}s")

        # Optimized queries should not degrade significantly
        largest_result = performance_results[-1]
        assert largest_result['query_times']['Recent sessions'] < 0.5
        assert largest_result['query_times']['Statistics'] < 1.0
        assert largest_result['query_times']['Count query'] < 0.1