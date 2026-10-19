"""TS-24.7: reproducible 5/10/20-year market, finance and squad stress audit.

By default, all real generated competition fixtures, monthly reviews,
promotion/relegation, contract renewals, transfer windows and academy annual
rollovers are processed. For runtime reasons ONLY in this diagnostics process,
English senior games use the existing strength-sensitive background scorer
instead of FastMatchSimulator. Thus senior match minutes, tactical selection,
player form, injuries and match-driven development are NOT simulated. This is
NOT proof that 20 seasons of normal interactive gameplay work.

Run from any cwd:
    python tools/stress_ts247_long_horizon.py --seasons 20 --output reports/ts247_long_horizon.json

The output JSON is written atomically after every completed season so a
failure does not destroy diagnostic evidence. Input saved games are NEVER read.
"""
from __future__ import annotations

import argparse
from contextlib import contextmanager
from collections import Counter
from datetime import date
import json
from pathlib import Path
import statistics
import sys
from time import perf_counter

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'src'))

from football_manager.dev_ui.session import DevelopmentSession
from football_manager.domain.world_runner import WorldSeasonRunner
from football_manager.services.ai_squad_planning import squad_plan
from football_manager.services.club_economy import weekly_payroll


def _median(nums: list[int | float]) -> float:
    return round(statistics.median(nums), 2) if nums else 0.0


def _pct(nums: list[int | float], pct: int) -> float:
    if not nums:
        return 0.0
    ordered = sorted(nums)
    index = (len(ordered) - 1) * pct / 100
    lo = int(index)
    hi = min(lo + 1, len(ordered) - 1)
    return round(ordered[lo] + (ordered[hi] - ordered[lo]) * (index - lo), 2)


@contextmanager
def background_score_only():
    """Replace senior match result solver for this test, restore even on error.

    Calendar and market review functions still see the live registry. A patch
    that set football_world=None throughout advance_until would accidentally
    skip monthly reviews; only the scoring call is switched here.
    """
    original = WorldSeasonRunner.simulate_fixture

    def light(self, fixture_id):
        registry = self.football_world
        self.football_world = None
        try:
            return original(self, fixture_id)
        finally:
            self.football_world = registry

    WorldSeasonRunner.simulate_fixture = light
    try:
        yield
    finally:
        WorldSeasonRunner.simulate_fixture = original


def snapshot(session, year: int) -> dict:
    registry = session._world_squads
    active_ids = sorted(cid for cid, ident in registry.identities.items() if ident.tier > 0)
    active = [registry.clubs[cid] for cid in active_ids]
    roster_ids = [p.id for club in registry.clubs.values() for p in club.squad.players]
    squad_sizes = [len(club.squad) for club in active]
    keeper_counts = [sum(p.primary_position.value == 'GK' for p in club.squad.players) for club in active]
    plan_violations = []
    uncovered_starters = uncovered_backups = 0
    for cid in active_ids:
        club = registry.clubs[cid]
        plan = squad_plan(club, registry.identities[cid].primary)
        uncovered_starters += 11 - plan['starters_covered']
        uncovered_backups += 11 - plan['backups_covered']
        if plan['starters_covered'] < 11:
            plan_violations.append({'club_id': cid, 'starters': plan['starters_covered'],
                                    'backups': plan['backups_covered'], 'squad': len(club.squad)})
    active_players = [p for club in active for p in club.squad.players]
    gks = [c for c, n in zip(active_ids, keeper_counts) if n < 2]
    finances = [registry.club_finances[c] for c in active_ids if c in registry.club_finances]
    full_cash = [a.cash_gbp for a in finances]
    cash_by_club = {cid: registry.club_finances[cid].cash_gbp for cid in active_ids}
    operating_surpluses = [a.season_income_gbp - a.season_wages_gbp - a.season_operations_gbp for a in finances]
    wages = [weekly_payroll(registry, cid) for cid in active_ids if cid in registry.club_finances]
    age = [p.age_on(session.current_date) for p in active_players]
    prices = [q.value_gbp for p in active_players if (q := registry.market_values.get(p.id))]
    youth = registry.youth
    academy_counts = {
        'u15': sum(len(a.u15) for a in youth.academies.values()) if youth else 0,
        'u17': sum(len(a.u17) for a in youth.academies.values()) if youth else 0,
        'u21': sum(len(a.u21) for a in youth.academies.values()) if youth else 0,
        'promoted_cumulative': sum(len(a.graduates) for a in youth.academies.values()) if youth else 0,
    }
    # The 'new entrant' label is a world count, not a player clone count.
    issues = []
    if len(active_ids) != 92:
        issues.append(f'expected 92 active professional clubs, found {len(active_ids)}')
    if set(registry.club_finances) != set(registry.clubs):
        issues.append('club financial accounts do not match registered clubs')
    if len(roster_ids) != len(set(roster_ids)):
        issues.append('a player is registered by more than one first team')
    if plan_violations:
        issues.append(f'{len(plan_violations)} active clubs cannot cover all XI starter positions')
    if gks:
        issues.append(f'{len(gks)} clubs have fewer than two natural goalkeepers')
    if squad_sizes and min(squad_sizes) < 18:
        issues.append('at least one club has fewer than 18 first-team players')
    if age and max(age) >= 50:
        issues.append('an active first-team footballer is at least 50 years old')
    if any(a.transfer_budget_gbp > max(0, a.cash_gbp) for a in finances):
        issues.append('club transfer allocation exceeds available cash')
    # Out-of-budget payroll can arise organically after renewals, including
    # promoted teams whose revenue drops; report rather than silently repairing.
    payroll_over = [cid for cid in active_ids if cid in registry.club_finances and
                    weekly_payroll(registry, cid) > registry.club_finances[cid].wage_budget_weekly_gbp]
    deals = [x for x in registry.transfer_offers.values() if x.status == 'completed']
    return {
        'season_number': year, 'label': session._world.season_label,
        'date': session.current_date.isoformat(),
        'active_clubs': len(active_ids), 'registered_clubs_total': len(registry.clubs),
        'fixtures': len(session._world.fixtures), 'completed_fixtures': len(session._world.results),
        'first_team_players': len(active_players), 'registered_roster_ids_total': len(roster_ids),
        'duplicate_first_team_ids': len(roster_ids) - len(set(roster_ids)),
        'squad_min': min(squad_sizes), 'squad_median': _median(squad_sizes),
        'squad_max': max(squad_sizes), 'clubs_below_18': sum(n < 18 for n in squad_sizes),
        'clubs_below_two_goalkeepers': len(gks),
        'uncovered_starter_slots': uncovered_starters,
        'uncovered_reserve_slots': uncovered_backups,
        'clubs_with_uncovered_starters': plan_violations[:20],
        'young_first_team_players_u23': sum(n <= 22 for n in age),
        'first_team_age_median': _median(age),
        'first_team_age_max': max(age),
        'first_team_players_over_40': sum(n > 40 for n in age),
        'first_team_players_over_45': sum(n > 45 for n in age),
        'salary_weekly_median_gbp': _median(wages),
        'salary_weekly_p95_gbp': _pct(wages, 95),
        'clubs_payroll_over_wage_budget': len(payroll_over),
        'cash_median_gbp': _median(full_cash),
        'cash_min_gbp': min(full_cash), 'cash_max_gbp': max(full_cash),
        'cash_negative_clubs': sum(a.cash_gbp < 0 for a in finances),
        'cash_total_gbp': sum(full_cash),
        'cash_by_club_gbp': cash_by_club,
        'clubs_operating_loss_this_season': sum(value < 0 for value in operating_surpluses),
        'clubs_operating_profit_this_season': sum(value > 0 for value in operating_surpluses),
        'market_value_median_gbp': _median(prices),
        'market_value_p95_gbp': _pct(prices, 95),
        'retirements_cumulative': len(registry.retired_players),
        'completed_transfers_cumulative': len(deals),
        'active_loans': sum(x.status == 'active' for x in registry.loans.values()),
        'free_agents': len(registry.free_agents),
        'youth': academy_counts,
        'senior_usage_minutes': sum(u.minutes for u in registry.usage.values()),
        'hard_issues': issues,
    }


def _save_atomic(data: dict, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    candidate = path.with_name(path.name + '.partial')
    candidate.write_text(json.dumps(data, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    candidate.replace(path)


def run(seasons: int, *, output: Path, milestones: tuple[int, ...] = (5, 10, 20)) -> dict:
    if not 1 <= seasons <= 20:
        raise ValueError('season count must be 1..20')
    if not milestones or any(m < 1 or m > 20 for m in milestones):
        raise ValueError('checkpoints must be between 1 and 20')
    started = perf_counter()
    data = {
        'version': 'TS-24.7', 'method': 'accelerated_competitions_market_youth',
        'years_requested': seasons, 'years_completed': 0,
        'checkpoints_requested': list(milestones),
        'disclaimer': [
            'Actual fixture schedules, tournament rounds, promotions, annual youth rollover, month-end finances, contract renewals and AI markets are executed.',
            'The senior games use the existing background score resolver rather than FastMatchSimulator, solely inside this disposable test run.',
            'Senior player appearances, minutes, injuries, fatigue, tactics and match-based development are NOT exercised; minutes opportunities cannot be established from these results.',
            'One default fictional-world seed. This is not a statistical multiple-seed calibration or proof of fully interactive 20-year play.',
            'No player save or user database is loaded or changed.',
        ],
        'annual_snapshots': [], 'checkpoints': {}, 'status': 'running',
    }
    session = DevelopmentSession()
    data['baseline'] = snapshot(session, 0)
    _save_atomic(data, output)
    with background_score_only():
        for season in range(1, seasons + 1):
            label = session._world.season_label
            try:
                deadline = date(int(label[:4]) + 1, 6, 30)
                progress = session._world.advance_until(deadline)
                if not session.season_finished:
                    raise RuntimeError('unplayed fixtures past the season deadline')
                session.current_date = deadline
                session._world.validate_integrity()
                registry = session._world_squads
                registry.validate()
                item = snapshot(session, season)
                previous = data['annual_snapshots'][-1] if data['annual_snapshots'] else data['baseline']
                current_cash = item['cash_by_club_gbp']
                old_cash = previous['cash_by_club_gbp']
                shared = current_cash.keys() & old_cash.keys()
                item['clubs_cash_increased_vs_previous'] = sum(current_cash[c] > old_cash[c] for c in shared)
                item['clubs_cash_decreased_vs_previous'] = sum(current_cash[c] < old_cash[c] for c in shared)
                item['clubs_cash_unchanged_vs_previous'] = sum(current_cash[c] == old_cash[c] for c in shared)
                item['season_simulated_fixtures'] = progress.matches_played
                item['elapsed_seconds'] = round(perf_counter() - started, 2)
                if item['completed_fixtures'] != item['fixtures']:
                    item['hard_issues'].append('unfinished competitions')
                data['annual_snapshots'].append(item)
                data['years_completed'] = season
                if season in milestones:
                    data['checkpoints'][str(season)] = item
                data['status'] = 'running' if season < seasons else 'completed'
                _save_atomic(data, output)
                print(json.dumps({'season': season, 'label': label, 'elapsed_seconds': item['elapsed_seconds'],
                                  'clubs': item['active_clubs'], 'club_min': item['squad_min'],
                                  'starter_gaps': item['uncovered_starter_slots'],
                                  'cash_negative': item['cash_negative_clubs'],
                                  'transfers_total': item['completed_transfers_cumulative'],
                                  'issues': item['hard_issues']}, ensure_ascii=False), flush=True)
                if season < seasons:
                    session.begin_next_season()
            except Exception as exc:
                data['status'] = 'failed'
                data['error_season'] = season
                data['error'] = f'{type(exc).__name__}: {exc}'
                data['elapsed_seconds'] = round(perf_counter() - started, 2)
                _save_atomic(data, output)
                raise
    data['elapsed_seconds'] = round(perf_counter() - started, 2)
    data['has_hard_issues'] = any(item['hard_issues'] for item in data['annual_snapshots'])
    _save_atomic(data, output)
    return data


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--seasons', type=int, default=20)
    parser.add_argument('--output', type=Path, default=ROOT / 'reports/ts247_long_horizon.json')
    args = parser.parse_args()
    result = run(args.seasons, output=args.output)
    print(json.dumps({'status':result['status'], 'years':result['years_completed'],
                      'seconds':result['elapsed_seconds'], 'hard_issues':result['has_hard_issues']}), flush=True)


if __name__ == '__main__':
    main()
