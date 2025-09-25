"""
Management command to set up gamification system with default badges and challenges
"""
from django.core.management.base import BaseCommand
from django.utils import timezone
from datetime import timedelta

from accounts.models import Badge, Challenge
from accounts.gamification_utils import create_default_badges


class Command(BaseCommand):
    help = 'Set up gamification system with default badges and challenges'

    def add_arguments(self, parser):
        parser.add_argument(
            '--create-badges',
            action='store_true',
            help='Create default badges'
        )
        parser.add_argument(
            '--create-challenges',
            action='store_true',
            help='Create sample challenges'
        )
        parser.add_argument(
            '--reset',
            action='store_true',
            help='Reset all gamification data (WARNING: This will delete existing badges and challenges)'
        )

    def handle(self, *args, **options):
        if options['reset']:
            self._reset_gamification_data()

        if options['create_badges']:
            self._create_default_badges()

        if options['create_challenges']:
            self._create_sample_challenges()

        if not any([options['create_badges'], options['create_challenges'], options['reset']]):
            self.stdout.write(
                self.style.WARNING(
                    'No action specified. Use --create-badges, --create-challenges, or --reset'
                )
            )

    def _reset_gamification_data(self):
        """Reset all gamification data"""
        self.stdout.write(
            self.style.WARNING('Resetting all gamification data...')
        )

        # Delete all badges and challenges
        badges_deleted = Badge.objects.all().delete()[0]
        challenges_deleted = Challenge.objects.all().delete()[0]

        self.stdout.write(
            f'Deleted {badges_deleted} badges and {challenges_deleted} challenges'
        )

    def _create_default_badges(self):
        """Create default badges for the gamification system"""
        self.stdout.write('Creating default badges...')

        created_badges = create_default_badges()

        if created_badges:
            self.stdout.write(
                self.style.SUCCESS(
                    f'Successfully created {len(created_badges)} new badges'
                )
            )
            for badge in created_badges:
                self.stdout.write(f'  - {badge.name} ({badge.get_rarity_display()})')
        else:
            self.stdout.write('All default badges already exist')

    def _create_sample_challenges(self):
        """Create sample challenges"""
        self.stdout.write('Creating sample challenges...')

        now = timezone.now()
        challenges_data = [
            {
                'name': 'Weekly Warrior',
                'description': 'Complete 25 timer sessions this week',
                'challenge_type': 'session_count',
                'target_value': 25,
                'start_date': now,
                'end_date': now + timedelta(days=7),
                'experience_reward': 200,
                'is_active': True,
                'is_premium_only': False
            },
            {
                'name': 'Compliance Champion',
                'description': 'Achieve 90% break compliance rate this week',
                'challenge_type': 'compliance_rate',
                'target_value': 90,
                'start_date': now,
                'end_date': now + timedelta(days=7),
                'experience_reward': 300,
                'is_active': True,
                'is_premium_only': False
            },
            {
                'name': 'Streak Master',
                'description': 'Maintain a 14-day daily streak',
                'challenge_type': 'daily_streak',
                'target_value': 14,
                'start_date': now,
                'end_date': now + timedelta(days=21),
                'experience_reward': 500,
                'is_active': True,
                'is_premium_only': True
            },
            {
                'name': 'Community Challenge',
                'description': 'Help the community reach 10,000 total sessions',
                'challenge_type': 'community',
                'target_value': 10000,
                'start_date': now,
                'end_date': now + timedelta(days=30),
                'experience_reward': 100,
                'is_active': True,
                'is_premium_only': False,
                'max_participants': 1000
            }
        ]

        created_count = 0
        for challenge_data in challenges_data:
            challenge, created = Challenge.objects.get_or_create(
                name=challenge_data['name'],
                defaults=challenge_data
            )
            if created:
                created_count += 1

        self.stdout.write(
            self.style.SUCCESS(
                f'Successfully created {created_count} new challenges'
            )
        )

        if created_count > 0:
            self.stdout.write('Created challenges:')
            for challenge_data in challenges_data:
                if Challenge.objects.filter(name=challenge_data['name']).exists():
                    self.stdout.write(f'  - {challenge_data["name"]}')
        else:
            self.stdout.write('All sample challenges already exist')