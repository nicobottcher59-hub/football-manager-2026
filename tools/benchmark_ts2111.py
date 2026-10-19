"""Reproducible TS-21.1.1 benchmark on disposable careers. Python only.

Default: python tools/benchmark_ts2111.py --repeats 3
Never reads/writes user save slots. --snapshot accepts a trusted synthetic
manager graph produced by --write-snapshot, to compare revisions on one input.
"""
from __future__ import annotations

import argparse
from copy import deepcopy
from dataclasses import asdict
from datetime import timedelta
import gzip
import hashlib
import json
from pathlib import Path
import platform
import statistics
import sys
from time import perf_counter

ROOT = Path(__file__).resolve().parents[1]


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source-root', type=Path, default=ROOT)
    parser.add_argument('--snapshot', type=Path)
    parser.add_argument('--write-snapshot', type=Path)
    parser.add_argument('--repeats', type=int, default=3)
    parser.add_argument('--days', type=int, default=28)
    parser.add_argument('--matches', type=int, default=128)
    parser.add_argument('--output', type=Path)
    args = parser.parse_args()
    if not 1 <= args.repeats <= 10 or not 1 <= args.days <= 60 or not 1 <= args.matches <= 256:
        parser.error('repeats: 1..10; days: 1..60; matches: 1..256')
    sys.path.insert(0, str(args.source_root.resolve()/'src'))
    from football_manager.dev_ui.session import DevelopmentSession
    from football_manager.persistence.session_codec import capture_manager_graph, restore_manager_graph
    from football_manager.ui_shell.application import GameApplication
    from football_manager.ui_shell.runtime import UIRuntime
    from football_manager.ui_shell.match import prematch_read_model

    if args.snapshot:
        graph = json.loads(gzip.decompress(args.snapshot.read_bytes()))
    else:
        source = DevelopmentSession()
        graph = capture_manager_graph(source)
    if args.write_snapshot:
        args.write_snapshot.write_bytes(gzip.compress(json.dumps(graph, separators=(',', ':')).encode(), mtime=0))
    session = restore_manager_graph(graph)
    session.quick_simulate()
    postmatch = capture_manager_graph(session)

    def digest(s):
        # Whole result ledger and all registered mutable footballer states.
        payload = {'results': [r.to_dict() for _, r in sorted(s._world.results.items())],
                   'players': [(p.id, asdict(p.state), asdict(p.positional_familiarity),
                                asdict(p.tactical_familiarity))
                               for _, c in sorted(s._world_squads.clubs.items()) for p in c.squad.players]}
        return hashlib.sha256(json.dumps(payload, sort_keys=True, default=str).encode()).hexdigest()

    rows = []
    for scenario in ('postmatch_continue', 'calendar_days', 'fixed_league_batch'):
        samples, outcomes = [], []
        for _ in range(args.repeats):
            s = restore_manager_graph(postmatch)
            before = len(s._world.results)
            if scenario == 'fixed_league_batch':
                pending = [f for f in sorted(s._world.fixtures.values(), key=lambda f:(f.kickoff,f.fixture_id))
                           if f.fixture_id not in s._world.results and f.competition_id in s._world.leagues
                           and s.home_club.id not in (f.home_club_id, f.away_club_id)][:args.matches]
                start = perf_counter()
                for f in pending:
                    s._world.simulate_fixture(f.fixture_id)
                elapsed = perf_counter() - start
            else:
                runtime = UIRuntime(session=s, frontend_root=ROOT/'frontend')
                app = GameApplication(runtime, prematch_builder=prematch_read_model)
                command = {'action':'advance_day'} if scenario == 'postmatch_continue' else {
                    'action':'simulate_until', 'date':(s.current_date+timedelta(days=args.days)).isoformat()}
                start = perf_counter()
                app.command('progression.command', command)
                elapsed = perf_counter()-start
                s = runtime.session
            samples.append(round(elapsed, 6))
            outcomes.append({'new_results':len(s._world.results)-before, 'digest':digest(s)})
        if any(out != outcomes[0] for out in outcomes):
            raise AssertionError(f'non-deterministic repetitions in {scenario}')
        rows.append({'scenario':scenario, 'seconds':samples, 'median_seconds':round(statistics.median(samples),6),
                     **outcomes[0]})
    report = {'python':platform.python_version(), 'platform':platform.system(), 'repeats':args.repeats,
              'days':args.days, 'batch_size':args.matches, 'source':str(args.source_root.resolve()),
              'synthetic_input_sha256':hashlib.sha256(json.dumps(graph,sort_keys=True).encode()).hexdigest(),
              'workloads':rows}
    text = json.dumps(report, indent=2)
    if args.output:
        args.output.write_text(text+'\n',encoding='utf-8')
    print(text)
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
