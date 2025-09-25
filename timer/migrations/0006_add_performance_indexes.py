# Generated optimization migration for performance indexes

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('timer', '0005_userfeedback_breakpreferenceanalytics'),
    ]

    operations = [
        # Add indexes to BreakRecord model for better performance
        migrations.RunSQL(
            "CREATE INDEX IF NOT EXISTS timer_break_record_user_start_time_idx ON timer_break_record (user_id, break_start_time);",
            reverse_sql="DROP INDEX IF EXISTS timer_break_record_user_start_time_idx;"
        ),
        migrations.RunSQL(
            "CREATE INDEX IF NOT EXISTS timer_break_record_session_completed_idx ON timer_break_record (session_id, break_completed);",
            reverse_sql="DROP INDEX IF EXISTS timer_break_record_session_completed_idx;"
        ),
        migrations.RunSQL(
            "CREATE INDEX IF NOT EXISTS timer_break_record_start_completed_idx ON timer_break_record (break_start_time, break_completed);",
            reverse_sql="DROP INDEX IF EXISTS timer_break_record_start_completed_idx;"
        ),
        migrations.RunSQL(
            "CREATE INDEX IF NOT EXISTS timer_break_record_user_compliance_idx ON timer_break_record (user_id, break_completed, break_duration_seconds);",
            reverse_sql="DROP INDEX IF EXISTS timer_break_record_user_compliance_idx;"
        ),

        # Add indexes to TimerInterval model for better performance
        migrations.RunSQL(
            "CREATE INDEX IF NOT EXISTS timer_interval_session_status_idx ON timer_interval (session_id, status);",
            reverse_sql="DROP INDEX IF EXISTS timer_interval_session_status_idx;"
        ),
        migrations.RunSQL(
            "CREATE INDEX IF NOT EXISTS timer_interval_start_status_idx ON timer_interval (start_time, status);",
            reverse_sql="DROP INDEX IF EXISTS timer_interval_start_status_idx;"
        ),
        migrations.RunSQL(
            "CREATE INDEX IF NOT EXISTS timer_interval_session_number_idx ON timer_interval (session_id, interval_number);",
            reverse_sql="DROP INDEX IF EXISTS timer_interval_session_number_idx;"
        ),
    ]