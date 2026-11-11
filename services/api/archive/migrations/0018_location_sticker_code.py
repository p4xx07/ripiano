import secrets

import archive.models
from django.db import migrations, models


def populate_codes(apps, schema_editor):
    Location = apps.get_model("archive", "Location")
    database = schema_editor.connection.alias
    alphabet = "23456789ABCDEFGHJKLMNPQRSTUVWXYZ"
    used = set(Location.objects.using(database).exclude(sticker_code__isnull=True).values_list("sticker_code", flat=True))
    for location in Location.objects.using(database).filter(sticker_code__isnull=True).iterator():
        while True:
            code = "L-" + "".join(secrets.choice(alphabet) for _ in range(8))
            if code not in used:
                break
        location.sticker_code = code
        location.save(update_fields=["sticker_code"])
        used.add(code)


class Migration(migrations.Migration):
    dependencies = [("archive", "0017_physicalcopy_missing_at_movement_kind")]

    operations = [
        migrations.AddField(
            model_name="location",
            name="sticker_code",
            field=models.CharField(max_length=10, null=True, unique=True),
        ),
        migrations.RunPython(populate_codes, migrations.RunPython.noop),
        migrations.AlterField(
            model_name="location",
            name="sticker_code",
            field=models.CharField(default=archive.models.new_location_code, max_length=10, unique=True),
        ),
    ]
