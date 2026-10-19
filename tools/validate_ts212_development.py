"""Isolated TS-21.2 checks. Standard library only; never opens personal saves.

cohort: 20-year synthetic trajectories, NOT a demographic/full-world balance test.
world: real fixtures, a month boundary, complete SQLite save/load and continuation.
season: a whole actual season + rollover; intentionally slower, optional.
benchmark: isolated development batches at increasing player counts.
"""
from __future__ import annotations

import argparse
from copy import deepcopy
from dataclasses import asdict, fields, replace
from datetime import date
import gc
import json
from pathlib import Path
import statistics
import sys
from tempfile import TemporaryDirectory
from time import perf_counter, process_time

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'src'))


def cohort_player(index):
    from football_manager.domain.player import Player,PlayerIdentity
    from football_manager.domain.attributes import PlayerAttributes,TechnicalAttributes,MentalAttributes,PhysicalAttributes,GoalkeepingAttributes
    from football_manager.domain.enums import Position,Foot
    from football_manager.domain.positional_familiarity import PositionalFamiliarity
    from football_manager.domain.player_development import initialize_development
    pos=(Position.GK,Position.CB,Position.RB,Position.CM,Position.AM,Position.LW,Position.ST)[index%7]
    skill=40+index%36
    def group(typ):return typ(**{f.name:skill for f in fields(typ)})
    p=Player(PlayerIdentity(f'cohort-{index}','Synthetic',str(index),date(2010,1+index%12,1),'Test',Foot.BOTH),
        PlayerAttributes(group(TechnicalAttributes),group(MentalAttributes),group(PhysicalAttributes),group(GoalkeepingAttributes) if pos is Position.GK else None),
        PositionalFamiliarity({pos:100}),pos,pos)
    initialize_development(p,date(2026,8,1),4321)
    return p


def evolve_cohort(players, years, good):
    from football_manager.domain.player_development import DevelopmentEnvironment,review_player,next_month,add_match_exposure,current_ability
    from football_manager.domain.roles import default_role_for_position
    initial=[current_ability(p) for p in players]
    potential=[p.development.potential for p in players]
    yearly=[]
    for month in range(years*12):
        for p in players:
            role=default_role_for_position(p.original_position).role_id
            if good:
                age=p.age_on(p.development.last_review)
                for _ in range(2 if age<18 else 3):
                    p.development=add_match_exposure(p,minutes=80,rating=6.8,role_minutes={role:80})
            p.attributes,p.development=review_player(p,next_month(p.development.last_review),DevelopmentEnvironment(80,80) if good else DevelopmentEnvironment(35,35))
            p.development.validate(p)
        if month%12==11:
            vals=[current_ability(p) for p in players]
            yearly.append({'year':month//12+1,'mean_ca':round(statistics.mean(vals),3),'max_ca':round(max(vals),3)})
    final=[current_ability(p) for p in players]
    return {'yearly':yearly,'mean_gain':round(statistics.mean(b-a for a,b in zip(initial,final)),3),
            'mean_unreached_potential':round(statistics.mean(b-a for a,b in zip(final,potential)),3),
            'pa_preserved':all(p.development.potential==pa for p,pa in zip(players,potential)),
            'within_potential':all(a<=pa+1e-7 for a,pa in zip(final,potential)),
            'bounded_history':all(len(p.development.history)<=12 and len(p.development.annual_history)<=40 for p in players)}


def run_cohort(args):
    a=[cohort_player(i) for i in range(args.players)];b=deepcopy(a)
    start=perf_counter()
    good=evolve_cohort(a,args.years,True)
    print('Supported cohort complete',flush=True)
    poor=evolve_cohort(b,args.years,False)
    assert good['mean_gain']>poor['mean_gain']
    assert all(x['pa_preserved'] and x['within_potential'] and x['bounded_history'] for x in (good,poor))
    return {'mode':'isolated_cohort','players_per_group':args.players,'years':args.years,
            'supported':good,'low_opportunity':poor,'seconds':round(perf_counter()-start,3),
            'limitation':'Tests growth rules/bounds only. No ageing decline, retirements or Newgens; NOT proof of stable population or global ratings.'}


def run_world(args,full=False):
    from football_manager.dev_ui.session import DevelopmentSession
    from football_manager.ui_shell.progression import simulate_until
    from football_manager.persistence import SQLiteSaveRepository,save_manager_career,load_manager_career
    from football_manager.persistence.manager_career import validate_manager_session
    from football_manager.persistence.session_codec import capture_manager_graph
    from football_manager.domain.player_development import current_ability
    start=perf_counter();s=DevelopmentSession()
    identities={p.id:p.identity for c in s._world_squads.clubs.values() for p in c.squad.players}
    initial={p.id:p.attributes for c in s._world_squads.clubs.values() for p in c.squad.players}
    print('Initialized',s.current_date,'with',len(identities),'players',flush=True)
    if full:
        count=s.simulate_remaining_season(on_progress=lambda n: print('Managed matches',n,'world',len(s._world.results),'date',s.current_date,flush=True) if n%10==0 else None)
        assert set(s._world.results)==set(s._world.fixtures)
        matches=len(s._world.results)
        validate_manager_session(s)
        s.begin_next_season()
        print('Rollover',s.current_date,flush=True)
    else:
        count=simulate_until(s,date(2026,9,2),on_day=lambda d,r: print(d,len(s._world.results),flush=True))['managed_matches']
        matches=len(s._world.results)
    validate_manager_session(s)
    with TemporaryDirectory(prefix='fm-ts212-validation-') as tmp:
        repo=SQLiteSaveRepository(Path(tmp)/'synthetic.sqlite3')
        save_manager_career(repo,slot_id='test',display_name='Synthetic development',session=s,expected_revision=0)
        restored=load_manager_career(repo,'test').session
        assert restored._world_squads==s._world_squads
        for a in (s,restored):
            if a.match_played:a.continue_to_next_match()
            if a.can_quick_sim:a.quick_simulate()
        assert restored._world_squads==s._world_squads
        assert restored._world.results==s._world.results
        players={p.id:p for c in restored._world_squads.clubs.values() for p in c.squad.players}
        assert all(pid in players and players[pid].identity==identity for pid,identity in identities.items())
        assert all(players[pid].development.history for pid in identities)
        assert all(current_ability(p)<=p.development.potential+1e-7 for p in players.values())
        nodes=len(capture_manager_graph(restored)['nodes'])
        changed=sum(players[pid].attributes!=attrs for pid,attrs in initial.items())
    return {'mode':'full_season_rollover' if full else 'real_fixture_month_boundary','world_matches':matches,
            'managed_matches':count,'initial_players':len(identities),'retained_players':len(players),
            'players_with_attribute_changes':changed,'identities_and_birthdays_preserved':True,
            'save_load_and_next_match_equal':True,'all_potential_bounds_valid':True,
            'graph_nodes':nodes,'date':s.current_date.isoformat(),'seconds':round(perf_counter()-start,3)}


def run_benchmark(args):
    from football_manager.domain.player_development import DevelopmentEnvironment,review_player,next_month
    rows=[]
    for size in (2024,args.players):
        players=[cohort_player(i) for i in range(size)];gc.collect()
        samples=[]
        for _ in range(3):
            t,c=perf_counter(),process_time()
            for p in players:
                p.attributes,p.development=review_player(p,next_month(p.development.last_review),DevelopmentEnvironment())
            samples.append({'seconds':round(perf_counter()-t,4),'cpu_seconds':round(process_time()-c,4)})
        rows.append({'players':size,'median_seconds':statistics.median(x['seconds'] for x in samples),
                     'median_cpu_seconds':statistics.median(x['cpu_seconds'] for x in samples),'samples':samples})
        print('Batch',rows[-1],flush=True)
        del players;gc.collect()
    return {'mode':'isolated_monthly_batch','results':rows,'note':'CPU-only development loop; does not claim full-game or save-file scaling.'}


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--mode',choices=['cohort','world','season','benchmark'],default='cohort')
    parser.add_argument('--players',type=int,default=120)
    parser.add_argument('--years',type=int,default=20)
    parser.add_argument('--output',type=Path)
    args=parser.parse_args()
    if not 2<=args.players<=50000 or not 1<=args.years<=40:parser.error('players: 2..50000; years: 1..40')
    data=run_cohort(args) if args.mode=='cohort' else run_world(args,args.mode=='season') if args.mode in ('world','season') else run_benchmark(args)
    text=json.dumps({'status':'PASS',**data},indent=2)
    if args.output:args.output.write_text(text+'\n',encoding='utf-8')
    print(text,flush=True)
    return 0


if __name__=='__main__':raise SystemExit(main())
