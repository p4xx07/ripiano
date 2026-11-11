from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [("archive", "0015_documentnote")]

    operations = [
        migrations.AddField(
            model_name="document",
            name="trashed_at",
            field=models.DateTimeField(blank=True, db_index=True, null=True),
        ),
    ]
