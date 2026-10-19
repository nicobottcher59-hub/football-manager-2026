"""TS-25.2: verify requests, real commitments, deduplication and moderate effects."""
from __future__ import annotations

from copy import deepcopy
from dataclasses import replace
from datetime import timedelta

import pytest

from football_manager.dev_ui.session import DevelopmentSession
from football_manager.domain.dressing_room import SocialAppearance
from football_manager.domain.loan_market import LoanAgreement
from football_manager.persistence.manager_career import validate_manager_session
from football_manager.services.club_economy import _date_plus_months
from football_manager.services.manager_inbox import (
    conversation, conversation_options, inbox_command, inbox_read_model,
    synchronize_manager_inbox,
)


@pytest.fixture(scope='module')
def seed():
    return DevelopmentSession(world_seed=6606)


def fresh(seed):
    return deepcopy(seed)


def test_topics_all_have_grounded_commitments(seed):
    choices = conversation_options()
    assert {x['id'] for x in choices} >= {'praise','support','minutes','future','role',
                                             'loan','transfer','development','leadership','recovery'}
    assert {x['promise_kind'] for x in choices if 'promise_kind' in x} == {
        'renewal','playing_time','starter_role','youth_opportunity','loan_move',
    }
    validate_manager_session(seed)


def test_unsupported_commitment_is_rejected_without_mutation(seed):
    session = fresh(seed)
    p = session.home_club.squad.players[0]
    old = p.state.morale
    with pytest.raises(ValueError):
        conversation(session,p.id,'praise',promise_kind='renewal')
    assert p.state.morale == old
    assert not session.manager_inbox.promises


def test_starter_role_promise_requires_real_majority_minutes(seed):
    session=fresh(seed)
    p=session.home_club.squad.players[0]
    event=conversation(session,p.id,'role',promise_kind='starter_role')
    assert event['promise_kind']=='starter_role'
    commitment=session.manager_inbox.promises[-1]
    begin=session.current_date
    member=session.dressing_room.members[p.id]
    member.appearances.extend([
        SocialAppearance('starter-a',begin+timedelta(days=7),85,True),
        SocialAppearance('starter-b',begin+timedelta(days=21),80,True),
    ])
    session.current_date=begin+timedelta(days=70)
    synchronize_manager_inbox(session)
    assert commitment.status=='kept'
    assert session.manager_inbox.relations[p.id].trust<=65


def test_starter_role_does_not_reward_zero_minutes(seed):
    session=fresh(seed);p=session.home_club.squad.players[0]
    conversation(session,p.id,'role',promise_kind='starter_role')
    begin=session.current_date
    session.dressing_room.members[p.id].appearances.extend([
        SocialAppearance('bench-a',begin+timedelta(days=5),0,True),
        SocialAppearance('bench-b',begin+timedelta(days=18),0,True),
    ])
    session.current_date+=timedelta(days=70)
    synchronize_manager_inbox(session)
    assert session.manager_inbox.promises[0].status=='broken'


def test_renewal_promise_needs_signed_extension(seed):
    session=fresh(seed);p=session.home_club.squad.players[0]
    contract=session._world_squads.contracts[p.id]
    conversation(session,p.id,'future',promise_kind='renewal')
    session.current_date+=timedelta(days=30)
    synchronize_manager_inbox(session)
    assert session.manager_inbox.promises[0].status=='active'
    updated=replace(contract,expires_on=contract.expires_on+timedelta(days=365),
                    renewed_on=session.current_date)
    session._world_squads.contracts[p.id]=updated
    synchronize_manager_inbox(session)
    assert session.manager_inbox.promises[0].status=='kept'
    assert any(m.source_key.startswith('contract:renewed:') for m in session.manager_inbox.messages)


def test_loan_promise_needs_actual_outgoing_loan(seed):
    session=fresh(seed);p=session.home_club.squad.players[0]
    event=conversation(session,p.id,'loan',promise_kind='loan_move')
    assert event['active_promise']
    start=session.current_date+timedelta(days=3)
    other=next(cid for cid in session._world_squads.clubs if cid!=session.home_club.id)
    loan=LoanAgreement('ts252-test-loan',p.id,session.home_club.id,other,
                       start,_date_plus_months(start,6),50,'rotation')
    session._world_squads.loans[loan.loan_id]=loan
    session.current_date=start
    synchronize_manager_inbox(session)
    assert session.manager_inbox.promises[0].status=='kept'
    assert any(m.source_key.startswith('loan:') for m in session.manager_inbox.messages)


def test_player_can_request_contract_meeting_and_be_declined(seed):
    session=fresh(seed)
    player=next((p for p in session.home_club.squad.players if p.personality.ambition>=65),None)
    assert player is not None
    contract=session._world_squads.contracts[player.id]
    today=session.current_date+timedelta(days=20)
    session._world_squads.contracts[player.id]=replace(contract,expires_on=today+timedelta(days=60))
    session.current_date=today
    synchronize_manager_inbox(session)
    requests=[m for m in session.manager_inbox.messages if m.requires_reply and m.player_id==player.id]
    assert len(requests)==1
    request=requests[0]
    assert request.source_key.startswith('request:contract:')
    before=player.state.morale
    result=inbox_command(session,{'action':'respond','message_id':request.message_id,'choice':'decline'})
    assert result['status']=='declined' and request.resolved
    assert before-player.state.morale<=1
    with pytest.raises(ValueError):
        inbox_command(session,{'action':'respond','message_id':request.message_id,'choice':'decline'})
    before_count=len(session.manager_inbox.messages)
    synchronize_manager_inbox(session)
    assert len(session.manager_inbox.messages)==before_count


def test_unrelated_chat_does_not_close_pending_request(seed):
    session=fresh(seed)
    p=next(p for p in session.home_club.squad.players if p.personality.ambition>=65)
    session.current_date+=timedelta(days=20)
    contract=session._world_squads.contracts[p.id]
    session._world_squads.contracts[p.id]=replace(contract,expires_on=session.current_date+timedelta(days=70))
    synchronize_manager_inbox(session)
    target=next(m for m in session.manager_inbox.messages if m.requires_reply and m.player_id==p.id)
    conversation(session,p.id,'praise')
    assert not target.resolved
    response=inbox_command(session,{'action':'respond','message_id':target.message_id,'choice':'discuss'})
    assert response['status']=='discussed' and target.resolved
    assert response['topic']=='future'


def test_request_expiry_has_one_small_effect(seed):
    session=fresh(seed)
    p=next(p for p in session.home_club.squad.players if p.personality.ambition>=65)
    session.current_date+=timedelta(days=20)
    contract=session._world_squads.contracts[p.id]
    session._world_squads.contracts[p.id]=replace(contract,expires_on=session.current_date+timedelta(days=60))
    synchronize_manager_inbox(session)
    request=next(m for m in session.manager_inbox.messages if m.requires_reply and m.player_id==p.id)
    before=p.state.morale
    session.current_date+=timedelta(days=29)
    synchronize_manager_inbox(session)
    assert request.resolved and 0 <= before-p.state.morale <= 1
    notices=sum(m.source_key.startswith('request-expired:') for m in session.manager_inbox.messages)
    synchronize_manager_inbox(session)
    assert notices==1==sum(m.source_key.startswith('request-expired:') for m in session.manager_inbox.messages)


def test_inbox_read_model_includes_actions_and_promises(seed):
    session=fresh(seed);p=session.home_club.squad.players[0]
    conversation(session,p.id,'minutes',promise_kind='playing_time')
    payload=inbox_read_model(session)
    assert payload['active_promises'][0]['kind']=='playing_time'
    assert any(entry['promise_kinds']==['playing_time'] for entry in payload['players'])
    assert any(item['category']=='conversations' for item in payload['messages'])
    validate_manager_session(session)
