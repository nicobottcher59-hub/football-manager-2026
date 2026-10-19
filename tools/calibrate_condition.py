from __future__ import annotations

import argparse
import sys
from dataclasses import replace
from pathlib import Path
from statistics import fmean

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
for path in (str(SRC), str(ROOT)):
    if path not in sys.path:
        sys.path.insert(0, path)

from examples.demo_match_factory import build_demo_snapshot
from football_manager.domain import Position, match_condition_state, recover_condition_state
from football_manager.fast_calibration.scenarios import neutralize_fast_snapshot
from football_manager.fast_simulation import (
    FastMatchSimulator,
    build_fast_team_profile,
    physical_state_after,
)


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Phase 5.11E condition/recovery benchmark.")
    parser.add_argument("--matches", type=int, default=200)
    return parser


def main(argv: list[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    if args.matches <= 0:
        raise SystemExit("--matches must be positive")

    print("\nCONDITION CURVE - NEUTRAL PLAYER (STARTING CONDITION 100)")
    print("=" * 88)
    for stamina in (40, 65, 90, 97):
        ninety = match_condition_state(
            starting_condition=100,
            starting_fatigue=0,
            stamina=stamina,
            minutes=90,
        )
        one_twenty = match_condition_state(
            starting_condition=100,
            starting_fatigue=0,
            stamina=stamina,
            minutes=120,
        )
        print(
            f"stamina={stamina:>2} | condition 100->{ninety.condition:>5.1f} after 90m "
            f"(fatigue={ninety.fatigue:>5.1f}) | 100->{one_twenty.condition:>5.1f} after 120m "
            f"(fatigue={one_twenty.fatigue:>5.1f})"
        )

    normal_90 = match_condition_state(
        starting_condition=100, starting_fatigue=0, stamina=65, minutes=90
    )
    normal_120 = match_condition_state(
        starting_condition=100, starting_fatigue=0, stamina=65, minutes=120
    )

    print("\nRECOVERY - NATURAL FITNESS 65")
    print("=" * 88)
    for days in (1, 3, 4, 7):
        after_90 = recover_condition_state(
            condition=normal_90.condition,
            fatigue=normal_90.fatigue,
            days=days,
            natural_fitness=65,
            stamina=65,
        )
        after_120 = recover_condition_state(
            condition=normal_120.condition,
            fatigue=normal_120.fatigue,
            days=days,
            natural_fitness=65,
            stamina=65,
        )
        print(
            f"days={days} | after 90m: condition={after_90.condition:>5.1f} fatigue={after_90.fatigue:>5.1f} | "
            f"after 120m: condition={after_120.condition:>5.1f} fatigue={after_120.fatigue:>5.1f}"
        )

    print("\nRECOVERY - NATURAL FITNESS DIFFERENCE AFTER 4 DAYS")
    print("=" * 88)
    for natural_fitness in (40, 65, 90):
        recovered = recover_condition_state(
            condition=normal_90.condition,
            fatigue=normal_90.fatigue,
            days=4,
            natural_fitness=natural_fitness,
            stamina=65,
        )
        print(
            f"natural_fitness={natural_fitness:>2} | condition={recovered.condition:>5.1f} | fatigue={recovered.fatigue:>5.1f}"
        )


    print("\nRECOVERY - STAMINA DIFFERENCE AFTER 4 DAYS (SAME STARTING POST-MATCH STATE)")
    print("=" * 88)
    for stamina in (40, 65, 90, 97):
        recovered = recover_condition_state(
            condition=normal_90.condition,
            fatigue=normal_90.fatigue,
            days=4,
            natural_fitness=65,
            stamina=stamina,
        )
        print(
            f"stamina={stamina:>2} | condition={recovered.condition:>5.1f} | fatigue={recovered.fatigue:>5.1f}"
        )

    snapshot = neutralize_fast_snapshot(build_demo_snapshot(seed=511_500), rating=70, seed=511_500)
    team = snapshot.home_team
    profile = build_fast_team_profile(team)
    striker = next(player for player in team.starters if player.assigned_position is Position.ST)
    centre_back = next(player for player in team.starters if player.assigned_position is Position.RCB)

    low_press = replace(profile, pressing=15.0, tempo=45.0)
    high_press = replace(profile, pressing=100.0, tempo=75.0)
    normal_block = replace(profile, defensive_depth=50.0)
    low_block = replace(profile, defensive_depth=10.0)

    print("\nTACTICAL WORKLOAD - SAME PLAYER QUALITY")
    print("=" * 88)
    print(
        f"ST low press condition={physical_state_after(striker, low_press, 90).condition:.1f} | "
        f"high press condition={physical_state_after(striker, high_press, 90).condition:.1f}"
    )
    print(
        f"RCB normal block condition={physical_state_after(centre_back, normal_block, 90).condition:.1f} | "
        f"low block condition={physical_state_after(centre_back, low_block, 90).condition:.1f}"
    )

    simulator = FastMatchSimulator()
    conditions: list[float] = []
    fatigue: list[float] = []
    positions = {
        player.player_id: player.assigned_position
        for side in (snapshot.home_team, snapshot.away_team)
        for player in side.starters
    }
    for offset in range(args.matches):
        seeded = replace(snapshot, seed=511_500 + offset, match_id=f"condition-{offset}")
        result = simulator.simulate(seeded)
        for item in result.player_statistics:
            if positions.get(item.player_id) is Position.GK:
                continue
            conditions.append(item.condition_after)
            fatigue.append(item.fatigue_after)

    print("\nFAST SIMULATOR 90-MINUTE OUTFIELD CHECK")
    print("=" * 88)
    print(
        f"N={args.matches} | avg condition={fmean(conditions):.1f} | avg fatigue={fmean(fatigue):.1f} | "
        f"min/max condition={min(conditions):.1f}/{max(conditions):.1f}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
