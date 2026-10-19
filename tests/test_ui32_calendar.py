"""UI-3.2: the calendar is a read-only view of the canonical Python world."""
from __future__ import annotations

import json
from pathlib import Path
from threading import Thread
from types import SimpleNamespace
from urllib.request import urlopen

from football_manager.dev_ui.session import DevelopmentSession
from football_manager.domain.world_runner import WorldMatchResult
from football_manager.ui_shell.calendar import _aggregate_for_fixture, calendar_read_model
from football_manager.ui_shell.server import create_server

ROOT = Path(__file__).resolve().parents[1]


def test_calendar_matches_exact_managed_schedule_and_officially_unknown_draws_omitted():
    session = DevelopmentSession()
    exported = calendar_read_model(session)
    known = session._season_calendar.fixtures_for_club(session.home_club.id)
    assert exported['source'] == 'python-development-session'
    assert exported['date'] == session.current_date.isoformat()
    assert exported['persistent'] is False
    assert exported['timezone'] == 'UTC'
    assert len(exported['matches']) == len(known)
    assert {game['id'] for game in exported['matches']} == {x.fixture_id for x in known}
    assert [game['date'] for game in exported['matches']] == sorted(game['date'] for game in exported['matches'])
    for game in exported['matches']:
        real = next(item for item in known if item.fixture_id == game['id'])
        scheduled = session._managed_schedule[game['id']]
        assert game['date'] == real.match_date.isoformat()
        assert game['kickoff'] == real.kickoff.isoformat()
        assert game['competition'] == scheduled.competition_name
        assert game['source'] == real.source.value
        assert game['status'] == real.status.value
        assert game['home'] == (scheduled.fixture.home_club_id == session.home_club.id)
        assert game['opponent'] in (game['home_club'], game['away_club'])
        assert game['score'] is None
        assert game['penalties'] is None
        assert game['outcome'] is None
    assert all('TBD' not in game['opponent'] and 'if qualified' not in game['opponent'] for game in exported['matches'])
    assert 'Premier League' in {game['competition'] for game in exported['matches']}
    assert 'Carabao Cup' in {game['competition'] for game in exported['matches']}
    assert 'UEFA Champions League' in {game['competition'] for game in exported['matches']}
    assert 'FA Cup' not in {game['competition'] for game in exported['matches']}  # not drawn yet


def test_calendar_uses_managed_result_score_from_world_not_fixture_date():
    session = DevelopmentSession()
    first = calendar_read_model(session)['matches'][0]
    session._world.record_result(first['id'], 2, 1, resolver='managed')
    updated = next(game for game in calendar_read_model(session)['matches'] if game['id'] == first['id'])
    assert updated['score'] == {'home': 2, 'away': 1}
    assert updated['outcome'] == 'V'
    assert updated['penalties'] is None
    assert updated['aggregate'] is None
    # Read-only: no change to the managed player's session current date.
    assert session.current_date.isoformat() == first['date']


def test_penalty_results_override_draw_and_two_leg_aggregate_is_separate():
    session = DevelopmentSession()
    carabao = next(g for g in calendar_read_model(session)['matches'] if g['competition_id'] == 'carabao-cup')
    session._world.record_result(carabao['id'], 1, 1, penalties_home=3, penalties_away=4, resolver='managed')
    played = next(g for g in calendar_read_model(session)['matches'] if g['id'] == carabao['id'])
    assert played['score'] == {'home': 1, 'away': 1}
    assert played['penalties'] == {'home': 3, 'away': 4}
    assert played['outcome'] == 'D'  # Lost shootout despite drawn match score.
    assert played['aggregate'] is None  # Single-legged tie: never mislabel as aggregate.

    # Separate actual two-legged domain resolver: lose a leg but qualify overall.
    leg1 = SimpleNamespace(fixture_id='leg1',leg_number=1,home_club_id='northbridge',away_club_id='guest')
    leg2 = SimpleNamespace(fixture_id='leg2',leg_number=2,home_club_id='guest',away_club_id='northbridge')
    from football_manager.domain.knockout import KnockoutTie
    tie = KnockoutTie('tie1','semi','northbridge','guest',(leg1,leg2))
    plan = SimpleNamespace(tie_for_fixture=lambda _: tie)
    world = SimpleNamespace(cups={'cup':SimpleNamespace(plan_for_fixture=lambda _: plan)},staged={},
        result_for={'leg1':WorldMatchResult('leg1',2,0),'leg2':WorldMatchResult('leg2',1,0)}.get)
    aggregate = _aggregate_for_fixture(SimpleNamespace(_world=world),'leg2','cup','semi','northbridge')
    assert aggregate == {
        'managed_goals': 2, 'opponent_goals': 1, 'complete': True,
        'qualified': True, 'decided_by_penalties': False,
    }


def test_calendar_api_and_static_assets_are_available_without_node():
    server = create_server(port=0)
    thread = Thread(target=server.serve_forever,daemon=True)
    thread.start()
    url=f'http://127.0.0.1:{server.server_port}'
    try:
        with urlopen(url+'/api/calendar',timeout=10) as res:
            assert res.status==200
            data=json.load(res)
        assert data['matches'] and data['date']=='2026-08-21'
        with urlopen(url+'/api/squad',timeout=10) as res:
            roster=json.load(res)
        assert roster['date']==data['date']
        assert roster['club']==data['club']
        for name,expect in [('/portable/calendar.js','FMCalendar'),('/portable/calendar.css','cal-fixture'),('/portable/portable.js','calendarPanel'),('/portable/index.html','calendar.js')]:
            with urlopen(url+name,timeout=10) as res:
                assert res.status==200
                assert expect.encode() in res.read()
    finally:
        server.shutdown(); server.server_close(); thread.join(timeout=5)


def test_position_sort_js_covers_real_python_position_codes():
    domain = ROOT / 'src/football_manager/domain/enums.py'
    ui = ROOT / 'frontend/public/squad/roster.js'
    source = ui.read_text(encoding='utf-8')
    assert 'POSITION_ORDER' in source and 'positionRank(x)-positionRank(y)' in source
    assert 'key===\'position\'||key===\'primary_position\'' in source
    from football_manager.domain.enums import Position
    assert all(p.value in source for p in Position)
