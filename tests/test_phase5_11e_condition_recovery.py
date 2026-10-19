from __future__ import annotations

from dataclasses import replace
from statistics import fmean

import pytest

from examples.demo_match_factory import _player, build_demo_snapshot
from football_manager.domain import Position, match_condition_state, recover_condition_state
from football_manager.fast_calibration.scenarios import neutralize_fast_snapshot
from football_manager.fast_simulation import (
    FastMatchSimulator,
    build_fast_team_profile,
    physical_state_after,
)
from football_manager.services import recover_player_between_matches, set_post_match_condition


def _neutral_snapshot(seed: int = 511_500):
    return neutralize_fast_snapshot(build_demo_snapshot(seed=seed), rating=70, seed=seed)


def test_neutral_90_minute_load_finishes_in_meaningful_rotation_zone() -> None:
    state = match_condition_state(
        starting_condition=100.0,
        starting_fatigue=0.0,
        stamina=65.0,
        minutes=90,
        workload_factor=1.0,
    )
    assert 50.0 <= state.condition <= 60.0
    assert 30.0 <= state.fatigue <= 45.0


def test_extra_time_is_non_linear_and_can_leave_long_runners_depleted() -> None:
    ninety = match_condition_state(
        starting_condition=100.0,
        starting_fatigue=0.0,
        stamina=65.0,
        minutes=90,
        workload_factor=1.0,
    )
    one_twenty = match_condition_state(
        starting_condition=100.0,
        starting_fatigue=0.0,
        stamina=65.0,
        minutes=120,
        workload_factor=1.0,
    )
    assert 20.0 <= one_twenty.condition <= 35.0
    assert ninety.condition - one_twenty.condition > 20.0
    assert one_twenty.fatigue > ninety.fatigue


def test_stamina_protects_condition_during_the_same_workload() -> None:
    low = match_condition_state(
        starting_condition=100,
        starting_fatigue=0,
        stamina=40,
        minutes=90,
    )
    normal = match_condition_state(
        starting_condition=100,
        starting_fatigue=0,
        stamina=65,
        minutes=90,
    )
    elite = match_condition_state(
        starting_condition=100,
        starting_fatigue=0,
        stamina=90,
        minutes=90,
    )
    assert low.condition < normal.condition < elite.condition
    assert low.fatigue > normal.fatigue > elite.fatigue
    assert elite.condition - low.condition >= 20.0


def test_high_press_is_more_expensive_for_a_forward() -> None:
    snapshot = _neutral_snapshot()
    striker = next(player for player in snapshot.home_team.starters if player.assigned_position is Position.ST)
    neutral = build_fast_team_profile(snapshot.home_team)
    low_press = replace(neutral, pressing=15.0, tempo=45.0)
    high_press = replace(neutral, pressing=100.0, tempo=75.0)

    low = physical_state_after(striker, low_press, 90)
    high = physical_state_after(striker, high_press, 90)
    assert high.condition < low.condition - 8.0


def test_low_block_shifts_more_work_to_a_centre_back() -> None:
    snapshot = _neutral_snapshot()
    centre_back = next(
        player for player in snapshot.home_team.starters if player.assigned_position is Position.RCB
    )
    neutral = build_fast_team_profile(snapshot.home_team)
    normal_block = replace(neutral, defensive_depth=50.0)
    low_block = replace(neutral, defensive_depth=10.0)

    normal = physical_state_after(centre_back, normal_block, 90)
    deep = physical_state_after(centre_back, low_block, 90)
    assert deep.condition < normal.condition - 3.0


def test_four_day_turnaround_after_90_minutes_recovers_but_not_automatically_to_100() -> None:
    post_match = match_condition_state(
        starting_condition=100,
        starting_fatigue=0,
        stamina=65,
        minutes=90,
    )
    recovered = recover_condition_state(
        condition=post_match.condition,
        fatigue=post_match.fatigue,
        days=4,
        natural_fitness=65,
        stamina=65,
    )
    assert 82.0 <= recovered.condition <= 88.0
    assert recovered.fatigue <= 5.0


def test_four_day_turnaround_after_120_minutes_can_force_rotation() -> None:
    post_match = match_condition_state(
        starting_condition=100,
        starting_fatigue=0,
        stamina=65,
        minutes=120,
    )
    recovered = recover_condition_state(
        condition=post_match.condition,
        fatigue=post_match.fatigue,
        days=4,
        natural_fitness=65,
        stamina=65,
    )
    assert 50.0 <= recovered.condition <= 70.0
    assert recovered.condition < 75.0
    assert recovered.fatigue > 0.0


def test_full_week_after_120_minutes_still_leaves_a_small_recovery_scar() -> None:
    post_match = match_condition_state(
        starting_condition=100,
        starting_fatigue=0,
        stamina=65,
        minutes=120,
    )
    recovered = recover_condition_state(
        condition=post_match.condition,
        fatigue=post_match.fatigue,
        days=7,
        natural_fitness=65,
        stamina=65,
    )
    assert 89.0 <= recovered.condition <= 95.0
    assert recovered.condition < 100.0


def test_full_week_restores_a_normal_90_minute_load() -> None:
    post_match = match_condition_state(
        starting_condition=100,
        starting_fatigue=0,
        stamina=65,
        minutes=90,
    )
    recovered = recover_condition_state(
        condition=post_match.condition,
        fatigue=post_match.fatigue,
        days=7,
        natural_fitness=65,
        stamina=65,
    )
    assert recovered.condition == pytest.approx(100.0)
    assert recovered.fatigue == pytest.approx(0.0)


def test_natural_fitness_is_primary_between_match_recovery_attribute() -> None:
    low = recover_condition_state(
        condition=55,
        fatigue=38,
        days=4,
        natural_fitness=40,
        stamina=65,
    )
    high = recover_condition_state(
        condition=55,
        fatigue=38,
        days=4,
        natural_fitness=90,
        stamina=65,
    )
    assert high.condition > low.condition + 10.0


def test_stamina_also_contributes_to_between_match_recovery() -> None:
    low = recover_condition_state(
        condition=54,
        fatigue=39,
        days=4,
        natural_fitness=65,
        stamina=40,
    )
    elite = recover_condition_state(
        condition=54,
        fatigue=39,
        days=4,
        natural_fitness=65,
        stamina=97,
    )
    assert elite.condition > low.condition + 5.0


def test_condition_below_75_has_meaningful_act_cost_for_rotation_decisions() -> None:
    player = _player("condition-act", Position.ST)
    player.state.fitness = 45.0
    tired = player.current_rating()
    player.state.fitness = 100.0
    fresh = player.current_rating()
    assert fresh.current - tired.current >= 6.0


def test_fast_result_exposes_condition_and_fatigue_after_match() -> None:
    snapshot = _neutral_snapshot()
    result = FastMatchSimulator().simulate(snapshot)
    positions = {
        player.player_id: player.assigned_position
        for team in (snapshot.home_team, snapshot.away_team)
        for player in team.starters
    }
    outfield = [
        item for item in result.player_statistics if positions.get(item.player_id) is not Position.GK
    ]
    assert 50.0 <= fmean(item.condition_after for item in outfield) <= 65.0
    assert fmean(item.fatigue_after for item in outfield) >= 30.0


def test_recovery_service_persists_post_match_and_calendar_recovery() -> None:
    player = _player("recovery-service", Position.CM)
    set_post_match_condition(player, condition=55.0, fatigue=38.0)
    assert player.state.condition == pytest.approx(55.0)
    assert player.state.fatigue == pytest.approx(38.0)

    recovered = recover_player_between_matches(player, days=4)
    assert player.state.condition == recovered.condition
    assert player.state.fatigue == recovered.fatigue
    assert player.state.condition > 85.0
