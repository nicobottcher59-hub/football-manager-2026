"""Reproducible TS-19 match stress, including planned extra time. No Node needed.

Run from the project root: python tools/validate_ts19_stress.py --matches 1000
This uses disposable snapshots, never reads or changes a user's saved career.
"""
from __future__ import annotations
import argparse
from collections import Counter
from dataclasses import replace
import json
from pathlib import Path
import sys
import time
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'src'))
sys.path.insert(0,str(ROOT))
from football_manager.dev_ui.session import DevelopmentSession
from football_manager.domain import MatchDecider
from football_manager.domain.tactical_studio import PlanRule
from football_manager.fast_simulation import FastMatchSimulator
from football_manager.services.tactical_studio import prepared_match_plans
from football_manager.ui_shell.transactions import apply_squad_command_atomically


def run(matches: int) -> dict:
    session=DevelopmentSession()
    def command(action,**args):
        return apply_squad_command_atomically(session,{'action':action,**args},None)
    command('studio_save',name='Balanced baseline')
    first=session.tactical_studio.active_id
    command('studio_plan',plan='A',entry_id=first)
    command('studio_point',slot_id='lb',phase='in_possession',x=28,y=32)
    command('studio_point',slot_id='rb',phase='in_possession',x=78,y=30)
    command('studio_position',slot_id='lb',position='DM')
    command('studio_save',name='Asymmetric alternative')
    command('studio_plan',plan='B',entry_id=session.tactical_studio.active_id)
    command('studio_load',entry_id=first)
    command('studio_rules',rules=[{'plan':'B','minute':35,'condition':'always'},
                                  {'plan':'A','minute':70,'condition':'trailing'},
                                  {'plan':'B','minute':105,'condition':'always'}])
    plans=prepared_match_plans(session)
    baseline=session._build_snapshot()
    immutable=repr(baseline)
    simulator=FastMatchSimulator()
    counter=Counter()
    started=time.monotonic()
    for index in range(matches):
        competition=replace(baseline.context.competition,match_decider=MatchDecider.EXTRA_TIME_AND_PENALTIES)
        snapshot=replace(baseline,seed=19000+index,context=replace(baseline.context,competition=competition))
        selected=plans if index%2 else ()
        result=simulator.simulate(snapshot,tactical_plans=selected)
        result.__post_init__()
        assert result.home_goals+result.away_goals==len(result.goals)
        counter['planned_matches' if selected else 'ordinary_matches']+=1
        counter['goals']+=len(result.goals)
        counter['substitutions']+=len(result.substitutions)
        counter[result.decision.value]+=1
        for club,stats in ((result.home_club_id,result.statistics_home),(result.away_club_id,result.statistics_away)):
            participants=[p for p in result.player_statistics if p.club_id==club]
            assert len({p.player_id for p in participants})==len(participants)
            for name in ('shots','shots_on_target','passes_attempted','passes_completed','fouls','yellow_cards','red_cards'):
                assert getattr(stats,name)==sum(getattr(p,name) for p in participants),(index,club,name)
            assert all(0<=p.minutes<=120 and 0<=p.condition_after<=100 and 0<=p.fatigue_after<=100 for p in participants)
        for event in result.tactical_events:
            own=sum(g.club_id==event.club_id and g.minute<event.minute for g in result.goals)
            other=sum(g.club_id!=event.club_id and g.minute<event.minute for g in result.goals)
            assert (own,other)==(event.own_goals,event.opponent_goals)
            assert event.applied==PlanRule(event.plan,event.minute,event.condition).matches(own,other)
            counter['applied_plans' if event.applied else 'skipped_plans']+=1
            if event.minute>90:counter['extra_time_plan_checks']+=1
        for card in result.cards:
            if card.card.value!='red':continue
            counter['red_cards']+=1
            assert not any(g.club_id==card.club_id and g.minute>card.minute and card.player_id in (g.scorer_player_id,g.assist_player_id) for g in result.goals)
        if index%50==0:
            assert simulator.simulate(snapshot,tactical_plans=selected)==result
            counter['deterministic_repeats']+=1
        if (index+1)%100==0:print(f'{index+1}/{matches} matches checked',flush=True)
    assert repr(baseline)==immutable
    return {'matches':matches,'failures':0,'elapsed_seconds':round(time.monotonic()-started,3),
            'checks':dict(counter),'input_snapshot_unchanged':True,
            'scope':'Snapshot stress only; not a claim of real-world tactical calibration or long-career aging.'}


def main() -> None:
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--matches',type=int,default=1000)
    parser.add_argument('--output',type=Path,default=Path('reports/ts19/stress.json'))
    args=parser.parse_args()
    if not 2<=args.matches<=20000:parser.error('--matches must be between 2 and 20000')
    result=run(args.matches)
    args.output.parent.mkdir(parents=True,exist_ok=True)
    args.output.write_text(json.dumps(result,indent=2),encoding='utf-8')
    print(json.dumps(result,indent=2))

if __name__=='__main__':main()
