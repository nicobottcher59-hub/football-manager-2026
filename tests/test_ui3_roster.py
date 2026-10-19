"""UI-3: truthful roster data, dynamic familiarity, DEV-only metadata and HTTP assets."""
from __future__ import annotations

from threading import Thread
from urllib.request import Request, urlopen
from urllib.error import HTTPError
import json
import pytest

from football_manager.dev_ui.session import DevelopmentSession
from football_manager.ui_shell.models import UIRosterAdmin, apply_squad_command, squad_read_model, SEASON_STAT_KEYS
from football_manager.ui_shell.server import create_server


@pytest.fixture
def session():
    return DevelopmentSession()


def test_roster_all_players_general_and_attributes_are_python_truth(session):
    view = squad_read_model(session)
    assert len(view['roster']) == len(session.home_club.squad.players)
    assert {p['id'] for p in view['roster']} == {p.id for p in session.home_club.squad.players}
    for item in view['roster']:
        player = session.home_club.squad.get(item['id'])
        assert item['base_ovr'] == round(player.overall_rating, 1)
        assert item['primary_position'] == player.primary_position.value
        assert item['secondary_positions'] == [pos.value for pos in player.secondary_positions]
        assert item['attributes']['technical']['passing'] == player.attributes.technical.passing
        assert item['attributes']['mental']['decisions'] == player.attributes.mental.decisions
        assert item['attributes']['physical']['pace'] == player.attributes.physical.pace
        assert item['age'] == player.age_on(session.current_date)
        assert item['number'] is None  # the domain has no shirt-number system yet
        assert item['market_value'].startswith('£') and item['market_value_gbp'] > 0
        assert item['contract'] is not None
        assert item['happiness'] is None  # never pretend that morale = happiness


def test_dynamic_positional_familiarity_shows_secondary_and_learning(session):
    player = next(p for p in session.home_club.squad.players if p.secondary_positions)
    view = squad_read_model(session)
    payload = next(p for p in view['roster'] if p['id'] == player.id)
    assert payload['familiarities'][0]['position'] == player.primary_position.value
    for position in (player.primary_position, *player.secondary_positions):
        item = next(x for x in payload['familiarities'] if x['position'] == position.value)
        assert item['effective'] == round(player.familiarity_for(position), 1)
        assert item['minutes'] == round(player.positional_familiarity.minutes_for(position), 1)
    secondary = player.secondary_positions[0]
    before = next(x for x in payload['familiarities'] if x['position'] == secondary.value)['effective']
    player.record_position_minutes(secondary, 90)
    after = next(x for x in squad_read_model(session)['roster'] if x['id'] == player.id)
    new = next(x for x in after['familiarities'] if x['position'] == secondary.value)['effective']
    assert new >= before


def test_season_stats_real_zeroes_for_unplayed_and_none_for_untracked(session):
    view = squad_read_model(session)
    assert view['roster_capabilities']['season_player_ledger'] is True
    assert view['season_stat_keys'] == list(SEASON_STAT_KEYS)
    for p in view['roster']:
        assert p['season_stats']['appearances'] == 0
        assert p['season_stats']['minutes'] == 0
        assert p['season_stats']['xa'] is p['season_stats']['tackles'] is None


def test_ui_admin_number_and_availability_change_only_ui_view(session):
    admin = UIRosterAdmin()
    players = list(session.home_club.squad.players)
    baseline = squad_read_model(session)
    pid = players[0].id
    changed = apply_squad_command(session, {'action':'squad_number','player_id':pid,'number':16}, admin)
    assert next(p for p in changed['roster'] if p['id']==pid)['number'] == 16
    changed = apply_squad_command(session, {'action':'transfer_status','player_id':pid,'status':'untouchable'},admin)
    assert next(p for p in changed['roster'] if p['id']==pid)['transfer_status'] == 'untouchable'
    assert players[0].overall_rating == session.home_club.squad.get(pid).overall_rating
    assert next(p for p in baseline['roster'] if p['id']==pid)['transfer_status'] == 'normal'
    assert next(p for p in squad_read_model(session)['roster'] if p['id']==pid)['number'] is None
    with pytest.raises(ValueError,match='already allocated'):
        apply_squad_command(session,{'action':'squad_number','player_id':players[1].id,'number':16},admin)
    with pytest.raises(ValueError,match='unknown transfer'):
        apply_squad_command(session,{'action':'transfer_status','player_id':pid,'status':'completed_transfer'},admin)
    with pytest.raises(ValueError,match='1..99'):
        apply_squad_command(session,{'action':'squad_number','player_id':pid,'number':300},admin)
    with pytest.raises(ValueError,match='unknown roster player'):
        apply_squad_command(session,{'action':'squad_number','player_id':'not-a-player','number':3},admin)
    # No manager save was introduced: a fresh UI admin object has no assignments.
    assert squad_read_model(session, UIRosterAdmin())['roster'][0]['number'] is None


def test_http_ui3_assets_and_admin_commands(session):
    server = create_server(port=0, session=session)
    thread = Thread(target=server.serve_forever,daemon=True)
    thread.start()
    base = f'http://127.0.0.1:{server.server_port}'
    try:
        for path, token in (
            ('/squad/embed.html','roster.js'),
            ('/squad/roster.js','FMRoster'),
            ('/squad/roster.css','rt-table'),
            ('/squad/squad.js','tacticMode'),
            ('/portable/portable.js','UI-3'),
        ):
            with urlopen(base+path,timeout=5) as resp:
                assert resp.status == 200
                assert token.encode() in resp.read()
        with urlopen(base+'/api/squad',timeout=5) as resp:
            player = json.loads(resp.read())['roster'][0]
        payload = json.dumps({'action':'squad_number','player_id':player['id'],'number':42}).encode()
        request = Request(base+'/api/squad',data=payload,headers={'Content-Type':'application/json'},method='POST')
        with urlopen(request,timeout=5) as resp:
            assert json.loads(resp.read())['roster'][0]['number'] == 42
        with urlopen(base+'/api/squad',timeout=5) as resp:
            assert json.loads(resp.read())['roster'][0]['number'] == 42
        with pytest.raises(HTTPError) as err:
            urlopen(Request(base+'/api/squad',headers={'Host':'example.com'}),timeout=5)
        assert err.value.code==403
    finally:
        server.shutdown();server.server_close();thread.join(timeout=5)
