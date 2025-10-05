from typing import Optional, Dict, Any, List, Union
from django.db import models
from django.conf import settings
from django.utils import timezone
from datetime import date, timedelta


class DailyStats(models.Model):
    """
    Daily aggregated statistics per user
    """
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='daily_stats')
    date = models.DateField(default=timezone.now)
    
    # Work statistics
    total_work_minutes = models.PositiveIntegerField(default=0)
    total_intervals_completed = models.PositiveIntegerField(default=0)
    total_breaks_taken = models.PositiveIntegerField(default=0)
    total_sessions = models.PositiveIntegerField(default=0)
    
    # Compliance statistics
    breaks_on_time = models.PositiveIntegerField(default=0)  # Breaks taken within 1 min of reminder
    breaks_compliant = models.PositiveIntegerField(default=0)  # Breaks that followed 20-20-20 rule
    average_break_duration = models.FloatField(default=0.0)
    
    # Streak tracking
    streak_maintained = models.BooleanField(default=False)
    
    # Performance metrics
    productivity_score = models.FloatField(default=0.0)  # 0-100 score based on compliance
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        db_table = 'analytics_daily_stats'
        verbose_name = 'Daily Statistics'
        verbose_name_plural = 'Daily Statistics'
        unique_together = ['user', 'date']
        ordering = ['-date']
        indexes = [
            models.Index(fields=['user', 'date']),
            models.Index(fields=['date']),
        ]
    
    def __str__(self):
        return f"{self.user.email} - {self.date}"
    
    @property
    def compliance_rate(self) -> float:
        if self.total_breaks_taken == 0:
            return 0.0
        return (self.breaks_compliant / self.total_breaks_taken) * 100


class WeeklyStats(models.Model):
    """
    Weekly aggregated statistics per user
    """
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='weekly_stats')
    week_start_date = models.DateField()  # Monday of the week
    week_end_date = models.DateField()
    
    # Aggregated work statistics
    total_work_minutes = models.PositiveIntegerField(default=0)
    total_intervals_completed = models.PositiveIntegerField(default=0)
    total_breaks_taken = models.PositiveIntegerField(default=0)
    total_sessions = models.PositiveIntegerField(default=0)
    
    # Days active this week
    active_days = models.PositiveIntegerField(default=0)
    
    # Weekly averages
    average_daily_work_minutes = models.FloatField(default=0.0)
    average_daily_breaks = models.FloatField(default=0.0)
    
    # Compliance statistics
    total_breaks_compliant = models.PositiveIntegerField(default=0)
    weekly_compliance_rate = models.FloatField(default=0.0)
    
    # Performance
    weekly_productivity_score = models.FloatField(default=0.0)
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        db_table = 'analytics_weekly_stats'
        verbose_name = 'Weekly Statistics'
        verbose_name_plural = 'Weekly Statistics'
        unique_together = ['user', 'week_start_date']
        ordering = ['-week_start_date']
    
    def __str__(self):
        return f"{self.user.email} - Week of {self.week_start_date}"


class MonthlyStats(models.Model):
    """
    Monthly aggregated statistics per user
    """
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='monthly_stats')
    year = models.PositiveIntegerField()
    month = models.PositiveIntegerField()  # 1-12
    
    # Aggregated work statistics
    total_work_minutes = models.PositiveIntegerField(default=0)
    total_intervals_completed = models.PositiveIntegerField(default=0)
    total_breaks_taken = models.PositiveIntegerField(default=0)
    total_sessions = models.PositiveIntegerField(default=0)
    
    # Days active this month
    active_days = models.PositiveIntegerField(default=0)
    
    # Monthly patterns
    most_productive_day_of_week = models.CharField(max_length=10, blank=True)  # Monday, Tuesday, etc.
    most_productive_hour = models.PositiveIntegerField(null=True, blank=True)  # 0-23
    
    # Monthly goals and achievements
    monthly_goal_minutes = models.PositiveIntegerField(default=0)
    goal_achieved = models.BooleanField(default=False)
    
    # Health metrics
    estimated_eye_strain_reduction = models.FloatField(default=0.0)  # Percentage
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        db_table = 'analytics_monthly_stats'
        verbose_name = 'Monthly Statistics'
        verbose_name_plural = 'Monthly Statistics'
        unique_together = ['user', 'year', 'month']
        ordering = ['-year', '-month']
    
    def __str__(self):
        return f"{self.user.email} - {self.year}-{self.month:02d}"


class UserBehaviorEvent(models.Model):
    """
    Track specific user behavior events for analytics
    """
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='behavior_events')
    
    EVENT_TYPES = [
        ('login', 'User Login'),
        ('logout', 'User Logout'),
        ('session_start', 'Timer Session Started'),
        ('session_end', 'Timer Session Ended'),
        ('break_reminder_shown', 'Break Reminder Shown'),
        ('break_taken', 'Break Taken'),
        ('break_skipped', 'Break Skipped'),
        ('settings_changed', 'Settings Modified'),
        ('subscription_upgraded', 'Subscription Upgraded'),
        ('subscription_downgraded', 'Subscription Downgraded'),
        ('email_opened', 'Email Notification Opened'),
        ('feature_used', 'Feature Used'),
    ]
    
    event_type = models.CharField(max_length=30, choices=EVENT_TYPES)
    timestamp = models.DateTimeField(default=timezone.now)
    
    # Additional event data (stored as JSON-like text)
    event_data = models.JSONField(default=dict, blank=True)
    
    # Context information
    session_id = models.CharField(max_length=100, blank=True)
    user_agent = models.TextField(blank=True)
    ip_address = models.GenericIPAddressField(null=True, blank=True)
    
    class Meta:
        db_table = 'analytics_user_behavior_event'
        verbose_name = 'User Behavior Event'
        verbose_name_plural = 'User Behavior Events'
        ordering = ['-timestamp']
        indexes = [
            models.Index(fields=['user', 'event_type', 'timestamp']),
            models.Index(fields=['timestamp']),
        ]
    
    def __str__(self):
        return f"{self.user.email} - {self.get_event_type_display()} - {self.timestamp}"


class EngagementMetrics(models.Model):
    """
    Track user engagement and retention metrics
    """
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='engagement_metrics')
    date = models.DateField(default=timezone.now)
    
    # Daily engagement
    daily_active = models.BooleanField(default=False)
    session_duration_minutes = models.PositiveIntegerField(default=0)
    pages_visited = models.PositiveIntegerField(default=0)
    features_used = models.PositiveIntegerField(default=0)
    
    # Interaction quality
    breaks_interaction_score = models.FloatField(default=0.0)  # How well user interacts with breaks
    settings_customization_score = models.FloatField(default=0.0)  # How much user customizes
    
    # Retention indicators
    days_since_last_active = models.PositiveIntegerField(default=0)
    risk_of_churn = models.FloatField(default=0.0)  # 0-1 score
    
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        db_table = 'analytics_engagement_metrics'
        verbose_name = 'Engagement Metrics'
        verbose_name_plural = 'Engagement Metrics'
        unique_together = ['user', 'date']
        ordering = ['-date']
    
    def __str__(self):
        return f"Engagement - {self.user.email} - {self.date}"


class UserSession(models.Model):
    """
    Track real-time user sessions for active users count
    """
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='user_sessions')
    session_key = models.CharField(max_length=100, unique=True)
    
    # Session tracking
    login_time = models.DateTimeField(default=timezone.now)
    last_activity = models.DateTimeField(default=timezone.now)
    logout_time = models.DateTimeField(null=True, blank=True)
    is_active = models.BooleanField(default=True)
    
    # Session details
    ip_address = models.GenericIPAddressField(null=True, blank=True)
    user_agent = models.TextField(blank=True)
    device_type = models.CharField(max_length=20, blank=True)  # mobile, desktop, tablet
    
    # Activity tracking
    timer_sessions_started = models.PositiveIntegerField(default=0)
    breaks_taken_in_session = models.PositiveIntegerField(default=0)
    pages_viewed = models.PositiveIntegerField(default=0)
    
    class Meta:
        db_table = 'analytics_user_session'
        verbose_name = 'User Session'
        verbose_name_plural = 'User Sessions'
        ordering = ['-last_activity']
        indexes = [
            models.Index(fields=['is_active', 'last_activity']),
            models.Index(fields=['user', 'is_active']),
        ]
    
    def __str__(self):
        status = "Active" if self.is_active else "Inactive"
        return f"{self.user.email} - {status} - {self.last_activity}"
    
    @property
    def session_duration(self) -> int:
        """Calculate session duration in minutes"""
        end_time = self.logout_time or timezone.now()
        return int((end_time - self.login_time).total_seconds() / 60)
    
    @classmethod
    def get_active_users_count(cls) -> int:
        """Get count of currently active users"""
        cutoff_time = timezone.now() - timedelta(minutes=5)  # Active within last 5 minutes
        return cls.objects.filter(
            is_active=True,
            last_activity__gte=cutoff_time
        ).count()
    
    @classmethod
    def get_real_time_breaks_count(cls) -> int:
        """Get total breaks taken today across all active sessions"""
        today = timezone.now().date()
        return cls.objects.filter(
            login_time__date=today
        ).aggregate(
            total_breaks=models.Sum('breaks_taken_in_session')
        )['total_breaks'] or 0


class UserSatisfactionRating(models.Model):
    """
    Track user satisfaction ratings and feedback
    """
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='satisfaction_ratings')
    
    # Rating details
    rating = models.PositiveIntegerField(choices=[(i, f"{i} Stars") for i in range(1, 6)])  # 1-5 stars
    rating_date = models.DateTimeField(default=timezone.now)
    
    # Context of rating
    RATING_CONTEXTS = [
        ('break_completion', 'After Break Completion'),
        ('session_end', 'After Session End'),
        ('weekly_summary', 'Weekly Summary'),
        ('monthly_report', 'Monthly Report'),
        ('feature_usage', 'Feature Usage'),
        ('general', 'General Rating'),
    ]
    context = models.CharField(max_length=20, choices=RATING_CONTEXTS, default='general')
    
    # Optional feedback
    feedback_text = models.TextField(blank=True)
    
    # Satisfaction categories
    ease_of_use_rating = models.PositiveIntegerField(null=True, blank=True, choices=[(i, i) for i in range(1, 6)])
    effectiveness_rating = models.PositiveIntegerField(null=True, blank=True, choices=[(i, i) for i in range(1, 6)])
    reminder_helpfulness = models.PositiveIntegerField(null=True, blank=True, choices=[(i, i) for i in range(1, 6)])
    
    # NPS (Net Promoter Score) - Would recommend to others?
    would_recommend = models.BooleanField(null=True, blank=True)
    recommendation_score = models.PositiveIntegerField(
        null=True, blank=True, 
        choices=[(i, i) for i in range(0, 11)],  # 0-10 scale
        help_text="0-10: How likely are you to recommend this to a friend?"
    )
    
    # Metadata
    session_id = models.CharField(max_length=100, blank=True)
    break_count_when_rated = models.PositiveIntegerField(default=0)
    days_since_signup = models.PositiveIntegerField(default=0)
    
    class Meta:
        db_table = 'analytics_satisfaction_rating'
        verbose_name = 'User Satisfaction Rating'
        verbose_name_plural = 'User Satisfaction Ratings'
        ordering = ['-rating_date']
        indexes = [
            models.Index(fields=['rating', 'rating_date']),
            models.Index(fields=['context', 'rating_date']),
        ]
    
    def __str__(self):
        return f"{self.user.email} - {self.rating}★ - {self.get_context_display()}"
    
    @classmethod
    def get_average_satisfaction(cls, days: int = 30) -> float:
        """Get average satisfaction rating for last N days"""
        cutoff_date = timezone.now() - timedelta(days=days)
        ratings = cls.objects.filter(rating_date__gte=cutoff_date)
        if ratings.exists():
            return ratings.aggregate(avg_rating=models.Avg('rating'))['avg_rating']
        return 0.0
    
    @classmethod
    def get_nps_score(cls, days: int = 30) -> float:
        """Calculate Net Promoter Score for last N days"""
        cutoff_date = timezone.now() - timedelta(days=days)
        ratings = cls.objects.filter(
            rating_date__gte=cutoff_date,
            recommendation_score__isnull=False
        )

        if not ratings.exists():
            return 0.0

        total_count = ratings.count()
        promoters = ratings.filter(recommendation_score__gte=9).count()
        detractors = ratings.filter(recommendation_score__lte=6).count()

        nps = ((promoters - detractors) / total_count) * 100
        return round(nps, 1)


class RealTimeMetrics(models.Model):
    """
    Store real-time system-wide metrics updated frequently
    """
    timestamp = models.DateTimeField(default=timezone.now, db_index=True)  # Added index for performance

    # Active users metrics
    active_users_count = models.PositiveIntegerField(default=0)
    active_sessions_count = models.PositiveIntegerField(default=0)
    users_in_break = models.PositiveIntegerField(default=0)
    users_working = models.PositiveIntegerField(default=0)

    # Real-time counters
    total_breaks_today = models.PositiveIntegerField(default=0)
    total_work_minutes_today = models.PositiveIntegerField(default=0)
    total_sessions_today = models.PositiveIntegerField(default=0)

    # Satisfaction metrics
    average_satisfaction_rating = models.FloatField(default=0.0)
    nps_score = models.FloatField(default=0.0)

    # System health
    server_response_time_ms = models.PositiveIntegerField(default=0)
    database_query_time_ms = models.PositiveIntegerField(default=0)

    class Meta:
        db_table = 'analytics_realtime_metrics'
        verbose_name = 'Real-Time Metrics'
        verbose_name_plural = 'Real-Time Metrics'
        ordering = ['-timestamp']
        indexes = [
            models.Index(fields=['-timestamp'], name='realtime_ts_idx'),
        ]
    
    def __str__(self):
        return f"Metrics - {self.timestamp} - {self.active_users_count} active users"
    
    @classmethod
    def get_latest_metrics(cls) -> 'RealTimeMetrics':
        """Get the most recent metrics or create default"""
        latest = cls.objects.first()
        if not latest:
            # Create initial metrics
            latest = cls.objects.create()
            latest.update_metrics()
        return latest
    
    def update_metrics(self) -> None:
        """
        Update all real-time metrics - Heavily optimized to reduce database queries

        Fixed: Added date filtering to prevent unbounded queries

        NOTE: For production, consider running this method via a background job (Celery)
        to avoid blocking requests. Example Celery task:

        @shared_task
        def update_realtime_metrics():
            from analytics.models import RealTimeMetrics
            latest = RealTimeMetrics.get_latest_metrics()
            latest.update_metrics()

        Then schedule it to run every 30-60 seconds.
        """
        from timer.models import TimerSession, BreakRecord
        from django.db.models import Q

        now = timezone.now()
        today = now.date()
        cutoff_time = now - timedelta(minutes=5)  # Active within last 5 minutes
        break_cutoff = now - timedelta(minutes=2)  # Break cutoff time
        # Add date range to prevent loading all historical data
        date_range_start = today - timedelta(days=7)  # Only look at last 7 days for activity

        # Single optimized query for user session metrics
        # Filter to recent activity only to prevent loading all historical data
        user_session_stats = UserSession.objects.filter(
            last_activity__gte=date_range_start
        ).aggregate(
            active_users=Count(
                'id',
                filter=Q(is_active=True, last_activity__gte=cutoff_time)
            ),
            active_sessions=Count('id', filter=Q(is_active=True))
        )

        # Single optimized query for timer session metrics
        # Filter to today's data only
        timer_session_stats = TimerSession.objects.filter(
            start_time__date__gte=date_range_start
        ).aggregate(
            users_working=Count('id', filter=Q(is_active=True)),
            sessions_today=Count('id', filter=Q(start_time__date=today)),
            work_minutes_today=Sum(
                'total_work_minutes',
                filter=Q(start_time__date=today)
            )
        )

        # Single optimized query for break metrics
        # Filter to today's data only
        break_stats = BreakRecord.objects.filter(
            break_start_time__date__gte=date_range_start
        ).aggregate(
            users_in_break=Count(
                'id',
                filter=Q(
                    break_start_time__gte=break_cutoff,
                    break_end_time__isnull=True
                )
            ),
            total_breaks_today=Count(
                'id',
                filter=Q(break_start_time__date=today)
            )
        )

        # Single optimized query for satisfaction metrics
        satisfaction_stats = UserSatisfactionRating.objects.filter(
            rating_date__gte=timezone.now() - timedelta(days=30)
        ).aggregate(
            avg_rating=Avg('rating'),
            total_count=Count('id'),
            promoters=Count('id', filter=Q(recommendation_score__gte=9)),
            detractors=Count('id', filter=Q(recommendation_score__lte=6)),
            nps_count=Count('id', filter=Q(recommendation_score__isnull=False))
        )

        # Update metrics from batch queries
        self.active_users_count = user_session_stats['active_users'] or 0
        self.active_sessions_count = user_session_stats['active_sessions'] or 0
        self.users_working = timer_session_stats['users_working'] or 0
        self.users_in_break = break_stats['users_in_break'] or 0
        self.total_breaks_today = break_stats['total_breaks_today'] or 0
        self.total_work_minutes_today = timer_session_stats['work_minutes_today'] or 0
        self.total_sessions_today = timer_session_stats['sessions_today'] or 0

        # Calculate satisfaction metrics from single query
        self.average_satisfaction_rating = satisfaction_stats['avg_rating'] or 0.0

        # Calculate NPS score
        nps_count = satisfaction_stats['nps_count'] or 0
        if nps_count > 0:
            promoters = satisfaction_stats['promoters'] or 0
            detractors = satisfaction_stats['detractors'] or 0
            self.nps_score = ((promoters - detractors) / nps_count) * 100
        else:
            self.nps_score = 0.0

        # Update timestamp
        self.timestamp = now
        self.save()


class LiveActivityFeed(models.Model):
    """
    Live activity feed for dashboard showing recent user activities
    """
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='activity_feed')
    timestamp = models.DateTimeField(default=timezone.now)
    
    ACTIVITY_TYPES = [
        ('session_started', 'Started Timer Session'),
        ('break_taken', 'Took Break'),
        ('goal_achieved', 'Goal Achieved'),
        ('streak_milestone', 'Streak Milestone'),
        ('satisfaction_rating', 'Rated Experience'),
        ('subscription_upgrade', 'Upgraded Plan'),
    ]
    
    activity_type = models.CharField(max_length=20, choices=ACTIVITY_TYPES)
    activity_data = models.JSONField(default=dict, blank=True)
    is_public = models.BooleanField(default=True)  # Show in public feed
    
    class Meta:
        db_table = 'analytics_live_activity_feed'
        verbose_name = 'Live Activity'
        verbose_name_plural = 'Live Activity Feed'
        ordering = ['-timestamp']
        indexes = [
            models.Index(fields=['is_public', 'timestamp']),
            models.Index(fields=['activity_type', 'timestamp']),
        ]
    
    def __str__(self):
        return f"{self.user.email} - {self.get_activity_type_display()} - {self.timestamp}"
    
    @classmethod
    def get_recent_public_activities(cls, limit: int = 10):
        """
        Get recent public activities for live feed

        Fixed: Added ordering to prevent inconsistent results
        """
        return cls.objects.filter(is_public=True).order_by('-timestamp')[:limit]


