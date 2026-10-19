from __future__ import annotations

from collections import Counter

from examples.demo_match_factory import build_demo_snapshot
from football_manager.simulation import (
    ActionType,
    MatchFlowController,
    MovementIntentType,
    PlayerDecision,
    SpatialMatchEngine,
    TeamSide,
    Vector2,
)


def _engine(seed: int = 5901) -> SpatialMatchEngine:
    return SpatialMatchEngine(build_demo_snapshot(seed=seed))


def test_every_off_ball_player_gets_a_live_movement_intention() -> None:
    engine = _engine()
    owner = engine.state.player_for_slot(TeamSide.HOME, "cm")
    engine.give_ball_to(owner.agent_id)

    engine.step()

    for agent in engine.state.active_players:
        if agent.agent_id == owner.agent_id:
            assert agent.movement_intent is None
            continue
        assert agent.movement_intent is not None
        assert agent.movement_target is not None


def test_off_ball_intention_persists_instead_of_reselecting_every_tick() -> None:
    engine = _engine()
    owner = engine.state.player_for_slot(TeamSide.HOME, "cm")
    winger = engine.state.player_for_slot(TeamSide.HOME, "lw")
    engine.give_ball_to(owner.agent_id)
    engine.step()
    first = winger.movement_intent

    for _ in range(4):
        engine.step()

    assert first is not None
    assert winger.movement_intent == first


def test_ball_owner_does_not_drift_without_an_explicit_on_ball_action() -> None:
    engine = _engine()
    owner = engine.state.player_for_slot(TeamSide.HOME, "cm")
    engine.give_ball_to(owner.agent_id)
    start = owner.location

    for _ in range(12):
        engine.step()

    assert owner.location == start
    assert engine.state.ball.location == start


def test_central_midfielder_can_drop_between_centre_backs_during_build_up() -> None:
    engine = _engine(seed=6001)
    goalkeeper = engine.state.player_for_slot(TeamSide.HOME, "gk")
    pivot = engine.state.player_for_slot(TeamSide.HOME, "cm")
    engine.give_ball_to(goalkeeper.agent_id)

    seen_drop = False
    for _ in range(72):
        engine.step()
        if pivot.movement_intent == MovementIntentType.DROP_BETWEEN_CBS.value:
            seen_drop = True
            target = pivot.movement_target
            assert target is not None
            assert target.x < goalkeeper.location.x + 35.0
            assert abs(target.y - engine.state.pitch.width_m / 2.0) <= 2.0
            break

    assert seen_drop


def test_flank_players_rotate_instead_of_living_on_fixed_lanes() -> None:
    engine = _engine(seed=5901)
    owner = engine.state.player_for_slot(TeamSide.HOME, "cm")
    left_back = engine.state.player_for_slot(TeamSide.HOME, "lb")
    right_back = engine.state.player_for_slot(TeamSide.HOME, "rb")
    left_winger = engine.state.player_for_slot(TeamSide.HOME, "lw")
    right_winger = engine.state.player_for_slot(TeamSide.HOME, "rw")
    engine.give_ball_to(owner.agent_id)

    fullback_intents: set[str | None] = set()
    winger_intents: set[str | None] = set()
    simultaneous_committed_fullbacks = 0
    for _ in range(600):
        engine.step()
        fullback_intents.update((left_back.movement_intent, right_back.movement_intent))
        winger_intents.update((left_winger.movement_intent, right_winger.movement_intent))
        if (
            left_back.movement_intent in {MovementIntentType.OVERLAP.value, MovementIntentType.UNDERLAP.value}
            and right_back.movement_intent in {MovementIntentType.OVERLAP.value, MovementIntentType.UNDERLAP.value}
        ):
            simultaneous_committed_fullbacks += 1

    assert fullback_intents & {MovementIntentType.OVERLAP.value, MovementIntentType.UNDERLAP.value}
    assert winger_intents & {
        MovementIntentType.MOVE_INSIDE.value,
        MovementIntentType.RUN_IN_BEHIND.value,
        MovementIntentType.DROP_TO_RECEIVE.value,
    }
    assert len(fullback_intents) >= 3
    assert len(winger_intents) >= 3
    # Rest-defence coordination: both full-backs may attack together briefly,
    # but the default pattern should normally leave one balancing behind play.
    assert simultaneous_committed_fullbacks < 60


def test_fullback_can_advance_beyond_midfield_reference_during_a_committed_rotation() -> None:
    engine = _engine(seed=5901)
    owner = engine.state.player_for_slot(TeamSide.HOME, "cm")
    left_back = engine.state.player_for_slot(TeamSide.HOME, "lb")
    right_back = engine.state.player_for_slot(TeamSide.HOME, "rb")
    engine.give_ball_to(owner.agent_id)

    furthest_lead = -999.0
    for _ in range(600):
        engine.step()
        furthest_lead = max(
            furthest_lead,
            left_back.location.x - owner.location.x,
            right_back.location.x - owner.location.x,
        )

    assert furthest_lead > 7.0


def test_committed_run_starts_from_an_onside_reference() -> None:
    engine = _engine(seed=5901)
    state = engine.state
    owner = state.player_for_slot(TeamSide.HOME, "cm")
    striker = state.player_for_slot(TeamSide.HOME, "st")
    owner.location = Vector2(40.0, 34.0)
    striker.location = Vector2(55.0, 34.0)
    for opponent in state.away_players:
        opponent.location = Vector2(60.0, opponent.location.y)
    state.player_for_slot(TeamSide.AWAY, "gk").location = Vector2(100.0, 34.0)
    engine.give_ball_to(owner.agent_id)

    for _ in range(96):
        engine.step()
        if striker.movement_intent in {
            MovementIntentType.RUN_IN_BEHIND.value,
            MovementIntentType.ATTACK_BOX.value,
        }:
            assert striker.movement_target is not None
            # second-last opponent is on x=60; the run should be timed just
            # behind that line until the pass itself releases the runner.
            assert striker.movement_target.x < 60.0
            break
    else:
        raise AssertionError("reference striker never selected a committed run")


def test_clearance_is_an_emergency_family_not_an_equal_default_choice() -> None:
    engine = _engine(seed=777)
    owner = engine.state.player_for_slot(TeamSide.HOME, "lcb")
    owner.location = Vector2(20.0, 30.0)
    for opponent in engine.state.away_players:
        opponent.location = Vector2(80.0, 50.0)
    engine.give_ball_to(owner.agent_id)

    choices = Counter(engine.decide(owner.agent_id).action_type for _ in range(200))

    assert choices[ActionType.CLEARANCE] < 20
    assert choices[ActionType.SHORT_PASS] + choices[ActionType.PROGRESSIVE_PASS] > choices[ActionType.CLEARANCE]


def test_long_pass_has_a_real_aerial_arc() -> None:
    engine = _engine(seed=6002)
    passer = engine.state.player_for_slot(TeamSide.HOME, "lcb")
    receiver = engine.state.player_for_slot(TeamSide.HOME, "rw")
    passer.location = Vector2(24.0, 30.0)
    receiver.location = Vector2(64.0, 18.0)
    for opponent in engine.state.away_players:
        opponent.location = Vector2(92.0, 60.0)
    engine.give_ball_to(passer.agent_id)
    active = engine.start_pass(
        PlayerDecision(
            agent_id=passer.agent_id,
            action_type=ActionType.LONG_PASS,
            target_agent_id=receiver.agent_id,
            utility=80.0,
            considered_options=1,
        )
    )

    assert active.profile.max_height_m >= 2.0
    half_ticks = max(1, round(active.profile.expected_travel_seconds / engine.timestep_seconds / 2.0))
    for _ in range(half_ticks):
        if engine.active_pass is None:
            break
        engine.step()

    assert engine.state.ball.height_m > 0.5


def test_non_receiver_players_keep_moving_while_a_long_pass_is_in_flight() -> None:
    engine = _engine(seed=6003)
    passer = engine.state.player_for_slot(TeamSide.HOME, "lcb")
    receiver = engine.state.player_for_slot(TeamSide.HOME, "rw")
    weak_side_winger = engine.state.player_for_slot(TeamSide.HOME, "lw")
    passer.location = Vector2(24.0, 30.0)
    receiver.location = Vector2(66.0, 18.0)
    engine.give_ball_to(passer.agent_id)
    engine.step()
    start = weak_side_winger.location

    engine.start_pass(
        PlayerDecision(
            agent_id=passer.agent_id,
            action_type=ActionType.LONG_PASS,
            target_agent_id=receiver.agent_id,
            utility=80.0,
            considered_options=1,
        )
    )
    for _ in range(80):
        if engine.active_pass is None:
            break
        engine.step()

    assert weak_side_winger.location.distance_to(start) > 1.0


def test_integrated_reference_match_contains_varied_progression_actions() -> None:
    flow = MatchFlowController(build_demo_snapshot(seed=5902))
    flow.start()
    while flow.engine.state.clock.elapsed_seconds < 12.0 * 60.0:
        flow.step()

    pass_actions = Counter()
    event_types = Counter()
    for event in flow.events:
        data = dict(event.data)
        if event.event_type.value == "pass" and data.get("status") == "attempt":
            pass_actions[data.get("action")] += 1
        if event.event_type.value in {"carry", "dribble", "cross", "shot"}:
            if event.event_type.value in {"dribble", "shot"} or data.get("outcome") is None:
                event_types[event.event_type.value] += 1

    assert pass_actions[ActionType.LONG_PASS.value] > 0
    assert pass_actions[ActionType.PROGRESSIVE_PASS.value] > 0
    assert event_types["carry"] > 0
    assert event_types["dribble"] > 0
    assert event_types["cross"] > 0
