"""Optional TS-21.3 synthetic validation. Does not open personal save slots.

Modes: season (real fixtures + rollover + SQLite); cohort (20-year individuals,
not demographic equilibrium); benchmark (isolated monthly batches, not UI time).
Python standard library only.
"""
from __future__ import annotations
import argparse
from copy import deepcopy
from dataclasses import fields, replace
from datetime import date
import gc
import json
from pathlib import Path
from statistics import mean, median
import sys
from tempfile import TemporaryDirectory
from time import perf_counter

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'src'))


def sample(i):
    from football_manager.domain.player import Player,PlayerIdentity
    from football_manager.domain.attributes import PlayerAttributes,TechnicalAttributes,MentalAttributes,PhysicalAttributes,GoalkeepingAttributes
    from football_manager.domain.enums import Position,Foot
    from football_manager.domain.positional_familiarity import PositionalFamiliarity
    from football_manager.domain.player_development import initialize_development
    from football_manager.domain.player_aging import initialize_aging
    pos=(Position.GK,Position.CB,Position.RB,Position.CM,Position.AM,Position.LW,Position.ST)[i%7]
    ability=50+i%34;age=15+i%24
    def group(cls):return cls(**{f.name:ability for f in fields(cls)})
    p=Player(PlayerIdentity(f'ts213-{i}','Synthetic',str(i),date(2026-age,1+i%12,1),'Test',Foot.RIGHT),
        PlayerAttributes(group(TechnicalAttributes),group(MentalAttributes),group(PhysicalAttributes),group(GoalkeepingAttributes) if pos is Position.GK else None),
        PositionalFamiliarity({pos:100}),pos,pos)
    initialize_development(p,date(2026,8,1),5123)
    initialize_aging(p,date(2026,8,1),5123)
    return p


def run_cohort(args):
    from football_manager.domain.player_development import current_ability,reference_overall,next_month,DevelopmentEnvironment,attribute_values,add_match_exposure
    from football_manager.domain.player_aging import review_career
    from football_manager.domain.roles import default_role_for_position
    players=[sample(i) for i in range(args.players)]
    original={p.id:(p.identity,p.development.potential,p.attributes) for p in players}
    rows=[];t=perf_counter()
    for month in range(args.years*12):
        for p in players:
            role=default_role_for_position(p.original_position).role_id
            if month%3!=0:
                for _ in range(2 if p.age_on(p.development.last_review)<18 else 3):
                    p.development=add_match_exposure(p,minutes=80,rating=6.8,role_minutes={role:80})
            p.attributes,p.development,p.aging=review_career(p,next_month(p.development.last_review),DevelopmentEnvironment())
            assert p.development.potential==original[p.id][1]
            assert all(1<=v<=100 for v in attribute_values(p.attributes).values())
        if month%12==11:
            rows.append({'year':month//12+1,'mean_reference_ovr':round(mean(reference_overall(p) for p in players),3),
                         'mean_pace':round(mean(p.attributes.physical.pace for p in players),3),
                         'mean_vision':round(mean(p.attributes.mental.vision for p in players),3),
                         'retirement_requests':sum(p.aging.retirement_requested_on is not None for p in players)})
    assert rows[-1]['mean_pace']<rows[0]['mean_pace']
    assert all(p.identity==original[p.id][0] for p in players)
    return {'mode':'cohort','players':len(players),'years':args.years,'seconds':round(perf_counter()-t,3),'yearly':rows,
            'bounds_and_potential_preserved':True,
            'limitation':'Isolated individuals, kept for observation after a retirement request. No new intake and NOT proof of stable population/ratings.'}


def run_season(args):
    from football_manager.dev_ui.session import DevelopmentSession
    from football_manager.persistence import SQLiteSaveRepository,save_manager_career,load_manager_career
    from football_manager.persistence.manager_career import validate_manager_session
    from football_manager.services.player_aging import repair_managed_unavailable
    from football_manager.domain.player_development import current_ability
    t=perf_counter();s=DevelopmentSession()
    initial={p.id:(p.identity,p.development.potential) for c in s._world_squads.clubs.values() for p in c.squad.players}
    rows=[]
    for season in range(args.seasons):
        label=s._world.season_label
        count=s.simulate_remaining_season(on_progress=lambda n:print(label,'managed',n,'world',len(s._world.results),flush=True) if n%10==0 else None)
        assert set(s._world.results)==set(s._world.fixtures)
        validate_manager_session(s)
        r=s._world_squads
        before_retired=len(r.retired_players)
        row={'season':label,'fixtures':len(s._world.results),'managed_matches':count,
             'completed_medical_episodes':sum(len(p.aging.medical_history) for c in r.clubs.values() for p in c.squad.players),
             'active_medical_episodes':len(r.medical_followups)}
        s.begin_next_season();validate_manager_session(s)
        all_players={p.id:p for c in r.clubs.values() for p in c.squad.players}
        all_players.update({pid:e.player for pid,e in r.retired_players.items()})
        assert all(pid in all_players and all_players[pid].identity==values[0] and all_players[pid].development.potential==values[1] for pid,values in initial.items())
        assert all(current_ability(p)<=p.development.potential+1e-7 for p in all_players.values())
        row.update(retired_this_transition=len(r.retired_players)-before_retired,
                   total_retired=len(r.retired_players),active_players=sum(len(c.squad) for c in r.clubs.values()),
                   registered_clubs=len(r.clubs),smallest_squad=min(len(c.squad) for c in r.clubs.values()),
                   deferred_retirements=sum(p.aging.retirement_status=='deferred' for c in r.clubs.values() for p in c.squad.players))
        rows.append(row);print('Rollover',s.current_date,row,flush=True)
    with TemporaryDirectory(prefix='fm-ts213-') as folder:
        repo=SQLiteSaveRepository(Path(folder)/'validation.sqlite3')
        save_manager_career(repo,slot_id='test',display_name='TS-21.3 synthetic validation',session=s,expected_revision=0)
        loaded=load_manager_career(repo,'test').session
        assert loaded._world_squads==s._world_squads
        for obj in (s,loaded):
            repair_managed_unavailable(obj)
            obj.quick_simulate();obj.continue_to_next_match()
        assert s._world.results==loaded._world.results and s._world_squads==loaded._world_squads
        validate_manager_session(s);validate_manager_session(loaded)
    return {'mode':'season','seasons':rows,'next_date':str(s.current_date),'seconds':round(perf_counter()-t,3),
            'identities_birthdays_potential_preserved':True,'sqlite_load_next_match_identical':True,
            'limitation':'Existing external entrants can add clubs/players at rollover. No Newgens, no constant-population claim.'}


def run_benchmark(args):
    from football_manager.domain.player_development import next_month,DevelopmentEnvironment,review_player
    from football_manager.domain.player_aging import review_career
    rows=[]
    for size in (2024,args.players):
        for mode in ('growth_only','growth_and_aging'):
            samples=[]
            for _ in range(3):
                players=[sample(i) for i in range(size)];gc.collect();t=perf_counter()
                for p in players:
                    if mode=='growth_only':p.attributes,p.development=review_player(p,next_month(p.development.last_review),DevelopmentEnvironment())
                    else:p.attributes,p.development,p.aging=review_career(p,next_month(p.development.last_review),DevelopmentEnvironment())
                samples.append(round(perf_counter()-t,4))
            rows.append({'players':size,'mode':mode,'samples_seconds':samples,'median_seconds':median(samples)})
    return {'mode':'benchmark','rows':rows,'limitation':'Isolated monthly calculation. Not end-to-end Continue/Windows measurements.'}


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('mode',choices=('cohort','season','benchmark'))
    p.add_argument('--players',type=int,default=140)
    p.add_argument('--years',type=int,default=20)
    p.add_argument('--seasons',type=int,default=2)
    p.add_argument('--output',type=Path,required=True)
    args=p.parse_args()
    if not 1<=args.players<=50000 or not 1<=args.years<=40 or not 1<=args.seasons<=20:p.error('invalid test size')
    data={'cohort':run_cohort,'season':run_season,'benchmark':run_benchmark}[args.mode](args)
    args.output.write_text(json.dumps(data,indent=2)+'\n',encoding='utf-8');print(json.dumps(data,indent=2),flush=True)

if __name__=='__main__':main()
