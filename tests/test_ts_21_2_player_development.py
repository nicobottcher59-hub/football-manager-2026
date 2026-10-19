"""TS-21.2 mandatory tests: Python/pytest only; no Node, browser or network.

Synthetic fixtures never access real save slots. Long cohort/world checks are
separate tools so this focused suite is practical on Windows.
"""
from __future__ import annotations

from copy import deepcopy
from dataclasses import asdict, fields, replace
from datetime import date, datetime, timedelta
from pathlib import Path
from threading import Thread
from urllib.request import Request, urlopen
from urllib.error import HTTPError
import gzip
import json

import pytest

from football_manager.domain.attributes import (
    PlayerAttributes, TechnicalAttributes, MentalAttributes, PhysicalAttributes, GoalkeepingAttributes,
)
from football_manager.domain.enums import Foot, Position
from football_manager.domain.player import Player, PlayerIdentity
from football_manager.domain.positional_familiarity import PositionalFamiliarity
from football_manager.domain.personality import Personality
from football_manager.domain.player_development import (
    DevelopmentEnvironment, DevelopmentExposure, PlayerDevelopment, DevelopmentReview,
    initialize_development, current_ability, reference_overall, next_month,
    ability_weights, attribute_values, review_player, growth_budget, add_match_exposure,
)
from football_manager.services.player_development import (
    advance_world_development, initialize_world_development, development_read_model,
    set_development_focus,
)
from football_manager.dev_ui.session import DevelopmentSession
from football_manager.domain.club import Club
from football_manager.domain.football_world import FootballWorld
from football_manager.domain.world_runner import WorldSeasonRunner
from football_manager.persistence.session_codec import capture_manager_graph, restore_manager_graph, GRAPH_VERSION
from football_manager.persistence import SQLiteSaveRepository, save_manager_career, load_manager_career, SaveIntegrityError
from football_manager.persistence.manager_career import validate_manager_session
from football_manager.services.world_matches import record_world_usage
from football_manager.ui_shell.player_profiles import player_profile_read_model
from football_manager.ui_shell.models import squad_read_model
from football_manager.ui_shell.club_profiles import club_profile_read_model
from football_manager.data.player_loader import load_player

START = date(2026, 8, 1)
ENV = DevelopmentEnvironment()


def make_player(pid='synthetic', *, age=16, ability=60, position=Position.CM, potential=90,
                rate=1.0, peak=21, end=29, initialize=True):
    def group(typ):
        return typ(**{f.name: ability for f in fields(typ)})
    player = Player(PlayerIdentity(pid, 'Test', 'Player', date(2026-age, 1, 1), 'Test Country', Foot.RIGHT),
        PlayerAttributes(group(TechnicalAttributes), group(MentalAttributes), group(PhysicalAttributes),
                         group(GoalkeepingAttributes) if position is Position.GK else None),
        PositionalFamiliarity({position: 100}), position, position,
        personality=Personality(professionalism=80, ambition=75))
    if initialize:
        initialize_development(player, START, 42, potential=potential,
            growth_peak_age=peak, growth_end_age=end, growth_rate=rate)
    return player


def play_exposure(player, appearances=3, minutes=80):
    from football_manager.domain.roles import default_role_for_position
    role=default_role_for_position(player.original_position).role_id
    for _ in range(appearances):
        player.development=add_match_exposure(player, minutes=minutes, rating=7.0,
                                             role_minutes={role: minutes})


def months(player, count, *, appearances=3, minutes=80, environment=ENV):
    for _ in range(count):
        play_exposure(player, appearances, minutes)
        attrs, dev=review_player(player, next_month(player.development.last_review), environment)
        player.attributes, player.development=attrs, dev
        dev.validate(player)
    return player


@pytest.fixture(scope='module')
def initial():
    return DevelopmentSession()


@pytest.fixture(scope='module')
def played(initial):
    s=deepcopy(initial); fid=s._active_match.fixture.fixture_id
    lineups=(s.home_lineup,s.away_lineup)
    result=s.quick_simulate()
    return s,fid,result,lineups


@pytest.mark.parametrize('on_date,expected', [(date(2026,2,27),17),(date(2026,2,28),17),(date(2026,3,1),18),(date(2028,2,28),19),(date(2028,2,29),20)])
def test_leap_birthday_is_date_based(on_date,expected):
    p=make_player(initialize=False);p.identity=replace(p.identity,birth_date=date(2008,2,29))
    # Existing age_on policy: leap-day births age on March 1 in non-leap years.
    assert p.age_on(on_date)==expected


@pytest.mark.parametrize('birthday,today,age',[(date(2010,10,16),date(2026,10,15),15),(date(2010,10,16),date(2026,10,16),16),(date(2010,10,16),date(2027,1,1),16)])
def test_birthdays_not_season_rollover(birthday,today,age):
    p=make_player(initialize=False);p.identity=replace(p.identity,birth_date=birthday)
    assert p.age_on(today)==age


@pytest.mark.parametrize('bad',[None,'2000-01-01',datetime(2000,1,1)])
def test_identity_requires_real_date(bad):
    with pytest.raises(ValueError):
        PlayerIdentity('id','Test','Name',bad,'Test',Foot.RIGHT)


@pytest.mark.parametrize('position',list(Position))
def test_ca_attribute_budget_all_positions_without_fatigue_or_assignment(position):
    p=make_player(position=position)
    before=current_ability(p);pa=p.development.potential
    p.state.fitness=10;p.state.morale=0;p.state.form=0
    p.primary_position=Position.ST if position is not Position.ST else Position.CB
    assert current_ability(p)==before and p.development.potential==pa
    weights=ability_weights(position)
    assert sum(w for _,w in weights)==pytest.approx(1)
    assert all(w>0 for _,w in weights)
    assert current_ability(p)==pytest.approx(60)


def test_initialization_preserves_attributes_state_and_date():
    p=make_player(initialize=False)
    identity,attrs,state=deepcopy((p.identity,p.attributes,p.state))
    initialize_development(p,START,100)
    assert (p.identity,p.attributes,p.state)==(identity,attrs,state)
    first=p.development
    initialize_development(p,date(2027,1,1),9999,potential=100)
    assert p.development is first


def test_profiles_deterministic_independent_of_order_and_club():
    a=[make_player(str(i),initialize=False) for i in range(30)]
    b=deepcopy(a)[::-1]
    for p in a+b:initialize_development(p,START,765)
    assert {p.id:p.development for p in a}=={p.id:p.development for p in b}
    assert len({round(p.development.potential,2) for p in a})>20


@pytest.mark.parametrize('kwargs',[{'potential':59},{'potential':101},{'potential':float('nan')},{'growth_rate':0},{'growth_peak_age':10},{'growth_end_age':20},{'growth_rate':True}])
def test_bad_import_is_rejected_without_partial_mutation(kwargs):
    p=make_player(initialize=False);original=deepcopy(p)
    with pytest.raises(ValueError):initialize_development(p,START,0,**kwargs)
    assert p==original


@pytest.mark.parametrize('ability,potential',[(40,48),(48,70),(60,88),(80,81),(65,98),(89,99)])
def test_limited_promising_early_developed_and_prodigious_players(ability,potential):
    p=make_player(ability=ability,potential=potential)
    start=current_ability(p)
    months(p,12)
    assert start<=current_ability(p)<=potential+1e-8
    assert p.development.potential==potential


def test_monthly_progress_reaches_real_attributes_not_act_only():
    p=make_player();before=attribute_values(p.attributes)
    months(p,12)
    after=attribute_values(p.attributes)
    assert current_ability(p)>60 and p.overall_rating>60
    assert any(after[k]>v for k,v in before.items())
    assert len({after[k]-v for k,v in before.items()})>1
    assert after['physical.natural_fitness']==before['physical.natural_fitness']
    assert after['mental.aggression']==before['mental.aggression']


def test_fractional_gains_survive_small_first_month():
    p=make_player();p.development=replace(p.development,started_on=date(2026,8,31),last_review=date(2026,8,31))
    attrs,dev=review_player(p,date(2026,9,1),ENV)
    assert attrs==p.attributes and dev.residuals
    assert not dev.last_changes and dev.history[-1].reason=='consolidating'


def test_potential_is_hard_budget_including_residuals():
    p=make_player(potential=60.03)
    months(p,48)
    budget=current_ability(p)+sum(dict(ability_weights(p.development.reference_position))[k]*v for k,v in p.development.residuals.items())
    assert budget<=60.03+1e-8


@pytest.mark.parametrize('focus',['balanced','technical','physical','mental'])
def test_focus_is_bounded_and_does_not_change_potential(focus):
    p=make_player();p.development=replace(p.development,focus=focus)
    months(p,8)
    assert p.development.potential==90 and max(attribute_values(p.attributes).values())<=100
    assert p.attributes.goalkeeping is None


def test_focused_training_changes_distribution_not_free_ca():
    tech=make_player();mental=deepcopy(tech)
    tech.development=replace(tech.development,focus='technical')
    mental.development=replace(mental.development,focus='mental')
    months(tech,24);months(mental,24)
    ta=attribute_values(tech.attributes);ma=attribute_values(mental.attributes)
    assert sum(v for k,v in ta.items() if k.startswith('technical.'))>sum(v for k,v in ma.items() if k.startswith('technical.'))
    assert sum(v for k,v in ma.items() if k.startswith('mental.'))>sum(v for k,v in ta.items() if k.startswith('mental.'))
    assert abs(current_ability(tech)-current_ability(mental))<1.5


@pytest.mark.parametrize('age',[15,16,19,23])
def test_overplaying_is_not_optimal(age):
    normal=make_player(age=age);over=deepcopy(normal)
    play_exposure(normal,2 if age<18 else 3)
    play_exposure(over,8,90)
    assert growth_budget(normal,date(2026,9,1),ENV)[0]>growth_budget(over,date(2026,9,1),ENV)[0]


def test_youth_can_develop_from_training_without_first_team_minutes():
    p=make_player(age=15);months(p,12,appearances=0)
    assert current_ability(p)>60


def test_mentoring_personality_and_staff_have_bounded_effects():
    p=make_player();play_exposure(p)
    no_support=growth_budget(p,date(2026,9,1),ENV)[0]
    supported=growth_budget(p,date(2026,9,1),ENV,mentoring=1)[0]
    assert no_support<supported<=no_support*1.051
    weak=deepcopy(p);weak.personality=replace(weak.personality,professionalism=15,ambition=15)
    assert growth_budget(weak,date(2026,9,1),ENV)[0]<no_support
    assert growth_budget(p,date(2026,9,1),DevelopmentEnvironment(90,90))[0]>no_support
    assert growth_budget(p,date(2026,9,1),DevelopmentEnvironment(20,20))[0]<no_support


def test_fatigue_is_not_attribute_decline():
    p=make_player(age=34,end=30);initial=p.attributes;p.state.fatigue=99;p.state.fitness=1
    months(p,2,appearances=0)
    assert p.attributes==initial and p.development.history[-1].reason=='mature'


def test_current_injury_pauses_development_without_pa_damage():
    p=make_player();p.state.injury='test injury';attrs=p.attributes
    months(p,3,appearances=0)
    assert p.attributes==attrs and p.development.potential==90
    assert not p.development.residuals and p.development.history[-1].reason=='injured'
    p.state.injury=None;months(p,6)
    assert p.attributes!=attrs


def test_no_growth_before_age_fifteen():
    p=make_player(age=13);months(p,4)
    assert current_ability(p)==pytest.approx(60)


def test_incomplete_careers_and_distinct_maturation_windows():
    a=make_player(peak=18,end=25);b=make_player(peak=25,end=33)
    for p in (a,b):months(p,14*12,appearances=0)
    assert 60<current_ability(a)<90 and 60<current_ability(b)<90
    assert current_ability(a)!=current_ability(b)
    assert len(a.development.history)==12
    assert len(a.development.annual_history)==14


def test_attribute_cap_and_rare_single_remaining_attribute():
    p=make_player(ability=99,potential=100,rate=2.4)
    p.attributes=replace(p.attributes,physical=replace(p.attributes.physical,pace=1))
    # Explicit synthetic extreme validates per-attribute bounds, not a save migration.
    p.development=replace(p.development,baseline_ability=current_ability(p))
    months(p,3)
    assert max(attribute_values(p.attributes).values())<=100
    assert p.attributes.physical.pace<=10


@pytest.mark.parametrize('bad',[{'minutes':True},{'appearances':1,'minutes':121},{'rating_total':float('inf')},{'role_minutes':{'made_up':20}},{'challenge_minutes':1}])
def test_exposure_validation(bad):
    with pytest.raises((ValueError,KeyError)):DevelopmentExposure(**bad).validate()


def test_unused_bench_is_not_exposure():
    p=make_player();before=p.development
    assert add_match_exposure(p,minutes=0,rating=6,role_minutes={}) is before


def test_matches_only_record_exposure_not_instant_attribute_boost(played):
    s,fid,r,lineups=played
    for l in lineups:
        if l.club_id not in s._world_squads.clubs:continue
        for p in l.starting_players:
            assert p.development.exposure.minutes>=next(x.minutes for x in r.player_statistics if x.player_id==p.id)
            assert p.development.last_review==p.development.started_on
            assert not p.development.history


def test_duplicate_fixture_cannot_duplicate_development(played):
    s,fid,r,ls=played
    before={p.id:p.development for c in s._world_squads.clubs.values() for p in c.squad.players}
    with pytest.raises(ValueError):record_world_usage(s._world,fid,r,ls)
    assert before=={p.id:p.development for c in s._world_squads.clubs.values() for p in c.squad.players}


def simple_world(n=6):
    world=WorldSeasonRunner(seed=51)
    registry=FootballWorld(51,START,'2026/27')
    for c in range(2):
        club=Club(f'country-x-{c}',f'Example {c}',f'X{c}','Unrelated Country')
        for i in range(n):club.squad.add(make_player(f'{c}-{i}'))
        registry.clubs[club.id]=club
    world.football_world=registry
    initialize_world_development(registry,START)
    return world


def test_shared_rules_work_without_english_leagues_or_tier_data():
    world=simple_world()
    assert advance_world_development(world,date(2026,11,1))==36
    assert all(len(p.development.history)==3 for c in world.football_world.clubs.values() for p in c.squad.players)


def test_no_match_months_and_long_skip_equal_month_by_month():
    a=simple_world();b=deepcopy(a)
    advance_world_development(a,date(2027,2,1))
    for month in (9,10,11,12):advance_world_development(b,date(2026,month,1))
    for month in (1,2):advance_world_development(b,date(2027,month,1))
    assert a.football_world==b.football_world
    assert advance_world_development(a,date(2027,2,1))==0


def test_empty_calendar_still_advances_every_player():
    w=simple_world();w.advance_until(date(2026,10,1))
    assert all(len(p.development.history)==2 for c in w.football_world.clubs.values() for p in c.squad.players)


def test_monthly_failure_rolls_back_attributes_profiles_and_clock(monkeypatch):
    w=simple_world();before=deepcopy(w.football_world)
    import football_manager.services.player_development as service
    actual=service.review_career;count=0
    def broken(*args,**kwargs):
        nonlocal count
        count+=1
        if count==4:raise RuntimeError('injected review failure')
        return actual(*args,**kwargs)
    monkeypatch.setattr(service,'review_career',broken)
    with pytest.raises(RuntimeError):advance_world_development(w,date(2026,11,1))
    assert w.football_world==before and w._active_journal is None


def test_composed_transaction_restores_prior_months():
    w=simple_world();before=deepcopy(w.football_world)
    with pytest.raises(RuntimeError):
        with w.transaction():
            advance_world_development(w,date(2026,9,1));advance_world_development(w,date(2026,10,1))
            raise RuntimeError('later transaction failure')
    assert w.football_world==before


def test_world_bootstrap_has_2024_profiles_and_birthdays(initial):
    r=initial._world_squads
    players=[p for c in r.clubs.values() for p in c.squad.players]
    assert len(players)==2024 and len({p.id for p in players})==2024
    assert all(isinstance(p.development,PlayerDevelopment) for p in players)
    assert all(type(p.identity.birth_date) is date and current_ability(p)<=p.development.potential for p in players)
    assert len({p.development.potential for p in players})>1900
    assert set(r.development_environments)==set(r.clubs)
    assert len(set(r.development_environments.values()))>1  # Saved club-support estimates, not league multipliers.


def test_reads_have_no_side_effect_or_hidden_pa(initial):
    before=capture_manager_graph(initial)
    own=squad_read_model(initial)
    assert all('birth_date' in p for p in own['roster'])
    p=initial.home_club.squad.players[0]
    data=player_profile_read_model(initial,initial.home_club.id,p.id)
    d=data['graphics']['evolution']
    assert d['registered'] and d['birth_date']==p.identity.birth_date.isoformat()
    forbidden={'potential','ability','growth_rate','growth_peak_age','growth_end_age','seed','residuals'}
    def keys(value):
        if isinstance(value,dict):
            return set(value).union(*(keys(v) for v in value.values()))
        if isinstance(value,list):return set().union(*(keys(v) for v in value))
        return set()
    assert not forbidden & keys(data)
    other=next(cid for cid in initial._world_squads.clubs if cid!=initial.home_club.id)
    assert all('birth_date' in p for p in club_profile_read_model(initial,other)['roster'])
    assert capture_manager_graph(initial)==before


def test_real_history_in_profile_excludes_ca_and_fatigue():
    p=make_player();months(p,3)
    before=development_read_model(p,date(2026,11,5))
    p.state.fitness=1;p.state.form=0
    after=development_read_model(p,date(2026,11,5))
    assert before==after and len(after['history'])==3
    assert all('ability' not in item for item in after['history'])


def test_focus_cannot_edit_rival_or_potential(initial):
    s=deepcopy(initial);p=s.home_club.squad.players[0];pa=p.development.potential
    result=set_development_focus(s,p.id,'physical')
    assert result['save_required'] and p.development.focus=='physical' and p.development.potential==pa
    other=next(c for c in s._world_squads.clubs.values() if c.id!=s.home_club.id)
    with pytest.raises(ValueError):set_development_focus(s,other.squad.players[0].id,'mental')
    with pytest.raises(ValueError):set_development_focus(s,p.id,'potential')


def test_v7_roundtrip_preserves_exposure_focus_and_shared_players(played,tmp_path):
    s=deepcopy(played[0]);p=s.home_club.squad.players[0];set_development_focus(s,p.id,'mental')
    repo=SQLiteSaveRepository(tmp_path/'v7.sqlite3')
    save_manager_career(repo,slot_id='v7',display_name='Synthetic',session=s,expected_revision=0)
    loaded=load_manager_career(repo,'v7').session
    assert GRAPH_VERSION==16
    assert loaded._world_squads==s._world_squads
    assert loaded.home_club.squad.get(p.id) is loaded._world_squads.clubs[s.home_club.id].squad.get(p.id)
    assert loaded.home_lineup.starting_players[0] is loaded.home_club.squad.get(loaded.home_lineup.starting_players[0].id)
    s.continue_to_next_match();loaded.continue_to_next_match()
    assert s.current_date==loaded.current_date and s._world_squads==loaded._world_squads


def test_true_v6_migration_preserves_all_attributes_dates_results_and_statistics():
    graph=json.loads(gzip.decompress(Path('tests/fixtures/ts212_manager_v6.json.gz').read_bytes()))
    assert graph['version']==6
    s=restore_manager_graph(graph)
    validate_manager_session(s)
    # The original dataclass nodes are kept byte-for-byte in the migrated graph.
    after=capture_manager_graph(s)
    def nodes(g,classes):
        return [n for n in g['nodes'] if n.get('type')=='object' and n.get('class') in classes]
    # Attribute groups contain primitives only; compare without graph ref renumbering.
    classes={'football_manager.domain.attributes:'+name for name in ('TechnicalAttributes','MentalAttributes','PhysicalAttributes','GoalkeepingAttributes')}
    assert len(nodes(graph,classes)) >= 2024*3
    # Later academy versions add new players. Require all *legacy* attribute
    # nodes to survive unchanged without forbidding new youth attributes.
    from collections import Counter
    old_attrs=Counter(json.dumps(n,sort_keys=True) for n in nodes(graph,classes))
    new_attrs=Counter(json.dumps(n,sort_keys=True) for n in nodes(after,classes))
    assert all(new_attrs[node] >= count for node,count in old_attrs.items())
    def preserved_player_records(g):
        def resolve(value):
            if not isinstance(value,dict) or '$ref' not in value:
                return value
            node=g['nodes'][value['$ref']]
            if node['type'] in ('date','datetime','enum'):
                return (node.get('class'),node['value'])
            if node['type']=='object':
                return {k:resolve(v) for k,v in node['fields'].items()}
            if node['type']=='dict':
                return sorted((str(resolve(k)),resolve(v)) for k,v in node['items'])
            if node['type'] in ('list','tuple','set','frozenset'):
                return [resolve(v) for v in node['items']]
            raise AssertionError('Unexpected player record node')
        result={}
        for node in nodes(g,{'football_manager.domain.player:Player'}):
            identity=resolve(node['fields']['identity'])
            result[identity['player_id']]={key:resolve(node['fields'][key]) for key in (
                'identity','attributes','original_position','primary_position','state',
                'positional_familiarity','tactical_familiarity','personality')}
        return result
    before_players=preserved_player_records(graph)
    assert len(before_players)>=2024
    # TS-23 introduces additional academy players; the legacy players must
    # still match byte-for-byte and may not be edited by migration.
    new_players=preserved_player_records(after)
    assert all(new_players[pid]==record for pid,record in before_players.items())
    assert s.match_played and s._world.results
    assert all(p.development.started_on==s.current_date and p.development.exposure.minutes==0 and not p.development.history
               for c in s._world_squads.clubs.values() for p in c.squad.players)
    restored=restore_manager_graph(capture_manager_graph(s))
    assert restored._world_squads==s._world_squads


@pytest.mark.parametrize('field,value',[('potential',-1),('growth_rate',float('inf')),('focus','unknown'),('policy_version',99)])
def test_corrupted_profile_rejected_at_save(initial,tmp_path,field,value):
    s=deepcopy(initial);p=s.home_club.squad.players[0]
    p.development=replace(p.development,**{field:value})
    repo=SQLiteSaveRepository(tmp_path/'bad.sqlite3')
    with pytest.raises(SaveIntegrityError):save_manager_career(repo,slot_id='bad',display_name='Bad',session=s,expected_revision=0)
    assert not repo.list_slots()


def test_imported_real_or_newgen_data_uses_same_model_without_attribute_rewrites():
    p=make_player(initialize=False);raw={
        'identity':{'id':p.id,'first_name':'Imported','last_name':'Player','birth_date':'2010-01-01','nationality':'Argentina','dominant_foot':'right'},
        'attributes':asdict(p.attributes),'positions':{'CM':100},'original_position':'CM','primary_position':'CM',
        'development':{'as_of':'2026-08-01','potential':97,'growth_rate':1.6,'growth_peak_age':20,'growth_end_age':29}}
    loaded=load_player(raw)
    assert loaded.attributes==p.attributes and loaded.development.potential==97
    assert loaded.identity.birth_date==date(2010,1,1)
    months(loaded,6)
    assert loaded.development.potential==97 and current_ability(loaded)>60


@pytest.mark.parametrize('bad',[{}, {'as_of':'bad'}, {'as_of':'2026-08-01','cheat':True}])
def test_import_requires_known_fields_and_explicit_game_date(bad):
    p=make_player(initialize=False);raw={'identity':{'id':'test','first_name':'T','last_name':'P','birth_date':'2010-01-01','nationality':'X','dominant_foot':'right'},
        'attributes':asdict(p.attributes),'positions':{'CM':100},'original_position':'CM','primary_position':'CM','development':bad}
    with pytest.raises(ValueError):load_player(raw)


def test_http_focus_authority_and_profile_response(initial,tmp_path):
    from football_manager.ui_shell.server import create_server
    from football_manager.ui_shell.runtime import UIRuntime
    # Server factory owns a disposable session; publish our clone explicitly.
    server=create_server(port=0,session=deepcopy(initial),save_repository=SQLiteSaveRepository(tmp_path/'http.sqlite3'))
    t=Thread(target=server.serve_forever,daemon=True);t.start()
    base=f'http://127.0.0.1:{server.server_port}'
    p=server.RequestHandlerClass.runtime.session.home_club.squad.players[0]
    try:
        data=json.dumps({'player_id':p.id,'focus':'technical'}).encode()
        req=Request(base+'/api/development/focus',data=data,headers={'Content-Type':'application/json'},method='POST')
        with urlopen(req) as r:answer=json.load(r)
        assert answer['focus']=='technical'
        with urlopen(base+f'/api/clubs/northbridge/players/{p.id}') as r:profile=json.load(r)
        assert profile['graphics']['evolution']['focus']=='technical'
        assert 'potential' not in profile['graphics']['evolution']
    finally:
        server.shutdown();server.server_close();t.join(timeout=3)


@pytest.mark.parametrize('position',list(Position))
def test_perfect_attribute_bound_has_no_floating_point_overflow(position):
    p=make_player(ability=100,potential=100,position=position)
    before=p.attributes
    months(p,2)
    assert p.attributes==before and current_ability(p)<=100
    p.development.validate(p)


def test_results_only_reset_keeps_profile_without_fake_experience():
    from football_manager.services.player_development import restart_results_only_tracking
    w=simple_world();advance_world_development(w,date(2027,2,1))
    saved={p.id:(p.identity,p.attributes,p.development.potential,p.development.seed,
        p.development.growth_peak_age,dict(p.development.residuals))
        for c in w.football_world.clubs.values() for p in c.squad.players}
    restart_results_only_tracking(w.football_world,date(2026,10,20))
    for c in w.football_world.clubs.values():
        for p in c.squad.players:
            assert (p.identity,p.attributes,p.development.potential,p.development.seed,
                p.development.growth_peak_age,p.development.residuals)==saved[p.id]
            assert not p.development.history and p.development.exposure.minutes==0
            assert p.development.last_review==date(2026,10,20)
            p.development.validate(p)
    assert w.football_world.development_next_review==date(2026,11,1)
    assert advance_world_development(w,date(2026,11,1))==12


def test_explicit_legacy_balance_preserves_potential_headroom(tmp_path):
    from football_manager.services.opening_balance import apply_opening_balance,BALANCE_ID
    # A genuine v4 save retains the old unbalanced opening Northbridge data.
    path=tmp_path/'legacy.sqlite3'
    path.write_bytes(gzip.decompress((Path(__file__).parent/'fixtures/ts21_manager_v4.sqlite3.gz').read_bytes()))
    s=load_manager_career(SQLiteSaveRepository(path),'legacy-v4').session
    before={p.id:(current_ability(p),p.development) for p in s.home_club.squad.players}
    answer=apply_opening_balance(s,BALANCE_ID)
    assert answer['player_ids']
    for pid in answer['player_ids']:
        p=s.home_club.squad.get(pid);ca,dev=before[pid]
        assert p.development.potential-current_ability(p)==pytest.approx(dev.potential-ca)
        assert (p.development.seed,p.development.growth_peak_age,p.development.growth_end_age)==(dev.seed,dev.growth_peak_age,dev.growth_end_age)
        assert not p.development.history
        p.development.validate(p)
    validate_manager_session(s)


def test_fifteenth_birthday_does_not_reward_previous_underage_days():
    p=make_player(age=14)
    p.identity=replace(p.identity,birth_date=date(2011,9,1))
    assert growth_budget(p,date(2026,9,1),ENV)==(0.0,'too_young')
    p.identity=replace(p.identity,birth_date=date(2011,8,31))
    late=growth_budget(p,date(2026,9,1),ENV)[0]
    p.identity=replace(p.identity,birth_date=date(2011,8,1))
    full=growth_budget(p,date(2026,9,1),ENV)[0]
    assert 0 < late < full/20
