"""TS-22 operation benchmark on disposable careers (Python standard library).

For comparisons, feed both revisions the same trusted synthetic snapshot.
Each repetition releases its throwaway session and collects old garbage before
measurement; garbage collection stays enabled inside the measured operation.
Reports elapsed time AND process CPU time. Does not access user save slots.
"""
from __future__ import annotations

import argparse
from dataclasses import asdict
from datetime import timedelta
import gc
import gzip
import hashlib
import json
from pathlib import Path
import platform
import statistics
import sys
from time import perf_counter, process_time

ROOT = Path(__file__).resolve().parents[1]


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source-root', type=Path, default=ROOT)
    parser.add_argument('--snapshot', type=Path)
    parser.add_argument('--write-snapshot', type=Path)
    parser.add_argument('--repeats', type=int, default=3)
    parser.add_argument('--days', type=int, default=7)
    parser.add_argument('--matches', type=int, default=48)
    parser.add_argument('--output', type=Path)
    args = parser.parse_args()
    if not 1 <= args.repeats <= 10 or not 1 <= args.days <= 60 or not 1 <= args.matches <= 256:
        parser.error('repeats: 1..10, days: 1..60, matches: 1..256')
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
        del source
    if args.write_snapshot:
        args.write_snapshot.write_bytes(gzip.compress(json.dumps(graph, separators=(',', ':')).encode(), mtime=0))
    session = restore_manager_graph(graph)
    session.quick_simulate()
    postmatch = capture_manager_graph(session)
    del session
    gc.collect()

    def digest(session):
        payload = {'results': [r.to_dict() for _, r in sorted(session._world.results.items())],
                   'players': [(p.id, asdict(p.state), asdict(p.positional_familiarity), asdict(p.tactical_familiarity))
                               for _, c in sorted(session._world_squads.clubs.items()) for p in c.squad.players]}
        return hashlib.sha256(json.dumps(payload, sort_keys=True, default=str).encode()).hexdigest()

    def sample(scenario):
        session = restore_manager_graph(postmatch)
        before = len(session._world.results)
        if scenario == 'fixed_league_batch':
            pending = [f for f in sorted(session._world.fixtures.values(), key=lambda f: (f.kickoff, f.fixture_id))
                       if f.fixture_id not in session._world.results and f.competition_id in session._world.leagues
                       and session.home_club.id not in (f.home_club_id, f.away_club_id)][:args.matches]
            def operation():
                for fixture in pending:
                    session._world.simulate_fixture(fixture.fixture_id)
                return session
        else:
            runtime = UIRuntime(session=session, frontend_root=ROOT/'frontend')
            app = GameApplication(runtime, prematch_builder=prematch_read_model)
            command = {'action': 'advance_day'} if scenario == 'postmatch_continue' else {
                'action': 'simulate_until', 'date': (session.current_date+timedelta(days=args.days)).isoformat()}
            def operation():
                app.command('progression.command', command)
                return runtime.session
        # This collects discarded synthetic inputs, not production match work.
        gc.collect()
        pauses = []
        gc_start = {}
        def on_gc(phase, info):
            generation = info['generation']
            if phase == 'start':
                gc_start[generation] = perf_counter()
            else:
                pauses.append(perf_counter() - gc_start.pop(generation, perf_counter()))
        gc.callbacks.append(on_gc)
        wall, cpu = perf_counter(), process_time()
        try:
            result = operation()
        finally:
            elapsed_cpu = process_time() - cpu
            elapsed_wall = perf_counter() - wall
            gc.callbacks.remove(on_gc)
        return {'seconds': round(elapsed_wall, 6), 'cpu_seconds': round(elapsed_cpu, 6),
                'gc_seconds': round(sum(pauses), 6), 'gc_collections': len(pauses),
                'new_results': len(result._world.results) - before, 'digest': digest(result)}

    rows = []
    for scenario in ('postmatch_continue', 'calendar_days', 'fixed_league_batch'):
        samples = []
        for _ in range(args.repeats):
            gc.collect()
            samples.append(sample(scenario))
            # The sample function has returned; no session survives here.
            gc.collect()
        assert all((s['new_results'], s['digest']) == (samples[0]['new_results'], samples[0]['digest']) for s in samples)
        rows.append({'scenario': scenario, 'median_seconds': round(statistics.median(s['seconds'] for s in samples), 6),
                     'median_cpu_seconds': round(statistics.median(s['cpu_seconds'] for s in samples), 6),
                     'new_results': samples[0]['new_results'], 'digest': samples[0]['digest'], 'samples': samples})
        print(scenario, rows[-1]['median_seconds'], 'seconds', flush=True)
    report = {'python': platform.python_version(), 'platform': platform.system(), 'repeats': args.repeats,
              'days': args.days, 'batch_size': args.matches,
              'method': 'fresh disposable session each repetition; pre-operation garbage collection; GC active during measurement',
              'source': str(args.source_root.resolve()),
              'synthetic_input_sha256': hashlib.sha256(json.dumps(graph, sort_keys=True).encode()).hexdigest(),
              'workloads': rows}
    text = json.dumps(report, indent=2)
    if args.output:
        args.output.write_text(text+'\n', encoding='utf-8')
    print(text)
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
