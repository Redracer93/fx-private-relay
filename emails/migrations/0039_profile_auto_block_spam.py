# Generated by Django 2.2.24 on 2022-01-11 21:15

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        (
            "emails",
            "0038_domain_address_min_length_validator_and_unique_together_user_and_address",
        ),
    ]

    operations = [
        migrations.AddField(
            model_name="profile",
            name="auto_block_spam",
            field=models.BooleanField(default=False),
        ),
    ]
