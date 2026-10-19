"""Audit a disposable opening career; no personal saves are opened or edited.

python tools/check_ts2111_calendar.py
"""
from pathlib import Path
import json
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT/'src'))


def main() -> int:
    from football_manager.dev_ui.session import DevelopmentSession
    from football_manager.domain.calendar_planner import calendar_rest_audit, repair_generated_calendar
    session = DevelopmentSession()
    session._world.validate_integrity()
    audit = calendar_rest_audit(session._world, after_date=session.current_date)
    audit['repeat_repair_moves'] = len(repair_generated_calendar(session._world)['moved'])
    audit['managed_november'] = [
        {'competition':f.competition_id, 'kickoff':f.kickoff.isoformat()}
        for f in session._world.calendar.fixtures_for_club(session.home_club.id)
        if f.kickoff.month==11]
    print(json.dumps(audit,indent=2))
    return int(bool(audit['hard_violations'] or audit['international_violations'] or audit['repeat_repair_moves']))


if __name__=='__main__':
    raise SystemExit(main())
