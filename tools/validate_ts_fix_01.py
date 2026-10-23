"""Run TS-FIX-01 match invariants and an actual calendar season.

Example (from project root):
  python tools/validate_ts_fix_01.py --season --samples 300 --output reports/ts_fix_01_validation.json

Uses temporary save files and never opens or overwrites the manager's saves.
"""
from __future__ import annotations
import argparse
from collections import Counter
from dataclasses import replace
from datetime import date
import json
from pathlib import Path
import statistics
import sys
from tempfile import TemporaryDirectory
from time import perf_counter

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT / 'src'), str(ROOT)]

from football_manager.fast_simulation import FastMatchSimulator, FastCardType
from football_manager.fast_simulation.ai_coaching import coach_for_match


def check_match(snapshot, result):
    duration = 120 if result.decision.value == 'extra_time' or any(s.extra_time for s in result.substitutions) else 90
    if any(s.end_minute > 90 for s in result.role_segments):
        duration = 120
    entries = {s.player_in_id: s.minute - 1 for s in result.substitutions}
    exits = {s.player_out_id: s.minute - 1 for s in result.substitutions}
    reds = {c.player_id: c.minute for c in result.cards if c.card is FastCardType.RED}
    segments = Counter()
    for segment in result.role_segments:
        segments[segment.player_id] += segment.minutes
    for p in result.player_statistics:
        assert p.minutes == min(exits.get(p.player_id, duration), reds.get(p.player_id, duration)) - entries.get(p.player_id, 0)
        if result.role_segments:
            assert segments[p.player_id] == p.minutes
        assert 0 <= p.condition_after <= 100 and 0 <= p.fatigue_after <= 100
    for goal in result.goals:
        for pid in (goal.scorer_player_id, goal.assist_player_id):
            if pid:
                assert entries.get(pid, 0) < goal.minute <= min(exits.get(pid, duration), reds.get(pid, duration))
    for card in result.cards:
        assert entries.get(card.player_id, 0) < card.minute <= min(exits.get(card.player_id, duration), reds.get(card.player_id, duration))
    rules = snapshot.context.competition
    for team, total in ((snapshot.home_team, result.statistics_home), (snapshot.away_team, result.statistics_away)):
        players = [p for p in result.player_statistics if p.club_id == team.club_id]
        lost = sum(duration - c.minute for c in result.cards if c.club_id == team.club_id and c.card is FastCardType.RED)
        assert sum(p.minutes for p in players) == 11 * duration - lost
        for field in ('shots', 'shots_on_target', 'fouls', 'yellow_cards', 'red_cards', 'passes_attempted', 'passes_completed'):
            assert getattr(total, field) == sum(getattr(p, field) for p in players)
        subs = [s for s in result.substitutions if s.club_id == team.club_id]
        assert len({s.player_in_id for s in subs}) == len(subs)
        assert len(subs) <= rules.substitution_limit + (rules.extra_time_additional_substitutions if duration == 120 else 0)
        if result.role_segments:
            # The legacy no-coach API retains its historical ET hook.
            assert len({s.minute for s in subs if s.minute <= 90 and s.minute != 46}) <= rules.substitution_window_limit
            assert len({s.minute for s in subs if s.minute not in (46, 91, 106)}) <= rules.substitution_window_limit + (rules.extra_time_additional_windows if duration == 120 else 0)


def sample_matches(count):
    from examples.demo_match_factory import build_demo_snapshot
    from football_manager.fast_calibration.scenarios import neutralize_fast_snapshot
    engine = FastMatchSimulator()
    base = neutralize_fast_snapshot(build_demo_snapshot(seed=1), rating=70, seed=1)
    totals = {key: [] for key in ('goals', 'shots', 'xg', 'substitutions', 'yellow_cards', 'red_cards')}
    for seed in range(1000, 1000 + count):
        snapshot = replace(base, seed=seed)
        coaches = {t.club_id: coach_for_match(seed, t.club_id, t.tactic.preset_origin.value, snapshot.match_id)
                   for t in (snapshot.home_team, snapshot.away_team)}
        result = engine.simulate(snapshot, ai_coaches=coaches)
        check_match(snapshot, result)
        if seed < 1005:
            assert result == engine.simulate(snapshot, ai_coaches=coaches)
        totals['goals'].append(result.home_goals + result.away_goals)
        totals['substitutions'].append(len(result.substitutions))
        for field in ('shots', 'xg', 'yellow_cards', 'red_cards'):
            totals[field].append(getattr(result.statistics_home, field) + getattr(result.statistics_away, field))
    return {'matches': count, 'mean': {key: round(statistics.mean(values), 4) for key, values in totals.items()},
            'substitutions_min_max': [min(totals['substitutions']), max(totals['substitutions'])],
            'invariants_passed': True}


def run_season(seed):
    from football_manager.dev_ui.session import DevelopmentSession
    from football_manager.ui_shell.progression import simulate_until
    from football_manager.persistence import SQLiteSaveRepository
    from football_manager.persistence.manager_career import save_manager_career, load_manager_career, validate_manager_session
    from football_manager.services.youth_match_development import advance_youth_matches
    match_count = 0
    subs_count = 0
    managed_subs = []
    observations = []
    original = FastMatchSimulator.simulate
    def checked(self, snapshot, **kwargs):
        nonlocal match_count, subs_count
        result = original(self, snapshot, **kwargs)
        check_match(snapshot, result)
        match_count += 1
        subs_count += len(result.substitutions)
        if 'northbridge' in (result.home_club_id, result.away_club_id):
            managed_subs.append(sum(s.club_id == 'northbridge' for s in result.substitutions))
        return result
    FastMatchSimulator.simulate = checked
    try:
        session = DevelopmentSession(world_seed=seed)
        def on_day(day, results):
            if day.day != 1:
                return
            youth = session._world_squads.youth
            academy = youth.academies[session.home_club.id]
            observation = {'date': day.isoformat()}
            for level in ('u17', 'u21'):
                roster = getattr(academy, level)
                sharp = [round(p.state.match_sharpness, 2) for p in roster.values()]
                observation[level] = {'players': len(roster), 'min': min(sharp), 'max': max(sharp),
                    'distinct': len(set(sharp)), 'played_last_28_days': sum(bool(youth.recent_participation.get(p.id)) for p in roster.values())}
            observations.append(observation)
            print('Season checkpoint', day, 'senior matches checked', match_count, flush=True)
        progress = simulate_until(session, date(2027, 6, 30), on_day=on_day)
        validate_manager_session(session)
        assert session.season_finished
        assert len(session._world.results) == len(session._world.fixtures)
        youth = session._world_squads.youth
        for history in youth.recent_participation.values():
            assert len(history) == len({d for d, _ in history}) <= 29
        with TemporaryDirectory(prefix='ts-fix-01-') as temporary:
            repo = SQLiteSaveRepository(Path(temporary) / 'career.sqlite3')
            save_manager_career(repo, slot_id='validation', display_name='TS-FIX-01 validation',
                                session=session, expected_revision=0)
            restored = load_manager_career(repo, 'validation').session
            validate_manager_session(restored)
            assert restored._world.results == session._world.results
            assert restored._world_squads.youth == youth
        return {'seed': seed, 'from': progress['from_date'], 'to': progress['to_date'],
                'managed_matches': progress['managed_matches'], 'background_matches': progress['background_matches'],
                'world_results': len(session._world.results), 'world_fixtures': len(session._world.fixtures),
                'fast_matches_checked_including_initialization': match_count,
                'substitutions': subs_count, 'managed_subs_min_max': [min(managed_subs), max(managed_subs)],
                'youth_matches_played': sum(f.home_goals is not None for f in youth.fixtures.values()),
                'youth_matches_total': len(youth.fixtures), 'monthly_observations': observations,
                'season_complete': True, 'sqlite_roundtrip': True, 'all_invariants_passed': True}
    finally:
        FastMatchSimulator.simulate = original


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--samples', type=int, default=300)
    parser.add_argument('--season', action='store_true')
    parser.add_argument('--seed', type=int, default=6606)
    parser.add_argument('--output', type=Path, default=ROOT / 'reports/ts_fix_01_validation.json')
    args = parser.parse_args()
    if args.samples < 1:
        parser.error('--samples must be positive')
    started = perf_counter()
    report = {'patch': 'TS-FIX-01', 'status': 'running'}
    try:
        report['sample'] = sample_matches(args.samples)
        print('Sample passed:', report['sample'], flush=True)
        if args.season:
            report['season'] = run_season(args.seed)
        report['status'] = 'passed'
    except Exception as exc:
        report.update(status='failed', error=f'{type(exc).__name__}: {exc}')
        raise
    finally:
        report['seconds'] = round(perf_counter() - started, 2)
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(json.dumps(report, indent=2), encoding='utf-8')
    print('Validation:', report['status'], 'Report:', args.output, flush=True)


if __name__ == '__main__':
    main()
