"""TS-24.10: the player decides retirement; the squad does not veto it."""
from copy import deepcopy
from dataclasses import replace
from datetime import date

import pytest

from football_manager.dev_ui.session import DevelopmentSession
from football_manager.domain.enums import Position
from football_manager.domain.loan_market import LoanAgreement
from football_manager.persistence.manager_career import validate_manager_session
from football_manager.services.club_economy import auto_renew_ai_contracts
from football_manager.services.loan_market import active_loan
from football_manager.services.player_aging import (
    finalize_season_retirements, register_medical_absence,
)

@pytest.fixture(scope='module')
def original():
    return DevelopmentSession()


def flagged(player, on_date, status='requested'):
    player.aging=replace(player.aging, retirement_status=status,
                         retirement_requested_on=on_date,
                         retirement_checked_on=(on_date if status == 'deferred' else None))


def test_requested_retirement_wins_even_if_last_goalkeeper_or_starter(original):
    s=deepcopy(original)
    reg=s._world_squads
    cid=next(cid for cid in reg.clubs if cid not in (s.home_club.id,s.away_club.id))
    club=reg.clubs[cid]
    keepers=[p for p in club.squad.players if p.primary_position is Position.GK]
    # Even if both are about to leave, the manager has no veto.
    for keeper in keepers:
        flagged(keeper,s.current_date)
    retired=finalize_season_retirements(s._world,date(2026,9,1))
    assert set(p.id for p in keepers).issubset(retired)
    assert sum(p.primary_position is Position.GK for p in club.squad.players)==0
    assert all(p.aging.retired_on == date(2026,9,1) for p in keepers)
    assert not any(p.aging.retirement_status == 'deferred' for p in club.squad.players)
    assert all(p.id not in reg.contracts for p in keepers)
    # Consequence is intentionally a sporting problem for club AI.
    reg.validate()


def test_legacy_deferred_status_is_honored_next_season(original):
    s=deepcopy(original)
    reg=s._world_squads
    cid=next(cid for cid in reg.clubs if cid!=s.home_club.id)
    player=reg.clubs[cid].squad.players[0]
    flagged(player,s.current_date,'deferred')
    assert player.aging.retirement_checked_on == s.current_date
    result=finalize_season_retirements(s._world,date(2027,7,1))
    assert player.id in result
    assert reg.retired_players[player.id].player is player
    assert finalize_season_retirements(s._world,date(2027,7,1)) == ()


def test_injured_player_retires_and_cleans_medical_followup(original):
    s=deepcopy(original)
    reg=s._world_squads
    cid=next(cid for cid in reg.clubs if cid!=s.home_club.id)
    player=reg.clubs[cid].squad.players[1]
    register_medical_absence(s._world,cid,player.id,s.current_date,
                             episode_id='ts2410', duration_days=100,
                             label='Serious injury')
    flagged(player,s.current_date)
    assert player.id in reg.medical_followups
    assert player.id in finalize_season_retirements(s._world,date(2026,9,1))
    assert player.id not in reg.medical_followups
    assert reg.retired_players[player.id].player.aging.active_injury is not None
    reg.validate()


def test_loaned_player_can_retire_without_returning_to_parent(original):
    s=deepcopy(original)
    reg=s._world_squads
    choices=[cid for cid in reg.clubs if cid not in (s.home_club.id,s.away_club.id)]
    parent,borrower=choices[:2]
    player=next(p for p in reg.clubs[parent].squad.players if p.primary_position is not Position.GK)
    reg.clubs[parent].squad.remove(player.id)
    reg.clubs[borrower].squad.add(player)
    loan=LoanAgreement('ts2410-loan',player.id,parent,borrower,
                       s.current_date,date(2027,2,21),25,'rotation')
    reg.loans[loan.loan_id]=loan
    flagged(player,s.current_date)
    reg.validate()
    retired=finalize_season_retirements(s._world,date(2026,9,1))
    assert player.id in retired
    assert active_loan(reg,player.id) is None
    assert reg.loans[loan.loan_id].status=='retired'
    assert reg.loans[loan.loan_id].completed_on==date(2026,9,1)
    assert not reg.clubs[borrower].squad.contains(player.id)
    assert not reg.clubs[parent].squad.contains(player.id)
    assert reg.retired_players[player.id].club_id==borrower
    assert player.id not in reg.contracts
    reg.validate()


def test_player_retirement_rolls_back_loans_medical_contracts_and_roster(original):
    s=deepcopy(original)
    reg=s._world_squads
    cid=next(cid for cid in reg.clubs if cid!=s.home_club.id)
    player=reg.clubs[cid].squad.players[2]
    flagged(player,s.current_date)
    original_age=player.aging
    initial_contract=reg.contracts[player.id]
    with pytest.raises(RuntimeError,match='undo'):
        with s._world.transaction():
            assert player.id in finalize_season_retirements(s._world,date(2026,9,1))
            raise RuntimeError('undo')
    assert player.aging==original_age
    assert reg.clubs[cid].squad.get(player.id) is player
    assert reg.contracts[player.id]==initial_contract
    assert player.id not in reg.retired_players
    reg.validate()


def test_ai_does_not_renew_a_player_who_has_chosen_retirement(original):
    s=deepcopy(original)
    reg=s._world_squads
    cid=next(cid for cid in reg.clubs if cid!=s.home_club.id)
    player=reg.clubs[cid].squad.players[3]
    contract=reg.contracts[player.id]
    reg.contracts[player.id]=replace(contract,expires_on=date(2026,9,1))
    flagged(player,s.current_date)
    with s._world.transaction():
        auto_renew_ai_contracts(s._world,date(2026,9,1),managed_club_id=s.home_club.id)
    assert reg.contracts[player.id].expires_on == date(2026,9,1)
    assert player.aging.retirement_status=='requested'


def test_retirement_policy_keeps_v16_graph_fields(original):
    from football_manager.persistence.manager_career import _REQUIRED_FIELDS
    s=deepcopy(original)
    reg=s._world_squads
    cid=next(cid for cid in reg.clubs if cid not in (s.home_club.id,s.away_club.id))
    player=reg.clubs[cid].squad.players[4]
    flagged(player,s.current_date)
    finalize_season_retirements(s._world,date(2026,9,1))
    assert set(vars(s))==_REQUIRED_FIELDS
    assert reg.retired_players[player.id].player is player
    # The new archive is still serializable without schema changes.
    from football_manager.persistence.session_codec import capture_manager_graph, restore_manager_graph
    restored=restore_manager_graph(capture_manager_graph(s))
    assert restored._world_squads.retired_players[player.id].retired_on==date(2026,9,1)
    restored._world_squads.validate()


def test_manager_cannot_overrule_retirement_with_new_contract(original):
    from football_manager.services.club_economy import quote_renewal
    s=deepcopy(original)
    player=s.home_club.squad.players[6]
    flagged(player,s.current_date)
    with pytest.raises(ValueError,match='decided to retire'):
        quote_renewal(s._world_squads,player,
                      s._world_squads.contracts[player.id],s.current_date,1)


def test_financial_outlook_does_not_make_losses_an_integrity_failure(original):
    from football_manager.services.club_economy import financial_outlook,finances_read_model
    s=deepcopy(original)
    reg=s._world_squads
    cid=s.home_club.id
    baseline=reg.club_finances[cid]
    analysis=financial_outlook(reg,cid)
    assert analysis['level'] in {'stable','investment_or_deficit','pressure','critical'}
    assert 'projected_six_month_cash_gbp' in analysis
    finance_view=finances_read_model(s)
    assert finance_view['financial_outlook']==analysis
    assert reg.club_finances[cid] is baseline
    # Negative cash is permitted and recorded rather than silently remedied.
    reg.club_finances[cid]=replace(baseline,cash_gbp=-100_000)
    assert financial_outlook(reg,cid)['level'] in {'pressure','critical'}
    assert reg.club_finances[cid].cash_gbp==-100_000
    reg.validate()


def test_player_with_confirmed_retirement_refuses_transfer(original):
    from football_manager.services.transfer_personal import _player_interest
    s=deepcopy(original)
    r=s._world_squads
    parent=s.home_club.id
    buyer=next(cid for cid in r.clubs if cid!=parent)
    p=s.home_club.squad.players[0]
    flagged(p,s.current_date)
    allowed,reason=_player_interest(r,p,parent,buyer,s.current_date)
    assert not allowed and 'decided to retire' in reason


def test_free_agent_retirement_is_decision_based_not_age_only(original):
    from football_manager.domain.loan_market import FreeAgent
    from football_manager.services.loan_market import _retire_old_unsigned
    s=deepcopy(original)
    r=s._world_squads
    cid=next(cid for cid in r.clubs if cid not in (s.home_club.id,s.away_club.id))
    club=r.clubs[cid]
    p=club.squad.players[0]
    p.identity=replace(p.identity,birth_date=date(1986,1,1))
    p.aging=replace(p.aging,retirement_age=45.5,retirement_status='active',
                    retirement_requested_on=None,retirement_checked_on=None)
    contract=r.contracts.pop(p.id)
    club.squad.remove(p.id)
    r.free_agents[p.id]=FreeAgent(p,cid,date(2025,8,21),contract.weekly_wage_gbp)
    with s._world.transaction():
        retired=_retire_old_unsigned(s._world,date(2026,9,1))
    assert retired==0 and p.id in r.free_agents
    assert p.aging.retirement_status=='active'
    flagged(p,s.current_date)
    with s._world.transaction():
        retired=_retire_old_unsigned(s._world,date(2026,10,1))
    assert retired==1 and p.id not in r.free_agents and p.id in r.retired_players
    r.validate()
