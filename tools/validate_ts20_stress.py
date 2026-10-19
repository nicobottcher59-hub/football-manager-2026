"""TS-20 bounded-history stress, distinct from youth/aging/newgen simulation.

The long run supplies synthetic actual-minute records to the social service;
separately, real DEV seasons run through the FastMatchSimulator and SQLite.
Nothing is written to a user's save database.
"""
from __future__ import annotations
import argparse
from copy import deepcopy
from datetime import timedelta
import json
from pathlib import Path
import sys
from tempfile import TemporaryDirectory
import time

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'src'))
from football_manager.dev_ui import DevelopmentSession
from football_manager.services.dressing_room import record_dressing_room_match, advance_dressing_room
from football_manager.persistence import SQLiteSaveRepository, save_manager_career, load_manager_career
from football_manager.persistence.manager_career import validate_manager_session


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--years',type=int,default=15)
    parser.add_argument('--seasons',type=int,default=2)
    parser.add_argument('--output',type=Path,default=Path('reports/ts20/stress.json'))
    args=parser.parse_args()
    if not 1<=args.years<=30 or not 0<=args.seasons<=5:
        parser.error('years must be 1..30 and real DEV seasons 0..5')
    started=time.monotonic();s=DevelopmentSession()
    people=s.home_club.squad.players
    attributes={p.id:p.attributes for p in people}
    profiles={p.id:p.personality for p in people}
    baseline_states={p.id:(p.state.morale,p.state.confidence,p.state.form,p.state.fitness) for p in people}
    start=s.current_date;count=0
    for elapsed in range(7,365*args.years+1,7):
        s.current_date=start+timedelta(days=elapsed)
        # Rotate selection; the test is NOT claiming these are league results.
        chosen={people[(count+i)%len(people)].id for i in range(11)}
        minutes={p.id:90 if p.id in chosen else 0 for p in people}
        eligible={p.id:True for p in people}
        record_dressing_room_match(s.dressing_room,people,fixture_id=f'social-stress-{count}',
            on_date=s.current_date,minutes=minutes,eligible=eligible,
            intervals={pid:((0,90),) for pid in chosen},outcome=(-1,0,1)[count%3])
        s.dressing_room.validate(set(minutes),s.current_date)
        assert all(-2<=p.state.dressing_room_morale<=2 for p in people)
        count+=1
    assert attributes=={p.id:p.attributes for p in people}
    assert profiles=={p.id:p.personality for p in people}
    assert baseline_states=={p.id:(p.state.morale,p.state.confidence,p.state.form,p.state.fitness) for p in people}
    before=deepcopy(s.dressing_room)
    advance_dressing_room(s.dressing_room,people,s.current_date)
    assert s.dressing_room==before
    social={'years':args.years,'elapsed_days':(s.current_date-start).days,
            'synthetic_participation_records':count,'members':len(s.dressing_room.members),
            'links':len(s.dressing_room.links),'remembered_fixtures':len(s.dressing_room.processed_fixtures),
            'events_retained':len(s.dressing_room.events),'base_attributes_and_states_unchanged':True,
            'morale_offsets_within_bounds':True}
    real=[]
    with TemporaryDirectory() as tmp:
        career=DevelopmentSession();repo=SQLiteSaveRepository(Path(tmp)/'stress.sqlite3')
        for i in range(args.seasons):
            played=career.simulate_remaining_season()
            validate_manager_session(career)
            label=career._world.season_label
            room=deepcopy(career.dressing_room)
            save_manager_career(repo,slot_id='stress',display_name='Stress validation',expected_revision=i,session=career)
            restored=load_manager_career(repo,'stress').session
            assert restored.dressing_room==room and restored._world.to_dict()==career._world.to_dict()
            real.append({'season':label,'real_managed_matches':played,'social_matches_retained':len(room.processed_fixtures),'save_reload_equal':True})
            career=restored
            if i<args.seasons-1:
                career.begin_next_season()
                assert career.dressing_room.last_updated==career.current_date
    result={'scope':'Social history stress plus separate real DEV seasons; no newgens, aging or medical simulation.',
            'social_stress':social,'real_seasons':real,'seconds':round(time.monotonic()-started,2)}
    args.output.parent.mkdir(parents=True,exist_ok=True);args.output.write_text(json.dumps(result,indent=2),encoding='utf-8')
    print(json.dumps(result,indent=2),flush=True)

if __name__=='__main__':
    main()
