"""
Premium analytics dashboard views
"""
from django.shortcuts import render, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.http import JsonResponse
from django.views.decorators.http import require_POST
from django.db.models import Count, Avg, Sum, Q
from django.utils import timezone
from datetime import datetime, timedelta, date
import json

from accounts.premium_features import can_access_feature
from .models import (
    DailyStats, WeeklyStats, MonthlyStats, PremiumAnalyticsReport,
    PremiumInsight, UserSatisfactionRating, RealTimeMetrics
)
from timer.models import TimerSession, BreakRecord


@login_required
def premium_dashboard_view(request):
    """
    Main premium analytics dashboard
    """
    # Check premium access
    if not can_access_feature(request.user, 'premium_analytics'):
        from django.contrib import messages
        messages.error(request, 'This feature requires a Premium subscription.')
        return redirect('accounts:pricing')

    # Get latest insights - Optimized query
    active_insights = PremiumInsight.objects.select_related().filter(
        user=request.user,
        is_active=True,
        expires_at__gt=timezone.now()
    ).order_by('-priority', '-generated_at')[:5]

    # Get recent reports - Optimized query
    recent_reports = PremiumAnalyticsReport.objects.select_related().filter(
        user=request.user,
        is_generated=True
    ).order_by('-generated_at')[:3]

    # Get current week summary
    week_start = date.today() - timedelta(days=date.today().weekday())
    week_end = week_start + timedelta(days=6)

    week_summary = _get_period_summary(request.user, week_start, week_end)

    # Get productivity trend (last 4 weeks)
    productivity_trend = _get_productivity_trend(request.user, weeks=4)

    # Real-time metrics
    real_time_metrics = RealTimeMetrics.get_latest_metrics()

    context = {
        'active_insights': active_insights,
        'recent_reports': recent_reports,
        'week_summary': week_summary,
        'productivity_trend': productivity_trend,
        'real_time_metrics': real_time_metrics,
        'can_generate_report': True,
    }

    return render(request, 'analytics/premium_dashboard.html', context)


@login_required
def detailed_analytics_view(request):
    """
    Detailed analytics page with charts and deep insights
    """
    if not can_access_feature(request.user, 'premium_analytics'):
        from django.contrib import messages
        messages.error(request, 'This feature requires a Premium subscription.')
        return redirect('accounts:pricing')

    # Get date range from query parameters
    days = int(request.GET.get('days', 30))
    end_date = date.today()
    start_date = end_date - timedelta(days=days)

    # Get comprehensive analytics data
    daily_stats = DailyStats.objects.filter(
        user=request.user,
        date__gte=start_date,
        date__lte=end_date
    ).order_by('date')

    # Calculate summary metrics
    total_sessions = sum(stat.total_sessions for stat in daily_stats)
    total_work_hours = sum(stat.total_work_minutes for stat in daily_stats) / 60.0
    total_breaks = sum(stat.total_breaks_taken for stat in daily_stats)
    avg_compliance = sum(stat.compliance_rate for stat in daily_stats) / max(1, len(daily_stats))

    # Productivity patterns analysis
    hourly_productivity = _analyze_hourly_patterns(request.user, start_date, end_date)
    daily_productivity = _analyze_daily_patterns(request.user, start_date, end_date)

    # Break patterns
    break_patterns = _analyze_break_patterns(request.user, start_date, end_date)

    # Chart data preparation
    chart_data = {
        'dates': [stat.date.strftime('%Y-%m-%d') for stat in daily_stats],
        'work_minutes': [stat.total_work_minutes for stat in daily_stats],
        'breaks_taken': [stat.total_breaks_taken for stat in daily_stats],
        'compliance_rates': [stat.compliance_rate for stat in daily_stats],
        'productivity_scores': [stat.productivity_score for stat in daily_stats],
        'hourly_productivity': hourly_productivity,
        'daily_productivity': daily_productivity,
        'break_patterns': break_patterns,
    }

    context = {
        'days': days,
        'date_range': f"{start_date} to {end_date}",
        'summary': {
            'total_sessions': total_sessions,
            'total_work_hours': round(total_work_hours, 1),
            'total_breaks': total_breaks,
            'avg_compliance': round(avg_compliance, 1),
        },
        'chart_data': chart_data,
        'daily_stats': daily_stats,
    }

    return render(request, 'analytics/detailed_analytics.html', context)


@login_required
def health_impact_view(request):
    """
    Health impact analytics page
    """
    if not can_access_feature(request.user, 'premium_analytics'):
        from django.contrib import messages
        messages.error(request, 'This feature requires a Premium subscription.')
        return redirect('accounts:pricing')

    # Calculate health metrics for different periods
    periods = {
        'week': 7,
        'month': 30,
        'quarter': 90,
        'year': 365
    }

    health_metrics = {}
    for period_name, days in periods.items():
        end_date = date.today()
        start_date = end_date - timedelta(days=days)

        metrics = _calculate_health_metrics(request.user, start_date, end_date)
        health_metrics[period_name] = metrics

    # Get satisfaction ratings trend
    satisfaction_trend = _get_satisfaction_trend(request.user)

    # Eye strain reduction estimates
    eye_strain_data = _calculate_eye_strain_reduction(request.user)

    context = {
        'health_metrics': health_metrics,
        'satisfaction_trend': satisfaction_trend,
        'eye_strain_data': eye_strain_data,
    }

    return render(request, 'analytics/health_impact.html', context)


@login_required
@require_POST
def generate_report_view(request):
    """
    Generate a premium analytics report
    """
    if not can_access_feature(request.user, 'premium_analytics'):
        return JsonResponse({'success': False, 'message': 'Premium subscription required'})

    try:
        data = json.loads(request.body)
        report_type = data.get('report_type', 'weekly')

        # Calculate date range based on report type
        end_date = date.today()
        if report_type == 'weekly':
            start_date = end_date - timedelta(days=7)
        elif report_type == 'monthly':
            start_date = end_date - timedelta(days=30)
        elif report_type == 'quarterly':
            start_date = end_date - timedelta(days=90)
        elif report_type == 'yearly':
            start_date = end_date - timedelta(days=365)
        else:
            return JsonResponse({'success': False, 'message': 'Invalid report type'})

        # Check if report already exists
        existing_report = PremiumAnalyticsReport.objects.filter(
            user=request.user,
            report_type=report_type,
            report_period_start=start_date
        ).first()

        if existing_report and existing_report.is_generated:
            return JsonResponse({
                'success': True,
                'message': 'Report already exists',
                'report_id': existing_report.id,
                'report_url': f'/analytics/reports/{existing_report.id}/'
            })

        # Create new report
        report = PremiumAnalyticsReport.objects.create(
            user=request.user,
            report_type=report_type,
            report_period_start=start_date,
            report_period_end=end_date
        )

        # Generate the report asynchronously (in production, use Celery)
        report.generate_report()

        return JsonResponse({
            'success': True,
            'message': 'Report generated successfully!',
            'report_id': report.id,
            'report_url': f'/analytics/reports/{report.id}/',
            'generation_time': report.generation_time_seconds
        })

    except json.JSONDecodeError:
        return JsonResponse({'success': False, 'message': 'Invalid request data'})
    except Exception as e:
        return JsonResponse({'success': False, 'message': 'Report generation failed'})


@login_required
def view_report_view(request, report_id):
    """
    View a specific premium analytics report
    """
    if not can_access_feature(request.user, 'premium_analytics'):
        from django.contrib import messages
        messages.error(request, 'This feature requires a Premium subscription.')
        return redirect('accounts:pricing')

    report = get_object_or_404(PremiumAnalyticsReport, id=report_id, user=request.user)

    if not report.is_generated:
        # Report is being generated
        context = {'report': report, 'is_generating': True}
        return render(request, 'analytics/report_generating.html', context)

    context = {
        'report': report,
        'is_generating': False,
    }

    return render(request, 'analytics/premium_report.html', context)


@login_required
def insights_api_view(request):
    """
    API endpoint to get user's active insights
    """
    if not can_access_feature(request.user, 'premium_analytics'):
        return JsonResponse({'success': False, 'message': 'Premium subscription required'})

    insights = PremiumInsight.objects.filter(
        user=request.user,
        is_active=True
    ).order_by('-priority', '-generated_at')

    insights_data = []
    for insight in insights:
        insights_data.append({
            'id': insight.id,
            'type': insight.insight_type,
            'title': insight.title,
            'description': insight.description,
            'action_suggestion': insight.action_suggestion,
            'priority': insight.priority,
            'confidence_score': insight.confidence_score,
            'generated_at': insight.generated_at.isoformat(),
            'viewed': bool(insight.viewed_at)
        })

    return JsonResponse({
        'success': True,
        'insights': insights_data,
        'count': len(insights_data)
    })


@login_required
@require_POST
def mark_insight_viewed_view(request, insight_id):
    """
    Mark an insight as viewed
    """
    insight = get_object_or_404(PremiumInsight, id=insight_id, user=request.user)
    insight.mark_as_viewed()

    return JsonResponse({'success': True})


@login_required
@require_POST
def dismiss_insight_view(request, insight_id):
    """
    Dismiss an insight
    """
    insight = get_object_or_404(PremiumInsight, id=insight_id, user=request.user)
    insight.dismiss()

    return JsonResponse({'success': True, 'message': 'Insight dismissed'})


def _get_period_summary(user, start_date, end_date):
    """Get summary statistics for a date period"""
    daily_stats = DailyStats.objects.filter(
        user=user,
        date__gte=start_date,
        date__lte=end_date
    )

    if not daily_stats.exists():
        return {
            'total_sessions': 0,
            'total_work_hours': 0.0,
            'total_breaks': 0,
            'avg_compliance': 0.0,
            'productivity_score': 0.0,
            'active_days': 0
        }

    total_sessions = sum(stat.total_sessions for stat in daily_stats)
    total_work_minutes = sum(stat.total_work_minutes for stat in daily_stats)
    total_breaks = sum(stat.total_breaks_taken for stat in daily_stats)
    avg_compliance = sum(stat.compliance_rate for stat in daily_stats) / len(daily_stats)
    avg_productivity = sum(stat.productivity_score for stat in daily_stats) / len(daily_stats)
    active_days = daily_stats.filter(total_sessions__gt=0).count()

    return {
        'total_sessions': total_sessions,
        'total_work_hours': round(total_work_minutes / 60.0, 1),
        'total_breaks': total_breaks,
        'avg_compliance': round(avg_compliance, 1),
        'productivity_score': round(avg_productivity, 1),
        'active_days': active_days
    }


def _get_productivity_trend(user, weeks=4):
    """Get productivity trend for last N weeks"""
    trends = []
    for i in range(weeks):
        week_start = date.today() - timedelta(weeks=i+1, days=date.today().weekday())
        week_end = week_start + timedelta(days=6)

        week_summary = _get_period_summary(user, week_start, week_end)
        trends.append({
            'week_start': week_start.strftime('%Y-%m-%d'),
            'productivity_score': week_summary['productivity_score'],
            'compliance_rate': week_summary['avg_compliance'],
            'total_sessions': week_summary['total_sessions']
        })

    return list(reversed(trends))  # Chronological order


def _analyze_hourly_patterns(user, start_date, end_date):
    """Analyze productivity patterns by hour of day - Optimized with database aggregation"""
    # Use database aggregation to avoid loading all session objects
    from django.db.models import IntegerField
    from django.db.models.functions import Extract

    hourly_stats = TimerSession.objects.filter(
        user=user,
        start_time__date__gte=start_date,
        start_time__date__lte=end_date,
        is_active=False
    ).annotate(
        hour=Extract('start_time', 'hour')
    ).values('hour').annotate(
        sessions=Count('id'),
        work_minutes=Sum('total_work_minutes')
    ).order_by('hour')

    # Convert to dictionary for easier lookup
    hourly_data = {stat['hour']: stat for stat in hourly_stats}

    # Fill in missing hours with 0
    result = []
    for hour in range(24):
        if hour in hourly_data:
            result.append({
                'hour': hour,
                'sessions': hourly_data[hour]['sessions'] or 0,
                'work_minutes': hourly_data[hour]['work_minutes'] or 0
            })
        else:
            result.append({'hour': hour, 'sessions': 0, 'work_minutes': 0})

    return result


def _analyze_daily_patterns(user, start_date, end_date):
    """Analyze productivity patterns by day of week - Optimized with database aggregation"""
    from django.db.models.functions import Extract

    # Use database aggregation to group by day of week
    daily_stats = TimerSession.objects.filter(
        user=user,
        start_time__date__gte=start_date,
        start_time__date__lte=end_date,
        is_active=False
    ).annotate(
        weekday=Extract('start_time', 'week_day')
    ).values('weekday').annotate(
        sessions=Count('id'),
        work_minutes=Sum('total_work_minutes')
    ).order_by('weekday')

    # Map weekday numbers to names
    weekday_names = {
        1: 'Sunday', 2: 'Monday', 3: 'Tuesday', 4: 'Wednesday',
        5: 'Thursday', 6: 'Friday', 7: 'Saturday'
    }

    return [
        {
            'day': weekday_names[stat['weekday']],
            'sessions': stat['sessions'] or 0,
            'work_minutes': stat['work_minutes'] or 0
        }
        for stat in daily_stats
    ]


def _analyze_break_patterns(user, start_date, end_date):
    """Analyze break taking patterns - Optimized with database aggregation"""
    from django.db.models.functions import Extract

    # Get all break statistics in a single query
    break_stats = BreakRecord.objects.filter(
        user=user,
        break_start_time__date__gte=start_date,
        break_start_time__date__lte=end_date,
        break_completed=True
    ).aggregate(
        total_breaks=Count('id'),
        average_duration=Avg('break_duration_seconds'),
        compliant_breaks=Count(
            'id',
            filter=Q(break_duration_seconds__gte=20, looked_at_distance=True)
        )
    )

    total_breaks = break_stats['total_breaks'] or 0
    compliant_breaks = break_stats['compliant_breaks'] or 0

    patterns = {
        'average_duration': break_stats['average_duration'] or 0,
        'compliance_rate': (compliant_breaks / total_breaks * 100) if total_breaks > 0 else 0,
        'most_common_hour': None,
        'total_breaks': total_breaks
    }

    # Find most common break hour using database aggregation
    if total_breaks > 0:
        hour_stats = BreakRecord.objects.filter(
            user=user,
            break_start_time__date__gte=start_date,
            break_start_time__date__lte=end_date,
            break_completed=True
        ).annotate(
            hour=Extract('break_start_time', 'hour')
        ).values('hour').annotate(
            count=Count('id')
        ).order_by('-count').first()

        if hour_stats:
            patterns['most_common_hour'] = hour_stats['hour']

    return patterns


def _calculate_health_metrics(user, start_date, end_date):
    """Calculate health impact metrics for a period"""
    breaks = BreakRecord.objects.filter(
        user=user,
        break_start_time__date__gte=start_date,
        break_start_time__date__lte=end_date,
        break_completed=True
    )

    sessions = TimerSession.objects.filter(
        user=user,
        start_time__date__gte=start_date,
        start_time__date__lte=end_date,
        is_active=False
    )

    total_work_hours = sum(session.total_work_minutes for session in sessions) / 60.0
    total_breaks = breaks.count()
    compliant_breaks = breaks.filter(
        break_duration_seconds__gte=20,
        looked_at_distance=True
    ).count()

    if total_breaks > 0:
        compliance_rate = (compliant_breaks / total_breaks) * 100
        breaks_per_hour = total_breaks / max(1, total_work_hours)

        # Estimated eye strain reduction based on compliance and frequency
        eye_strain_reduction = min(80, (compliance_rate / 100.0) * breaks_per_hour * 25)

        # Estimated productivity boost
        productivity_boost = min(15, compliance_rate * 0.15)

        # Overall health score
        health_score = (compliance_rate * 0.6 + min(100, breaks_per_hour * 33.33) * 0.4)
    else:
        compliance_rate = 0
        eye_strain_reduction = 0
        productivity_boost = 0
        health_score = 0
        breaks_per_hour = 0

    return {
        'compliance_rate': round(compliance_rate, 1),
        'breaks_per_hour': round(breaks_per_hour, 1),
        'eye_strain_reduction': round(eye_strain_reduction, 1),
        'productivity_boost': round(productivity_boost, 1),
        'health_score': round(health_score, 1),
        'total_breaks': total_breaks,
        'compliant_breaks': compliant_breaks
    }


def _get_satisfaction_trend(user, days=30):
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
            'recommendation_score': rating.recommendation_score
        })

    return trend_data


def _calculate_eye_strain_reduction(user):
    """Calculate detailed eye strain reduction estimates"""
    # This would implement more sophisticated eye strain calculations
    # based on user's break patterns, work hours, screen time, etc.

    periods = ['week', 'month', 'quarter', 'year']
    eye_strain_data = {}

    for period in periods:
        if period == 'week':
            days = 7
        elif period == 'month':
            days = 30
        elif period == 'quarter':
            days = 90
        else:  # year
            days = 365

        start_date = date.today() - timedelta(days=days)
        end_date = date.today()

        health_metrics = _calculate_health_metrics(user, start_date, end_date)
        eye_strain_data[period] = health_metrics['eye_strain_reduction']

    return eye_strain_data