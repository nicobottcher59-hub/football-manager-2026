"""TS-20 football/domain contracts: automatic, bounded, deterministic, optional UI."""
from __future__ import annotations

from copy import deepcopy
from dataclasses import asdict, replace
from datetime import date, timedelta
import json
import os
from pathlib import Path
import random
import subprocess
import sys

import pytest

from football_manager.dev_ui import DevelopmentSession
from football_manager.domain.dressing_room import MAX_EVENTS, MAX_FIXTURE_MEMORY, MAX_APPEARANCES
from football_manager.domain.personality import Personality, personality_for
from football_manager.domain.player_state import PlayerState
from football_manager.domain.snapshot_assignment import assign_match_player
from football_manager.services.dressing_room import (
    create_dressing_room, advance_dressing_room, record_dressing_room_match,
    participation_concern, sync_roster,
)
from football_manager.ui_shell.dressing_room import dressing_room_read_model
from football_manager.ui_shell.models import UIRosterAdmin, apply_squad_command, squad_read_model


@pytest.fixture(scope='module')
def template():
    return DevelopmentSession()


@pytest.fixture
def session(template):
    return deepcopy(template)


def _record(s, n, *, played=None, eligible=None, days=7, outcome=0, intervals=None):
    s.current_date += timedelta(days=days)
    players=s.home_club.squad.players
    if played is None:
        played={p.id:90 if i<11 else 0 for i,p in enumerate(players)}
    if eligible is None:
        eligible={p.id:True for p in players}
    if intervals is None:
        intervals={p:((0,m),) for p,m in played.items() if m}
    return record_dressing_room_match(s.dressing_room,players,fixture_id=f'ts20-{n}',
        on_date=s.current_date,minutes=played,eligible=eligible,intervals=intervals,outcome=outcome)


def test_new_state_is_neutral_and_does_not_invent_past_history(session):
    assert len(session.dressing_room.members)==len(session.home_club.squad)
    n = len(session.home_club.squad)
    assert len(session.dressing_room.links)==n*(n-1)//2
    assert session.dressing_room.processed_fixtures=={}
    assert not session.dressing_room.events
    assert all(not m.appearances for m in session.dressing_room.members.values())
    assert all(p.state.dressing_room_morale==0 for p in session.home_club.squad.players)
    session.dressing_room.validate({p.id for p in session.home_club.squad.players},session.current_date)


@pytest.mark.parametrize('name',list(Personality.__dataclass_fields__))
@pytest.mark.parametrize('bad',[0,101,True,float('nan')])
def test_hidden_trait_validation(name,bad):
    with pytest.raises(ValueError):
        Personality(**{name:bad})


def test_personality_defaults_stay_stable_without_consuming_global_rng():
    before=random.getstate()
    assert personality_for('player-7')==personality_for('player-7')
    assert personality_for('player-7')!=personality_for('player-8')
    assert random.getstate()==before
    code="from dataclasses import asdict;from football_manager.domain.personality import personality_for;import json;print(json.dumps(asdict(personality_for('player-7')),sort_keys=True))"
    a=subprocess.check_output([sys.executable,'-c',code],text=True,env={**os.environ, 'PYTHONPATH':str(Path(__file__).resolve().parents[1]/'src')})
    assert json.loads(a)==asdict(personality_for('player-7'))


@pytest.mark.parametrize('bad',[-2.001,2.001,float('nan'),float('inf'),True])
def test_social_morale_is_strictly_bounded(bad):
    with pytest.raises(ValueError):
        PlayerState(dressing_room_morale=bad)


def test_context_replaces_itself_and_never_mutates_base_ability_state_or_chemistry(session):
    players=session.home_club.squad.players
    before={p.id:(p.attributes,deepcopy(p.positional_familiarity),deepcopy(p.tactical_familiarity),p.overall_rating,
                  p.state.morale,p.state.confidence,p.state.form,p.state.fitness) for p in players}
    chemistry=deepcopy(session._home_chemistry)
    advance_dressing_room(session.dressing_room,players,session.current_date+timedelta(days=365))
    for p in players:
        assert (p.attributes,p.positional_familiarity,p.tactical_familiarity,p.overall_rating,
                p.state.morale,p.state.confidence,p.state.form,p.state.fitness)==before[p.id]
        assert -2<=p.state.dressing_room_morale<=2
    assert session._home_chemistry==chemistry
    state=deepcopy(session.dressing_room);morales=[deepcopy(p.state) for p in players]
    advance_dressing_room(session.dressing_room,players,state.last_updated)
    assert session.dressing_room==state
    assert [p.state for p in players]==morales


def test_daily_and_fast_forward_are_exactly_identical(session):
    batch=deepcopy(session)
    target=session.current_date+timedelta(days=100)
    for i in range(1,101):
        advance_dressing_room(session.dressing_room,session.home_club.squad.players,session.current_date+timedelta(days=i))
    advance_dressing_room(batch.dressing_room,batch.home_club.squad.players,target)
    assert session.dressing_room==batch.dressing_room
    assert [p.state for p in session.home_club.squad.players]==[p.state for p in batch.home_club.squad.players]


def test_roster_insertion_order_does_not_change_social_results(session):
    other=deepcopy(session)
    other.home_club.squad._players=dict(reversed(list(other.home_club.squad._players.items())))
    for s in (session,other):
        advance_dressing_room(s.dressing_room,s.home_club.squad.players,s.current_date+timedelta(days=45))
    assert session.dressing_room==other.dressing_room


def test_reads_and_lineup_experiments_do_not_advance_hierarchy_or_penalize(session):
    before=deepcopy(session.dressing_room)
    states={p.id:deepcopy(p.state) for p in session.home_club.squad.players}
    admin=UIRosterAdmin()
    for _ in range(3):
        dressing_room_read_model(session);squad_read_model(session)
        session.swap_starting_slots('lcm','rcm')
        apply_squad_command(session,{'action':'transfer_status','player_id':session.home_lineup.starters[0].player.id,'status':'transfer_listed'},admin)
    assert session.dressing_room==before
    assert states=={p.id:p.state for p in session.home_club.squad.players}


def test_api_has_no_hidden_personality_numbers_or_player_seed(session):
    payload=json.dumps(dressing_room_read_model(session))
    for name in ['professionalism','ambition','loyalty','pressure_resistance','injury_susceptibility','leadership']:
        assert f'"{name}"' not in payload
    assert 'personality' not in squad_read_model(session)['starters'][0]
    assert dressing_room_read_model(session)['decisions_required'] is False
    assert dressing_room_read_model(session)['automated'] is True


def test_actual_match_appearances_and_overlap_only(session):
    ids=list(session.dressing_room.members)
    a,b,c=ids[:3]
    played={a:45,b:45,c:60}
    intervals={a:((0,45),),b:((45,90),),c:((30,90),)}
    _record(session,1,played=played,intervals=intervals)
    links=session.dressing_room.links
    assert links[tuple(sorted((a,b)))].shared_minutes==0
    assert links[tuple(sorted((a,c)))].shared_minutes==15
    assert links[tuple(sorted((b,c)))].shared_minutes==45
    for pid,member in session.dressing_room.members.items():
        assert member.appearances[-1].minutes==played.get(pid,0)


def test_duplicate_result_is_idempotent(session):
    _record(session,1)
    state=deepcopy(session.dressing_room)
    players=deepcopy([p.state for p in session.home_club.squad.players])
    assert not _record(session,1,days=0)
    assert session.dressing_room==state
    assert [p.state for p in session.home_club.squad.players]==players


@pytest.mark.parametrize('bad',[-1,121,True])
def test_invalid_participation_is_rejected_before_any_change(session,bad):
    state=deepcopy(session.dressing_room)
    ids=list(state.members)
    with pytest.raises(ValueError):
        _record(session,1,played={ids[0]:bad},intervals={})
    assert session.dressing_room==state


def test_omitted_interval_is_not_guessed_from_totals(session):
    _record(session,1,intervals={})
    assert all(link.shared_minutes==0 for link in session.dressing_room.links.values())


def test_sustained_available_absence_mildly_matters_but_single_rotation_does_not(session):
    player=session.home_club.squad.players[-1]
    for n in range(1,4):
        _record(session,n)
        assert participation_concern(session.dressing_room.members[player.id],player,session.current_date)==0
    _record(session,4)
    assert participation_concern(session.dressing_room.members[player.id],player,session.current_date)>0
    player2=session.home_club.squad.players[0]
    assert participation_concern(session.dressing_room.members[player2.id],player2,session.current_date)==0
    all_played={p.id:90 for p in session.home_club.squad.players}
    # Two real appearances dissolve this short-term concern, without a meeting.
    _record(session,5,played=all_played);_record(session,6,played=all_played)
    assert participation_concern(session.dressing_room.members[player.id],player,session.current_date)==0


def test_unavailable_players_are_not_punished_for_missing_matches(session):
    players=session.home_club.squad.players
    eligibility={p.id:i<11 for i,p in enumerate(players)}
    for n in range(1,8):
        _record(session,n,eligible=eligibility)
    for p in players[11:]:
        assert participation_concern(session.dressing_room.members[p.id],p,session.current_date)==0


def test_old_absences_expire_during_offseason(session):
    for n in range(5):
        _record(session,n)
    player=session.home_club.squad.players[-1]
    assert participation_concern(session.dressing_room.members[player.id],player,session.current_date)>0
    session.current_date+=timedelta(days=60);session.update_dressing_room()
    assert participation_concern(session.dressing_room.members[player.id],player,session.current_date)==0


def test_veteran_arrival_starts_low_and_can_climb_automatically(session):
    new=deepcopy(session.home_club.squad.players[0])
    new.identity=replace(new.identity,player_id='veteran-arrival',birth_date=date(1993,1,1))
    new.personality=Personality(95,60,80,85,35,95)
    session.home_club.squad.add(new)
    session.update_dressing_room()
    member=session.dressing_room.members[new.id]
    assert member.tier=='emerging' and member.integration==30
    assert member.influence<50
    initial=member.influence
    for n in range(52):
        _record(session,n,played={p.id:90 for p in session.home_club.squad.players})
    assert member.influence>initial+15
    assert member.tier!='emerging'
    assert any(e.kind=='hierarchy' and new.id in e.player_ids for e in session.dressing_room.events)


def test_support_and_professionalism_help_integration_without_attribute_growth(session):
    elder=deepcopy(session.home_club.squad.players[0]);young=deepcopy(elder)
    elder.identity=replace(elder.identity,player_id='elder',birth_date=date(1992,1,1))
    young.identity=replace(young.identity,player_id='young',birth_date=date(2008,1,1))
    elder.personality=Personality(95,50,80,80,50,95)
    young.personality=Personality(90,50,50,50,50,30)
    alternatives=deepcopy([elder,young]);alternatives[0].personality=replace(elder.personality,leadership=10)
    profiles=[([elder,young],None),(alternatives,None)]
    rooms=[create_dressing_room('test',p,session.current_date) for p,_ in profiles]
    attributes=young.attributes
    for room,(players,_) in zip(rooms,profiles):
        advance_dressing_room(room,players,session.current_date+timedelta(days=60))
    assert rooms[0].members['young'].support_player_id=='elder'
    assert rooms[1].members['young'].support_player_id is None
    assert rooms[0].members['young'].integration>rooms[1].members['young'].integration
    assert young.attributes==attributes


def test_removal_changes_only_close_teammates_and_recovers_without_replacement(session):
    session.current_date+=timedelta(days=90);session.update_dressing_room()
    room=session.dressing_room
    leaving=max(room.members,key=lambda pid:room.members[pid].influence)
    # Set up one observed close tie and unrelated working ties, never all-team
    # grief just because a leader was removed.
    peers=[p for p in room.members if p!=leaving]
    for pid in peers:
        room.links[tuple(sorted((leaving,pid)))].affinity=50
    room.links[tuple(sorted((leaving,peers[0])))].affinity=85
    removed=session.home_club.squad.remove(leaving)
    session.update_dressing_room()
    assert removed.state.dressing_room_morale==0
    assert room.members[peers[0]].departure_disruption>0
    assert all(room.members[pid].departure_disruption==0 for pid in peers[1:])
    assert all(leaving not in pair for pair in room.links)
    assert all(m.support_player_id!=leaving for m in room.members.values())
    for p in session.home_club.squad.players:
        assert -2<=p.state.dressing_room_morale<=2
    session.current_date+=timedelta(days=60);session.update_dressing_room()
    assert room.members[peers[0]].departure_disruption<.03


def test_hierarchy_does_not_recalculate_on_every_day(session):
    original={pid:(m.tier,m.influence) for pid,m in session.dressing_room.members.items()}
    session.current_date+=timedelta(days=6);session.update_dressing_room()
    assert original=={pid:(m.tier,m.influence) for pid,m in session.dressing_room.members.items()}
    session.current_date+=timedelta(days=1);session.update_dressing_room()
    assert original!={pid:(m.tier,m.influence) for pid,m in session.dressing_room.members.items()}
    assert session.dressing_room.last_review==session.current_date


def test_social_morale_is_frozen_once_and_not_double_applied_on_reassignment(session):
    p=session.home_lineup.starters[0].player
    p.state.dressing_room_morale=-2
    snapshot=session._build_snapshot()
    team=snapshot.home_team if snapshot.home_team.club_id==session.home_club.id else snapshot.away_team
    source=next(q for q in team.starters if q.player_id==p.id)
    assert source.state.morale==p.state.effective_morale
    assigned=assign_match_player(source,slot_id=source.assigned_slot_id,position=source.assigned_position,
        role_id=source.role_id,role_name=source.role_name,tactic_id=team.tactic.tactic_id,
        instructions=source.effective_instructions)
    assert assigned.current_rating==pytest.approx(source.current_rating)
    assert assigned.state.morale==source.state.morale


def test_context_small_even_at_the_extreme_and_cannot_change_ovr(session):
    p=session.home_club.squad.players[0]
    for morale in (0,30,65,99,100):
        p.state.morale=morale
        p.state.dressing_room_morale=0
        original=p.current_rating();overall=p.overall_rating
        for offset in (-2,2):
            p.state.dressing_room_morale=offset
            assert abs(p.current_rating().current-original.current)<1
            assert p.overall_rating==overall
            assert 0<=p.state.effective_morale<=100


def test_long_history_is_bounded_and_all_fields_stay_valid(session):
    for n in range(280):
        _record(session,n,days=7,outcome=-1 if n%4 else 1)
    room=session.dressing_room
    room.validate(set(room.members),session.current_date)
    assert len(room.events)<=MAX_EVENTS
    assert len(room.processed_fixtures)<=MAX_FIXTURE_MEMORY
    assert all(len(m.appearances)<=MAX_APPEARANCES for m in room.members.values())
    assert all(-2<=p.state.dressing_room_morale<=2 for p in session.home_club.squad.players)


def test_clock_rejects_backdated_results_and_unreasonable_jump(session):
    previous=deepcopy(session.dressing_room)
    with pytest.raises(ValueError):
        advance_dressing_room(session.dressing_room,session.home_club.squad.players,session.current_date-timedelta(days=1))
    with pytest.raises(ValueError):
        advance_dressing_room(session.dressing_room,session.home_club.squad.players,session.current_date+timedelta(days=366*31))
    assert session.dressing_room==previous


def test_first_week_without_matches_does_not_manufacture_leadership_loss(session):
    before={pid:m.influence for pid,m in session.dressing_room.members.items()}
    session.current_date+=timedelta(days=7);session.update_dressing_room()
    assert all(abs(m.influence-before[pid])<.5 for pid,m in session.dressing_room.members.items())
    assert not [e for e in session.dressing_room.events if e.kind=='hierarchy']
