"""TS-UI-01A: Sunderland visual proof of concept, reusable for any club ID.

All game models are read-only: no renaming of the canonical Northbridge career.
"""
from pathlib import Path
import json
from html.parser import HTMLParser

from PIL import Image
import pytest

from football_manager.dev_ui.session import DevelopmentSession
from football_manager.ui_shell.calendar import calendar_read_model
from football_manager.ui_shell.competitions import competition_options, competition_read_model
from football_manager.ui_shell.models import squad_read_model
from football_manager.ui_shell.home_news import home_news_read_model

FRONT = Path(__file__).resolve().parents[1] / 'frontend' / 'portable'
CATALOG = FRONT / 'data' / 'club-identities.json'


@pytest.fixture(scope='module')
def session():
    return DevelopmentSession()


def test_identity_catalog_is_club_id_based_and_presentation_only(session):
    identity = json.loads(CATALOG.read_text(encoding='utf-8'))
    assert identity['schema_version'] == 1
    configured = identity['clubs'][session.home_club.id]
    assert configured['visual_only'] is True
    assert configured['display_name'] == 'Sunderland AFC'
    assert configured['stadium'] == 'Stadium of Light'
    assert configured['founded'] == 1879
    assert session.home_club.id == 'northbridge'
    assert session.home_club.name == 'Northbridge FC'
    # Other clubs use live data and default visuals; no code path mentions Sunderland.
    for file in ('ui_home.js', 'club_identity.js', 'ui_home.css'):
        assert 'Sunderland' not in (FRONT / file).read_text(encoding='utf-8')
    assert 'visual_only' in (FRONT / 'club_identity.js').read_text(encoding='utf-8')


def test_approved_hero_assets_are_local_usable_and_clear():
    data = json.loads(CATALOG.read_text(encoding='utf-8'))['clubs']['northbridge']
    for field in ('crest', 'hero_image'):
        asset = (FRONT / data[field]).resolve()
        assert asset.is_relative_to(FRONT.resolve())
        assert asset.exists() and asset.stat().st_size > 8000
    with Image.open(FRONT / data['crest']) as crest:
        assert crest.mode == 'RGBA'
        assert crest.getchannel('A').getextrema() == (0, 255)
    with Image.open(FRONT / data['hero_image']) as hero:
        assert hero.width >= 2000 and hero.height >= 1000


def test_portable_document_loads_new_modules_without_removing_old_navigation():
    page = (FRONT / 'index.html').read_text(encoding='utf-8')
    assert 'ui_home.css' in page and 'ui_home.js' in page and 'club_identity.js' in page
    assert page.index('club_identity.js') < page.index('portable.js') < page.index('ui_home.js')
    for route in ('Home', 'Squad', 'Calendar', 'Competitions', 'Inbox'):
        assert route in page
    ui = (FRONT / 'ui_home.js').read_text(encoding='utf-8')
    for hook in ('/api/squad','/api/calendar','/api/competitions','/api/inbox','/api/news'):
        assert hook in ui
    assert "c.managed" in ui
    assert 'data-tsui-competition' in ui and 'data-tsui-activity' in ui
    assert 'managed_entry_round_label' in ui


def test_all_four_widgets_use_unchanged_world_read_models(session):
    before = (session.home_club.id,session.home_club.name,session.current_date,
              len(session._world.results))
    squad = squad_read_model(session)
    calendar = calendar_read_model(session)
    index = competition_options(session)
    news = home_news_read_model(session)
    assert squad['club_id'] == index['managed_id'] == before[0]
    assert len(squad['starters']) == 11
    assert len(calendar['matches']) > 0
    assert all(c['managed'] for c in index['competitions'])
    assert any(c['kind'] == 'cup' for c in index['competitions'])
    cup = next(c for c in index['competitions'] if c['kind'] == 'cup')
    comp = competition_read_model(session,cup['id'])
    assert comp['kind'] == 'cup'
    assert 'knockout' in comp
    assert news['source'] == 'career-ledgers'
    assert (session.home_club.id,session.home_club.name,session.current_date,
            len(session._world.results)) == before
