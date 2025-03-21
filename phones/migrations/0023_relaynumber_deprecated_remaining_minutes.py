# Generated by Django 3.2.15 on 2022-09-28 01:14

from django.db import migrations, models


def add_db_default_forward_func(apps, schema_editor):
    """
    Add a database default of 3000 for remaining_seconds, for PostgreSQL and SQLite3

    Using `./manage.py sqlmigrate` for the SQL, and the technique from:
    https://stackoverflow.com/a/45232678/10612
    """
    if schema_editor.connection.vendor.startswith("postgres"):
        schema_editor.execute(
            'ALTER TABLE "phones_relaynumber"'
            ' ALTER COLUMN "remaining_minutes" SET DEFAULT 50;'
        )
    elif schema_editor.connection.vendor.startswith("sqlite"):
        schema_editor.execute(
            'CREATE TABLE "new__phones_relaynumber"'
            ' ("id" integer NOT NULL PRIMARY KEY AUTOINCREMENT,'
            ' "calls_blocked" integer NOT NULL DEFAULT 0,'
            ' "calls_forwarded" integer NOT NULL DEFAULT 0,'
            ' "enabled" bool NOT NULL DEFAULT 1,'
            ' "location" varchar(255) NOT NULL,'
            ' "number" varchar(15) NOT NULL,'
            ' "remaining_minutes" integer NULL DEFAULT 50,'
            ' "remaining_seconds" integer NOT NULL DEFAULT 3000,'
            ' "remaining_texts" integer NOT NULL DEFAULT 75,'
            ' "texts_blocked" integer NOT NULL DEFAULT 0,'
            ' "texts_forwarded" integer NOT NULL DEFAULT 0,'
            ' "user_id" integer NOT NULL REFERENCES "auth_user" ("id") DEFERRABLE INITIALLY DEFERRED,'
            ' "vcard_lookup_key" varchar(6) NOT NULL UNIQUE);'
        )
        schema_editor.execute(
            'INSERT INTO "new__phones_relaynumber" ("id", "number", "location",'
            ' "user_id", "vcard_lookup_key", "enabled", "calls_blocked",'
            ' "calls_forwarded", "remaining_texts", "texts_blocked",'
            ' "texts_forwarded", "remaining_seconds", "remaining_minutes")'
            ' SELECT "id", "number", "location", "user_id", "vcard_lookup_key",'
            ' "enabled", "calls_blocked", "calls_forwarded", "remaining_texts",'
            ' "texts_blocked", "texts_forwarded", "remaining_seconds", NULL'
            ' FROM "phones_relaynumber";'
        )
        schema_editor.execute('DROP TABLE "phones_relaynumber";')
        schema_editor.execute(
            'ALTER TABLE "new__phones_relaynumber" RENAME TO "phones_relaynumber";'
        )
        schema_editor.execute(
            'CREATE INDEX "phones_relaynumber_number_742e5d6b" ON "phones_relaynumber"'
            ' ("number");'
        )
        schema_editor.execute(
            'CREATE INDEX "phones_relaynumber_user_id_62c65ede" ON "phones_relaynumber"'
            ' ("user_id");'
        )
    else:
        raise Exception(f'Unknown database vendor "{schema_editor.connection.vendor}"')


class Migration(migrations.Migration):

    dependencies = [
        ("phones", "0022_relaynumber_remaining_seconds_20220921_1829"),
    ]

    operations = [
        migrations.AddField(
            model_name="relaynumber",
            name="deprecated_remaining_minutes",
            field=models.IntegerField(
                blank=True, db_column="remaining_minutes", default=50, null=True
            ),
        ),
        migrations.RunPython(
            code=add_db_default_forward_func,
            reverse_code=migrations.RunPython.noop,
            elidable=True,
        ),
    ]
