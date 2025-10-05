"""
Celery tasks for analytics and real-time metrics
"""
from celery import shared_task
from django.utils import timezone
from datetime import date, timedelta
from .models import RealTimeMetrics, UserSession, DailyStats, WeeklyStats, MonthlyStats
from .views import update_real_time_metrics
from accounts.timezone_utils import user_today


@shared_task
def update_metrics_periodically():
    """
    Update real-time metrics every minute
    """
    try:
        # Update main metrics
        update_real_time_metrics()
        
        # Clean up old user sessions (inactive for more than 1 hour)
        cutoff_time = timezone.now() - timedelta(hours=1)
        UserSession.objects.filter(
            last_activity__lt=cutoff_time,
            is_active=True
        ).update(
            is_active=False,
            logout_time=timezone.now()
        )
        
        return f"Metrics updated at {timezone.now()}"
    except Exception as e:
        return f"Error updating metrics: {str(e)}"


@shared_task
def generate_daily_reports():
    """
    Generate daily statistical reports (run at end of each day)
    """
    try:
        yesterday = date.today() - timedelta(days=1)
        
        # This would typically aggregate data from various sources
        # For now, just ensure daily stats exist
        from accounts.models import User
        
        users = User.objects.filter(is_active=True)
        reports_created = 0
        
        for user in users:
            daily_stats, created = DailyStats.objects.get_or_create(
                user=user,
                date=yesterday,
                defaults={
                    'total_work_minutes': 0,
                    'total_intervals_completed': 0,
                    'total_breaks_taken': 0,
                    'total_sessions': 0,
                }
            )
            if created:
                reports_created += 1
        
        return f"Generated {reports_created} daily reports for {yesterday}"
    except Exception as e:
        return f"Error generating daily reports: {str(e)}"


@shared_task
def send_satisfaction_survey():
    """
    Send satisfaction surveys to active users (weekly)
    """
    try:
        from accounts.models import User
        from django.core.mail import send_mail
        from django.conf import settings
        
        # Get users who haven't rated in the last 7 days
        week_ago = timezone.now() - timedelta(days=7)
        
        users_to_survey = User.objects.filter(
            is_active=True,
            satisfaction_ratings__rating_date__lt=week_ago,
            email_notifications=True
        ).distinct()[:50]  # Limit to 50 users per batch
        
        surveys_sent = 0
        for user in users_to_survey:
            try:
                send_mail(
                    subject='How is your eye health journey going?',
                    message=f'''
Hi {user.get_full_name()},

We hope you're enjoying EyeHealth 20-20-20! 

We'd love to hear how the app is helping you protect your vision. 
Your feedback helps us make the experience even better.

Please take a moment to rate your experience: {settings.SITE_URL}/timer/real-time/

Thank you for taking care of your eyes!

Best regards,
The EyeHealth 20-20-20 Team
                    '''.strip(),
                    from_email=settings.DEFAULT_FROM_EMAIL,
                    recipient_list=[user.email],
                    fail_silently=True,
                )
                surveys_sent += 1
            except Exception as email_error:
                print(f"Failed to send survey to {user.email}: {email_error}")
        
        return f"Sent satisfaction surveys to {surveys_sent} users"
    except Exception as e:
        return f"Error sending satisfaction surveys: {str(e)}"


@shared_task
def cleanup_old_metrics():
    """
    Clean up old real-time metrics (keep only last 24 hours)
    """
    try:
        cutoff_time = timezone.now() - timedelta(hours=24)
        
        deleted_count = RealTimeMetrics.objects.filter(
            timestamp__lt=cutoff_time
        ).delete()[0]
        
        return f"Cleaned up {deleted_count} old metric records"
    except Exception as e:
        return f"Error cleaning up metrics: {str(e)}"


@shared_task
def update_user_streaks():
    """
    Update user streaks based on daily activity
    """
    try:
        from accounts.models import User, UserProfile
        
        today = date.today()
        yesterday = today - timedelta(days=1)
        
        users_updated = 0
        
        for user in User.objects.filter(is_active=True):
            profile, created = UserProfile.objects.get_or_create(user=user)
            
            # Check if user was active yesterday
            yesterday_stats = DailyStats.objects.filter(
                user=user,
                date=yesterday,
                total_sessions__gt=0
            ).first()
            
            if yesterday_stats:
                # User was active, increment streak
                profile.current_streak_days += 1
                if profile.current_streak_days > profile.longest_streak_days:
                    profile.longest_streak_days = profile.current_streak_days
            else:
                # User was not active, reset streak
                profile.current_streak_days = 0
            
            profile.save()
            users_updated += 1
        
        return f"Updated streaks for {users_updated} users"
    except Exception as e:
        return f"Error updating user streaks: {str(e)}"


@shared_task
def generate_weekly_insights():
    """
    Generate weekly insights and recommendations for users
    """
    try:
        from accounts.models import User
        from django.core.mail import send_mail
        from django.conf import settings
        
        # Get users who should receive weekly reports
        users_for_reports = User.objects.filter(
            is_active=True,
            weekly_report=True,
        )[:100]  # Limit batch size
        
        reports_sent = 0
        
        for user in users_for_reports:
            # Calculate weekly stats
            week_start = date.today() - timedelta(days=7)
            from django.db.models import Sum, Avg
            weekly_stats = DailyStats.objects.filter(
                user=user,
                date__gte=week_start
            ).aggregate(
                total_work_minutes=Sum('total_work_minutes'),
                total_breaks=Sum('total_breaks_taken'),
                total_breaks_compliant=Sum('breaks_compliant')
            )

            # Calculate average compliance
            total_breaks = weekly_stats['total_breaks'] or 0
            total_compliant = weekly_stats['total_breaks_compliant'] or 0
            weekly_stats['avg_compliance'] = (total_compliant / total_breaks * 100) if total_breaks > 0 else 0
            
            # Generate insights
            insights = generate_user_insights(user, weekly_stats)
            
            # Send email
            try:
                send_mail(
                    subject='Your Weekly Eye Health Summary',
                    message=f'''
Hi {user.get_full_name()},

Here's your eye health summary for this week:

📊 Your Weekly Stats:
• Work minutes: {weekly_stats['total_work_minutes'] or 0}
• Breaks taken: {weekly_stats['total_breaks'] or 0}
• Compliance rate: {weekly_stats['avg_compliance'] or 0:.1f}%

💡 Personalized Insights:
{insights}

Keep up the great work protecting your vision!

View detailed statistics: {settings.SITE_URL}/timer/statistics/

Best regards,
The EyeHealth 20-20-20 Team
                    '''.strip(),
                    from_email=settings.DEFAULT_FROM_EMAIL,
                    recipient_list=[user.email],
                    fail_silently=True,
                )
                reports_sent += 1
            except Exception as email_error:
                print(f"Failed to send weekly report to {user.email}: {email_error}")
        
        return f"Sent weekly insights to {reports_sent} users"
    except Exception as e:
        return f"Error generating weekly insights: {str(e)}"


def generate_user_insights(user, weekly_stats):
    """
    Generate personalized insights for a user based on their stats
    """
    insights = []
    
    work_minutes = weekly_stats.get('total_work_minutes', 0)
    total_breaks = weekly_stats.get('total_breaks', 0)
    compliance_rate = weekly_stats.get('avg_compliance', 0)
    
    # Work time insights
    if work_minutes > 2000:  # More than 33 hours
        insights.append("💪 You've been very productive this week! Remember to take regular breaks.")
    elif work_minutes < 300:  # Less than 5 hours
        insights.append("⏰ You had a light work week. Consider using the app more regularly when working.")
    
    # Break compliance insights
    if compliance_rate > 80:
        insights.append("🌟 Excellent compliance! You're doing great at following the 20-20-20 rule.")
    elif compliance_rate > 60:
        insights.append("👍 Good job on taking breaks! Try to be more consistent for even better eye health.")
    elif compliance_rate > 30:
        insights.append("📈 You're making progress with breaks. Try setting reminders to improve consistency.")
    else:
        insights.append("🎯 Focus on taking more regular breaks. Your eyes will thank you!")
    
    # Break frequency insights
    expected_breaks = work_minutes // 20  # One break every 20 minutes
    if total_breaks > expected_breaks * 0.8:
        insights.append("✅ You're taking breaks at a good frequency!")
    else:
        insights.append("⏱️ Try to take more frequent breaks - aim for one every 20 minutes.")
    
    return '\n• '.join(insights) if insights else "Keep up the good work with your eye health routine!"