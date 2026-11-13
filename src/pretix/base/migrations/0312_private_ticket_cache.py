# Ticket PDFs used to live under MEDIA_ROOT, which is served as static files (and by nginx without
# authentication). They now live in private storage that no static route can reach. The cached tickets
# are regenerated on demand and expire anyway, so the existing public copies are removed here.

from django.core.files.storage import default_storage
from django.db import migrations, models

import pretix.base.models.base
import pretix.base.models.orders


def remove_public_ticket_cache(apps, _):
    for model_name in ("CachedTicket", "CachedCombinedTicket"):
        Model = apps.get_model("pretixbase", model_name)
        for obj in Model.objects.exclude(file__isnull=True).exclude(file="").iterator():
            default_storage.delete(obj.file.name)
        Model.objects.all().delete()


class Migration(migrations.Migration):

    dependencies = [
        ('pretixbase', '0311_fix_unshredded_invoices'),
    ]

    operations = [
        migrations.RunPython(remove_public_ticket_cache, migrations.RunPython.noop),
        migrations.AlterField(
            model_name='cachedcombinedticket',
            name='file',
            field=models.FileField(max_length=255, null=True, storage=pretix.base.models.base.get_private_file_storage, upload_to=pretix.base.models.orders.cachedcombinedticket_name),
        ),
        migrations.AlterField(
            model_name='cachedticket',
            name='file',
            field=models.FileField(max_length=255, null=True, storage=pretix.base.models.base.get_private_file_storage, upload_to=pretix.base.models.orders.cachedticket_name),
        ),
    ]
