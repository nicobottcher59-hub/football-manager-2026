"""TS-UI-07.01: youth academy visual/contract integration without new save schema."""
from __future__ import annotations
from copy import deepcopy
from datetime import date
from pathlib import Path

import pytest
from football_manager.dev_ui.session import DevelopmentSession
from football_manager.domain.enums import Position
from football_manager.domain.youth_academy import YouthScoutingCandidate
from football_manager.services import youth_academy as ya


@pytest.fixture(scope='module')
def session():
    return DevelopmentSession()


def test_estimated_potential_is_band_not_hidden_saved_pa(session):
    d=ya.youth_read_model(session)
    assert len(d['u15'])==20 and len(d['u17'])==18 and len(d['u21'])==18
    assert all(len(p['potential_range'])==2 for group in ('u15','u17','u21') for p in d[group])
    assert all('potential_budget' not in p and 'potential' not in p for group in ('u15','u17','u21') for p in d[group])
    assert all(p['potential_confidence']=='Approximate' for group in ('u17','u21') for p in d[group])
    d2=ya.youth_read_model(session)
    assert [p['potential_range'] for p in d['u17']]==[p['potential_range'] for p in d2['u17']]
    for p in d['u17']:
        assert p['potential_range'][0] <= p['potential_range'][1]


def test_instant_hiring_disabled_and_rejected_offer_is_atomic(session):
    s=deepcopy(session)
    offer=ya.scout_market(s._world_squads.youth)[0]
    with pytest.raises(ValueError,match='negotiated'):
        ya.youth_command(s,{'action':'hire_scout','offer_id':offer['id']})
    youth=s._world_squads.youth
    before=youth.recruitment_funds
    result=ya.youth_command(s,{'action':'offer_scout','offer_id':offer['id'],
        'scout_id':None,'monthly_wage':100,'years':1,'signing_fee':0})
    assert not result['accepted'] and result['counter_monthly_wage']>100
    assert not youth.scouts and youth.recruitment_funds==before


def test_scout_offer_accepts_contract_charges_budget_and_payroll(session):
    s=deepcopy(session)
    youth=s._world_squads.youth
    offer=ya.scout_market(youth)[0]
    funds=youth.recruitment_funds
    reply=ya.youth_command(s,{'action':'offer_scout','offer_id':offer['id'],'scout_id':None,
        'monthly_wage':offer['monthly_wage']*2,'years':2,'signing_fee':offer['signing_fee']})
    assert reply['accepted'] and reply['kind']=='appointment'
    assert youth.scouts[reply['scout_id']].monthly_wage==offer['monthly_wage']*2
    assert youth.recruitment_funds==funds-offer['signing_fee']
    m=ya.youth_read_model(s)
    assert m['monthly_scout_cost']==offer['monthly_wage']*2
    assert m['scouts'][0]['contract_until']==reply['until']
    before=youth.recruitment_funds
    ya._pay_scouts(youth,date(2026,9,1))
    assert youth.recruitment_funds==before-offer['monthly_wage']*2
    ya._pay_scouts(youth,date(2026,9,1))
    assert youth.recruitment_funds==before-offer['monthly_wage']*2


def test_scout_renewal_is_negotiated_and_keeps_assignments(session):
    s=deepcopy(session);youth=s._world_squads.youth
    o=ya.scout_market(youth)[1]
    hire=ya.youth_command(s,{'action':'offer_scout','offer_id':o['id'],'scout_id':None,
        'monthly_wage':o['monthly_wage']*2,'years':2,'signing_fee':o['signing_fee']})
    sid=hire['scout_id']
    ya.youth_command(s,{'action':'assign_scout','scout_id':sid,'country':'Argentina','position':'ST'})
    prev_date=youth.scouts[sid].next_report
    result=ya.youth_command(s,{'action':'offer_scout','offer_id':None,'scout_id':sid,
        'monthly_wage':o['monthly_wage']*3,'years':1,'signing_fee':0})
    assert result['accepted'] and result['kind']=='renewal'
    assert youth.scouts[sid].next_report==prev_date
    assert youth.scouts[sid].country=='Argentina'
    assert youth.scouts[sid].contract_until.isoformat()==result['until']


def test_invalid_and_unaffordable_scout_offers_do_not_mutate(session):
    s=deepcopy(session);youth=s._world_squads.youth
    o=ya.scout_market(youth)[0]
    baseline=youth.recruitment_funds
    for terms in (dict(monthly_wage=100.5,years=2,signing_fee=0),
                  dict(monthly_wage=3900,years=7,signing_fee=0),
                  dict(monthly_wage=3900,years=2,signing_fee=-1)):
        with pytest.raises(ValueError):
            ya.youth_command(s,dict(action='offer_scout',offer_id=o['id'],scout_id=None,**terms))
    youth.recruitment_funds=100
    with pytest.raises(ValueError,match='budget'):
        ya.youth_command(s,dict(action='offer_scout',offer_id=o['id'],scout_id=None,
                                monthly_wage=4000,years=2,signing_fee=0))
    assert not youth.scouts and baseline>youth.recruitment_funds


def test_scout_followup_is_automatic_without_watch_button(session):
    s=deepcopy(session);registry=s._world_squads;youth=registry.youth
    offer=ya.scout_market(youth)[0]
    response=ya.youth_command(s,{'action':'offer_scout','offer_id':offer['id'],'scout_id':None,
        'monthly_wage':offer['monthly_wage']*2,'years':2,'signing_fee':offer['signing_fee']})
    sid=response['scout_id']
    ya.youth_command(s,{'action':'assign_scout','scout_id':sid,'country':'England','position':'any'})
    prev=ya._talent(registry.seed,'scout-world','test-followup',2,
                    on_date=date(2026,5,1),country='England',position=Position.ST,age=16,source='test')
    youth.candidates[prev.id]=YouthScoutingCandidate(prev,date(2026,5,1),sid,52,0,'available')
    count=ya._month_scout_reports(registry,youth,date(2026,11,21))
    assert count>=1 and youth.candidates[prev.id].confidence==62
    assert youth.candidates[prev.id].status=='available'


def test_scouted_prospect_only_signs_to_u17_and_cannot_bypass_age(session):
    s=deepcopy(session);registry=s._world_squads;youth=registry.youth
    academy=youth.academies[s.home_club.id]
    prev=ya._talent(registry.seed,'scout-world','test-sign',2,
                    on_date=s.current_date,country='France',position=Position.ST,age=16,source='test')
    youth.candidates[prev.id]=YouthScoutingCandidate(prev,s.current_date,'scout-1',70)
    reply=ya.youth_command(s,{'action':'sign','player_id':prev.id})
    assert reply['team']=='u17' and prev.id in academy.u17 and prev.id not in academy.u21
    assert prev.id not in youth.candidates
    overage=ya._talent(registry.seed,'scout-world','test-overage',2,
                    on_date=s.current_date,country='France',position=Position.ST,age=18,source='test')
    youth.candidates[overage.id]=YouthScoutingCandidate(overage,s.current_date,'scout-1',70)
    with pytest.raises(ValueError,match='U17'):
        ya.youth_command(s,{'action':'sign','player_id':overage.id})
    assert overage.id in youth.candidates



def test_manual_watch_and_dismiss_commands_are_retired(session):
    s=deepcopy(session)
    registry=s._world_squads
    candidate=ya._talent(registry.seed,'scout-world','test-no-manual-tracking',2,
                         on_date=s.current_date,country='England',position=Position.ST,age=16,source='test')
    registry.youth.candidates[candidate.id]=YouthScoutingCandidate(
        candidate,s.current_date,'scout-1',65)
    for action in ('watch','dismiss'):
        with pytest.raises(ValueError,match='automatically'):
            ya.youth_command(s,{'action':action,'player_id':candidate.id})
    assert registry.youth.candidates[candidate.id].status=='available'


def test_frontend_uses_shared_identity_one_recruitment_action_and_no_staff_photos():
    base=Path(__file__).resolve().parents[1]
    js=(base/'frontend/portable/youth_academy.js').read_text()
    css=(base/'frontend/portable/youth_academy.css').read_text()
    assert 'FMClubIdentity' in js and 'Sign to U17' in js
    assert 'data-youth-negotiate-offer' in js and 'offer_scout' in js
    assert 'data-youth-action="watch"' not in js and 'data-youth-action="dismiss"' not in js
    assert '<span class="ya-scout-person"' in js and 'portrait(scout' not in js
    assert 'assets/youth/academy-training-ground.webp' in css
    assert 'var(--ui-club-rgb' in css
    assert (base/'frontend/portable/assets/youth/academy-training-ground.webp').is_file()



def test_sqlite_manager_section_and_graph_versions_are_aligned():
    from football_manager.persistence.manager_career import MANAGER_STATE_VERSION
    from football_manager.persistence.session_codec import GRAPH_VERSION
    assert MANAGER_STATE_VERSION == GRAPH_VERSION == 26
