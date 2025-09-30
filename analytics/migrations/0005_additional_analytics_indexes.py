# Performance optimization migration for analytics indexes

from django.db import migrations, connection


def apply_indexes(apps, schema_editor):
    """Apply indexes based on database backend"""
    db_vendor = connection.vendor

    with schema_editor.connection.cursor() as cursor:
        # Add indexes for daily stats aggregation queries
        cursor.execute(
            "CREATE INDEX IF NOT EXISTS analytics_daily_stats_user_date_range_idx ON analytics_daily_stats (user_id, date, total_sessions);"
        )

        # Creating index on the underlying columns used for calculation
        cursor.execute(
            "CREATE INDEX IF NOT EXISTS analytics_daily_stats_compliance_calc_idx ON analytics_daily_stats (user_id, breaks_compliant, total_breaks_taken);"
        )

        # Add indexes for user session tracking
        cursor.execute(
            "CREATE INDEX IF NOT EXISTS analytics_user_session_active_recent_idx ON analytics_user_session (is_active, last_activity) WHERE is_active = true;"
        )

        # PostgreSQL-compatible date index without requiring IMMUTABLE
        # Index on login_time directly instead of DATE(login_time)
        cursor.execute(
            "CREATE INDEX IF NOT EXISTS analytics_user_session_today_breaks_idx ON analytics_user_session (login_time, breaks_taken_in_session);"
        )

        # Add indexes for satisfaction analytics
        cursor.execute(
            "CREATE INDEX IF NOT EXISTS analytics_satisfaction_rating_recent_idx ON analytics_satisfaction_rating (rating_date, rating, recommendation_score);"
        )

        # Add indexes for live activity feed
        cursor.execute(
            "CREATE INDEX IF NOT EXISTS analytics_live_activity_public_recent_idx ON analytics_live_activity_feed (is_public, timestamp) WHERE is_public = true;"
        )

        # Add indexes for real-time metrics
        cursor.execute(
            "CREATE INDEX IF NOT EXISTS analytics_realtime_metrics_timestamp_idx ON analytics_realtime_metrics (timestamp DESC);"
        )


def reverse_indexes(apps, schema_editor):
    """Remove indexes"""
    with schema_editor.connection.cursor() as cursor:
        cursor.execute("DROP INDEX IF EXISTS analytics_daily_stats_user_date_range_idx;")
        cursor.execute("DROP INDEX IF EXISTS analytics_daily_stats_compliance_calc_idx;")
        cursor.execute("DROP INDEX IF EXISTS analytics_user_session_active_recent_idx;")
        cursor.execute("DROP INDEX IF EXISTS analytics_user_session_today_breaks_idx;")
        cursor.execute("DROP INDEX IF EXISTS analytics_satisfaction_rating_recent_idx;")
        cursor.execute("DROP INDEX IF EXISTS analytics_live_activity_public_recent_idx;")
        cursor.execute("DROP INDEX IF EXISTS analytics_realtime_metrics_timestamp_idx;")


class Migration(migrations.Migration):

    dependencies = [
        ('analytics', '0004_premiuminsight_premiumanalyticsreport'),
    ]

    operations = [
        migrations.RunPython(apply_indexes, reverse_indexes),
    ]