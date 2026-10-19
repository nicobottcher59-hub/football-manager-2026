"""Read-only TS-24.1 market calibration (stdlib, no Node)."""
from __future__ import annotations

from collections import defaultdict
from statistics import median
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'src'))
from football_manager.dev_ui.session import DevelopmentSession
from football_manager.domain.market_valuation import ANCHORS_GBP, valuation_amount
from football_manager.services.market_valuation import format_gbp


def main() -> int:
    print('TS-24.1 MARKET VALUATION AUDIT (no transfers executed)')
    print('BASE PRICES: 27 years, normal form, typical conditions')
    for ovr, price in ANCHORS_GBP:
        assert valuation_amount(ovr=ovr, age=27) == price
        print(f'  OVR {ovr:>2}: {format_gbp(price)}')
    print('\nILLUSTRATIVE AGE / PERCEIVED UPSIDE COMPARISON')
    for age, ovr, upside in ((16,60,0),(16,60,15),(16,60,30),
                             (19,72,0),(19,72,15),(19,72,27),
                             (20,75,0),(20,75,12),(21,80,12),
                             (27,80,0),(34,80,0),(19,90,7),
                             (35,85,0)):
        value=valuation_amount(ovr=ovr,age=age,perceived_growth=upside)
        print(f'  {age:>2} years  {ovr:>2} OVR  perceived upside {upside:>2}: {format_gbp(value)}')
    session=DevelopmentSession(); registry=session._world_squads
    tiers=defaultdict(list)
    for cid, club in registry.clubs.items():
        for player in club.squad.players:
            tiers[registry.identities[cid].tier].append(registry.market_values[player.id].value_gbp)
    print('\nPROFESSIONAL DIVISIONS — CURRENT OPENING COHORT')
    for tier, name in ((1,'Premier'),(2,'Championship'),(3,'League One'),(4,'League Two')):
        prices=tiers[tier]
        print(f'  {name:<13}: {len(prices)} players, median {format_gbp(int(median(prices)))}')
    print(f'  Price snapshots: {len(registry.market_values)} including U17/U21 (not U15 previews)')
    print('These are game-design prices, not real-market evidence or actual asking prices.')
    return 0


if __name__ == '__main__':
    sys.exit(main())
