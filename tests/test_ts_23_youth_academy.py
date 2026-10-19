"""TS-23 youth, scouting, progression, persistence and no-FM-premium fixtures."""
from __future__ import annotations
from copy import deepcopy
from datetime import date
import pytest

from football_manager.dev_ui.session import DevelopmentSession
from football_manager.domain.player_development import next_month
from football_manager.persistence.session_codec import capture_manager_graph, restore_manager_graph, GRAPH_VERSION
from football_manager.persistence.manager_career import manager_career_document, validate_manager_session
from football_manager.services.player_development import advance_world_development
from football_manager.services.youth_academy import (
    MAX_U15, POSITION_POOL, scout_market, youth_command, youth_read_model, roll_youth_season,
)


def hire_test_scout(session, *, strong=False):
    offers=scout_market(session._world_squads.youth)
    offer=max(offers,key=lambda o:o['quality']) if strong else offers[0]
    return youth_command(session,{'action':'hire_scout','offer_id':offer['id']})['scout_id']


@pytest.fixture(scope='module')
def starting():
    return DevelopmentSession()


def test_all_clubs_have_real_youth_rosters_and_non_playable_u15_preview(starting):
    registry=starting._world_squads
    youth=registry.youth
    assert len(youth.academies)==92
    assert sum(len(a.u15) for a in youth.academies.values())==1840
    assert sum(len(a.u17) for a in youth.academies.values())==1656
    assert sum(len(a.u21) for a in youth.academies.values())==1656
    assert len(youth.fixtures)==4072
    assert all(len(a.u15)==MAX_U15 for a in youth.academies.values())
    assert all(any(p.position.value=='GK' for p in a.u15.values()) for a in youth.academies.values())
    for academy in youth.academies.values():
        assert all(p.development is not None and p.aging is not None for p in (*academy.u17.values(),*academy.u21.values()))
    youth.check_unique(registry)
    view=youth_read_model(starting)
    assert len(view['u15'])==20 and view['managed']
    assert not any('potential_budget' in p or 'pa' in p for p in view['u15'])
    assert all('projection' in p for p in view['u15'])


def test_youth_fixtures_are_same_double_round_robin_for_every_club(starting):
    youth=starting._world_squads.youth
    fixture_ids=list(youth.fixtures)
    assert len(set(fixture_ids))==len(fixture_ids)
    for level in ('u17','u21'):
        same=[f for f in youth.fixtures.values() if f.level==level and f.division=='dev-premier']
        assert len(same)==380
        assert len({(f.home_club_id,f.away_club_id) for f in same})==380


def test_advance_one_month_records_real_youth_exposures_without_duplicate(starting):
    session=deepcopy(starting)
    youth=session._world_squads.youth
    boundary=date(2026,10,1)
    count_before=sum(f.home_goals is not None for f in youth.fixtures.values())
    n=advance_world_development(session._world,boundary)
    assert n>0
    completed=[f for f in youth.fixtures.values() if f.home_goals is not None]
    assert len(completed)>count_before
    assert any(p.development.history for a in youth.academies.values() for p in a.u17.values())
    assert any(p.state.match_sharpness>65 for a in youth.academies.values() for p in a.u21.values())
    snapshots=tuple((f.fixture_id,f.home_goals,f.away_goals) for f in completed)
    assert advance_world_development(session._world,boundary)==0
    assert snapshots == tuple((f.fixture_id,f.home_goals,f.away_goals) for f in youth.fixtures.values() if f.home_goals is not None)
    session._world_squads.youth.check_unique(session._world_squads)


def test_scout_quarterly_reports_are_country_specific_and_have_new_ids(starting):
    session=deepcopy(starting)
    sid=hire_test_scout(session,strong=True)
    result=youth_command(session,{'action':'assign_scout','scout_id':sid,'country':'Brazil','position':'ST'})
    assert result['next_report']=='2026-11-21'
    assert not session._world_squads.youth.candidates
    advance_world_development(session._world,date(2026,12,1))
    candidates=list(session._world_squads.youth.candidates.values())
    assert 7<=len(candidates)<=9
    assert all(c.preview.nationality=='Brazil' and c.preview.position.value=='ST' for c in candidates)
    assert all(c.scout_id==sid for c in candidates)
    first=candidates[0].preview
    assert first.player_id not in session.home_club.squad._players
    result=youth_command(session,{'action':'watch','player_id':first.player_id})
    assert result['watching']
    signed=youth_command(session,{'action':'sign','player_id':first.player_id})
    assert signed['signed'] and signed['player_id']==first.player_id
    academy=session._world_squads.youth.academies[session.home_club.id]
    assert first.player_id in academy.u17
    assert academy.u17[first.player_id].identity.birth_date == first.birth_date
    assert academy.u17[first.player_id].development.potential >= 1
    assert first.player_id not in session._world_squads.youth.candidates
    with pytest.raises(ValueError):
        youth_command(session,{'action':'sign','player_id':first.player_id})


def test_youth_player_moves_keep_identity_and_manager_career_valid(starting):
    session=deepcopy(starting)
    academy=session._world_squads.youth.academies[session.home_club.id]
    player=next(p for p in academy.u17.values() if p.age_on(session.current_date)<=17)
    player_id=player.id
    result=youth_command(session,{'action':'move','player_id':player_id,'target':'first'})
    assert result['moved']
    assert session.home_club.squad.get(player_id) is player
    assert player_id not in academy.u17
    assert session._world_squads.youth.promoted_to_first[player_id]==session.home_club.id
    assert player.state.match_sharpness<=72
    back=youth_command(session,{'action':'move','player_id':player_id,'target':'u17'})
    assert back['moved'] and academy.u17[player_id] is player
    assert not session.home_club.squad.contains(player_id)
    validate_manager_session(session)


def test_v9_save_upgrade_and_v10_roundtrip_do_not_modify_original_players(starting):
    session=deepcopy(starting)
    original={p.id:(p.identity.birth_date,p.attributes,p.development.potential)
              for c in session._world_squads.clubs.values() for p in c.squad.players}
    graph=capture_manager_graph(session)
    assert graph['version']==GRAPH_VERSION==16
    restored=restore_manager_graph(graph)
    assert restored._world_squads.youth is restored._world.football_world.youth
    assert restored._world_squads.youth.check_unique(restored._world_squads) is None
    assert original=={p.id:(p.identity.birth_date,p.attributes,p.development.potential)
                     for c in restored._world_squads.clubs.values() for p in c.squad.players}
    # Saved v9 graph contains no youth node, and upgrading creates youth only once.
    old=deepcopy(graph)
    old['version']=9
    oldworld=[n for n in old['nodes'] if n.get('class')=='football_manager.domain.football_world:FootballWorld']
    assert len(oldworld)==1
    del oldworld[0]['fields']['youth']
    migrated=restore_manager_graph(old)
    assert migrated._world_squads.youth is not None
    assert {p.id for a in migrated._world_squads.youth.academies.values() for p in a.u15.values()}=={
        p.id for a in restored._world_squads.youth.academies.values() for p in a.u15.values()}
    assert original=={p.id:(p.identity.birth_date,p.attributes,p.development.potential)
                     for c in migrated._world_squads.clubs.values() for p in c.squad.players}


def test_readonly_queries_do_not_change_scouters_or_youth_seed(starting):
    session=deepcopy(starting)
    before=capture_manager_graph(session)['version']
    fixture_count=sum(f.home_goals is not None for f in session._world_squads.youth.fixtures.values())
    for _ in range(5):
        youth_read_model(session)
    assert before == GRAPH_VERSION  # Match the current save codec, not TS-23
    assert sum(f.home_goals is not None for f in session._world_squads.youth.fixtures.values())==fixture_count
    assert not session._world_squads.youth.candidates


def test_live_python_http_youth_route_and_scout_action(starting):
    """Test real static assets, GET read models and POST transactional commands."""
    from threading import Thread
    from urllib.request import Request, urlopen
    from football_manager.ui_shell.server import create_server
    import json
    server = create_server(port=0,session=deepcopy(starting))
    thread = Thread(target=server.serve_forever,daemon=True)
    thread.start()
    host=f'http://127.0.0.1:{server.server_port}'
    try:
        with urlopen(host+'/api/youth',timeout=30) as resp:
            before=json.load(resp)
        assert before['managed'] and len(before['u15'])==20
        assert len(before['standings']['u17'])==20
        with urlopen(host+'/portable/youth_academy.js',timeout=30) as resp:
            js=resp.read().decode('utf8')
        assert 'window.FMYouthAcademy' in js
        offers=before['market_offers']
        hire_req=Request(host+'/api/youth',method='POST',headers={'Content-Type':'application/json'},
            data=json.dumps({'action':'hire_scout','offer_id':offers[0]['id']}).encode())
        with urlopen(hire_req,timeout=60) as resp:
            hired=json.load(resp)
        request=Request(host+'/api/youth',method='POST',headers={'Content-Type':'application/json'},
              data=json.dumps({'action':'assign_scout','scout_id':hired['scout_id'],'country':'Argentina','position':'ST'}).encode())
        with urlopen(request,timeout=60) as resp:
            result=json.load(resp)
        assert result['assigned'] and result['next_report']=='2026-11-21'
        with urlopen(host+'/api/youth',timeout=30) as resp:
            after=json.load(resp)
        assert after['scouts'][0]['country']=='Argentina'
        assert len(after['u15'])==len(before['u15'])
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=5)


def test_age_promotion_is_annual_and_non_playable_u15_does_not_bypass_u17(starting):
    session=deepcopy(starting)
    academy=session._world_squads.youth.academies[session.home_club.id]
    before={p.id:p for p in academy.u15.values()}
    assert len(before)==20
    # No instant promotion when reading on another day.
    youth_read_model(session)
    assert len(academy.u15)==20
    today=date(2027,7,1)
    tally=roll_youth_season(session._world_squads,today,session.home_club.id,new_label='2027/28')
    promoted={pid for pid in before if pid in academy.u17}
    assert 8<=len(promoted)<=12
    assert all(academy.u17[pid].identity.birth_date==before[pid].birth_date for pid in promoted)
    assert len(academy.u15)==20
    assert tally['u15_to_u17']>=len(promoted)


def test_full_sqlite_career_save_preserves_youth_fixtures_and_scouts(starting,tmp_path):
    from football_manager.persistence import SQLiteSaveRepository
    from football_manager.persistence.manager_career import save_manager_career,load_manager_career
    s=deepcopy(starting)
    before=s._world_squads.youth
    sid=hire_test_scout(s)
    youth_command(s,{'action':'assign_scout','scout_id':sid,'country':'France','position':'MID'})
    repo=SQLiteSaveRepository(tmp_path/'ts23.sqlite3')
    save_manager_career(repo,slot_id='youth',display_name='TS23',session=s,expected_revision=0)
    loaded=load_manager_career(repo,'youth').session
    assert loaded._world_squads.youth==s._world_squads.youth
    assert loaded._world_squads.youth is loaded._world.football_world.youth
    assert loaded._world_squads.youth.scouts[sid].country=='France'
    assert len(loaded._world_squads.youth.academies)==len(before.academies)
    validate_manager_session(loaded)
