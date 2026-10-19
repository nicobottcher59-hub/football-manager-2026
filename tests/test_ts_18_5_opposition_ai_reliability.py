"""Regression checks for existing opponent extra-time selection."""
from dataclasses import replace
from examples.demo_match_factory import build_demo_snapshot
from football_manager.domain import Position
from football_manager.fast_simulation.engine import FastMatchSimulator, _TeamRuntime
from football_manager.fast_simulation.profiles import build_fast_team_profile
from football_manager.fast_simulation.randomness import FastMatchRandom


def _runtime(seed):
    team = build_demo_snapshot(seed=seed).away_team
    return _TeamRuntime(team, build_fast_team_profile(team))


def test_opponent_substitute_maintains_assignment():
    runtime = _runtime(185)
    FastMatchSimulator()._apply_extra_time_substitutions(runtime, 1, FastMatchRandom(185))
    for event in runtime.substitutions:
        replacement = next(p for p in runtime.team.starters if p.player_id == event.player_in_id)
        assert replacement.assigned_position is not Position.GK
        assert replacement.assigned_slot_id is not None
        assert replacement.role_id is not None
        assert event.player_in_id not in {p.player_id for p in runtime.team.bench}


def test_opponent_skips_unassigned_jobs():
    runtime = _runtime(186)
    runtime.team = replace(runtime.team, starters=tuple(
        replace(p, role_id=None)
        if p.assigned_position is not Position.GK else p
        for p in runtime.team.starters
    ))
    FastMatchSimulator()._apply_extra_time_substitutions(runtime, 1, FastMatchRandom(186))
    assert not runtime.substitutions


def test_opponent_respects_zero_allowance():
    runtime = _runtime(187)
    initial = runtime.team
    FastMatchSimulator()._apply_extra_time_substitutions(runtime, 0, FastMatchRandom(187))
    assert runtime.team == initial
    assert not runtime.substitutions


def test_opponent_never_substitutes_dismissed_players():
    runtime = _runtime(188)
    runtime.dismissed_at = {p.player_id: 60 for p in runtime.team.starters if p.assigned_position is not Position.GK}
    FastMatchSimulator()._apply_extra_time_substitutions(runtime, 1, FastMatchRandom(188))
    assert not runtime.substitutions



def test_generated_opponent_lineup_and_tactic_reach_simulator_snapshot():
    from football_manager.dev_ui.session import DevelopmentSession
    from football_manager.domain.tactical_presets import instructions_for_preset
    session = DevelopmentSession()
    session._prepare_development_opponent()
    snapshot = session._build_snapshot()
    rival = snapshot.away_team if session.managed_is_home else snapshot.home_team
    assert rival.club_id == session.away_club.id
    assert len(rival.starters) == 11
    assert len(rival.bench) == 7
    assert rival.tactic.team_instructions == session.away_tactic.team_instructions
    assert {p.player_id for p in rival.starters} == {entry.player.id for entry in session.away_lineup.starters}
    assert all(p.role_id is not None for p in rival.starters)
    assert len({p.assigned_slot_id for p in rival.starters}) == 11


def test_opponent_snapshot_simulation_is_deterministic():
    from football_manager.dev_ui.session import DevelopmentSession
    session = DevelopmentSession()
    session._prepare_development_opponent()
    snapshot = session._build_snapshot()
    simulator = FastMatchSimulator()
    first = simulator.simulate(snapshot)
    second = simulator.simulate(snapshot)
    assert first == second
    participating = {p.player_id for p in snapshot.home_team.starters + snapshot.away_team.starters}
    assert {goal.scorer_player_id for goal in first.goals}.issubset(participating)


def test_generated_opponent_presets_preserve_lineup_and_roles():
    from football_manager.dev_ui.session import _build_side, _AWAY_NAMES
    from football_manager.domain.tactical_presets import TacticalPreset, instructions_for_preset
    for preset in (TacticalPreset.BALANCED, TacticalPreset.COUNTER_ATTACK,
                   TacticalPreset.POSSESSION, TacticalPreset.CONSTANT_PRESS):
        club, lineup, tactic = _build_side(
            club_id='ts185-rival', name='TS185 Rival', short_name='Rival',
            base_offset=0, tactic_preset=preset, names=_AWAY_NAMES,
        )
        assert len(lineup.starters) == 11
        assert len(lineup.bench) == 7
        assert len({entry.player.id for entry in lineup.starters}) == 11
        assert len({entry.slot_id for entry in lineup.starters}) == 11
        assert tactic.team_instructions == instructions_for_preset(preset)
        assert {p.id for p in club.squad.players} >= {entry.player.id for entry in lineup.starters}
