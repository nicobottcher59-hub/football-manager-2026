"""TS-FIX-03: new shared agent bargaining, public disclosure and money-backed terms."""
from __future__ import annotations

from copy import deepcopy
from datetime import date

import pytest
from football_manager.dev_ui.session import DevelopmentSession
from football_manager.domain.football_world import PlayerSeasonUsage
from football_manager.domain.transfer_personal import PersonalTerms
from football_manager.persistence.session_codec import capture_manager_graph, restore_manager_graph, GRAPH_VERSION
from football_manager.services.contract_renewal import renewal_command, renew_read_model, _quote
from football_manager.services.club_economy import finances_read_model, review_finances
from football_manager.services.contract_bargaining import agent_response, public_wage_range, terms_from_json
from football_manager.services.transfer_negotiation import transfer_read_model


@pytest.fixture(scope='module')
def base():
    return DevelopmentSession()


def player_and_quote(session):
    p=session.home_club.squad.players[0]
    return p,_quote(session._world_squads,p,session._world_squads.contracts[p.id],session.current_date)


def offer(quote,wage=0,bonuses=None,signing=0):
    return {'weekly_wage_gbp':wage,'years':quote['years'],'role':quote['role'],
            'signing_bonus_gbp':signing,'bonuses':bonuses or []}


def test_wage_starts_zero_without_exposing_private_floor(base):
    p,q=player_and_quote(base)
    public=renew_read_model(base,p.id)
    row=next(r for r in finances_read_model(base)['contracts'] if r['player_id']==p.id)
    assert public['quote']['range']['low_gbp']<q['weekly_wage_gbp']<public['quote']['range']['high_gbp']
    assert 'minimum_weekly_gbp' not in row['renewal']
    assert 'weekly_wage_gbp' not in public['quote']
    assert q['weekly_wage_gbp'] not in row['renewal'].values()
    assert renew_read_model(base,p.id)==public  # read is pure/deterministic


def test_zero_offer_gets_counter_and_patience_loss(base):
    s=deepcopy(base);p,q=player_and_quote(s)
    result=renewal_command(s,{'action':'contract_offer','player_id':p.id,'terms':offer(q)})
    assert result['status']=='counter' and result['patience']<100
    row=renew_read_model(s,p.id)['talk']
    assert row['status']=='counter' and len(row['history'])==2
    assert row['counter']['weekly_wage_gbp']>=75
    s._world_squads.validate()


def test_lowball_repeatedly_can_end_talks(base):
    s=deepcopy(base);p,q=player_and_quote(s)
    seen=[]
    for _ in range(7):
        reply=renewal_command(s,{'action':'contract_offer','player_id':p.id,'terms':offer(q)})
        seen.append(reply['patience'])
        if reply['status']=='ended':break
    assert seen==sorted(seen,reverse=True) and seen[-1]==0
    with pytest.raises(ValueError,match='closed'):
        renewal_command(s,{'action':'contract_offer','player_id':p.id,'terms':offer(q,wage=q['weekly_wage_gbp'])})


def test_agent_can_trade_bonus_and_promised_role_for_wage(base):
    p,q=player_and_quote(base)
    high=PersonalTerms(q['weekly_wage_gbp'],q['years'],q['role'],0)
    result=agent_response(p,high,q,100,0)
    assert result[0]=='accept'
    low=PersonalTerms(round(q['weekly_wage_gbp']*.83),q['years'],q['role'],0)
    reaction=agent_response(p,low,q,100,0)
    assert reaction[0]=='counter'
    assert reaction[1].weekly_wage_gbp>=75
    assert reaction[1]!=low


def test_accept_agent_counter_settles_real_bonus_and_changes_role(base):
    s=deepcopy(base);p,q=player_and_quote(s);r=s._world_squads
    renewal_command(s,{'action':'contract_offer','player_id':p.id,'terms':offer(q)})
    prev=r.contracts[p.id];account=r.club_finances[s.home_club.id]
    counter=r.contract_talks[p.id].counter
    outcome=renewal_command(s,{'action':'contract_accept','player_id':p.id})
    assert outcome['renewed'] and r.contracts[p.id].weekly_wage_gbp==counter.weekly_wage_gbp
    assert r.contracts[p.id].role==counter.role
    assert r.club_finances[s.home_club.id].cash_gbp==account.cash_gbp-counter.signing_bonus_gbp
    assert r.club_finances[s.home_club.id].season_operations_gbp==account.season_operations_gbp+counter.signing_bonus_gbp
    assert r.contracts[p.id].history and r.contracts[p.id].history[-1].weekly_gbp==prev.weekly_wage_gbp
    with pytest.raises(ValueError,match='closed'):
        renewal_command(s,{'action':'contract_accept','player_id':p.id})
    r.validate()


def test_earned_contract_bonus_once_at_monthly_review(base):
    s=deepcopy(base);p,q=player_and_quote(s);r=s._world_squads
    amount=3_000
    bonus={'kind':'appearances','threshold':5,'amount_gbp':amount}
    reply=renewal_command(s,{'action':'contract_offer','player_id':p.id,
        'terms':offer(q,wage=q['weekly_wage_gbp'],bonuses=[bonus])})
    assert reply['renewed']
    r.usage[p.id]=PlayerSeasonUsage(appearances=6,starts=6,minutes=540,goals=0,assists=0,rating_total=38.)
    with s._world._atomic():
        review_finances(s._world,date(2026,10,1))
    row=r.contract_bonuses[p.id]
    assert row.paid==('appearances',)
    assert r.club_finances[s.home_club.id].season_operations_gbp>=amount
    previous=sum(month.operations_gbp for month in r.club_finances[s.home_club.id].history)
    with s._world._atomic():
        review_finances(s._world,date(2026,11,1))
    assert r.contract_bonuses[p.id].paid==('appearances',)
    assert r.club_finances[s.home_club.id].history[-1].operations_gbp<previous+amount
    r.validate()


def test_validation_rejects_invalid_bonus_combinations():
    with pytest.raises(ValueError):
        terms_from_json({'weekly_wage_gbp':0,'years':2,'role':'star','signing_bonus_gbp':0,
                         'bonuses':[{'kind':'unknown','threshold':1,'amount_gbp':3_000}]})
    with pytest.raises(ValueError):
        terms_from_json({'weekly_wage_gbp':0,'years':2,'role':'star','signing_bonus_gbp':0,
                         'bonuses':[{'kind':'appearances','threshold':5,'amount_gbp':3_000}]*2})


def test_graph_v28_roundtrip_keeps_agent_persistence(base):
    s=deepcopy(base);p,q=player_and_quote(s)
    renewal_command(s,{'action':'contract_offer','player_id':p.id,'terms':offer(q)})
    graph=capture_manager_graph(s)
    assert GRAPH_VERSION==28 and graph['version']==28
    reloaded=restore_manager_graph(graph)
    assert reloaded._world_squads.contract_talks[p.id]==s._world_squads.contract_talks[p.id]
    reloaded._world_squads.validate()


def test_version27_graph_migrates_new_contract_fields(base):
    graph=capture_manager_graph(base)
    graph['version']=27
    for node in graph['nodes']:
        if node.get('class')=='football_manager.domain.football_world:FootballWorld':
            node['fields'].pop('contract_talks',None)
            node['fields'].pop('contract_bonuses',None)
    reloaded=restore_manager_graph(graph)
    assert reloaded._world_squads.contract_talks=={}
    assert reloaded._world_squads.contract_bonuses=={}
    reloaded._world_squads.validate()


def test_closed_renewal_reopens_only_after_real_cooling_period(base):
    from datetime import timedelta
    s=deepcopy(base);p,q=player_and_quote(s)
    renewal_command(s,{'action':'contract_walk_away','player_id':p.id})
    assert renew_read_model(s,p.id)['talk']['status']=='ended'
    s.current_date+=timedelta(days=44)
    assert renew_read_model(s,p.id)['talk']['status']=='ended'
    saved=s._world_squads.contract_talks[p.id]
    s.current_date+=timedelta(days=1)
    public=renew_read_model(s,p.id)
    assert public['talk']['status']=='open' and public['talk']['patience']==100
    assert s._world_squads.contract_talks[p.id] is saved  # Read does not reset history.
    response=renewal_command(s,{'action':'contract_offer','player_id':p.id,'terms':offer(q,0)})
    assert response['status']=='counter'
    assert s._world_squads.contract_talks[p.id].started_on==s.current_date
    s._world_squads.validate()


def test_signed_renewal_can_be_negotiated_again_after_90_days(base):
    from datetime import timedelta
    s=deepcopy(base);p,q=player_and_quote(s)
    first=renewal_command(s,{'action':'contract_offer','player_id':p.id,
                             'terms':offer(q,q['weekly_wage_gbp'])})
    assert first['status']=='renewed'
    initial=s.current_date
    s.current_date=initial+timedelta(days=89)
    assert renew_read_model(s,p.id)['talk']['status']=='renewed'
    s.current_date+=timedelta(days=1)
    public=renew_read_model(s,p.id)
    assert public['available'] and public['talk']['status']=='open'
    assert s._world_squads.contract_talks[p.id].status=='renewed'
    second=renewal_command(s,{'action':'contract_offer','player_id':p.id,
                               'terms':offer(q,0)})
    assert second['status']=='counter'
    assert s._world_squads.contract_talks[p.id].started_on==s.current_date
    s._world_squads.validate()


def _affordable_agreed_transfer(s):
    from dataclasses import replace
    from football_manager.services.transfer_negotiation import _create_offer,_quote
    from football_manager.domain.transfer_negotiation import TransferTerms
    from football_manager.services.club_economy import weekly_payroll
    from football_manager.services.transfer_personal import agent_demand
    registry=s._world_squads;club_id=s.home_club.id
    funds=registry.club_finances[club_id]
    wage_room=funds.wage_budget_weekly_gbp-weekly_payroll(registry,club_id)
    for seller,other in registry.clubs.items():
        if seller==club_id or len(other.squad)<18:
            continue
        for p in other.squad.players:
            if p.primary_position.value=='GK' or _quote(registry,p).value_gbp>funds.transfer_budget_gbp//6:
                continue
            quote=agent_demand(registry,p,seller,club_id,s.current_date)
            if not quote['interested'] or quote['weekly_wage_gbp']>=wage_room:
                continue
            deal=_create_offer(registry,p.id,seller,club_id,s.current_date,TransferTerms(100_000),club_id)
            registry.transfer_offers[deal.deal_id]=replace(deal,status='agreed')
            return p,deal,quote
    raise AssertionError('No realistic affordable signing found')


def test_purchase_agent_counter_accept_and_persisted_bonus(base):
    from football_manager.services.transfer_negotiation import negotiate,transfer_read_model
    s=deepcopy(base);r=s._world_squads
    player,deal,quote=_affordable_agreed_transfer(s)
    public=next(row for row in transfer_read_model(s)['offers'] if row['id']==deal.deal_id)
    assert public['personal_quote']['wage_range'] and 'weekly_wage_gbp' not in public['personal_quote']
    proposal={'weekly_wage_gbp':max(75,int(quote['weekly_wage_gbp']*.60)),
      'years':quote['years'],'role':quote['role'],'signing_bonus_gbp':0,
      'bonuses':[{'kind':'appearances','threshold':5,'amount_gbp':3000}]}
    reply=negotiate(s,{'action':'personal_offer','deal_id':deal.deal_id,'terms':proposal})
    assert reply['status']=='counter' and 0<reply['patience']<100
    signed=negotiate(s,{'action':'personal_accept','deal_id':deal.deal_id})
    assert signed['status']=='completed'
    assert r.contracts[player.id].club_id==s.home_club.id
    assert r.contract_bonuses[player.id].bonuses[0].amount_gbp==3000
    graph=restore_manager_graph(capture_manager_graph(s))
    assert graph._world_squads.contract_bonuses[player.id]==r.contract_bonuses[player.id]
    assert graph._world_squads.transfer_offers[deal.deal_id].personal_status=='completed'
    graph._world_squads.validate()


def test_goalkeeper_clean_sheet_bonus_counts_verified_stats_once(base):
    from football_manager.domain.season_statistics import SeasonPlayerStatistics
    s=deepcopy(base)
    p=next(player for player in s.home_club.squad.players if player.primary_position.value=='GK')
    q=_quote(s._world_squads,p,s._world_squads.contracts[p.id],s.current_date)
    registry=s._world_squads
    season=registry.season_label
    ledger=registry.statistics
    ledger.start_season(season,s.current_date,complete=True)
    league='ts-fix-03-clean-sheet-test'
    ledger.seasons[season][league]={p.id:SeasonPlayerStatistics(appearances=2,starts=2,minutes=180,clean_sheets=1)}
    contract={'kind':'clean_sheets','threshold':3,'amount_gbp':3000}
    reply=renewal_command(s,{'action':'contract_offer','player_id':p.id,
        'terms':offer(q,q['weekly_wage_gbp'],bonuses=[contract])})
    assert reply['status']=='renewed'
    row=registry.contract_bonuses[p.id]
    assert row.baseline[3]==1
    ledger.seasons[season][league]={p.id:SeasonPlayerStatistics(appearances=6,starts=6,minutes=540,clean_sheets=4)}
    with s._world._atomic():
        review_finances(s._world,date(2026,10,1))
    assert registry.contract_bonuses[p.id].paid==('clean_sheets',)
    with s._world._atomic():
        review_finances(s._world,date(2026,11,1))
    assert registry.contract_bonuses[p.id].paid==('clean_sheets',)
    registry.validate()


def test_clean_sheet_bonus_rejected_for_striker(base):
    from football_manager.services.contract_bargaining import validate_player_bonuses
    striker=next(player for player in base.home_club.squad.players if player.primary_position.value=='ST')
    terms=terms_from_json({'weekly_wage_gbp':10000,'years':3,'role':'rotation',
                           'signing_bonus_gbp':0,
                           'bonuses':[{'kind':'clean_sheets','threshold':3,'amount_gbp':1000}]})
    with pytest.raises(ValueError,match='goalkeepers and defenders'):
        validate_player_bonuses(striker,terms)
