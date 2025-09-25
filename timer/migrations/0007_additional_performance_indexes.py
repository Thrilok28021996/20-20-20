# Performance optimization migration for additional indexes

from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ('timer', '0006_add_performance_indexes'),
    ]

    operations = [
        # Add compound indexes for common query patterns in dashboard and analytics
        migrations.RunSQL(
            "CREATE INDEX IF NOT EXISTS timer_session_user_date_active_idx ON timer_session (user_id, date(start_time), is_active);",
            reverse_sql="DROP INDEX IF EXISTS timer_session_user_date_active_idx;"
        ),
        migrations.RunSQL(
            "CREATE INDEX IF NOT EXISTS timer_session_user_active_idx ON timer_session (user_id, is_active) WHERE is_active = true;",
            reverse_sql="DROP INDEX IF EXISTS timer_session_user_active_idx;"
        ),

        # Add indexes for break analytics queries
        migrations.RunSQL(
            "CREATE INDEX IF NOT EXISTS timer_break_record_user_date_compliance_idx ON timer_break_record (user_id, date(break_start_time), break_completed, break_duration_seconds, looked_at_distance);",
            reverse_sql="DROP INDEX IF EXISTS timer_break_record_user_date_compliance_idx;"
        ),

        # Add indexes for break patterns analysis
        migrations.RunSQL(
            "CREATE INDEX IF NOT EXISTS timer_break_record_hour_analysis_idx ON timer_break_record (user_id, extract(hour from break_start_time), break_completed);",
            reverse_sql="DROP INDEX IF EXISTS timer_break_record_hour_analysis_idx;"
        ),

        # Add index for user timer settings rapid lookup
        migrations.RunSQL(
            "CREATE INDEX IF NOT EXISTS timer_user_settings_user_smart_idx ON timer_user_settings (user_id, smart_break_enabled, preferred_break_duration);",
            reverse_sql="DROP INDEX IF EXISTS timer_user_settings_user_smart_idx;"
        ),

        # Add partial index for active intervals
        migrations.RunSQL(
            "CREATE INDEX IF NOT EXISTS timer_interval_active_lookup_idx ON timer_interval (session_id, status, interval_number) WHERE status = 'active';",
            reverse_sql="DROP INDEX IF EXISTS timer_interval_active_lookup_idx;"
        ),
    ]