"""Opt-in TS-05 benchmark: no dependencies beyond the Python standard library.

From repository root:
    python tools/benchmark_world_progression.py --leagues 4 8

Wall time varies by CPU and OS; correctness is asserted, not elapsed time.
"""
from __future__ import annotations

import argparse
from datetime import date
from pathlib import Path
import sys
from time import perf_counter

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT))

from tools.stress_world_calendar import create_world  # noqa: E402


def main() -> None:
    parser = argparse.ArgumentParser(description="Measure world fixture advancement")
    parser.add_argument("--leagues", nargs="+", type=int, default=[4, 8])
    parser.add_argument("--seed", type=int, default=5555)
    options = parser.parse_args()
    for leagues in options.leagues:
        world, _ = create_world(leagues=leagues, seed=options.seed)
        before = len(world.fixtures)
        start = perf_counter()
        progress = world.advance_until(date(2027, 6, 30))
        duration = perf_counter() - start
        if progress.matches_played != len(world.results) or len(world.results) != before:
            raise RuntimeError("incomplete world simulation")
        print(f"{leagues} leagues / {before} matches: {duration:.3f}s | "
              f"played={progress.matches_played}")


if __name__ == "__main__":
    main()
