"""TS-21.1: persistent English squads, football identities and portable integration.

All tests are Python-only. The legacy fixture is synthetic and was saved with
an unmodified version-4 (TS-20 + TS-19 hotfix) manager codec.
"""
from __future__ import annotations

from collections import Counter
from copy import deepcopy
from dataclasses import asdict, replace
from datetime import date, timedelta
import gzip
import itertools
import json
from pathlib import Path
from threading import Thread
from urllib.error import HTTPError
from urllib.request import urlopen

import pytest

from football_manager.data.english_players import (
    CB, STYLE_FORMATIONS, generate_club, make_identity, stable_seed, target_quality,
)
from football_manager.dev_ui.session import DevelopmentSession
from football_manager.domain.enums import Position
from football_manager.domain.football_world import PlayerSeasonUsage
from football_manager.domain.season_cycle import TIER_IDS
from football_manager.domain.tactical_catalogue import development_formations
from football_manager.persistence import (
    SQLiteSaveRepository, SaveIntegrityError, load_manager_career, save_manager_career,
)
from football_manager.persistence.manager_career import validate_manager_session
from football_manager.persistence.session_codec import capture_manager_graph, restore_manager_graph
from football_manager.services.world_matches import competition_context, opponent_side
from football_manager.services.world_squads import (
    coverage_report, english_participants, maximum_assignment, select_lineup,
    recover_world_club,
)
from football_manager.ui_shell.world_squads import club_squad_read_model, world_squads_index


@pytest.fixture(scope='module')
def initial():
    return DevelopmentSession()


@pytest.fixture
def session(initial):
    return deepcopy(initial)


def players(session):
    return {p.id: p for c in session._world_squads.clubs.values() for p in c.squad.players}


def next_background(session):
    r = session._world_squads
    return min((f for fid,f in session._world.fixtures.items()
                if fid not in session._world.results
                and session.home_club.id not in (f.home_club_id,f.away_club_id)
                and f.home_club_id in r.clubs and f.away_club_id in r.clubs
                and f.match_date >= max(r.last_recovery[f.home_club_id],r.last_recovery[f.away_club_id])),
               key=lambda f: (f.kickoff,f.fixture_id))


def test_exact_initial_universe_and_canonical_objects(initial):
    r=initial._world_squads
    assert len(r.clubs)==92 and len(players(initial))==2024
    assert Counter(i.tier for i in r.identities.values())=={1:20,2:24,3:24,4:24}
    assert all(len(c.squad)==22 for c in r.clubs.values())
    assert r is initial._world.football_world
    assert r.clubs[initial.home_club.id] is initial.home_club
    assert r.clubs[initial.away_club.id] is initial.away_club
    validate_manager_session(initial)


@pytest.mark.parametrize('tier', [1,2,3,4])
def test_each_division_has_quality_range_styles_ages_and_internal_depth(initial,tier):
    r=initial._world_squads
    ids=[cid for cid,i in r.identities.items() if i.tier==tier]
    ratings=[]
    for cid in ids:
        club,identity=r.clubs[cid],r.identities[cid]
        model=club_squad_read_model(initial,cid)
        ratings.append(model['mean_xi_ovr'])
        if not identity.source.startswith('preserved'):
            ages=[p.age_on(r.created_on) for p in club.squad.players]
            assert min(ages)<=20 and max(ages)>=32
            natural=[p.overall_rating for p in club.squad.players]
            assert max(natural)-min(natural)>5
    assert set(r.identities[cid].style_key for cid in ids)==set(STYLE_FORMATIONS)
    assert max(ratings)-min(ratings)>10
    assert abs(sum(ratings)/len(ratings)-{1:79.5,2:69.5,3:59.5,4:49.5}[tier])<2


@pytest.mark.parametrize('tier',[1,2,3])
def test_division_ranges_overlap_without_individual_caps(tier):
    assert target_quality(tier,0,24)<target_quality(tier+1,23,24)
    values=[target_quality(tier,i,24) for i in range(24)]
    assert values==sorted(values)


@pytest.mark.parametrize('formation',development_formations(),ids=lambda f:f.formation_id)
def test_22_players_generated_for_every_existing_formation(formation):
    club,identity=generate_club(club_id='test-shape',name='Shape Athletic',tier=2,quality=68,
        seed=217,on_date=date(2026,8,1),style='balanced',formation_id=formation.formation_id)
    counts=Counter(p.primary_position for p in club.squad.players)
    assert counts==Counter({p:2*n for p,n in Counter(s.position for s in formation.slots).items()})
    assert len(club.squad)==22 and counts[Position.GK]==2
    assert coverage_report(club,identity.primary)['complete']
    assert len({p.id for p in club.squad.players})==22
    assert sum(p.primary_position in CB for p in club.squad.players)==2*sum(s.position in CB for s in formation.slots)
    if sum(s.position in CB for s in formation.slots)==3:
        assert sum(p.primary_position in CB for p in club.squad.players)>=5
    assert sum(len(p.secondary_positions)>0 for p in club.squad.players)>=6
    lineup=select_lineup(club,identity.primary)
    assert len(lineup.starters)==11 and len(lineup.bench)==7
    assert len({p.id for p in lineup.starting_players+lineup.bench})==18


@pytest.mark.parametrize('style',list(STYLE_FORMATIONS))
def test_styles_drive_instructions_roles_and_player_profiles(style):
    a,i=generate_club(club_id='same-club',name='Identity FC',tier=2,quality=70,
                     seed=123,on_date=date(2026,8,1),style=style,formation_id='dev-4-4-2')
    i.validate()
    assert i.primary.preset_origin.value==style
    assert i.primary.team_instructions!=i.alternative.team_instructions
    assert len(i.primary.formation.slots)==11
    for slot in i.primary.formation.slots:
        role=i.primary.role_for_slot(slot.slot_id)
        assert slot.position in role.compatible_positions
        natural=[p for p in a.squad.players if p.primary_position is slot.position]
        assert natural
        assert max(p.tactical_familiarity.role_score(role.role_id) for p in natural)>=80
    if style in ('direct_play','direct_counter'):
        strikers=[i.primary.role_for_slot(s.slot_id).role_id for s in i.primary.formation.slots if s.position is Position.ST]
        assert strikers==['target_forward','advanced_forward']
    if style in ('low_block','catenaccio'):
        assert i.primary.role_for_slot('rw').role_id=='defensive_winger'
    if style=='possession':
        assert i.primary.role_for_slot('gk').role_id=='distributor_keeper'


def test_same_shape_does_not_mean_same_style():
    identities=[make_identity('club','Club',1,s,21,'dev-4-3-3') for s in STYLE_FORMATIONS]
    assert len({repr(i.primary.team_instructions) for i in identities})==11
    assert len({tuple(i.primary.role_for_slot(s.slot_id).role_id for s in i.primary.formation.slots)
                for i in identities})>=7


def test_generation_is_reproducible_and_does_not_use_process_hash_seed():
    kwargs=dict(club_id='club',name='Club',tier=2,quality=69,seed=21,on_date=date(2026,8,1),style='counterpress')
    a,ia=generate_club(**kwargs);b,ib=generate_club(**kwargs)
    assert a==b and ia==ib
    assert stable_seed(21,'club')==int.from_bytes(__import__('hashlib').sha256(b'21:club').digest()[:8],'big')
    c,_=generate_club(**{**kwargs,'seed':22})
    assert a.squad.players[0].id!=c.squad.players[0].id


def test_all_clubs_have_two_nonoverlapping_xis_and_usable_alternative(initial):
    for cid,club in initial._world_squads.clubs.items():
        identity=initial._world_squads.identities[cid]
        coverage=coverage_report(club,identity.primary)
        assert coverage['complete'],cid
        assert len({a['player_id'] for a in coverage['assignments']})==22
        lineup=select_lineup(club,identity.alternative,current=False)
        assert min(e.player.familiarity_for(lineup.formation.slot(e.slot_id).position)
                   for e in lineup.starters)>=70,cid


@pytest.mark.parametrize('weights',[
    [[9,8,1],[9,0,3]], [[1,2,3],[3,2,1],[2,4,3]], [[-4,-3,-2],[0,-4,-2]], [[3,3],[3,3]],
])
def test_assignment_matches_exhaustive_optimum(weights):
    assignment=maximum_assignment(weights)
    result=sum(weights[i][j] for i,j in enumerate(assignment))
    expected=max(sum(weights[i][j] for i,j in enumerate(p))
                 for p in itertools.permutations(range(len(weights[0])),len(weights)))
    assert len(set(assignment))==len(weights) and result==expected


def test_selection_avoids_unavailable_and_exhausted_players(session):
    r=session._world_squads;cid=session.away_club.id;c=r.clubs[cid];t=r.identities[cid].primary
    original=select_lineup(c,t)
    gk=next(e.player for e in original.starters if e.player.primary_position is Position.GK)
    gk.state.injury='test injury'
    tired=next(e.player for e in original.starters if e.player.primary_position is not Position.GK)
    tired.state.fitness=12;tired.state.fatigue=95
    selected=select_lineup(c,t)
    assert gk.id not in {p.id for p in selected.starting_players+selected.bench}
    assert tired.id not in {p.id for p in selected.starting_players}
    for p in c.squad.players:
        if p.primary_position is Position.GK:p.state.injury='unavailable'
    with pytest.raises(ValueError):select_lineup(c,t)


def test_prepare_opponent_reuses_players_and_real_tactics(session):
    old=session.away_club; attrs={p.id:p.attributes for p in old.squad.players}
    session._prepare_development_opponent(); session._prepare_development_opponent()
    assert session.away_club is old
    assert attrs=={p.id:p.attributes for p in old.squad.players}
    snap=session._build_snapshot();team=snap.away_team if session.managed_is_home else snap.home_team
    assert team.tactic.team_instructions==session.away_tactic.team_instructions
    assert {p.player_id for p in team.starters}=={e.player.id for e in session.away_lineup.starters}
    assert all(p.role_id==session.away_tactic.role_for_slot(p.assigned_slot_id).role_id for p in team.starters)


def test_debug_handicap_does_not_mutate_persistent_players(session):
    attrs={p.id:p.attributes for p in session.away_club.squad.players}
    def rating():
        snap=session._build_snapshot();team=snap.away_team if session.managed_is_home else snap.home_team
        return sum(p.overall_rating for p in team.starters)
    normal=rating();session.set_dev_favorable_mode(True)
    assert rating()<normal-50
    assert attrs=={p.id:p.attributes for p in session.away_club.squad.players}
    session.set_dev_favorable_mode(False)
    assert rating()==normal


def test_background_and_managed_use_same_engine_and_registered_ids(session,monkeypatch):
    import football_manager.services.world_matches as service
    fixture=next_background(session); seen=[]; actual=service.FastMatchSimulator.simulate
    def spy(self,snapshot,**kwargs):
        seen.append(snapshot);return actual(self,snapshot,**kwargs)
    monkeypatch.setattr(service.FastMatchSimulator,'simulate',spy)
    record=session._world.simulate_fixture(fixture.fixture_id)
    assert record.fixture_id==fixture.fixture_id and len(seen)==1
    snapshot=seen[0];r=session._world_squads
    for team in (snapshot.home_team,snapshot.away_team):
        club=r.clubs[team.club_id];identity=r.identities[team.club_id]
        assert all(club.squad.contains(p.player_id) for p in team.starters+team.bench)
        assert team.tactic.tactic_id in (identity.primary.tactic_id,identity.alternative.tactic_id)
        assert all(r.usage[p.player_id].minutes>=90 for p in team.starters)
        assert r.last_recovery[club.id]==fixture.match_date
    assert fixture.fixture_id in r.processed_fixtures
    with pytest.raises(ValueError):session._world.simulate_fixture(fixture.fixture_id)


def test_english_match_strength_comes_from_players_not_tier_scalars(session):
    fixture=next_background(session);other=deepcopy(session)
    other._world.strengths[fixture.home_club_id]=1.0
    other._world.strengths[fixture.away_club_id]=99.0
    a=session._world.simulate_fixture(fixture.fixture_id)
    b=other._world.simulate_fixture(fixture.fixture_id)
    assert (a.home_goals,a.away_goals)==(b.home_goals,b.away_goals)
    assert session._world_squads.usage==other._world_squads.usage


def test_background_rollback_includes_usage_clock_and_players(session,monkeypatch):
    import football_manager.services.world_matches as service
    fixture=next_background(session)
    before=deepcopy(session._world_squads)
    results=dict(session._world.results)
    real=service.record_world_usage
    def fail(*args):
        real(*args);raise RuntimeError('commit injection')
    monkeypatch.setattr(service,'record_world_usage',fail)
    with pytest.raises(RuntimeError,match='injection'):
        session._world.simulate_fixture(fixture.fixture_id)
    assert session._world_squads==before and session._world.results==results
    assert session._world._active_journal is None


def test_managed_usage_commits_exact_minutes_once_and_rolls_back(session,monkeypatch):
    import football_manager.services.world_matches as service
    before=deepcopy(session._world_squads);real=service.record_world_usage
    def fail(*args):
        real(*args);raise RuntimeError('usage injection')
    monkeypatch.setattr(service,'record_world_usage',fail)
    with pytest.raises(RuntimeError):session.quick_simulate()
    assert session._world_squads==before
    monkeypatch.undo();result=session.quick_simulate()
    for stat in result.player_statistics:
        if stat.minutes>0 and stat.club_id in session._world_squads.clubs:
            old=before.usage.get(stat.player_id,PlayerSeasonUsage())
            new=session._world_squads.usage[stat.player_id]
            assert new.minutes-old.minutes==stat.minutes
            assert new.goals-old.goals==stat.goals
    with pytest.raises(RuntimeError):session.quick_simulate()
    validate_manager_session(session)


def test_daily_recovery_is_cadence_independent(session):
    a=deepcopy(session._world);b=deepcopy(session._world)
    cid=session.away_club.id;start=a.football_world.last_recovery[cid]
    recover_world_club(a,cid,start+timedelta(days=5))
    for i in range(1,6):recover_world_club(b,cid,start+timedelta(days=i))
    assert a.football_world.clubs[cid]==b.football_world.clubs[cid]
    with pytest.raises(ValueError):recover_world_club(a,cid,start)


def test_promotion_changes_membership_not_players_or_attributes(session):
    r=session._world_squads;before=deepcopy(r.clubs);old_usage=deepcopy(r.usage);old_season=r.season_label
    tiers=english_participants(session._world)
    a=next(c for c,t in tiers.items() if t==1);b=next(c for c,t in tiers.items() if t==2)
    tiers[a],tiers[b]=2,1
    r.adopt_season('2027-2028',tiers)
    assert r.clubs==before and r.history[old_season]==old_usage
    assert r.identities[a].tier==2 and r.identities[a].initial_tier==1
    assert not r.usage and not r.processed_fixtures
    r.validate(tiers)


def test_complete_save_roundtrip_then_same_results(session,tmp_path):
    repo=SQLiteSaveRepository(tmp_path/'career.sqlite3')
    save_manager_career(repo,slot_id='career',display_name='Test',session=session,expected_revision=0)
    restored=load_manager_career(repo,'career').session
    assert restored._world_squads==session._world_squads
    assert restored._world_squads is restored._world.football_world
    assert restored.home_club is restored._world_squads.clubs[restored.home_club.id]
    a=session.quick_simulate();b=restored.quick_simulate()
    assert a==b and restored._world_squads==session._world_squads
    validate_manager_session(restored)


def test_real_version_four_save_migrates_without_rewriting_players(tmp_path):
    path=tmp_path/'v4.sqlite3'
    path.write_bytes(gzip.decompress((Path(__file__).parent/'fixtures/ts21_manager_v4.sqlite3.gz').read_bytes()))
    repo=SQLiteSaveRepository(path)
    raw=repo.load('legacy-v4').document
    graph=next(s.payload for s in raw.sections if s.name=='manager_state')
    assert graph['version']==4
    old=restore_manager_graph(graph,migrate_world=False)
    preserved={p.id:(deepcopy(p.identity),deepcopy(p.attributes),deepcopy(p.personality),deepcopy(p.state))
               for club in (old.home_club,old.away_club) for p in club.squad.players}
    loaded=load_manager_career(repo,'legacy-v4').session
    assert len(players(loaded))==2024
    for pid,expected in preserved.items():
        p=players(loaded)[pid]
        assert (p.identity,p.attributes,p.personality,p.state)==expected
    assert loaded.home_tactic==old.home_tactic
    # TS-21.2 adds private development metadata, not different footballers or slots.
    assert loaded.home_lineup.formation==old.home_lineup.formation
    assert [(e.slot_id,e.player.id) for e in loaded.home_lineup.starters]==[(e.slot_id,e.player.id) for e in old.home_lineup.starters]
    assert [p.id for p in loaded.home_lineup.bench]==[p.id for p in old.home_lineup.bench]
    assert not loaded._world_squads.usage
    assert loaded._world_squads.tracked_from==loaded.current_date
    validate_manager_session(loaded)
    save_manager_career(repo,slot_id='new-v5',display_name='Migrated',session=loaded,expected_revision=0)
    reread=load_manager_career(repo,'new-v5').session
    assert players(loaded).keys()==players(reread).keys()


@pytest.mark.parametrize('damage',['duplicate','missing-club','negative-minutes','personality','uncounted-result','foreign-usage'])
def test_corrupt_world_save_is_rejected(session,damage):
    r=session._world_squads;club=next(iter(r.clubs.values()));p=club.squad.players[0]
    if damage=='duplicate':
        other=next(c for c in r.clubs.values() if c is not club);other.squad._players[p.id]=p
    elif damage=='missing-club':r.clubs.pop(club.id)
    elif damage=='negative-minutes':p.positional_familiarity.played_minutes[p.primary_position]=-2
    elif damage=='personality':p.personality=None
    elif damage=='uncounted-result':r.processed_fixtures['invented-fixture']=True
    else:r.usage['unknown-player']=PlayerSeasonUsage()
    with pytest.raises(SaveIntegrityError):validate_manager_session(session)


def test_results_only_import_is_not_a_fake_complete_squad_restore(session,tmp_path):
    path=tmp_path/'results.json';session.save_world(path)
    before_ids=set(players(session));session.quick_simulate();session.load_world(path)
    assert set(players(session))==before_ids
    assert not session._world_squads.usage
    validate_manager_session(session)
    session.quick_simulate();validate_manager_session(session)


def test_roster_api_read_models_are_pure_and_expose_real_data(session):
    before=capture_manager_graph(session)
    index=world_squads_index(session);roster=club_squad_read_model(session,session.away_club.id)
    assert index['player_count']==2024 and len(index['leagues'])==4
    assert roster['count']==22 and len(roster['primary']['slots'])==11
    assert roster['primary']['instructions'] and roster['alternative']['instructions']
    assert all(p['attributes'] and 'personality' not in p for p in roster['players'])
    assert roster['development_enabled'] is False
    assert capture_manager_graph(session)==before
    with pytest.raises(KeyError):club_squad_read_model(session,'unknown')


def test_http_api_and_portable_assets_without_node(session,tmp_path):
    from football_manager.ui_shell.server import create_server
    root=Path(__file__).resolve().parents[1]/'frontend'
    server=create_server(0,session,SQLiteSaveRepository(tmp_path/'api.sqlite3'),root)
    thread=Thread(target=server.serve_forever,daemon=True);thread.start()
    base=f'http://127.0.0.1:{server.server_port}'
    try:
        def get(path):
            with urlopen(base+path,timeout=15) as response:return response.read()
        assert json.loads(get('/api/world-squads'))['club_count']==92
        assert json.loads(get('/api/world-squads/'+session.away_club.id))['count']==22
        assert b'FMWorldSquads' in get('/portable/world_squads.js')
        assert b'.ws-' in get('/portable/world_squads.css')
        page=get('/').decode()
        assert page.index('world_squads.js')<page.index('competitions.js')
        with pytest.raises(HTTPError) as error:get('/api/world-squads/unknown')
        assert error.value.code==404
    finally:
        server.shutdown();thread.join(5);server.server_close()


def test_outer_world_transaction_rolls_back_successful_background_player_updates(session):
    before = deepcopy(session._world_squads)
    ledger = deepcopy(session._world.results)
    fixture = next_background(session)
    with pytest.raises(RuntimeError, match='outer failure'):
        with session._world.transaction():
            session._world.simulate_fixture(fixture.fixture_id)
            assert fixture.fixture_id in session._world_squads.processed_fixtures
            raise RuntimeError('outer failure')
    assert session._world_squads == before
    assert session._world.results == ledger


def test_external_relegation_retains_players_and_bootstraps_only_new_entrant(session):
    from football_manager.services.world_squads import bind_football_world
    r = session._world_squads
    old = {p.id:p.attributes for c in r.clubs.values() for p in c.squad.players}
    league_id = TIER_IDS[-1]
    edition = session._world.leagues[league_id]
    outgoing = edition.participant_club_ids[-1]
    incoming = 'external-test-entrant'
    # Isolate squad binding from calendar generation; complete valid season
    # transitions are exercised by tools/check_ts21_full_season.py.
    from types import SimpleNamespace
    session._world.leagues[league_id] = SimpleNamespace(
        participant_club_ids=tuple(c for c in edition.participant_club_ids if c!=outgoing)+(incoming,))
    session._career.club_names[incoming] = 'External Test Entrant'
    bind_football_world(session)
    assert r.identities[outgoing].tier == 0 and len(r.clubs[outgoing].squad)==22
    assert r.identities[incoming].tier == 4 and len(r.clubs[incoming].squad)==22
    current = {p.id:p.attributes for c in r.clubs.values() for p in c.squad.players}
    assert old.keys() <= current.keys() and all(current[pid]==a for pid,a in old.items())
    assert len(current)==2046
    r.validate(english_participants(session._world))
