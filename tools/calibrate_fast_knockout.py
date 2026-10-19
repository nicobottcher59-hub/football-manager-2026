from __future__ import annotations

import argparse
import sys
import time
from dataclasses import replace
from pathlib import Path
from statistics import fmean

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
for path in (str(SRC), str(ROOT)):
    if path not in sys.path:
        sys.path.insert(0, path)

from examples.demo_match_factory import build_demo_snapshot
from football_manager.domain import MatchDecider, Position
from football_manager.fast_calibration.scenarios import neutralize_fast_snapshot
from football_manager.fast_simulation import FastMatchDecision, FastMatchSimulator


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Phase 5.11D extra-time and penalty-shootout benchmark.",
    )
    parser.add_argument("--matches", type=int, default=500)
    parser.add_argument("--seed-start", type=int, default=511_400)
    return parser


def _with_seed(snapshot, seed: int):
    return replace(snapshot, seed=seed, match_id=f"phase-5-11d-{seed}")


def _with_decider(snapshot, decider: MatchDecider, *, extra_subs: int = 1):
    competition = replace(
        snapshot.context.competition,
        match_decider=decider,
        extra_time_additional_substitutions=extra_subs,
    )
    return replace(snapshot, context=replace(snapshot.context, competition=competition))


def _familiar_bench(team):
    role_ids = tuple(sorted({slot.role_id for slot in team.tactic.slots}))
    bench = []
    for player in team.bench:
        familiarity = replace(
            player.familiarity,
            roles=tuple((role_id, 65.0) for role_id in role_ids),
            tactics=((team.tactic.tactic_id, 65.0),),
        )
        bench.append(replace(player, familiarity=familiarity))
    return replace(team, bench=tuple(bench))


def _base(seed: int):
    snapshot = neutralize_fast_snapshot(build_demo_snapshot(seed=seed), rating=70, seed=seed)
    return replace(
        snapshot,
        home_team=_familiar_bench(snapshot.home_team),
        away_team=_familiar_bench(snapshot.away_team),
    )


def _tune_penalties(team, penalties: int, confidence: float):
    starters = []
    for player in team.starters:
        attrs = replace(
            player.attributes,
            technical=replace(player.attributes.technical, penalties=penalties),
        )
        starters.append(
            replace(player, attributes=attrs, state=replace(player.state, confidence=confidence))
        )
    return replace(team, starters=tuple(starters))


def main(argv: list[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    if args.matches <= 0:
        raise SystemExit("--matches must be positive")
    if args.seed_start < 0:
        raise SystemExit("--seed-start cannot be negative")

    simulator = FastMatchSimulator()
    base = _base(args.seed_start)
    league = _with_decider(base, MatchDecider.DRAW_ALLOWED)
    knockout = _with_decider(base, MatchDecider.EXTRA_TIME_AND_PENALTIES)

    decisions = {decision: 0 for decision in FastMatchDecision}
    extra_shots: list[int] = []
    extra_xg: list[float] = []
    extra_goals: list[int] = []
    shootouts = []
    condition_90: list[float] = []
    condition_120: list[float] = []
    substitution_counts: list[int] = []

    started = time.perf_counter()
    for offset in range(args.matches):
        seed = args.seed_start + offset
        ninety = simulator.simulate(_with_seed(league, seed))
        result = simulator.simulate(_with_seed(knockout, seed))
        decisions[result.decision] += 1

        if ninety.decision is FastMatchDecision.DRAW:
            extra_shots.append(
                result.statistics_home.shots
                + result.statistics_away.shots
                - ninety.statistics_home.shots
                - ninety.statistics_away.shots
            )
            extra_xg.append(
                result.statistics_home.xg
                + result.statistics_away.xg
                - ninety.statistics_home.xg
                - ninety.statistics_away.xg
            )
            extra_goals.append(result.extra_time_home_goals + result.extra_time_away_goals)
            substitution_counts.append(len(result.substitutions))
            condition_90.extend(item.condition_after for item in ninety.player_statistics)
            condition_120.extend(
                item.condition_after for item in result.player_statistics if item.minutes >= 120
            )
        if result.decision is FastMatchDecision.PENALTIES:
            shootouts.append(result)

    elapsed = time.perf_counter() - started
    reached_extra_time = len(extra_goals)
    kicks = [kick for result in shootouts for kick in result.penalty_kicks]
    scored_kicks = sum(kick.scored for kick in kicks)
    sudden_shootouts = sum(any(kick.sudden_death for kick in result.penalty_kicks) for result in shootouts)
    home_shootout_wins = sum(result.penalties_home > result.penalties_away for result in shootouts)

    print("\nFAST KNOCKOUT - EQUAL 70 v 70")
    print("=" * 88)
    print(
        f"N={args.matches} | regulation={decisions[FastMatchDecision.REGULATION]} | "
        f"reached ET={reached_extra_time} | ET winner={decisions[FastMatchDecision.EXTRA_TIME]} | "
        f"penalties={decisions[FastMatchDecision.PENALTIES]}"
    )
    if reached_extra_time:
        print(
            f"ET avg added goals={fmean(extra_goals):.2f} | shots={fmean(extra_shots):.2f} | "
            f"xG={fmean(extra_xg):.2f} | extra-time subs={fmean(substitution_counts):.2f}"
        )
        print(
            f"condition avg 90m={fmean(condition_90):.1f} | "
            f"120m long-runners={fmean(condition_120):.1f}"
        )
    if shootouts:
        print(
            f"shootout conversion={scored_kicks / len(kicks) * 100:.1f}% | "
            f"avg kicks={fmean(len(result.penalty_kicks) for result in shootouts):.2f} | "
            f"sudden death={sudden_shootouts / len(shootouts) * 100:.1f}% | "
            f"home shootout wins={home_shootout_wins / len(shootouts) * 100:.1f}%"
        )
    print(f"throughput={args.matches / elapsed:.1f} knockout pairs/sec")

    strong_home = replace(
        base,
        home_team=_tune_penalties(base.home_team, 95, 90.0),
        away_team=_tune_penalties(base.away_team, 45, 40.0),
    )
    direct = _with_decider(strong_home, MatchDecider.PENALTIES_AFTER_90)
    specialist_shootouts = []
    for offset in range(args.matches * 2):
        seed = args.seed_start + 10_000 + offset
        result = simulator.simulate(_with_seed(direct, seed))
        if result.decision is FastMatchDecision.PENALTIES:
            specialist_shootouts.append(result)
        if len(specialist_shootouts) >= max(100, args.matches // 2):
            break

    print("\nPENALTY SPECIALISTS - SAME TEAM QUALITY")
    print("=" * 88)
    if specialist_shootouts:
        home_wins = sum(
            result.penalties_home > result.penalties_away for result in specialist_shootouts
        )
        print(
            f"shootouts={len(specialist_shootouts)} | HOME pen=95/conf=90 vs AWAY pen=45/conf=40 | "
            f"HOME wins={home_wins / len(specialist_shootouts) * 100:.1f}%"
        )
        print("expected: strong edge, but never deterministic")
    else:
        print("No regulation draws found in specialist sample.")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
