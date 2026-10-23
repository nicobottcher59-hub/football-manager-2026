"""TS-24.1 market valuation: scale, uncertainty, symmetry and full-save clock."""
from __future__ import annotations

from copy import deepcopy
from dataclasses import replace
from datetime import date

import pytest

from football_manager.dev_ui.session import DevelopmentSession
from football_manager.domain.market_valuation import (
    ANCHORS_GBP, MarketQuote, SaleContext, asking_band, base_market_value,
    medical_adjustment, perceived_upside, valuation_amount,
    market_value_for_player,
)
from football_manager.persistence.session_codec import (
    capture_manager_graph, restore_manager_graph, GRAPH_VERSION,
)
from football_manager.persistence.manager_career import (
    validate_manager_session, save_manager_career, load_manager_career,
)
from football_manager.persistence.sqlite_repository import SQLiteSaveRepository
from football_manager.services.market_valuation import player_market_view
from football_manager.services.player_development import advance_world_development
from football_manager.ui_shell.models import squad_read_model
from football_manager.ui_shell.club_profiles import club_profile_read_model
from football_manager.ui_shell.world_squads import club_squad_read_model


@pytest.fixture(scope='module')
def initial():
    return DevelopmentSession()


@pytest.mark.parametrize('ovr,price', ANCHORS_GBP)
def test_reference_scale_anchor_prices(ovr, price):
    assert base_market_value(ovr) == pytest.approx(price)
    assert valuation_amount(ovr=ovr, age=27) == price


def test_interpolation_smooth_and_strictly_increasing():
    values = [base_market_value(ovr/10) for ovr in range(350, 981)]
    assert all(a < b for a,b in zip(values, values[1:]))
    assert base_market_value(79) < 24_000_000 < base_market_value(81)


@pytest.mark.parametrize('age,ovr,upside,low,high', [
    (19,72,0,4_000_000,7_000_000),
    (19,72,15,15_000_000,24_000_000),
    (19,72,27,30_000_000,45_000_000),
    (16,60,15,2_000_000,5_000_000),
    (16,60,30,6_000_000,10_000_000),
    (16,67,27,18_000_000,28_000_000),
    (20,75,0,9_000_000,13_000_000),
    (21,80,12,60_000_000,80_000_000),
    (27,80,0,24_000_000,24_000_000),
    (34,80,0,6_000_000,6_000_000),
    (19,90,7,215_000_000,265_000_000),
])
def test_many_age_potential_scenarios(age,ovr,upside,low,high):
    amount=valuation_amount(ovr=ovr,age=age,perceived_growth=upside)
    assert low <= amount <= high


def test_younger_great_prospects_expensive_but_not_automatic():
    kwargs=dict(ovr=72,age=19)
    low=valuation_amount(**kwargs, perceived_growth=0)
    high=valuation_amount(**kwargs, perceived_growth=15)
    generational=valuation_amount(**kwargs, perceived_growth=27)
    assert generational >= high * 1.8
    assert high >= low * 2.8
    # An adult with the same OVR should not receive youth premiums.
    assert valuation_amount(ovr=72, age=27, perceived_growth=27) == valuation_amount(ovr=72, age=27)


def test_goalkeepers_decline_differently_and_medical_history_matters():
    outfield = valuation_amount(ovr=85, age=35)
    keeper = valuation_amount(ovr=85, age=35, goalkeeper=True)
    assert 1.75 < keeper / outfield < 2
    assert medical_adjustment(burden=0,serious_injuries=0) == 1
    assert medical_adjustment(burden=.9,serious_injuries=3) < .8
    assert valuation_amount(ovr=85,age=35,medical_factor=.8) < outfield


def test_sustained_form_bounded_and_fatigue_not_an_input(initial):
    weak=valuation_amount(ovr=80,age=27,form=0)
    strong=valuation_amount(ovr=80,age=27,form=100)
    assert strong <= 27_000_000 and weak >= 20_000_000
    p=deepcopy(initial.home_club.squad.players[0])
    original=market_value_for_player(p, initial.current_date, 123)
    p.state.fatigue=100;p.state.fitness=1
    assert market_value_for_player(p, initial.current_date,123)==original
    p.state.form=100
    assert market_value_for_player(p, initial.current_date,123).value_gbp>original.value_gbp


def test_perceived_potential_stable_but_not_exact_pa():
    samples=[perceived_upside(123,'player-a',room) for room in (3,12,25)]
    assert samples == [perceived_upside(123,'player-a',room) for room in (3,12,25)]
    assert samples[0] < samples[1] < samples[2]
    assert samples[1] != 12
    assert perceived_upside(123,'player-b',12)!=samples[1]


def test_sale_scenarios_are_symmetric_and_contract_aware():
    q=MarketQuote('abc',24_000_000,date(2026,8,1))
    normal=asking_band(q,SaleContext())
    long_key=asking_band(q,SaleContext(contract_months=60,importance='key'))
    short=asking_band(q,SaleContext(contract_months=6))
    rival=asking_band(q,SaleContext(contract_months=36,direct_rival=True))
    urgent=asking_band(q,SaleContext(contract_months=36,urgency='urgent',transfer_listed=True,player_wants_exit=True))
    contested=asking_band(q,SaleContext(contract_months=36,other_bidders=3))
    assert normal.contract_data_available is False
    assert long_key.low_gbp > normal.low_gbp
    assert short.market_value_gbp < q.value_gbp and short.high_gbp < normal.high_gbp
    assert rival.low_gbp > normal.low_gbp
    assert urgent.high_gbp < normal.low_gbp
    assert contested.high_gbp > normal.high_gbp
    assert asking_band(q,SaleContext()) == asking_band(q,SaleContext())
    assert asking_band(q,SaleContext(contract_months=0)).low_gbp == 0


def test_invalid_values_are_rejected():
    with pytest.raises(ValueError): base_market_value(float('nan'))
    with pytest.raises(ValueError): valuation_amount(ovr=80,age=18, medical_factor=.5)
    with pytest.raises(ValueError): asking_band(MarketQuote('x',24_000_000,date(2026,8,1)), SaleContext(contract_months=-1))


def test_all_clubs_quoted_with_same_policy_and_get_is_readonly(initial):
    s=deepcopy(initial)
    registry=s._world_squads
    count=sum(len(c.squad) for c in registry.clubs.values())
    youth_count=sum(len(a.u17)+len(a.u21) for a in registry.youth.academies.values())
    assert count==2024
    assert len(registry.market_values)==count+youth_count
    original=dict(registry.market_values)
    own=squad_read_model(s)
    assert own['roster_capabilities']['market_values'] is True
    assert all(p['market_value_gbp']>0 and p['market_value'].startswith('£') and p['contract'] is not None for p in own['roster'])
    other=next(cid for cid in registry.clubs if cid!=s.home_club.id)
    rival=club_profile_read_model(s,other)
    assert all(p['market_value_gbp']>0 for p in rival['roster'])
    same=club_squad_read_model(s,other)
    assert {p['id']:p['market_value_gbp'] for p in rival['roster']}=={p['id']:p['market_value_gbp'] for p in same['players']}
    assert registry.market_values==original


def test_monthly_valuation_stable_during_match_form_changes_and_idempotent(initial):
    s=deepcopy(initial)
    r=s._world_squads
    p=s.home_club.squad.players[0]
    q=r.market_values[p.id]
    p.state.form=95
    assert player_market_view(r,p,s.current_date)['market_value_gbp']==q.value_gbp
    assert r.market_review_on == date(2026,8,1)
    advance_world_development(s._world,date(2026,9,1))
    after=r.market_values[p.id]
    assert r.market_review_on == date(2026,9,1) and after.as_of == date(2026,9,1)
    assert after.value_gbp > q.value_gbp
    snapshot=dict(r.market_values)
    assert advance_world_development(s._world,date(2026,9,1)) == 0
    assert r.market_values == snapshot


def test_monthly_rollback_on_failure(initial, monkeypatch):
    s=deepcopy(initial);r=s._world_squads
    original_quotes=dict(r.market_values); original_clock=r.market_review_on
    from football_manager.services import market_valuation
    original_quote_fn=market_valuation.market_value_for_player
    counter={'n':0}
    def explode(*args,**kwargs):
        counter['n']+=1
        if counter['n']==4: raise RuntimeError('fail during price update')
        return original_quote_fn(*args,**kwargs)
    monkeypatch.setattr(market_valuation,'market_value_for_player',explode)
    with pytest.raises(RuntimeError,match='fail during'):
        advance_world_development(s._world,date(2026,9,1))
    assert r.market_values==original_quotes and r.market_review_on==original_clock


def test_v11_migration_no_player_mutations_and_quotes_persist(initial):
    s=deepcopy(initial)
    before={(p.id):(p.attributes,p.development.potential,p.state.form)
            for c in s._world_squads.clubs.values() for p in c.squad.players}
    graph=capture_manager_graph(s)
    assert graph['version']==GRAPH_VERSION==27
    legacy=deepcopy(graph);legacy['version']=11
    node=next(n for n in legacy['nodes'] if n.get('class')=='football_manager.domain.football_world:FootballWorld')
    del node['fields']['market_review_on'];del node['fields']['market_values']
    migrated=restore_manager_graph(legacy)
    r=migrated._world_squads
    assert r.market_review_on==s.current_date.replace(day=1)
    assert len(r.market_values)==2024+sum(len(a.u17)+len(a.u21) for a in r.youth.academies.values())
    assert before=={p.id:(p.attributes,p.development.potential,p.state.form)
                   for c in r.clubs.values() for p in c.squad.players}
    loaded=restore_manager_graph(capture_manager_graph(migrated))
    assert loaded._world_squads.market_values==r.market_values
    validate_manager_session(loaded)


def test_sqlite_full_save_roundtrip(initial,tmp_path):
    s=deepcopy(initial);repo=SQLiteSaveRepository(tmp_path/'market.sqlite3')
    save_manager_career(repo,slot_id='test',display_name='Market',session=s,expected_revision=0)
    loaded=load_manager_career(repo,'test').session
    assert loaded._world_squads.market_values==s._world_squads.market_values
    assert loaded._world_squads.market_review_on==s._world_squads.market_review_on
    assert capture_manager_graph(loaded)['version']==GRAPH_VERSION==27


def test_ceiling_on_extreme_market_scenario():
    assert valuation_amount(ovr=100, age=16, perceived_growth=34) <= 500_000_000


def test_expired_contract_and_flags_are_not_accepted_as_regular_offers():
    with pytest.raises(ValueError):
        SaleContext(direct_rival=1).validate()
    q=MarketQuote('p',24_000_000,date(2026,8,1))
    expiring=asking_band(q,SaleContext(contract_months=0))
    assert expiring.low_gbp==expiring.high_gbp==0


def test_position_demand_is_small_and_does_not_override_quality():
    striker=valuation_amount(age=27, ovr=80, position_market_factor=1.06)
    fullback=valuation_amount(age=27, ovr=80, position_market_factor=.97)
    assert striker > fullback
    assert striker/fullback < 1.15
