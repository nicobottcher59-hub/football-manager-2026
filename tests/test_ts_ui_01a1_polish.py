"""TS-UI-01A.1: real opponent form + visual calendar integration."""
from __future__ import annotations

from datetime import date, datetime, timezone
from pathlib import Path
from types import SimpleNamespace

from football_manager.domain.world_runner import WorldMatchResult
from football_manager.dev_ui.session import DevelopmentSession
from football_manager.ui_shell.calendar import _latest_opponent_form, calendar_read_model

FRONT = Path(__file__).resolve().parents[1] / "frontend" / "portable"


def sample_world(entries):
    """Fixture-result pairs, no external season data or fabricated projections."""
    world = SimpleNamespace(results={}, fixtures={})
    for i, (day, home, away, hs, aws, pens) in enumerate(entries):
        fid = f"played-{i}"
        world.fixtures[fid] = SimpleNamespace(
            home_club_id=home, away_club_id=away,
            kickoff=datetime.fromisoformat(day + 'T15:00:00+00:00'),
        )
        world.results[fid] = WorldMatchResult(fid, hs, aws, *pens)
    return world


def test_opponent_form_uses_last_five_confirmed_results_and_correct_viewpoint():
    world = sample_world([
        ('2026-08-01', 'rival', 'a', 2, 1, (0, 0)),
        ('2026-08-02', 'b', 'rival', 0, 0, (0, 0)),
        ('2026-08-03', 'rival', 'c', 0, 1, (0, 0)),
        ('2026-08-04', 'd', 'rival', 3, 2, (0, 0)),
        ('2026-08-05', 'rival', 'e', 5, 0, (0, 0)),
        ('2026-08-06', 'rival', 'f', 3, 3, (4, 2)),
        ('2026-08-07', 'g', 'rival', 1, 1, (1, 2)),
        ('2026-08-08', 'rival', 'h', 0, 10, (0, 0)),  # Recorded but in future
    ])
    form = _latest_opponent_form(world, {'rival', 'a', 'nonexistent'}, date(2026, 8, 7))
    assert form['rival'] == ['D', 'D', 'V', 'V', 'V']
    assert form['a'] == ['D']
    assert form['nonexistent'] == []
    assert len(form['rival']) == 5


def test_opponent_form_shootout_and_no_fake_scores():
    world = sample_world([
        ('2026-08-01', 'home', 'away', 1, 1, (4, 3)),
        ('2026-08-02', 'other', 'away', 0, 0, (0, 0)),
    ])
    assert _latest_opponent_form(world, {'home', 'away'}, date(2026, 8, 2)) == {
        'home': ['V'], 'away': ['D', 'E'],
    }
    assert _latest_opponent_form(world, {'away'}, date(2026, 7, 31)) == {'away': []}
    assert _latest_opponent_form(world, set(), date(2026, 8, 2)) == {}


def test_calendar_serializes_opponent_id_and_form_without_new_game_state():
    session = DevelopmentSession()
    result_count = len(session._world.results)
    result = calendar_read_model(session)
    next_five = [m for m in result['matches'] if not m['score'] and m['date'] >= result['date']][:5]
    assert len(next_five) == 5
    assert all(isinstance(g['opponent_form'], list) and len(g['opponent_form']) <= 5 for g in next_five)
    assert all(set(g['opponent_form']) <= {'V', 'E', 'D'} for g in next_five)
    assert len(session._world.results) == result_count
    assert session.home_club.id == 'northbridge'


def test_home_remains_four_cards_and_has_featured_match_and_live_forms():
    js = (FRONT / 'ui_home.js').read_text(encoding='utf-8')
    css = (FRONT / 'ui_home.css').read_text(encoding='utf-8')
    assert js.count('tsui-home-card tsui-') == 4
    for text in ('tsui-featured-fixture', 'tsui-opponent-form', 'f.opponent_form',
                 'FORMA DEL RIVAL', 'tsui-fixture-row', 'tsui-hero-results'):
        assert text in js
    assert 'tsui-featured-fixture' in css
    assert 'tsui-featured-team' in css
    assert 'tsui-home-card' in css
    assert 'data-tsui-route="Calendar"' in js
    assert 'Sunderland' not in js and 'Sunderland' not in css
