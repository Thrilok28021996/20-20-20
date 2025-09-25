"""
Management command to update and recalculate user statistics
"""
from django.core.management.base import BaseCommand
from django.utils import timezone
from django.db.models import Sum, Count, Avg
from datetime import date, timedelta

from accounts.models import User, UserProfile, UserStreakData
from analytics.models import DailyStats, WeeklyStats, MonthlyStats
from timer.models import TimerSession, BreakRecord


class Command(BaseCommand):
    help = 'Update and recalculate user statistics for accurate data display'

    def add_arguments(self, parser):
        parser.add_argument(
            '--user-id',
            type=int,
            help='Update statistics for a specific user ID'
        )
        parser.add_argument(
            '--days',
            type=int,
            default=30,
            help='Number of days to recalculate (default: 30)'
        )
        parser.add_argument(
            '--force',
            action='store_true',
            help='Force recalculation even if data exists'
        )
        parser.add_argument(
            '--create-missing-profiles',
            action='store_true',
            help='Create missing user profiles and streak data'
        )

    def handle(self, *args, **options):
        self.stdout.write('Starting user statistics update...')

        # Get users to process
        if options['user_id']:
            users = User.objects.filter(id=options['user_id'])
            if not users.exists():
                self.stdout.write(
                    self.style.ERROR(f'User with ID {options["user_id"]} not found')
                )
                return
        else:
            users = User.objects.filter(is_active=True)

        total_users = users.count()
        self.stdout.write(f'Processing {total_users} users...')

        # Create missing profiles if requested
        if options['create_missing_profiles']:
            self._create_missing_profiles(users)

        # Update daily statistics
        days_to_process = options['days']
        for i, user in enumerate(users, 1):
            self.stdout.write(f'Processing user {i}/{total_users}: {user.email}')
            self._update_user_daily_stats(user, days_to_process, options['force'])
            self._update_user_streak_data(user, options['force'])

            if i % 10 == 0:
                self.stdout.write(f'Processed {i}/{total_users} users...')

        # Update weekly and monthly aggregations
        self._update_weekly_stats(users)
        self._update_monthly_stats(users)

        self.stdout.write(
            self.style.SUCCESS(f'Successfully updated statistics for {total_users} users')
        )

    def _create_missing_profiles(self, users):
        """Create missing user profiles and streak data"""
        self.stdout.write('Creating missing user profiles...')

        profiles_created = 0
        streak_data_created = 0

        for user in users:
            # Create user profile if missing
            profile, created = UserProfile.objects.get_or_create(
                user=user,
                defaults={
                    'daily_screen_time_hours': 8.0,
                    'timezone': 'UTC',
                    'preferred_language': 'en'
                }
            )
            if created:
                profiles_created += 1

            # Create streak data if missing
            streak_data, created = UserStreakData.objects.get_or_create(
                user=user,
                defaults={
                    'current_daily_streak': 0,
                    'best_daily_streak': 0,
                    'total_sessions_completed': 0,
                    'total_break_time_minutes': 0,
                    'average_session_length': 0.0
                }
            )
            if created:
                streak_data_created += 1

        self.stdout.write(
            f'Created {profiles_created} user profiles and {streak_data_created} streak data records'
        )

    def _update_user_daily_stats(self, user, days, force=False):
        """Update daily statistics for a user"""
        end_date = date.today()
        start_date = end_date - timedelta(days=days)

        for single_date in self._daterange(start_date, end_date):
            # Check if stats already exist
            daily_stat, created = DailyStats.objects.get_or_create(
                user=user,
                date=single_date,
                defaults=self._calculate_daily_stats(user, single_date)
            )

            # Update existing stats if force is True
            if not created and force:
                calculated_stats = self._calculate_daily_stats(user, single_date)
                for key, value in calculated_stats.items():
                    setattr(daily_stat, key, value)
                daily_stat.save()

    def _calculate_daily_stats(self, user, target_date):
        """Calculate daily statistics for a specific date"""
        # Get sessions for the date
        sessions = TimerSession.objects.filter(
            user=user,
            start_time__date=target_date
        )

        # Get breaks for the date
        breaks = BreakRecord.objects.filter(
            user=user,
            break_start_time__date=target_date,
            break_completed=True
        )

        # Calculate basic metrics
        total_work_minutes = sum(session.total_work_minutes for session in sessions)
        total_intervals = sum(session.total_intervals_completed for session in sessions)
        total_breaks = breaks.count()
        total_sessions = sessions.count()

        # Calculate compliance metrics
        compliant_breaks = breaks.filter(
            break_duration_seconds__gte=20,
            looked_at_distance=True
        ).count()

        breaks_on_time = 0  # Would need more complex calculation
        average_break_duration = 0.0

        if total_breaks > 0:
            average_break_duration = sum(
                br.break_duration_seconds for br in breaks
            ) / total_breaks

        # Calculate productivity score
        productivity_score = self._calculate_productivity_score(
            total_sessions, total_breaks, compliant_breaks, total_work_minutes
        )

        return {
            'total_work_minutes': total_work_minutes,
            'total_intervals_completed': total_intervals,
            'total_breaks_taken': total_breaks,
            'total_sessions': total_sessions,
            'breaks_on_time': breaks_on_time,
            'breaks_compliant': compliant_breaks,
            'average_break_duration': average_break_duration,
            'productivity_score': productivity_score,
            'streak_maintained': total_sessions > 0
        }

    def _calculate_productivity_score(self, sessions, breaks, compliant_breaks, work_minutes):
        """Calculate productivity score (0-100)"""
        if sessions == 0:
            return 0.0

        # Compliance rate (40% weight)
        compliance_rate = (compliant_breaks / breaks * 100) if breaks > 0 else 0

        # Session consistency (30% weight)
        consistency_score = min(100, sessions * 20)  # Up to 5 sessions = 100%

        # Break frequency (30% weight)
        expected_breaks = work_minutes // 20  # One break every 20 minutes
        frequency_score = min(100, (breaks / max(1, expected_breaks)) * 100)

        productivity_score = (
            compliance_rate * 0.4 +
            consistency_score * 0.3 +
            frequency_score * 0.3
        )

        return round(productivity_score, 1)

    def _update_user_streak_data(self, user, force=False):
        """Update user streak data based on daily statistics"""
        streak_data, created = UserStreakData.objects.get_or_create(user=user)

        if created or force:
            # Recalculate from all sessions
            all_sessions = TimerSession.objects.filter(
                user=user,
                is_active=False
            ).order_by('start_time')

            if all_sessions.exists():
                # Update total sessions
                streak_data.total_sessions_completed = all_sessions.count()

                # Calculate total break time
                all_breaks = BreakRecord.objects.filter(
                    user=user,
                    break_completed=True
                )
                total_break_seconds = sum(br.break_duration_seconds for br in all_breaks)
                streak_data.total_break_time_minutes = total_break_seconds // 60

                # Calculate average session length
                total_duration = sum(session.duration_minutes for session in all_sessions)
                streak_data.average_session_length = total_duration / all_sessions.count()

                # Calculate current and best streaks
                self._calculate_streaks(user, streak_data)

                streak_data.save()

    def _calculate_streaks(self, user, streak_data):
        """Calculate current and best daily streaks"""
        # Get daily stats ordered by date
        daily_stats = DailyStats.objects.filter(
            user=user,
            total_sessions__gt=0
        ).order_by('date')

        if not daily_stats.exists():
            streak_data.current_daily_streak = 0
            streak_data.best_daily_streak = 0
            return

        # Calculate streaks
        current_streak = 0
        best_streak = 0
        temp_streak = 0
        last_date = None

        for stat in daily_stats:
            if last_date is None:
                temp_streak = 1
            elif stat.date == last_date + timedelta(days=1):
                temp_streak += 1
            else:
                temp_streak = 1

            best_streak = max(best_streak, temp_streak)
            last_date = stat.date

        # Current streak is only valid if it includes today or yesterday
        today = date.today()
        if last_date and last_date >= today - timedelta(days=1):
            current_streak = temp_streak
        else:
            current_streak = 0

        streak_data.current_daily_streak = current_streak
        streak_data.best_daily_streak = best_streak

    def _update_weekly_stats(self, users):
        """Update weekly aggregated statistics"""
        self.stdout.write('Updating weekly statistics...')

        # Get current week
        today = date.today()
        week_start = today - timedelta(days=today.weekday())
        week_end = week_start + timedelta(days=6)

        for user in users:
            self._calculate_weekly_stats(user, week_start, week_end)

    def _calculate_weekly_stats(self, user, week_start, week_end):
        """Calculate weekly statistics for a user"""
        daily_stats = DailyStats.objects.filter(
            user=user,
            date__gte=week_start,
            date__lte=week_end
        )

        if daily_stats.exists():
            weekly_stat, created = WeeklyStats.objects.get_or_create(
                user=user,
                week_start_date=week_start,
                defaults={
                    'week_end_date': week_end,
                    'total_work_minutes': 0,
                    'total_intervals_completed': 0,
                    'total_breaks_taken': 0,
                    'total_sessions': 0,
                    'active_days': 0,
                    'total_breaks_compliant': 0,
                    'weekly_compliance_rate': 0.0,
                    'weekly_productivity_score': 0.0
                }
            )

            # Calculate aggregated values
            total_work_minutes = sum(stat.total_work_minutes for stat in daily_stats)
            total_intervals = sum(stat.total_intervals_completed for stat in daily_stats)
            total_breaks = sum(stat.total_breaks_taken for stat in daily_stats)
            total_sessions = sum(stat.total_sessions for stat in daily_stats)
            total_compliant = sum(stat.breaks_compliant for stat in daily_stats)
            active_days = daily_stats.filter(total_sessions__gt=0).count()

            # Update weekly stats
            weekly_stat.total_work_minutes = total_work_minutes
            weekly_stat.total_intervals_completed = total_intervals
            weekly_stat.total_breaks_taken = total_breaks
            weekly_stat.total_sessions = total_sessions
            weekly_stat.active_days = active_days
            weekly_stat.total_breaks_compliant = total_compliant

            if total_breaks > 0:
                weekly_stat.weekly_compliance_rate = (total_compliant / total_breaks) * 100

            # Calculate weekly averages
            if active_days > 0:
                weekly_stat.average_daily_work_minutes = total_work_minutes / active_days
                weekly_stat.average_daily_breaks = total_breaks / active_days

            # Calculate productivity score
            avg_productivity = sum(stat.productivity_score for stat in daily_stats) / len(daily_stats)
            weekly_stat.weekly_productivity_score = avg_productivity

            weekly_stat.save()

    def _update_monthly_stats(self, users):
        """Update monthly aggregated statistics"""
        self.stdout.write('Updating monthly statistics...')

        # Get current month
        today = date.today()
        month_start = today.replace(day=1)

        for user in users:
            self._calculate_monthly_stats(user, month_start.year, month_start.month)

    def _calculate_monthly_stats(self, user, year, month):
        """Calculate monthly statistics for a user"""
        # Get daily stats for the month
        daily_stats = DailyStats.objects.filter(
            user=user,
            date__year=year,
            date__month=month
        )

        if daily_stats.exists():
            monthly_stat, created = MonthlyStats.objects.get_or_create(
                user=user,
                year=year,
                month=month,
                defaults={
                    'total_work_minutes': 0,
                    'total_intervals_completed': 0,
                    'total_breaks_taken': 0,
                    'total_sessions': 0,
                    'active_days': 0,
                    'monthly_goal_minutes': 0,
                    'goal_achieved': False,
                    'estimated_eye_strain_reduction': 0.0
                }
            )

            # Calculate aggregated values
            total_work_minutes = sum(stat.total_work_minutes for stat in daily_stats)
            total_intervals = sum(stat.total_intervals_completed for stat in daily_stats)
            total_breaks = sum(stat.total_breaks_taken for stat in daily_stats)
            total_sessions = sum(stat.total_sessions for stat in daily_stats)
            active_days = daily_stats.filter(total_sessions__gt=0).count()

            # Update monthly stats
            monthly_stat.total_work_minutes = total_work_minutes
            monthly_stat.total_intervals_completed = total_intervals
            monthly_stat.total_breaks_taken = total_breaks
            monthly_stat.total_sessions = total_sessions
            monthly_stat.active_days = active_days

            # Estimate eye strain reduction
            avg_compliance = sum(stat.compliance_rate for stat in daily_stats) / len(daily_stats)
            monthly_stat.estimated_eye_strain_reduction = min(50, avg_compliance * 0.5)

            monthly_stat.save()

    def _daterange(self, start_date, end_date):
        """Generate date range"""
        for n in range(int((end_date - start_date).days) + 1):
            yield start_date + timedelta(n)