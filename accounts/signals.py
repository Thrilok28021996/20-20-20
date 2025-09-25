"""
Django signals for gamification system
"""
from django.dispatch import Signal, receiver
from django.db.models.signals import post_save
from django.utils import timezone
from datetime import date

# Custom signals
level_up_signal = Signal()

# Experience point values
EXPERIENCE_POINTS = {
    'session_completed': 25,
    'break_taken': 10,
    'compliant_break': 15,
    'perfect_day': 100,
    'streak_day': 5,
    'first_session_of_day': 20,
}


@receiver(post_save, sender='timer.TimerSession')
def award_session_completion_experience(sender, instance, created, **kwargs):
    """Award experience when a session is completed"""
    if not created and not instance.is_active and instance.end_time:
        # Session was just completed
        from .models import UserLevel

        level_data, created = UserLevel.objects.get_or_create(user=instance.user)
        level_data.sessions_completed += 1
        level_data.add_experience(EXPERIENCE_POINTS['session_completed'])

        # Check if this is first session of the day for bonus XP
        today = date.today()
        sessions_today = sender.objects.filter(
            user=instance.user,
            start_time__date=today
        ).count()

        if sessions_today == 1:
            level_data.add_experience(EXPERIENCE_POINTS['first_session_of_day'])


@receiver(post_save, sender='timer.BreakRecord')
def award_break_experience(sender, instance, created, **kwargs):
    """Award experience when a break is completed"""
    if not created and instance.break_completed:
        from .models import UserLevel

        level_data, created = UserLevel.objects.get_or_create(user=instance.user)
        level_data.breaks_completed += 1

        # Base XP for taking break
        experience_earned = EXPERIENCE_POINTS['break_taken']

        # Bonus XP for compliant break
        if instance.is_compliant:
            level_data.compliant_breaks += 1
            experience_earned += EXPERIENCE_POINTS['compliant_break']

        level_data.add_experience(experience_earned)


@receiver(level_up_signal)
def handle_level_up(sender, user, new_level, **kwargs):
    """Handle level up event - could trigger notifications, badges, etc."""
    from .models import UserLevel, Badge, UserBadge
    from notifications.models import Notification

    # Create level up notification
    Notification.objects.create(
        user=user,
        title=f"🎉 Level Up! You're now Level {new_level}!",
        message=f"Congratulations! You've reached Level {new_level}. Keep up the great work!",
        notification_type='achievement'
    )

    # Check for level-based badges
    level_badges = {
        5: "Level 5 - Eye Care Apprentice",
        10: "Level 10 - Break Master",
        15: "Level 15 - Vision Guardian",
        20: "Level 20 - Eye Health Expert",
        25: "Level 25 - Wellness Champion",
        30: "Level 30 - Health Guru",
        50: "Level 50 - 20-20-20 Master"
    }

    if new_level in level_badges:
        try:
            badge = Badge.objects.get(name=level_badges[new_level])
            UserBadge.objects.get_or_create(user=user, badge=badge)
        except Badge.DoesNotExist:
            pass  # Badge doesn't exist yet


def check_daily_achievements(user):
    """Check and award daily achievements"""
    from .models import UserLevel, Badge, UserBadge
    from timer.models import TimerSession, BreakRecord
    from analytics.models import DailyStats

    today = date.today()

    # Get today's stats
    try:
        daily_stats = DailyStats.objects.get(user=user, date=today)

        # Check for perfect day (100% break compliance)
        if (daily_stats.total_breaks_taken > 0 and
            daily_stats.breaks_compliant == daily_stats.total_breaks_taken):

            level_data, created = UserLevel.objects.get_or_create(user=user)
            level_data.perfect_days += 1
            level_data.add_experience(EXPERIENCE_POINTS['perfect_day'])

            # Award perfect day badge if applicable
            try:
                perfect_day_badge = Badge.objects.get(name="Perfect Day")
                UserBadge.objects.get_or_create(user=user, badge=perfect_day_badge)
            except Badge.DoesNotExist:
                pass

    except DailyStats.DoesNotExist:
        pass


def check_streak_achievements(user, streak_data):
    """Check and award streak-based achievements"""
    from .models import Badge, UserBadge, UserLevel

    # Award streak milestone badges
    streak_badges = {
        7: "Week Warrior",
        14: "Fortnight Focus",
        30: "Monthly Master",
        60: "Consistency Champion",
        100: "Century Striker",
        365: "Year-Long Legend"
    }

    current_streak = streak_data.current_daily_streak
    level_data, created = UserLevel.objects.get_or_create(user=user)

    for milestone, badge_name in streak_badges.items():
        if current_streak >= milestone:
            try:
                badge = Badge.objects.get(name=badge_name)
                badge_earned, created = UserBadge.objects.get_or_create(user=user, badge=badge)
                if created:
                    # Award XP for new badge
                    level_data.add_experience(badge.experience_reward)
                    level_data.achievements_earned += 1
                    level_data.save()
            except Badge.DoesNotExist:
                pass

    # Award daily streak XP
    if current_streak > 0:
        level_data.add_experience(EXPERIENCE_POINTS['streak_day'] * min(current_streak, 7))


def initialize_default_badges():
    """Create default badges for the system"""
    from .models import Badge

    default_badges = [
        {
            'name': 'First Session',
            'description': 'Complete your first timer session',
            'icon': '🚀',
            'category': 'milestone',
            'requires_sessions': 1,
            'rarity': 'common',
            'experience_reward': 50
        },
        {
            'name': 'Week Warrior',
            'description': 'Maintain a 7-day streak',
            'icon': '🗓️',
            'category': 'streak',
            'requires_streak_days': 7,
            'rarity': 'rare',
            'experience_reward': 100
        },
        {
            'name': 'Monthly Master',
            'description': 'Maintain a 30-day streak',
            'icon': '🏆',
            'category': 'streak',
            'requires_streak_days': 30,
            'rarity': 'epic',
            'experience_reward': 300
        },
        {
            'name': 'Century Striker',
            'description': 'Maintain a 100-day streak',
            'icon': '💯',
            'category': 'streak',
            'requires_streak_days': 100,
            'rarity': 'legendary',
            'experience_reward': 1000
        },
        {
            'name': 'Perfect Day',
            'description': 'Complete a day with 100% break compliance',
            'icon': '⭐',
            'category': 'compliance',
            'requires_perfect_days': 1,
            'rarity': 'rare',
            'experience_reward': 150
        },
        {
            'name': 'Eye Health Expert',
            'description': 'Complete 1000 compliant breaks',
            'icon': '👁️',
            'category': 'milestone',
            'requires_compliant_breaks': 1000,
            'rarity': 'epic',
            'experience_reward': 500
        },
        {
            'name': 'Early Bird',
            'description': 'Complete 10 sessions between 5 AM and 9 AM',
            'icon': '🌅',
            'category': 'timing',
            'special_requirements': {'early_morning_sessions': 10},
            'rarity': 'rare',
            'experience_reward': 200
        },
        {
            'name': 'Night Owl',
            'description': 'Complete 10 sessions between 6 PM and 12 AM',
            'icon': '🦉',
            'category': 'timing',
            'special_requirements': {'evening_sessions': 10},
            'rarity': 'rare',
            'experience_reward': 200
        },
    ]

    for badge_data in default_badges:
        Badge.objects.get_or_create(
            name=badge_data['name'],
            defaults=badge_data
        )