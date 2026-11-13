import pytest
from django.utils.timezone import now
from django_scopes import scopes_disabled

from pretix.base.models import Event, Organizer, Team, User
from pretix.plugins.ticketoutputpdf.models import TicketLayout


@pytest.mark.django_db
def test_layout_editor_loads_pdfjs_as_module(client):
    with scopes_disabled():
        user = User.objects.create_user('dummy@dummy.dummy', 'dummy')
        orga = Organizer.objects.create(name='Dummy', slug='dummy')
        event = Event.objects.create(
            organizer=orga, name='Dummy', slug='dummy', date_from=now(),
            plugins='pretix.plugins.ticketoutputpdf',
        )
        team = Team.objects.create(organizer=orga, all_event_permissions=True)
        team.members.add(user)
        team.limit_events.add(event)
        layout = TicketLayout.objects.create(event=event, name='Layout', layout='[]')

    client.login(email='dummy@dummy.dummy', password='dummy')
    r = client.get(f'/control/event/dummy/dummy/pdfoutput/{layout.pk}/editor')
    assert r.status_code == 200
    html = r.content.decode()

    # pdf.js 4.x is an ES module, loaded on demand by the editor; the 3.x UMD script must not be referenced.
    assert 'data-pdfjs-url="/static/pdfjs/pdf.mjs"' in html
    assert 'data-worker-url="/static/pdfjs/pdf.worker.mjs"' in html
    assert 'pdfjs/pdf.js' not in html
