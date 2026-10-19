"""TS-18.3: existing score-dependent tactical instructions must respect the score."""
from __future__ import annotations

from dataclasses import replace

from examples.demo_match_factory import build_demo_snapshot
from football_manager.domain import Level, analyze_tactical_style
from football_manager.fast_simulation import FastMatchSimulator, build_fast_team_profile
from football_manager.fast_simulation.engine import _ShotRecord, _TeamRuntime
from football_manager.fast_simulation.randomness import FastMatchRandom
from football_manager.fast_simulation.tactical_coverage import tactical_consumer_coverage


def _risk_team(team, level: Level):
    instructions = team.tactic.team_instructions
    management = replace(instructions.game_management, risk_when_leading=level)
    instructions = replace(instructions, game_management=management)
    tactic = replace(team.tactic, team_instructions=instructions, style=analyze_tactical_style(instructions))
    return replace(team, tactic=tactic)


def _runtime(team):
    return _TeamRuntime(team=team, profile=build_fast_team_profile(team))


def _goal(player, minute):
    return _ShotRecord(
        player_id=player.player_id, assist_player_id=None,
        xg=0.2, on_target=True, goal=True, minute=minute, extra_time=minute > 90,
    )


def test_leading_only_instruction_does_not_modify_unconditional_tactical_style():
    base = build_demo_snapshot(seed=18301).home_team
    timid = _risk_team(base, Level.VERY_LOW)
    bold = _risk_team(base, Level.VERY_HIGH)
    assert timid.tactic.style.risk == bold.tactic.style.risk
    assert build_fast_team_profile(timid).risk == build_fast_team_profile(bold).risk
    assert build_fast_team_profile(timid).risk_when_leading == 0.0
    assert build_fast_team_profile(bold).risk_when_leading == 100.0


def test_leading_only_instruction_is_reported_as_conditional_not_unconditional():
    coverage = {item.control: item.status for item in tactical_consumer_coverage()}
    assert coverage['game_management.risk_when_leading'] == 'partial_match_effect'
    assert coverage['player.shooting_frequency'] == 'match_effect'
    assert coverage['player.attack_space'] == 'match_effect'


def test_no_goal_means_no_leading_risk_replay(monkeypatch):
    base = build_demo_snapshot(seed=18302)
    home = _runtime(_risk_team(base.home_team, Level.VERY_HIGH))
    away = _runtime(_risk_team(base.away_team, Level.VERY_LOW))
    shot = replace(_goal(home.team.starters[0], 40), goal=False, on_target=False)
    home.shots = [shot]
    engine = FastMatchSimulator()
    def must_not_resimulate(*args, **kwargs):
        raise AssertionError('A tied game must not trigger risk replay')
    monkeypatch.setattr(engine, '_simulate_shot_windows', must_not_resimulate)
    engine._apply_score_dependent_risk(home, away, random=FastMatchRandom(18302))
    assert home.shots == [shot]
    assert not away.shots


def test_leading_risk_applies_after_goal_and_resets_after_equalizer(monkeypatch):
    base = build_demo_snapshot(seed=18303)
    home = _runtime(_risk_team(base.home_team, Level.VERY_HIGH))
    away = _runtime(_risk_team(base.away_team, Level.NORMAL))
    home.shots = [_goal(home.team.starters[0], 18)]
    engine = FastMatchSimulator()
    calls = []

    def simulate_window(attacker, defender, **kwargs):
        calls.append((attacker.team.club_id, kwargs['minute_start'], attacker.profile.risk, defender.profile.risk))
        # One equalizer, generated only in the post-lead window.
        if attacker is away and kwargs['minute_start'] == 19:
            attacker.shots.append(_goal(away.team.starters[0], 34))

    monkeypatch.setattr(engine, '_simulate_shot_windows', simulate_window)
    baseline_home = home.profile.risk
    baseline_away = away.profile.risk
    engine._apply_score_dependent_risk(home, away, random=FastMatchRandom(18303))

    assert len(calls) == 4
    assert calls[0] == (home.team.club_id, 19, baseline_home + 50.0 / 3.0, baseline_away)
    assert calls[1] == (away.team.club_id, 19, baseline_away, baseline_home + 50.0 / 3.0)
    assert calls[2] == (home.team.club_id, 35, baseline_home, baseline_away)
    assert calls[3] == (away.team.club_id, 35, baseline_away, baseline_home)
    assert home.profile.risk == baseline_home
    assert away.profile.risk == baseline_away
    assert len(home.shots) == len(away.shots) == 1


def test_risk_for_trailing_side_does_not_activate_when_opponent_leads(monkeypatch):
    base = build_demo_snapshot(seed=18304)
    home = _runtime(_risk_team(base.home_team, Level.NORMAL))
    away = _runtime(_risk_team(base.away_team, Level.VERY_HIGH))
    home.shots = [_goal(home.team.starters[0], 20)]
    engine = FastMatchSimulator()
    monkeypatch.setattr(engine, '_simulate_shot_windows', lambda *a, **kw: (_ for _ in ()).throw(AssertionError('wrong activation')))
    engine._apply_score_dependent_risk(home, away, random=FastMatchRandom(18304))
    assert sum(shot.goal for shot in home.shots) == 1


def test_minute_90_lead_cannot_change_earlier_chances(monkeypatch):
    base = build_demo_snapshot(seed=18305)
    home = _runtime(_risk_team(base.home_team, Level.VERY_HIGH))
    away = _runtime(base.away_team)
    home.shots = [_goal(home.team.starters[0], 90)]
    engine = FastMatchSimulator()
    monkeypatch.setattr(engine, '_simulate_shot_windows', lambda *a, **kw: (_ for _ in ()).throw(AssertionError('no minutes remain')))
    engine._apply_score_dependent_risk(home, away, random=FastMatchRandom(18305))
    assert len(home.shots) == 1


def test_full_match_is_deterministic_with_nondefault_leading_risk():
    base = build_demo_snapshot(seed=18306)
    snapshot = replace(base, home_team=_risk_team(base.home_team, Level.VERY_HIGH), away_team=_risk_team(base.away_team, Level.VERY_LOW))
    engine = FastMatchSimulator()
    assert engine.simulate(snapshot) == engine.simulate(snapshot)


def test_different_leading_risk_levels_have_same_match_before_first_lead():
    base = build_demo_snapshot(seed=18307)
    engine = FastMatchSimulator()
    for seed in range(18307, 18377):
        low = replace(base, seed=seed, home_team=_risk_team(base.home_team, Level.VERY_LOW))
        high = replace(base, seed=seed, home_team=_risk_team(base.home_team, Level.VERY_HIGH))
        control = engine.simulate(low)
        treatment = engine.simulate(high)
        goals_low = sorted((goal.minute, goal.club_id) for goal in control.goals if goal.minute <= 90)
        goals_high = sorted((goal.minute, goal.club_id) for goal in treatment.goals if goal.minute <= 90)
        assert (goals_low[0] if goals_low else None) == (goals_high[0] if goals_high else None)


def test_unmodelled_player_controls_are_not_falsely_advertised():
    entries = {entry.control: entry.status for entry in tactical_consumer_coverage()}
    assert entries['player.dribbling_frequency'] == 'match_effect'
    assert entries['player.shooting_frequency'] == 'match_effect'
    assert entries['player.attack_space'] == 'match_effect'


class _FixedZeroRandom:
    """Deterministic boundary RNG to isolate the late-management acceptance."""
    def fork(self, namespace: str):
        return self

    def random(self):
        return 0.0


def test_time_wasting_also_filters_extra_urgency_chances(monkeypatch):
    base = build_demo_snapshot(seed=18308)
    instructions = base.home_team.tactic.team_instructions
    instructions = replace(
        instructions,
        game_management=replace(instructions.game_management, time_wasting=Level.VERY_HIGH),
    )
    home_team = replace(base.home_team, tactic=replace(base.home_team.tactic, team_instructions=instructions))
    instructions = base.away_team.tactic.team_instructions
    instructions = replace(
        instructions,
        game_management=replace(instructions.game_management, urgency_when_trailing=Level.VERY_HIGH),
    )
    away_team = replace(base.away_team, tactic=replace(base.away_team.tactic, team_instructions=instructions))
    home, away = _runtime(home_team), _runtime(away_team)
    home.shots = [_goal(home.team.starters[0], 12)]
    late_chance = replace(_goal(away.team.starters[0], 75), goal=False, on_target=False)
    engine = FastMatchSimulator()

    def make_urgency(attacker, defender, **kwargs):
        assert kwargs['minute_start'] == 71
        attacker.shots.append(late_chance)

    monkeypatch.setattr(engine, '_simulate_shot_windows', make_urgency)
    engine._apply_regulation_game_management(home, away, _FixedZeroRandom())
    assert home.shots == [_goal(home.team.starters[0], 12)]
    assert away.shots == []  # Leader's time wasting applies to *all* chances.


def test_urgency_chances_survive_without_time_wasting(monkeypatch):
    base = build_demo_snapshot(seed=18309)
    instructions = base.away_team.tactic.team_instructions
    instructions = replace(
        instructions,
        game_management=replace(instructions.game_management, urgency_when_trailing=Level.VERY_HIGH),
    )
    away_team = replace(base.away_team, tactic=replace(base.away_team.tactic, team_instructions=instructions))
    home, away = _runtime(base.home_team), _runtime(away_team)
    home.shots = [_goal(home.team.starters[0], 12)]
    late_chance = replace(_goal(away.team.starters[0], 76), goal=False, on_target=False)
    engine = FastMatchSimulator()
    monkeypatch.setattr(engine, '_simulate_shot_windows', lambda attacker, defender, **kw: attacker.shots.append(late_chance))
    engine._apply_regulation_game_management(home, away, _FixedZeroRandom())
    assert away.shots == [late_chance]


def test_lead_at_extra_time_start_activates_risk_without_changing_regulation(monkeypatch):
    base = build_demo_snapshot(seed=18310)
    home = _runtime(_risk_team(base.home_team, Level.VERY_LOW))
    away = _runtime(base.away_team)
    regulation_goal = _goal(home.team.starters[0], 41)
    home.shots = [regulation_goal]
    baseline_risk = home.profile.risk
    observed = []

    def replay(attacker, defender, **kw):
        observed.append((kw['minute_start'], kw['minute_end'],
                         attacker.profile.risk, defender.profile.risk,
                         kw['pace_factor'], kw['attacker_energy'], kw['defender_energy']))

    engine = FastMatchSimulator()
    monkeypatch.setattr(engine, '_simulate_shot_windows', replay)
    engine._apply_score_dependent_risk(
        home, away, random=FastMatchRandom(18310), minute_start=91,
        minute_end=105, pace_factor=0.76, home_energy=0.72, away_energy=0.83,
    )
    assert observed == [
        (91, 105, baseline_risk - 50.0 / 3.0, away.profile.risk, 0.76, 0.72, 0.83),
        (91, 105, away.profile.risk, baseline_risk - 50.0 / 3.0, 0.76, 0.83, 0.72),
    ]
    assert home.shots == [regulation_goal]
    assert home.profile.risk == baseline_risk


def test_two_simultaneous_opposing_goals_do_not_activate_risk(monkeypatch):
    base = build_demo_snapshot(seed=18311)
    home = _runtime(_risk_team(base.home_team, Level.VERY_HIGH))
    away = _runtime(_risk_team(base.away_team, Level.VERY_LOW))
    home.shots = [_goal(home.team.starters[0], 28)]
    away.shots = [_goal(away.team.starters[0], 28)]
    engine = FastMatchSimulator()
    def should_not_run(*args, **kwargs):
        raise AssertionError('No lead exists after simultaneous goals')
    monkeypatch.setattr(engine, '_simulate_shot_windows', should_not_run)
    engine._apply_score_dependent_risk(home, away, random=FastMatchRandom(18311))
    assert len(home.shots) == len(away.shots) == 1
