"""TS-17.4: opt-in long-career SQLite durability/performance diagnostic.

No source saves are touched. This creates a temporary SQLite database,
plays whole DEV seasons, and round-trips at selected checkpoints.

    python tools/profile_long_career.py --seasons 10 --every 5
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys
from tempfile import TemporaryDirectory
from time import perf_counter

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'src'))

from football_manager.dev_ui.session import DevelopmentSession
from football_manager.persistence import (
    SQLiteSaveRepository, load_manager_career, save_manager_career,
)
from football_manager.persistence.session_codec import capture_manager_graph


def profile(*, seasons: int = 10, every: int = 5) -> list[dict]:
    if not 1 <= seasons <= 50 or not 1 <= every <= seasons:
        raise ValueError('seasons must be 1..50 and every must be 1..seasons')
    results: list[dict] = []
    session = DevelopmentSession()
    with TemporaryDirectory(prefix='fm-long-career-') as tmp:
        db_path = Path(tmp) / 'diagnostic.sqlite3'
        repo = SQLiteSaveRepository(db_path)
        revision = 0
        for i in range(1, seasons + 1):
            if i > 1:
                session.begin_next_season()
            start = perf_counter()
            managed_matches = session.simulate_remaining_season()
            session._world.validate_integrity()
            item = {'year': session._world.season_label,
                    'season': i, 'managed_matches': managed_matches,
                    'fixtures': len(session._world.fixtures),
                    'seconds_simulation': round(perf_counter() - start, 3)}
            if i % every == 0 or i == seasons:
                t = perf_counter()
                graph = capture_manager_graph(session)
                item['graph_nodes'] = len(graph['nodes'])
                del graph
                metadata = save_manager_career(
                    repo, slot_id='long-career', display_name='Technical Stress',
                    expected_revision=revision, session=session,
                )
                revision = metadata.revision
                item['seconds_save'] = round(perf_counter() - t, 3)
                item['sqlite_mib'] = round(db_path.stat().st_size / 2**20, 3)
                t = perf_counter()
                recovered = load_manager_career(repo, 'long-career').session
                item['seconds_load'] = round(perf_counter() - t, 3)
                assert recovered._world.to_dict() == session._world.to_dict()
                assert recovered._career.current is recovered._world
                assert recovered._seed == session._seed
                assert recovered.current_date == session.current_date
                session = recovered
            results.append(item)
            print(json.dumps(item, sort_keys=True), flush=True)
    return results


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--seasons', type=int, default=10)
    parser.add_argument('--every', type=int, default=5)
    args = parser.parse_args()
    profile(seasons=args.seasons, every=args.every)


if __name__ == '__main__':
    main()
