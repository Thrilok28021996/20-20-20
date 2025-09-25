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
    timestamp = models.DateTimeField(default=timezone.now)
    
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
        """Update all real-time metrics - Heavily optimized to reduce database queries"""
        from timer.models import TimerSession, BreakRecord
        from django.db.models import Q

        now = timezone.now()
        today = now.date()
        cutoff_time = now - timedelta(minutes=5)  # Active within last 5 minutes
        break_cutoff = now - timedelta(minutes=2)  # Break cutoff time

        # Single optimized query for user session metrics
        user_session_stats = UserSession.objects.aggregate(
            active_users=Count(
                'id',
                filter=Q(is_active=True, last_activity__gte=cutoff_time)
            ),
            active_sessions=Count('id', filter=Q(is_active=True))
        )

        # Single optimized query for timer session metrics
        timer_session_stats = TimerSession.objects.aggregate(
            users_working=Count('id', filter=Q(is_active=True)),
            sessions_today=Count('id', filter=Q(start_time__date=today)),
            work_minutes_today=Sum(
                'total_work_minutes',
                filter=Q(start_time__date=today)
            )
        )

        # Single optimized query for break metrics
        break_stats = BreakRecord.objects.aggregate(
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
        """Get recent public activities for live feed"""
        return cls.objects.filter(is_public=True)[:limit]


class PremiumAnalyticsReport(models.Model):
    """
    Generated premium analytics reports for users
    """
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='premium_reports')

    # Report metadata
    report_type = models.CharField(
        max_length=20,
        choices=[
            ('weekly', 'Weekly Report'),
            ('monthly', 'Monthly Report'),
            ('quarterly', 'Quarterly Report'),
            ('yearly', 'Yearly Report'),
        ]
    )
    report_period_start = models.DateField()
    report_period_end = models.DateField()

    # Key metrics
    total_sessions = models.PositiveIntegerField(default=0)
    total_work_hours = models.FloatField(default=0.0)
    total_breaks = models.PositiveIntegerField(default=0)
    compliance_rate = models.FloatField(default=0.0)
    productivity_score = models.FloatField(default=0.0)

    # Advanced insights
    peak_productivity_hours = models.JSONField(default=list)  # [14, 15, 16] for 2-4pm
    most_productive_days = models.JSONField(default=list)  # ['Monday', 'Tuesday']
    break_patterns = models.JSONField(default=dict)  # Analysis of break timing
    improvement_suggestions = models.JSONField(default=list)  # AI-generated suggestions

    # Health impact metrics
    estimated_eye_strain_reduction = models.FloatField(default=0.0)
    estimated_productivity_boost = models.FloatField(default=0.0)
    health_score = models.FloatField(default=0.0)  # 0-100 overall health score

    # Comparison data
    vs_previous_period = models.JSONField(default=dict)  # % change from previous period
    vs_user_average = models.JSONField(default=dict)  # vs user's historical average
    vs_community_average = models.JSONField(default=dict)  # vs community benchmarks

    # Report status
    is_generated = models.BooleanField(default=False)
    generated_at = models.DateTimeField(null=True, blank=True)
    generation_time_seconds = models.PositiveIntegerField(default=0)

    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'analytics_premium_report'
        verbose_name = 'Premium Analytics Report'
        verbose_name_plural = 'Premium Analytics Reports'
        unique_together = ['user', 'report_type', 'report_period_start']
        ordering = ['-report_period_start']

    def __str__(self):
        return f"{self.user.email} - {self.get_report_type_display()} - {self.report_period_start}"

    def generate_report(self) -> None:
        """Generate the analytics report with insights"""
        start_time = timezone.now()

        # Calculate basic metrics
        self._calculate_basic_metrics()

        # Generate advanced insights
        self._analyze_productivity_patterns()
        self._calculate_health_impact()
        self._generate_improvement_suggestions()
        self._calculate_comparisons()

        # Mark as generated
        self.is_generated = True
        self.generated_at = timezone.now()
        self.generation_time_seconds = int((timezone.now() - start_time).total_seconds())
        self.save()

    def _calculate_basic_metrics(self) -> None:
        """Calculate basic report metrics"""
        from timer.models import TimerSession, BreakRecord

        # Get sessions in report period
        sessions = TimerSession.objects.filter(
            user=self.user,
            start_time__date__gte=self.report_period_start,
            start_time__date__lte=self.report_period_end,
            is_active=False
        )

        self.total_sessions = sessions.count()
        self.total_work_hours = sum(session.total_work_minutes for session in sessions) / 60.0

        # Get breaks in report period
        breaks = BreakRecord.objects.filter(
            user=self.user,
            break_start_time__date__gte=self.report_period_start,
            break_start_time__date__lte=self.report_period_end,
            break_completed=True
        )

        self.total_breaks = breaks.count()

        # Calculate compliance rate
        if self.total_breaks > 0:
            compliant_breaks = breaks.filter(
                break_duration_seconds__gte=20,
                looked_at_distance=True
            ).count()
            self.compliance_rate = (compliant_breaks / self.total_breaks) * 100
        else:
            self.compliance_rate = 0.0

        # Calculate productivity score (based on compliance, consistency, etc.)
        self.productivity_score = self._calculate_productivity_score(sessions, breaks)

    def _calculate_productivity_score(self, sessions, breaks):
        """Calculate overall productivity score (0-100)"""
        if not sessions.exists():
            return 0.0

        # Components of productivity score
        consistency_score = self._calculate_consistency_score(sessions)
        compliance_score = self.compliance_rate
        engagement_score = min(100, (self.total_work_hours / 40.0) * 100)  # Up to 40 hours/week

        # Weighted average
        productivity_score = (
            consistency_score * 0.4 +
            compliance_score * 0.4 +
            engagement_score * 0.2
        )

        return round(productivity_score, 1)

    def _calculate_consistency_score(self, sessions):
        """Calculate consistency score based on regular usage"""
        period_days = (self.report_period_end - self.report_period_start).days + 1
        active_days = sessions.values('start_time__date').distinct().count()

        if period_days == 0:
            return 0.0

        return min(100, (active_days / period_days) * 100)

    def _analyze_productivity_patterns(self):
        """Analyze when user is most productive"""
        from timer.models import TimerSession

        sessions = TimerSession.objects.filter(
            user=self.user,
            start_time__date__gte=self.report_period_start,
            start_time__date__lte=self.report_period_end,
            is_active=False
        )

        # Analyze peak hours
        hour_productivity = {}
        for session in sessions:
            hour = session.start_time.hour
            if hour not in hour_productivity:
                hour_productivity[hour] = 0
            hour_productivity[hour] += session.total_work_minutes

        # Find top 3 productive hours
        top_hours = sorted(hour_productivity.items(), key=lambda x: x[1], reverse=True)[:3]
        self.peak_productivity_hours = [hour for hour, _ in top_hours]

        # Analyze productive days
        day_productivity = {}
        for session in sessions:
            day = session.start_time.strftime('%A')
            if day not in day_productivity:
                day_productivity[day] = 0
            day_productivity[day] += session.total_work_minutes

        top_days = sorted(day_productivity.items(), key=lambda x: x[1], reverse=True)[:3]
        self.most_productive_days = [day for day, _ in top_days]

    def _calculate_health_impact(self):
        """Calculate estimated health impact"""
        # Estimates based on research
        breaks_per_hour = self.total_breaks / max(1, self.total_work_hours)
        recommended_breaks_per_hour = 3  # Every 20 minutes

        # Eye strain reduction (%)
        compliance_factor = self.compliance_rate / 100.0
        self.estimated_eye_strain_reduction = min(80, breaks_per_hour * compliance_factor * 25)

        # Productivity boost (%)
        self.estimated_productivity_boost = min(15, self.compliance_rate * 0.15)

        # Overall health score
        self.health_score = (
            self.compliance_rate * 0.6 +
            min(100, (breaks_per_hour / recommended_breaks_per_hour) * 100) * 0.4
        )

    def _generate_improvement_suggestions(self):
        """Generate AI-powered improvement suggestions"""
        suggestions = []

        if self.compliance_rate < 60:
            suggestions.append({
                'category': 'compliance',
                'title': 'Improve Break Compliance',
                'description': 'Try shorter break durations to build the habit.',
                'action': 'Consider using 10-second breaks initially.',
                'priority': 'high'
            })

        if self.total_work_hours < 20:
            suggestions.append({
                'category': 'engagement',
                'title': 'Increase Usage Consistency',
                'description': 'Regular daily usage helps build healthy habits.',
                'action': 'Set a daily goal of 4 hours with the timer.',
                'priority': 'medium'
            })

        if len(self.peak_productivity_hours) > 0:
            peak_hour = self.peak_productivity_hours[0]
            suggestions.append({
                'category': 'optimization',
                'title': 'Optimize Peak Hours',
                'description': f'You\'re most productive around {peak_hour}:00.',
                'action': 'Schedule important tasks during this time.',
                'priority': 'low'
            })

        self.improvement_suggestions = suggestions

    def _calculate_comparisons(self):
        """Calculate comparison metrics"""
        # This would implement comparisons vs previous period, user average, community
        self.vs_previous_period = {
            'sessions': 0,  # % change
            'compliance_rate': 0,
            'productivity_score': 0
        }

        self.vs_user_average = {
            'sessions': 0,
            'compliance_rate': 0,
            'productivity_score': 0
        }

        self.vs_community_average = {
            'sessions': 0,
            'compliance_rate': 0,
            'productivity_score': 0
        }


class PremiumInsight(models.Model):
    """
    AI-generated insights for premium users
    """
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='premium_insights')

    insight_type = models.CharField(
        max_length=20,
        choices=[
            ('pattern', 'Usage Pattern Insight'),
            ('achievement', 'Achievement Insight'),
            ('health', 'Health Impact Insight'),
            ('productivity', 'Productivity Insight'),
            ('recommendation', 'Recommendation'),
        ]
    )

    title = models.CharField(max_length=200)
    description = models.TextField()
    action_suggestion = models.TextField(blank=True)

    # Data backing the insight
    supporting_data = models.JSONField(default=dict)
    confidence_score = models.FloatField(default=0.0)  # 0-1 confidence in insight

    # Insight metadata
    is_active = models.BooleanField(default=True)
    priority = models.CharField(
        max_length=10,
        choices=[('low', 'Low'), ('medium', 'Medium'), ('high', 'High')],
        default='medium'
    )

    generated_at = models.DateTimeField(auto_now_add=True)
    expires_at = models.DateTimeField(null=True, blank=True)  # When insight becomes stale

    # User interaction
    viewed_at = models.DateTimeField(null=True, blank=True)
    dismissed_at = models.DateTimeField(null=True, blank=True)
    acted_on = models.BooleanField(default=False)

    class Meta:
        db_table = 'analytics_premium_insight'
        verbose_name = 'Premium Insight'
        verbose_name_plural = 'Premium Insights'
        ordering = ['-generated_at', '-priority']

    def __str__(self):
        return f"{self.user.email} - {self.title}"

    def mark_as_viewed(self) -> None:
        """Mark insight as viewed by user"""
        if not self.viewed_at:
            self.viewed_at = timezone.now()
            self.save()

    def dismiss(self) -> None:
        """User dismisses this insight"""
        self.dismissed_at = timezone.now()
        self.is_active = False
        self.save()