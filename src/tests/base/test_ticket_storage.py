import os

import pytest
from django.conf import settings

from pretix.base.models import CachedCombinedTicket, CachedTicket


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
