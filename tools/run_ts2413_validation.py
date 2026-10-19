"""TS-24.13 long-horizon balance stress tests.

Runs real fixture calendars, market, youth progression and finances. Only the
senior match score is replaced by the existing test-only background resolver.
This does NOT replace match-minute or manual Windows UI validation.

    python tools/run_ts2413_validation.py --mode quick
    python tools/run_ts2413_validation.py --mode extended
    python tools/run_ts2413_validation.py --mode single --world-seed 6606 --seasons 5 \
        --output reports/local_ts2413.json
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

from run_ts2412_validation import audit_world
from stress_ts248_long_horizon import _save_atomic

ROOT = Path(__file__).resolve().parents[1]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--mode', choices=('quick', 'extended', 'single'), default='quick')
    parser.add_argument('--world-seed', type=int, default=6606)
    parser.add_argument('--seasons', type=int, default=5)
    parser.add_argument('--output', type=Path)
    args = parser.parse_args()
    if args.mode == 'single':
        jobs = [(args.world_seed, args.seasons,
                 args.output or ROOT / f'reports/local_ts2413_seed{args.world_seed}_{args.seasons}y.json')]
    elif args.mode == 'quick':
        jobs = [(seed, 5, ROOT / f'reports/local_ts2413_seed{seed}_5y.json')
                for seed in (6606, 7707, 8808)]
    else:
        jobs = [(6606, 20, ROOT / 'reports/local_ts2413_seed6606_20y.json'),
                (7707, 5, ROOT / 'reports/local_ts2413_seed7707_5y.json'),
                (8808, 5, ROOT / 'reports/local_ts2413_seed8808_5y.json')]
    outcomes = []
    for seed, years, path in jobs:
        try:
            outcome = audit_world(world_seed=seed, seasons=years, output=path)
        except Exception:
            # The inherited auditor saves a partial JSON even on failure.
            # Preserve that evidence but label it with the actual code version.
            if path.is_file():
                partial = json.loads(path.read_text(encoding='utf-8'))
                partial['version'] = 'TS-24.13'
                partial['code_scope'] = 'natural_academy_goalkeeper_pipeline_and_senior_depth'
                partial['financial_policy'] = 'unchanged_from_TS-24.12'
                _save_atomic(partial, path)
            raise
        outcome['version'] = 'TS-24.13'
        outcome['code_scope'] = 'natural_academy_goalkeeper_pipeline_and_senior_depth'
        outcome['financial_policy'] = 'unchanged_from_TS-24.12'
        _save_atomic(outcome, path)
        outcomes.append({'seed': seed, 'completed': outcome['completed_seasons'],
                         'requested': years, 'status': outcome['status'],
                         'technical_failures': len(outcome['technical_failures'])})
    print(json.dumps({'version': 'TS-24.13', 'audits': outcomes}), flush=True)


if __name__ == '__main__':
    main()
