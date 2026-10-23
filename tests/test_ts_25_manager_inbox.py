"""TS-25 manager inbox regression and persistence tests."""
from __future__ import annotations

from copy import deepcopy
from datetime import date, timedelta
from pathlib import Path

import pytest

from football_manager.dev_ui.session import DevelopmentSession
from football_manager.domain.dressing_room import SocialAppearance
from football_manager.domain.manager_inbox import MAX_MESSAGES
from football_manager.persistence import SQLiteSaveRepository
from football_manager.persistence.manager_career import (
    MANAGER_STATE_VERSION, load_manager_career, save_manager_career, validate_manager_session,
)
from football_manager.services.manager_inbox import (
    conversation, create_manager_inbox, inbox_command, inbox_read_model,
    synchronize_manager_inbox,
)
from football_manager.ui_shell.application import GameApplication
from football_manager.ui_shell.match import prematch_read_model
from football_manager.ui_shell.runtime import UIRuntime


@pytest.fixture(scope='module')
def seed():
    return DevelopmentSession(world_seed=6606)


def player(session):
    return session.home_club.squad.players[0]


def test_bootstrap_contains_no_unsupported_fake_events(seed):
    data = inbox_read_model(seed)
    assert data['source']=='python-manager-inbox'
    # TS-FIX-02 may start with real actionable bids already in the world.
    # These are not invented history and must be visible to the manager.
    assert sum(m['category']=='system' for m in data['messages'])==1
    live={key for key,d in seed._world_squads.transfer_offers.items()
          if seed.home_club.id in (d.buyer_id,d.seller_id)
          and d.status in ('manager_turn','agreed') and d.expires_on>=seed.current_date}
    market=[m for m in seed.manager_inbox.messages if m.category=='market']
    assert len(market)==len(live)
    assert all(any(m.source_key.startswith('offer:'+key+':') for key in live) for m in market)
    assert all(m['category'] in ('system','market') for m in data['messages'])
    assert 'international' not in {m['category'] for m in data['messages']}
    assert len(data['players']) == len(seed.home_club.squad.players)
    validate_manager_session(seed)


def test_injury_and_recovery_events_are_from_actual_state_and_deduplicated(seed):
    session=deepcopy(seed); p=player(session)
    p.state.injury='ankle sprain'
    synchronize_manager_inbox(session)
    assert sum(m.category=='medical' for m in session.manager_inbox.messages)==1
    synchronize_manager_inbox(session)
    assert sum(m.category=='medical' for m in session.manager_inbox.messages)==1
    p.state.injury=None
    synchronize_manager_inbox(session)
    assert sum(m.category=='medical' for m in session.manager_inbox.messages)==2


def test_contract_threshold_alerts_and_reads_are_idempotent(seed):
    session=deepcopy(seed)
    contract=next(c for pid,c in session._world_squads.contracts.items()
                  if pid == player(session).id)
    # Use future in-game date and existing contract, without altering it.
    session.current_date=contract.expires_on-timedelta(days=100)
    session.dressing_room.last_updated=session.current_date  # isolated inbox clock test
    synchronize_manager_inbox(session)
    count=sum(m.category=='contracts' for m in session.manager_inbox.messages)
    assert count>=1
    synchronize_manager_inbox(session)
    assert sum(m.category=='contracts' for m in session.manager_inbox.messages)==count
    mid=session.manager_inbox.messages[-1].message_id
    assert inbox_command(session,{'action':'read','message_id':mid})['status']=='read'
    assert inbox_command(session,{'action':'read','message_id':mid})['status']=='read'
    with pytest.raises(ValueError):
        inbox_command(session,{'action':'read','message_id':mid+999})


def test_repeated_conversations_reduce_effectiveness_without_rating_boost(seed):
    session=deepcopy(seed); p=player(session)
    p.state.form=83
    before=p.state.morale
    first=conversation(session,p.id,'praise')
    second=conversation(session,p.id,'praise')
    third=conversation(session,p.id,'praise')
    assert 0 <= first['morale_delta'] <= .8
    assert second['morale_delta'] <= 0
    assert third['morale_delta'] < 0
    assert p.state.morale-before <= .8
    assert second['pressure']>first['pressure']
    with pytest.raises(ValueError, match='space'):
        conversation(session,p.id,'future')  # fourth conversation the same day is blocked
    assert 35 <= third['trust'] <= 65
    assert session.home_club.squad.players[0].overall_rating == seed.home_club.squad.players[0].overall_rating
    validate_manager_session(session)


def test_a_player_can_be_approached_about_contract_without_renewing(seed):
    session=deepcopy(seed); p=player(session)
    before=session._world_squads.contracts[p.id]
    result=conversation(session,p.id,'future')
    assert 'expires' in result['reaction']
    assert session._world_squads.contracts[p.id] is before
    assert result['morale_delta']==0


def test_minutes_promises_have_one_live_commitment_and_require_real_minutes(seed):
    session=deepcopy(seed); p=player(session)
    reply=conversation(session,p.id,'minutes',promise=True)
    assert reply['active_promise']
    with pytest.raises(ValueError):
        conversation(session,p.id,'minutes',promise=True)
    promise=session.manager_inbox.promises[0]
    base=session.current_date
    member=session.dressing_room.members[p.id]
    member.appearances.extend([
        SocialAppearance('unique-a',base+timedelta(days=14),0,True),
        SocialAppearance('unique-b',base+timedelta(days=28),0,True),
    ])
    session.current_date=base+timedelta(days=56)
    synchronize_manager_inbox(session)
    assert promise.status=='broken' and promise.assessed_on==session.current_date
    assert any(m.category=='conversations' and m.source_key.endswith('broken') for m in session.manager_inbox.messages)
    message_count=len(session.manager_inbox.messages)
    synchronize_manager_inbox(session)
    assert len(session.manager_inbox.messages)==message_count


def test_fewer_than_two_eligible_games_must_not_count_as_keeping_promise(seed):
    session=deepcopy(seed); p=player(session)
    conversation(session,p.id,'minutes',promise=True)
    promise=session.manager_inbox.promises[0]
    session.current_date+=timedelta(days=56)
    synchronize_manager_inbox(session)
    assert promise.status=='active' and promise.extension_count==1
    session.current_date+=timedelta(days=21)
    synchronize_manager_inbox(session)
    assert promise.status=='void'


def test_scouting_news_only_when_real_report_counter_advances(seed):
    session=deepcopy(seed)
    youth=session._world_squads.youth
    if not youth.scouts:
        from football_manager.domain.youth_academy import YouthScout
        scout=YouthScout(scout_id='test-scout-hired', quality=60)
        youth.scouts[scout.scout_id]=scout
    else:
        scout=next(iter(youth.scouts.values()))
    scout.reports_sent+=1
    synchronize_manager_inbox(session)
    assert any(m.category=='scouting' and 'report' in m.title.lower() for m in session.manager_inbox.messages)


def test_save_load_keeps_chat_messages_promise_and_relationship(seed, tmp_path):
    session=deepcopy(seed); p=player(session)
    conversation(session,p.id,'support')
    conversation(session,p.id,'minutes',promise=True)
    repo=SQLiteSaveRepository(tmp_path/'save.sqlite3')
    saved=save_manager_career(repo,slot_id='career',display_name='TS25',session=session,expected_revision=0)
    assert MANAGER_STATE_VERSION>=17  # TS-26 adds version 18 without dropping TS-25 data
    loaded=load_manager_career(repo,'career').session
    assert loaded.manager_inbox.relations[p.id].conversations==2
    assert loaded.manager_inbox.promises[0].status=='active'
    assert [m.source_key for m in loaded.manager_inbox.messages]==[m.source_key for m in session.manager_inbox.messages]
    validate_manager_session(loaded)


def test_game_application_posts_atomic_conversation(seed):
    runtime=UIRuntime(deepcopy(seed))
    service=GameApplication(runtime,prematch_builder=prematch_read_model)
    old=runtime.session
    pid=player(old).id
    result=service.command('inbox.command',{'action':'talk','player_id':pid,'topic':'future'})
    assert result['topic']=='future'
    assert runtime.session is not old
    assert not hasattr(old.manager_inbox,'junk')
    before=len(runtime.session.manager_inbox.messages)
    with pytest.raises(ValueError):
        service.command('inbox.command',{'action':'talk','player_id':'not-on-roster','topic':'future'})
    assert len(runtime.session.manager_inbox.messages)==before


def test_inbox_messages_are_bounded(seed):
    session=deepcopy(seed)
    from football_manager.services.manager_inbox import _notice
    for n in range(MAX_MESSAGES+5):
        _notice(session.manager_inbox,session.current_date,'system','T','B',f'test:{n}')
    validate_manager_session(session)
    assert len(session.manager_inbox.messages)==MAX_MESSAGES
