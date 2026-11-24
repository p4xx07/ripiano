from django.db import migrations, models
from django.db.models import Q


class Migration(migrations.Migration):
    dependencies = [("archive", "0068_paperstickeralias")]

    operations = [
        migrations.AddField(
            model_name="physicalcopy",
            name="reserved_at",
            field=models.DateTimeField(blank=True, null=True),
        ),
        migrations.AddConstraint(
            model_name="physicalcopy",
            constraint=models.UniqueConstraint(fields=("document",), condition=Q(reserved_at__isnull=False), name="one_reserved_code_per_document"),
        ),
        migrations.AddConstraint(
            model_name="physicalcopy",
            constraint=models.CheckConstraint(condition=Q(reserved_at__isnull=True) | Q(location__isnull=True), name="reserved_code_has_no_location"),
        ),
    ]
