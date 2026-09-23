from django.db import migrations, models


class Migration(migrations.Migration):
    initial = True
    dependencies = []
    operations = [
        migrations.CreateModel(
            name="DeviceState",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("zone", models.CharField(max_length=32)),
                ("device", models.CharField(max_length=32)),
                ("value", models.JSONField(default=dict)),
                ("manual_override", models.BooleanField(default=False)),
                ("updated_at", models.DateTimeField(auto_now=True)),
            ],
            options={"ordering": ["zone", "device"]},
        ),
        migrations.CreateModel(
            name="NFCAuditLog",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("tag_id", models.CharField(max_length=128)),
                ("granted", models.BooleanField(default=False)),
                ("source", models.CharField(default="reader", max_length=32)),
                ("note", models.CharField(blank=True, max_length=255)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
            ],
            options={"ordering": ["-created_at"]},
        ),
        migrations.CreateModel(
            name="SystemState",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("security_mode", models.BooleanField(default=False)),
                ("updated_at", models.DateTimeField(auto_now=True)),
            ],
        ),
        migrations.AddConstraint(
            model_name="devicestate",
            constraint=models.UniqueConstraint(fields=("zone", "device"), name="unique_zone_device"),
        ),
    ]
