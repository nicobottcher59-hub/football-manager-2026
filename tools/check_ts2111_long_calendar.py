"""Optional 15-season scheduling-only stress check (not a player-aging test).

Uses the real cup/league schedulers and the existing aggregate result fallback
on a disposable world with NO football-player registry. Production careers
continue using their full persistent players. Never opens a personal save.
"""
from datetime import date
import json
from pathlib import Path
import sys
from time import perf_counter

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT/'src'))


def main() -> int:
    from football_manager.dev_ui.session import DevelopmentSession
    from football_manager.domain.calendar_planner import calendar_rest_audit
    session = DevelopmentSession()
    career = session._career
    career.current.football_world = None  # Isolate scheduling, ONLY in this diagnostic.
    rows = []
    start = perf_counter()
    for n in range(15):
        if n:
            career.begin_next_season()
        world = career.current
        assert world.football_world is None
        year = int(world.season_label[:4])
        world.advance_until(date(year+1, 6, 30))
        world.validate_integrity()
        if set(world.results) != set(world.fixtures):
            raise AssertionError(f'unfinished season: {world.season_label}')
        audit = calendar_rest_audit(world)
        if audit['hard_violations'] or audit['international_violations']:
            raise AssertionError(f'invalid dates: {world.season_label}')
        rows.append({'season':world.season_label, 'fixtures':len(world.fixtures),
                     'short_rest_pairs':len(audit['short_rest_pairs']),
                     'hard_violations':audit['hard_violations'],
                     'international_violations':len(audit['international_violations'])})
    career.validate_integrity()
    print(json.dumps({'status':'PASS', 'scope':'calendar-only, aggregate result fallback',
                      'seasons':rows, 'elapsed_seconds':round(perf_counter()-start, 2)}, indent=2))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
