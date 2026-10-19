"""TS-24.12 detailed-match sample to complement the accelerated long run.

All minutes are read from the real recorded match-usage ledger, not invented.
This sample cannot prove full-season growth, injuries, or game balance.
"""
from __future__ import annotations
import argparse
from pathlib import Path
import json
from audit_ts249_real_match_minutes import audit
from stress_ts248_long_horizon import _save_atomic

ROOT=Path(__file__).resolve().parents[1]

def main():
    ap=argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--matches',type=int,default=18)
    ap.add_argument('--world-seed',type=int,default=6606)
    ap.add_argument('--output',type=Path,default=ROOT/'reports/ts2412_detailed_matches.json')
    a=ap.parse_args()
    result=audit(matches=a.matches,world_seed=a.world_seed,output=a.output)
    result['version']='TS-24.12'
    result['scope']='sample_of_detailed_AI_AI_matches_not_an_entire_season'
    _save_atomic(result,a.output)
    print(json.dumps({'version':result['version'],'matches':result['matches_completed'],
        'u23_minutes':result['total_u23_minutes'],'status':result['status']}),flush=True)

if __name__=='__main__':main()
