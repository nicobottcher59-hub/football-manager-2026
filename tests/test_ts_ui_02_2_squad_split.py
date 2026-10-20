"""TS-UI-02.2 structural regressions (stdlib + pytest, no simulated matches)."""
from pathlib import Path
import json

ROOT = Path(__file__).resolve().parents[1]
SQUAD = ROOT / 'frontend/public/squad'
PORTABLE = ROOT / 'frontend/portable'


def read(relative):
    return (ROOT / relative).read_text(encoding='utf-8')


def test_split_view_is_loaded_after_the_original_roster():
    html = read('frontend/public/squad/embed.html')
    assert 'squad_ui02.css' in html and 'squad_ui02.js' in html
    assert html.index('roster.js') < html.index('squad_ui02.js') < html.index('squad.js')


def test_player_selection_and_full_profile_are_distinct():
    js = read('frontend/public/squad/squad_ui02.js')
    assert 'data-roster-expand=' in js
    assert 'data-open-career-player=' in js
    assert 's2-roster-row' in js and 's2-inspector' in js
    assert 'rt-table-wrap' not in js


def test_profile_has_four_sections_with_separate_contract_and_actions():
    js = read('frontend/public/squad/squad_ui02.js')
    for tab in ('Profile / Attributes', 'Season statistics', 'Status & development', 'Contract & actions'):
        assert tab in js
    assert 's2-contract-card' in js and 's2-actions-card' in js
    css = read('frontend/public/squad/squad_ui02.css')
    assert '.s2-management{display:grid' in css


def test_season_selector_supports_complete_season_and_real_competitions():
    js = read('frontend/public/squad/squad_ui02.js')
    assert 'All competitions' in js
    assert "state.competition='all'" in js
    assert 'data-s2-competition' in js
    assert 'season_stats' in js and 'opt.supported' in js
    assert 'data.stats_selection?.season' in js
    assert 'p.season_stats' in js


def test_management_controls_are_python_backed_or_existing_navigation():
    js = read('frontend/public/squad/squad_ui02.js')
    assert "action:'squad_number'" in js
    assert "action:'transfer_status'" in js
    assert 'data-open-finances' in js
    assert 'data-s2-navigate="Dressing Room"' in js
    assert 'Unsupported clauses and bonuses are not invented.' in js


def test_club_theme_comes_from_catalogue_not_sunderland_specific_code():
    js = read('frontend/public/squad/squad_ui02.js')
    assert "data.club_id" in js
    assert 'club-identities.json' in js
    assert 'entry.primary_color' in js and 'entry.hero_image' in js
    assert 'sunderland' not in js.lower()


def test_portraits_replace_by_player_id_and_keep_fallbacks():
    js = read('frontend/public/squad/squad_ui02.js')
    assert 'view.images[player.id]' in js
    assert 'FMPortraits?.portrait' in js
    assert 'safeAsset(photo)' in js
    catalogue = json.loads((SQUAD / 'data/player-portraits.json').read_text(encoding='utf-8'))
    assert catalogue['schema_version'] == 1
    assert catalogue['portraits'] == {}


def test_roster_and_inspector_keep_their_own_scroll():
    js = read('frontend/public/squad/squad.js')
    assert "$('.s2-list-scroll')?.scrollTop" in js
    assert "$('.s2-detail-scroll')?.scrollTop" in js
    assert 'data-s2-row' in js
    css = read('frontend/public/squad/squad_ui02.css')
    assert '.s2-list-scroll{min-height:0;overflow-y:auto' in css
    assert '.s2-detail-scroll{overflow:auto' in css
    assert '@media(max-width:1000px)' in css


def test_other_navigation_keeps_consistent_squad_theme():
    shell = read('frontend/portable/portable.js')
    assert 'fm-squad-open-section' in shell
    assert "'Medical Centre'" in shell and "'Training'" in shell
    css = read('frontend/portable/club_theme.css')
    assert 'body.tsui-squad-active .sidebar' in css
    assert '--ui-club-rgb' in css


def test_read_model_filters_only_scheduled_club_competitions():
    models = read('src/football_manager/ui_shell/models.py')
    assert 'fx.competition_id for fx in session._world.fixtures.values()' in models
    assert 'session.home_club.id in (fx.home_club_id, fx.away_club_id)' in models
    assert 'statistics_options(session._world_squads, session._world)' in models
