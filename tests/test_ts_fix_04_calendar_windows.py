"""TS-FIX-04: July planning, unattended Calendar and scheduled market registrations."""
from copy import deepcopy
from dataclasses import replace
from datetime import date, timedelta

import pytest

from football_manager.dev_ui.session import DevelopmentSession
from football_manager.domain.transfer_negotiation import TransferTerms
from football_manager.domain.transfer_personal import PersonalTerms, PersonalEvent
from football_manager.services.transfer_negotiation import (
    _create_offer, negotiate, transfer_read_model,
)
from football_manager.services.transfer_personal import _finish, agent_demand
from football_manager.services.transfer_windows import window_open, next_opening, windows_for_year, window_info
from football_manager.ui_shell.calendar import calendar_read_model
from football_manager.ui_shell.progression import (
    _settle_scheduled_registrations, pending_transfer_decisions, progression_read_model, simulate_until,
)
from football_manager.persistence.session_codec import GRAPH_VERSION, capture_manager_graph, restore_manager_graph


@pytest.fixture(scope='module')
def base():
    return DevelopmentSession()


@pytest.fixture
def s(base):
    return deepcopy(base)


def _candidate(s, *, arrival=date(2027, 1, 1)):
    reg=s._world_squads
    for cid, club in reg.clubs.items():
        if cid==s.home_club.id:continue
        for player in club.squad.players:
            contract=reg.contracts.get(player.id)
            if (contract and contract.kind=='professional'
                    and contract.expires_on>arrival+timedelta(days=10)
                    and 50<player.overall_rating<65 and player.age_on(s.current_date)>=20):
                demand=agent_demand(reg,player,cid,s.home_club.id,s.current_date)
                if demand['interested']:
                    return cid,player,demand
    raise AssertionError('No test candidate available')


def _prepare_pending(s, *, date_signed=date(2026, 10, 5), price=10_000):
    s.current_date=date_signed
    reg=s._world_squads
    seller,player,demand=_candidate(s)
    deal=_create_offer(reg,player.id,seller,s.home_club.id,s.current_date,
                       TransferTerms(price),s.home_club.id)
    terms=PersonalTerms(demand['weekly_wage_gbp'],demand['years'],demand['role'],0)
    deal=replace(deal,status='agreed',personal_terms=terms,
                 personal_events=(PersonalEvent(s.current_date,'agent',terms,'Contract accepted'),))
    reg.transfer_offers[deal.deal_id]=deal
    return deal,player,terms


def test_new_career_starts_in_july_with_preseason_time(base):
    assert base.current_date==date(2026,7,1)
    next_match=base._next_unplayed_managed_match()
    assert next_match.match_date>base.current_date
    assert (next_match.match_date-base.current_date).days>=21
    day=calendar_read_model(base)
    assert day['date']=='2026-07-01'
    assert day['transfer_windows'][0]['start']=='2026-07-01'
    assert progression_read_model(base)['match_day'] is False


@pytest.mark.parametrize('day,expected',[(date(2026,6,30),False), (date(2026,7,1),True),
    (date(2026,8,31),True), (date(2026,9,1),False), (date(2027,1,1),True),
    (date(2027,1,31),True), (date(2027,2,1),False)])
def test_english_registration_window_boundaries(day,expected):
    assert window_open(day)==expected


def test_next_english_window_and_public_info():
    assert next_opening(date(2026,9,2))==date(2027,1,1)
    assert next_opening(date(2027,2,1))==date(2027,7,1)
    assert next_opening(date(2026,8,1))==date(2026,8,1)
    assert window_info(date(2026,9,5))['opens_on']=='2027-01-01'
    assert windows_for_year(2027,'England')[1]==(date(2027,7,1),date(2027,8,31))


def test_new_club_bid_allowed_outside_window_without_initial_price_hint(s):
    s.current_date=date(2026,10,5)
    seller,player,_=_candidate(s)
    response=negotiate(s,{'action':'submit','player_id':player.id,
                    'seller_id':seller,'terms':{'fixed_gbp':0}})
    assert response['deal_id'] in s._world_squads.transfer_offers
    page=transfer_read_model(s)
    assert not page['window_open']
    assert page['window']['opens_on']=='2027-01-01'


def test_signed_terms_wait_for_next_window_without_player_or_cash_movement(s):
    deal,player,terms=_prepare_pending(s)
    registry=s._world_squads
    previous_cash=registry.club_finances[deal.buyer_id].cash_gbp
    current_team=registry.contracts[player.id].club_id
    result=_finish(s,deal,terms)
    assert result['status']=='pending_window'
    assert result['arrival_on']=='2027-01-01'
    assert registry.contracts[player.id].club_id==current_team
    assert registry.club_finances[deal.buyer_id].cash_gbp==previous_cash
    assert registry.transfer_offers[deal.deal_id].personal_status=='completed'
    assert registry.transfer_offers[deal.deal_id].status=='pending_window'
    assert not any(row['deal_id']==deal.deal_id for row in pending_transfer_decisions(s))
    read=transfer_read_model(s)
    assert next(x for x in read['offers'] if x['id']==deal.deal_id)['arrival_on']=='2027-01-01'
    registry.validate()


def test_scheduled_transfer_only_finishes_when_registration_opens(s):
    deal,player,terms=_prepare_pending(s)
    registry=s._world_squads
    _finish(s,deal,terms)
    for day in (date(2026,10,5),date(2026,12,31)):
        s.current_date=day
        _settle_scheduled_registrations(s)
        assert registry.transfer_offers[deal.deal_id].status=='pending_window'
        assert registry.contracts[player.id].club_id==deal.seller_id
    original=registry.club_finances[deal.buyer_id].cash_gbp
    s.current_date=date(2027,1,1)
    _settle_scheduled_registrations(s)
    settled=registry.transfer_offers[deal.deal_id]
    assert settled.status=='completed'
    assert settled.settled_on==s.current_date
    assert registry.contracts[player.id].club_id==deal.buyer_id
    assert registry.club_finances[deal.buyer_id].cash_gbp==original-deal.terms.fixed_gbp
    _settle_scheduled_registrations(s)
    assert registry.club_finances[deal.buyer_id].cash_gbp==original-deal.terms.fixed_gbp
    registry.validate()


def test_unaffordable_scheduled_registration_fails_without_transferring(s):
    deal,player,terms=_prepare_pending(s,price=15_000)
    registry=s._world_squads
    _finish(s,deal,terms)
    account=registry.club_finances[deal.buyer_id]
    registry.club_finances[deal.buyer_id]=replace(account,cash_gbp=0,transfer_budget_gbp=0)
    s.current_date=date(2027,1,1)
    _settle_scheduled_registrations(s)
    assert registry.transfer_offers[deal.deal_id].status=='failed'
    assert registry.contracts[player.id].club_id==deal.seller_id
    registry.validate()


def test_calendar_auto_sim_does_not_pause_for_open_offers(s,monkeypatch):
    from football_manager.ui_shell import progression
    seller,player,_=_candidate(s,arrival=date(2027,1,1))
    deal=_create_offer(s._world_squads,player.id,seller,s.home_club.id,s.current_date,
                     TransferTerms(0),seller)
    first=s.current_date
    monkeypatch.setattr(progression,'_finish_day',lambda *_:0)
    monkeypatch.setattr(progression,'_move_day',lambda session: setattr(session,'current_date',session.current_date+timedelta(days=1)) or 0)
    output=simulate_until(s,first+timedelta(days=5))
    assert s.current_date==first+timedelta(days=5)
    assert output['to_date']==s.current_date.isoformat()
    assert not output['stopped_for_decision']
    assert output['decisions']
    assert s._world_squads.transfer_offers[deal.deal_id].status=='manager_turn'
    assert s._calendar_resume_target is None


def test_v29_pending_registration_survives_roundtrip(s):
    deal,player,terms=_prepare_pending(s)
    _finish(s,deal,terms)
    graph=capture_manager_graph(s)
    assert graph['version']==GRAPH_VERSION==29
    restored=restore_manager_graph(graph)
    other=restored._world_squads.transfer_offers[deal.deal_id]
    assert other.status=='pending_window' and other.personal_terms==terms
    assert restored._world_squads.contracts[player.id].club_id==deal.seller_id
    restored._world_squads.validate()


def test_v28_graph_compatibility(s):
    graph=capture_manager_graph(s)
    graph['version']=28
    restored=restore_manager_graph(graph)
    assert restored.current_date==s.current_date
    assert restored._world_squads.clubs.keys()==s._world_squads.clubs.keys()
