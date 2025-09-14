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
    
    def __str__(self):
        return f"{self.email} ({self.get_subscription_type_display()})"
    
    @property
    def is_premium_user(self):
        return self.subscription_type == 'premium'
    
    @property
    def is_subscription_active(self):
        if not self.subscription_end_date:
            return False
        return timezone.now() < self.subscription_end_date
    
    def get_full_name(self):
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
    def can_use_premium_features(self):
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