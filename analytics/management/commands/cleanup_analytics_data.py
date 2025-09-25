"""
Management command to clean up old analytics data and optimize database
"""
from django.core.management.base import BaseCommand
from django.utils import timezone
from django.db import transaction
from datetime import timedelta

from analytics.models import (
    RealTimeMetrics, UserSession, UserBehaviorEvent,
    LiveActivityFeed, UserSatisfactionRating
)


class Command(BaseCommand):
    help = 'Clean up old analytics data and optimize database performance'

    def add_arguments(self, parser):
        parser.add_argument(
            '--days',
            type=int,
            default=90,
            help='Keep data for the last N days (default: 90)'
        )
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Show what would be deleted without actually deleting'
        )
        parser.add_argument(
            '--cleanup-sessions',
            action='store_true',
            help='Clean up old user sessions'
        )
        parser.add_argument(
            '--cleanup-metrics',
            action='store_true',
            help='Clean up old real-time metrics'
        )
        parser.add_argument(
            '--cleanup-events',
            action='store_true',
            help='Clean up old behavior events'
        )
        parser.add_argument(
            '--cleanup-feed',
            action='store_true',
            help='Clean up old activity feed entries'
        )
        parser.add_argument(
            '--all',
            action='store_true',
            help='Clean up all data types'
        )

    def handle(self, *args, **options):
        self.dry_run = options['dry_run']
        self.days_to_keep = options['days']
        cutoff_date = timezone.now() - timedelta(days=self.days_to_keep)

        if self.dry_run:
            self.stdout.write(
                self.style.WARNING('DRY RUN MODE - No data will be deleted')
            )

        self.stdout.write(f'Cleaning up data older than {cutoff_date.date()}...')

        total_deleted = 0

        # Clean up based on options
        if options['all'] or options['cleanup_sessions']:
            total_deleted += self._cleanup_user_sessions(cutoff_date)

        if options['all'] or options['cleanup_metrics']:
            total_deleted += self._cleanup_real_time_metrics(cutoff_date)

        if options['all'] or options['cleanup_events']:
            total_deleted += self._cleanup_behavior_events(cutoff_date)

        if options['all'] or options['cleanup_feed']:
            total_deleted += self._cleanup_activity_feed(cutoff_date)

        # If no specific options selected, show help
        if not any([
            options['cleanup_sessions'],
            options['cleanup_metrics'],
            options['cleanup_events'],
            options['cleanup_feed'],
            options['all']
        ]):
            self.stdout.write(
                self.style.WARNING(
                    'No cleanup options specified. Use --all or specific --cleanup-* options.'
                )
            )
            return

        if self.dry_run:
            self.stdout.write(
                self.style.SUCCESS(
                    f'DRY RUN: Would delete {total_deleted} records'
                )
            )
        else:
            self.stdout.write(
                self.style.SUCCESS(
                    f'Successfully deleted {total_deleted} old records'
                )
            )

    def _cleanup_user_sessions(self, cutoff_date):
        """Clean up old user sessions"""
        self.stdout.write('Cleaning up old user sessions...')

        # Clean up inactive sessions older than cutoff
        old_sessions = UserSession.objects.filter(
            last_activity__lt=cutoff_date,
            is_active=False
        )

        count = old_sessions.count()
        self.stdout.write(f'Found {count} old user sessions to delete')

        if not self.dry_run and count > 0:
            with transaction.atomic():
                deleted = old_sessions.delete()[0]
                self.stdout.write(f'Deleted {deleted} user sessions')
                return deleted

        return count

    def _cleanup_real_time_metrics(self, cutoff_date):
        """Clean up old real-time metrics (keep only last 48 hours)"""
        self.stdout.write('Cleaning up old real-time metrics...')

        # For real-time metrics, keep only last 48 hours
        metrics_cutoff = timezone.now() - timedelta(hours=48)
        old_metrics = RealTimeMetrics.objects.filter(
            timestamp__lt=metrics_cutoff
        )

        count = old_metrics.count()
        self.stdout.write(f'Found {count} old real-time metrics to delete')

        if not self.dry_run and count > 0:
            with transaction.atomic():
                deleted = old_metrics.delete()[0]
                self.stdout.write(f'Deleted {deleted} real-time metrics')
                return deleted

        return count

    def _cleanup_behavior_events(self, cutoff_date):
        """Clean up old behavior events"""
        self.stdout.write('Cleaning up old behavior events...')

        old_events = UserBehaviorEvent.objects.filter(
            timestamp__lt=cutoff_date
        )

        count = old_events.count()
        self.stdout.write(f'Found {count} old behavior events to delete')

        if not self.dry_run and count > 0:
            # Delete in batches to avoid memory issues
            batch_size = 1000
            total_deleted = 0

            while True:
                with transaction.atomic():
                    batch_ids = list(
                        old_events.values_list('id', flat=True)[:batch_size]
                    )
                    if not batch_ids:
                        break

                    deleted = UserBehaviorEvent.objects.filter(
                        id__in=batch_ids
                    ).delete()[0]
                    total_deleted += deleted

                    self.stdout.write(f'Deleted batch of {deleted} events...')

            self.stdout.write(f'Deleted {total_deleted} behavior events')
            return total_deleted

        return count

    def _cleanup_activity_feed(self, cutoff_date):
        """Clean up old activity feed entries"""
        self.stdout.write('Cleaning up old activity feed entries...')

        # Keep activity feed for shorter period (30 days)
        feed_cutoff = timezone.now() - timedelta(days=30)
        old_activities = LiveActivityFeed.objects.filter(
            timestamp__lt=feed_cutoff
        )

        count = old_activities.count()
        self.stdout.write(f'Found {count} old activity feed entries to delete')

        if not self.dry_run and count > 0:
            with transaction.atomic():
                deleted = old_activities.delete()[0]
                self.stdout.write(f'Deleted {deleted} activity feed entries')
                return deleted

        return count