"""UI-3.3 contracts for the read-only Python competition centre."""
from __future__ import annotations

import json
from pathlib import Path
from threading import Thread
from urllib.error import HTTPError
from urllib.request import urlopen

import pytest

from football_manager.dev_ui.session import DevelopmentSession
from football_manager.ui_shell.competitions import competition_options, competition_read_model
from football_manager.ui_shell.server import create_server

ROOT = Path(__file__).resolve().parents[1]


@pytest.fixture(scope="module")
def session():
    return DevelopmentSession()


def test_club_competitions_only_are_shown_and_rest_reserved_for_future_world_view(session):
    model = competition_options(session)
    world = session._world
    expected = set(world.leagues) | set(world.cups) | set(world.staged)
    visible = model['competitions']
    other = model['other_competitions']
    assert {c['id'] for c in visible} | {c['id'] for c in other} == expected
    assert set(c['id'] for c in visible).isdisjoint(c['id'] for c in other)
    assert len(visible) + len(other) == 10
    assert {c['id'] for c in visible} == {
        'dev-premier', 'fa-cup', 'carabao-cup', 'champions-league'
    }
    assert all(c['managed'] for c in visible)
    assert not any(c['managed'] for c in other)
    assert model['source'] == 'python-world-runner'
    assert model['persistent'] is False
    assert model['season'] == world.season_label


def test_fa_cup_is_a_club_competition_even_before_northbridge_draw(session):
    """The club joins a later cup round and cannot disappear from its own menu."""
    cup = session._world.cups['fa-cup']
    assert not any(session.home_club.id in (tie.club_a_id, tie.club_b_id)
                   for plan in cup.plans for tie in plan.ties)
    rule = next(rule for rule in cup.rounds if session.home_club.id in rule.entrants)
    model = competition_read_model(session, 'fa-cup')
    assert model['managed_entry_round_id'] == rule.round_id
    assert model['managed_entry_round_label'] == rule.label
    assert not model['bracket_prediction_supported']


@pytest.mark.parametrize('cid', ['dev-premier', 'dev-championship', 'dev-league-one', 'dev-league-two'])
def test_league_all_club_tables_and_full_matchdays_not_managed_only(session, cid):
    world = session._world
    data = competition_read_model(session, cid)
    edition = world.leagues[cid]
    assert data['kind'] == 'league'
    assert len(data['table']) == len(edition.participant_club_ids)
    assert len(data['rounds']) == (38 if cid == 'dev-premier' else 46)
    assert sum(len(r['matches']) for r in data['rounds']) == len(edition.fixtures)
    assert all(len(r['matches']) == len(edition.participant_club_ids)//2 for r in data['rounds'])
    actual = world.standings(cid)
    for row, real in zip(data['table'], actual):
        assert (row['club_id'], row['points'], row['gd']) == (real.club_id, real.points, real.goal_difference)
    first = data['rounds'][0]['matches'][0]
    raw = world.fixtures[first['id']]
    assert first['kickoff'] == raw.kickoff.isoformat()
    assert first['source'] == raw.source.value
    assert data['knockout'] == []


@pytest.mark.parametrize('cid', ['fa-cup', 'carabao-cup'])
def test_cup_bracket_only_has_actual_drawn_ties_no_fake_future(session, cid):
    cup = session._world.cups[cid]
    data = competition_read_model(session, cid)
    assert data['kind'] == 'cup'
    assert not data['rounds'] and not data['table']
    assert len(data['knockout']) == len(cup.rounds)
    assert sum(r['drawn'] for r in data['knockout']) == len(cup.plans)
    assert all(not r['ties'] and not r['matches'] for r in data['knockout'] if not r['drawn'])
    for plan, exp in zip(cup.plans, data['knockout']):
        assert {t['id'] for t in exp['ties']} == {t.tie_id for t in plan.ties}
        assert len(exp['matches']) == len(plan.fixtures)
        assert exp['source'] == plan.source.value
    assert data['fixed_bracket'] is False and data['bracket_prediction_supported'] is False


@pytest.mark.parametrize('cid, expected_matches,expected_matchdays', [
    ('champions-league', 144, 8), ('europa-league', 144, 8), ('conference-league', 108, 6),
])
def test_uefa_swiss_phase_has_36_clubs_all_matches_and_unfabricated_knockout(session, cid, expected_matches, expected_matchdays):
    data = competition_read_model(session, cid)
    assert data['kind'] == 'multi'
    assert data['format'] == 'uefa'
    assert [s['mode'] for s in data['stages']] == ['table', 'bracket']
    assert len(data['table']) == 36
    assert len(data['rounds']) == expected_matchdays
    assert all(len(r['matches']) == 18 for r in data['rounds'])
    assert sum(len(r['matches']) for r in data['rounds']) == expected_matches
    assert len(data['knockout']) == 5
    assert all(not r['drawn'] and not r['ties'] for r in data['knockout'])
    assert data['bracket_prediction_supported'] is False


def test_efl_trophy_has_16_actual_groups_and_each_matchday_all_32_games(session):
    data = competition_read_model(session, 'efl-trophy')
    assert data['kind'] == 'multi' and data['format'] == 'efl-trophy'
    assert len(data['groups']) == 16
    assert all(len(g['table']) == 4 for g in data['groups'])
    assert len(data['table']) == 4
    assert [len(r['matches']) for r in data['rounds']] == [32,32,32]
    assert all(not r['drawn'] for r in data['knockout'])


def test_penalty_result_and_tie_winner_are_separate_from_regulation_score():
    session = DevelopmentSession()
    cup = competition_read_model(session, 'carabao-cup')
    tie = next(t for r in cup['knockout'] for t in r['ties'] if t['managed'])
    match = tie['legs'][0]
    session._world.record_result(match['id'], 1, 1, penalties_home=3, penalties_away=4, resolver='managed')
    winner = match['away_id']
    refreshed = competition_read_model(session, 'carabao-cup')
    resolved = next(t for r in refreshed['knockout'] for t in r['ties'] if t['id']==tie['id'])
    assert resolved['complete'] is True
    assert resolved['winner_id'] == winner
    assert resolved['aggregate'] == {'a': 1, 'b': 1}
    assert resolved['legs'][0]['score'] == {'home': 1, 'away': 1}
    assert resolved['legs'][0]['penalties'] == {'home': 3, 'away': 4}


def test_http_api_registers_all_competitions_and_rejects_unknown(session):
    server = create_server(port=0, session=session)
    server.timeout = 0.15
    t = Thread(target=server.serve_forever, daemon=True)
    t.start()
    base=f'http://127.0.0.1:{server.server_port}'
    try:
        with urlopen(base+'/api/competitions', timeout=10) as response:
            index=json.load(response)
            assert len(index['competitions'])==4
            assert len(index['other_competitions'])==6
        with urlopen(base+'/api/competitions/dev-premier', timeout=10) as response:
            detail=json.load(response)
            assert detail['id']=='dev-premier'
            assert len(detail['rounds'][0]['matches'])==10
        with urlopen(base+'/api/competitions/fa-cup', timeout=10) as response:
            detail=json.load(response)
            assert detail['kind']=='cup'
        with pytest.raises(HTTPError) as unknown:
            urlopen(base+'/api/competitions/unregistered',timeout=10)
        assert unknown.value.code==404
        with urlopen(base+'/portable/competitions.js',timeout=10) as response:
            assert b'FMCompetitions' in response.read()
        with urlopen(base+'/portable/competitions.css',timeout=10) as response:
            assert b'cmp-bracket-board' in response.read()
    finally:
        server.shutdown()
        server.server_close()
        t.join(timeout=3)


def test_frontend_routes_and_true_bracket_links_static_safety():
    html=(ROOT/'frontend/portable/index.html').read_text(encoding='utf-8')
    js=(ROOT/'frontend/portable/competitions.js').read_text(encoding='utf-8')
    base=(ROOT/'frontend/portable/portable.js').read_text(encoding='utf-8')
    assert '<script src="competitions.js" defer></script>' in html
    assert '<link rel="stylesheet" href="competitions.css" />' in html
    assert 'window.FMCompetitions?.mount' in base
    assert 'if(!tie.complete||!tie.winner_id)continue' in js
    assert 'Opponents not known' in js
    assert 'All clubs' in js
    assert "data-cmp-zoom" in js
    assert 'cmp-bilateral-board' in js
    assert 'cmp-bilateral-final-label' in js
    assert "bracketWing(r,i,'left'" in js
    assert "bracketWing(r,i,'right'" in js
    assert 'cmp-confirmed-link' in js
    assert 'cmp-unresolved-stub' in js
    assert "zoomLevel=clamp(zoomLevel+Number(btn.dataset.cmpZoom)" in js
    assert 'index?.competitions' in js
    assert 'index?.other_competitions' in js
    assert 'data-cmp-competition-select' in js
