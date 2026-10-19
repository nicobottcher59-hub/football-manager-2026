"""TS-18.4: correct existing match event and player attribution contracts."""
from __future__ import annotations

import pytest

from examples.demo_match_factory import build_demo_snapshot
from football_manager.domain import Position
from football_manager.fast_simulation import FastMatchSimulator
from football_manager.fast_simulation.engine import _ShotRecord, _TeamRuntime
from football_manager.fast_simulation.profiles import build_fast_team_profile
from football_manager.fast_simulation.randomness import FastMatchRandom
from football_manager.simulation import (
    CardType, MatchEndReason, MatchFlowController, MatchPhase,
    RestartType, TeamSide,
)
from test_spatial_core import make_snapshot


def _runtimes():
    snapshot = build_demo_snapshot(seed=731800)
    return (
        _TeamRuntime(snapshot.home_team, build_fast_team_profile(snapshot.home_team)),
        _TeamRuntime(snapshot.away_team, build_fast_team_profile(snapshot.away_team)),
    )


def _keeper_rating_with_opposition_shot(*, minute: int | None, goal: bool = False) -> float:
    simulator = FastMatchSimulator()
    home, away = _runtimes()
    goalkeeper = next(player for player in home.team.starters if player.assigned_position is Position.GK)
    home.dismissed_at[goalkeeper.player_id] = 30
    if minute is not None:
        shooter = away.team.starters[-1]
        away.shots.append(_ShotRecord(
            player_id=shooter.player_id,
            assist_player_id=None,
            xg=0.25,
            on_target=True,
            goal=goal,
            minute=minute,
            extra_time=False,
        ))
    stats = simulator._player_statistics(
        home, away, goals=(), extra_time_played=False,
        winner_club_id=None, root=FastMatchRandom(731800),
    )
    return next(item.match_rating for item in stats if
                item.club_id == home.team.club_id and item.player_id == goalkeeper.player_id)


def test_goalkeeper_is_not_credited_with_saves_after_dismissal() -> None:
    assert _keeper_rating_with_opposition_shot(minute=70) == _keeper_rating_with_opposition_shot(minute=None)
    assert _keeper_rating_with_opposition_shot(minute=20) > _keeper_rating_with_opposition_shot(minute=70)


def test_goalkeeper_is_not_charged_for_goals_after_dismissal() -> None:
    assert _keeper_rating_with_opposition_shot(minute=70, goal=True) == _keeper_rating_with_opposition_shot(minute=None)
    assert _keeper_rating_with_opposition_shot(minute=20, goal=True) < _keeper_rating_with_opposition_shot(minute=70, goal=True)


def _flow_with_keeper_red(*, side: TeamSide = TeamSide.HOME, second_yellow: bool = False):
    flow = MatchFlowController(make_snapshot(seed=731801))
    flow.start()
    dismissed = flow.engine.state.player_for_slot(side, 'gk')
    if second_yellow:
        flow._apply_card(dismissed.agent_id, CardType.YELLOW)
        flow._apply_card(dismissed.agent_id, CardType.YELLOW)
    else:
        flow._apply_card(dismissed.agent_id, CardType.RED)
    return flow, dismissed


@pytest.mark.parametrize('side', [TeamSide.HOME, TeamSide.AWAY])
@pytest.mark.parametrize('second_yellow', [False, True])
def test_keeper_dismissal_keeps_an_active_goalkeeper(side: TeamSide, second_yellow: bool) -> None:
    flow, dismissed = _flow_with_keeper_red(side=side, second_yellow=second_yellow)
    replacement = flow.engine.state.player_for_slot(side, 'gk')
    assert dismissed.dismissed
    assert replacement.agent_id != dismissed.agent_id
    assert replacement.is_active
    assert replacement.assigned_position is Position.GK
    assert replacement.player.assigned_position is Position.GK
    assert len(flow.engine.state.active_players_for_side(side)) == 10
    assert flow.engine.shooting._goalkeeper(flow.engine.state, side) is replacement


def test_goal_kick_still_works_after_keepers_red_card() -> None:
    flow, dismissed = _flow_with_keeper_red()
    replacement = flow.engine.state.player_for_slot(TeamSide.HOME, 'gk')
    flow.award_restart(RestartType.GOAL_KICK, TeamSide.HOME)
    assert flow.engine.state.ball.owner_agent_id == replacement.agent_id
    assert not dismissed.is_active


def test_keeper_red_does_not_modify_opposing_team_assignments() -> None:
    flow = MatchFlowController(make_snapshot(seed=731803))
    flow.start()
    opponents_before = {
        agent.agent_id: (agent.player, agent.assigned_position, agent.slot_id)
        for agent in flow.engine.state.active_players_for_side(TeamSide.AWAY)
    }
    flow._apply_card(flow.engine.state.player_for_slot(TeamSide.HOME, 'gk').agent_id, CardType.RED)
    opponents_after = {
        agent.agent_id: (agent.player, agent.assigned_position, agent.slot_id)
        for agent in flow.engine.state.active_players_for_side(TeamSide.AWAY)
    }
    assert opponents_after == opponents_before


def test_extra_long_shootout_can_only_be_decided_by_an_actual_kick(monkeypatch) -> None:
    flow = MatchFlowController(make_snapshot(seed=731802))
    flow.phase = MatchPhase.PENALTY_SHOOTOUT
    monkeypatch.setattr(flow, '_penalty_takers', lambda side: ('taker',))
    kicks: list[TeamSide] = []
    def fake_kick(side, taker):
        kicks.append(side)
        # Twenty-six complete tied rounds, then the home side converts.
        return side is TeamSide.HOME and kicks.count(TeamSide.HOME) == 27
    monkeypatch.setattr(flow, '_take_penalty', fake_kick)

    flow._run_penalty_shootout()
    result = flow.result
    assert result is not None
    assert result.end_reason is MatchEndReason.PENALTIES
    assert result.winner is TeamSide.HOME
    assert result.penalties_home == 1 and result.penalties_away == 0
    assert len(kicks) == 54
    assert kicks[-2:] == [TeamSide.HOME, TeamSide.AWAY]


def test_real_spatial_shot_uses_emergency_keeper_after_dismissal() -> None:
    from football_manager.simulation.decisions import ActionType, PlayerDecision

    flow, dismissed = _flow_with_keeper_red()
    covering = flow.engine.state.player_for_slot(TeamSide.HOME, 'gk')
    shooter = flow.engine.state.player_for_slot(TeamSide.AWAY, 'st')
    flow.engine.give_ball_to(shooter.agent_id)
    profile = flow.engine.shot_profile(PlayerDecision(
        agent_id=shooter.agent_id, action_type=ActionType.SHOOT,
        target_agent_id=None, utility=0.0, considered_options=1,
    ))
    assert profile.goalkeeper_agent_id == covering.agent_id
    assert profile.goalkeeper_agent_id != dismissed.agent_id
    result = flow.engine.resolve_active_shot()
    assert result.goalkeeper_agent_id == covering.agent_id


def test_shootout_still_resolves_after_keeper_red_card() -> None:
    flow, dismissed = _flow_with_keeper_red()
    covering = flow.engine.state.player_for_slot(TeamSide.HOME, 'gk')
    flow.phase = MatchPhase.PENALTY_SHOOTOUT
    flow._run_penalty_shootout()
    assert flow.result is not None
    assert flow.result.end_reason is MatchEndReason.PENALTIES
    assert flow.result.winner is not None
    assert all(event.secondary_agent_id != dismissed.agent_id for event in flow.events
               if event.event_type.value == 'penalty_kick')
    assert any(event.secondary_agent_id == covering.agent_id for event in flow.events
               if event.event_type.value == 'penalty_kick')


def test_full_time_goalkeeper_ratings_preserve_previous_formula() -> None:
    simulator = FastMatchSimulator()
    home, away = _runtimes()
    goalkeeper = next(player for player in home.team.starters if player.assigned_position is Position.GK)
    shooter = away.team.starters[-1]
    away.shots.extend([
        _ShotRecord(shooter.player_id, None, 0.30, True, False, 18, False),
        _ShotRecord(shooter.player_id, None, 0.24, True, True, 63, False),
        _ShotRecord(shooter.player_id, None, 0.05, False, False, 80, False),
    ])
    stats = simulator._player_statistics(home, away, goals=(), extra_time_played=False,
                                           winner_club_id=None, root=FastMatchRandom(731800))
    actual = next(item.match_rating for item in stats if
                  item.club_id == home.team.club_id and item.player_id == goalkeeper.player_id)
    noise = FastMatchRandom(731800).fork(f'home/rating/{goalkeeper.player_id}').gauss(0.0, 0.12)
    old_expected = round(simulator._clamp(6.45 + 1 * 0.055 + 0 + noise, 3.0, 10.0), 2)
    assert actual == old_expected


def _defender_rating_with_goal(*, minute: int | None, dismissed: bool = False) -> float:
    home, away = _runtimes()
    player = next(p for p in home.team.starters if p.assigned_position in {Position.CB, Position.RCB, Position.LCB})
    if dismissed:
        home.dismissed_at[player.player_id] = 30
    else:
        home.exited_minute[player.player_id] = 90
    if minute is not None:
        shooter = away.team.starters[-1]
        away.shots.append(_ShotRecord(shooter.player_id, None, 0.3, True, True,
                                      minute, minute > 90))
    stats = FastMatchSimulator()._player_statistics(
        home, away, goals=(), extra_time_played=not dismissed,
        winner_club_id=None, root=FastMatchRandom(731800),
    )
    return next(item.match_rating for item in stats if
                item.club_id == home.team.club_id and item.player_id == player.player_id)


def test_outfield_defender_is_not_charged_for_goal_after_red() -> None:
    assert _defender_rating_with_goal(minute=70, dismissed=True) == _defender_rating_with_goal(minute=None, dismissed=True)
    assert _defender_rating_with_goal(minute=20, dismissed=True) < _defender_rating_with_goal(minute=70, dismissed=True)


def test_outfield_defender_leaving_at_90_keeps_clean_sheet_in_extra_time() -> None:
    assert _defender_rating_with_goal(minute=111) == _defender_rating_with_goal(minute=None)
    assert _defender_rating_with_goal(minute=70) < _defender_rating_with_goal(minute=111)
