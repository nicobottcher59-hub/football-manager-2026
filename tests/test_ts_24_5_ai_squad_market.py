"""TS-24.5 squad planning and autonomous market integration tests."""
from __future__ import annotations

from collections import Counter
from copy import deepcopy
from datetime import date
from pathlib import Path

import pytest

from football_manager.dev_ui.session import DevelopmentSession
from football_manager.domain.enums import Position
from football_manager.services.ai_squad_planning import squad_plan, can_spare, club_planning_view
from football_manager.services.ai_transfer_market import process_ai_market, window_open
from football_manager.services.transfer_negotiation import review_transfers, transfer_read_model, negotiate
from football_manager.services.club_economy import weekly_payroll


@pytest.fixture(scope='module')
def starting():
    return DevelopmentSession()


def _snapshot(registry):
    return ({cid:tuple(sorted(p.id for p in club.squad.players)) for cid,club in registry.clubs.items()},
            dict(registry.contracts),dict(registry.club_finances),dict(registry.transfer_offers),
            registry.transfer_last_review_on,registry.transfer_next_id)


def test_all_clubs_plan_two_lineups_plus_keeper_without_double_count(starting):
    r=starting._world_squads
    assert len(r.clubs)==92
    for cid,club in r.clubs.items():
        plan=squad_plan(club,r.identities[cid].primary)
        assigned=[x['player_id'] for x in plan['assignments']]
        assert len(assigned)==len(set(assigned))
        assert plan['target_size']==23
        assert plan['starters_covered']==11 and plan['backups_covered']==11
        assert len(plan['vacancies'])==1 and plan['vacancies'][0]['position']=='GK'
        assert len(plan['assignments'])+len(plan['vacancies'])==23
    view=club_planning_view(starting,starting.home_club.id)
    assert view['club_id']==starting.home_club.id


def test_planner_detects_real_role_shortage_and_different_formation(starting):
    r=starting._world_squads
    cid=next(cid for cid in r.clubs if cid!=starting.home_club.id)
    club=r.clubs[cid]
    keeper=next(p for p in club.squad.players if p.primary_position is Position.GK)
    old=squad_plan(club,r.identities[cid].primary)
    after=squad_plan(club,r.identities[cid].primary,excluded_id=keeper.id)
    assert after['starters_covered']+after['backups_covered'] < old['starters_covered']+old['backups_covered']
    assert any(x['position']=='GK' and x['layer']<=2 for x in after['vacancies'])
    assert not can_spare(club,r.identities[cid].primary,keeper.id)
    other=squad_plan(club,r.identities[cid].alternative)
    assert len(other['assignments'])+len(other['vacancies'])==23
    assert all(x['position'] in {pos.value for pos in Position} for x in other['vacancies'])


def test_windows_and_closed_offer_without_modifying_balances(starting):
    assert all(window_open(date(2027,m,15)) == (m in (1,7,8)) for m in range(1,13))
    s=deepcopy(starting)
    from football_manager.services.transfer_negotiation import _availability
    r=s._world_squads
    target=next((cid,p) for cid,c in r.clubs.items() if cid!=s.home_club.id for p in c.squad.players)
    old=s.current_date
    s.current_date=date(2026,10,13)
    money=_availability(r,s.home_club.id,s.current_date)
    with pytest.raises(ValueError,match='window is closed'):
        negotiate(s,{'action':'submit','seller_id':target[0],'player_id':target[1].id,
                     'terms':{'fixed_gbp':100_000}})
    assert _availability(r,s.home_club.id,s.current_date)==money
    s.current_date=old


def test_autonomous_ai_transfers_are_real_and_fully_reversible(starting):
    s=deepcopy(starting)
    r=s._world_squads
    before=_snapshot(r)
    manager=s.home_club.id
    with pytest.raises(RuntimeError,match='abort market'):
        with s._world.transaction():
            review_transfers(s._world,date(2026,9,1))
            assert any(d.status=='completed' for d in r.transfer_offers.values())
            raise RuntimeError('abort market')
    assert _snapshot(r)==before
    with s._world.transaction():
        count=review_transfers(s._world,date(2026,9,1))
    assert count>0
    deals=[d for d in r.transfer_offers.values() if d.status=='completed']
    assert deals
    assert sum(len(c.squad) for c in r.clubs.values())==sum(len(c.squad) for c in starting._world_squads.clubs.values())
    for deal in deals:
        assert manager not in (deal.seller_id,deal.buyer_id)
        assert not r.clubs[deal.seller_id].squad.contains(deal.player_id)
        assert r.clubs[deal.buyer_id].squad.contains(deal.player_id)
        assert r.contracts[deal.player_id].club_id==deal.buyer_id
        assert deal.personal_status=='completed' and deal.personal_terms.weekly_wage_gbp>0
        assert deal.terms.fixed_gbp>=5_000
    # The manager's club never silently spends or sells in an AI cycle.
    assert r.club_finances[manager]==before[2][manager]
    assert tuple(sorted(p.id for p in s.home_club.squad.players))==before[0][manager]
    assert sum(account.cash_gbp for account in r.club_finances.values())==sum(account.cash_gbp for account in before[2].values())
    assert all(weekly_payroll(r,cid)<=r.club_finances[cid].wage_budget_weekly_gbp
               for cid in r.clubs if cid!=manager)
    r.validate()
    # Same boundary is idempotent: no duplicate transfer settlement.
    snapshot=_snapshot(r)
    with s._world.transaction():
        assert review_transfers(s._world,date(2026,9,1))==0
    assert _snapshot(r)==snapshot
    ui=transfer_read_model(s)
    assert ui['world_transfers']
    assert ui['world_transfers'][0]['fee_gbp']>0
    assert ui['window_open'] is True  # the career itself remains in August


def test_closed_month_review_does_not_create_new_trades(starting):
    s=deepcopy(starting)
    r=s._world_squads
    with s._world.transaction():
        review_transfers(s._world,date(2026,9,1))
    before_count=sum(d.status=='completed' for d in r.transfer_offers.values())
    with s._world.transaction():
        review_transfers(s._world,date(2026,10,1))
    assert sum(d.status=='completed' for d in r.transfer_offers.values())==before_count
    r.validate()


def test_pending_manager_offer_reserves_ai_buyers_budget(starting):
    from datetime import timedelta
    from football_manager.domain.transfer_negotiation import (
        NegotiationEvent, TransferNegotiation, TransferTerms)
    from football_manager.services.transfer_negotiation import _availability

    s=deepcopy(starting)
    r=s._world_squads
    manager=s.home_club.id
    buyer=max((cid for cid in r.clubs if cid!=manager),
              key=lambda cid:_availability(r,cid,s.current_date))
    before=_availability(r,buyer,s.current_date)
    assert before>200_000
    own_player=next(iter(s.home_club.squad.players))
    fee=100_000
    terms=TransferTerms(fee)
    deal=TransferNegotiation('t24-reserved-test',own_player.id,manager,buyer,
        s.current_date,s.current_date+timedelta(days=20),
        'manager_turn',buyer,terms,
        (NegotiationEvent(s.current_date,buyer,terms,'Real AI offer awaiting manager decision'),))
    deal.validate()
    r.transfer_offers[deal.deal_id]=deal
    assert _availability(r,buyer,s.current_date)==before-fee


def test_cached_opponent_lineup_is_rebuilt_after_ai_sale(starting):
    from football_manager.ui_shell.progression import _bind_next_match

    s=deepcopy(starting)
    rival=s.away_club
    assert rival.id in s._world_squads.clubs
    selected=next(player for player in s.away_lineup.selected_players
                  if player.primary_position is not Position.GK)
    rival.squad.remove(selected.id)
    _bind_next_match(s)
    assert selected.id not in {p.id for p in s.away_lineup.selected_players}
    rival.validate_lineup(s.away_lineup)


def test_source_contracts_for_ui():
    root=Path(__file__).resolve().parents[1]
    js=(root/'frontend/portable/transfers.js').read_text()
    squads=(root/'frontend/portable/world_squads.js').read_text()
    assert 'World transfers' in js and 'world_transfers' in js
    assert 'Window' in js and 'window_open' in js
    assert 'squad_planning' in squads
