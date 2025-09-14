# Generated manually for sound notification settings

from django.db import migrations, models
import django.core.validators


class Migration(migrations.Migration):

    dependencies = [
        ('timer', '0001_initial'),
    ]

    operations = [
        migrations.AddField(
            model_name='usertimersettings',
            name='notification_sound_type',
            field=models.CharField(
                choices=[
                    ('gentle', 'Gentle Tone'), 
                    ('chime', 'Chime'), 
                    ('beep', 'Beep'), 
                    ('bell', 'Bell')
                ],
                default='gentle',
                help_text='Type of sound to play when timer reaches zero',
                max_length=10
            ),
        ),
        migrations.AddField(
            model_name='usertimersettings',
            name='sound_volume',
            field=models.FloatField(
                default=0.5,
                help_text='Sound volume (0.0 to 1.0)',
                validators=[
                    django.core.validators.MinValueValidator(0.0),
                    django.core.validators.MaxValueValidator(1.0)
                ]
            ),
        ),
    ]