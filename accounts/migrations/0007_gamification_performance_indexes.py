# Performance optimization migration for accounts/gamification indexes

from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ('accounts', '0006_badge_challenge_userlevel_userbadge_and_more'),
    ]

    operations = [
        # Add indexes for user achievements and badges
        migrations.RunSQL(
            "CREATE INDEX IF NOT EXISTS accounts_achievement_user_recent_idx ON accounts_achievement (user_id, earned_at DESC);",
            reverse_sql="DROP INDEX IF EXISTS accounts_achievement_user_recent_idx;"
        ),
        migrations.RunSQL(
            "CREATE INDEX IF NOT EXISTS accounts_userbadge_user_earned_idx ON accounts_userbadge (user_id, earned_at DESC);",
            reverse_sql="DROP INDEX IF EXISTS accounts_userbadge_user_earned_idx;"
        ),

        # Add indexes for streak data queries
        migrations.RunSQL(
            "CREATE INDEX IF NOT EXISTS accounts_userstreakdata_user_current_streak_idx ON accounts_userstreakdata (user_id, current_daily_streak, best_daily_streak);",
            reverse_sql="DROP INDEX IF EXISTS accounts_userstreakdata_user_current_streak_idx;"
        ),
        migrations.RunSQL(
            "CREATE INDEX IF NOT EXISTS accounts_userstreakdata_last_session_idx ON accounts_userstreakdata (user_id, last_session_date);",
            reverse_sql="DROP INDEX IF EXISTS accounts_userstreakdata_last_session_idx;"
        ),

        # Add indexes for user level data
        migrations.RunSQL(
            "CREATE INDEX IF NOT EXISTS accounts_userlevel_user_level_idx ON accounts_userlevel (user_id, current_level, total_experience_points);",
            reverse_sql="DROP INDEX IF EXISTS accounts_userlevel_user_level_idx;"
        ),

        # Add indexes for challenge participation
        migrations.RunSQL(
            "CREATE INDEX IF NOT EXISTS accounts_challengeparticipation_active_idx ON accounts_challengeparticipation (user_id, challenge_id, is_completed);",
            reverse_sql="DROP INDEX IF EXISTS accounts_challengeparticipation_active_idx;"
        ),
        migrations.RunSQL(
            "CREATE INDEX IF NOT EXISTS accounts_challenge_active_period_idx ON accounts_challenge (is_active, start_date, end_date) WHERE is_active = true;",
            reverse_sql="DROP INDEX IF EXISTS accounts_challenge_active_period_idx;"
        ),

        # Add indexes for badge requirements checking
        migrations.RunSQL(
            "CREATE INDEX IF NOT EXISTS accounts_badge_active_requirements_idx ON accounts_badge (is_active, category, rarity) WHERE is_active = true;",
            reverse_sql="DROP INDEX IF EXISTS accounts_badge_active_requirements_idx;"
        ),

        # Add indexes for user subscription and premium features
        migrations.RunSQL(
            "CREATE INDEX IF NOT EXISTS accounts_user_subscription_active_idx ON accounts_user (subscription_type, subscription_end_date);",
            reverse_sql="DROP INDEX IF EXISTS accounts_user_subscription_active_idx;"
        ),
    ]