"""TS-FIX-01: real youth minutes, daily rhythm, shared exposure and rollback."""
from copy import deepcopy
from datetime import date, timedelta
from dataclasses import replace

import pytest
from football_manager.dev_ui.session import DevelopmentSession
from football_manager.domain.match_rhythm import after_match, after_inactivity
from football_manager.domain.enums import Position
from football_manager.services.player_development import advance_world_development
from football_manager.services.youth_match_development import (
    advance_youth_matches, record_participation, select_youth_team, _participation_plan,
)
from football_manager.services.youth_academy import youth_command, youth_read_model


@pytest.fixture(scope='module')
def baseline():
    return DevelopmentSession()


def signature(session):
    youth = session._world_squads.youth
    return (youth.match_clock, youth.last_processed, dict(youth.recent_participation), dict(youth.state_dates),
            tuple((f.fixture_id, f.home_goals, f.away_goals) for f in youth.fixtures.values()),
            tuple((p.id, p.attributes, p.development, p.aging, p.state.fitness, p.state.fatigue,
                   p.state.match_sharpness, p.state.injury)
                  for a in youth.academies.values() for p in (*a.u17.values(), *a.u21.values())))


def test_minute_scaled_rhythm_has_diminishing_gains_and_no_fixed_94_cap():
    assert after_match(65, 0) == 65
    assert 65 < after_match(65, 15) < after_match(65, 90)
    assert after_match(94, 90, rate=.15) > 94
    assert after_match(99.9, 120, rate=.15) <= 100
    assert after_match(65, 90) - 65 > after_match(95, 90) - 95
    healthy = after_inactivity(65, 60, training_quality=60, injured=False)
    injured = after_inactivity(65, 60, training_quality=60, injured=True)
    assert injured < healthy < 65
    assert after_inactivity(65, 60, training_quality=90, injured=False) > healthy


def test_inactivity_clock_is_partition_invariant():
    once = after_inactivity(94, 30, training_quality=65, injured=False)
    value = 94
    for _ in range(30):
        value = after_inactivity(value, 1, training_quality=65, injured=False)
    assert value == pytest.approx(once)


def test_youth_plan_conserves_minutes_and_uses_substitutes(baseline):
    s = deepcopy(baseline)
    youth = s._world_squads.youth
    academy = youth.academies[s.home_club.id]
    for level in ('u17', 'u21'):
        team = select_youth_team(academy, level, s.current_date, youth)
        plan = _participation_plan(team, academy, level, s.current_date, youth, 42)
        assert sum(minutes for _, minutes, _ in plan) == 990
        assert len({p.id for p, _, _ in plan}) == len(plan) > 11
        assert any(minutes < 45 for _, minutes, _ in plan)
        assert sum(minutes for _, minutes, position in plan if position is Position.GK) == 90


def test_daily_fixtures_first_of_month_and_idempotence(baseline):
    s = deepcopy(baseline)
    y = s._world_squads.youth
    fixture = next(f for f in y.fixtures.values() if f.match_date >= s.current_date)
    fixture.match_date = date(2026, 9, 1)
    advance_world_development(s._world, date(2026, 9, 1))
    assert fixture.home_goals is None
    advance_world_development(s._world, date(2026, 9, 2))
    assert fixture.home_goals is not None
    before = signature(s)
    assert advance_world_development(s._world, date(2026, 9, 2)) == 0
    assert signature(s) == before


def test_rotation_and_sharpness_do_not_collapse_into_two_values(baseline):
    s = deepcopy(baseline)
    advance_world_development(s._world, date(2026, 11, 1))
    y = s._world_squads.youth
    academy = y.academies[s.home_club.id]
    for level in ('u17', 'u21'):
        roster = getattr(academy, level)
        sharpness = {round(p.state.match_sharpness, 1) for p in roster.values()}
        assert len(sharpness) >= 8
        assert sharpness != {65., 94.}
        played = [sum(minutes for _, minutes in y.recent_participation.get(p.id, ())) for p in roster.values()]
        assert sum(value > 0 for value in played) >= 15
        assert len(set(played)) >= 6
    assert all(len(h) <= 29 for h in y.recent_participation.values())


def test_no_games_still_changes_rhythm_and_read_model_is_pure(baseline):
    s = deepcopy(baseline)
    y = s._world_squads.youth
    y.fixtures = {}
    player = next(iter(y.academies[s.home_club.id].u17.values()))
    player.state.match_sharpness = 94
    advance_world_development(s._world, s.current_date + timedelta(days=7))
    assert 65 < player.state.match_sharpness < 94
    before = signature(s)
    youth_read_model(s)
    youth_read_model(s)
    assert signature(s) == before


def test_missing_goalkeeper_never_generates_fixture_or_exposure(baseline):
    s = deepcopy(baseline)
    y = s._world_squads.youth
    a = y.academies[s.home_club.id]
    before_results = {f.fixture_id: (f.home_goals, f.away_goals) for f in y.fixtures.values()
                      if f.level == 'u17' and s.home_club.id in (f.home_club_id, f.away_club_id)}
    before_minutes = {p.id: p.development.exposure.minutes for p in a.u17.values()}
    for p in a.u17.values():
        if p.primary_position is Position.GK:
            p.state.injury = 'test absence'
    with s._world.transaction():
        advance_youth_matches(s._world, date(2026, 9, 1))
    assert before_results == {f.fixture_id: (f.home_goals, f.away_goals) for f in y.fixtures.values()
                              if f.fixture_id in before_results}
    assert before_minutes == {p.id: p.development.exposure.minutes for p in a.u17.values()}


def test_shared_ledger_blocks_same_day_youth_and_senior_appearance(baseline):
    s = deepcopy(baseline)
    y = s._world_squads.youth
    a = y.academies[s.home_club.id]
    player = next(p for p in a.u17.values() if p.primary_position is not Position.GK)
    with s._world.transaction():
        record_participation(s._world, player.id, s.current_date, 90)
    assert player not in select_youth_team(a, 'u17', s.current_date, y)
    before = dict(y.recent_participation)
    with pytest.raises(ValueError, match='already participated'):
        with s._world.transaction():
            record_participation(s._world, player.id, s.current_date, 20)
    assert y.recent_participation == before


def test_category_move_preserves_real_rhythm_and_existing_identity(baseline):
    s = deepcopy(baseline)
    a = s._world_squads.youth.academies[s.home_club.id]
    p = next(p for p in a.u17.values() if p.age_on(s.current_date) <= 17)
    p.state.match_sharpness = 89.4
    youth_command(s, {'action': 'move', 'player_id': p.id, 'target': 'first'})
    assert s.home_club.squad.get(p.id) is p
    assert p.state.match_sharpness == 89.4
    youth_command(s, {'action': 'move', 'player_id': p.id, 'target': 'u17'})
    assert a.u17[p.id] is p and p.state.match_sharpness == 89.4


def test_failed_academy_progression_rolls_back_clock_fixtures_minutes_and_state(baseline):
    s = deepcopy(baseline)
    before = signature(s)
    with pytest.raises(RuntimeError, match='injected'):
        with s._world.transaction():
            advance_youth_matches(s._world, date(2026, 9, 1))
            raise RuntimeError('injected failure')
    assert signature(s) == before


def test_dated_youth_injury_recovers_without_playing_before_return(baseline):
    from football_manager.domain.player_aging import create_injury
    s = deepcopy(baseline)
    y = s._world_squads.youth
    a = y.academies[s.home_club.id]
    p = next(iter(a.u17.values()))
    p.aging = create_injury(p, s.current_date, 'fix01-test', 10, 'Test injury')
    p.state.injury = 'Test injury'
    with s._world.transaction():
        advance_youth_matches(s._world, date(2026, 9, 1))
    assert p.state.injury is None and p.aging.active_injury is None
    assert all(day >= date(2026, 8, 31) for day, _ in y.recent_participation.get(p.id, ()))
