"""TS-22: real statistics, read-only profiles, migrations and safe match routing.

Required tests use only Python/pytest. Browser checks are supplementary; neither
Node nor npm is needed to play, verify the package, or run this module.
"""
from __future__ import annotations

from copy import deepcopy
from dataclasses import asdict, fields, replace
from datetime import date
from pathlib import Path
from threading import Thread
from urllib.error import HTTPError
from urllib.request import Request, urlopen
import gzip
import json

import pytest

from football_manager.dev_ui.session import DevelopmentSession
from football_manager.domain.enums import Position
from football_manager.domain.player_ratings import CurrentRatingContext
from football_manager.domain.roles import roles_for_position
from football_manager.domain.season_statistics import SeasonPlayerStatistics, SeasonStatisticsLedger
from football_manager.persistence import SQLiteSaveRepository, load_manager_career, save_manager_career, SaveIntegrityError
from football_manager.persistence.session_codec import capture_manager_graph, restore_manager_graph, GRAPH_VERSION
from football_manager.services.opening_balance import BALANCE_ID, preview_opening_balance, apply_opening_balance
from football_manager.services.season_statistics import player_statistics, statistics_options, record_season_statistics, migrate_statistics
from football_manager.ui_shell.application import GameApplication
from football_manager.ui_shell.club_profiles import club_profile_read_model
from football_manager.ui_shell.home_competition import home_competition_read_model
from football_manager.ui_shell.match import prematch_read_model
from football_manager.ui_shell.models import UIRosterAdmin, squad_read_model
from football_manager.ui_shell.player_profiles import profile_graphics, player_profile_read_model
from football_manager.ui_shell.progression import advance_day, simulate_until
from football_manager.ui_shell.runtime import UIRuntime
from football_manager.ui_shell.server import create_server


@pytest.fixture(scope='module')
def initial():
    return DevelopmentSession()


@pytest.fixture(scope='module')
def played(initial):
    session = deepcopy(initial)
    first = session._active_match.fixture.fixture_id
    lineups = (session.home_lineup, session.away_lineup)
    result = session.quick_simulate()
    return session, first, result, lineups


@pytest.fixture(scope='module')
def legacy(tmp_path_factory):
    directory = tmp_path_factory.mktemp('ts22-v5')
    path = directory / 'legacy.sqlite3'
    source = Path('tests/fixtures/ts2111_manager_v5_before.sqlite3.gz')
    path.write_bytes(gzip.decompress(source.read_bytes()))
    repo = SQLiteSaveRepository(path)
    slot = next(s for s in repo.list_slots() if s.kind == 'manager_career')
    return load_manager_career(repo, slot.slot_id).session


@pytest.mark.parametrize('key', [f.name for f in fields(SeasonPlayerStatistics)])
def test_negative_statistics_are_rejected(key):
    with pytest.raises(ValueError):
        SeasonPlayerStatistics(**{key: -1})


@pytest.mark.parametrize('kwargs', [
    {'appearances': True}, {'minutes': 1.5}, {'starts': 1}, {'minutes': 121, 'appearances': 1},
    {'shots': 1, 'shots_on_target': 2}, {'passes_attempted': 4, 'passes_completed': 5},
    {'rating_total': float('nan')}, {'xg': float('inf')}, {'clean_sheets': 1},
])
def test_invalid_counts_and_ratios_rejected(kwargs):
    with pytest.raises(ValueError):
        SeasonPlayerStatistics(**kwargs)


def test_weighted_pass_percentage_and_rating_not_average_of_percentages():
    a = SeasonPlayerStatistics(appearances=1, minutes=90, passes_attempted=100, passes_completed=90, rating_total=7)
    b = SeasonPlayerStatistics(appearances=1, minutes=20, passes_attempted=10, passes_completed=1, rating_total=6)
    total = a.plus(b).view()
    assert total['pass_completion'] == 82.7
    assert total['average_match_rating'] == 6.5
    assert total['xa'] is total['tackles'] is None


def test_new_career_unplayed_stats_are_zero_but_missing_rates_are_not(initial):
    data = squad_read_model(initial)
    assert data['roster_capabilities']['season_player_ledger']
    for row in data['roster']:
        stats = row['season_stats']
        assert stats['appearances'] == stats['goals'] == stats['minutes'] == 0
        assert stats['xg'] == 0
        assert stats['pass_completion'] is stats['average_match_rating'] is stats['xa'] is None
        assert stats['coverage']['complete_season'] is True
    assert set(data['statistics']['unsupported']) == {'xa', 'tackles'}


def test_actual_game_updates_both_clubs_and_only_participants(played):
    session, fid, result, lineups = played
    registry = session._world_squads
    cid = session._world.fixtures[fid].competition_id
    participants = {s.player_id for s in result.player_statistics if s.minutes > 0}
    starting = {e.player.id for team in lineups for e in team.starters}
    for team in lineups:
        for p in registry.clubs[team.club_id].squad.players:
            value = player_statistics(registry, p.id, competition=cid)
            raw = next((x for x in result.player_statistics if x.player_id == p.id), None)
            assert value['appearances'] == int(p.id in participants)
            assert value['starts'] == int(p.id in starting and p.id in participants)
            for key in ('minutes','goals','assists','shots','shots_on_target','passes_attempted','passes_completed','yellow_cards','red_cards'):
                assert value[key] == (getattr(raw, key) if raw and raw.minutes else 0)
            assert value['xg'] == (round(raw.xg, 2) if raw and raw.minutes else 0)
    assert f'{registry.season_label}:{fid}' in registry.statistics.recorded_fixtures
    assert set(registry.usage).issuperset(participants)


def test_team_totals_match_engine_and_shootout_not_included(played):
    session, fid, result, lineups = played
    cid = session._world.fixtures[fid].competition_id
    for club_id, raw in ((result.home_club_id, result.statistics_home), (result.away_club_id, result.statistics_away)):
        rows = [player_statistics(session._world_squads, p.id, competition=cid)
                for p in session._world_squads.clubs[club_id].squad.players]
        for key in ('shots', 'shots_on_target', 'passes_attempted', 'passes_completed'):
            assert sum(row[key] for row in rows) == getattr(raw, key)
        expected_goals = result.home_goals if club_id == result.home_club_id else result.away_goals
        assert sum(row['goals'] for row in rows) == expected_goals


def test_duplicate_statistics_record_is_noop(played):
    session, fid, result, lineups = played
    before = deepcopy(session._world_squads.statistics)
    assert record_season_statistics(session._world, fid, result, lineups) is False
    assert session._world_squads.statistics == before


def test_clean_sheet_definition_no_credit_for_unused_bench_or_attackers(initial, played):
    session = deepcopy(initial)
    _, fid, result, lineups = played
    # Use a zero-conceded result for the definition test; stats remain actual.
    changed = replace(result, home_goals=0, away_goals=0, aggregate_home_goals=0, aggregate_away_goals=0,
                      regulation_home_goals=0, regulation_away_goals=0, extra_time_home_goals=0, extra_time_away_goals=0,
                      winner_club_id=None, decision='draw', penalties_home=0, penalties_away=0, penalty_kicks=(), goals=(),
                      statistics_home=replace(result.statistics_home, goals=0), statistics_away=replace(result.statistics_away, goals=0),
                      player_statistics=tuple(replace(p,goals=0,assists=0) for p in result.player_statistics))
    record_season_statistics(session._world, fid, changed, lineups)
    cid = session._world.fixtures[fid].competition_id
    pos = {e.player.id: t.formation.slot(e.slot_id).position.value for t in lineups for e in t.starters}
    pos.update({e.player_in_id: e.position for e in result.substitutions})
    for stat in result.player_statistics:
        expected = int(stat.minutes >= 60 and pos.get(stat.player_id) in {'GK','CB','LCB','RCB','RB','LB','RWB','LWB'})
        assert player_statistics(session._world_squads, stat.player_id, competition=cid)['clean_sheets'] == expected


def test_stat_failure_rolls_back_score_usage_and_players(initial, monkeypatch):
    from football_manager.services import season_statistics as service
    session = deepcopy(initial)
    before = deepcopy(session)
    real = service.record_season_statistics
    def fail(*args, **kwargs):
        real(*args, **kwargs)
        raise RuntimeError('statistics fault injection')
    monkeypatch.setattr(service, 'record_season_statistics', fail)
    with pytest.raises(RuntimeError, match='fault injection'):
        session.quick_simulate()
    assert session._world.to_dict() == before._world.to_dict()
    assert session._world_squads == before._world_squads
    assert session.dressing_room == before.dressing_room
    assert session.last_result == before.last_result and session._seed == before._seed


def test_background_matches_use_same_ledger(initial):
    ledger = initial._world_squads.statistics
    assert len(ledger.recorded_fixtures) > 10
    for tier in (2,3,4):
        clubs = [cid for cid,i in initial._world_squads.identities.items() if i.tier == tier]
        assert any(player_statistics(initial._world_squads, p.id)['appearances'] > 0
                   for cid in clubs for p in initial._world_squads.clubs[cid].squad.players)


def test_new_season_zeros_current_retains_past(played):
    session = deepcopy(played[0]); registry = session._world_squads
    pid = session.home_lineup.starting_players[0].id
    old = player_statistics(registry, pid)
    previous = registry.season_label
    registry.adopt_season('2027/28', {cid:i.tier for cid,i in registry.identities.items() if i.tier})
    registry.statistics.start_season('2027/28', date(2027,7,1), complete=True)
    assert player_statistics(registry, pid)['appearances'] == 0
    assert player_statistics(registry, pid, season=previous) == old
    assert statistics_options(registry)['seasons'][0] == '2027/28'


def test_save_current_version_roundtrip_has_exact_stats_and_deterministic_continuation(played, tmp_path):
    session = deepcopy(played[0]); repo = SQLiteSaveRepository(tmp_path/'save.sqlite3')
    save_manager_career(repo, slot_id='ts22', display_name='TS22', session=session, expected_revision=0)
    saved = repo.load('ts22').document
    assert next(s.version for s in saved.sections if s.name=='manager_state') == GRAPH_VERSION == 16
    loaded = load_manager_career(repo,'ts22').session
    assert loaded._world_squads.statistics == session._world_squads.statistics
    assert loaded._world_squads.balance_adjustments == session._world_squads.balance_adjustments
    assert loaded._world.football_world is loaded._world_squads
    simulate_until(session,date(2026,8,24));simulate_until(loaded,date(2026,8,24))
    assert loaded._world.to_dict() == session._world.to_dict()
    assert loaded._world_squads == session._world_squads
    assert loaded.dressing_room == session.dressing_room


def test_legacy_v5_preserves_verified_basics_and_explicit_missing_details(legacy):
    registry=legacy._world_squads
    assert not registry.statistics.complete_seasons[registry.season_label]
    assert registry.statistics.coverage_from[registry.season_label] == legacy.current_date
    for pid,usage in registry.usage.items():
        stats=player_statistics(registry,pid)
        assert stats['appearances']==usage.appearances
        assert stats['minutes']==usage.minutes
        assert stats['goals']==usage.goals
        if usage.appearances:
            assert stats['shots'] is stats['xg'] is stats['pass_completion'] is None
    assert not registry.balance_adjustments
    assert preview_opening_balance(legacy)['eligible']


def test_legacy_migration_never_guesses_competition_history(legacy):
    registry=legacy._world_squads
    pid=legacy.home_lineup.starting_players[0].id
    stats=player_statistics(registry,pid,competition='dev-premier')
    assert stats['appearances'] is stats['minutes'] is stats['goals'] is None
    assert stats['coverage']['scope']=='recorded_matches'


def test_new_opening_rating_is_midtable_but_formulas_and_roles_unchanged(initial):
    # Use the actual initial assigned XI, not generic primary-position averages.
    ratings=[p['ovr'] for p in squad_read_model(initial)['starters']]
    assert 80 <= sum(ratings)/len(ratings) <= 81
    assert preview_opening_balance(initial)['applied']
    with pytest.raises(ValueError,match='already applied'):
        apply_opening_balance(deepcopy(initial),BALANCE_ID)


def test_legacy_balance_once_keeps_states_results_others_and_modified_players(legacy):
    session=deepcopy(legacy)
    eligible=preview_opening_balance(session)['players'];assert len(eligible)==18
    protected=session.home_club.squad.get(eligible[0]['id'])
    protected.attributes=replace(protected.attributes,mental=replace(protected.attributes.mental,vision=protected.attributes.mental.vision+1))
    protection=deepcopy(protected)
    other_clubs={cid:deepcopy(c) for cid,c in session._world_squads.clubs.items() if cid!=session.home_club.id}
    states={p.id:deepcopy(p.state) for p in session.home_club.squad.players}
    scores=dict(session._world.results)
    before={p.id:deepcopy(p.attributes) for p in session.home_club.squad.players}
    with pytest.raises(ValueError,match='confirmation'):
        apply_opening_balance(session,'yes')
    result=apply_opening_balance(session,BALANCE_ID)
    assert len(result['player_ids'])==17
    assert protected==protection
    assert session._world.results==scores
    for p in session.home_club.squad.players:
        assert p.state==states[p.id]
        if p.id not in result['player_ids']:assert p.attributes==before[p.id]
    for cid,club in other_clubs.items(): assert session._world_squads.clubs[cid]==club
    with pytest.raises(ValueError,match='already applied'):apply_opening_balance(session,BALANCE_ID)


@pytest.mark.parametrize('position',list(Position))
def test_graphics_use_valid_attributes_and_exact_engine_role_weights(initial,position):
    player=next(p for p in initial.home_club.squad.players if (p.primary_position is Position.GK)==(position is Position.GK))
    role=roles_for_position(position)[0]
    graph=profile_graphics(player,position,role.role_id)
    assert graph['scale']==[0,100]
    assert len(graph['general'])==6
    for axis in graph['general']:
        values=[getattr(getattr(player.attributes,path.split('.')[0]),path.split('.')[1]) for path in axis['attributes']]
        assert axis['value']==round(sum(values)/len(values),1)
    assert {x['attribute']:x['weight'] for x in graph['role']['axes']}==dict(sorted(role.attribute_weights,key=lambda x:(-x[1],x[0]))[:6])
    assert not graph['evolution']['available']


def test_invalid_role_and_unknown_player_cannot_change_anything(initial):
    player=initial.home_club.squad.players[0]
    with pytest.raises(ValueError):
        profile_graphics(player,Position.GK,roles_for_position(Position.ST)[0].role_id)
    with pytest.raises(KeyError):player_profile_read_model(initial,'riverside',player.id)


@pytest.mark.parametrize('tier',[1,2,3,4])
def test_same_rival_profile_works_for_all_four_divisions_without_mutation(initial,tier):
    cid=next(cid for cid,i in initial._world_squads.identities.items() if i.tier==tier and cid!='northbridge')
    before=capture_manager_graph(initial)
    view=club_profile_read_model(initial,cid)
    assert view['readonly'] and view['available'] and len(view['roster'])==22
    assert view['information']['stadium'] is view['information']['capacity'] is view['information']['city'] is None
    assert view['information']['league']['position']>=1
    for row in view['roster']:
        assert row['id'] in {p.id for p in initial._world_squads.clubs[cid].squad.players}
        assert row['season_stats']==player_statistics(initial._world_squads,row['id'])
    assert capture_manager_graph(initial)==before


def test_nonpersistent_cup_club_does_not_get_a_fake_squad(initial):
    cid=next(cid for cid in initial._world_club_names if cid not in initial._world_squads.clubs)
    before=len(initial._world_squads.clubs)
    view=club_profile_read_model(initial,cid)
    assert view['available'] is False and view['roster']==[]
    assert len(initial._world_squads.clubs)==before
    with pytest.raises(KeyError):club_profile_read_model(initial,'not-a-club')


def test_pre_match_ratings_in_real_assigned_contexts(initial):
    view=prematch_read_model(initial,UIRosterAdmin())
    own=squad_read_model(initial)
    rows={p['id']:p for p in own['starters']}
    for side in ('home','away'):
        club=view[side]
        for p in club['starters']:
            assert 0<=p['x']<=100 and 0<=p['y']<=100
            assert 0<=p['condition']<=100 and 0<p['act']<=100
            if p['id'] in rows:
                assert p['act']==rows[p['id']]['act']
        assert all(p['act'] is not None and p['condition'] is not None for p in club['bench'])


def test_home_selection_default_local_table_and_cup_draw_not_predicted(initial):
    before=capture_manager_graph(initial)
    home=home_competition_read_model(initial)
    assert home['id']==initial._world.fixtures[initial._active_match.fixture.fixture_id].competition_id
    assert home['mode']=='table' and any(r['managed'] for r in home['table'])
    cup=home_competition_read_model(initial,'fa-cup')
    assert cup['mode']=='knockout' and cup['next_tie'] is None and 'draw pending' in cup['status']
    uefa=home_competition_read_model(initial,'champions-league')
    assert uefa['mode']=='table' and uefa['phase']=='League phase'
    with pytest.raises(KeyError):home_competition_read_model(initial,'not-a-competition')
    assert capture_manager_graph(initial)==before


def test_http_end_to_end_stats_idempotency_save_load_and_readonly(initial,tmp_path):
    server=create_server(port=0,session=deepcopy(initial),save_repository=SQLiteSaveRepository(tmp_path/'http.sqlite3'))
    t=Thread(target=server.serve_forever,daemon=True);t.start()
    host=f'http://127.0.0.1:{server.server_port}'
    def request(path,payload=None):
        req=Request(host+path,data=json.dumps(payload).encode() if payload is not None else None,
                    headers={'Content-Type':'application/json'})
        with urlopen(req,timeout=40) as response:return json.load(response)
    try:
        before=request('/api/match');fid=before['match']['fixture_id']
        actual=request('/api/match',{'action':'quick_sim','fixture_id':fid})
        assert actual['status']=='finished'
        rt=server.RequestHandlerClass.runtime
        stats=deepcopy(rt.session._world_squads.statistics)
        assert request('/api/match',{'action':'quick_sim','fixture_id':fid})==actual
        assert rt.session._world_squads.statistics==stats
        roster=request('/api/squad')['roster']
        assert any(p['season_stats']['minutes']>0 for p in roster)
        other=request('/api/clubs/'+before['away']['id'])
        assert other['readonly'] and any(p['season_stats']['appearances'] for p in other['roster'])
        details=request('/api/clubs/'+before['away']['id']+'/players/'+other['roster'][0]['id'])
        assert len(details['graphics']['general'])==6
        request('/api/career/save',{'slot_id':'s22','display_name':'S22','expected_revision':0})
        request('/api/progression',{'action':'advance_day'})
        request('/api/career/load',{'slot_id':'s22'})
        assert rt.session._world_squads.statistics==stats
        assert request('/api/match')['status']=='finished'
        assert request('/api/match',{'action':'quick_sim','fixture_id':fid})==actual
        assert rt.session._world_squads.statistics==stats
        for url in ('/api/clubs/riverside','/api/clubs/riverside/players/northbridge-1'):
            with pytest.raises(HTTPError) as err:request(url,{'action':'edit'})
            assert err.value.code in (403,404)
        with pytest.raises(HTTPError):request('/api/clubs/no-club')
    finally:server.shutdown();server.server_close();t.join(timeout=5)


def test_portable_assets_use_shared_views_and_no_node_or_popups():
    root=Path('frontend')
    shell=(root/'portable/portable.js').read_text(encoding='utf-8')
    match=(root/'portable/match.js').read_text(encoding='utf-8')
    roster=(root/'public/squad/roster.js').read_text(encoding='utf-8')
    charts=(root/'public/squad/presentation.js').read_text(encoding='utf-8')
    assert 'window.open(' not in shell and 'window.close(' not in match and 'window.opener' not in match
    assert 'location.replace(url)' in shell and "'popstate'" in shell
    assert 'fm-open-club' in match and 'fm-match-return' in match
    assert 'playerMetrics(p)' in match and 'arrangePitches' in match
    assert 'data-roster-more' in roster and 'data-roster-expand' in roster
    assert '<svg' in charts and 'profile_graphics' not in charts
    assert 'home_competition.js' in (root/'portable/index.html').read_text(encoding='utf-8')


def test_immutable_totals_can_be_shared_by_transaction_snapshots():
    from dataclasses import FrozenInstanceError
    total = SeasonPlayerStatistics(appearances=1, minutes=90, goals=2)
    clone = deepcopy(total)
    assert clone is total
    assert total.plus(SeasonPlayerStatistics(appearances=1, minutes=30)).minutes == 120
    assert total.minutes == 90
    with pytest.raises(FrozenInstanceError):
        total.minutes = 80


@pytest.mark.parametrize('field', ['statistics', 'balance_adjustments'])
def test_new_v6_missing_fields_are_corrupt_not_silently_migrated(initial, field):
    graph = capture_manager_graph(initial)
    node = next(n for n in graph['nodes'] if n.get('class') == 'football_manager.domain.football_world:FootballWorld')
    del node['fields'][field]
    with pytest.raises(SaveIntegrityError):
        restore_manager_graph(graph)


@pytest.mark.parametrize('win', [True, False])
def test_home_knockout_result_and_pending_draw_are_real(initial, win):
    session = deepcopy(initial)
    card = home_competition_read_model(session, 'carabao-cup')
    assert card['mode'] == 'knockout' and card['tie']['managed']
    assert card['status'] == 'Your tie' and card['next_tie'] is None
    fid = card['tie']['legs'][0]['id']
    fixture = session._world.fixtures[fid]
    home_win = (fixture.home_club_id == session.home_club.id) == win
    session._world.record_result(fid, 2 if home_win else 0, 0 if home_win else 2)
    card = home_competition_read_model(session, 'carabao-cup')
    assert card['tie']['complete']
    assert card['status'] == ('Qualified' if win else 'Eliminated')
    assert card['next_status'] == ('Next opponent: pending draw.' if win else None)
    assert card['next_tie'] is None


def test_opening_balance_decision_survives_complete_save(legacy, tmp_path):
    session = deepcopy(legacy)
    apply_opening_balance(session, BALANCE_ID)
    repo = SQLiteSaveRepository(tmp_path/'balanced.sqlite3')
    save_manager_career(repo, slot_id='balanced', display_name='Balanced', session=session, expected_revision=0)
    loaded = load_manager_career(repo, 'balanced').session
    assert loaded._world_squads.balance_adjustments == session._world_squads.balance_adjustments
    assert loaded.home_club.squad == session.home_club.squad
    assert preview_opening_balance(loaded)['applied']
    with pytest.raises(ValueError, match='already applied'):
        apply_opening_balance(loaded, BALANCE_ID)
