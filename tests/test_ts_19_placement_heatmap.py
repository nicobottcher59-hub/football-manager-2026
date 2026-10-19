"""TS-19 zone-aware placement and heatmap regression. Node is optional."""
from __future__ import annotations

from copy import deepcopy
import json
from pathlib import Path
import shutil
import subprocess
from threading import Thread
from urllib.error import HTTPError
from urllib.request import Request, urlopen

import pytest

from football_manager.dev_ui.session import DevelopmentSession
from football_manager.domain.enums import Position
from football_manager.domain.roles import get_role
from football_manager.domain.tactical_geometry import phase_points
from football_manager.domain.tactical_position_zones import (
    POSITION_ZONES, position_options, position_zone_read_model,
)
from football_manager.persistence import SQLiteSaveRepository, load_manager_career, save_manager_career
from football_manager.persistence.session_codec import capture_manager_graph
from football_manager.ui_shell.models import squad_read_model
from football_manager.ui_shell.server import create_server
from football_manager.ui_shell.transactions import apply_squad_command_atomically

ROOT = Path(__file__).resolve().parents[1]
NODE = shutil.which('node')


@pytest.fixture(scope='module')
def template():
    return DevelopmentSession()


@pytest.fixture
def session(template):
    return deepcopy(template)


def command(session, action, **values):
    return apply_squad_command_atomically(session, dict(action=action, **values), None)


def place(session, **values):
    return command(session, 'studio_place', **dict(slot_id='lb', phase='in_possession',
                   x=50, y=29, position='AM', **values))


@pytest.mark.parametrize('x,y,expected', [
    (.50,.10, {'ST'}), (.50,.29, {'ST','SS','AM'}),
    (.50,.44, {'AM','CM','LCM','RCM'}), (.35,.58, {'LCM','CM','DM','LW'}),
    (.50,.67, {'DM'}), (.50,.90, {'CB','LCB','RCB'}),
    (.10,.20, {'LW'}), (.90,.20, {'RW'}),
    (.10,.64, {'LWB'}), (.90,.64, {'RWB'}),
    (.10,.90, {'LB'}), (.90,.90, {'RB'}),
])
def test_zones_offer_only_neighbouring_football_positions(x,y,expected):
    assert {p.value for p in position_options(x,y)} == expected


def test_overlaps_have_no_dead_areas_and_no_goalkeeper_conversions():
    assert {z.position for z in POSITION_ZONES} == set(Position)-{Position.GK}
    for x in range(4,97):
        for y in range(4,97):
            options=position_options(x/100,y/100)
            assert options and Position.GK not in options, (x,y)
    assert position_options(.12,.24,goalkeeper=True)==(Position.GK,)
    assert position_options(.95,.96,goalkeeper=True)==(Position.GK,)


@pytest.mark.parametrize('x,y', [(float('nan'),.5),(.5,float('inf')),(-1,.5),(.5,1.01),(True,.5),('50',.5),(.039,.5),(.961,.5)])
def test_invalid_coordinates_are_rejected_before_position_lookup(x,y):
    with pytest.raises(ValueError):position_options(x,y)


@pytest.mark.parametrize('values', [
    {'position':'LB'}, {'position':'CB'}, {'position':'GK'},
    {'position':'not-real'}, {'position':None}, {'x':True}, {'x':float('nan')},
    {'y':99}, {'slot_id':'missing'}, {'phase':'transition'},
    {'expected_revision':-1}, {'expected_revision':True},
])
def test_rejected_drop_does_not_change_tactic_players_revision_or_social_state(session,values):
    before=capture_manager_graph(session)
    before_view=squad_read_model(session)
    payload=dict(slot_id='lb',phase='in_possession',x=50,y=29,position='AM')
    payload.update(values)
    with pytest.raises((ValueError,TypeError,KeyError)):
        command(session,'studio_place',**payload)
    assert capture_manager_graph(session)==before
    assert squad_read_model(session)==before_view


def test_choose_position_commits_coordinates_position_role_and_revision_together(session):
    ids={e.slot_id:e.player for e in session.home_lineup.starters}
    other=phase_points(session.home_tactic,'out_of_possession')
    team_instructions=session.home_tactic.team_instructions
    previous=squad_read_model(session)
    result=place(session)
    assert session.home_tactic.formation.slot('lb').position is Position.AM
    assert get_role(session.home_tactic.role_assignments['lb'].role_id).supports(Position.AM)
    assert session.home_tactic.formation==session.home_lineup.formation
    assert all(e.player is ids[e.slot_id] for e in session.home_lineup.starters)
    assert phase_points(session.home_tactic,'in_possession')['lb']==(.5,.29)
    assert phase_points(session.home_tactic,'out_of_possession')==other
    assert session.home_tactic.team_instructions==team_instructions
    assert result['studio']['revision']==previous['studio']['revision']+1
    changed=next(p for p in result['starters'] if p['slot_id']=='lb')
    old=next(p for p in previous['starters'] if p['slot_id']=='lb')
    assert changed['ovr']!=old['ovr']  # existing position fit, not an invented penalty
    snap=session._build_snapshot().home_team.tactic
    assert snap.formation.slot('lb').position is Position.AM


def test_same_position_drop_keeps_roles_attributes_ratings_and_other_phase(session):
    before=squad_read_model(session)
    roles=dict(session.home_tactic.role_assignments)
    other=phase_points(session.home_tactic,'out_of_possession')
    result=command(session,'studio_place',slot_id='st',phase='in_possession',position='ST',x=52,y=18)
    assert session.home_tactic.role_assignments==roles
    assert phase_points(session.home_tactic,'out_of_possession')==other
    assert [(p['id'],p['ovr'],p['act'],p['attributes']) for p in result['starters']]==[(p['id'],p['ovr'],p['act'],p['attributes']) for p in before['starters']]
    assert phase_points(session.home_tactic,'in_possession')['st']==(.52,.18)


def test_out_of_possession_edit_uses_same_orientation_and_preserves_attack_shape(session):
    on=phase_points(session.home_tactic,'in_possession')
    command(session,'studio_place',slot_id='lb',phase='out_of_possession',x=35,y=63,position='DM')
    assert phase_points(session.home_tactic,'out_of_possession')['lb']==(.35,.63)
    assert phase_points(session.home_tactic,'in_possession')==on
    assert session.home_tactic.formation.slot('lb').position is Position.DM


def test_keeper_is_never_reassigned_or_moved_in_the_editor(session):
    before=squad_read_model(session)
    for position, x, y in [('GK',50,73), ('GK',50,90), ('ST',50,15)]:
        with pytest.raises(ValueError, match='goalkeeper is fixed'):
            command(session,'studio_place',slot_id='gk',phase='in_possession',x=x,y=y,position=position)
        assert squad_read_model(session)==before
    assert sum(s.position is Position.GK for s in session.home_tactic.formation.slots)==1


@pytest.mark.parametrize('action,kwargs', [
    ('studio_point', {'slot_id':'gk','phase':'in_possession','x':50,'y':70}),
    ('studio_point', {'slot_id':'gk','phase':'out_of_possession','x':40,'y':92}),
    ('studio_place', {'slot_id':'gk','phase':'out_of_possession','x':50,'y':90,'position':'GK'}),
    ('studio_shape', {'phase':'in_possession','points':[{'slot_id':'gk','x':50,'y':70}]}),
    ('studio_shape', {'phase':'out_of_possession','points':[{'slot_id':'gk','x':50,'y':90},
                                                            {'slot_id':'lb','x':30,'y':75}]}),
])
def test_keeper_cannot_be_moved_even_by_direct_backend_commands(session,action,kwargs):
    before=squad_read_model(session)
    with pytest.raises(ValueError,match='goalkeeper is fixed'):
        command(session,action,**kwargs)
    assert squad_read_model(session)==before


def test_keeper_legacy_manual_target_can_be_reset_without_allowing_drag(session):
    # An older career could already have a manual keeper position. Resetting
    # that obsolete target is allowed; creating new ones is not.
    session.home_tactic.set_phase_point('in_possession','gk',.5,.63)
    command(session,'studio_point',slot_id='gk',phase='in_possession',reset=True)
    assert 'gk' not in squad_read_model(session)['studio']['anchors'].get('in_possession',{})


def test_midfield_flanks_offer_lm_rm_as_labels_with_legacy_position_codes():
    zones=position_zone_read_model()
    for x,code,label in ((.16,'LW','LM'),(.84,'RW','RM')):
        at_mid=[z for z in zones if z['x_min']<=x<=z['x_max'] and z['y_min']<=.48<=z['y_max']]
        assert any(z['position']==code and z['display_position']==label for z in at_mid)
        at_front=[z for z in zones if z['x_min']<=x<=z['x_max'] and z['y_min']<=.20<=z['y_max']]
        assert any(z['position']==code and z['display_position']==code for z in at_front)
        assert all(z['display_position']!=label for z in at_front)
        assert position_options(x,.48) and Position(code) in position_options(x,.48)
    assert 'LM' not in {p.value for p in Position}
    assert 'RM' not in {p.value for p in Position}


def test_midfield_flank_placement_keeps_existing_role_familiarity_and_save_schema(session):
    result=command(session,'studio_place',slot_id='lb',phase='in_possession',position='LW',x=18,y=47)
    assert result['studio']['shapes']['in_possession']['lb']=={'x':18,'y':47}
    assert session.home_tactic.formation.slot('lb').position is Position.LW
    assert get_role(session.home_tactic.role_assignments['lb'].role_id).supports(Position.LW)
    from football_manager.persistence.session_codec import GRAPH_VERSION
    assert capture_manager_graph(session)['version']==GRAPH_VERSION


def test_phase_aware_existing_position_control_cannot_bypass_zone_filter(session):
    command(session,'studio_point',slot_id='lb',phase='in_possession',x=50,y=29)
    before=squad_read_model(session)
    with pytest.raises(ValueError):
        command(session,'studio_position',slot_id='lb',phase='in_possession',position='CB')
    assert squad_read_model(session)==before
    command(session,'studio_position',slot_id='lb',phase='in_possession',position='SS')
    assert session.home_tactic.formation.slot('lb').position is Position.SS


def test_library_and_full_career_round_trip_keep_zone_selection(session,tmp_path):
    place(session)
    command(session,'studio_save',name='Zonal attack')
    saved=session.tactical_studio.active_id
    before=squad_read_model(session)['studio']
    repository=SQLiteSaveRepository(tmp_path/'career.sqlite3')
    save_manager_career(repository,slot_id='zone',display_name='Zone career',session=session,expected_revision=0)
    loaded=load_manager_career(repository,'zone').session
    assert squad_read_model(loaded)['studio']==before
    assert loaded.home_tactic.formation.slot('lb').position is Position.AM
    command(loaded,'formation',id='dev-5-2-2-1')
    command(loaded,'studio_load',entry_id=saved)
    assert phase_points(loaded.home_tactic,'in_possession')['lb']==(.5,.29)
    assert loaded.home_tactic.formation.slot('lb').position is Position.AM


def test_ts19_edits_do_not_modify_ts20_when_installed(session):
    # This test also runs on TS-19 without requiring the TS-20 module or data.
    before=deepcopy(getattr(session,'dressing_room',None))
    states=[deepcopy(p.state) for p in session.home_club.squad.players]
    place(session)
    assert getattr(session,'dressing_room',None)==before
    assert [p.state for p in session.home_club.squad.players]==states


def test_actual_http_supports_atomic_placement_and_sends_same_zone_config(session,tmp_path):
    server=create_server(port=0,session=session,save_repository=SQLiteSaveRepository(tmp_path/'http.sqlite3'))
    thread=Thread(target=server.serve_forever,daemon=True);thread.start()
    base=f'http://127.0.0.1:{server.server_port}'
    def get():
        with urlopen(base+'/api/squad',timeout=10) as response:return json.loads(response.read())
    def post(payload):
        req=Request(base+'/api/squad',data=json.dumps(payload).encode(),headers={'Content-Type':'application/json'},method='POST')
        with urlopen(req,timeout=10) as response:return json.loads(response.read())
    try:
        view=get()
        assert view['studio']['position_zones']==position_zone_read_model()
        payload=dict(action='studio_place',slot_id='st',phase='in_possession',position='CB',x=50,y=20,expected_revision=view['studio']['revision'])
        with pytest.raises(HTTPError) as exc:post(payload)
        assert exc.value.code==400
        assert get()==view
        payload['position']='SS'
        result=post(payload)
        assert result['studio']['revision']==view['studio']['revision']+1
        assert next(s for s in result['slots'] if s['slot_id']=='st')['position']=='SS'
        with pytest.raises(HTTPError):post(payload)
        assert get()==result
    finally:
        server.shutdown();server.server_close();thread.join(timeout=3)


@pytest.mark.skipif(NODE is None,reason='Optional Node.js check; Python/browser validation does not require Node')
def test_javascript_candidates_match_python_every_percent_and_heatmap_has_fixed_color_scale(session):
    cells=[{'x':x,'y':y} for x in range(4,97) for y in range(4,97)]
    payload=dict(studio=squad_read_model(session)['studio'],cells=cells)
    js="""const fs=require('fs');const vm=require('vm');const scope={};vm.runInNewContext(fs.readFileSync('./frontend/public/squad/studio.js','utf8'),scope);const s=scope.FMStudio;const d=JSON.parse(fs.readFileSync(0,'utf8'));
    console.log(JSON.stringify({options:d.cells.map(p=>s.positionOptions(d.studio,p).map(z=>z.position)),colors:[-1,0,.125,.25,.5,.75,1,2].map(s.coverageColor)}));"""
    run=subprocess.run([NODE,'-e',js],input=json.dumps(payload),text=True,capture_output=True,check=True,cwd=ROOT,timeout=20)
    actual=json.loads(run.stdout)
    assert actual['options']==[[p.value for p in position_options(c['x']/100,c['y']/100)] for c in cells]
    assert actual['colors']==[[239,68,68],[239,68,68],[242,113,40],[245,158,11],[250,204,21],[132,204,22],[34,197,94],[34,197,94]]


def test_frontend_keeps_smoothing_and_textual_legend_without_external_dependencies():
    js=(ROOT/'frontend/public/squad/studio.js').read_text(encoding='utf-8')
    css=(ROOT/'frontend/public/squad/studio.css').read_text(encoding='utf-8')
    assert "imageSmoothingEnabled=true" in js
    assert 'Low (red)' in js and 'Medium (yellow)' in js and 'High (green)' in js
    assert 'phase:context.phase' in js and "action:'studio_place'" in js
    assert 'role="dialog"' in js or '<dialog ' in js
    assert '#ef4444 0%' in css and '#22c55e 100%' in css
    assert 'require(' not in js and 'https://' not in js
