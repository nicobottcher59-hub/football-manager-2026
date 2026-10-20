"""TS-UI-01A.3.1: all match rows use the working Carabao branding path."""
from pathlib import Path

from PIL import Image

from football_manager.dev_ui.session import DevelopmentSession
from football_manager.ui_shell.calendar import calendar_read_model

FRONT = Path(__file__).resolve().parents[1] / 'frontend' / 'portable'


def test_calendar_ids_equal_canonical_fixture_ids_not_legacy_schedule_keys():
    session = DevelopmentSession()
    data = calendar_read_model(session)
    for game in data['matches']:
        expected = session._world.fixtures[game['id']].competition_id
        assert game['competition_id'] == expected, (game['competition'], game['competition_id'], expected)
    ids = {game['competition_id'] for game in data['matches']}
    assert {'dev-premier', 'carabao-cup', 'champions-league'} <= ids
    assert 'league' not in ids
    # FA Cup is a registered competition but may not be drawn yet in August.
    assert any(item.cup_id == 'fa-cup' for item in session._world.cups.values())


def test_all_four_competition_logos_and_themes_use_one_registry():
    registry = (FRONT / 'competition_branding.js').read_text(encoding='utf-8')
    for item in ('dev-premier', 'fa-cup', 'carabao-cup', 'champions-league'):
        assert f"'{item}':{{" in registry
    home = (FRONT / 'ui_home.js').read_text(encoding='utf-8')
    assert 'competitionLabel(first.competition_id,first.competition,true)' in home
    assert 'competitionLabel(f.competition_id,f.competition)' in home
    assert 'branding(f.competition_id).key' in home
    assert 'brandStyle(f.competition_id)' in home
    css = (FRONT / 'competition_branding.css').read_text(encoding='utf-8')
    assert 'color:var(--ci-accent' in css
    assert '.tsui-home .tsui-fixture-row[data-competition-brand]' in css
    for file in ('premier-league-icon.png', 'champions-league-icon.png', 'fa-cup-icon.png', 'carabao-cup.png'):
        assert (FRONT / 'assets/competitions' / file).exists()


def test_champions_icon_is_usable_in_the_same_compact_slot_as_carabao():
    with Image.open(FRONT / 'assets/competitions/champions-league-icon.png') as image:
        assert image.size == (160, 160)
        bounds = image.convert('RGBA').getchannel('A').getbbox()
        assert bounds is not None
        assert bounds[2] - bounds[0] > 110
        assert bounds[3] - bounds[1] > 125


def test_full_calendar_still_recognizes_premier_league_after_canonical_id_fix():
    js = (FRONT / 'calendar.js').read_text(encoding='utf-8')
    assert "'dev-premier':'league'" in js
    assert "'fa-cup':'fa'" in js
    assert "'champions-league':'champions'" in js
