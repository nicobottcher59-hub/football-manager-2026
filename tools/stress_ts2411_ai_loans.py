"""TS-24.11: accelerated one-to-twenty-season loan and market audit.

The career calendar, financial reviews, AI transfers, AI loans, youth and
season transitions run normally. Senior matches are scored with the TS-24.8
background stress resolver, so this does NOT certify promised playing time.
For actual senior-match minutes, run tests/test_ts_24_11_ai_loans.py.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path
from stress_ts248_long_horizon import run

ROOT=Path(__file__).resolve().parents[1]


def classify_legacy_audit(report: dict) -> dict:
    """Do not call an imperfect yet playable AI roster a broken world.

    Keep the original TS-24.8 flags for inspection. A shortage of second
    keepers is a sporting warning ONLY if all eleven starting slots remain
    covered; lacking an eligible first goalkeeper remains a hard failure.
    """
    for snap in report['annual_snapshots']:
        previous=list(snap.get('hard_issues',()))
        warnings=[]
        critical=[]
        for issue in previous:
            if ('clubs have fewer than two natural goalkeepers' in issue
                    and snap.get('uncovered_starter_slots',1)==0):
                warnings.append(issue)
            else:
                critical.append(issue)
        snap['legacy_hard_issues']=previous
        snap['sporting_warnings']=warnings
        snap['hard_issues']=critical
    for key,snap in report.get('checkpoints',{}).items():
        matching=next((x for x in report['annual_snapshots']
                       if str(x['season_number'])==key),None)
        if matching is not None:
            snap.update({'hard_issues':matching['hard_issues'],
                         'legacy_hard_issues':matching['legacy_hard_issues'],
                         'sporting_warnings':matching['sporting_warnings']})
    report['has_hard_issues']=any(s['hard_issues'] for s in report['annual_snapshots'])
    report['has_sporting_warnings']=any(s['sporting_warnings'] for s in report['annual_snapshots'])
    return report


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--seasons',type=int,default=5)
    parser.add_argument('--output',type=Path,default=ROOT/'reports/ts2411_ai_loans.json')
    args=parser.parse_args()
    report=classify_legacy_audit(run(args.seasons,output=args.output,
                                   milestones=tuple(v for v in (1,5,10,20) if v<=args.seasons)))
    report['version']='TS-24.11'
    report['method']='accelerated_market_loan_contracts_no_senior_minutes'
    report['notes']=['AI loan registrations/returns and employer ownership are verified by FootballWorld.validate.',
                     'Administrative no-show match behavior and promised-minute consequences require the real-match tests.',
                     'Synthetic scorelines never count as senior participation for breached-loan promises.',
                     'The prior auditor flags fewer than two keepers as hard; TS-24.11 retains the original flag but treats it as a sporting warning when all starting slots are covered.']
    args.output.write_text(json.dumps(report,indent=2,ensure_ascii=False)+'\n',encoding='utf-8')
    last=report['annual_snapshots'][-1]
    print(json.dumps({'version':report['version'],'years_completed':report['years_completed'],
                      'active_loans':last['active_loans'],'active_clubs':last['active_clubs'],
                      'hard_issues':report.get('has_hard_issues'),
                      'sporting_warnings':report.get('has_sporting_warnings')},ensure_ascii=False))


if __name__=='__main__':
    main()
