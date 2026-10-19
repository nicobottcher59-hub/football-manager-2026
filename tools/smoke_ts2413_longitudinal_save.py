"""TS-24.13 optional smoke: one real full-world season and SQLite save/load.

Run from the project root: python tools/smoke_ts2413_longitudinal_save.py
This runs a full calendar with test-only senior score resolution. It creates
and deletes a temporary DB; it does not open a user's career save.
"""
from __future__ import annotations

from datetime import date
import json
from pathlib import Path
import sys
from tempfile import TemporaryDirectory

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT / 'src'), str(ROOT / 'tools')]

from football_manager.dev_ui.session import DevelopmentSession
from football_manager.persistence import SQLiteSaveRepository, save_manager_career, load_manager_career
from football_manager.persistence.manager_career import MANAGER_STATE_VERSION
from football_manager.persistence import session_codec
from football_manager.domain.enums import Position
from stress_ts248_long_horizon import background_score_only


def main():
    if MANAGER_STATE_VERSION != 16 or session_codec.GRAPH_VERSION != 16:
        raise AssertionError('Unexpected SQLite save graph version')
    session = DevelopmentSession(world_seed=6606)
    with background_score_only():
        session._world.advance_until(date(2027, 6, 30))
    if not session.season_finished:
        raise AssertionError('Season did not finish')
    session.current_date = date(2027, 6, 30)
    session.begin_next_season()
    cid = session.home_club.id
    original = session._world_squads.youth.academies[cid]
    before = set(original.u15)
    keepers = {pid for pid, preview in original.u15.items() if preview.position is Position.GK}
    assert len(keepers) >= 2, 'Natural goalkeeper replenishment failed'
    with TemporaryDirectory(prefix='ts2413_sqlite_') as tmp:
        repo = SQLiteSaveRepository(Path(tmp) / 'roundtrip.sqlite3')
        save_manager_career(repo, slot_id='test', display_name='TS-24.13',
                            expected_revision=0, session=session)
        restored = load_manager_career(repo, 'test').session
    after = restored._world_squads.youth.academies[cid]
    assert set(after.u15) == before
    assert keepers <= set(after.u15)
    assert restored._world.season_label == session._world.season_label
    restored._world_squads.validate()
    print(json.dumps({'status': 'passed', 'sqlite_version': 16,
                      'season_label': restored._world.season_label,
                      'academy_u15': len(after.u15),
                      'academy_u15_goalkeepers': len(keepers)}, ensure_ascii=False))


if __name__ == '__main__':
    main()
