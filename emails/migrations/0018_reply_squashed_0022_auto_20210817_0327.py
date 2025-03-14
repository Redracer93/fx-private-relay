# Generated by Django 2.2.24 on 2021-08-17 03:30

from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    replaces = [
        ("emails", "0018_reply"),
        ("emails", "0019_auto_20210817_0318"),
        ("emails", "0020_auto_20210817_0320"),
        ("emails", "0021_auto_20210817_0326"),
        ("emails", "0022_auto_20210817_0327"),
    ]

    dependencies = [
        ("emails", "0017_remove_unique_from_address"),
    ]

    operations = [
        migrations.CreateModel(
            name="Reply",
            fields=[
                (
                    "id",
                    models.AutoField(
                        auto_created=True,
                        primary_key=True,
                        serialize=False,
                        verbose_name="ID",
                    ),
                ),
                ("lookup", models.CharField(max_length=255)),
                ("encrypted_metadata", models.TextField()),
                (
                    "domain_address",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.CASCADE,
                        to="emails.DomainAddress",
                    ),
                ),
                (
                    "relay_address",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.CASCADE,
                        to="emails.RelayAddress",
                    ),
                ),
            ],
        ),
    ]
