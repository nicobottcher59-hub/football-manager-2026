"""UI-2 integration tests using the existing development session, no altered engine."""
from __future__ import annotations

from dataclasses import fields
import json
from threading import Thread
from urllib.error import HTTPError
from urllib.parse import urljoin
from urllib.request import Request, urlopen

import pytest

from football_manager.dev_ui.session import DevelopmentSession
from football_manager.domain.tactical_instructions import (
    InPossessionInstructions, OutOfPossessionInstructions, TransitionInstructions,
    GameManagementInstructions, PlayerInstructionOverrides,
)
from football_manager.ui_shell.models import apply_squad_command, squad_read_model
from football_manager.ui_shell.server import create_server


@pytest.fixture
def session():
    return DevelopmentSession()


def test_squad_view_is_based_on_python_and_contains_all_fields(session):
    data = squad_read_model(session)
    assert data['source'] == 'python-development-session'
    assert data['persistent'] is False
    assert len(data['starters']) == 11
    assert len(data['bench']) == len(session.home_lineup.bench) == 7
    assert data['outside'] == []  # never invent 5 extra players to match a mockup
    assert len({p['id'] for p in data['starters'] + data['bench']}) == 18
    assert len(data['slots']) == 11
    assert len(data['slots'][0]['individual']) == len(fields(PlayerInstructionOverrides)) == 15
    expected = sum(len(fields(cls)) for cls in (InPossessionInstructions, TransitionInstructions, OutOfPossessionInstructions, GameManagementInstructions))
    assert len(data['tactics']['fields']) == expected == 44
    assert data['set_pieces']['supported'] is False


def test_rating_source_is_session_not_ui_mock(session):
    data=squad_read_model(session)
    for p in data['starters']:
        row=next(r for r in session.squad_rows() if r.player_id==p['id'])
        assert p['ovr']==round(row.overall,1)
        assert p['act']==round(row.current,1)
        assert p['condition']==round(row.condition,1)
        assert 0<=p['ovr']<=100 and 0<=p['act']<=100


def test_shape_presets_and_instructions_use_existing_commands(session):
    initial=squad_read_model(session)
    f=next(f for f in initial['formations'] if f['id']!=initial['formation']['id'])
    changed=apply_squad_command(session,{'action':'formation','id':f['id']})
    assert changed['formation']['id']==f['id']
    assert len(changed['starters'])==11
    assert len({p['id'] for p in changed['starters']})==11
    changed=apply_squad_command(session,{'action':'preset','id':'wide_attack'})
    assert changed['tactics']['preset']=='wide_attack'
    changed=apply_squad_command(session,{'action':'team_instruction','group':'in_possession','field':'attacking_line_width','value':'very_high'})
    width=next(v for v in changed['tactics']['fields'] if v['group']=='in_possession' and v['field']=='attacking_line_width')
    assert width['value']=='very_high'
    assert changed['tactics']['preset']=='custom'
    changed=apply_squad_command(session,{'action':'team_instruction','group':'out_of_possession','field':'offside_trap','value':'on'})
    assert any(f['value']=='on' for f in changed['tactics']['fields'] if f['field']=='offside_trap')


def test_role_and_all_individual_fields_are_editable(session):
    data=squad_read_model(session)
    slot=data['slots'][0]
    next_role=next(r for r in slot['roles'] if r['id']!=slot['role_id'])
    changed=apply_squad_command(session,{'action':'role','slot_id':slot['slot_id'],'role_id':next_role['id']})
    assert changed['slots'][0]['role_id']==next_role['id']
    effective=changed['slots'][0]['individual']
    assert len(effective)==15
    first=effective[0]
    choice=next(x for x in first['options'] if x != first['effective'])
    changed=apply_squad_command(session,{'action':'player_instruction','slot_id':slot['slot_id'],'field':first['field'],'value':choice})
    assert changed['slots'][0]['individual'][0]['effective']==choice
    assert changed['slots'][0]['individual'][0]['override']==choice
    changed=apply_squad_command(session,{'action':'player_instruction','slot_id':slot['slot_id'],'field':'marking','value':'position:ST'})
    assert next(i for i in changed['slots'][0]['individual'] if i['field']=='marking')['effective']=='position:ST'
    changed=apply_squad_command(session,{'action':'reset_player_instructions','slot_id':slot['slot_id']})
    assert all(i['override'] is None for i in changed['slots'][0]['individual'])


def test_substitution_and_starter_swap_keep_squad_unique(session):
    data=squad_read_model(session)
    first,second=data['starters'][:2]
    switched=apply_squad_command(session,{'action':'swap_starters','first':first['slot_id'],'second':second['slot_id']})
    assert next(p for p in switched['starters'] if p['slot_id']==first['slot_id'])['id']==second['id']
    bench_id=switched['bench'][0]['id']
    starter_id=switched['starters'][0]['id']
    swapped=apply_squad_command(session,{'action':'swap_bench','starter_id':starter_id,'bench_id':bench_id})
    assert bench_id in [p['id'] for p in swapped['starters']]
    assert starter_id in [p['id'] for p in swapped['bench']]
    assert len(set(p['id'] for p in swapped['starters']+swapped['bench']))==18


@pytest.mark.parametrize('command',[
    {}, {'action':'team_instruction','group':'invalid','field':'tempo','value':'high'},
    {'action':'formation','id':'nonexistent'}, {'action':'role','slot_id':'gk','role_id':'striker'},
    {'action':'player_instruction','slot_id':'gk','field':'not-real','value':'high'},
    {'action':'player_instruction','slot_id':'gk','field':'marking','value':'player:nonexistent'},
    {'action':'swap_starters','first':'gk','second':'other'},
])
def test_invalid_commands_are_rejected_without_fake_success(session, command):
    with pytest.raises((ValueError, KeyError)):
        apply_squad_command(session,command)


def test_http_api_and_static_files_are_local_only(session):
    server=create_server(port=0,session=session)
    thread=Thread(target=server.serve_forever,daemon=True)
    thread.start()
    base=f'http://127.0.0.1:{server.server_port}'
    try:
        with urlopen(base+'/api/squad',timeout=5) as response:
            assert len(json.loads(response.read())['tactics']['fields'])==44
        with urlopen(base+'/squad/embed.html',timeout=5) as response:
            assert b'squad.js' in response.read()
        with urlopen(base+'/portable/index.html',timeout=5) as response:
            assert b'FM PROJECT' in response.read()
        request=Request(base+'/api/squad',data=json.dumps({'action':'preset','id':'tiki_taka'}).encode(),headers={'Content-Type':'application/json'},method='POST')
        with urlopen(request,timeout=5) as response:
            assert json.loads(response.read())['tactics']['preset']=='tiki_taka'
        host=Request(base+'/api/squad',headers={'Host':'malicious.invalid'})
        with pytest.raises(HTTPError) as err:
            urlopen(host,timeout=5)
        assert err.value.code==403
        for route in ('/portable/../../README.md','/public/squad/../../../README.md'):
            with pytest.raises(HTTPError):
                urlopen(base+route,timeout=5)
        assert session.home_tactic.preset_origin.value=='tiki_taka'
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=5)


def test_portable_root_redirects_and_loads_all_relative_assets(session):
    """Prevent regression: a root-served index must not request /styles.css."""
    server = create_server(port=0, session=session)
    thread = Thread(target=server.serve_forever, daemon=True)
    thread.start()
    base = f'http://127.0.0.1:{server.server_port}'
    try:
        # urllib follows the redirect; the resolved URL must be the asset folder.
        with urlopen(base + '/', timeout=5) as response:
            assert response.status == 200
            assert response.url == base + '/portable/'
            html = response.read().decode('utf-8')
            assert 'href="styles.css"' in html
            assert 'src="data/demo.js"' in html
            assert 'src="portable.js"' in html
        for asset, mime in (
            ('styles.css', 'text/css'),
            ('data/demo.js', 'javascript'),
            ('portable.js', 'javascript'),
            ('assets/stadium.svg', 'image/svg+xml'),
            ('../public/squad/embed.html', 'text/html'),
        ):
            with urlopen(urljoin(base + '/portable/', asset), timeout=5) as response:
                assert response.status == 200
                assert mime in response.headers.get_content_type()
                assert response.read()
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=5)
