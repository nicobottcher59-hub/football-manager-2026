"""TS-21.4/21.5 world diagnostics. No changes to players, saves or matches.

Modes: opening is an actual 92-club read-only snapshot; cohort is a *sampled
hypothetical* 15-20-year development/retirement sensitivity test, NOT 20
seasons of competitive football. No Newgens are generated in either mode.
"""
from __future__ import annotations

import argparse
from copy import deepcopy
from datetime import date
import json
from pathlib import Path
import sys
from time import perf_counter

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT/'src'))


def run(mode: str, years: int, count: int) -> dict:
    from football_manager.dev_ui.session import DevelopmentSession
    from football_manager.calibration.world_balance import world_balance_snapshot, population_metrics
    from football_manager.domain.player_development import add_match_exposure, next_month
    from football_manager.domain.player_aging import review_career
    from football_manager.domain.roles import default_role_for_position
    from football_manager.services.world_training import estimated_training_environment
    from football_manager.domain.player_development import stable_random

    clock = perf_counter()
    session = DevelopmentSession()
    registry = session._world_squads
    opening = world_balance_snapshot(registry, session.current_date)
    if mode == 'opening':
        return {'mode': mode, 'opening': opening, 'seconds': round(perf_counter()-clock, 3),
                'limitations': 'Only the existing four English divisions are persistent.'}
    all_players = [(club_id, player) for club_id, club in sorted(registry.clubs.items())
                   for player in sorted(club.squad.players, key=lambda p:p.id)]
    # Uniform spacing across teams/positions, not a cherry-picked star cohort.
    index = sorted(set(min(len(all_players)-1, int((i+.5)*len(all_players)/count)) for i in range(count)))
    selected = [(cid, deepcopy(p)) for j in index for cid, p in (all_players[j],)]
    first_date = selected[0][1].development.last_review
    # Simulate each individual's monthly core using assumed 0-4 appearances.
    # We do NOT claim to simulate AI fixture tactics or match results here.
    timeline = []
    retired_count = 0
    for year in range(years):
        for month in range(12):
            for club_id, player in selected:
                # A deterministic scenario; never write match results or club records.
                visits = 2 + stable_random(player.id, year, month, 'hypothetical').randrange(3)
                if player.age_on(player.development.last_review) >= 36:
                    visits = max(0, visits-2)
                role_id = default_role_for_position(player.development.reference_position).role_id
                for _ in range(visits):
                    player.development = add_match_exposure(player, minutes=75,
                        rating=6.6, role_minutes={role_id:75})
                env = registry.development_environments[club_id]
                new_date = next_month(player.development.last_review)
                player.attributes, player.development, player.aging = review_career(player, new_date, env)
        last_date = selected[0][1].development.last_review if selected else date(first_date.year+year+1, first_date.month, 1)
        remaining = [(cid, p) for cid, p in selected if p.aging.retirement_requested_on is None]
        newly_retired = len(selected)-len(remaining)
        retired_count += newly_retired
        selected = remaining
        metrics = population_metrics((p for _,p in selected), last_date)
        timeline.append({'year': year+1, 'date': last_date.isoformat(),
                         'retirement_requests_removed_this_year': newly_retired,
                         'retirement_requests_total': retired_count, **metrics})
        if not selected:
            break
    return {
        'mode': mode, 'years_requested': years, 'opening_world': opening,
        'sample_initial_players': len(index), 'scenario': 'deterministic 2-4 appearances/month for active sample members; no transfer, no fixtures, no new players',
        'annual_projection': timeline, 'seconds': round(perf_counter()-clock,3),
        'limitations': [
            'This is a hypothetical player-cohort projection, not a full 20-season career simulation.',
            'Retirement requests are treated as departures here; real squads defer some departures until they can field a team.',
            'No Newgens means the population declines; stability cannot be established yet.',
            'Actual clubs, fixtures, results, and careers remain untouched.',
        ],
    }


def main() -> None:
    cli=argparse.ArgumentParser(description=__doc__)
    cli.add_argument('--mode', choices=('opening','cohort'), default='cohort')
    cli.add_argument('--years', type=int, default=20)
    cli.add_argument('--players', type=int, default=192)
    cli.add_argument('--output', type=Path, required=True)
    args=cli.parse_args()
    if not 15<=args.years<=30 or not 10<=args.players<=2024:
        cli.error('years must be 15-30 and players 10-2024')
    data=run(args.mode,args.years,args.players)
    args.output.parent.mkdir(parents=True,exist_ok=True)
    args.output.write_text(json.dumps(data,indent=2,ensure_ascii=False)+'\n',encoding='utf-8')
    print(json.dumps({'mode':data['mode'],'seconds':data['seconds'],
        'initial_population':data['sample_initial_players'] if 'sample_initial_players' in data else data['opening']['active']['players'],
        'remaining':data['annual_projection'][-1]['players'] if 'annual_projection' in data else data['opening']['active']['players']}, ensure_ascii=False))

if __name__ == '__main__':
    main()
