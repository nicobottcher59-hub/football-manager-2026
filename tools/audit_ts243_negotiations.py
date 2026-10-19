"""Small, deterministic TS-24.3 market sanity check; never modifies saves."""
from __future__ import annotations
from statistics import median
from pathlib import Path
import sys

# Direct invocation from the project root also works without installation.
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'src'))
from football_manager.dev_ui.session import DevelopmentSession
from football_manager.services.transfer_negotiation import _seller_target, _quote


def main() -> None:
    s=DevelopmentSession();r=s._world_squads;manager=s.home_club.id
    ratios=[]
    for cid,club in r.clubs.items():
        if cid==manager:continue
        for player in club.squad.players:
            quote=_quote(r,player).value_gbp
            if quote:
                ratios.append(_seller_target(r,cid,manager,player,r.contracts[player.id],s.current_date)/quote)
    print('TS-24.3 fictional England opening economy')
    print(f'Players reviewed: {len(ratios)}')
    print(f'Median asking/market: {median(ratios):.3f}x')
    print(f'Min asking/market: {min(ratios):.3f}x; max: {max(ratios):.3f}x')
    print('No club money or player contracts changed.')


if __name__=='__main__':
    main()
