"""TS-24.9: execute actual detailed senior matches, not accelerated background scores.

This intentionally audits a bounded cross-section, NOT entire seasons.
Each recorded minute must come from the regular match-result pipeline.
Example: python tools/audit_ts249_real_match_minutes.py --matches 18 --output reports/ts249_real_minutes.json
"""
from __future__ import annotations
import argparse
from collections import defaultdict
import json
from pathlib import Path
import sys
from time import perf_counter
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'src'))
from football_manager.dev_ui.session import DevelopmentSession
from football_manager.services.world_matches import opponent_side
from stress_ts248_long_horizon import _save_atomic


def audit(*,matches:int,world_seed:int,output:Path)->dict:
    if not 1<=matches<=100:
        raise ValueError('Sample must include 1..100 real matches')
    session=DevelopmentSession(world_seed=world_seed)
    registry=session._world_squads
    fixtures=sorted((v for v in session._world.fixtures.values()
                     if v.home_club_id in registry.clubs and v.away_club_id in registry.clubs
                     and session.home_club.id not in (v.home_club_id,v.away_club_id)
                     and v.match_date is not None and v.fixture_id not in session._world.results),
                    key=lambda fixture:(fixture.match_date,fixture.fixture_id))
    # Sample distributed through the fixture calendar. No invented youth minutes
    # and no changes to the manager's lineup or sporting choices.
    if len(fixtures)<matches:
        raise ValueError('not enough scheduled AI-versus-AI senior matches')
    stride=max(1,len(fixtures)//matches)
    selected=fixtures[::stride][:matches]
    started=perf_counter()
    rows=[]
    for fixture in selected:
        usage_before={pid:u.minutes for pid,u in registry.usage.items()}
        actual_rotated=[]
        for cid in (fixture.home_club_id,fixture.away_club_id):
            _,lineup,_=opponent_side(session._world,cid,fixture_id=fixture.fixture_id)
            _,regular,_=opponent_side(session._world,cid)
            baseline={e.player.id for e in regular.starters}
            for row in lineup.starters:
                player=row.player
                if player.id not in baseline and player.age_on(fixture.match_date)<23:
                    actual_rotated.append(player.id)
        result=session._world.simulate_fixture(fixture.fixture_id)
        assert fixture.fixture_id in session._world.results
        assert registry.processed_fixtures.get(fixture.fixture_id) is True  # detailed engine usage ledger
        # Usage minutes are stored ONLY by the real simulation result handler.
        youth_minutes=0
        used=0
        rostered=0
        for cid in (fixture.home_club_id,fixture.away_club_id):
            for player in registry.clubs[cid].squad.players:
                gained=registry.usage.get(player.id)
                delta=gained.minutes-usage_before.get(player.id,0) if gained else 0
                if delta<0:
                    raise AssertionError('minutes decreased during a match')
                if delta:
                    used+=1
                    if player.age_on(fixture.match_date)<23:
                        youth_minutes+=delta
                        rostered+=1
        # Pre-match projections can change after the player's dated
        # development review; judge recorded minutes, not predictions.
        verified_rotated=sum(registry.usage.get(pid) is not None and
                             registry.usage[pid].minutes>usage_before.get(pid,0)
                             for pid in actual_rotated)
        rows.append({'fixture_id':fixture.fixture_id,'date':fixture.match_date.isoformat(),
                     'home':fixture.home_club_id,'away':fixture.away_club_id,
                     'real_match_result_resolver':session._world.results[fixture.fixture_id].resolver,
                     'detailed_usage_recorded': registry.processed_fixtures.get(fixture.fixture_id) is True,
                     'players_with_logged_minutes':used,'u23_total_minutes':youth_minutes,
                     'u23_players_with_minutes':rostered,'projected_rotated_u23_starters':len(actual_rotated),
                     'projected_rotated_u23_with_actual_minutes':verified_rotated})
        print(json.dumps({'real_match':len(rows),'u23_minutes':youth_minutes,
                          'projected_rotated_u23':len(actual_rotated),'verified_rotated':verified_rotated}),flush=True)
    registry.validate()
    report={'version':'TS-24.9','world_seed':world_seed,'method':'real_FastMatchSimulator_AI_vs_AI_fixture_sample',
            'matches_requested':matches,'matches_completed':len(rows),'status':'completed',
            'total_u23_minutes':sum(i['u23_total_minutes'] for i in rows),
            'projected_rotated_u23_starts':sum(i['projected_rotated_u23_starters'] for i in rows),
            'projected_rotated_u23_with_actual_minutes':sum(i['projected_rotated_u23_with_actual_minutes'] for i in rows),
            'games_with_u23_minutes':sum(i['u23_total_minutes']>0 for i in rows),
            'minutes_are_from_real_matches':True,
            'limitations':'Selected fixture sample only; not a whole-season career, injury/season growth or 20-year development guarantee.',
            'elapsed_seconds':round(perf_counter()-started,2),'fixtures':rows}
    _save_atomic(report,output)
    return report


def main():
    ap=argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--matches',type=int,default=18)
    ap.add_argument('--world-seed',type=int,default=6606)
    ap.add_argument('--output',type=Path,default=ROOT/'reports/ts249_real_minutes.json')
    a=ap.parse_args()
    x=audit(matches=a.matches,world_seed=a.world_seed,output=a.output)
    print(json.dumps({'status':x['status'],'matches':x['matches_completed'],
                      'u23_minutes':x['total_u23_minutes'],'seconds':x['elapsed_seconds']}),flush=True)
if __name__=='__main__':main()
