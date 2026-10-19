"""UI-3.4.1 hotfix: club-only visible feed and integrated confirmation."""
from __future__ import annotations

from datetime import date
from pathlib import Path

from football_manager.dev_ui.session import DevelopmentSession
from football_manager.ui_shell.progression import simulate_until


ROOT = Path(__file__).resolve().parents[1] / "frontend" / "portable"


def test_simulation_feed_uses_managed_ledger_flag_and_keeps_background_world():
    session = DevelopmentSession()
    collected = []
    before = set(session._world.results)
    outcome = simulate_until(session, date(2026, 8, 31),
                             on_day=lambda _day, events: collected.extend(events))
    managed = [event for event in collected if event["managed"]]
    background = [event for event in collected if not event["managed"]]
    assert managed and background
    assert len(managed) == outcome["managed_matches"]
    assert len(background) == outcome["background_matches"]
    assert len(collected) == len(session._world.results.keys() - before)
    for event in collected:
        fixture = session._world.fixtures[event["id"]]
        expected_managed = session.home_club.id in (fixture.home_club_id, fixture.away_club_id)
        assert event["managed"] is expected_managed


def test_calendar_uses_custom_confirmation_and_accurate_known_fixture_preview():
    calendar = (ROOT / 'calendar.js').read_text(encoding='utf-8')
    simulation = (ROOT / 'simulation.js').read_text(encoding='utf-8')
    style = (ROOT / 'simulation.css').read_text(encoding='utf-8')
    assert 'window.confirm(' not in calendar
    assert 'window.FMSimulationOverlay.confirm({target,fromDate:today(),knownMatches})' in calendar
    assert 'game.date>=today()&&game.date<=target&&!game.score' in calendar
    assert 'fm-sim-confirm-dialog' in simulation and 'fm-sim-confirm-accept' in simulation
    assert 'fm-sim-confirm-backdrop' in style
    assert 'if(!accepted || simulating || target<today())return;' in calendar


def test_only_managed_matches_render_and_cursor_still_pages_all_results():
    simulation = (ROOT / 'simulation.js').read_text(encoding='utf-8')
    assert "queue.push(...payload.events.filter(item => item.type==='result' && item.managed===true))" in simulation
    assert "if(item.type!=='result' || item.managed!==true) return;" in simulation
    assert 'cursor=payload.next_cursor' in simulation
    assert 'YOUR MATCHES SHOWN' in simulation
    assert 'Other clubs were simulated in the background' in simulation
    assert 'fm-sim-results-count' not in simulation
