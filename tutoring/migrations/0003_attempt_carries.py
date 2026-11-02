from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [('tutoring', '0002_attempt')]
    operations = [
        migrations.AddField(
            model_name='attempt', name='carries',
            field=models.JSONField(blank=True, default=dict),
        ),
    ]
