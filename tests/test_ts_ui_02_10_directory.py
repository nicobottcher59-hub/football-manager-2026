"""TS-UI-02.10: directory hierarchy, real data, and no added CSS cascade."""
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
UI = ROOT / 'frontend/public/squad'
JS = (UI / 'squad_ui02.js').read_text(encoding='utf-8')
CSS = (UI / 'squad_ui029.css').read_text(encoding='utf-8')
HTML = (UI / 'embed.html').read_text(encoding='utf-8')
ROW = JS.split('function rosterRow(p,data){', 1)[1].split('function rosterContents(data){', 1)[0]
DIRECTORY = JS.split('function roster(data){', 1)[1].split('function kitGraphic', 1)[0]


def test_existing_module_was_updated_instead_of_adding_another_stylesheet():
    assert 'squad_ui0210.css' not in HTML
    assert HTML.index('squad_ui028.css') < HTML.index('squad_ui029.css')
    assert 'TS-UI-02.10' in CSS


def test_cards_have_three_real_regions_and_an_accessible_action():
    assert 's210-portrait' in ROW
    assert 's210-identity' in ROW
    assert 's210-rating' in ROW
    assert ROW.index('s210-portrait') < ROW.index('s210-identity') < ROW.index('s210-rating')
    assert 'role="row"' in ROW and 'aria-selected=' in ROW
    assert 'data-roster-expand=' in ROW and 'data-open-career-player=' in ROW


def test_every_presented_metric_is_recorded_by_python():
    for key in ('p.name', 'p.number', 'p.age', 'p.primary_position', 'p.nationality',
                'p.condition', 'p.morale', 'p.form', 'p.act'):
        if key == 'p.nationality':
            assert 'nation(p)' in ROW
        else:
            assert key in ROW
    assert "p.number==null?" in ROW
    assert "numeric(p.form)?" in ROW
    assert "numeric(p.condition)?" in ROW
    assert "mood==null?'—'" in ROW
    assert "p.available?'':'is-unavailable'" in ROW


def test_captain_ribbon_uses_effective_read_model_only():
    assert "data?.set_pieces?.roles?.find(entry=>entry.role==='captain')" in JS
    assert 'captain.effective_id===player.id' in JS
    assert 'captainBadge(p,data)' in ROW
    assert '.s210-name-line .s25-captain' in CSS
    assert 'clip-path:polygon(' in CSS
    assert 'vice_captain' not in ROW


def test_directory_filters_and_new_condition_sort_preserve_prior_sort_modes():
    assert "['position','Position']" in DIRECTORY
    assert "['grl','GRL']" in DIRECTORY
    assert "['condition','Condition']" in DIRECTORY
    assert "['name','Name']" in DIRECTORY
    assert "view.order==='condition'" in JS
    assert 'data-s2-search' in DIRECTORY and 'data-s2-sort' in DIRECTORY
    assert 'data-s25-list-count' in DIRECTORY
    assert 'function updateRosterList(resetScroll=false)' in JS


def test_theme_not_special_cased_for_one_club():
    assert 'var(--s2-club-primary)' in CSS
    assert 'rgba(var(--s2-club-rgb)' in CSS
    assert 'var(--s2-club-accent)' in CSS
    assert 'sunderland' not in ROW.lower()
    assert 'brighton' not in ROW.lower()
    assert 'view.identities[id]' in JS


def test_media_queries_and_keyboard_access_kept():
    assert '@media(max-width:1500px)' in CSS
    assert '@media(max-width:1350px)' in CSS
    assert '@media(max-width:1000px)' in CSS
    assert '@media(max-width:560px)' in CSS
    assert '@media(prefers-reduced-motion:reduce)' in CSS
    assert 'tabindex="0"' in ROW
    controller = (UI / 'squad.js').read_text(encoding='utf-8')
    assert "['Enter',' '].includes(event.key)" in controller
    assert 'data-s2-row' in controller
