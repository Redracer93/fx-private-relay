# Generated by Django 2.2.27 on 2022-05-05 15:10

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("emails", "0042_domainaddress_used_on"),
    ]

    operations = [
        migrations.AddField(
            model_name="domainaddress",
            name="num_replied",
            field=models.PositiveIntegerField(default=0),
        ),
        migrations.AddField(
            model_name="relayaddress",
            name="num_replied",
            field=models.PositiveIntegerField(default=0),
        ),
    ]
