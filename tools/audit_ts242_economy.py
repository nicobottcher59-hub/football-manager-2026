"""Read-only weekly wage and 92-club budget calibration (stdlib only)."""
from __future__ import annotations

from collections import defaultdict
from statistics import median
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'src'))

from football_manager.dev_ui.session import DevelopmentSession
from football_manager.services.club_economy import WAGE_ANCHORS, weekly_payroll
from football_manager.services.market_valuation import format_gbp

TIERS = ((1, 'Premier League'), (2, 'Championship'), (3, 'League One'), (4, 'League Two'))


def main() -> int:
    print('TS-24.2 - WEEKLY WAGES AND CLUB FINANCE AUDIT')
    print('WAGE ANCHORS: standard professional reference salary per week')
    for ovr, wage in WAGE_ANCHORS:
        print(f'  OVR {ovr:>2}: {format_gbp(wage):>11} / week')
    registry = DevelopmentSession()._world_squads
    amounts = defaultdict(lambda: {'payroll': [], 'budgets': [], 'cash': [], 'transfers': []})
    for cid in registry.clubs:
        tier = registry.identities[cid].tier
        finances = registry.club_finances[cid]
        payroll = weekly_payroll(registry, cid)
        assert payroll <= finances.wage_budget_weekly_gbp
        assert finances.transfer_budget_gbp <= finances.cash_gbp
        amounts[tier]['payroll'].append(payroll)
        amounts[tier]['budgets'].append(finances.wage_budget_weekly_gbp)
        amounts[tier]['cash'].append(finances.cash_gbp)
        amounts[tier]['transfers'].append(finances.transfer_budget_gbp)
    print('\nDIVISION MEDIANS - fictional opening career budgets')
    for tier, name in TIERS:
        item=amounts[tier]
        print(f'  {name:<16} {len(item["payroll"]):>2} clubs |'
              f' wages {format_gbp(int(median(item["payroll"]))):>11}/wk |'
              f' ceiling {format_gbp(int(median(item["budgets"]))):>11}/wk |'
              f' transfers {format_gbp(int(median(item["transfers"]))):>11}')
    print(f'\nTotal contracts: {len(registry.contracts)}'
          f' (first team plus U17/U21) | club budgets: {len(registry.club_finances)}')
    print('Revenue and initial cash are simulation assumptions, not verified real-club finances.')
    return 0


if __name__ == '__main__':
    sys.exit(main())
