"""TS-24.12 reproducible end-to-end career stress runner.

This runs real career fixtures, scheduling, promotion/relegation, monthly contracts,
AI transfers/loans, academy rollovers, retirement and finance, but replaces ONLY
senior match scoring with the test-only lightweight background resolver.
Consequently long-horizon results DO NOT prove detailed match minutes/injuries.

The disposable human manager's academy promotions are explicit user commands,
not AI control and not automatic replacements injected into normal gameplay.
Run full audit: python tools/run_ts2412_validation.py --mode extended
Run shorter check: python tools/run_ts2412_validation.py --mode quick
"""
from __future__ import annotations

import argparse
from collections import defaultdict
from datetime import date
import json
from pathlib import Path
import sys
from time import perf_counter

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT/'src'))
from football_manager.dev_ui.session import DevelopmentSession
from football_manager.domain.enums import Position
from football_manager.services.ai_squad_planning import squad_plan
from football_manager.services.youth_academy import youth_command
from stress_ts248_long_horizon import background_score_only, snapshot, _save_atomic


def _available_academy_players(session) -> list:
    youth = session._world_squads.youth
    if youth is None or session.home_club.id not in youth.academies:
        return []
    academy = youth.academies[session.home_club.id]
    return [p for p in (*academy.u21.values(), *academy.u17.values())
            if p.age_on(session.current_date) >= 15]


def choose_manager_promotion(session):
    """Select an EXISTING player for an explicitly logged test-manager command."""
    available = _available_academy_players(session)
    if not available:
        return None
    club = session.home_club
    tactic = session.home_tactic
    plan = squad_plan(club, tactic)
    starter_needs = [row['position'] for row in plan['vacancies'] if row['layer'] == 1]
    reserve_needs = [row['position'] for row in plan['vacancies'] if row['layer'] == 2]
    keepers = sum(p.primary_position is Position.GK for p in club.squad.players)

    def priority(player):
        pos = player.primary_position.value
        if pos == 'GK' and keepers < 1:
            positional = 500
        elif pos in starter_needs:
            positional = 300
        elif pos == 'GK' and keepers < 2:
            positional = 250
        elif pos in reserve_needs:
            positional = 160
        else:
            positional = 0
        return (positional + player.overall_rating * 1.5,
                player.age_on(session.current_date), player.id)
    return max(available, key=priority)


def manager_promote_real_academy_players(session, *, target_size: int = 23, max_per_year: int = 6) -> list[dict]:
    """Explicit actions on a throwaway manager; never manufactures players.

    Not used for the 91 AI-managed clubs and never used by normal game play.
    The requested target is NOT enforced on AI teams. Missing academy talent
    remains an observed problem instead of being replaced by fictional extras.
    """
    moves = []
    for _ in range(max_per_year):
        if len(session.home_club.squad) >= target_size:
            break
        player = choose_manager_promotion(session)
        if player is None:
            break
        before = len(session.home_club.squad)
        result = youth_command(session, {'action':'move', 'player_id':player.id, 'target':'first'})
        if not result.get('moved') or len(session.home_club.squad) != before + 1:
            raise AssertionError('Academy promotion must move one existing player')
        moves.append({'club_id':session.home_club.id,'player_id':player.id,
                      'age':player.age_on(session.current_date),
                      'position':player.primary_position.value,
                      'date':session.current_date.isoformat(),
                      'via':'explicit_youth_command'})
    return moves


def classify_checkpoint(item: dict) -> dict:
    """Keep raw inherited diagnostics, split technical failure from sporting risk."""
    structural = []
    sporting = []
    economic = []
    warnings = []
    for finding in item.get('hard_issues', []):
        if 'XI starter positions' in finding or 'fewer than 18 first-team players' in finding:
            sporting.append(finding)
        elif 'fewer than two natural goalkeepers' in finding:
            warnings.append(finding)
        elif 'transfer allocation exceeds available cash' in finding:
            economic.append(finding)
        else:
            structural.append(finding)
    if item['completed_fixtures'] != item['fixtures']:
        structural.append('Not all official fixtures completed')
    if item.get('clubs_below_two_goalkeepers',0)>=10:
        sporting.append('Ten or more professional clubs lack a second natural goalkeeper: widespread depth risk')
    if item['cash_min_gbp'] < -100_000_000:
        economic.append('At least one club cash balance is below GBP -100m: investigate sustained insolvency')
    if item['first_team_players_over_45']:
        warnings.append('Some first-team footballers are older than 45; inspect retirement autonomy')
    return {'structural_failures':structural,'sporting_risks':sporting,
            'financial_risks':economic,'squad_warnings':warnings}


def audit_world(*, world_seed: int, seasons: int, output: Path,
                manager_interventions: bool = True) -> dict:
    if type(world_seed) is not int or not 1 <= world_seed <= 2_147_483_647:
        raise ValueError('world_seed must be a positive 32-bit integer')
    if not 1 <= seasons <= 20:
        raise ValueError('seasons must be between 1 and 20')
    start = perf_counter()
    run = {'version':'TS-24.12', 'seed':world_seed, 'requested_seasons':seasons,
           'status':'running','completed_seasons':0,'manager_interventions':manager_interventions,
           'method':'full_world_calendar_ai_market_loans_youth_finances_background_senior_scores',
           'baseline':{},'annual_snapshots':[], 'manager_academy_promotions':[],
           'technical_failures':[], 'limitations':[
               'Senior matches use lightweight background scores; no detailed match minutes or fatigue are produced.',
               'Only a disposable test manager uses explicit academy promotions; all AI clubs remain autonomous.',
               'Negative cash and imperfect squads are diagnostics, not automatic violations.',
               'This does not play or modify user SQLite files.'
           ]}
    _save_atomic(run,output)
    session = DevelopmentSession(world_seed=world_seed)
    run['baseline']=snapshot(session,0)
    negative_streak=defaultdict(int)
    longest_streak=defaultdict(int)
    min_seen={}
    with background_score_only():
        try:
            for year in range(1,seasons+1):
                label=session._world.season_label
                deadline=date(int(label[:4])+1,6,30)
                progress=session._world.advance_until(deadline)
                if not session.season_finished:
                    raise RuntimeError('Unfinished competitions at season close')
                session.current_date=deadline
                session._world.validate_integrity()
                session._world_squads.validate()
                item=snapshot(session,year)
                item.update(classify_checkpoint(item))
                item['senior_fixtures_advanced']=progress.matches_played
                item['elapsed_seconds']=round(perf_counter()-start,2)
                for club,cash in item['cash_by_club_gbp'].items():
                    negative_streak[club]=negative_streak[club]+1 if cash<0 else 0
                    longest_streak[club]=max(longest_streak[club],negative_streak[club])
                    min_seen[club]=min(min_seen.get(club,cash),cash)
                item['longest_observed_negative_cash_streak']=max(longest_streak.values(),default=0)
                item['deepest_observed_negative_cash_gbp']=min(min_seen.values(),default=0)
                item['checkpoint_warnings_total']=(len(item['sporting_risks'])+
                                                   len(item['financial_risks'])+len(item['squad_warnings']))
                run['annual_snapshots'].append(item)
                run['completed_seasons']=year
                _save_atomic(run,output)
                print(json.dumps({'seed':world_seed,'season':year,'clubs':item['active_clubs'],
                      'starter_gaps':item['uncovered_starter_slots'],
                      'clubs_under_two_GK':item['clubs_below_two_goalkeepers'],
                      'cash_negative':item['cash_negative_clubs'],
                      'min_cash_gbp':item['cash_min_gbp'],
                      'older_than_45':item['first_team_players_over_45'],
                      'technical_failures':item['structural_failures'],
                      'elapsed_seconds':item['elapsed_seconds']}),flush=True)
                if year<seasons:
                    if manager_interventions:
                        moves=manager_promote_real_academy_players(session)
                        run['manager_academy_promotions'].extend(moves)
                    session.begin_next_season()
                    _save_atomic(run,output)
            run['status']='completed'
        except Exception as e:
            run['status']='failed'
            run['error']={'exception':type(e).__name__, 'detail':str(e),
                          'season_attempted':run['completed_seasons']+1}
            run['technical_failures'].append(dict(run['error']))
            run['elapsed_seconds']=round(perf_counter()-start,2)
            run['negative_cash_streaks']={k:v for k,v in longest_streak.items() if v}
            run['min_cash_by_club_gbp']=min_seen
            _save_atomic(run,output)
            raise
    run['technical_failures']=[{'season':s['season_number'],'finding':finding}
        for s in run['annual_snapshots'] for finding in s['structural_failures']]
    run['elapsed_seconds']=round(perf_counter()-start,2)
    run['negative_cash_streaks']={k:v for k,v in longest_streak.items() if v}
    run['min_cash_by_club_gbp']=min_seen
    _save_atomic(run,output)
    return run


def main():
    ap=argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--mode',choices=('quick','extended','single'),default='quick')
    ap.add_argument('--world-seed',type=int,default=6606)
    ap.add_argument('--seasons',type=int,default=5,help='For --mode single')
    ap.add_argument('--output',type=Path,help='Only for --mode single')
    ap.add_argument('--without-test-manager',action='store_true',help='Probe unmanaged human club; may stop at a valid user intervention point')
    args=ap.parse_args()
    if args.mode=='single':
        requests=[(args.world_seed,args.seasons,args.output or ROOT/f'reports/ts2412_seed{args.world_seed}_{args.seasons}y.json')]
    elif args.mode=='quick':
        requests=[(6606,5,ROOT/'reports/ts2412_seed6606_5y.json'),
                  (7707,5,ROOT/'reports/ts2412_seed7707_5y.json'),
                  (8808,5,ROOT/'reports/ts2412_seed8808_5y.json')]
    else:
        requests=[(6606,20,ROOT/'reports/ts2412_seed6606_20y.json'),
                  (7707,5,ROOT/'reports/ts2412_seed7707_5y.json'),
                  (8808,5,ROOT/'reports/ts2412_seed8808_5y.json')]
    summaries=[]
    for seed,years,path in requests:
        result=audit_world(world_seed=seed,seasons=years,output=path,
                           manager_interventions=not args.without_test_manager)
        summaries.append({'seed':seed,'requested':years,'completed':result['completed_seasons'],
                          'technical_failures':len(result['technical_failures']),
                          'promotions':len(result['manager_academy_promotions'])})
    print(json.dumps({'version':'TS-24.12','audits':summaries},ensure_ascii=False),flush=True)

if __name__=='__main__':main()
