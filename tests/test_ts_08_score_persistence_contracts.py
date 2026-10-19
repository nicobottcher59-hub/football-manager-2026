"""TS-08: reject lossy scores and validate complete career archives on save."""
from __future__ import annotations

from dataclasses import replace
import json

import pytest

from football_manager.domain.calendar import ScheduledFixtureStatus
from football_manager.domain.career import WorldCareer
from football_manager.domain.knockout import KnockoutMatchResult
from football_manager.domain.league import LeagueResult
from football_manager.domain.world_runner import WorldMatchResult, WorldSeasonRunner
from football_manager.fast_simulation.models import (
    FastMatchDecision, FastMatchResult, FastPenaltyKickEvent, FastTeamStatistics,
)
from tools.stress_world_calendar import create_world


def _minimal_fast_result(*, aggregate_home: int = 2, aggregate_away: int = 1,
                         winner: str | None = 'home',
                         decision: FastMatchDecision = FastMatchDecision.REGULATION,
                         penalties_home: int = 0, penalties_away: int = 0,
                         kicks: tuple = ()) -> FastMatchResult:
    stats = FastTeamStatistics(
        possession_pct=50.0, passes_attempted=0, passes_completed=0,
        shots=0, shots_on_target=0, xg=0.0, goals=0, saves=0, fouls=0,
        yellow_cards=0, red_cards=0, corners=0,
    )
    return FastMatchResult(
        match_id='synthetic', home_club_id='home', away_club_id='away',
        home_goals=0, away_goals=0,
        aggregate_home_goals=aggregate_home, aggregate_away_goals=aggregate_away,
        winner_club_id=winner, decision=decision,
        penalties_home=penalties_home, penalties_away=penalties_away,
        regulation_home_goals=0, regulation_away_goals=0,
        extra_time_home_goals=0, extra_time_away_goals=0,
        statistics_home=stats, statistics_away=stats,
        goals=(), cards=(), substitutions=(), penalty_kicks=kicks,
        player_statistics=(),
    )


@pytest.mark.parametrize('value', [1.5, True, False, '2', None])
@pytest.mark.parametrize('field', ['home_goals', 'away_goals', 'penalties_home', 'penalties_away'])
def test_world_result_scores_must_be_nonnegative_python_integers(field, value):
    kwargs = dict(fixture_id='fixture', home_goals=1, away_goals=2)
    kwargs[field] = value
    with pytest.raises(ValueError, match='integer'):
        WorldMatchResult(**kwargs)


def test_world_load_rejects_fractional_score_without_truncating():
    saved = WorldMatchResult('fixture', 1, 2).to_dict()
    saved['home_goals'] = 1.5
    with pytest.raises(ValueError, match='integer'):
        WorldMatchResult.from_dict(saved)


def test_record_result_rejects_invalid_score_without_mutating_fixture():
    world, _ = create_world(leagues=1, seed=1808)
    fixture = next(iter(world.fixtures.values()))
    with pytest.raises(ValueError, match='integer'):
        world.record_result(fixture.fixture_id, 1.5, 0)
    assert world.results == {}
    assert world.fixtures[fixture.fixture_id].status is ScheduledFixtureStatus.SCHEDULED


def test_loading_saved_world_cannot_silently_change_score():
    world, _ = create_world(leagues=1, seed=1809)
    fixture = next(iter(world.fixtures.values()))
    world.record_result(fixture.fixture_id, 2, 1)
    payload = world.to_dict()
    payload['results'][0]['home_goals'] = 2.75
    with pytest.raises(ValueError, match='integer'):
        WorldSeasonRunner.from_dict(payload)


@pytest.mark.parametrize('klass', [LeagueResult, KnockoutMatchResult])
def test_league_and_knockout_archives_reject_lossy_conversion(klass):
    data = dict(fixture_id='f', home_goals=2, away_goals=0.8)
    with pytest.raises(ValueError, match='integer'):
        klass.from_dict(data)


def test_fast_match_winner_matches_aggregate_score():
    result = _minimal_fast_result()
    assert result.winner_club_id == 'home'
    with pytest.raises(ValueError, match='winner'):
        replace(result, winner_club_id='away')
    with pytest.raises(ValueError, match='winner'):
        replace(result, winner_club_id=None)


def test_fast_match_draw_must_have_tied_aggregate_and_no_winner():
    valid = _minimal_fast_result(aggregate_home=0, aggregate_away=0,
                                 winner=None, decision=FastMatchDecision.DRAW)
    assert valid.winner_club_id is None
    with pytest.raises(ValueError, match='draw'):
        replace(valid, aggregate_home_goals=1)
    with pytest.raises(ValueError, match='winner'):
        replace(valid, winner_club_id='home')


def test_fast_penalty_winner_must_match_shootout_score():
    kick = FastPenaltyKickEvent(
        sequence=1, round_number=1, club_id='home', taker_player_id='h1',
        goalkeeper_player_id='a1', scored=True, sudden_death=False, pressure=.5,
        score_after_home=1, score_after_away=0,
    )
    result = _minimal_fast_result(
        aggregate_home=0, aggregate_away=0, winner='home',
        decision=FastMatchDecision.PENALTIES,
        penalties_home=5, penalties_away=4, kicks=(kick,),
    )
    with pytest.raises(ValueError, match='winner'):
        replace(result, winner_club_id='away')
    with pytest.raises(ValueError, match='aggregate'):
        replace(result, aggregate_home_goals=1)


@pytest.mark.parametrize('field,value', [
    ('home_goals', 1.25), ('away_goals', False),
    ('aggregate_home_goals', 1.5), ('penalties_home', True),
    ('regulation_away_goals', '0'),
])
def test_fast_score_requires_integer_values(field, value):
    result = _minimal_fast_result()
    with pytest.raises(ValueError, match='integer'):
        replace(result, **{field: value})


def test_career_save_refuses_orphan_result_before_writing(tmp_path):
    world, _ = create_world(leagues=1, seed=1810)
    career = WorldCareer(world, {})
    world.results['unknown'] = WorldMatchResult('unknown', 2, 0)
    target = tmp_path / 'archive.json'
    with pytest.raises(ValueError, match='played fixture and result ledger mismatch'):
        career.save_json(target)
    assert not target.exists()


def test_career_save_failure_does_not_overwrite_previous_archive(tmp_path):
    world, _ = create_world(leagues=1, seed=1811)
    career = WorldCareer(world, {})
    target = tmp_path / 'archive.json'
    career.save_json(target)
    original = target.read_bytes()
    world.results['unknown'] = WorldMatchResult('unknown', 2, 0)
    with pytest.raises(ValueError, match='played fixture and result ledger mismatch'):
        career.save_json(target)
    assert target.read_bytes() == original


def test_career_save_rejects_broken_timeline_before_writing(tmp_path):
    world, _ = create_world(leagues=1, seed=1812)
    career = WorldCareer(world, {})
    career.worlds.append(world)
    target = tmp_path / 'broken.json'
    with pytest.raises(ValueError, match='timeline'):
        career.save_json(target)
    assert not target.exists()


def test_unchanged_valid_world_and_career_files_roundtrip(tmp_path):
    world, _ = create_world(leagues=1, seed=1813)
    fixture = next(iter(world.fixtures.values()))
    world.record_result(fixture.fixture_id, 2, 1)
    world_path = tmp_path / 'world.json'
    career_path = tmp_path / 'career.json'
    world.save_json(world_path)
    career = WorldCareer(world, {fixture.home_club_id: 'Example'})
    career.save_json(career_path)
    assert WorldSeasonRunner.load_json(world_path).to_dict() == world.to_dict()
    assert WorldCareer.load_json(career_path).to_dict() == career.to_dict()
    assert json.loads(career_path.read_text(encoding='utf-8'))['schema_version'] == 1
