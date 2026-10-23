"""TS-UI-10: Club Info is universal, live and grounded in verified records."""
from __future__ import annotations

from copy import copy
from dataclasses import replace
from datetime import date
from pathlib import Path
from types import SimpleNamespace
import json

import pytest

from football_manager.dev_ui.session import DevelopmentSession
from football_manager.domain.season_cycle import SeasonReport
from football_manager.ui_shell.career_history import club_career_read_model


@pytest.fixture(scope="module")
def career():
    return DevelopmentSession()


def test_live_profile_uses_real_league_competitions_and_next_game(career):
    club_id = career.home_club.id
    before = (len(career._career.reports), len(career._world.results), career.current_date)
    data = club_career_read_model(career, club_id)
    assert data["id"] == club_id and data["source"] == "verified-career-ledgers"
    assert data["live"]["league"]["id"] == "dev-premier"
    assert data["live"]["league"]["points"] == 0
    assert "fa-cup" in {c["id"] for c in data["live"]["competitions"]}
    assert data["live"]["next_fixture"]["date"] >= career.current_date.isoformat()
    assert data["trophies"] == []
    assert before == (len(career._career.reports), len(career._world.results), career.current_date)


def test_other_clubs_use_same_read_model(career):
    visiting = next(cid for cid in career._world_club_names if cid != career.home_club.id
                    and any(cid in edition.participant_club_ids for edition in career._world.leagues.values()))
    data = club_career_read_model(career, visiting)
    assert data["id"] == visiting and data["live"]["league"]
    assert data["live"]["date"] == career.current_date.isoformat()


def test_title_and_relegation_follow_confirmed_report_not_theme(career):
    club_id = career.home_club.id
    # Simulate a completed season report and a new actual competition roster.
    report = SeasonReport(
        season_label="2026/27",
        league_tables={"dev-premier": (club_id,)},
        champions={"champions-league": club_id},
        promoted={}, relegated={"dev-premier": (club_id,)},
        next_tiers={}, europe={}, external_national_league_promotions=(), fixture_count=0,
    )
    old_world, old_reports = career._world, career._career.reports
    try:
        new_leagues = {
            cid: SimpleNamespace(participant_club_ids=tuple(
                (x for x in edition.participant_club_ids if x != club_id)
            ) if cid == "dev-premier" else tuple(edition.participant_club_ids) + (club_id,)
                if cid == "dev-championship" else edition.participant_club_ids)
            for cid, edition in old_world.leagues.items()
        }
        new_world = SimpleNamespace(
            season_label="2027/28", leagues=new_leagues, cups={}, staged={},
            results={}, fixtures={}, strengths=old_world.strengths,
            standings=lambda lid: (SimpleNamespace(
                club_id=club_id,position=15,played=5,won=1,drawn=2,lost=2,
                goals_for=7,goals_against=9,goal_difference=-2,points=5),)
                if lid == "dev-championship" else (),
        )
        career._world = new_world
        career._career.reports = [*old_reports, report]
        data = club_career_read_model(career, club_id)
        assert data['live']['league']['id'] == 'dev-championship'
        assert data['live']['league']['position'] == 15
        assert data['live']['league']['points'] == 5
        assert data['seasons'][1]['relegated'] == ['dev-premier']
        assert data['trophies'] == [{
            'season': '2026/27', 'id': 'champions-league',
            'name': 'Champions League'}]
        assert data['seasons'][0]['complete'] is False
    finally:
        career._world = old_world
        career._career.reports = old_reports


def test_archive_has_no_fabricated_histories_and_is_keyed_by_id():
    base = Path(__file__).resolve().parents[1]
    archive = json.loads((base/'frontend/portable/data/club-historical-records.json').read_text())
    assert archive['schema_version'] == 1 and archive['clubs'] == {}
    js = (base/'frontend/portable/club_info.js').read_text()
    assert 'seed.honours' in js and 'd.trophies' in js
    assert 'seed.timeline' in js and 'd.seasons' in js
    assert 'stadium_capacity' not in js and 'Stadium capacity' not in js
    assert 'data-fm-club-theme' in js and 'paintWithin' in js
    assert 'data-ci-squad' in js


def test_frontend_navigation_uses_club_info_for_view_club():
    root=Path(__file__).resolve().parents[1]/'frontend/portable'
    js=(root/'portable.js').read_text()
    html=(root/'index.html').read_text()
    assert "navigate('Club Info',false,{club:id})" in js
    assert "clubSquad:(id)=>navigate('Club Profile'" in js
    assert 'club_info.js' in html and 'club_info.css' in html


def test_promotion_updates_competition_without_overwriting_history(career):
    club_id=career.home_club.id
    original_world,original_reports=career._world,career._career.reports
    try:
        league_rows={cid:SimpleNamespace(participant_club_ids=(club_id,) if cid=='dev-premier' else ())
                     for cid in original_world.leagues}
        career._world=SimpleNamespace(season_label='2028/29',leagues=league_rows,
            cups={},staged={},fixtures={},results={},strengths={},
            standings=lambda league: (SimpleNamespace(club_id=club_id,position=7,played=11,
                won=6,drawn=2,lost=3,goals_for=18,goals_against=15,
                goal_difference=3,points=20),))
        career._career.reports=[SeasonReport('2027/28',{'dev-championship':(club_id,)},{},
            {'dev-championship':(club_id,)},{},{},{},(),0)]
        club=club_career_read_model(career,club_id)
        assert club['live']['league']['id']=='dev-premier'
        assert club['live']['league']['played']==11
        assert club['seasons'][1]['promoted']==['dev-championship']
        assert club['seasons'][1]['league'].endswith('Championship')
    finally:
        career._world=original_world
        career._career.reports=original_reports


def test_http_serves_dynamic_club_and_optional_archive(career):
    from threading import Thread
    from urllib.request import urlopen
    from football_manager.ui_shell.server import create_server
    server=create_server(port=0,session=career)
    t=Thread(target=server.serve_forever,daemon=True);t.start()
    base=f'http://127.0.0.1:{server.server_port}'
    try:
        for route in ('/portable/club_info.js','/portable/club_info.css',
                      '/portable/data/club-historical-records.json'):
            with urlopen(base+route,timeout=10) as response:
                assert response.status==200 and len(response.read())>10
        with urlopen(base+f'/api/history/club/{career.home_club.id}',timeout=10) as response:
            payload=json.load(response)
            assert payload['type']=='club' and payload['live']['season']=='2026/27'
    finally:
        server.shutdown();server.server_close();t.join(timeout=5)
