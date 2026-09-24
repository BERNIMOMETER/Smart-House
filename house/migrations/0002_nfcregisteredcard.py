from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [("house", "0001_initial")]

    operations = [
        migrations.CreateModel(
            name="NFCRegisteredCard",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("tag_id", models.CharField(max_length=32, unique=True)),
                ("note", models.CharField(blank=True, max_length=255)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
            ],
            options={"ordering": ["tag_id"]},
        ),
    ]
