"""Optional, isolated season/rollover/SQLite regression. No Node and no real save edits.

Run at the repository root: python tools/check_ts21_full_season.py
This creates a fresh DEV career; it never opens the user's save database.
"""
from __future__ import annotations

from pathlib import Path
import json
import sys
from tempfile import TemporaryDirectory
from time import perf_counter

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'src'))


def main() -> int:
    from football_manager.dev_ui.session import DevelopmentSession
    from football_manager.persistence import SQLiteSaveRepository, save_manager_career, load_manager_career
    from football_manager.persistence.manager_career import validate_manager_session
    from football_manager.ui_shell.world_squads import world_squads_index

    start = perf_counter()
    session = DevelopmentSession()
    registry = session._world_squads
    original = {p.id: p.attributes for c in registry.clubs.values() for p in c.squad.players}
    if len(registry.clubs) != 92 or len(original) != 2024:
        raise AssertionError('fresh career does not contain 92 x 22 footballers')
    count = session.simulate_remaining_season()
    validate_manager_session(session)
    if set(session._world.results) != set(session._world.fixtures):
        raise AssertionError('unfinished season')
    matches = len(session._world.results)
    appearances = len(registry.usage)
    session.begin_next_season()
    validate_manager_session(session)
    active = world_squads_index(session)
    if active['club_count'] != 92 or active['player_count'] != 2024:
        raise AssertionError('incorrect next-season active pyramid')
    if active['retained_external_clubs'] != 2:
        raise AssertionError('relegated-out clubs were not retained')
    for _ in range(2):
        session.quick_simulate()
        session.continue_to_next_match()
    with TemporaryDirectory(prefix='fm-ts21-check-') as temp:
        repo = SQLiteSaveRepository(Path(temp) / 'synthetic.sqlite3')
        save_manager_career(repo, slot_id='test', display_name='Synthetic TS21 test',
                            expected_revision=0, session=session)
        loaded = load_manager_career(repo, 'test').session
        validate_manager_session(loaded)
        current = {p.id: p.attributes for c in loaded._world_squads.clubs.values() for p in c.squad.players}
        if not original.keys() <= current.keys() or any(current[pid] != attrs for pid, attrs in original.items()):
            raise AssertionError('existing footballers were regenerated or attributes rewritten')
        if loaded._world.football_world is not loaded._world_squads:
            raise AssertionError('lost shared registry identity')
    print(json.dumps({'status': 'PASS', 'completed_fixtures': matches,
                     'managed_matches_first_season': count,
                     'players_with_recorded_appearances': appearances,
                     'next_season': registry.season_label, 'active_clubs': active['club_count'],
                     'active_players': active['player_count'], 'retained_external_clubs': 2,
                     'save_load_after_rollover': 'PASS',
                     'elapsed_seconds': round(perf_counter() - start, 2)}, indent=2))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
