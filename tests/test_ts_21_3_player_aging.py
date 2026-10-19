"""TS-21.3 mandatory regression: Python only, no network or real user saves."""
from copy import deepcopy
from dataclasses import fields, replace
from datetime import date, timedelta
from pathlib import Path
from types import SimpleNamespace
import json
import pytest
from football_manager.domain.attributes import PlayerAttributes, TechnicalAttributes, MentalAttributes, PhysicalAttributes, GoalkeepingAttributes
from football_manager.domain.player import Player, PlayerIdentity
from football_manager.domain.enums import Foot, Position
from football_manager.domain.personality import Personality
from football_manager.domain.positional_familiarity import PositionalFamiliarity
from football_manager.domain.player_development import initialize_development, attribute_values, current_ability, next_month, DevelopmentEnvironment, review_player
from football_manager.domain.player_aging import initialize_aging, review_career, create_injury, injury_availability, aging_read_model
from football_manager.domain.club import Club
from football_manager.domain.football_world import FootballWorld
from football_manager.domain.world_runner import WorldSeasonRunner
from football_manager.services.player_development import initialize_world_development, advance_world_development, development_read_model
from football_manager.services.player_aging import register_medical_absence, recover_medical_absences, finalize_season_retirements, repair_managed_unavailable, record_postmatch_health
from football_manager.persistence.session_codec import capture_manager_graph, restore_manager_graph
from football_manager.persistence.manager_career import validate_manager_session
from football_manager.dev_ui.session import DevelopmentSession
from football_manager.services.world_squads import select_team
from football_manager.data.english_players import generate_club

START = date(2026, 8, 1)
ENV = DevelopmentEnvironment()


def player(pid='example', age=35, position=Position.CM, ability=75, **aging):
    def group(cls):return cls(**{f.name:ability for f in fields(cls)})
    p=Player(PlayerIdentity(pid,'Test','Player',date(2026-age,1,1),'Example Country',Foot.RIGHT),
        PlayerAttributes(group(TechnicalAttributes),group(MentalAttributes),group(PhysicalAttributes),
                         group(GoalkeepingAttributes) if position is Position.GK else None),
        PositionalFamiliarity({position:100}),position,position,
        personality=Personality(professionalism=75,ambition=70))
    initialize_development(p,START,133,potential=max(ability,95),growth_end_age=30)
    initialize_aging(p,START,133,**aging)
    return p


def review(p,count=12):
    for _ in range(count):
        p.attributes,p.development,p.aging=review_career(p,next_month(p.development.last_review),ENV)
    return p


def small_world(players=None):
    w=WorldSeasonRunner();r=FootballWorld(13,START,'2026/27')
    c=Club('test-club','Test Club','TST','Other Country')
    for p in players or [player(str(i),age=34+i) for i in range(6)]:c.squad.add(p)
    r.clubs[c.id]=c;w.football_world=r
    initialize_world_development(r,START)
    return w,c


def generated_world(age=39):
    w=WorldSeasonRunner();r=FootballWorld(19,START,'2026/27')
    c,identity=generate_club(club_id='outside-england',name='Example Club',tier=1,quality=78,
        seed=19,on_date=START,style='balanced',formation_id='dev-4-3-3')
    for p in c.squad.players:p.identity=replace(p.identity,birth_date=date(2026-age,1,1))
    r.clubs[c.id]=c;r.identities[c.id]=identity;r.last_recovery[c.id]=START;w.football_world=r
    initialize_world_development(r,START)
    return w,c


@pytest.fixture(scope='module')
def session():return DevelopmentSession()


def test_initialization_preserves_all_existing_player_data():
    p=player();p.aging=None
    before=deepcopy((p.identity,p.attributes,p.state,p.development,p.personality))
    a=initialize_aging(p,START,9)
    assert before==(p.identity,p.attributes,p.state,p.development,p.personality)
    assert initialize_aging(p,date(2028,1,1),555) is a


def test_profiles_deterministic_independent_of_order_and_club():
    a=[player(str(i)) for i in range(40)];b=[player(str(i)) for i in reversed(range(40))]
    assert {p.id:p.aging for p in a}=={p.id:p.aging for p in b}
    assert len({p.aging.physical_decline_age for p in a})>35


@pytest.mark.parametrize('age',[13,15,16,19,22,25])
def test_youth_growth_unchanged_without_injury_or_decline(age):
    p=player(age=age);q=deepcopy(p)
    for _ in range(5):
        p.attributes,p.development,p.aging=review_career(p,next_month(p.development.last_review),ENV)
        q.attributes,q.development=review_player(q,next_month(q.development.last_review),ENV)
        assert p.attributes==q.attributes and p.development==q.development


@pytest.mark.parametrize('position',[Position.CM,Position.ST,Position.CB,Position.GK])
def test_old_players_lose_physical_before_mental(position):
    p=player(age=35,position=position,physical_decline_age=29,technical_decline_age=35,mental_decline_age=39)
    before=attribute_values(p.attributes);review(p,24);after=attribute_values(p.attributes)
    assert after['physical.pace']<before['physical.pace']
    assert after['mental.vision']==before['mental.vision']
    assert after['physical.natural_fitness']==before['physical.natural_fitness']
    assert p.development.potential==95
    assert any(h.ability_gain<0 for h in p.development.history)


def test_no_birthday_or_ui_read_attribute_change():
    p=player(age=34);attrs=p.attributes
    for day in (date(2026,12,31),date(2027,1,1),date(2027,1,2)):
        p.age_on(day);development_read_model(p,day)
        assert p.attributes is attrs


def test_fatigue_does_not_change_permanent_decline():
    a=player();b=deepcopy(a);b.state.fatigue=100;b.state.fitness=1
    review(a,24);review(b,24)
    assert a.attributes==b.attributes and a.aging==b.aging


def test_no_retroactive_age_loss_midmonth_migration():
    a=player(age=39);b=deepcopy(a)
    b.aging=replace(b.aging,started_on=date(2026,8,31),last_review=date(2026,8,31))
    review(a,1);review(b,1)
    assert b.attributes==player(age=39).attributes
    assert sum(b.aging.loss_residuals.values())<sum(a.aging.loss_residuals.values())


def test_changing_position_does_not_reroll_longevity():
    a=player(position=Position.ST);b=deepcopy(a);b.primary_position=Position.CM
    review(a,12);review(b,12)
    assert a.attributes==b.attributes and a.aging==b.aging


def test_signed_history_and_bounds_over_twenty_years():
    p=player(age=25);review(p,240)
    assert all(1<=v<=100 for v in attribute_values(p.attributes).values())
    assert len(p.development.history)==12 and len(p.development.annual_history)==20
    assert current_ability(p)<75 and p.aging.retirement_status=='requested'
    p.development.validate(p);p.aging.validate(p)


@pytest.mark.parametrize('field,value',[('physical_decline_age',float('nan')),('decline_rate',float('inf')),('retirement_age',12),('physical_decline_age',True),('mental_decline_age',50),('loss_residuals',{'physical.pace':-1})])
def test_bad_profiles_rejected(field,value):
    p=player()
    with pytest.raises(ValueError):replace(p.aging,**{field:value}).validate(p)


@pytest.mark.parametrize('bad',[0,-1,True,731,2.5])
def test_invalid_medical_duration_rejected(bad):
    with pytest.raises(ValueError):create_injury(player(),START,'episode',bad,'Test')


def test_legacy_injury_not_given_an_invented_recovery_date():
    p=player();p.aging=None;p.state.injury='Existing injury';initialize_aging(p,START,1)
    assert p.aging.active_injury.return_on is None and not p.aging.active_injury.sequelae


def test_partial_month_absence_reduces_growth_proportionally():
    p=player(age=17);w,c=small_world([p]);healthy=deepcopy(p)
    register_medical_absence(w,c.id,p.id,date(2026,8,10),episode_id='a',duration_days=10,label='Test')
    assert injury_availability(p,START,date(2026,9,1))==pytest.approx(21/31)
    advance_world_development(w,date(2026,9,1));review(healthy,1)
    assert sum(p.development.residuals.values())<sum(healthy.development.residuals.values())
    assert p.state.injury is None and p.aging.active_injury is None


def test_recovery_is_dated_without_fitness_reset():
    p=player(age=19);w,c=small_world([p]);p.state.fitness=47
    register_medical_absence(w,c.id,p.id,START,episode_id='a',duration_days=12,label='Test')
    recover_medical_absences(w,date(2026,8,12));assert p.state.injury=='Test'
    recover_medical_absences(w,date(2026,8,13));assert p.state.injury is None
    assert p.state.fitness==47 and len(p.aging.medical_history)==1
    assert recover_medical_absences(w,date(2026,8,20))==0


def test_large_jump_equal_daily_medical_and_development_advances():
    p=player(age=17);a,c=small_world([p]);register_medical_absence(a,c.id,p.id,START,episode_id='severe',duration_days=85,label='Serious')
    b=deepcopy(a);advance_world_development(a,date(2027,1,1));d=START
    while d<date(2027,1,1):
        d+=timedelta(days=1);advance_world_development(b,d)
    assert a.football_world==b.football_world


def test_recover_and_reinjure_transaction_restores_original_index():
    p=player(age=20);w,c=small_world([p]);register_medical_absence(w,c.id,p.id,START,episode_id='first',duration_days=4,label='First')
    before=deepcopy(w.football_world)
    with pytest.raises(RuntimeError):
        with w.transaction():
            recover_medical_absences(w,date(2026,8,5))
            register_medical_absence(w,c.id,p.id,date(2026,8,5),episode_id='second',duration_days=8,label='Second')
            raise RuntimeError('rollback')
    assert w.football_world==before


def test_failure_restores_attributes_medical_state_and_month_clock():
    p=player();w,c=small_world([p]);register_medical_absence(w,c.id,p.id,START,episode_id='x',duration_days=35,label='Test')
    before=deepcopy(w.football_world)
    with pytest.raises(RuntimeError):
        with w.transaction():
            advance_world_development(w,date(2027,1,1))
            raise RuntimeError('fail')
    assert w.football_world==before


def test_sequelae_applied_once_without_changing_pa():
    p=player(age=17);w,c=small_world([p]);register_medical_absence(w,c.id,p.id,START,episode_id='scar',duration_days=42,label='Test')
    p.aging=replace(p.aging,active_injury=replace(p.aging.active_injury,sequelae={'physical.pace':2.3}))
    advance_world_development(w,date(2026,10,1))
    assert p.attributes.physical.pace<=73 and p.development.potential==95
    attrs=p.attributes;profile=p.aging;advance_world_development(w,date(2026,10,1))
    assert p.attributes is attrs and p.aging is profile


def test_minor_injuries_do_not_generate_sequelae():
    p=player(age=16)
    for i in range(50):assert not create_injury(p,START,str(i),4,'Minor').active_injury.sequelae


def test_overlapping_and_duplicate_medical_episodes_rejected():
    p=player();a=create_injury(p,START,'one',20,'Test');p.aging=a;p.state.injury='Test'
    with pytest.raises(ValueError):create_injury(p,START,'two',10,'Test')
    with pytest.raises(ValueError):replace(a,medical_history=(a.active_injury,)).validate(p)


def test_retirement_only_requested_at_month_review():
    p=player(age=43);w,c=small_world([p]);advance_world_development(w,date(2026,9,1))
    assert p.aging.retirement_status=='requested' and c.squad.contains(p.id)
    assert not w.football_world.retired_players


def test_player_requested_retirement_not_subject_to_club_depth():
    w,c=generated_world(age=34)
    goalkeeper=next(p for p in c.squad.players if p.original_position is Position.GK)
    field_player=next(p for p in c.squad.players if p.original_position is not Position.GK)
    for p in (goalkeeper,field_player):
        p.aging=replace(p.aging,retirement_status='requested', retirement_requested_on=START)
    before={p.id for p in c.squad.players}
    gone=finalize_season_retirements(w,date(2026,9,1))
    assert set(gone)=={goalkeeper.id,field_player.id}
    assert before=={p.id for p in c.squad.players}|set(w.football_world.retired_players)
    assert all(p.aging.retirement_status=='retired'
               for p in (goalkeeper,field_player))
    assert not any(p.aging.retirement_status=='deferred' for p in c.squad.players)
    w.football_world.validate()
    assert finalize_season_retirements(w,date(2026,9,1))==()


def test_player_can_retire_even_if_club_loses_second_keeper():
    w,c=generated_world(age=34)
    keepers=[p for p in c.squad.players if p.original_position is Position.GK]
    for p in keepers[1:]:
        p.aging=replace(p.aging,retirement_status='requested',retirement_requested_on=START)
    retired=finalize_season_retirements(w,date(2026,9,1))
    assert set(retired)=={p.id for p in keepers[1:]}
    assert sum(p.original_position is Position.GK for p in c.squad.players)==1


def test_retirement_transaction_restores_squads_and_archives():
    w,c=generated_world(age=34);victim=c.squad.players[0];victim.aging=replace(victim.aging,retirement_status='requested',retirement_requested_on=START);before=deepcopy(w.football_world)
    with pytest.raises(RuntimeError):
        with w.transaction():
            finalize_season_retirements(w,date(2026,9,1));raise RuntimeError('fail')
    assert w.football_world==before


def test_archived_players_do_not_keep_developing():
    w,c=generated_world(age=34);victim=c.squad.players[0];victim.aging=replace(victim.aging,retirement_status='requested',retirement_requested_on=START);finalize_season_retirements(w,date(2026,9,1))
    archived=deepcopy(w.football_world.retired_players);advance_world_development(w,date(2027,1,1))
    assert w.football_world.retired_players==archived


def test_public_model_keeps_latent_curve_private():
    text=json.dumps(aging_read_model(player()))
    assert 'decline_rate' not in text and 'retirement_age' not in text and 'seed' not in text


def test_session_has_2024_aging_profiles_and_valid_state(session):
    r=session._world_squads
    assert sum(len(c.squad) for c in r.clubs.values())==2024
    assert all(p.aging is not None for c in r.clubs.values() for p in c.squad.players)
    validate_manager_session(session)


def test_full_graph_roundtrip_preserves_age_and_medical_data(session):
    s=deepcopy(session);p=next(p for p in s.home_club.squad.players if p.state.injury is None)
    register_medical_absence(s._world,s.home_club.id,p.id,s.current_date,episode_id='saved',duration_days=70,label='Test')
    graph=capture_manager_graph(s);assert graph['version']==17
    loaded=restore_manager_graph(graph);validate_manager_session(loaded)
    assert loaded._world_squads==s._world_squads
    assert loaded.home_lineup.starters[0].player is loaded.home_club.squad.get(loaded.home_lineup.starters[0].player.id)


def test_auto_repair_retains_healthy_starters_and_tactics(session):
    s=deepcopy(session);original=s.home_lineup;tactic=s.home_tactic;p=original.starters[4].player
    register_medical_absence(s._world,s.home_club.id,p.id,s.current_date,episode_id='lineup',duration_days=20,label='Test')
    assert repair_managed_unavailable(s)
    assert s.home_tactic is tactic and p.id not in {p.id for p in s.home_lineup.selected_players}
    assert all(e.player is s.home_lineup.starters[i].player for i,e in enumerate(original.starters) if i!=4)
    assert len(set(p.id for p in s.home_lineup.selected_players))==len(s.home_lineup.selected_players)
    s.home_club.validate_lineup(s.home_lineup)


def test_manual_submission_still_rejects_injured_players(session):
    s=deepcopy(session);p=s.home_lineup.starters[5].player
    register_medical_absence(s._world,s.home_club.id,p.id,s.current_date,episode_id='manual',duration_days=20,label='Test')
    with pytest.raises(ValueError):s.quick_simulate()


def test_postmatch_assessments_deterministic_and_only_for_played_minutes(session):
    s=deepcopy(session);r=s.quick_simulate();fid=s._active_match.fixture.fixture_id
    a=deepcopy(session);b=deepcopy(session)
    with a._world.transaction():record_postmatch_health(a._world,fid,r)
    with b._world.transaction():record_postmatch_health(b._world,fid,r)
    assert a._world_squads==b._world_squads
    zero=SimpleNamespace(player_statistics=[SimpleNamespace(club_id=s.home_club.id,player_id=p.id,minutes=0) for p in s.home_club.squad.players])
    before=deepcopy(a._world_squads)
    with a._world.transaction():record_postmatch_health(a._world,fid,zero)
    assert a._world_squads==before


def test_negative_changes_render_without_plus_minus_prefix():
    js=(Path(__file__).resolve().parents[1]/'frontend/public/squad/presentation.js').read_text()
    assert "${v>0?'+':''}${v}" in js and '<b>+${v}</b>' not in js


def test_actual_version_seven_migration_preserves_every_existing_attribute_and_birthdate():
    import gzip
    folder=Path(__file__).resolve().parent/'fixtures'
    graph=json.loads(gzip.decompress((folder/'ts213_manager_v7.json.gz').read_bytes()))
    facts=json.loads(gzip.decompress((folder/'ts213_manager_v7_facts.json.gz').read_bytes()))
    assert graph['version']==7
    s=restore_manager_graph(graph);validate_manager_session(s)
    assert s.current_date.isoformat()==facts['date']
    for c in s._world_squads.clubs.values():
        for p in c.squad.players:
            expected=facts['players'][p.id]
            assert p.attributes and attribute_values(p.attributes)==expected['attrs']
            assert p.identity.birth_date.isoformat()==expected['birth']
            assert p.development.potential==expected['pa']
            assert p.development.last_review.isoformat()==expected['review']
            assert p.state.fitness==expected['fitness'] and p.state.injury==expected['injury']
            assert p.aging.started_on==s.current_date and not p.aging.loss_residuals
    assert not s._world_squads.retired_players


def test_prepare_next_match_clears_unavailable_selections_without_healing(session):
    s=deepcopy(session);p=s.home_lineup.starters[4].player
    register_medical_absence(s._world,s.home_club.id,p.id,s.current_date,episode_id='prepare',duration_days=20,label='Test')
    s._prepare_development_opponent()
    assert p.state.injury=='Test' and p.id not in {p.id for p in s.home_lineup.selected_players}


def test_sqlite_roundtrip_with_medical_data(session,tmp_path):
    from football_manager.persistence import SQLiteSaveRepository,save_manager_career,load_manager_career
    s=deepcopy(session);p=s.home_club.squad.players[0]
    register_medical_absence(s._world,s.home_club.id,p.id,s.current_date,episode_id='sqlite',duration_days=40,label='Test')
    repo=SQLiteSaveRepository(tmp_path/'career.sqlite3')
    save_manager_career(repo,slot_id='career',display_name='Synthetic',session=s,expected_revision=0)
    loaded=load_manager_career(repo,'career').session
    assert loaded._world_squads==s._world_squads
    loaded._prepare_development_opponent();s._prepare_development_opponent()
    assert loaded.quick_simulate()==s.quick_simulate()
    loaded.continue_to_next_match();s.continue_to_next_match()
    assert loaded._world_squads==s._world_squads


def test_failed_postmatch_commit_restores_health_and_rng_state(session,monkeypatch):
    import football_manager.services.player_aging as service
    s=deepcopy(session)
    before=deepcopy((s._world_squads,s._world.results,s._seed,s.last_result,s.match_played))
    def broken(world,fixture_id,result):
        p=s.home_club.squad.players[0]
        register_medical_absence(world,s.home_club.id,p.id,s.current_date,episode_id='rollback',duration_days=80,label='Test')
        raise RuntimeError('injected health commit failure')
    monkeypatch.setattr(service,'record_postmatch_health',broken)
    with pytest.raises(RuntimeError):s.quick_simulate()
    # The transaction restores equivalent data, not graph node allocation or
    # incidental object aliasing inside immutable attribute groups.
    assert (s._world_squads,s._world.results,s._seed,s.last_result,s.match_played)==before
    validate_manager_session(s)


def test_retired_shirt_number_does_not_block_new_active_assignment(session):
    from football_manager.persistence.manager_career import _validate_admin
    from football_manager.ui_shell.models import UIRosterAdmin
    from football_manager.domain.player_aging import RetiredPlayer
    s=deepcopy(session)
    p=next(p for p in s.home_club.squad.players if p.id not in {q.id for q in s.home_lineup.selected_players})
    p.aging=replace(p.aging,retirement_status='retired',retirement_requested_on=s.current_date,retired_on=s.current_date)
    s.home_club.squad._players.pop(p.id)
    s._world_squads.retired_players[p.id]=RetiredPlayer(p,s.home_club.id,s.current_date)
    from football_manager.services.dressing_room import sync_roster
    sync_roster(s.dressing_room,s.home_club.squad.players)
    other=s.home_lineup.starters[0].player
    _validate_admin(UIRosterAdmin(numbers={p.id:12,other.id:12}),s)
    validate_manager_session(s)


def test_bad_retired_attribute_data_rejected():
    from football_manager.domain.player_aging import RetiredPlayer
    p=player();p.aging=replace(p.aging,retirement_status='retired',retirement_requested_on=START,retired_on=START)
    object.__setattr__(p.attributes.physical,'pace',101)
    with pytest.raises(ValueError):RetiredPlayer(p,'club',START).validate()


def test_prematch_medical_dates_are_real_and_readonly(session):
    from football_manager.ui_shell.match import prematch_read_model
    from football_manager.ui_shell.models import UIRosterAdmin
    s=deepcopy(session)
    p=next(p for p in s.home_club.squad.players if p.id not in {q.id for q in s.home_lineup.selected_players})
    register_medical_absence(s._world,s.home_club.id,p.id,s.current_date,episode_id='display-old',duration_days=14,label='Test medical absence')
    before=deepcopy(s._world_squads)
    view=prematch_read_model(s,UIRosterAdmin())
    row=next(r for r in view['managed']['unavailable'] if r['id']==p.id)
    assert row['injury']=='Test medical absence'
    assert row['return_on']==(s.current_date+timedelta(days=14)).isoformat()
    assert s._world_squads==before


def test_postmatch_reports_assessments_not_invented_match_events(session):
    from football_manager.ui_shell.match import prematch_read_model,result_read_model
    from football_manager.ui_shell.models import UIRosterAdmin
    s=deepcopy(session)
    reserve=next(p for p in s.home_club.squad.players if p.id not in {q.id for q in s.home_lineup.selected_players})
    register_medical_absence(s._world,s.home_club.id,reserve.id,s.current_date,episode_id='old-absence',duration_days=14,label='Existing absence')
    meta=prematch_read_model(s,UIRosterAdmin())['match'];result=s.quick_simulate()
    p=next(p for p in s.home_lineup.starting_players if p.state.injury is None)
    register_medical_absence(s._world,s.home_club.id,p.id,s.current_date,episode_id=meta['fixture_id']+':'+p.id,duration_days=30,label='Test post-match assessment',source='postmatch-assessment-v1')
    view=result_read_model(s,meta,result)
    assert view['injury_tracking_supported'] and not view['in_match_injuries_supported']
    assert any(r['player']==p.full_name and r['return_on']==(s.current_date+timedelta(days=30)).isoformat() for r in view['new_injuries'])
    assert not any(r['player']==reserve.full_name for r in view['new_injuries'])
    assert not any(e['kind']=='injury' for e in view['events'])
    assert view==result_read_model(s,meta,result)
