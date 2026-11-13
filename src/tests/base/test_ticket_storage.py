import importlib
import os
from datetime import timedelta
from decimal import Decimal

import pytest
from django.apps import apps
from django.conf import settings
from django.core.files.base import ContentFile
from django.core.files.storage import default_storage
from django.utils.timezone import now
from django_scopes import scope

from pretix.base.models import (
    CachedCombinedTicket, CachedTicket, Event, Order, OrderPosition, Organizer,
)


@pytest.mark.parametrize("model", [CachedTicket, CachedCombinedTicket])
def test_ticket_cache_storage_is_private(model):
    storage = model._meta.get_field("file").storage
    private_root = os.path.abspath(os.path.join(settings.DATA_DIR, "private"))
    media_root = os.path.abspath(settings.MEDIA_ROOT)

    assert os.path.abspath(storage.location) == private_root
    assert not os.path.abspath(storage.location).startswith(media_root + os.sep)


@pytest.mark.parametrize("model", [CachedTicket, CachedCombinedTicket])
def test_ticket_cache_files_have_no_url(model):
    # No link can be generated for a ticket file, so templates and serializers cannot publish one.
    obj = model(file="tickets/example/example/ticket.dat")
    with pytest.raises(ValueError):
        obj.file.url


@pytest.fixture
def ticketed_order():
    o = Organizer.objects.create(name='Dummy', slug='dummy', plugins='pretix.plugins.banktransfer')
    event = Event.objects.create(
        organizer=o, name='Dummy', slug='dummy', date_from=now(),
        plugins='pretix.plugins.banktransfer,pretix.plugins.ticketoutputpdf',
    )
    with scope(organizer=o):
        item = event.items.create(name='Ticket', category=None, default_price=23, admission=True)
        order = Order.objects.create(
            code='FOO', event=event, email='dummy@dummy.test', status=Order.STATUS_PENDING,
            datetime=now(), expires=now() + timedelta(days=10),
            sales_channel=event.organizer.sales_channels.get(identifier="web"), total=14, locale='en',
        )
        OrderPosition.objects.create(
            order=order, item=item, variation=None, price=Decimal("14"),
            attendee_name_parts={'full_name': "Peter", "_scheme": "full"},
        )
        yield order


@pytest.mark.django_db
def test_migration_removes_public_ticket_cache(ticketed_order):
    migration = importlib.import_module("pretix.base.migrations.0312_private_ticket_cache")

    position = ticketed_order.positions.first()
    # A legacy ticket cache entry, as written before this change: a file under MEDIA_ROOT and rows pointing at it.
    legacy_name = default_storage.save("tickets/legacy-test.dat", ContentFile(b"%PDF legacy"))
    legacy_path = default_storage.path(legacy_name)
    ct = CachedTicket.objects.create(order_position=position, provider="pdf", type="application/pdf",
                                     extension=".pdf", file=legacy_name)
    cct = CachedCombinedTicket.objects.create(order=ticketed_order, provider="pdf", type="application/pdf",
                                              extension=".pdf", file=legacy_name)
    try:
        assert os.path.exists(legacy_path)
        migration.remove_public_ticket_cache(apps, None)
        assert not os.path.exists(legacy_path)
        assert not CachedTicket.objects.filter(pk=ct.pk).exists()
        assert not CachedCombinedTicket.objects.filter(pk=cct.pk).exists()
    finally:
        if os.path.exists(legacy_path):
            os.remove(legacy_path)
