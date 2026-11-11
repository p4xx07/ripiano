from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [("archive", "0016_document_trashed_at")]

    operations = [
        migrations.AddField(
            model_name="physicalcopy",
            name="missing_at",
            field=models.DateTimeField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name="movement",
            name="kind",
            field=models.CharField(choices=[("placement", "Initial placement"), ("move", "Move"), ("missing", "Marked missing"), ("found", "Marked found")], default="move", max_length=12),
        ),
    ]
