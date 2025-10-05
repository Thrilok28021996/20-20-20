# Generated manually for test premium tracking

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('accounts', '0007_gamification_performance_indexes'),
    ]

    operations = [
        migrations.AddField(
            model_name='user',
            name='test_premium_metadata',
            field=models.JSONField(blank=True, default=dict),
        ),
    ]
