"""TS-19 updates the historical backlog to reflect implemented consumers.

TS-13: tactical controls must not silently masquerade as fast-sim effects."""

from collections import Counter
from dataclasses import fields, replace

from examples.demo_match_factory import build_demo_snapshot
from football_manager.domain import (
    GameManagementInstructions,
    InPossessionInstructions,
    Level,
    OutOfPossessionInstructions,
    PlayerInstructions,
    TransitionInstructions,
)
from football_manager.fast_simulation import FastMatchSimulator, build_fast_team_profile
from football_manager.fast_simulation.engine import _ShotRecord, _TeamRuntime
from football_manager.fast_simulation.randomness import FastMatchRandom
from football_manager.fast_simulation.tactical_coverage import tactical_consumer_coverage


def _change_team_instruction(team, group: str, field: str, value):
    instructions = team.tactic.team_instructions
    new_group = replace(getattr(instructions, group), **{field: value})
    new_instructions = replace(instructions, **{group: new_group})
    return replace(team, tactic=replace(team.tactic, team_instructions=new_instructions))


def _runtime(team):
    return _TeamRuntime(team=team, profile=build_fast_team_profile(team))


def _shot(minute: int, player_id: str, goal: bool = False):
    return _ShotRecord(
        player_id=player_id, assist_player_id=None, xg=0.15,
        on_target=goal, goal=goal, minute=minute, extra_time=False,
    )


def test_coverage_catalogue_lists_every_control_once() -> None:
    entries = tactical_consumer_coverage()
    names = [entry.control for entry in entries]
    expected = {
        f"{group}.{item.name}"
        for group, schema in (
            ("in_possession", InPossessionInstructions),
            ("transition", TransitionInstructions),
            ("out_of_possession", OutOfPossessionInstructions),
            ("game_management", GameManagementInstructions),
            ("player", PlayerInstructions),
        )
        for item in fields(schema)
    }
    assert set(names) == expected
    assert len(names) == len(set(names))
    assert all(entry.status in {
        "match_effect", "partial_match_effect", "player_conditioning",
        "style_label_only", "not_modelled",
    } for entry in entries)
    assert Counter(entry.status for entry in entries)["not_modelled"] == 0


def test_coverage_does_not_claim_silent_controls_are_used() -> None:
    catalogue = {item.control: item.status for item in tactical_consumer_coverage()}
    assert catalogue["in_possession.long_shot_frequency"] == "match_effect"
    assert catalogue["out_of_possession.marking_style"] == "match_effect"
    assert catalogue["transition.goalkeeper_release_speed"] == "match_effect"
    assert catalogue["player.shooting_frequency"] == "match_effect"
    assert catalogue["game_management.risk_when_leading"] == "partial_match_effect"
    assert catalogue["game_management.time_wasting"] == "partial_match_effect"
    assert catalogue["game_management.urgency_when_trailing"] == "partial_match_effect"
    assert catalogue["out_of_possession.offside_trap"] == "match_effect"


def test_three_match_controls_reach_the_profile() -> None:
    base = build_demo_snapshot(seed=13).home_team
    changed = _change_team_instruction(base, "out_of_possession", "offside_trap", True)
    changed = _change_team_instruction(changed, "game_management", "time_wasting", Level.VERY_HIGH)
    changed = _change_team_instruction(changed, "game_management", "urgency_when_trailing", Level.VERY_HIGH)
    profile = build_fast_team_profile(changed)
    assert profile.offside_trap is True
    assert profile.time_wasting == 100.0
    assert profile.urgency_when_trailing == 100.0


def test_offside_trap_is_a_contextual_effect_not_free_bonus() -> None:
    base = build_demo_snapshot(seed=13)
    engine = FastMatchSimulator()
    attacker, defender = engine.profiles(base)
    patient = replace(attacker, directness=15.0)
    direct = replace(attacker, directness=95.0)
    coherent = replace(defender, offside_trap=True, defensive_depth=90.0, pressing=90.0)
    exposed = replace(defender, offside_trap=True, defensive_depth=15.0, pressing=40.0)
    assert engine._offside_trap_matchup(patient, coherent) > 0
    assert engine._offside_trap_matchup(direct, exposed) < 0
    assert engine._tactical_shot_edge(patient, coherent) < engine._tactical_shot_edge(patient, replace(coherent, offside_trap=False))
    assert engine._tactical_shot_edge(direct, exposed) > engine._tactical_shot_edge(direct, replace(exposed, offside_trap=False))
    assert engine._offside_trap_matchup(direct, replace(coherent, offside_trap=False)) == 0.0


def test_time_wasting_reduces_both_sides_late_chances_only_when_leading() -> None:
    base = build_demo_snapshot(seed=13)
    changed_home = _change_team_instruction(base.home_team, "game_management", "time_wasting", Level.VERY_HIGH)
    engine = FastMatchSimulator()
    home, away = _runtime(changed_home), _runtime(base.away_team)
    first = home.team.starters[0].player_id
    rival = away.team.starters[0].player_id
    home.shots = [_shot(10, first, True)] + [_shot(x, first) for x in range(65, 90)]
    away.shots = [_shot(x, rival) for x in range(65, 90)]
    engine._apply_regulation_game_management(home, away, FastMatchRandom(13))
    assert home.shots[0].goal
    assert len(home.shots) + len(away.shots) < 51
    # Without any lead, time wasting must not affect the opportunities.
    home2, away2 = _runtime(changed_home), _runtime(base.away_team)
    home2.shots = [_shot(x, first) for x in range(65, 90)]
    away2.shots = [_shot(x, rival) for x in range(65, 90)]
    engine._apply_regulation_game_management(home2, away2, FastMatchRandom(13))
    assert len(home2.shots) + len(away2.shots) == 50


def test_high_urgency_only_adds_late_chances_if_trailing() -> None:
    base = build_demo_snapshot(seed=13)
    high_urgency = _change_team_instruction(base.away_team, "game_management", "urgency_when_trailing", Level.VERY_HIGH)
    engine = FastMatchSimulator()
    home, away = _runtime(base.home_team), _runtime(high_urgency)
    home.shots = [_shot(11, home.team.starters[0].player_id, True)]
    count = 0
    for seed in range(120):
        h, a = _runtime(base.home_team), _runtime(high_urgency)
        h.shots = home.shots.copy()
        engine._apply_regulation_game_management(h, a, FastMatchRandom(seed))
        assert all(71 <= shot.minute <= 90 for shot in a.shots)
        count += len(a.shots)
    assert count > 30  # Extra volume is real but not a guaranteed comeback.
    tied_home, tied_away = _runtime(base.home_team), _runtime(high_urgency)
    engine._apply_regulation_game_management(tied_home, tied_away, FastMatchRandom(13))
    assert tied_away.shots == []


def test_no_active_management_preserves_all_existing_shots() -> None:
    base = build_demo_snapshot(seed=13)
    home, away = _runtime(base.home_team), _runtime(base.away_team)
    home.shots = [_shot(11, home.team.starters[0].player_id, True), _shot(75, home.team.starters[0].player_id)]
    away.shots = [_shot(81, away.team.starters[0].player_id)]
    original = (home.shots.copy(), away.shots.copy())
    FastMatchSimulator()._apply_regulation_game_management(home, away, FastMatchRandom(13))
    assert (home.shots, away.shots) == original


def test_seeded_fast_match_deterministic_with_new_tactical_effects() -> None:
    base = build_demo_snapshot(seed=13)
    home = _change_team_instruction(base.home_team, "out_of_possession", "offside_trap", True)
    home = _change_team_instruction(home, "game_management", "time_wasting", Level.HIGH)
    away = _change_team_instruction(base.away_team, "game_management", "urgency_when_trailing", Level.VERY_HIGH)
    snapshot = replace(base, home_team=home, away_team=away)
    sim = FastMatchSimulator()
    assert sim.simulate(snapshot) == sim.simulate(snapshot)
