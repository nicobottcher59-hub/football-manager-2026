"""TS-24.9: real economy, youth, transfers and competition transitions with multiple independent world seeds.

Only the *senior match scoring* is replaced by the existing lightweight
background resolver. Therefore 5/10/20-year results CANNOT establish actual
match minutes, player fatigue, injury rates or real-game pace. Use the separate
real-match audit for those checks. No user save is read or overwritten.

Examples:
 python tools/stress_ts249_multiseed.py --seeds 6606,7707,8808 --seasons 5 --output reports/ts249_multi_seed.json
 python tools/stress_ts249_multiseed.py --seeds 6606 --seasons 20 --output reports/ts249_long_horizon.json
"""
from __future__ import annotations

import argparse
from datetime import date
import json
from pathlib import Path
from time import perf_counter
import sys

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'src'))
from football_manager.dev_ui.session import DevelopmentSession
from stress_ts248_long_horizon import background_score_only,snapshot,_save_atomic


def audit(*, seeds: tuple[int,...], seasons: int, output: Path) -> dict:
    if not seeds or len(set(seeds))!=len(seeds) or any(type(s) is not int or s<=0 or s>2_147_483_647 for s in seeds):
        raise ValueError('Provide distinct positive 32-bit seeds')
    if not 1<=seasons<=20:
        raise ValueError('The horizon must be 1..20 seasons')
    started=perf_counter()
    result={'version':'TS-24.9','method':'actual_calendar_economy_transfers_youth_background_scorer',
            'seeds':list(seeds),'seasons_requested':seasons,'status':'running','runs':[],
            'limits':[
                'Each seed creates an independent canonical world roster with different players, attributes and competition results.',
                'Actual monthly finance/renewal decisions, youth, market and promotion/relegation transitions execute.',
                'Only senior match scoring is accelerated; real senior minutes, playing-time-based growth, injuries and fatigue are excluded.',
                'No reading or changing user saved games. Multiple worlds are compared; no universal zero-deficit target is enforced.'
            ]}
    _save_atomic(result,output)
    try:
        for seed in seeds:
            session=DevelopmentSession(world_seed=seed)
            r={'world_seed':seed,'initial':snapshot(session,0),'seasons_completed':0,'annual_snapshots':[],'status':'running'}
            result['runs'].append(r)
            _save_atomic(result,output)
            with background_score_only():
                for year in range(1,seasons+1):
                    label=session._world.season_label
                    deadline=date(int(label[:4])+1,6,30)
                    progress=session._world.advance_until(deadline)
                    if not session.season_finished:
                        raise RuntimeError('Unplayed fixtures past season deadline')
                    session.current_date=deadline
                    session._world.validate_integrity()
                    session._world_squads.validate()
                    item=snapshot(session,year)
                    item['season_fixtures_simulated']=progress.matches_played
                    if item['completed_fixtures'] != item['fixtures']:
                        item['hard_issues'].append('Incomplete competitions')
                    r['annual_snapshots'].append(item)
                    r['seasons_completed']=year
                    r['status']='completed' if year==seasons else 'running'
                    _save_atomic(result,output)
                    print(json.dumps({'seed':seed,'year':year,'backup_gaps':item['uncovered_reserve_slots'],
                          'neg_cash_clubs':item['cash_negative_clubs'],
                          'above_45':item['first_team_players_over_45'],
                          'hard_issues':item['hard_issues'],'seconds':round(perf_counter()-started,1)}),flush=True)
                    if year<seasons:
                        session.begin_next_season()
            del session
        result['status']='completed'
    except Exception as exc:
        result['status']='failed'
        result['error']=f'{type(exc).__name__}: {exc}'
        _save_atomic(result,output)
        raise
    result['elapsed_seconds']=round(perf_counter()-started,2)
    result['hard_issues']=sum(len(i['hard_issues']) for run in result['runs'] for i in run['annual_snapshots'])
    _save_atomic(result,output)
    return result


def main():
    ap=argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--seeds',default='6606,7707,8808')
    ap.add_argument('--seasons',type=int,default=5)
    ap.add_argument('--output',type=Path,default=ROOT/'reports/ts249_multi_seed.json')
    args=ap.parse_args()
    result=audit(seeds=tuple(int(v) for v in args.seeds.split(',')),seasons=args.seasons,output=args.output)
    print(json.dumps({'status':result['status'],'elapsed_seconds':result['elapsed_seconds'],
                      'years':sum(r['seasons_completed'] for r in result['runs']),
                      'hard_issues':result['hard_issues']}),flush=True)

if __name__=='__main__':
    main()
