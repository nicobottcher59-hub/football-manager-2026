from __future__ import annotations

from dataclasses import replace
from statistics import fmean
from time import perf_counter

from demo_match_factory import build_demo_snapshot
from football_manager.fast_simulation import FastMatchSimulator


def main() -> None:
    simulator = FastMatchSimulator()
    snapshot = build_demo_snapshot(seed=51110)
    result = simulator.simulate(snapshot)

    print("FAST MATCH SIMULATOR — SINGLE MATCH")
    print(f"{snapshot.home_team.club_short_name} {result.home_goals}-{result.away_goals} {snapshot.away_team.club_short_name}")
    print(
        f"xG {result.statistics_home.xg:.2f}-{result.statistics_away.xg:.2f} | "
        f"shots {result.statistics_home.shots}-{result.statistics_away.shots} | "
        f"SOT {result.statistics_home.shots_on_target}-{result.statistics_away.shots_on_target}"
    )
    print(
        f"possession {result.statistics_home.possession_pct:.1f}-{result.statistics_away.possession_pct:.1f} | "
        f"passes {result.statistics_home.passes_completed}/{result.statistics_home.passes_attempted} - "
        f"{result.statistics_away.passes_completed}/{result.statistics_away.passes_attempted}"
    )
    print(
        f"fouls {result.statistics_home.fouls}-{result.statistics_away.fouls} | "
        f"YC {result.statistics_home.yellow_cards}-{result.statistics_away.yellow_cards} | "
        f"corners {result.statistics_home.corners}-{result.statistics_away.corners}"
    )
    if result.goals:
        print("goals:")
        for goal in result.goals:
            assist = f" assist={goal.assist_player_id}" if goal.assist_player_id else ""
            print(f"  {goal.minute}' {goal.club_id} {goal.scorer_player_id}{assist} xG={goal.xg:.3f}")
    else:
        print("goals: none")

    repeated = simulator.simulate(snapshot)
    print(f"same seed reproducible: {repeated == result}")

    samples = 1000
    started = perf_counter()
    batch = [
        simulator.simulate(replace(snapshot, seed=seed, match_id=f"fast-demo-{seed}"))
        for seed in range(1, samples + 1)
    ]
    elapsed = perf_counter() - started
    home_wins = sum(item.home_goals > item.away_goals for item in batch)
    draws = sum(item.home_goals == item.away_goals for item in batch)
    away_wins = samples - home_wins - draws
    print("\n1000-MATCH EQUAL-TEAM BASELINE")
    print(
        f"goals={fmean(item.total_goals for item in batch):.2f} | "
        f"shots={fmean(item.statistics_home.shots + item.statistics_away.shots for item in batch):.2f} | "
        f"SOT={fmean(item.statistics_home.shots_on_target + item.statistics_away.shots_on_target for item in batch):.2f}"
    )
    print(
        f"xG={fmean(item.statistics_home.xg + item.statistics_away.xg for item in batch):.2f} | "
        f"fouls={fmean(item.statistics_home.fouls + item.statistics_away.fouls for item in batch):.2f} | "
        f"YC={fmean(item.statistics_home.yellow_cards + item.statistics_away.yellow_cards for item in batch):.2f} | "
        f"corners={fmean(item.statistics_home.corners + item.statistics_away.corners for item in batch):.2f}"
    )
    print(f"H/D/A={home_wins / samples * 100:.1f}/{draws / samples * 100:.1f}/{away_wins / samples * 100:.1f}")
    print(f"time={elapsed:.3f}s | {samples / elapsed:.1f} matches/sec")


if __name__ == "__main__":
    main()
