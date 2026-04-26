from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("users", "0009_friendrequest"),
    ]

    operations = [
        migrations.AddField(
            model_name="directmessage",
            name="image",
            field=models.ImageField(blank=True, null=True, upload_to="direct_message_images/"),
        ),
    ]
