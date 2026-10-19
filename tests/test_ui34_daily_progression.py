"""UI-3.4: manual day, match-day hold and Calendar auto-sim through own fixtures."""
from datetime import date, timedelta
from pathlib import Path
from unittest.mock import patch
from threading import Thread
from urllib.error import HTTPError
from urllib.request import Request, urlopen
import json
import pytest

from football_manager.dev_ui.session import DevelopmentSession
from football_manager.ui_shell.progression import advance_day, progression_read_model, simulate_until
from football_manager.ui_shell.calendar import calendar_read_model
from football_manager.ui_shell.competitions import competition_options
from football_manager.ui_shell.server import create_server


def test_matchday_go_to_match_has_no_side_effects_and_manual_advance_holds():
    session=DevelopmentSession()
    initial=progression_read_model(session)
    assert initial['date']=='2026-08-21'
    assert initial['button_label']=='Go to Match'
    assert initial['match_day'] and initial['match_screen_supported']
    fixture=initial['pending_match']['id']
    assert session._world.result_for(fixture) is None
    with pytest.raises(ValueError,match='Go to Match'):
        advance_day(session)
    assert session.current_date==date(2026,8,21)
    assert session._world.result_for(fixture) is None


def test_calendar_can_auto_simulate_managed_match_on_current_day_and_resume_daily():
    session=DevelopmentSession()
    first=progression_read_model(session)['pending_match']['id']
    progress=simulate_until(session,date(2026,8,21))
    assert progress['managed_matches']==1
    assert progress['background_matches']>=0
    assert session._world.result_for(first).resolver=='managed'
    assert progress['state']['button_label']=='Continue'
    assert calendar_read_model(session)['matches'][0]['score'] is not None
    following=advance_day(session)
    assert following['from_date']=='2026-08-21'
    assert following['to_date']=='2026-08-22'
    assert session.current_date==date(2026,8,22)
    assert session._world.result_for(first) is not None
    assert following['managed_matches']==0


def test_manual_continue_advances_one_day_and_stops_on_next_match():
    session=DevelopmentSession()
    simulate_until(session,session.current_date)
    next_game=progression_read_model(session)['pending_match']
    assert next_game['date'] > '2026-08-21'
    while session.current_date < date.fromisoformat(next_game['date']):
        before=session.current_date
        step=advance_day(session)
        assert session.current_date==before+timedelta(days=1)
        assert step['managed_matches']==0
    assert progression_read_model(session)['button_label']=='Go to Match'
    assert session._world.result_for(next_game['id']) is None
    with pytest.raises(ValueError,match='Go to Match'):
        advance_day(session)


def test_calendar_skip_crosses_own_games_and_updates_world_and_player_condition():
    session=DevelopmentSession()
    first=session.home_lineup.starting_players[0]
    initial_minutes=first.positional_familiarity.total_minutes if hasattr(first.positional_familiarity,'total_minutes') else None
    original_date=session.current_date
    progress=simulate_until(session,date(2026,12,31))
    assert (progress['managed_matches']>=15 and progress['background_matches']>100)
    assert session.current_date==date(2026,12,31)
    assert len(progress['auto_results'])==progress['managed_matches']
    managed_results={r.fixture_id for r in session._world.results.values() if r.resolver=='managed'}
    assert len(managed_results)==progress['managed_matches']
    assert len(session._world.results)==len({*session._world.results})
    assert progression_read_model(session)['pending_match']['date']>'2026-12-31'
    assert competition_options(session)['competitions']
    assert session.current_date > original_date
    if initial_minutes is not None:
        assert first.positional_familiarity.total_minutes >= initial_minutes


def test_all_season_games_resolve_without_duplicate_results_or_tbd():
    session=DevelopmentSession()
    progress=simulate_until(session,date(2027,6,30))
    assert progress['managed_matches'] > 40
    assert len(session._world.results)==len(session._world.fixtures)==2959
    assert session.season_finished is True
    assert progress['state']['season_complete'] is True
    assert all(g['status']=='played' for g in calendar_read_model(session)['matches'])
    assert len({r['id'] for r in progress['auto_results']})==progress['managed_matches']


def test_reject_past_and_outside_season_dates_without_mutation():
    session=DevelopmentSession()
    for invalid in (date(2026,8,14),date(2027,7,1)):
        with pytest.raises(ValueError): simulate_until(session,invalid)
        assert session.current_date==date(2026,8,21)
    with pytest.raises(ValueError):simulate_until(session,'2026-08-21')


def test_http_api_world_mutations_are_transactional_on_failure_and_matchday_hold():
    server=create_server(port=0)
    worker=Thread(target=server.serve_forever,daemon=True)
    worker.start()
    base=f'http://127.0.0.1:{server.server_port}'
    def get(path):
        with urlopen(base+path,timeout=20) as r:return json.load(r)
    def post(action,**kwargs):
        body=json.dumps({'action':action,**kwargs}).encode()
        request=Request(base+'/api/progression',data=body,method='POST',headers={'Content-Type':'application/json'})
        with urlopen(request,timeout=20) as r:return json.load(r)
    try:
        current=get('/api/progression')
        assert current['button_label']=='Go to Match'
        first=current['pending_match']['id']
        original_count=len(server.RequestHandlerClass.runtime.session._world.results)
        with pytest.raises(HTTPError) as ex:post('advance_day')
        assert ex.value.code==400
        assert get('/api/progression')['date']=='2026-08-21'
        with pytest.raises(HTTPError) as ex:post('simulate_until',date='2026-07-20')
        assert ex.value.code==400
        with pytest.raises(HTTPError) as ex:post('simulate_until',date='not-a-date')
        assert ex.value.code==400
        assert len(server.RequestHandlerClass.runtime.session._world.results)==original_count
        response=post('simulate_until',date='2026-08-22')
        assert response['managed_matches']>=1
        assert response['state']['date']=='2026-08-22'
        assert response['state']['button_label']=='Continue'
        assert get('/api/calendar')['date']=='2026-08-22'
        assert any(g['id']==first and g['score'] is not None for g in get('/api/calendar')['matches'])
        assert get('/api/competitions')['schema_version']==2
    finally:
        server.shutdown();server.server_close();worker.join(timeout=5)


def test_frontend_uses_single_authoritative_progression_api_and_day_selection():
    root=Path(__file__).resolve().parents[1]
    shell=(root/'frontend/portable/portable.js').read_text(encoding='utf-8')
    cal=(root/'frontend/portable/calendar.js').read_text(encoding='utf-8')
    css=(root/'frontend/portable/calendar.css').read_text(encoding='utf-8')
    assert "fetch('/api/progression'" in shell
    assert "submitProgression('advance_day')" in shell
    assert 'window.FMProgression' in shell
    assert 'match_screen_supported' in (root/'src/football_manager/ui_shell/progression.py').read_text(encoding='utf-8')
    assert 'data-cal-date' in cal and 'data-cal-simulate' in cal
    assert 'window.FMProgression.simulateUntil' in cal
    assert '.cal-sim-card' in css


def test_failed_internal_progression_does_not_commit_partial_world_to_http_runtime():
    server=create_server(port=0)
    worker=Thread(target=server.serve_forever,daemon=True);worker.start()
    base=f'http://127.0.0.1:{server.server_port}'
    runtime=server.RequestHandlerClass.runtime
    original=runtime.session
    original_results=set(original._world.results)
    def fail_midway(tentative,target):
        tentative.current_date=date(2026,8,30)
        tentative._world.results.clear()
        raise RuntimeError('forced scheduling failure')
    try:
        body=json.dumps({'action':'simulate_until','date':'2026-08-30'}).encode()
        request=Request(base+'/api/progression',data=body,method='POST',headers={'Content-Type':'application/json'})
        with patch('football_manager.ui_shell.server.simulate_until',side_effect=fail_midway):
            with pytest.raises(HTTPError) as exc:urlopen(request,timeout=20)
            assert exc.value.code==409
        assert runtime.session is original
        assert runtime.session.current_date==date(2026,8,21)
        assert set(runtime.session._world.results)==original_results
    finally:
        server.shutdown();server.server_close();worker.join(timeout=5)
