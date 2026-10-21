"""TS-28.3 + 28.4: factual recognition and institutional Club Info tests."""
from copy import deepcopy
from dataclasses import replace
from datetime import date, timedelta
from pathlib import Path

import pytest

from football_manager.dev_ui.session import DevelopmentSession
from football_manager.domain.season_statistics import SeasonPlayerStatistics
from football_manager.domain.career_recognition import IndividualAward
from football_manager.persistence.manager_career import validate_manager_session
from football_manager.persistence.session_codec import capture_manager_graph, restore_manager_graph
from football_manager.services.career_recognition import award_season, record_rating_snapshots
from football_manager.ui_shell.career_history import (
    player_career_read_model, club_career_read_model, competition_career_read_model,
)
from football_manager.ui_shell.home_news import home_news_read_model


@pytest.fixture(scope='module')
def initial():
    return DevelopmentSession()


def test_initial_player_evolution_and_club_info_are_live_read_only(initial):
    registry = initial._world_squads
    pid = initial.home_club.squad.players[0].id
    before = (len(registry.rating_history), len(registry.individual_awards), initial.current_date)
    profile = player_career_read_model(initial, pid)
    assert profile['awards'] == []
    assert profile['progression'][0]['overall'] > 0
    assert profile['progression'][-1]['is_current'] is True
    assert 'Technical average' in profile['progression'][0]['indicators']
    club = club_career_read_model(initial, initial.home_club.id)
    info = club['institution']
    assert info['registered'] and info['country'] == 'England'
    assert info['league_id'] == 'dev-premier'
    assert info['finance']['transfer_budget_gbp'] >= 0
    assert len(info['facilities']['staffing_slots']) == 4
    assert len(info['top_players']) == 7
    assert info['city'] is None and info['founded'] is None
    assert 'provisional' in info['note'].lower()
    assert before == (len(registry.rating_history), len(registry.individual_awards), initial.current_date)


def make_verified_stats(session):
    registry = session._world_squads
    club = session.home_club.id
    players = session.home_club.squad.players
    ids = [p.id for p in players[:12]]
    season = registry.season_label
    cid = 'dev-premier'
    table = {}
    for index, pid in enumerate(ids):
        table[pid] = SeasonPlayerStatistics(appearances=12, starts=12, minutes=1000,
             goals=max(0, 12-index), assists=max(0, 7-index), rating_total=96-index/3,
             clean_sheets=3 if players[index].primary_position.value=='GK' else 0)
        registry.player_season_clubs.setdefault(season, {})[pid] = (club,)
    registry.statistics.seasons[season][cid] = table
    registry.statistics.complete_seasons[season] = True
    return ids


def test_awards_are_verified_deterministic_and_persistent(initial):
    session = deepcopy(initial)
    reg = session._world_squads
    ids = make_verified_stats(session)
    from types import SimpleNamespace
    report = SimpleNamespace(season_label=reg.season_label, champions={})
    count = award_season(reg, session._world, report, as_of=session.current_date)
    assert count > 4
    awards = reg.individual_awards[reg.season_label]
    assert any(a.competition_id == 'world' and a.category == 'world_player' for a in awards)
    assert any(a.competition_id == 'dev-premier' and a.category == 'goals' and a.player_id == ids[0]
               for a in awards)
    assert award_season(reg, session._world, report, as_of=session.current_date) == 0
    assert reg.individual_awards[reg.season_label] == awards
    player = player_career_read_model(session, ids[0])
    league = competition_career_read_model(session, 'dev-premier')
    club = club_career_read_model(session, session.home_club.id)
    assert player['awards'] and league['awards'] and club['awards']
    assert club['records']['goals'][0]['player_id'] == ids[0]
    assert league['records']['goals'][0]['player_id'] == ids[0]
    reg.validate()


def test_missing_or_partial_coverage_never_issues_awards(initial):
    session = deepcopy(initial)
    reg = session._world_squads
    ids = make_verified_stats(session)
    reg.statistics.complete_seasons[reg.season_label] = False
    from types import SimpleNamespace
    assert award_season(reg,session._world,SimpleNamespace(season_label=reg.season_label),as_of=session.current_date) == 0
    assert reg.individual_awards[reg.season_label] == ()


def test_multiclub_statistics_are_not_falsely_attributed(initial):
    session = deepcopy(initial)
    ids = make_verified_stats(session)
    second = next(cid for cid in session._world_squads.clubs if cid!=session.home_club.id)
    reg = session._world_squads
    reg.player_season_clubs[reg.season_label][ids[0]] = (session.home_club.id,second)
    from types import SimpleNamespace
    award_season(reg,session._world,SimpleNamespace(season_label=reg.season_label),as_of=session.current_date)
    best = next(a for a in reg.individual_awards[reg.season_label]
                if a.category=='goals' and a.competition_id=='dev-premier')
    assert best.player_id == ids[0] and best.club_id is None
    assert ids[0] not in {row['player_id'] for row in club_career_read_model(session,session.home_club.id)['records']['goals']}


def test_new_season_snapshots_are_chronological_and_bounded(initial):
    session = deepcopy(initial)
    reg = session._world_squads
    pid=session.home_club.squad.players[0].id
    count=len(reg.rating_history[pid])
    assert record_rating_snapshots(reg,session.current_date,final=True) > 0
    assert len(reg.rating_history[pid]) == count+1
    assert record_rating_snapshots(reg,session.current_date,final=True) == 0
    reg.season_label='2027/28'
    assert record_rating_snapshots(reg,session.current_date+timedelta(days=45))==0
    assert len(reg.rating_history[pid]) == count+1
    assert len({x.on_date for x in reg.rating_history[pid]})==count+1


def test_save_v22_round_trip_and_v21_migration(initial):
    graph=capture_manager_graph(initial)
    assert graph['version']==24
    restored=restore_manager_graph(graph)
    validate_manager_session(restored)
    assert restored._world_squads.rating_history==initial._world_squads.rating_history
    assert restored._world_squads.individual_awards==initial._world_squads.individual_awards
    # An actual v21 graph cannot have the new fields. The migration must
    # observe only its current state, never backfill prior years.
    graph['version']=21
    world_node=next(n for n in graph['nodes'] if n.get('class') == 'football_manager.domain.football_world:FootballWorld')
    world_node['fields'].pop('rating_history')
    world_node['fields'].pop('individual_awards')
    migrated=restore_manager_graph(graph)
    validate_manager_session(migrated)
    assert migrated._world_squads.rating_history
    assert migrated._world_squads.individual_awards=={}
    assert all(len(points)==1 for points in migrated._world_squads.rating_history.values())


def test_awards_news_only_after_completed_season(initial):
    session=deepcopy(initial)
    make_verified_stats(session)
    reg=session._world_squads
    from types import SimpleNamespace
    report=SimpleNamespace(season_label=reg.season_label,champions={})
    award_season(reg,session._world,report,as_of=session.current_date)
    session._career.reports.append(report)
    news=home_news_read_model(session)
    awarded=[x for x in news['stories'] if x['category']=='award']
    assert awarded and all(x['date'] is None and x['season']==reg.season_label for x in awarded)
    assert any(x['player_id'] for x in awarded)


def test_frontend_includes_real_charts_and_institution():
    root=Path(__file__).resolve().parents[1]
    frontend=(root/'frontend/portable/history.js').read_text()
    assert 'data-history-metric' in frontend
    assert 'data-career-type' in frontend
    assert 'institutionPanel' in frontend and 'awardPanel' in frontend
    assert 'recordsPanel' in frontend
    assert 'No verified season-end awards yet.' in frontend
