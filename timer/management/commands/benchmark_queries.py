"""
Django management command to benchmark database query performance
Helps identify N+1 queries and measure optimization improvements
"""

import time
from django.core.management.base import BaseCommand
from django.contrib.auth import get_user_model
from django.db import connection, reset_queries
from django.conf import settings

from timer.models import TimerSession, BreakRecord
from timer.views import dashboard_view
from timer.utils import get_optimized_recent_sessions, get_user_session_statistics_optimized
from accounts.gamification_utils import get_user_gamification_summary
from analytics.models import RealTimeMetrics

User = get_user_model()


class Command(BaseCommand):
    help = 'Benchmark database query performance to identify N+1 queries and measure optimizations'

    def add_arguments(self, parser):
        parser.add_argument(
            '--users',
            type=int,
            default=5,
            help='Number of users to test with (default: 5)'
        )
        parser.add_argument(
            '--verbose',
            action='store_true',
            help='Show detailed query analysis'
        )
        parser.add_argument(
            '--benchmark-all',
            action='store_true',
            help='Run all benchmark tests'
        )

    def handle(self, *args, **options):
        self.stdout.write(self.style.SUCCESS('Starting database query benchmark...'))

        # Ensure DEBUG is True to enable query logging
        if not settings.DEBUG:
            self.stdout.write(
                self.style.WARNING('DEBUG must be True to track queries. Enable DEBUG temporarily.')
            )
            return

        users = self._get_test_users(options['users'])
        if not users:
            self.stdout.write(self.style.ERROR('No users found for testing'))
            return

        self.stdout.write(f'Testing with {len(users)} users...\n')

        if options['benchmark_all']:
            self._run_all_benchmarks(users, options['verbose'])
        else:
            self._benchmark_dashboard_view(users, options['verbose'])

    def _get_test_users(self, count):
        """Get test users with some data"""
        return User.objects.filter(
            timer_sessions__isnull=False
        ).distinct()[:count]

    def _run_all_benchmarks(self, users, verbose):
        """Run all performance benchmarks"""
        self.stdout.write(self.style.SUCCESS('=== COMPREHENSIVE PERFORMANCE BENCHMARK ===\n'))

        benchmarks = [
            ('Dashboard View Query Optimization', self._benchmark_dashboard_view),
            ('Recent Sessions Query Optimization', self._benchmark_recent_sessions),
            ('User Statistics Optimization', self._benchmark_user_statistics),
            ('Gamification Summary Optimization', self._benchmark_gamification_summary),
            ('Real-time Metrics Optimization', self._benchmark_real_time_metrics),
        ]

        results = {}
        for name, benchmark_func in benchmarks:
            self.stdout.write(f'\n--- {name} ---')
            results[name] = benchmark_func(users, verbose)

        self._print_summary(results)

    def _benchmark_dashboard_view(self, users, verbose):
        """Benchmark dashboard view performance"""
        self.stdout.write('Benchmarking dashboard view...')

        total_queries = 0
        total_time = 0

        for user in users:
            reset_queries()
            start_time = time.time()

            # Simulate what dashboard_view does
            recent_sessions = get_optimized_recent_sessions(user, 10)
            list(recent_sessions)  # Force query execution

            gamification_data = get_user_gamification_summary(user)

            end_time = time.time()
            query_count = len(connection.queries)
            execution_time = end_time - start_time

            total_queries += query_count
            total_time += execution_time

            if verbose:
                self.stdout.write(f'  User {user.id}: {query_count} queries, {execution_time:.3f}s')
                for query in connection.queries:
                    self.stdout.write(f'    SQL: {query["sql"][:100]}...')

        avg_queries = total_queries / len(users)
        avg_time = total_time / len(users)

        self.stdout.write(
            f'Dashboard View Results: Avg {avg_queries:.1f} queries, {avg_time:.3f}s per user'
        )

        return {'avg_queries': avg_queries, 'avg_time': avg_time}

    def _benchmark_recent_sessions(self, users, verbose):
        """Benchmark recent sessions query optimization"""
        self.stdout.write('Benchmarking recent sessions queries...')

        total_queries = 0
        total_time = 0

        for user in users:
            reset_queries()
            start_time = time.time()

            # Test optimized version
            sessions = get_optimized_recent_sessions(user, 10)

            # Force evaluation and access related objects
            for session in sessions:
                list(session.intervals.all())
                list(session.breaks.all())

            end_time = time.time()
            query_count = len(connection.queries)
            execution_time = end_time - start_time

            total_queries += query_count
            total_time += execution_time

            if verbose:
                self.stdout.write(f'  User {user.id}: {query_count} queries, {execution_time:.3f}s')

        avg_queries = total_queries / len(users)
        avg_time = total_time / len(users)

        self.stdout.write(
            f'Recent Sessions Results: Avg {avg_queries:.1f} queries, {avg_time:.3f}s per user'
        )

        return {'avg_queries': avg_queries, 'avg_time': avg_time}

    def _benchmark_user_statistics(self, users, verbose):
        """Benchmark user statistics optimization"""
        self.stdout.write('Benchmarking user statistics calculation...')

        total_queries = 0
        total_time = 0

        for user in users:
            reset_queries()
            start_time = time.time()

            stats = get_user_session_statistics_optimized(user)

            end_time = time.time()
            query_count = len(connection.queries)
            execution_time = end_time - start_time

            total_queries += query_count
            total_time += execution_time

            if verbose:
                self.stdout.write(f'  User {user.id}: {query_count} queries, {execution_time:.3f}s')
                self.stdout.write(f'    Stats: {stats}')

        avg_queries = total_queries / len(users)
        avg_time = total_time / len(users)

        self.stdout.write(
            f'User Statistics Results: Avg {avg_queries:.1f} queries, {avg_time:.3f}s per user'
        )

        return {'avg_queries': avg_queries, 'avg_time': avg_time}

    def _benchmark_gamification_summary(self, users, verbose):
        """Benchmark gamification summary optimization"""
        self.stdout.write('Benchmarking gamification summary...')

        total_queries = 0
        total_time = 0

        for user in users:
            reset_queries()
            start_time = time.time()

            summary = get_user_gamification_summary(user)

            end_time = time.time()
            query_count = len(connection.queries)
            execution_time = end_time - start_time

            total_queries += query_count
            total_time += execution_time

            if verbose:
                self.stdout.write(f'  User {user.id}: {query_count} queries, {execution_time:.3f}s')

        avg_queries = total_queries / len(users)
        avg_time = total_time / len(users)

        self.stdout.write(
            f'Gamification Summary Results: Avg {avg_queries:.1f} queries, {avg_time:.3f}s per user'
        )

        return {'avg_queries': avg_queries, 'avg_time': avg_time}

    def _benchmark_real_time_metrics(self, users, verbose):
        """Benchmark real-time metrics update"""
        self.stdout.write('Benchmarking real-time metrics update...')

        reset_queries()
        start_time = time.time()

        metrics = RealTimeMetrics.get_latest_metrics()
        metrics.update_metrics()

        end_time = time.time()
        query_count = len(connection.queries)
        execution_time = end_time - start_time

        if verbose:
            self.stdout.write(f'  Real-time metrics: {query_count} queries, {execution_time:.3f}s')
            for query in connection.queries:
                self.stdout.write(f'    SQL: {query["sql"][:150]}...')

        self.stdout.write(
            f'Real-time Metrics Results: {query_count} queries, {execution_time:.3f}s'
        )

        return {'avg_queries': query_count, 'avg_time': execution_time}

    def _print_summary(self, results):
        """Print benchmark summary"""
        self.stdout.write('\n' + '='*60)
        self.stdout.write(self.style.SUCCESS('BENCHMARK SUMMARY'))
        self.stdout.write('='*60)

        for test_name, result in results.items():
            queries = result['avg_queries']
            time_taken = result['avg_time']

            # Determine performance rating
            if queries <= 5 and time_taken <= 0.1:
                rating = self.style.SUCCESS('EXCELLENT')
            elif queries <= 10 and time_taken <= 0.5:
                rating = self.style.SUCCESS('GOOD')
            elif queries <= 20 and time_taken <= 1.0:
                rating = self.style.WARNING('FAIR')
            else:
                rating = self.style.ERROR('NEEDS OPTIMIZATION')

            self.stdout.write(
                f'{test_name:<40} | {queries:>6.1f} queries | {time_taken:>7.3f}s | {rating}'
            )

        self.stdout.write('\n' + '='*60)
        self.stdout.write('Optimization Guidelines:')
        self.stdout.write('• EXCELLENT: <= 5 queries, <= 0.1s')
        self.stdout.write('• GOOD: <= 10 queries, <= 0.5s')
        self.stdout.write('• FAIR: <= 20 queries, <= 1.0s')
        self.stdout.write('• NEEDS OPTIMIZATION: > 20 queries or > 1.0s')
        self.stdout.write('='*60)

    def _analyze_n_plus_one(self, queries):
        """Analyze queries for N+1 patterns"""
        similar_queries = {}

        for query in queries:
            sql = query['sql']
            # Remove specific IDs to group similar queries
            normalized = self._normalize_query(sql)

            if normalized in similar_queries:
                similar_queries[normalized] += 1
            else:
                similar_queries[normalized] = 1

        # Find potential N+1 queries (repeated similar queries)
        n_plus_one_queries = {
            query: count for query, count in similar_queries.items()
            if count > 3  # More than 3 similar queries indicates potential N+1
        }

        return n_plus_one_queries

    def _normalize_query(self, sql):
        """Normalize SQL query to identify similar patterns"""
        import re
        # Replace specific values with placeholders
        normalized = re.sub(r'\b\d+\b', 'ID', sql)
        normalized = re.sub(r"'[^']*'", "'VALUE'", normalized)
        normalized = re.sub(r'"[^"]*"', '"VALUE"', normalized)
        return normalized