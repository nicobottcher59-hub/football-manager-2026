"""Reproduce a managed fixture against an AI club without a natural available goalkeeper.

No existing career save is read or written. Uses an isolated generated world.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT/'src'))
from football_manager.dev_ui.session import DevelopmentSession
from football_manager.domain.enums import Position
from football_manager.persistence.manager_career import MANAGER_STATE_VERSION, _REQUIRED_FIELDS


def run_check() -> dict:
    session = DevelopmentSession(world_seed=6606)
    original_id = session._active_match.fixture.fixture_id
    fixture = session._world.fixtures[original_id]
    opponent_id = (fixture.away_club_id if fixture.home_club_id == session.home_club.id
                   else fixture.home_club_id)
    opponent = session._world_squads.clubs[opponent_id]
    original_ids = [p.id for p in opponent.squad.players]
    for player in opponent.squad.players:
        if player.primary_position is Position.GK:
            player.state.suspended_matches = 50
    assert not any(p.primary_position is Position.GK and p.state.is_available for p in opponent.squad.players)
    session._prepare_development_opponent()
    result = session._world.results[original_id]
    session._world.validate_integrity()
    session._world_squads.validate()
    conditions = {
        'administrative_resolver': result.resolver == 'administrative',
        'no_loaned_or_generated_replacement': original_ids == [p.id for p in opponent.squad.players],
        'forfeited_game_not_registered_as_played_minutes': original_id not in session._world_squads.processed_fixtures,
        'next_managed_fixture_prepared': session._active_match is not None and session._active_match.fixture.fixture_id != original_id,
        'sqlite_v16_schema_unchanged': MANAGER_STATE_VERSION == 16 and set(vars(session)) == _REQUIRED_FIELDS,
    }
    assert all(conditions.values()),conditions
    return {
        'version': 'TS-24.12', 'status': 'passed', 'scenario': 'unplayable-ai-opponent-at-managed-match',
        'world_seed': 6606, 'fixture_id': original_id, 'ai_club_id': opponent_id,
        'result_resolver': result.resolver, 'home_goals': result.home_goals,
        'away_goals': result.away_goals, 'next_fixture_id': session._active_match.fixture.fixture_id,
        'checks': conditions,
        'warning': 'This targeted smoke test does not certify the unresolved 20-season audit.'
    }


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--output', type=Path, default=ROOT/'reports/ts2412_forfeit_fix_smoke.json')
    args = ap.parse_args()
    data = run_check()
    args.output.parent.mkdir(parents=True,exist_ok=True)
    args.output.write_text(json.dumps(data,indent=2,ensure_ascii=False)+'\n',encoding='utf-8')
    print(json.dumps(data, ensure_ascii=False))

if __name__ == '__main__':
    main()
