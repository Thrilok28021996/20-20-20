# Performance optimization migration for analytics indexes

from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ('analytics', '0004_premiuminsight_premiumanalyticsreport'),
    ]

    operations = [
        # Add indexes for daily stats aggregation queries
        migrations.RunSQL(
            "CREATE INDEX IF NOT EXISTS analytics_daily_stats_user_date_range_idx ON analytics_daily_stats (user_id, date, total_sessions);",
            reverse_sql="DROP INDEX IF EXISTS analytics_daily_stats_user_date_range_idx;"
        ),
        migrations.RunSQL(
            "CREATE INDEX IF NOT EXISTS analytics_daily_stats_compliance_idx ON analytics_daily_stats (user_id, compliance_rate) WHERE compliance_rate = 100.0;",
            reverse_sql="DROP INDEX IF EXISTS analytics_daily_stats_compliance_idx;"
        ),

        # Add indexes for user session tracking
        migrations.RunSQL(
            "CREATE INDEX IF NOT EXISTS analytics_user_session_active_recent_idx ON analytics_user_session (is_active, last_activity) WHERE is_active = true;",
            reverse_sql="DROP INDEX IF EXISTS analytics_user_session_active_recent_idx;"
        ),
        migrations.RunSQL(
            "CREATE INDEX IF NOT EXISTS analytics_user_session_today_breaks_idx ON analytics_user_session (date(login_time), breaks_taken_in_session);",
            reverse_sql="DROP INDEX IF EXISTS analytics_user_session_today_breaks_idx;"
        ),

        # Add indexes for satisfaction analytics
        migrations.RunSQL(
            "CREATE INDEX IF NOT EXISTS analytics_satisfaction_rating_recent_idx ON analytics_satisfaction_rating (rating_date, rating, recommendation_score) WHERE rating_date >= CURRENT_DATE - INTERVAL '30 days';",
            reverse_sql="DROP INDEX IF EXISTS analytics_satisfaction_rating_recent_idx;"
        ),

        # Add indexes for live activity feed
        migrations.RunSQL(
            "CREATE INDEX IF NOT EXISTS analytics_live_activity_public_recent_idx ON analytics_live_activity_feed (is_public, timestamp) WHERE is_public = true;",
            reverse_sql="DROP INDEX IF EXISTS analytics_live_activity_public_recent_idx;"
        ),

        # Add indexes for real-time metrics
        migrations.RunSQL(
            "CREATE INDEX IF NOT EXISTS analytics_realtime_metrics_timestamp_idx ON analytics_realtime_metrics (timestamp DESC);",
            reverse_sql="DROP INDEX IF EXISTS analytics_realtime_metrics_timestamp_idx;"
        ),
    ]