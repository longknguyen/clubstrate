from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('discussions', '0002_post_kind_and_blank_title'),
    ]

    operations = [
        migrations.AddField(
            model_name='post',
            name='announcement_tags',
            field=models.JSONField(blank=True, default=list),
        ),
    ]
