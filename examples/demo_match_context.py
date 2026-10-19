"""Phase 5.8 football-facing debug demo.

Run from the repository root with:
    $env:PYTHONPATH = "src"
    python examples/demo_match_context.py
"""
from __future__ import annotations

from dataclasses import replace

from football_manager.domain import (
    MatchConditionsSnapshot,
    PitchCondition,
    RefereeSnapshot,
    WeatherSnapshot,
    WeatherType,
)
from football_manager.simulation import (
    CardType,
    FlowConfig,
    MatchEventType,
    MatchFlowController,
    SpatialMatchEngine,
    TeamSide,
    Vector2,
)

from demo_match_factory import build_demo_snapshot


def with_conditions(
    *,
    seed: int,
    weather_type: WeatherType = WeatherType.CLEAR,
    temperature_c: float = 20.0,
    wind_kph: float = 0.0,
    humidity: float = 50.0,
    precipitation_intensity: float = 0.0,
    pitch_condition: PitchCondition = PitchCondition.GOOD,
    referee: RefereeSnapshot | None = None,
):
    snapshot = build_demo_snapshot(seed=seed)
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
    return replace(
        snapshot,
        context=replace(
            snapshot.context,
            conditions=conditions,
            referee=referee or snapshot.context.referee,
        ),
    )


def short_flow() -> FlowConfig:
    return FlowConfig(
        regulation_half_seconds=2.0,
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


def line() -> None:
    print("=" * 96)


def scenario_a() -> None:
    line()
    print("SCENARIO A - SAME PLAYER, MILD CONDITIONS VS HOT / HUMID / HEAVY PITCH")
    line()
    mild = SpatialMatchEngine(with_conditions(seed=8801))
    harsh = SpatialMatchEngine(
        with_conditions(
            seed=8801,
            weather_type=WeatherType.HEAVY_RAIN,
            temperature_c=34.0,
            humidity=90.0,
            precipitation_intensity=85.0,
            pitch_condition=PitchCondition.HEAVY,
        )
    )
    mild_cm = mild.state.player_for_slot(TeamSide.HOME, "cm")
    harsh_cm = harsh.state.player_for_slot(TeamSide.HOME, "cm")
    mild_cm.velocity = Vector2(5.5, 0.0)
    harsh_cm.velocity = Vector2(5.5, 0.0)

    mild.context.update_player_condition(mild.state, 30.0 * 60.0)
    harsh.context.update_player_condition(harsh.state, 30.0 * 60.0)

    print(
        f"Mild       -> fatigue={mild_cm.current_fatigue:5.2f} | fitness={mild_cm.current_fitness:5.2f} "
        f"| movement multiplier={mild.context.movement_speed_multiplier(mild_cm):.3f}"
    )
    print(
        f"Hot/heavy  -> fatigue={harsh_cm.current_fatigue:5.2f} | fitness={harsh_cm.current_fitness:5.2f} "
        f"| movement multiplier={harsh.context.movement_speed_multiplier(harsh_cm):.3f}"
    )
    print("Same base attributes; only live condition and environment changed.")
    print()


def scenario_b() -> None:
    line()
    print("SCENARIO B - RAIN / WIND / PITCH ALTER THE ACTION, NOT THE PLAYER RATING")
    line()
    good = SpatialMatchEngine(with_conditions(seed=8802))
    bad = SpatialMatchEngine(
        with_conditions(
            seed=8802,
            weather_type=WeatherType.STORM,
            temperature_c=12.0,
            wind_kph=65.0,
            humidity=92.0,
            precipitation_intensity=90.0,
            pitch_condition=PitchCondition.WATERLOGGED,
        )
    )
    good_cm = good.state.player_for_slot(TeamSide.HOME, "cm")
    bad_cm = bad.state.player_for_slot(TeamSide.HOME, "cm")
    print(
        "30 m aerial pass -> "
        f"good execution adj={good.context.execution_adjustment(good_cm, pressure=0.4, distance_m=30, aerial=True):+.2f}, "
        f"error x{good.context.error_multiplier(distance_m=30, aerial=True):.2f}"
    )
    print(
        "30 m aerial pass -> "
        f"storm execution adj={bad.context.execution_adjustment(bad_cm, pressure=0.4, distance_m=30, aerial=True):+.2f}, "
        f"error x{bad.context.error_multiplier(distance_m=30, aerial=True):.2f}"
    )
    print(
        f"Ground-ball speed multiplier: good={good.context.ball_speed_multiplier():.3f} "
        f"| waterlogged={bad.context.ball_speed_multiplier():.3f}"
    )
    print(
        f"Passing attribute remains {good_cm.player.attributes.technical.passing} in both contexts."
    )
    print()


def scenario_c() -> None:
    line()
    print("SCENARIO C - REFEREE PROFILE CHANGES FOUL / CARD / ADVANTAGE DECISIONS")
    line()
    lenient_ref = RefereeSnapshot(
        "ref-lenient",
        "Lenient",
        strictness=15,
        contact_tolerance=85,
        card_tendency=20,
        penalty_tendency=35,
        advantage_tendency=80,
    )
    strict_ref = RefereeSnapshot(
        "ref-strict",
        "Strict",
        strictness=90,
        contact_tolerance=10,
        card_tendency=90,
        penalty_tendency=75,
        advantage_tendency=25,
    )
    lenient = SpatialMatchEngine(with_conditions(seed=8803, referee=lenient_ref))
    strict = SpatialMatchEngine(with_conditions(seed=8803, referee=strict_ref))
    for engine in (lenient, strict):
        attacker = engine.state.player_for_slot(TeamSide.HOME, "st")
        defender = engine.state.player_for_slot(TeamSide.AWAY, "rcb")
        attacker.location = Vector2(78.0, 34.0)
        defender.location = Vector2(78.8, 34.0)

    lenient_assessment = lenient.context.foul_assessment(
        lenient.state,
        lenient.state.player_for_slot(TeamSide.AWAY, "rcb"),
        lenient.state.player_for_slot(TeamSide.HOME, "st"),
    )
    strict_assessment = strict.context.foul_assessment(
        strict.state,
        strict.state.player_for_slot(TeamSide.AWAY, "rcb"),
        strict.state.player_for_slot(TeamSide.HOME, "st"),
    )
    print(
        f"Lenient -> foul={lenient_assessment.foul_probability*100:4.1f}% "
        f"| yellow={lenient_assessment.yellow_probability*100:4.1f}% "
        f"| advantage={lenient_assessment.advantage_probability*100:4.1f}%"
    )
    print(
        f"Strict  -> foul={strict_assessment.foul_probability*100:4.1f}% "
        f"| yellow={strict_assessment.yellow_probability*100:4.1f}% "
        f"| advantage={strict_assessment.advantage_probability*100:4.1f}%"
    )
    print()


def scenario_d() -> None:
    line()
    print("SCENARIO D - SECOND YELLOW REALLY REMOVES THE PLAYER FROM ACTIVE PLAY")
    line()
    flow = MatchFlowController(build_demo_snapshot(seed=8804), config=short_flow())
    flow.start()
    offender = flow.engine.state.player_for_slot(TeamSide.AWAY, "rcb")
    victim = flow.engine.state.player_for_slot(TeamSide.HOME, "st")
    print(f"Away active players before cards: {len(flow.engine.state.active_players_for_side(TeamSide.AWAY))}")
    flow.register_foul(offender.agent_id, victim.agent_id, card=CardType.YELLOW)
    print(f"First yellow  -> yellow count={offender.yellow_cards} | dismissed={offender.dismissed}")
    flow.register_foul(offender.agent_id, victim.agent_id, card=CardType.YELLOW)
    print(f"Second yellow -> yellow count={offender.yellow_cards} | dismissed={offender.dismissed}")
    print(f"Away active players after dismissal: {len(flow.engine.state.active_players_for_side(TeamSide.AWAY))}")
    print()


def scenario_e() -> None:
    line()
    print("SCENARIO E - FOUL INSIDE THE BOX BECOMES A REAL PENALTY EVENT")
    line()
    flow = MatchFlowController(build_demo_snapshot(seed=8805), config=short_flow())
    flow.start()
    attacker = flow.engine.state.player_for_slot(TeamSide.HOME, "st")
    defender = flow.engine.state.player_for_slot(TeamSide.AWAY, "rcb")
    attacker.location = Vector2(96.0, 34.0)
    defender.location = Vector2(96.8, 34.0)
    assessment = flow.engine.context.foul_assessment(flow.engine.state, defender, attacker)
    flow.register_foul(defender.agent_id, attacker.agent_id, assessment=assessment)
    penalty_events = [
        event
        for event in flow.events
        if event.event_type in {
            MatchEventType.PENALTY_AWARDED,
            MatchEventType.PENALTY_KICK,
            MatchEventType.GOAL,
            MatchEventType.SAVE,
        }
    ]
    print(f"Detected as penalty area: {assessment.is_penalty_area}")
    for event in penalty_events:
        if event.event_type is MatchEventType.PENALTY_KICK:
            print(
                f"{event.event_type.value}: scored={event.value('scored')} "
                f"| conversion probability={float(event.value('probability'))*100:.1f}%"
            )
        else:
            print(event.event_type.value)
    print(f"Score after penalty sequence: HOME {flow.score.home}-{flow.score.away} AWAY")
    print()


def scenario_f() -> None:
    line()
    print("SCENARIO F - HOME ADVANTAGE IS SMALL AND SITUATIONAL, NOT A RATING BOOST")
    line()
    engine = SpatialMatchEngine(build_demo_snapshot(seed=8806))
    home = engine.state.player_for_slot(TeamSide.HOME, "cm")
    away = engine.state.player_for_slot(TeamSide.AWAY, "cm")
    print(
        "No pressure -> "
        f"HOME adj={engine.context.execution_adjustment(home, pressure=0.0):+.2f} "
        f"| AWAY adj={engine.context.execution_adjustment(away, pressure=0.0):+.2f}"
    )
    print(
        "Heavy pressure -> "
        f"HOME adj={engine.context.execution_adjustment(home, pressure=0.8):+.2f} "
        f"| AWAY adj={engine.context.execution_adjustment(away, pressure=0.8):+.2f}"
    )
    print(
        f"Passing attribute stays HOME={home.player.attributes.technical.passing}, "
        f"AWAY={away.player.attributes.technical.passing}."
    )
    print("Exact contextual strengths are provisional until Phase 5.10 calibration.")


def main() -> None:
    scenario_a()
    scenario_b()
    scenario_c()
    scenario_d()
    scenario_e()
    scenario_f()


if __name__ == "__main__":
    main()
