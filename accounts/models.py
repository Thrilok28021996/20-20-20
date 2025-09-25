from typing import Optional, Dict, Any
from django.contrib.auth.models import AbstractUser
from django.db import models
from django.utils import timezone


class User(AbstractUser):
    """
    Custom User model extending Django's AbstractUser
    Implements user authentication and profile management for the 20-20-20 rule SaaS
    """
    email = models.EmailField(unique=True)
    
    class Meta:
        db_table = 'accounts_user'
        indexes = [
            models.Index(fields=['stripe_customer_id']),
            models.Index(fields=['subscription_type', 'subscription_end_date']),
            models.Index(fields=['email']),
        ]
    first_name = models.CharField(max_length=150, blank=True)
    last_name = models.CharField(max_length=150, blank=True)
    
    # Profile fields
    date_joined = models.DateTimeField(default=timezone.now)
    is_verified = models.BooleanField(default=False)
    
    # Subscription fields
    subscription_type = models.CharField(
        max_length=20,
        choices=[
            ('free', 'Free'),
            ('premium', 'Premium')
        ],
        default='free'
    )
    
    # Stripe integration
    stripe_customer_id = models.CharField(max_length=100, blank=True, null=True)
    subscription_start_date = models.DateTimeField(null=True, blank=True)
    subscription_end_date = models.DateTimeField(null=True, blank=True)
    
    # Notification preferences
    email_notifications = models.BooleanField(default=True)
    break_reminders = models.BooleanField(default=True)
    daily_summary = models.BooleanField(default=True)
    weekly_report = models.BooleanField(default=True)
    
    # User preferences
    work_start_time = models.TimeField(null=True, blank=True)
    work_end_time = models.TimeField(null=True, blank=True)
    break_duration = models.IntegerField(default=20)  # seconds
    reminder_sound = models.BooleanField(default=True)
    
    USERNAME_FIELD = 'email'
    REQUIRED_FIELDS = ['username']
    
    def __str__(self) -> str:
        return f"{self.email} ({self.get_subscription_type_display()})"

    @property
    def is_premium_user(self) -> bool:
        return self.subscription_type == 'premium'

    @property
    def is_subscription_active(self) -> bool:
        if not self.subscription_end_date:
            return False
        return timezone.now() < self.subscription_end_date

    def get_full_name(self) -> str:
        return f"{self.first_name} {self.last_name}".strip() or self.username


class UserProfile(models.Model):
    """
    Extended user profile information
    """
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='profile')
    
    # Demographics
    age = models.PositiveIntegerField(null=True, blank=True)
    occupation = models.CharField(max_length=100, blank=True)
    daily_screen_time_hours = models.FloatField(default=8.0)
    
    # Eye health information
    wears_glasses = models.BooleanField(default=False)
    has_eye_strain = models.BooleanField(default=True)
    last_eye_checkup = models.DateField(null=True, blank=True)
    
    # Usage statistics
    total_breaks_taken = models.PositiveIntegerField(default=0)
    total_screen_time_minutes = models.PositiveIntegerField(default=0)
    longest_streak_days = models.PositiveIntegerField(default=0)
    current_streak_days = models.PositiveIntegerField(default=0)
    
    # Settings
    timezone = models.CharField(max_length=50, default='UTC')
    preferred_language = models.CharField(max_length=10, default='en')
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        db_table = 'accounts_userprofile'
        verbose_name = 'User Profile'
        verbose_name_plural = 'User Profiles'
    
    def __str__(self):
        return f"Profile of {self.user.email}"
    
    @property
    def can_use_premium_features(self) -> bool:
        """Check if user can access premium features"""
        return self.user.is_premium_user and self.user.is_subscription_active


class Achievement(models.Model):
    """
    User achievements for premium gamification features
    """
    ACHIEVEMENT_TYPES = [
        ('streak_7', '7 Day Streak'),
        ('streak_30', '30 Day Streak'),
        ('streak_100', '100 Day Streak'),
        ('early_bird', 'Early Bird (5 AM - 9 AM sessions)'),
        ('night_owl', 'Night Owl (6 PM - 12 AM sessions)'),
        ('weekend_warrior', 'Weekend Warrior'),
        ('session_master', '1000 Sessions Complete'),
        ('eye_health_champion', 'Perfect Week'),
    ]
    
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='achievements')
    achievement_type = models.CharField(max_length=20, choices=ACHIEVEMENT_TYPES)
    earned_at = models.DateTimeField(auto_now_add=True)
    description = models.TextField(blank=True)
    
    class Meta:
        db_table = 'accounts_achievement'
        unique_together = ['user', 'achievement_type']
        verbose_name = 'Achievement'
        verbose_name_plural = 'Achievements'
    
    def __str__(self):
        return f"{self.user.email} - {self.get_achievement_type_display()}"


class UserStreakData(models.Model):
    """
    Track user streaks for premium analytics
    """
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='streak_data')
    
    # Current streaks
    current_daily_streak = models.PositiveIntegerField(default=0)
    current_weekly_streak = models.PositiveIntegerField(default=0)
    
    # Best streaks
    best_daily_streak = models.PositiveIntegerField(default=0)
    best_weekly_streak = models.PositiveIntegerField(default=0)
    
    # Tracking dates
    last_session_date = models.DateField(null=True, blank=True)
    streak_start_date = models.DateField(null=True, blank=True)
    
    # Premium analytics
    total_sessions_completed = models.PositiveIntegerField(default=0)
    total_break_time_minutes = models.PositiveIntegerField(default=0)
    average_session_length = models.FloatField(default=0.0)
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        db_table = 'accounts_userstreakdata'
        verbose_name = 'User Streak Data'
        verbose_name_plural = 'User Streak Data'
    
    def __str__(self):
        return f"{self.user.email} - {self.current_daily_streak} day streak"


class UserLevel(models.Model):
    """
    User leveling system for gamification
    """
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='level_data')

    # Current level and experience
    current_level = models.PositiveIntegerField(default=1)
    total_experience_points = models.PositiveIntegerField(default=0)
    experience_to_next_level = models.PositiveIntegerField(default=100)

    # Level progression
    sessions_completed = models.PositiveIntegerField(default=0)
    breaks_completed = models.PositiveIntegerField(default=0)
    compliant_breaks = models.PositiveIntegerField(default=0)

    # Special achievements count
    achievements_earned = models.PositiveIntegerField(default=0)
    perfect_days = models.PositiveIntegerField(default=0)  # Days with 100% compliance

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'accounts_userlevel'
        verbose_name = 'User Level'
        verbose_name_plural = 'User Levels'

    def __str__(self):
        return f"{self.user.email} - Level {self.current_level}"

    def add_experience(self, points: int) -> None:
        """Add experience points and check for level up"""
        self.total_experience_points += points

        while self.total_experience_points >= self.experience_to_next_level:
            self._level_up()

        self.save()

    def _level_up(self) -> None:
        """Handle level up logic"""
        self.current_level += 1
        self.total_experience_points -= self.experience_to_next_level
        # Increase XP requirement for next level (progressive difficulty)
        self.experience_to_next_level = int(self.experience_to_next_level * 1.2)

        # Could trigger level up rewards here
        from .signals import level_up_signal
        level_up_signal.send(sender=self.__class__, user=self.user, new_level=self.current_level)

    def get_level_title(self) -> str:
        """Get user's level title"""
        level_titles = {
            1: "Newcomer",
            5: "Eye Care Apprentice",
            10: "Break Master",
            15: "Vision Guardian",
            20: "Eye Health Expert",
            25: "Wellness Champion",
            30: "Health Guru",
            40: "Eye Care Legend",
            50: "20-20-20 Master"
        }

        title = "Newcomer"
        for level, level_title in sorted(level_titles.items()):
            if self.current_level >= level:
                title = level_title

        return title


class Badge(models.Model):
    """
    Available badges that users can earn
    """
    name = models.CharField(max_length=100, unique=True)
    description = models.TextField()
    icon = models.CharField(max_length=50, blank=True)  # Icon class or emoji
    category = models.CharField(max_length=50, default='general')

    # Requirements
    requires_streak_days = models.PositiveIntegerField(null=True, blank=True)
    requires_sessions = models.PositiveIntegerField(null=True, blank=True)
    requires_compliant_breaks = models.PositiveIntegerField(null=True, blank=True)
    requires_perfect_days = models.PositiveIntegerField(null=True, blank=True)

    # Special requirements (JSON field for complex conditions)
    special_requirements = models.JSONField(default=dict, blank=True)

    # Badge properties
    is_active = models.BooleanField(default=True)
    rarity = models.CharField(
        max_length=10,
        choices=[
            ('common', 'Common'),
            ('rare', 'Rare'),
            ('epic', 'Epic'),
            ('legendary', 'Legendary'),
        ],
        default='common'
    )
    experience_reward = models.PositiveIntegerField(default=50)

    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'accounts_badge'
        verbose_name = 'Badge'
        verbose_name_plural = 'Badges'
        ordering = ['category', 'name']

    def __str__(self):
        return f"{self.name} ({self.get_rarity_display()})"


class UserBadge(models.Model):
    """
    Badges earned by users
    """
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='earned_badges')
    badge = models.ForeignKey(Badge, on_delete=models.CASCADE)

    earned_at = models.DateTimeField(auto_now_add=True)
    progress_data = models.JSONField(default=dict, blank=True)  # Track progress toward badge

    class Meta:
        db_table = 'accounts_userbadge'
        verbose_name = 'User Badge'
        verbose_name_plural = 'User Badges'
        unique_together = ['user', 'badge']
        ordering = ['-earned_at']

    def __str__(self):
        return f"{self.user.email} - {self.badge.name}"


class Challenge(models.Model):
    """
    Time-limited challenges for users
    """
    name = models.CharField(max_length=100)
    description = models.TextField()

    # Challenge timing
    start_date = models.DateTimeField()
    end_date = models.DateTimeField()

    # Challenge requirements
    CHALLENGE_TYPES = [
        ('daily_streak', 'Daily Streak Challenge'),
        ('session_count', 'Session Count Challenge'),
        ('compliance_rate', 'Compliance Rate Challenge'),
        ('community', 'Community Challenge'),
    ]
    challenge_type = models.CharField(max_length=20, choices=CHALLENGE_TYPES)
    target_value = models.PositiveIntegerField()  # Target sessions, days, percentage, etc.

    # Rewards
    experience_reward = models.PositiveIntegerField(default=100)
    badge_reward = models.ForeignKey(Badge, null=True, blank=True, on_delete=models.SET_NULL)

    # Challenge properties
    is_active = models.BooleanField(default=True)
    is_premium_only = models.BooleanField(default=False)
    max_participants = models.PositiveIntegerField(null=True, blank=True)

    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'accounts_challenge'
        verbose_name = 'Challenge'
        verbose_name_plural = 'Challenges'
        ordering = ['-start_date']

    def __str__(self):
        return f"{self.name} ({self.start_date.date()} - {self.end_date.date()})"

    @property
    def is_current(self) -> bool:
        """Check if challenge is currently active"""
        now = timezone.now()
        return self.start_date <= now <= self.end_date

    def get_participant_count(self) -> int:
        """Get number of users participating in this challenge"""
        return self.participants.count()


class ChallengeParticipation(models.Model):
    """
    User participation in challenges
    """
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='challenge_participations')
    challenge = models.ForeignKey(Challenge, on_delete=models.CASCADE, related_name='participants')

    # Progress tracking
    current_progress = models.PositiveIntegerField(default=0)
    is_completed = models.BooleanField(default=False)
    completed_at = models.DateTimeField(null=True, blank=True)

    # Ranking
    final_rank = models.PositiveIntegerField(null=True, blank=True)

    joined_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'accounts_challengeparticipation'
        verbose_name = 'Challenge Participation'
        verbose_name_plural = 'Challenge Participations'
        unique_together = ['user', 'challenge']
        ordering = ['-current_progress']

    def __str__(self):
        return f"{self.user.email} - {self.challenge.name} ({self.current_progress}/{self.challenge.target_value})"

    def update_progress(self, new_progress: int) -> None:
        """Update challenge progress and check for completion"""
        self.current_progress = new_progress

        if not self.is_completed and new_progress >= self.challenge.target_value:
            self.is_completed = True
            self.completed_at = timezone.now()

            # Award experience and badge if applicable
            if self.challenge.experience_reward:
                level_data, created = UserLevel.objects.get_or_create(user=self.user)
                level_data.add_experience(self.challenge.experience_reward)

            if self.challenge.badge_reward:
                UserBadge.objects.get_or_create(
                    user=self.user,
                    badge=self.challenge.badge_reward
                )

        self.save()

    @property
    def progress_percentage(self) -> float:
        """Get completion percentage"""
        if self.challenge.target_value == 0:
            return 0.0
        return min(100.0, (self.current_progress / self.challenge.target_value) * 100)