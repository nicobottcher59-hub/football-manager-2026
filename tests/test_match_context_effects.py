from __future__ import annotations

from dataclasses import replace

import pytest

from football_manager.domain import (
    MatchConditionsSnapshot,
    PitchCondition,
    RefereeSnapshot,
    StadiumSnapshot,
    SurfaceType,
    WeatherSnapshot,
    WeatherType,
)
from football_manager.simulation import (
    CardType,
    FlowConfig,
    MatchContextSystem,
    MatchEventType,
    MatchFlowController,
    SpatialMatchEngine,
    TeamSide,
    Vector2,
)

from test_spatial_core import make_snapshot


def _snapshot_with_context(
    *,
    seed: int = 8100,
    weather_type: WeatherType = WeatherType.CLEAR,
    temperature_c: float = 20.0,
    wind_kph: float = 0.0,
    humidity: float = 50.0,
    precipitation_intensity: float = 0.0,
    pitch_condition: PitchCondition = PitchCondition.GOOD,
    surface: SurfaceType = SurfaceType.HYBRID_GRASS,
    referee: RefereeSnapshot | None = None,
):
    snapshot = make_snapshot(seed=seed)
    conditions = MatchConditionsSnapshot(
        weather=WeatherSnapshot(
            weather_type=weather_type,
            temperature_c=temperature_c,
            wind_kph=wind_kph,
            humidity=humidity,
            precipitation_intensity=precipitation_intensity,
        ),
        pitch_condition=pitch_condition,
    )
    stadium = replace(snapshot.context.stadium, surface=surface)
    return replace(
        snapshot,
        context=replace(
            snapshot.context,
            conditions=conditions,
            stadium=stadium,
            referee=referee or snapshot.context.referee,
        ),
    )


def _short_flow_config() -> FlowConfig:
    return FlowConfig(
        regulation_half_seconds=1.0,
        extra_time_half_seconds=1.0,
        decision_cooldown_seconds=0.5,
        loose_ball_collection_seconds=0.5,
        forced_loose_ball_collection_seconds=1.0,
        added_time_unit_seconds=1.0,
        regulation_added_time_cap_seconds=0.0,
        extra_time_added_time_cap_seconds=0.0,
        autonomous_actions=False,
        autonomous_tackles=False,
    )


def _foul_pair(engine: SpatialMatchEngine, *, home_attacking: bool = True):
    attacker_side = TeamSide.HOME if home_attacking else TeamSide.AWAY
    defender_side = attacker_side.opponent
    attacker = engine.state.player_for_slot(attacker_side, "st")
    defender = engine.state.player_for_slot(defender_side, "rcb")
    attacker.location = Vector2(60.0, 34.0)
    defender.location = Vector2(60.8, 34.0)
    return defender, attacker


def test_runtime_condition_is_initialized_from_immutable_player_snapshot() -> None:
    snapshot = make_snapshot(seed=8101)
    engine = SpatialMatchEngine(snapshot)
    agent = engine.state.player_for_slot(TeamSide.HOME, "cm")

    assert agent.current_fitness == agent.player.state.fitness
    assert agent.current_fatigue == agent.player.state.fatigue


def test_live_match_ticks_accumulate_fatigue_and_reduce_fitness() -> None:
    engine = SpatialMatchEngine(make_snapshot(seed=8102))
    agent = engine.state.player_for_slot(TeamSide.HOME, "cm")
    start_fatigue = agent.current_fatigue
    start_fitness = agent.current_fitness

    engine.advance_ticks(120)

    assert agent.current_fatigue > start_fatigue
    assert agent.current_fitness < start_fitness


def test_running_player_fatigues_more_than_stationary_player() -> None:
    engine = SpatialMatchEngine(make_snapshot(seed=8103))
    runner = engine.state.player_for_slot(TeamSide.HOME, "cm")
    stationary = engine.state.player_for_slot(TeamSide.HOME, "lcm")
    engine.set_player_velocity(runner.agent_id, Vector2(6.5, 0.0))
    engine.set_player_velocity(stationary.agent_id, Vector2.zero())

    engine.advance_ticks(160)

    assert runner.current_fatigue > stationary.current_fatigue


def test_hot_humid_heavy_conditions_increase_fatigue_cost() -> None:
    mild = SpatialMatchEngine(_snapshot_with_context(seed=8104))
    harsh = SpatialMatchEngine(
        _snapshot_with_context(
            seed=8104,
            weather_type=WeatherType.HEAVY_RAIN,
            temperature_c=34.0,
            humidity=90.0,
            precipitation_intensity=85.0,
            pitch_condition=PitchCondition.HEAVY,
        )
    )
    mild_player = mild.state.player_for_slot(TeamSide.HOME, "cm")
    harsh_player = harsh.state.player_for_slot(TeamSide.HOME, "cm")
    mild.set_player_velocity(mild_player.agent_id, Vector2(5.5, 0.0))
    harsh.set_player_velocity(harsh_player.agent_id, Vector2(5.5, 0.0))

    mild.advance_ticks(200)
    harsh.advance_ticks(200)

    assert harsh_player.current_fatigue > mild_player.current_fatigue
    assert harsh_player.current_fitness < mild_player.current_fitness


def test_heavy_pitch_reduces_player_movement_speed_multiplier() -> None:
    good_engine = SpatialMatchEngine(_snapshot_with_context(seed=8105))
    heavy_engine = SpatialMatchEngine(
        _snapshot_with_context(seed=8105, pitch_condition=PitchCondition.HEAVY)
    )
    good = good_engine.state.player_for_slot(TeamSide.HOME, "rw")
    heavy = heavy_engine.state.player_for_slot(TeamSide.HOME, "rw")

    assert heavy_engine.context.movement_speed_multiplier(heavy) < good_engine.context.movement_speed_multiplier(good)


def test_waterlogged_pitch_slows_ground_ball_relative_to_good_pitch() -> None:
    good = MatchContextSystem(_snapshot_with_context(seed=8106))
    waterlogged = MatchContextSystem(
        _snapshot_with_context(seed=8106, pitch_condition=PitchCondition.WATERLOGGED)
    )

    assert waterlogged.ball_speed_multiplier() < good.ball_speed_multiplier()


def test_wet_pitch_can_make_ground_ball_run_faster_than_good_pitch() -> None:
    good = MatchContextSystem(_snapshot_with_context(seed=8107))
    wet = MatchContextSystem(
        _snapshot_with_context(seed=8107, pitch_condition=PitchCondition.WET)
    )

    assert wet.ball_speed_multiplier() > good.ball_speed_multiplier()


def test_strong_wind_increases_long_aerial_execution_error() -> None:
    calm = MatchContextSystem(_snapshot_with_context(seed=8108, wind_kph=0.0))
    windy = MatchContextSystem(
        _snapshot_with_context(
            seed=8108,
            weather_type=WeatherType.STORM,
            wind_kph=65.0,
            precipitation_intensity=60.0,
        )
    )

    assert windy.error_multiplier(distance_m=32.0, aerial=True) > calm.error_multiplier(distance_m=32.0, aerial=True)


def test_fog_reduces_useful_player_awareness_radius() -> None:
    clear_engine = SpatialMatchEngine(_snapshot_with_context(seed=8109))
    fog_engine = SpatialMatchEngine(
        _snapshot_with_context(seed=8109, weather_type=WeatherType.FOG)
    )
    clear = clear_engine.state.player_for_slot(TeamSide.HOME, "cm")
    fog = fog_engine.state.player_for_slot(TeamSide.HOME, "cm")

    assert fog_engine.perceive(fog.agent_id).awareness_radius_m < clear_engine.perceive(clear.agent_id).awareness_radius_m


def test_weather_and_pitch_reduce_first_touch_quality_without_mutating_attributes() -> None:
    good_engine = SpatialMatchEngine(_snapshot_with_context(seed=8110))
    harsh_engine = SpatialMatchEngine(
        _snapshot_with_context(
            seed=8110,
            weather_type=WeatherType.HEAVY_RAIN,
            precipitation_intensity=90.0,
            pitch_condition=PitchCondition.WATERLOGGED,
        )
    )
    good = good_engine.state.player_for_slot(TeamSide.HOME, "cm")
    harsh = harsh_engine.state.player_for_slot(TeamSide.HOME, "cm")

    assert harsh_engine.context.first_touch_adjustment(harsh) < good_engine.context.first_touch_adjustment(good)
    assert harsh.player.attributes.technical.first_touch == good.player.attributes.technical.first_touch == 70


def test_home_context_has_no_unconditional_execution_bonus_without_pressure() -> None:
    engine = SpatialMatchEngine(make_snapshot(seed=8111))
    home = engine.state.player_for_slot(TeamSide.HOME, "cm")
    away = engine.state.player_for_slot(TeamSide.AWAY, "cm")

    assert engine.context.execution_adjustment(home, pressure=0.0) == pytest.approx(
        engine.context.execution_adjustment(away, pressure=0.0)
    )


def test_home_context_gives_small_pressure_resilience_not_attribute_bonus() -> None:
    engine = SpatialMatchEngine(make_snapshot(seed=8112))
    home = engine.state.player_for_slot(TeamSide.HOME, "cm")
    away = engine.state.player_for_slot(TeamSide.AWAY, "cm")
    passing = home.player.attributes.technical.passing

    home_adjustment = engine.context.execution_adjustment(home, pressure=0.8)
    away_adjustment = engine.context.execution_adjustment(away, pressure=0.8)

    assert home_adjustment > away_adjustment
    assert home.player.attributes.technical.passing == passing


def test_strict_low_tolerance_referee_calls_more_contact_than_lenient_referee() -> None:
    strict_ref = RefereeSnapshot(
        referee_id="strict",
        name="Strict",
        strictness=90,
        contact_tolerance=10,
        card_tendency=50,
        penalty_tendency=50,
        advantage_tendency=50,
    )
    lenient_ref = replace(strict_ref, referee_id="lenient", name="Lenient", strictness=10, contact_tolerance=90)
    strict = SpatialMatchEngine(_snapshot_with_context(seed=8113, referee=strict_ref))
    lenient = SpatialMatchEngine(_snapshot_with_context(seed=8113, referee=lenient_ref))
    strict_def, strict_att = _foul_pair(strict)
    lenient_def, lenient_att = _foul_pair(lenient)

    strict_assessment = strict.context.foul_assessment(strict.state, strict_def, strict_att)
    lenient_assessment = lenient.context.foul_assessment(lenient.state, lenient_def, lenient_att)

    assert strict_assessment.foul_probability > lenient_assessment.foul_probability


def test_high_card_tendency_increases_yellow_probability() -> None:
    low_ref = RefereeSnapshot("low-cards", "Low cards", card_tendency=5)
    high_ref = RefereeSnapshot("high-cards", "High cards", card_tendency=95)
    low = SpatialMatchEngine(_snapshot_with_context(seed=8114, referee=low_ref))
    high = SpatialMatchEngine(_snapshot_with_context(seed=8114, referee=high_ref))
    low_def, low_att = _foul_pair(low)
    high_def, high_att = _foul_pair(high)

    low_assessment = low.context.foul_assessment(low.state, low_def, low_att)
    high_assessment = high.context.foul_assessment(high.state, high_def, high_att)

    assert high_assessment.yellow_probability > low_assessment.yellow_probability


def test_high_advantage_tendency_increases_advantage_probability() -> None:
    low_ref = RefereeSnapshot("low-adv", "Low adv", advantage_tendency=0)
    high_ref = RefereeSnapshot("high-adv", "High adv", advantage_tendency=100)
    low = SpatialMatchEngine(_snapshot_with_context(seed=8115, referee=low_ref))
    high = SpatialMatchEngine(_snapshot_with_context(seed=8115, referee=high_ref))
    low_def, low_att = _foul_pair(low)
    high_def, high_att = _foul_pair(high)
    low_att.location = Vector2(80.0, 34.0)
    low_def.location = Vector2(80.8, 34.0)
    high_att.location = Vector2(80.0, 34.0)
    high_def.location = Vector2(80.8, 34.0)

    low_assessment = low.context.foul_assessment(low.state, low_def, low_att)
    high_assessment = high.context.foul_assessment(high.state, high_def, high_att)

    assert low_assessment.advantage_probability == 0.0
    assert high_assessment.advantage_probability > low_assessment.advantage_probability


def test_penalty_area_detection_works_for_both_attacking_directions() -> None:
    engine = SpatialMatchEngine(make_snapshot(seed=8116))

    assert engine.context.is_attacking_penalty_area(engine.state, TeamSide.HOME, Vector2(100.0, 34.0))
    assert engine.context.is_attacking_penalty_area(engine.state, TeamSide.AWAY, Vector2(5.0, 34.0))
    assert not engine.context.is_attacking_penalty_area(engine.state, TeamSide.HOME, Vector2(100.0, 2.0))
    assert not engine.context.is_attacking_penalty_area(engine.state, TeamSide.AWAY, Vector2(30.0, 34.0))


def test_penalty_tendency_only_biases_foul_call_inside_penalty_area() -> None:
    low_ref = RefereeSnapshot("low-pen", "Low pen", penalty_tendency=0)
    high_ref = RefereeSnapshot("high-pen", "High pen", penalty_tendency=100)
    low = SpatialMatchEngine(_snapshot_with_context(seed=8117, referee=low_ref))
    high = SpatialMatchEngine(_snapshot_with_context(seed=8117, referee=high_ref))
    low_def, low_att = _foul_pair(low)
    high_def, high_att = _foul_pair(high)
    low_att.location = Vector2(96.0, 34.0)
    low_def.location = Vector2(96.8, 34.0)
    high_att.location = Vector2(96.0, 34.0)
    high_def.location = Vector2(96.8, 34.0)

    low_assessment = low.context.foul_assessment(low.state, low_def, low_att)
    high_assessment = high.context.foul_assessment(high.state, high_def, high_att)

    assert low_assessment.is_penalty_area and high_assessment.is_penalty_area
    assert high_assessment.foul_probability > low_assessment.foul_probability
    assert high_assessment.advantage_probability == 0.0


def test_card_choice_respects_seeded_probability_thresholds() -> None:
    engine = SpatialMatchEngine(make_snapshot(seed=8118))
    defender, attacker = _foul_pair(engine)
    assessment = engine.context.foul_assessment(engine.state, defender, attacker)

    assert engine.context.choose_card(assessment, 0.0) in {CardType.RED, CardType.YELLOW}
    assert engine.context.choose_card(assessment, 1.0) is None


def test_second_yellow_dismisses_player_and_removes_them_from_active_play() -> None:
    flow = MatchFlowController(make_snapshot(seed=8119), config=_short_flow_config())
    flow.start()
    offender = flow.engine.state.player_for_slot(TeamSide.AWAY, "rcb")
    victim = flow.engine.state.player_for_slot(TeamSide.HOME, "st")

    flow.register_foul(offender.agent_id, victim.agent_id, card=CardType.YELLOW)
    flow.register_foul(offender.agent_id, victim.agent_id, card=CardType.YELLOW)

    assert offender.yellow_cards == 2
    assert offender.dismissed
    assert offender not in flow.engine.state.active_players
    card_events = [event for event in flow.events if event.event_type is MatchEventType.CARD]
    assert card_events[-1].value("card") == CardType.SECOND_YELLOW_RED.value


def test_direct_red_dismissal_removes_player_from_perception() -> None:
    flow = MatchFlowController(make_snapshot(seed=8120), config=_short_flow_config())
    flow.start()
    offender = flow.engine.state.player_for_slot(TeamSide.AWAY, "rcb")
    observer = flow.engine.state.player_for_slot(TeamSide.HOME, "cm")
    victim = flow.engine.state.player_for_slot(TeamSide.HOME, "st")
    offender.location = Vector2(observer.location.x + 2.0, observer.location.y)

    flow.register_foul(offender.agent_id, victim.agent_id, card=CardType.RED)
    perception = flow.engine.perceive(observer.agent_id)

    assert offender.dismissed
    assert offender.agent_id not in {player.agent_id for player in perception.opponents}


def test_penalty_area_foul_emits_award_and_penalty_kick_event() -> None:
    flow = MatchFlowController(make_snapshot(seed=8121), config=_short_flow_config())
    flow.start()
    attacker = flow.engine.state.player_for_slot(TeamSide.HOME, "st")
    defender = flow.engine.state.player_for_slot(TeamSide.AWAY, "rcb")
    attacker.location = Vector2(96.0, 34.0)
    defender.location = Vector2(96.8, 34.0)
    assessment = flow.engine.context.foul_assessment(flow.engine.state, defender, attacker)

    flow.register_foul(defender.agent_id, attacker.agent_id, assessment=assessment)

    event_types = [event.event_type for event in flow.events]
    assert MatchEventType.PENALTY_AWARDED in event_types
    assert MatchEventType.PENALTY_KICK in event_types
    assert any(event.event_type in {MatchEventType.GOAL, MatchEventType.SAVE} for event in flow.events)


def test_match_result_exposes_final_runtime_condition_and_discipline() -> None:
    flow = MatchFlowController(make_snapshot(seed=8122), config=_short_flow_config())
    flow.start()
    offender = flow.engine.state.player_for_slot(TeamSide.AWAY, "rcb")
    victim = flow.engine.state.player_for_slot(TeamSide.HOME, "st")
    flow.register_foul(offender.agent_id, victim.agent_id, card=CardType.RED)

    result = flow.run_to_completion()
    condition = next(item for item in result.player_conditions if item.agent_id == victim.agent_id)
    discipline = next(item for item in result.discipline if item.agent_id == offender.agent_id)

    assert len(result.player_conditions) == 22
    assert len(result.discipline) == 22
    assert condition.fatigue > victim.player.state.fatigue
    assert discipline.dismissed


def test_runtime_fatigue_does_not_mutate_immutable_match_snapshot() -> None:
    snapshot = make_snapshot(seed=8123)
    frozen_cm = snapshot.home_team.player_for_slot("cm")
    engine = SpatialMatchEngine(snapshot)
    runtime_cm = engine.state.player_for_slot(TeamSide.HOME, "cm")
    engine.set_player_velocity(runtime_cm.agent_id, Vector2(6.0, 0.0))

    engine.advance_ticks(240)

    assert runtime_cm.current_fatigue > frozen_cm.state.fatigue
    assert frozen_cm.state.fatigue == 0.0
    assert frozen_cm.state.fitness == 100.0


def test_match_context_progression_is_deterministic_for_same_snapshot_and_inputs() -> None:
    snapshot = _snapshot_with_context(
        seed=8124,
        weather_type=WeatherType.RAIN,
        temperature_c=29.0,
        wind_kph=25.0,
        humidity=80.0,
        precipitation_intensity=55.0,
        pitch_condition=PitchCondition.WET,
    )
    first = SpatialMatchEngine(snapshot)
    second = SpatialMatchEngine(snapshot)
    first_cm = first.state.player_for_slot(TeamSide.HOME, "cm")
    second_cm = second.state.player_for_slot(TeamSide.HOME, "cm")
    first.set_player_velocity(first_cm.agent_id, Vector2(4.5, 0.5))
    second.set_player_velocity(second_cm.agent_id, Vector2(4.5, 0.5))

    first.advance_ticks(160)
    second.advance_ticks(160)

    assert first.state.signature() == second.state.signature()


def test_artificial_surface_has_distinct_contextual_movement_and_fatigue_effects() -> None:
    hybrid_engine = SpatialMatchEngine(
        _snapshot_with_context(seed=8125, surface=SurfaceType.HYBRID_GRASS)
    )
    artificial_engine = SpatialMatchEngine(
        _snapshot_with_context(seed=8125, surface=SurfaceType.ARTIFICIAL)
    )
    hybrid = hybrid_engine.state.player_for_slot(TeamSide.HOME, "cm")
    artificial = artificial_engine.state.player_for_slot(TeamSide.HOME, "cm")

    assert artificial_engine.context.movement_speed_multiplier(artificial) > hybrid_engine.context.movement_speed_multiplier(hybrid)

    hybrid_engine.set_player_velocity(hybrid.agent_id, Vector2(5.0, 0.0))
    artificial_engine.set_player_velocity(artificial.agent_id, Vector2(5.0, 0.0))
    hybrid_engine.advance_ticks(120)
    artificial_engine.advance_ticks(120)
    assert artificial.current_fatigue > hybrid.current_fatigue


def test_live_fatigue_reduces_defensive_duel_execution_quality() -> None:
    fresh = SpatialMatchEngine(make_snapshot(seed=8126))
    tired = SpatialMatchEngine(make_snapshot(seed=8126))
    for engine in (fresh, tired):
        attacker = engine.state.player_for_slot(TeamSide.HOME, "st")
        defender = engine.state.player_for_slot(TeamSide.AWAY, "rcb")
        attacker.location = Vector2(60.0, 34.0)
        defender.location = Vector2(60.8, 34.0)
        engine.give_ball_to(attacker.agent_id)
    tired_defender = tired.state.player_for_slot(TeamSide.AWAY, "rcb")
    tired_defender.current_fatigue = 90.0
    tired_defender.current_fitness = 50.0

    fresh_profile = fresh.defensive_duel_profile(
        fresh.state.player_for_slot(TeamSide.AWAY, "rcb").agent_id
    )
    tired_profile = tired.defensive_duel_profile(tired_defender.agent_id)

    assert tired_profile.defender_quality < fresh_profile.defender_quality
    assert tired_profile.success_probability < fresh_profile.success_probability


def test_second_yellow_cannot_be_overridden_by_advantage_request() -> None:
    flow = MatchFlowController(make_snapshot(seed=8127), config=_short_flow_config())
    flow.start()
    offender = flow.engine.state.player_for_slot(TeamSide.AWAY, "rcb")
    victim = flow.engine.state.player_for_slot(TeamSide.HOME, "st")
    flow.register_foul(offender.agent_id, victim.agent_id, card=CardType.YELLOW)

    flow.register_foul(
        offender.agent_id,
        victim.agent_id,
        card=CardType.YELLOW,
        advantage=True,
    )

    foul_events = [event for event in flow.events if event.event_type is MatchEventType.FOUL]
    assert foul_events[-1].value("advantage") == "false"
    assert offender.dismissed
    assert any(event.event_type is MatchEventType.RESTART for event in flow.events)
