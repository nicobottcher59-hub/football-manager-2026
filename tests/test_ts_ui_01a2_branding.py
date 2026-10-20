"""TS-UI-01A.2 regression: shared competition visuals and truthful cup overview.
These structural/asset tests don't need to start or mutate the game world.
"""
from pathlib import Path

from PIL import Image

BASE = Path(__file__).resolve().parents[1]
FRONT = BASE / 'frontend' / 'portable'


def test_all_four_user_competition_logos_are_usable_transparent_png():
    logos = ('premier-league', 'fa-cup', 'carabao-cup', 'champions-league')
    for logo in logos:
        file = FRONT / 'assets' / 'competitions' / (logo + '.png')
        assert file.exists() and file.stat().st_size > 1000
        with Image.open(file) as image:
            assert image.mode == 'RGBA' and image.width >= 150
            assert image.getchannel('A').getextrema() == (0, 255)


def test_shared_theme_is_loaded_before_both_consumers():
    html = (FRONT / 'index.html').read_text(encoding='utf-8')
    assert html.count('competition_branding.js') == 1
    assert html.count('competition_branding.css') == 1
    assert html.index('competition_branding.js') < html.index('competitions.js')
    assert html.index('competition_branding.js') < html.index('ui_home.js')
    assert html.index('competitions.css') < html.index('competition_branding.css')
    code = (FRONT / 'competition_branding.js').read_text(encoding='utf-8')
    for key in ('dev-premier', 'fa-cup', 'carabao-cup', 'champions-league'):
        assert "'" + key + "'" in code
    assert 'Object.freeze' in code and 'neutral' in code


def test_home_keeps_four_widgets_and_uses_actual_competition_ids():
    home = (FRONT / 'ui_home.js').read_text(encoding='utf-8')
    assert home.count('tsui-home-card tsui-') == 4
    assert 'first.competition_id' in home and 'f.competition_id' in home
    for key in ('competitionLabel(', 'brandStyle(', 'brandLogo(',
                'data-competition-brand', 'tsui-update-featured', 'state.news.stories'):
        assert key in home
    assert '/api/competitions/' in home
    assert 'window.FMCompetitionBranding' in home
    assert 'Sunderland' not in home


def test_cup_home_has_two_slots_without_fictitious_next_opponent():
    home = (FRONT / 'ui_home.js').read_text(encoding='utf-8')
    start = home.index('  function renderKnockout(')
    end = home.index('  function renderCompetitionBody(', start)
    code = home[start:end]
    assert 'tsui-mini-path' in code
    assert 'compactTie(active.tie,' in code
    assert 'Sorteo pendiente' in code
    assert 'rounds.slice(active.index+1)' in code
    assert 't.managed' in code
    assert 'slice(0,3)' not in code
    assert 'round.ties.filter(t=>!t.managed)' not in code
    # The only second real card requires a confirmed, explicit managed tie.
    assert 'confirmedNext?compactTie(' in code


def test_expanded_competition_uses_same_theme_and_doesnt_change_world():
    full = (FRONT / 'competitions.js').read_text(encoding='utf-8')
    assert 'window.FMCompetitionBranding' in full
    assert 'ciLogo(data.id' in full
    assert 'data-competition-brand' in full
    assert 'FMCompetitions' in full
    # TS-UI-01A.3.1 changes only how the read-only calendar reports the
    # canonical world competition ID. Comparing backend files to a developer's
    # absolute /mnt/data folder is not portable (and would reject this fix).
    calendar = (BASE / 'src/football_manager/ui_shell/calendar.py').read_text(encoding='utf-8')
    assert 'competition_id = scheduled.competition_id' in calendar
    assert 'world.result_for(scheduled.fixture_id)' in calendar
    for path in ('src/football_manager/ui_shell/competitions.py',
                 'src/football_manager/ui_shell/home_competition.py'):
        assert (BASE / path).is_file()
