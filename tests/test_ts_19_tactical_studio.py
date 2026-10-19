"""TS-19 domain, persistence and atomic editor commands. Python-only tests."""
from __future__ import annotations
from copy import deepcopy
import gzip
import json
from pathlib import Path
import pytest
from football_manager.dev_ui.session import DevelopmentSession
from football_manager.dev_ui.formations import development_formations
from football_manager.domain.enums import Position
from football_manager.domain.roles import get_role
from football_manager.domain.tactical_shapes import PhaseShape, SlotPoint, phase_target
from football_manager.domain.tactical_studio import PlanRule
from football_manager.domain.tactical_geometry import phase_points
from football_manager.fast_simulation import FastMatchSimulator
from football_manager.persistence import SQLiteSaveRepository, save_manager_career, load_manager_career, SaveIntegrityError
from football_manager.persistence.manager_career import validate_manager_session
from football_manager.persistence.session_codec import capture_manager_graph, restore_manager_graph, GRAPH_VERSION
from football_manager.services.tactical_studio import same_tactic
from football_manager.ui_shell.models import UIRosterAdmin, squad_read_model
from football_manager.ui_shell.transactions import apply_squad_command_atomically
ROOT = Path(__file__).resolve().parents[1]

@pytest.fixture
def session():
    return DevelopmentSession()

def command(session, action, **kwargs):
    return apply_squad_command_atomically(session, {'action': action, **kwargs}, UIRosterAdmin())

def save(session, name):
    command(session, 'studio_save', name=name)
    return session.tactical_studio.active_id

def ratings(session):
    return {p.player_id: (p.overall_rating, p.current_rating) for p in session._build_snapshot().home_team.starters}

def test_drag_changes_only_requested_phase_not_roster_role_or_ratings(session):
    tactic = deepcopy(session.home_tactic)
    lineup, original = session.home_lineup, ratings(session)
    original_off = phase_points(tactic, 'out_of_possession')
    view = command(session, 'studio_point', slot_id='lb', phase='in_possession', x=33, y=28)
    assert session.home_lineup is lineup
    assert session.home_tactic.role_assignments == tactic.role_assignments
    assert ratings(session) == original
    assert phase_points(session.home_tactic, 'in_possession')['lb'] == (.33, .28)
    assert phase_points(session.home_tactic, 'out_of_possession') == original_off
    assert view['studio']['anchors']['in_possession']['lb'] == {'x': 33, 'y': 28}
    snapshot = session._build_snapshot()
    assert phase_target(snapshot.home_team.tactic.phase_shapes, 'in_possession', 'lb') == SlotPoint('lb', .33, .28)

@pytest.mark.parametrize('value', [float('nan'), float('inf'), -1, 0, 3.99, 96.01, 100, True, '40', None])
def test_invalid_drag_is_atomic_and_does_not_advance_revision(session, value):
    before = squad_read_model(session)
    tactic, lineup = session.home_tactic, session.home_lineup
    with pytest.raises((ValueError, TypeError)):
        command(session, 'studio_point', slot_id='lb', phase='in_possession', x=value, y=40)
    assert session.home_tactic is tactic and session.home_lineup is lineup
    assert squad_read_model(session) == before

@pytest.mark.parametrize('extra', [{'phase':'transition'}, {'slot_id':'missing'}, {'expected_revision':-1}, {'expected_revision':True}, {'slot_id':['lb']}])
def test_invalid_context_or_stale_revision_rejects_whole_edit(session, extra):
    data = {'slot_id':'lb', 'phase':'in_possession', 'x':25, 'y':30, **extra}
    before = squad_read_model(session)
    with pytest.raises((ValueError, TypeError, KeyError)):
        command(session, 'studio_point', **data)
    assert squad_read_model(session) == before

def test_reset_restores_automatic_phase_and_copy_is_independent(session):
    automatic = phase_points(session.home_tactic, 'in_possession')
    command(session, 'studio_point', slot_id='rb', phase='in_possession', x=65, y=25)
    goalkeeper_before = phase_points(session.home_tactic,'out_of_possession')['gk']
    points = [{'slot_id':k, 'x':x*100, 'y':y*100} for k,(x,y) in phase_points(session.home_tactic,'in_possession').items() if k!='gk']
    command(session, 'studio_shape', phase='out_of_possession', points=points)
    assert all(phase_points(session.home_tactic,'out_of_possession')[key] == pytest.approx(point) for key,point in phase_points(session.home_tactic,'in_possession').items() if key!='gk')
    assert phase_points(session.home_tactic,'out_of_possession')['gk']==goalkeeper_before
    command(session, 'studio_point', slot_id='rb', phase='in_possession', reset=True)
    assert phase_points(session.home_tactic,'in_possession') == automatic
    assert phase_points(session.home_tactic,'out_of_possession')['rb'] == (.65,.25)
    command(session,'studio_shape',phase='out_of_possession',points=[])
    assert not session.home_tactic.phase_shapes

@pytest.mark.parametrize('points', [[{'slot_id':'lb','x':40,'y':50}]*2, [{'slot_id':'missing','x':40,'y':50}], [{'slot_id':'lb','x':40,'y':50,'extra':1}], [{'slot_id':'lb','x':40}]])
def test_invalid_bulk_shapes_are_atomic(session, points):
    before = squad_read_model(session)
    with pytest.raises((ValueError,TypeError)):
        command(session,'studio_shape',phase='in_possession',points=points)
    assert squad_read_model(session)==before

def test_explicit_football_position_updates_role_and_context_not_player_identity(session):
    players = {e.slot_id:e.player for e in session.home_lineup.starters}
    before = ratings(session)
    command(session,'studio_point',slot_id='lb',phase='in_possession',x=36,y=48)
    command(session,'studio_position',slot_id='lb',position='AM')
    assert session.home_tactic.formation.slot('lb').position is Position.AM
    assert session.home_lineup.formation == session.home_tactic.formation
    assert {e.slot_id:e.player for e in session.home_lineup.starters} == players
    assert get_role(session.home_tactic.role_assignments['lb'].role_id).supports(Position.AM)
    assert ratings(session)[players['lb'].id] != before[players['lb'].id]
    assert phase_points(session.home_tactic,'in_possession')['lb']==(.36,.48)
    # Existing team-plan familiarity may change ACT for the whole XI.
    # The untouched players' structural OVR must remain identical.
    assert all(ratings(session)[p.id][0]==before[p.id][0] for k,p in players.items() if k!='lb')

@pytest.mark.parametrize('slot,position',[('gk','ST'),('lb','GK'),('lb','unknown')])
def test_keeper_integrity_in_position_editor(session,slot,position):
    before=squad_read_model(session)
    with pytest.raises(ValueError):
        command(session,'studio_position',slot_id=slot,position=position)
    assert squad_read_model(session)==before

def test_presets_keep_manual_geometry_but_formation_change_resets_it(session):
    command(session,'studio_point',slot_id='lb',phase='in_possession',x=40,y=38)
    command(session,'preset',id='balanced')
    assert phase_points(session.home_tactic,'in_possession')['lb']==(.4,.38)
    command(session,'formation',id='dev-5-2-2-1')
    assert not session.home_tactic.phase_shapes
    assert len(session.home_lineup.starters)==11

def test_library_crud_keeps_templates_separate_and_preserves_current_selection(session):
    original=deepcopy(session.home_tactic)
    first=save(session,'Primary')
    command(session,'studio_point',slot_id='lb',phase='in_possession',x=40,y=30)
    second=save(session,'Attack')
    assert same_tactic(session.tactical_studio.library[first].tactic,original)
    assert session.tactical_studio.library[first].tactic is not session.home_tactic
    out=session.home_lineup.starters[-1].player.id
    inc=next(p.id for p in session.home_lineup.bench if p.primary_position is not Position.GK)
    command(session,'swap_bench',starter_id=out,bench_id=inc)
    chosen={p.player.id for p in session.home_lineup.starters}
    command(session,'studio_load',entry_id=first)
    assert {p.player.id for p in session.home_lineup.starters}==chosen
    assert out not in chosen and inc in chosen
    command(session,'studio_duplicate',entry_id=second,name='Attack copy')
    duplicate=next(e for e in session.tactical_studio.library.values() if e.name=='Attack copy')
    command(session,'studio_rename',entry_id=duplicate.entry_id,name='Alternative')
    assert session.tactical_studio.library[second].name=='Attack'
    command(session,'studio_plan',plan='B',entry_id=duplicate.entry_id)
    command(session,'studio_rules',rules=[{'plan':'B','minute':65,'condition':'trailing'}])
    command(session,'studio_delete',entry_id=duplicate.entry_id)
    assert session.tactical_studio.plans['B'] is None
    assert session.tactical_studio.rules==()
    assert first in session.tactical_studio.library and second in session.tactical_studio.library

@pytest.mark.parametrize('name',['',' ','x'*61,'evil\nname',4,'<script>safe text</script>'])
def test_library_names_are_validated_as_data(session,name):
    if isinstance(name,str) and name.startswith('<script>'):
        entry=save(session,name)
        assert session.tactical_studio.library[entry].name==name
    else:
        with pytest.raises(ValueError):
            save(session,name)
        assert not session.tactical_studio.library
        assert session.tactical_studio.sequence==0

def test_duplicate_names_and_invalid_rules_cannot_partially_mutate_state(session):
    entry=save(session,'Primary')
    command(session,'studio_plan',plan='A',entry_id=entry)
    before=squad_read_model(session)
    for action in [
        {'action':'studio_save','name':'PRIMARY'},
        {'action':'studio_rules','rules':[{'plan':'B','minute':60,'condition':'always'}]},
        {'action':'studio_rules','rules':[{'plan':'A','minute':60,'condition':'always'}]*2},
        {'action':'studio_plan','plan':'D','entry_id':entry},
        {'action':'studio_load','entry_id':'no-such-tactic'},
    ]:
        with pytest.raises(ValueError):
            command(session,**action)
        assert squad_read_model(session)==before

def test_templates_round_trip_in_real_sqlite_career_and_next_season(session,tmp_path):
    command(session,'studio_point',slot_id='lb',phase='in_possession',x=35,y=44)
    command(session,'studio_position',slot_id='lb',position='DM')
    key=save(session,'Asymmetric')
    command(session,'studio_plan',plan='B',entry_id=key)
    command(session,'studio_rules',rules=[{'plan':'B','minute':65,'condition':'trailing'}])
    before=squad_read_model(session)['studio']
    repo=SQLiteSaveRepository(tmp_path/'career.sqlite3')
    save_manager_career(repo,slot_id='ts19',display_name='Tactical career',session=session,expected_revision=0)
    restored=load_manager_career(repo,'ts19').session
    assert squad_read_model(restored)['studio']==before
    assert restored.home_lineup.formation.slot('lb').position is Position.DM
    assert all(e.player is next(p for p in restored.home_club.squad.players if p.id==e.player.id) for e in restored.home_lineup.starters)
    restored.simulate_remaining_season()
    restored.begin_next_season()
    assert restored.tactical_studio.library[key].name=='Asymmetric'
    assert restored.tactical_studio.plans['B']==key
    validate_manager_session(restored)

def test_real_v2_save_with_match_result_loads_without_invented_data():
    payload=json.loads(gzip.decompress((ROOT/'tests/fixtures/ts19/manager_v2_with_result.json.gz').read_bytes()))
    assert payload['version']==2
    restored=restore_manager_graph(payload)
    validate_manager_session(restored)
    assert not restored.tactical_studio.library
    assert not restored.home_tactic.phase_shapes
    assert restored.last_result is not None
    assert restored.last_result.tactical_events==()
    assert restored.last_result.role_segments==()
    assert capture_manager_graph(restored)['version']==GRAPH_VERSION  # Preserve v2 content, migrate to the current graph schema.

def test_new_saves_reject_missing_or_invalid_tactical_data(session):
    command(session,'studio_point',slot_id='lb',phase='in_possession',x=35,y=44)
    graph=capture_manager_graph(session)
    node=next(n for n in graph['nodes'] if n.get('class')=='football_manager.domain.tactical_shapes:SlotPoint')
    node['fields']['x']=float('nan')
    with pytest.raises(SaveIntegrityError):
        validate_manager_session(restore_manager_graph(graph))
    graph=capture_manager_graph(session)
    node=next(n for n in graph['nodes'] if n.get('class')=='football_manager.domain.tactics:Tactic')
    del node['fields']['phase_shapes']
    with pytest.raises(SaveIntegrityError):
        restore_manager_graph(graph)

def test_domain_rejects_mutable_or_ambiguous_shapes_and_invalid_plan_times():
    with pytest.raises(ValueError):
        PhaseShape('in_possession',(SlotPoint('lb',.3,.5),SlotPoint('lb',.4,.6)))
    with pytest.raises(ValueError):
        PhaseShape('in_possession',[SlotPoint('lb',.3,.5)])
    for minute in (0,120,True,50.5):
        with pytest.raises(ValueError):
            PlanRule('A',minute)

def test_all_28_formations_accept_independent_shapes_and_simulate(session):
    original={e.player.id for e in session.home_lineup.starters}
    for formation in development_formations():
        command(session,'formation',id=formation.formation_id)
        slot=next(s.slot_id for s in formation.slots if s.position is not Position.GK)
        command(session,'studio_point',phase='in_possession',slot_id=slot,x=31,y=29)
        command(session,'studio_point',phase='out_of_possession',slot_id=slot,x=71,y=64)
        snapshot=session._build_snapshot()
        result=FastMatchSimulator().simulate(snapshot)
        result.__post_init__()
        assert phase_points(snapshot.home_team.tactic,'in_possession')[slot]==(.31,.29)
        assert phase_points(snapshot.home_team.tactic,'out_of_possession')[slot]==(.71,.64)
        assert {p.player_id for p in snapshot.home_team.starters}==original
        assert sum(p.shots for p in result.player_statistics if p.club_id==result.home_club_id)==result.statistics_home.shots
