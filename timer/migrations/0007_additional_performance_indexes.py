# Performance optimization migration for additional indexes

from django.db import migrations


def apply_indexes(apps, schema_editor):
    """Apply indexes based on database backend"""
    with schema_editor.connection.cursor() as cursor:
        # Add compound indexes for common query patterns
        # Index on start_time directly instead of date(start_time)
        cursor.execute(
            "CREATE INDEX IF NOT EXISTS timer_session_user_date_active_idx "
            "ON timer_session (user_id, start_time, is_active);"
        )

        cursor.execute(
            "CREATE INDEX IF NOT EXISTS timer_session_user_active_idx "
            "ON timer_session (user_id, is_active) WHERE is_active = true;"
        )

        # Add indexes for break analytics queries
        # Index on break_start_time directly instead of date(break_start_time)
        cursor.execute(
            "CREATE INDEX IF NOT EXISTS timer_break_record_user_date_compliance_idx "
            "ON timer_break_record (user_id, break_start_time, break_completed, break_duration_seconds, looked_at_distance);"
        )

        # Index on break_start_time directly instead of extracting hour
        cursor.execute(
            "CREATE INDEX IF NOT EXISTS timer_break_record_hour_analysis_idx "
            "ON timer_break_record (user_id, break_start_time, break_completed);"
        )

        # Add index for user timer settings rapid lookup
        cursor.execute(
            "CREATE INDEX IF NOT EXISTS timer_user_settings_user_smart_idx "
            "ON timer_user_settings (user_id, smart_break_enabled, preferred_break_duration);"
        )

        # Add partial index for active intervals
        cursor.execute(
            "CREATE INDEX IF NOT EXISTS timer_interval_active_lookup_idx "
            "ON timer_interval (session_id, status, interval_number) WHERE status = 'active';"
        )


def reverse_indexes(apps, schema_editor):
    """Remove indexes"""
    with schema_editor.connection.cursor() as cursor:
        cursor.execute("DROP INDEX IF EXISTS timer_session_user_date_active_idx;")
        cursor.execute("DROP INDEX IF EXISTS timer_session_user_active_idx;")
        cursor.execute("DROP INDEX IF EXISTS timer_break_record_user_date_compliance_idx;")
        cursor.execute("DROP INDEX IF EXISTS timer_break_record_hour_analysis_idx;")
        cursor.execute("DROP INDEX IF EXISTS timer_user_settings_user_smart_idx;")
        cursor.execute("DROP INDEX IF EXISTS timer_interval_active_lookup_idx;")


class Migration(migrations.Migration):

    dependencies = [
        ('timer', '0006_add_performance_indexes'),
    ]

    operations = [
        migrations.RunPython(apply_indexes, reverse_indexes),
    ]