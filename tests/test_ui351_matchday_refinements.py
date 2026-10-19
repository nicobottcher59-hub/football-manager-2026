"""UI-3.5.1: design controls reuse existing match-only squad commands."""
from pathlib import Path

from football_manager.dev_ui.session import DevelopmentSession
from football_manager.ui_shell.match import prematch_read_model
from football_manager.ui_shell.models import UIRosterAdmin


PORTABLE = Path('frontend/portable')


def test_match_tactics_can_swap_starters_without_touching_base_lineup():
    session = DevelopmentSession()
    admin = UIRosterAdmin()
    start = prematch_read_model(session, admin)
    original = {entry.slot_id: entry.player.id for entry in session.home_lineup.starters}
    first, second = start['managed']['starters'][:2]
    preview = prematch_read_model(session, admin, [
        {'action': 'swap_starters', 'first': first['slot_id'], 'second': second['slot_id']}
    ])
    by_slot = {p['slot_id']: p['id'] for p in preview['managed']['starters']}
    assert by_slot[first['slot_id']] == second['id']
    assert by_slot[second['slot_id']] == first['id']
    assert {entry.slot_id: entry.player.id for entry in session.home_lineup.starters} == original


def test_match_tactics_can_replace_starter_with_bench_without_touching_base():
    session = DevelopmentSession()
    admin = UIRosterAdmin()
    original = prematch_read_model(session, admin)
    outgoing = original['managed']['starters'][0]
    incoming = original['managed']['bench'][0]
    preview = prematch_read_model(session, admin, [
        {'action': 'swap_bench', 'starter_id': outgoing['id'], 'bench_id': incoming['id']}
    ])
    assert incoming['id'] in {p['id'] for p in preview['managed']['starters']}
    assert outgoing['id'] in {p['id'] for p in preview['managed']['bench']}
    assert outgoing['id'] in {p['id'] for p in original['managed']['starters']}
    assert outgoing['id'] in {e.player.id for e in session.home_lineup.starters}
    assert incoming['id'] in {p.id for p in session.home_lineup.bench}


def test_drag_and_drop_uses_existing_match_only_commands_with_click_fallback():
    js = (PORTABLE / 'match.js').read_text(encoding='utf-8')
    css = (PORTABLE / 'match.css').read_text(encoding='utf-8')
    assert 'draggable="true"' in js
    assert 'data-drag-kind="starter"' in js and 'data-drag-kind="bench"' in js
    assert all(f"'{evt}'" in js for evt in ('dragstart', 'dragover', 'drop', 'dragend'))
    assert "action:'swap_bench'" in js and "action:'swap_starters'" in js
    assert 'selectedBenchId' in js and 'Click a shirt on the pitch' in js
    assert 'fm-match-bench-grid' in js and css
    assert 'fm-swap-fallback' in js  # keyboard/touch-friendly dropdowns retained
    assert 'mode=\'tactics\'' in js


def test_kit_preview_and_match_timeline_do_not_fabricate_sporting_events():
    js = (PORTABLE / 'match.js').read_text(encoding='utf-8')
    assert 'fm-kit-swatches' in js and 'fm-kit-hero-jersey' in js
    assert 'fm-kit-contrast' in js and 'draftKits' in js
    assert "action:'match_kits'" in js
    assert 'Weather and referee: decorative DEV data' not in js
    assert 'fm-event-icon' in js and 'fm-event-copy' in js
    assert 'fm-home-lane' in js and 'fm-away-lane' in js
    assert 'eventSymbol(e)' in js
    assert '/api/match' in js  # no second match simulator in browser
