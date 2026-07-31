# Add sawie_id: create as non-unique, backfill existing rows, then enforce unique.
from django.db import migrations, models


def backfill_sawie_ids(apps, schema_editor):
    Farmer = apps.get_model("farmers", "Farmer")
    n = 1101
    # Assign in registration order so older farmers get lower numbers.
    for farmer in Farmer.objects.filter(sawie_id="").order_by("registration_date", "id"):
        while Farmer.objects.filter(sawie_id=f"SW{n}").exists():
            n += 1
        farmer.sawie_id = f"SW{n}"
        farmer.save(update_fields=["sawie_id"])
        n += 1


def noop(apps, schema_editor):
    pass


class Migration(migrations.Migration):

    dependencies = [
        ("farmers", "0001_initial"),
    ]

    operations = [
        # 1) Add the column, not yet unique, default blank.
        migrations.AddField(
            model_name="farmer",
            name="sawie_id",
            field=models.CharField(
                blank=True, db_index=True, default="",
                help_text="Auto-generated unique ID (e.g. SW1101).",
                max_length=12, verbose_name="SAWiE ID",
            ),
        ),
        # 2) Backfill existing farmers with SW1101, SW1102, ...
        migrations.RunPython(backfill_sawie_ids, noop),
        # 3) Now enforce uniqueness.
        migrations.AlterField(
            model_name="farmer",
            name="sawie_id",
            field=models.CharField(
                blank=True, db_index=True, unique=True,
                help_text="Auto-generated unique ID (e.g. SW1101).",
                max_length=12, verbose_name="SAWiE ID",
            ),
        ),
    ]
