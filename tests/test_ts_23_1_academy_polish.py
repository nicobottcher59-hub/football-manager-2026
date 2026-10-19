"""TS-23.1: academy UI contracts, paid scouting, rival recruitment and save migration."""
from __future__ import annotations

from copy import deepcopy
from datetime import date
from pathlib import Path

import pytest

from football_manager.dev_ui.session import DevelopmentSession
from football_manager.domain.world_runner import _WorldChangeJournal
from football_manager.domain.youth_academy import YouthScoutingCandidate
from football_manager.domain.enums import Position
from football_manager.persistence.session_codec import capture_manager_graph, restore_manager_graph, GRAPH_VERSION
from football_manager.services import youth_academy as svc


@pytest.fixture(scope='module')
def starting():
    return DevelopmentSession()


def test_new_career_starts_with_no_hired_scouts_and_market_is_stable(starting):
    youth=starting._world_squads.youth
    assert not youth.scouts
    assert youth.recruitment_funds == 500_000
    assert svc.scout_market(youth) == svc.scout_market(youth)
    view=svc.youth_read_model(starting)
    assert view['scout_slots']==3 and view['monthly_scout_cost']==0
    assert len(view['market_offers'])>=5
    assert all(x['signing_fee']>0 and x['monthly_wage']>0 for x in view['market_offers'])
    assert not any('potential_budget' in p for p in view['u15'])


def test_hires_charge_budget_and_hiring_more_than_three_is_rejected(starting):
    session=deepcopy(starting);youth=session._world_squads.youth
    offers=svc.scout_market(youth)
    initial=youth.recruitment_funds
    for i in range(3):
        result=svc.youth_command(session,{'action':'hire_scout','offer_id':offers[i]['id']})
        assert result['scout_id']==f'scout-{i+1}'
    assert len(youth.scouts)==3
    assert youth.recruitment_funds == initial - sum(o['signing_fee'] for o in offers[:3])
    with pytest.raises(ValueError,match='slot'):
        svc.youth_command(session,{'action':'hire_scout','offer_id':offers[3]['id']})
    exit_cost=youth.scouts['scout-1'].monthly_wage
    result=svc.youth_command(session,{'action':'fire_scout','scout_id':'scout-1'})
    assert result['termination_fee']==exit_cost and len(youth.scouts)==2
    assert youth.recruitment_spent == initial-youth.recruitment_funds


def test_monthly_wages_are_charged_once_and_never_negative(starting):
    session=deepcopy(starting);youth=session._world_squads.youth
    offer=svc.scout_market(youth)[0]
    svc.youth_command(session,{'action':'hire_scout','offer_id':offer['id']})
    before=youth.recruitment_funds
    svc._pay_scouts(youth,date(2026,9,1))
    assert youth.recruitment_funds == before-offer['monthly_wage']
    svc._pay_scouts(youth,date(2026,9,1))
    assert youth.recruitment_funds == before-offer['monthly_wage']
    youth.recruitment_funds=0
    svc._pay_scouts(youth,date(2026,10,1))
    assert not youth.scouts and youth.recruitment_funds==0


def test_scout_offer_rejects_bad_or_unaffordable_contracts(starting):
    session=deepcopy(starting)
    with pytest.raises(ValueError,match='offer'):
        svc.youth_command(session,{'action':'hire_scout','offer_id':'bogus'})
    session._world_squads.youth.recruitment_funds=1
    with pytest.raises(ValueError,match='Insufficient'):
        svc.youth_command(session,{'action':'hire_scout','offer_id':svc.scout_market(session._world_squads.youth)[0]['id']})


def test_poaching_moves_the_same_id_to_a_rival_and_is_rollback_safe(starting,monkeypatch):
    session=deepcopy(starting)
    registry=session._world_squads;youth=registry.youth
    scout_id='scout-1'
    offer=svc.scout_market(youth)[-1]
    svc.youth_command(session,{'action':'hire_scout','offer_id':offer['id']})
    # Discovered player is unsigned and has had ample time to attract rival bids.
    prev=svc._talent(registry.seed,'scout-world','known-prospect',2,
                     on_date=date(2026,6,1),country='Brazil',position=Position.ST,age=16,source='scout-Brazil')
    youth.candidates[prev.id]=YouthScoutingCandidate(prev,date(2026,6,1),scout_id,90,status='watching')
    original_rng=svc._rng
    class CertainPoaching:
        def random(self):return 0
    monkeypatch.setattr(svc,'_rng',lambda *args:CertainPoaching() if 'poach' in args else original_rng(*args))
    journal=_WorldChangeJournal()
    count=svc._poach_prospects(registry,youth,date(2026,10,1),journal)
    assert count==1 and prev.id not in youth.candidates
    name,when,cid=youth.lost_prospects[prev.id]
    assert name==prev.full_name and when==date(2026,10,1)
    assert registry.clubs[cid].id!=session.home_club.id
    assert youth.academies[cid].u17[prev.id].identity.birth_date==prev.birth_date
    youth.check_unique(registry)
    assert svc._poach_prospects(registry,youth,date(2026,10,1),journal)==0
    journal.rollback()
    assert prev.id in youth.candidates and prev.id not in youth.lost_prospects
    assert prev.id not in youth.academies[cid].u17
    youth.check_unique(registry)


def test_old_v10_save_migrates_scouts_without_retroactive_charges(starting):
    session=deepcopy(starting)
    svc.youth_command(session,{'action':'hire_scout','offer_id':svc.scout_market(session._world_squads.youth)[0]['id']})
    graph=capture_manager_graph(session)
    assert graph['version']==GRAPH_VERSION==17
    previous=deepcopy(graph);previous['version']=10
    for node in previous['nodes']:
        if node.get('class')=='football_manager.domain.youth_academy:YouthSystem':
            for field in ('recruitment_funds','recruitment_spent','last_scout_payroll','lost_prospects'):
                node['fields'].pop(field)
        if node.get('class')=='football_manager.domain.youth_academy:YouthScout':
            for field in ('name','hired_on','contract_until','signing_fee','monthly_wage'):
                node['fields'].pop(field)
    restored=restore_manager_graph(previous)
    youth=restored._world_squads.youth
    assert len(youth.scouts)==1 and youth.scouts['scout-1'].monthly_wage==0
    assert youth.last_scout_payroll==session.current_date.replace(day=1)
    assert youth.recruitment_funds==500_000
    assert restored._world_squads.youth.check_unique(restored._world_squads) is None


def test_frontend_assets_show_real_operations_and_zero_build_requirement():
    root=Path(__file__).resolve().parents[1]
    script=(root/'frontend/portable/youth_academy.js').read_text(encoding='utf-8')
    css=(root/'frontend/portable/youth_academy.css').read_text(encoding='utf-8')
    assert 'data-youth-hire' in script and 'data-youth-action="sign"' in script
    assert 'poaching_risk' in script and 'data-youth-action="watch"' in script
    assert 'Next academy intake' in script and 'Recent results' in script
    assert '.ya-field' in css and '.ya-scout-grid' in css and '.ya-prospect-table' in css
    assert 'window.FMYouthAcademy' in script
