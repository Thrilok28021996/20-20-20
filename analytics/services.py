"""
Analytics service layer for calculations, insights, and reporting
Handles premium analytics, real-time metrics, and data aggregation
"""
from typing import Dict, List, Optional, Tuple, Union, Any
from django.db.models import QuerySet
from datetime import date, datetime, timedelta
from django.utils import timezone
from django.db.models import Sum, Count, Avg, Q, F, Max, Min
from django.db.models.functions import Extract, TruncDate, TruncHour
from django.contrib.auth import get_user_model
import logging

from .models import (
    DailyStats, WeeklyStats, MonthlyStats, UserBehaviorEvent,
    EngagementMetrics, UserSession, UserSatisfactionRating,
    RealTimeMetrics, LiveActivityFeed, PremiumAnalyticsReport,
    PremiumInsight
)
from timer.models import TimerSession, BreakRecord, UserTimerSettings
from accounts.models import UserStreakData

User = get_user_model()
logger = logging.getLogger(__name__)


class AnalyticsService:
    """Main analytics service for data aggregation and calculations"""

    @staticmethod
    def calculate_period_summary(user: User, start_date: date, end_date: date) -> Dict[str, Any]:
        """Calculate comprehensive summary for a date period"""
        daily_stats = DailyStats.objects.filter(
            user=user,
            date__gte=start_date,
            date__lte=end_date
        )

        if not daily_stats.exists():
            return AnalyticsService._get_empty_summary()

        # Use database aggregation for better performance
        aggregated_stats = daily_stats.aggregate(
            total_sessions=Sum('total_sessions'),
            total_work_minutes=Sum('total_work_minutes'),
            total_breaks=Sum('total_breaks_taken'),
            total_breaks_compliant=Sum('breaks_compliant'),
            avg_productivity=Avg('productivity_score')
        )

        total_breaks = aggregated_stats['total_breaks'] or 0
        compliant_breaks = aggregated_stats['total_breaks_compliant'] or 0

        avg_compliance = (
            (compliant_breaks / total_breaks) * 100
            if total_breaks > 0 else 0.0
        )

        active_days = daily_stats.filter(total_sessions__gt=0).count()

        return {
            'total_sessions': aggregated_stats['total_sessions'] or 0,
            'total_work_hours': round((aggregated_stats['total_work_minutes'] or 0) / 60.0, 1),
            'total_breaks': total_breaks,
            'avg_compliance': round(avg_compliance, 1),
            'productivity_score': round(aggregated_stats['avg_productivity'] or 0, 1),
            'active_days': active_days,
            'period_days': (end_date - start_date).days + 1
        }

    @staticmethod
    def _get_empty_summary() -> Dict[str, Any]:
        """Return empty summary structure"""
        return {
            'total_sessions': 0,
            'total_work_hours': 0.0,
            'total_breaks': 0,
            'avg_compliance': 0.0,
            'productivity_score': 0.0,
            'active_days': 0,
            'period_days': 0
        }

    @staticmethod
    def get_productivity_trend(user: User, weeks: int = 4) -> List[Dict[str, Any]]:
        """Get productivity trend for last N weeks"""
        trends = []
        today = date.today()

        for i in range(weeks):
            week_start = today - timedelta(weeks=i+1, days=today.weekday())
            week_end = week_start + timedelta(days=6)

            week_summary = AnalyticsService.calculate_period_summary(user, week_start, week_end)
            trends.append({
                'week_start': week_start.strftime('%Y-%m-%d'),
                'week_end': week_end.strftime('%Y-%m-%d'),
                'productivity_score': week_summary['productivity_score'],
                'compliance_rate': week_summary['avg_compliance'],
                'total_sessions': week_summary['total_sessions'],
                'work_hours': week_summary['total_work_hours']
            })

        return list(reversed(trends))  # Chronological order

    @staticmethod
    def analyze_hourly_patterns(user: User, start_date: date, end_date: date) -> List[Dict[str, Any]]:
        """Analyze productivity patterns by hour of day using database aggregation"""
        hourly_stats = TimerSession.objects.filter(
            user=user,
            start_time__date__gte=start_date,
            start_time__date__lte=end_date,
            is_active=False
        ).annotate(
            hour=Extract('start_time', 'hour')
        ).values('hour').annotate(
            sessions=Count('id'),
            work_minutes=Sum('total_work_minutes'),
            breaks_taken=Sum('total_breaks_taken')
        ).order_by('hour')

        # Convert to dictionary for easier lookup
        hourly_data = {stat['hour']: stat for stat in hourly_stats}

        # Fill in missing hours with 0
        result = []
        for hour in range(24):
            if hour in hourly_data:
                data = hourly_data[hour]
                result.append({
                    'hour': hour,
                    'hour_display': f"{hour:02d}:00",
                    'sessions': data['sessions'] or 0,
                    'work_minutes': data['work_minutes'] or 0,
                    'breaks_taken': data['breaks_taken'] or 0,
                    'productivity_score': AnalyticsService._calculate_hour_productivity(data)
                })
            else:
                result.append({
                    'hour': hour,
                    'hour_display': f"{hour:02d}:00",
                    'sessions': 0,
                    'work_minutes': 0,
                    'breaks_taken': 0,
                    'productivity_score': 0
                })

        return result

    @staticmethod
    def _calculate_hour_productivity(hour_data: Dict[str, Any]) -> float:
        """Calculate productivity score for an hour"""
        sessions = hour_data['sessions'] or 0
        work_minutes = hour_data['work_minutes'] or 0
        breaks_taken = hour_data['breaks_taken'] or 0

        if sessions == 0:
            return 0.0

        # Simple productivity score based on work time and break compliance
        base_score = min(100, (work_minutes / sessions) * 2)  # Up to 100 for 50+ min per session
        break_bonus = min(20, breaks_taken * 5)  # Bonus for taking breaks

        return round(base_score + break_bonus, 1)

    @staticmethod
    def analyze_daily_patterns(user: User, start_date: date, end_date: date) -> List[Dict[str, Any]]:
        """Analyze productivity patterns by day of week using database aggregation"""
        daily_stats = TimerSession.objects.filter(
            user=user,
            start_time__date__gte=start_date,
            start_time__date__lte=end_date,
            is_active=False
        ).annotate(
            weekday=Extract('start_time', 'week_day')
        ).values('weekday').annotate(
            sessions=Count('id'),
            work_minutes=Sum('total_work_minutes'),
            breaks_taken=Sum('total_breaks_taken')
        ).order_by('weekday')

        # Map weekday numbers to names
        weekday_names = {
            1: 'Sunday', 2: 'Monday', 3: 'Tuesday', 4: 'Wednesday',
            5: 'Thursday', 6: 'Friday', 7: 'Saturday'
        }

        return [
            {
                'day': weekday_names[stat['weekday']],
                'weekday': stat['weekday'],
                'sessions': stat['sessions'] or 0,
                'work_minutes': stat['work_minutes'] or 0,
                'breaks_taken': stat['breaks_taken'] or 0,
                'avg_session_length': (
                    (stat['work_minutes'] or 0) / (stat['sessions'] or 1)
                )
            }
            for stat in daily_stats
        ]


class BreakAnalyticsService:
    """Service for break pattern analysis and insights"""

    @staticmethod
    def analyze_break_patterns(user: User, start_date: date, end_date: date) -> Dict[str, Any]:
        """Comprehensive break pattern analysis using database aggregation"""
        break_stats = BreakRecord.objects.filter(
            user=user,
            break_start_time__date__gte=start_date,
            break_start_time__date__lte=end_date,
            break_completed=True
        ).aggregate(
            total_breaks=Count('id'),
            average_duration=Avg('break_duration_seconds'),
            min_duration=Min('break_duration_seconds'),
            max_duration=Max('break_duration_seconds'),
            compliant_breaks=Count(
                'id',
                filter=Q(break_duration_seconds__gte=20, looked_at_distance=True)
            ),
            distance_looks=Count('id', filter=Q(looked_at_distance=True))
        )

        total_breaks = break_stats['total_breaks'] or 0
        compliant_breaks = break_stats['compliant_breaks'] or 0
        distance_looks = break_stats['distance_looks'] or 0

        patterns = {
            'total_breaks': total_breaks,
            'average_duration': round(break_stats['average_duration'] or 0, 1),
            'min_duration': break_stats['min_duration'] or 0,
            'max_duration': break_stats['max_duration'] or 0,
            'compliance_rate': (compliant_breaks / total_breaks * 100) if total_breaks > 0 else 0,
            'distance_look_rate': (distance_looks / total_breaks * 100) if total_breaks > 0 else 0,
            'most_common_hour': None,
            'hourly_distribution': []
        }

        # Find hourly distribution and most common hour
        if total_breaks > 0:
            hourly_breaks = BreakAnalyticsService._get_hourly_break_distribution(
                user, start_date, end_date
            )
            patterns['hourly_distribution'] = hourly_breaks

            if hourly_breaks:
                most_common = max(hourly_breaks, key=lambda x: x['break_count'])
                patterns['most_common_hour'] = most_common['hour']

        return patterns

    @staticmethod
    def _get_hourly_break_distribution(user: User, start_date: date, end_date: date) -> List[Dict[str, Any]]:
        """Get break distribution by hour"""
        hourly_stats = BreakRecord.objects.filter(
            user=user,
            break_start_time__date__gte=start_date,
            break_start_time__date__lte=end_date,
            break_completed=True
        ).annotate(
            hour=Extract('break_start_time', 'hour')
        ).values('hour').annotate(
            break_count=Count('id'),
            avg_duration=Avg('break_duration_seconds'),
            compliance_rate=Count(
                'id',
                filter=Q(break_duration_seconds__gte=20, looked_at_distance=True)
            ) * 100.0 / Count('id')
        ).order_by('hour')

        return [
            {
                'hour': stat['hour'],
                'hour_display': f"{stat['hour']:02d}:00",
                'break_count': stat['break_count'],
                'avg_duration': round(stat['avg_duration'], 1),
                'compliance_rate': round(stat['compliance_rate'], 1)
            }
            for stat in hourly_stats
        ]

    @staticmethod
    def calculate_break_effectiveness(user: User, days: int = 30) -> Dict[str, Any]:
        """Calculate break effectiveness metrics"""
        end_date = date.today()
        start_date = end_date - timedelta(days=days)

        # Get break data
        breaks = BreakRecord.objects.filter(
            user=user,
            break_start_time__date__gte=start_date,
            break_start_time__date__lte=end_date,
            break_completed=True
        )

        # Get session data for context
        sessions = TimerSession.objects.filter(
            user=user,
            start_time__date__gte=start_date,
            start_time__date__lte=end_date,
            is_active=False
        )

        total_work_hours = sessions.aggregate(
            total_minutes=Sum('total_work_minutes')
        )['total_minutes'] or 0
        total_work_hours = total_work_hours / 60.0

        break_stats = breaks.aggregate(
            total_breaks=Count('id'),
            compliant_breaks=Count(
                'id',
                filter=Q(break_duration_seconds__gte=20, looked_at_distance=True)
            ),
            avg_duration=Avg('break_duration_seconds')
        )

        total_breaks = break_stats['total_breaks'] or 0
        compliant_breaks = break_stats['compliant_breaks'] or 0

        # Calculate effectiveness metrics
        if total_breaks > 0 and total_work_hours > 0:
            compliance_rate = (compliant_breaks / total_breaks) * 100
            breaks_per_hour = total_breaks / total_work_hours
            recommended_breaks_per_hour = 3  # Every 20 minutes

            # Effectiveness score based on compliance and frequency
            frequency_score = min(100, (breaks_per_hour / recommended_breaks_per_hour) * 100)
            effectiveness_score = (compliance_rate * 0.7 + frequency_score * 0.3)

            return {
                'compliance_rate': round(compliance_rate, 1),
                'breaks_per_hour': round(breaks_per_hour, 1),
                'recommended_breaks_per_hour': recommended_breaks_per_hour,
                'frequency_score': round(frequency_score, 1),
                'effectiveness_score': round(effectiveness_score, 1),
                'avg_duration': round(break_stats['avg_duration'] or 0, 1),
                'total_breaks': total_breaks,
                'compliant_breaks': compliant_breaks,
                'period_work_hours': round(total_work_hours, 1)
            }
        else:
            return {
                'compliance_rate': 0,
                'breaks_per_hour': 0,
                'recommended_breaks_per_hour': 3,
                'frequency_score': 0,
                'effectiveness_score': 0,
                'avg_duration': 0,
                'total_breaks': 0,
                'compliant_breaks': 0,
                'period_work_hours': 0
            }


class HealthImpactService:
    """Service for calculating health impact metrics"""

    @staticmethod
    def calculate_health_metrics(user: User, start_date: date, end_date: date) -> Dict[str, Any]:
        """Calculate comprehensive health impact metrics"""
        break_effectiveness = BreakAnalyticsService.calculate_break_effectiveness(
            user, (end_date - start_date).days
        )

        # Eye strain reduction calculation
        eye_strain_reduction = HealthImpactService._calculate_eye_strain_reduction(
            break_effectiveness
        )

        # Productivity impact calculation
        productivity_impact = HealthImpactService._calculate_productivity_impact(
            break_effectiveness
        )

        # Overall health score
        health_score = HealthImpactService._calculate_health_score(break_effectiveness)

        return {
            'compliance_rate': break_effectiveness['compliance_rate'],
            'breaks_per_hour': break_effectiveness['breaks_per_hour'],
            'eye_strain_reduction': eye_strain_reduction,
            'productivity_boost': productivity_impact,
            'health_score': health_score,
            'total_breaks': break_effectiveness['total_breaks'],
            'compliant_breaks': break_effectiveness['compliant_breaks'],
            'effectiveness_score': break_effectiveness['effectiveness_score']
        }

    @staticmethod
    def _calculate_eye_strain_reduction(break_effectiveness: Dict[str, Any]) -> float:
        """Calculate estimated eye strain reduction percentage"""
        compliance_rate = break_effectiveness['compliance_rate']
        breaks_per_hour = break_effectiveness['breaks_per_hour']

        # Research-based formula for eye strain reduction
        base_reduction = compliance_rate * 0.6  # Compliance is most important
        frequency_bonus = min(30, breaks_per_hour * 10)  # Frequency bonus up to 30%

        total_reduction = min(80, base_reduction + frequency_bonus)  # Cap at 80%
        return round(total_reduction, 1)

    @staticmethod
    def _calculate_productivity_impact(break_effectiveness: Dict[str, Any]) -> float:
        """Calculate estimated productivity boost percentage"""
        effectiveness_score = break_effectiveness['effectiveness_score']

        # Conservative estimate based on break effectiveness
        productivity_boost = effectiveness_score * 0.15  # Up to 15% boost
        return round(min(15, productivity_boost), 1)

    @staticmethod
    def _calculate_health_score(break_effectiveness: Dict[str, Any]) -> float:
        """Calculate overall health score (0-100)"""
        compliance_rate = break_effectiveness['compliance_rate']
        frequency_score = break_effectiveness['frequency_score']

        # Weighted combination of compliance and frequency
        health_score = compliance_rate * 0.6 + frequency_score * 0.4
        return round(health_score, 1)

    @staticmethod
    def get_health_trends(user: User, periods: List[str]) -> Dict[str, Dict[str, Any]]:
        """Get health metrics for multiple time periods"""
        period_days = {
            'week': 7,
            'month': 30,
            'quarter': 90,
            'year': 365
        }

        health_trends = {}
        end_date = date.today()

        for period_name in periods:
            if period_name in period_days:
                days = period_days[period_name]
                start_date = end_date - timedelta(days=days)
                health_trends[period_name] = HealthImpactService.calculate_health_metrics(
                    user, start_date, end_date
                )

        return health_trends


class RealTimeMetricsService:
    """Service for real-time metrics calculation and updates"""

    @staticmethod
    def update_real_time_metrics() -> RealTimeMetrics:
        """Update system-wide real-time metrics"""
        latest_metrics = RealTimeMetrics.get_latest_metrics()
        latest_metrics.update_metrics()
        return latest_metrics

    @staticmethod
    def get_current_active_users() -> int:
        """Get count of currently active users"""
        return UserSession.get_active_users_count()

    @staticmethod
    def get_today_break_count() -> int:
        """Get total breaks taken today"""
        return UserSession.get_real_time_breaks_count()

    @staticmethod
    def get_live_activity_feed(limit: int = 10) -> QuerySet[LiveActivityFeed]:
        """Get recent live activities"""
        return LiveActivityFeed.get_recent_public_activities(limit)

    @staticmethod
    def track_user_activity(user: User, activity_type: str, activity_data: Dict[str, Any]) -> None:
        """Track user activity for real-time feed"""
        try:
            LiveActivityFeed.objects.create(
                user=user,
                activity_type=activity_type,
                activity_data=activity_data
            )
        except Exception as e:
            logger.warning(f"Failed to track user activity: {e}")


class SatisfactionAnalyticsService:
    """Service for user satisfaction analysis"""

    @staticmethod
    def get_satisfaction_trend(user: User, days: int = 30) -> List[Dict[str, Any]]:
        """Get user satisfaction trend over time"""
        end_date = timezone.now()
        start_date = end_date - timedelta(days=days)

        ratings = UserSatisfactionRating.objects.filter(
            user=user,
            rating_date__gte=start_date,
            rating_date__lte=end_date
        ).order_by('rating_date')

        trend_data = []
        for rating in ratings:
            trend_data.append({
                'date': rating.rating_date.strftime('%Y-%m-%d'),
                'rating': rating.rating,
                'context': rating.get_context_display(),
                'recommendation_score': rating.recommendation_score,
                'ease_of_use': rating.ease_of_use_rating,
                'effectiveness': rating.effectiveness_rating,
                'helpfulness': rating.reminder_helpfulness
            })

        return trend_data

    @staticmethod
    def calculate_satisfaction_metrics(user: User, days: int = 30) -> Dict[str, Any]:
        """Calculate satisfaction metrics for user"""
        end_date = timezone.now()
        start_date = end_date - timedelta(days=days)

        ratings = UserSatisfactionRating.objects.filter(
            user=user,
            rating_date__gte=start_date,
            rating_date__lte=end_date
        )

        if not ratings.exists():
            return {
                'average_rating': 0,
                'total_ratings': 0,
                'nps_score': 0,
                'would_recommend_percentage': 0
            }

        stats = ratings.aggregate(
            avg_rating=Avg('rating'),
            avg_ease_of_use=Avg('ease_of_use_rating'),
            avg_effectiveness=Avg('effectiveness_rating'),
            avg_helpfulness=Avg('reminder_helpfulness'),
            total_count=Count('id'),
            recommend_count=Count('id', filter=Q(would_recommend=True))
        )

        # Calculate NPS score
        nps_ratings = ratings.filter(recommendation_score__isnull=False)
        if nps_ratings.exists():
            total_nps = nps_ratings.count()
            promoters = nps_ratings.filter(recommendation_score__gte=9).count()
            detractors = nps_ratings.filter(recommendation_score__lte=6).count()
            nps_score = ((promoters - detractors) / total_nps) * 100
        else:
            nps_score = 0

        return {
            'average_rating': round(stats['avg_rating'], 1),
            'ease_of_use': round(stats['avg_ease_of_use'] or 0, 1),
            'effectiveness': round(stats['avg_effectiveness'] or 0, 1),
            'helpfulness': round(stats['avg_helpfulness'] or 0, 1),
            'total_ratings': stats['total_count'],
            'nps_score': round(nps_score, 1),
            'would_recommend_percentage': round(
                (stats['recommend_count'] / stats['total_count']) * 100, 1
            ) if stats['total_count'] > 0 else 0
        }


class PremiumReportService:
    """Service for premium analytics report generation"""

    @staticmethod
    def generate_premium_report(user: User, report_type: str,
                              start_date: date, end_date: date) -> PremiumAnalyticsReport:
        """Generate a comprehensive premium analytics report"""
        # Check if report already exists
        existing_report = PremiumAnalyticsReport.objects.filter(
            user=user,
            report_type=report_type,
            report_period_start=start_date,
            report_period_end=end_date
        ).first()

        if existing_report and existing_report.is_generated:
            return existing_report

        # Create new report
        report = PremiumAnalyticsReport.objects.create(
            user=user,
            report_type=report_type,
            report_period_start=start_date,
            report_period_end=end_date
        )

        # Generate the report
        report.generate_report()
        return report

    @staticmethod
    def create_insights(user: User) -> List[PremiumInsight]:
        """Create AI-generated insights for premium user"""
        insights = []

        # Get user data for analysis
        user_stats = PremiumReportService._get_user_insights_data(user)

        # Generate insights based on patterns
        pattern_insights = PremiumReportService._generate_pattern_insights(user, user_stats)
        health_insights = PremiumReportService._generate_health_insights(user, user_stats)
        productivity_insights = PremiumReportService._generate_productivity_insights(user, user_stats)

        insights.extend(pattern_insights)
        insights.extend(health_insights)
        insights.extend(productivity_insights)

        return insights

    @staticmethod
    def _get_user_insights_data(user: User) -> Dict[str, Any]:
        """Get user data for insights generation"""
        end_date = date.today()
        start_date = end_date - timedelta(days=30)

        return {
            'period_summary': AnalyticsService.calculate_period_summary(user, start_date, end_date),
            'break_patterns': BreakAnalyticsService.analyze_break_patterns(user, start_date, end_date),
            'health_metrics': HealthImpactService.calculate_health_metrics(user, start_date, end_date),
            'hourly_patterns': AnalyticsService.analyze_hourly_patterns(user, start_date, end_date),
            'satisfaction': SatisfactionAnalyticsService.calculate_satisfaction_metrics(user)
        }

    @staticmethod
    def _generate_pattern_insights(user: User, user_stats: Dict[str, Any]) -> List[PremiumInsight]:
        """Generate insights about user patterns"""
        insights = []

        # Analyze peak productivity hours
        hourly_patterns = user_stats['hourly_patterns']
        if hourly_patterns:
            most_productive = max(hourly_patterns, key=lambda x: x['productivity_score'])
            if most_productive['productivity_score'] > 50:
                insight = PremiumInsight.objects.create(
                    user=user,
                    insight_type='pattern',
                    title='Peak Productivity Hours Identified',
                    description=f"You're most productive around {most_productive['hour_display']} "
                               f"with a productivity score of {most_productive['productivity_score']}.",
                    action_suggestion='Schedule your most important tasks during this time period.',
                    supporting_data={'peak_hour': most_productive['hour'], 'score': most_productive['productivity_score']},
                    confidence_score=0.8,
                    priority='medium'
                )
                insights.append(insight)

        return insights

    @staticmethod
    def _generate_health_insights(user: User, user_stats: Dict[str, Any]) -> List[PremiumInsight]:
        """Generate health-related insights"""
        insights = []

        health_metrics = user_stats['health_metrics']
        compliance_rate = health_metrics['compliance_rate']

        if compliance_rate < 60:
            insight = PremiumInsight.objects.create(
                user=user,
                insight_type='health',
                title='Low Break Compliance Detected',
                description=f"Your break compliance rate is {compliance_rate}%, "
                           "which may increase eye strain risk.",
                action_suggestion='Try setting shorter break durations to build the habit gradually.',
                supporting_data={'compliance_rate': compliance_rate},
                confidence_score=0.9,
                priority='high'
            )
            insights.append(insight)
        elif compliance_rate > 85:
            insight = PremiumInsight.objects.create(
                user=user,
                insight_type='health',
                title='Excellent Break Compliance!',
                description=f"Your break compliance rate of {compliance_rate}% is outstanding! "
                           f"This could reduce eye strain by up to {health_metrics['eye_strain_reduction']}%.",
                action_suggestion='Keep up the great work and consider sharing your success with others.',
                supporting_data={'compliance_rate': compliance_rate, 'eye_strain_reduction': health_metrics['eye_strain_reduction']},
                confidence_score=0.95,
                priority='low'
            )
            insights.append(insight)

        return insights

    @staticmethod
    def _generate_productivity_insights(user: User, user_stats: Dict[str, Any]) -> List[PremiumInsight]:
        """Generate productivity-related insights"""
        insights = []

        period_summary = user_stats['period_summary']
        productivity_score = period_summary['productivity_score']

        if productivity_score > 0:
            if productivity_score < 40:
                insight = PremiumInsight.objects.create(
                    user=user,
                    insight_type='productivity',
                    title='Productivity Improvement Opportunity',
                    description=f"Your productivity score of {productivity_score} suggests room for improvement.",
                    action_suggestion='Focus on consistent daily usage and regular break-taking to boost your score.',
                    supporting_data={'productivity_score': productivity_score},
                    confidence_score=0.75,
                    priority='medium'
                )
                insights.append(insight)

        return insights


class ChartDataService:
    """Service for preparing chart data for frontend visualization"""

    @staticmethod
    def prepare_dashboard_charts(user: User, days: int = 30) -> Dict[str, Any]:
        """Prepare comprehensive chart data for dashboard - Optimized"""
        end_date = date.today()
        start_date = end_date - timedelta(days=days)

        # Get daily statistics with prefetch optimization
        daily_stats = DailyStats.objects.filter(
            user=user,
            date__gte=start_date,
            date__lte=end_date
        ).order_by('date')

        # Basic time series data
        chart_data = {
            'dates': [stat.date.strftime('%Y-%m-%d') for stat in daily_stats],
            'work_minutes': [stat.total_work_minutes for stat in daily_stats],
            'breaks_taken': [stat.total_breaks_taken for stat in daily_stats],
            'compliance_rates': [stat.compliance_rate for stat in daily_stats],
            'productivity_scores': [stat.productivity_score for stat in daily_stats]
        }

        # Use batch processing for pattern analysis to reduce database load
        patterns_data = ChartDataService._get_patterns_batch(user, start_date, end_date)
        chart_data.update(patterns_data)

        return chart_data

    @staticmethod
    def _get_patterns_batch(user: User, start_date: date, end_date: date) -> Dict[str, Any]:
        """Get all pattern analysis data in optimized batch queries"""
        # Single query for hourly patterns with all needed data
        hourly_patterns = AnalyticsService.analyze_hourly_patterns(user, start_date, end_date)

        # Single query for daily patterns with all needed data
        daily_patterns = AnalyticsService.analyze_daily_patterns(user, start_date, end_date)

        # Single query for break patterns with all needed data
        break_patterns = BreakAnalyticsService.analyze_break_patterns(user, start_date, end_date)

        # Optimized productivity trend (reduces weeks analyzed)
        productivity_trend = AnalyticsService.get_productivity_trend(user, 4)

        return {
            'hourly_productivity': hourly_patterns,
            'daily_patterns': daily_patterns,
            'break_patterns': break_patterns,
            'productivity_trend': productivity_trend
        }

    @staticmethod
    def prepare_comparison_data(user: User, current_period_days: int = 30) -> Dict[str, Any]:
        """Prepare comparison data for current vs previous period"""
        end_date = date.today()
        current_start = end_date - timedelta(days=current_period_days)
        previous_start = current_start - timedelta(days=current_period_days)
        previous_end = current_start - timedelta(days=1)

        current_summary = AnalyticsService.calculate_period_summary(
            user, current_start, end_date
        )
        previous_summary = AnalyticsService.calculate_period_summary(
            user, previous_start, previous_end
        )

        # Calculate percentage changes
        comparisons = {}
        for key in ['total_sessions', 'total_work_hours', 'total_breaks', 'avg_compliance', 'productivity_score']:
            current_value = current_summary.get(key, 0)
            previous_value = previous_summary.get(key, 0)

            if previous_value > 0:
                change_percent = ((current_value - previous_value) / previous_value) * 100
            else:
                change_percent = 100 if current_value > 0 else 0

            comparisons[key] = {
                'current': current_value,
                'previous': previous_value,
                'change_percent': round(change_percent, 1),
                'improved': change_percent > 0
            }

        return {
            'current_period': current_summary,
            'previous_period': previous_summary,
            'comparisons': comparisons,
            'period_days': current_period_days
        }