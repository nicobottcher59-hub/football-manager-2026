"""Real managed-match/day/save boundaries, not mocked success assertions."""
from __future__ import annotations
from copy import deepcopy
from datetime import date, timedelta
import gzip
import json
from pathlib import Path

import pytest

from football_manager.dev_ui import DevelopmentSession
from football_manager.persistence import SQLiteSaveRepository, load_manager_career, save_manager_career, SaveIntegrityError
from football_manager.persistence.manager_career import validate_manager_session
from football_manager.persistence.session_codec import capture_manager_graph, restore_manager_graph
from football_manager.ui_shell.dressing_room import dressing_room_read_model
from football_manager.ui_shell.progression import advance_day, simulate_until
from football_manager.ui_shell.application import GameApplication
from football_manager.ui_shell.runtime import UIRuntime
from football_manager.ui_shell.match import prematch_read_model
import football_manager.services.dressing_room as social

ROOT=Path(__file__).resolve().parents[1]

@pytest.fixture(scope='module')
def template():
    return DevelopmentSession()

@pytest.fixture
def session(template):
    return deepcopy(template)


def test_real_managed_result_updates_the_graph_exactly_once(session):
    fixture=session._active_match.fixture.fixture_id
    result=session.quick_simulate()
    assert list(session.dressing_room.processed_fixtures)==[fixture]
    stats={s.player_id:s.minutes for s in result.player_statistics if s.club_id==session.home_club.id}
    assert {p:m.appearances[-1].minutes for p,m in session.dressing_room.members.items()}=={p:stats.get(p,0) for p in session.dressing_room.members}
    before=deepcopy(session.dressing_room)
    with pytest.raises(RuntimeError):
        session.quick_simulate()
    assert session.dressing_room==before
    assert session._world.results[fixture].home_goals==result.home_goals


def test_social_failure_rolls_back_world_players_and_room(monkeypatch,session):
    before_room=deepcopy(session.dressing_room)
    before_players=[deepcopy(p.state) for p in session.home_club.squad.players]
    before_world=session._world.to_dict()
    before_seed=session._seed
    original=social.record_session_match
    def fail(*args,**kwargs):
        original(*args,**kwargs)
        raise RuntimeError('injected social commit failure')
    monkeypatch.setattr(social,'record_session_match',fail)
    with pytest.raises(RuntimeError,match='social commit'):
        session.quick_simulate()
    assert session.dressing_room==before_room
    assert [p.state for p in session.home_club.squad.players]==before_players
    assert session._world.to_dict()==before_world
    assert session._seed==before_seed and not session.match_played
    monkeypatch.setattr(social,'record_session_match',original)
    session.quick_simulate()
    assert len(session.dressing_room.processed_fixtures)==1


def test_daily_http_boundary_and_next_match_shortcut_keep_same_social_clock(session):
    session.quick_simulate()
    other=deepcopy(session)
    session.continue_to_next_match()
    while other.current_date<session.current_date:
        advance_day(other)
    assert session.dressing_room==other.dressing_room
    assert [p.state.dressing_room_morale for p in session.home_club.squad.players]==[p.state.dressing_room_morale for p in other.home_club.squad.players]


def test_failed_day_progression_does_not_publish_partial_social_state(session,tmp_path):
    session.quick_simulate()
    runtime=UIRuntime(session,SQLiteSaveRepository(tmp_path/'rollback.sqlite3'))
    before=dressing_room_read_model(session)
    def fail(s):
        advance_day(s)
        raise RuntimeError('injected after day')
    app=GameApplication(runtime,prematch_builder=prematch_read_model,advance_day_fn=fail)
    with pytest.raises(RuntimeError):
        app.command('progression.command',{'action':'advance_day'})
    assert runtime.session is session
    assert dressing_room_read_model(runtime.session)==before


def test_real_v3_save_migrates_without_retroactive_absences_or_tactic_loss():
    graph=json.loads(gzip.decompress((ROOT/'tests/fixtures/ts20/manager_v3_with_studio.json.gz').read_bytes()))
    assert graph['version']==3
    restored=restore_manager_graph(graph)
    validate_manager_session(restored)
    assert restored.tactical_studio.library
    assert next(iter(restored.tactical_studio.library.values())).name=='Legacy TS-19 tactic'
    assert not restored.dressing_room.processed_fixtures
    assert all(not m.appearances for m in restored.dressing_room.members.values())
    assert all(p.state.dressing_room_morale==0 for p in restored.home_club.squad.players)
    assert restored.last_result is None  # Fixture had already been continued.
    from football_manager.persistence.session_codec import GRAPH_VERSION
    assert capture_manager_graph(restored)['version']==GRAPH_VERSION
    assert restored.home_lineup.starting_players[0] is restored.home_club.squad.get(restored.home_lineup.starting_players[0].id)


def test_actual_v2_save_also_gets_neutral_social_baseline():
    graph=json.loads(gzip.decompress((ROOT/'tests/fixtures/ts19/manager_v2_with_result.json.gz').read_bytes()))
    restored=restore_manager_graph(graph)
    validate_manager_session(restored)
    assert restored.last_result is not None
    assert not restored.dressing_room.processed_fixtures
    assert restored.dressing_room.last_updated==restored.current_date


def test_sqlite_roundtrip_preserves_hidden_personality_graph_and_continuation(session,tmp_path):
    simulate_until(session,date(2026,9,5))
    repository=SQLiteSaveRepository(tmp_path/'career.sqlite3')
    save_manager_career(repository,slot_id='ts20',display_name='TS-20',expected_revision=0,session=session)
    loaded=load_manager_career(repository,'ts20').session
    assert loaded.dressing_room==session.dressing_room
    assert [p.personality for p in loaded.home_club.squad.players]==[p.personality for p in session.home_club.squad.players]
    assert dressing_room_read_model(loaded)==dressing_room_read_model(session)
    for instance in (session,loaded):
        simulate_until(instance,date(2026,9,20))
    assert loaded._world.to_dict()==session._world.to_dict()
    assert loaded.dressing_room==session.dressing_room
    assert [p.state for p in loaded.home_club.squad.players]==[p.state for p in session.home_club.squad.players]


@pytest.mark.parametrize('class_name,field',[
    ('football_manager.domain.player:Player','personality'),
    ('football_manager.domain.player_state:PlayerState','dressing_room_morale'),
    ('football_manager.domain.dressing_room:DressingRoomState','links'),
])
def test_current_save_cannot_silently_default_missing_social_fields(session,class_name,field):
    graph=capture_manager_graph(session)
    node=next(n for n in graph['nodes'] if n.get('class')==class_name)
    del node['fields'][field]
    with pytest.raises(SaveIntegrityError):
        restore_manager_graph(graph)


@pytest.mark.parametrize('field,bad',[
    ('integration',float('nan')),('influence',101),('departure_disruption',5),('tier','invented'),
])
def test_corrupt_social_data_is_rejected(session,field,bad):
    graph=capture_manager_graph(session)
    member=next(n for n in graph['nodes'] if n.get('class')=='football_manager.domain.dressing_room:SocialMember')
    member['fields'][field]=bad
    with pytest.raises(SaveIntegrityError):
        validate_manager_session(restore_manager_graph(graph))


def test_invalid_personality_cannot_be_saved(session,tmp_path):
    player=session.home_club.squad.players[0]
    object.__setattr__(player.personality,'professionalism',101)
    with pytest.raises(SaveIntegrityError):
        save_manager_career(SQLiteSaveRepository(tmp_path/'bad.sqlite3'),slot_id='bad',display_name='Bad',expected_revision=0,session=session)


def test_real_season_transition_preserves_people_and_advances_room(session,tmp_path):
    personalities={p.id:p.personality for p in session.home_club.squad.players}
    start=session.dressing_room.started_on
    count=session.simulate_remaining_season()
    assert count>30
    assert session.dressing_room.last_updated==session.current_date
    appearances_before=len(session.dressing_room.processed_fixtures)
    session.begin_next_season()
    assert session.dressing_room.started_on==start
    assert session.dressing_room.last_updated==session.current_date
    assert len(session.dressing_room.processed_fixtures)==appearances_before
    assert {p.id:p.personality for p in session.home_club.squad.players}==personalities
    validate_manager_session(session)
    repository=SQLiteSaveRepository(tmp_path/'next-season.sqlite3')
    save_manager_career(repository,slot_id='season',display_name='Season',expected_revision=0,session=session)
    loaded=load_manager_career(repository,'season').session
    assert loaded.dressing_room==session.dressing_room


def test_results_only_rewind_does_not_keep_future_social_history(session,tmp_path):
    path=tmp_path/'world.json'
    session.save_world(path)
    simulate_until(session,date(2026,9,3))
    assert session.dressing_room.processed_fixtures
    session.load_world(path)
    assert session.dressing_room.last_updated==session.current_date
    assert not session.dressing_room.processed_fixtures
    assert all(p.state.dressing_room_morale==0 for p in session.home_club.squad.players)
