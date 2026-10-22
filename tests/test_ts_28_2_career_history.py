"""TS-28.2: permanent verified player, club and competition histories."""
from copy import deepcopy
from dataclasses import replace
from datetime import timedelta
from threading import Thread
from urllib.error import HTTPError
from urllib.request import urlopen
import json

import pytest

from football_manager.dev_ui.session import DevelopmentSession
from football_manager.domain.player_aging import RetiredPlayer
from football_manager.persistence.manager_career import validate_manager_session
from football_manager.persistence.session_codec import GRAPH_VERSION, capture_manager_graph, restore_manager_graph
from football_manager.ui_shell.career_history import (
    player_career_read_model, club_career_read_model, competition_career_read_model,
)
from football_manager.ui_shell.server import create_server


@pytest.fixture(scope='module')
def starting():
    return DevelopmentSession()


def test_player_history_is_real_and_read_only(starting):
    player = starting.home_club.squad.players[0]
    before = (len(starting._world.results), starting.current_date,
              len(starting._world_squads.player_season_clubs), len(starting._world_squads.player_honours))
    result = player_career_read_model(starting, player.id)
    assert result == player_career_read_model(starting, player.id)
    assert result['source'] == 'verified-career-ledgers'
    assert result['name'] == player.full_name and result['status'] == 'active'
    assert result['id'] == player.id and result['current_club_id'] == starting.home_club.id
    assert not result['transfers'] and not result['honours']
    assert before == (len(starting._world.results), starting.current_date,
                      len(starting._world_squads.player_season_clubs), len(starting._world_squads.player_honours))
    with pytest.raises(KeyError):
        player_career_read_model(starting, 'no-real-player')


def test_club_and_competition_are_linked_but_not_fabricated(starting):
    cid = starting.home_club.id
    club = club_career_read_model(starting, cid)
    assert club['name'] == starting.home_club.name
    assert club['source'] == 'verified-career-ledgers'
    assert club['seasons'][0]['season'] == starting._world.season_label
    assert club['seasons'][0]['complete'] is False
    assert not club['trophies']
    assert all(match['home_goals'] >= 0 and match['away_goals'] >= 0 for match in club['fixtures']['matches'])
    tournament = competition_career_read_model(starting, 'dev-premier')
    assert tournament['name'] and not tournament['season_complete']
    assert tournament['season'] in tournament['available_seasons']
    assert any(row['club_id'] == cid for row in tournament['table'])
    assert not tournament['champions']
    for bad in ('unregistered-club', ''):
        with pytest.raises(KeyError):
            club_career_read_model(starting, bad)
    with pytest.raises(KeyError):
        competition_career_read_model(starting, 'not-a-competition')
    with pytest.raises(KeyError):
        competition_career_read_model(starting, 'dev-premier', season='1920/21')


def test_real_match_records_club_season_and_player_stats(starting):
    session = deepcopy(starting)
    result = session.quick_simulate()
    assert result.home_goals >= 0
    league = club_career_read_model(session, session.home_club.id)
    assert league['fixtures']['total'] >= 1
    assert any(m['home_id'] == session.home_club.id or m['away_id'] == session.home_club.id for m in league['fixtures']['matches'])
    registry = session._world_squads
    links = registry.player_season_clubs[session._world.season_label]
    candidate = next(p for p in session.home_club.squad.players if session.home_club.id in links.get(p.id, ()))
    history = player_career_read_model(session, candidate.id)
    assert history['seasons'][0]['clubs'] == [{'id':session.home_club.id,'name':session.home_club.name}]
    assert history['seasons'][0]['statistics']['appearances'] >= 1
    validate_manager_session(session)
    graph = capture_manager_graph(session)
    assert graph['version'] == GRAPH_VERSION == 25
    restored = restore_manager_graph(graph)
    validate_manager_session(restored)
    assert player_career_read_model(restored,candidate.id) == history
    assert club_career_read_model(restored, session.home_club.id) == league


def test_retired_player_remains_accessible_after_leaving_active_squad(starting):
    session = deepcopy(starting)
    reg = session._world_squads
    cid = next(x for x in reg.clubs if x not in (session.home_club.id, session.away_club.id))
    club = reg.clubs[cid]
    player = club.squad.players[0]
    assert player.aging is not None
    now=session.current_date
    player.aging = replace(player.aging,retirement_status='retired',
        retirement_requested_on=now,retirement_checked_on=now,retired_on=now)
    reg.retired_players[player.id] = RetiredPlayer(player,cid,now)
    club.squad._players.pop(player.id)
    result = player_career_read_model(session, player.id)
    assert result['status'] == 'retired' and result['retired_on']==now.isoformat()
    assert result['current_club_id'] == cid
    assert player.id in {r['id'] for r in club_career_read_model(session,cid)['retired_players']}
    # No speculative trophies or guessed earlier clubs.
    assert not result['honours']
    assert all(row['clubs'] or row['coverage'] for row in result['seasons'])


def test_version20_graph_migrates_with_explicit_empty_new_ledgers(starting):
    graph = capture_manager_graph(starting)
    graph['version'] = 20
    nodes = [x for x in graph['nodes'] if x.get('class')=='football_manager.domain.football_world:FootballWorld']
    assert len(nodes)==1
    nodes[0]['fields'].pop('player_season_clubs')
    nodes[0]['fields'].pop('player_honours')
    loaded = restore_manager_graph(graph)
    assert loaded._world_squads.player_season_clubs == {}
    assert loaded._world_squads.player_honours == {}
    validate_manager_session(loaded)
    assert player_career_read_model(loaded, loaded.home_club.squad.players[0].id)['name']


def test_api_and_assets_are_served_with_validation(starting):
    server=create_server(port=0,session=starting)
    thread=Thread(target=server.serve_forever,daemon=True)
    thread.start()
    try:
        base=f'http://127.0.0.1:{server.server_port}'
        player=starting.home_club.squad.players[0]
        for path,expected in ((f'/api/history/player/{player.id}','player'),
                              (f'/api/history/club/{starting.home_club.id}','club'),
                              ('/api/history/competition/dev-premier','competition')):
            with urlopen(base+path,timeout=20) as r:
                obj=json.load(r)
                assert r.status==200 and obj['type']==expected and obj['source']=='verified-career-ledgers'
        for path,code in (('/api/history/player/not-a-player',404),
                          ('/api/history/club/northbridge?season=1900%2F01',404),
                          ('/api/history/competition/dev-premier?offset=-1',400)):
            with pytest.raises(HTTPError) as exc: urlopen(base+path,timeout=20)
            assert exc.value.code == code
        for path in ('/portable/history.js','/portable/history.css','/portable/index.html'):
            with urlopen(base+path,timeout=20) as r:
                assert r.status==200 and len(r.read())>50
    finally:
        server.shutdown();server.server_close();thread.join(timeout=8)
