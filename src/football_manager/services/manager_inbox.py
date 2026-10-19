"""TS-25 real, non-spammy career notifications and manager interactions.

Reads never advance clocks; event generation happens only after committed
world transitions.  No fictional call-ups, reschedules or scout discoveries.
"""
from __future__ import annotations

from datetime import date, timedelta
from football_manager.domain.manager_inbox import (
    InboxMessage, ManagerInbox, ManagerRelation, ManagerPromise, MAX_KEYS, MAX_MESSAGES, TOPICS, PROMISE_KINDS,
)


def _players(session):
    return {p.id: p for p in session.home_club.squad.players}


def _fixtures(session):
    result = {}
    for fixture in session._managed_schedule.values():
        if fixture.match_date >= session.current_date:
            result[fixture.fixture.fixture_id] = fixture.match_date
    return result


def _offers(session):
    cid = session.home_club.id
    return {key: deal.status + ':' + deal.personal_status
            for key, deal in session._world_squads.transfer_offers.items()
            if cid in (deal.seller_id, deal.buyer_id)}


def _scouts(session):
    youth = session._world_squads.youth
    if youth is None:
        return set(), {}
    return set(youth.candidates), {sid: s.reports_sent for sid, s in youth.scouts.items()}


def create_manager_inbox(session) -> ManagerInbox:
    """Start from actual known facts, not an invented message history."""
    now = session.current_date
    players = _players(session)
    found, reports = _scouts(session)
    state = ManagerInbox(session.home_club.id, now, now)
    state.injuries = {pid: p.state.injury for pid, p in players.items() if p.state.injury}
    state.contracts = {pid: c.expires_on.isoformat() for pid, c in session._world_squads.contracts.items()
                       if pid in players}
    state.scouting_candidates, state.scout_report_counts = found, reports
    state.fixtures = _fixtures(session)
    state.results = {key for key, fixture in session._world.fixtures.items()
                     if session.home_club.id in (fixture.home_club_id, fixture.away_club_id)
                     and key in session._world.results}
    state.offers = _offers(session)
    state.social_sequence = session.dressing_room.event_sequence
    if session._world_squads.youth is not None:
        academy = session._world_squads.youth.academies.get(session.home_club.id)
        if academy is not None:
            state.known_sources.update(f'academy:first:{pid}' for pid in academy.graduates)
        state.known_sources.update(
            f'academy:first:{pid}' for pid, club_id in session._world_squads.youth.promoted_to_first.items()
            if club_id == session.home_club.id)
    _notice(state, now, 'system', 'Your manager inbox is ready',
            'Updates here come from actual career events. Discussions with players are optional.',
            'inbox:welcome')
    return state


def _notice(state: ManagerInbox, day: date, category: str, title: str, body: str,
            source: str, *, player_id: str | None = None, reply: bool = False):
    if source in state.known_sources:
        return None
    state.sequence += 1
    msg = InboxMessage(state.sequence, day, category, title[:140], body[:800],
                       source, player_id, requires_reply=reply)
    state.messages.append(msg)
    del state.messages[:-MAX_MESSAGES]
    state.known_sources.add(source)
    if len(state.known_sources) > MAX_KEYS:
        # Retain the keys of live messages and all recent-event deduplication.
        # Old contracts/fixtures are never replayed because snapshots carry
        # their present state; a key aging out does not manufacture new events.
        state.known_sources = {m.source_key for m in state.messages}
    return msg


def _age_relations(state: ManagerInbox, day: date) -> None:
    for relation in state.relations.values():
        start = relation.last_updated or state.started_on
        days = max(0, (day-start).days)
        relation.pressure = max(0., relation.pressure - 1.5*days)
        # Trust drifts slowly toward neutral when there is no contact or action.
        relation.trust = 50 + (relation.trust-50)*(.999**days)
        relation.last_updated = day


def _loan_evidence(session, player_id: str, start: date, due: date) -> bool:
    return any(agreement.player_id == player_id
               and agreement.parent_id == session.home_club.id
               and start <= agreement.started_on <= due
               for agreement in session._world_squads.loans.values())


def _promise_outcome(session, promise: ManagerPromise, player, member) -> str | None:
    """Only documented, committed career actions can satisfy commitments."""
    kind = promise.kind
    if kind == 'renewal':
        contract = session._world_squads.contracts.get(promise.player_id)
        if contract and contract.club_id == session.home_club.id and contract.renewed_on is not None:
            if promise.created_on <= contract.renewed_on <= promise.due_on:
                return 'kept'
    if kind == 'loan_move' and _loan_evidence(session, promise.player_id, promise.created_on, promise.due_on):
        return 'kept'
    now = session.current_date
    if now < promise.due_on:
        return None
    if player is None and kind != 'loan_move':
        return 'void'  # no longer registered, not a manufactured promise success
    if kind in ('playing_time', 'starter_role', 'youth_opportunity'):
        if member is None:
            return 'void'
        games = [a for a in member.appearances
                 if promise.created_on < a.day <= promise.due_on and a.eligible]
        if len(games) < 2:
            if promise.extension_count == 0:
                promise.due_on += timedelta(days=21)
                promise.extension_count = 1
                return None
            return 'void'
        participation = sum(min(90, a.minutes) for a in games) / (90 * len(games))
        if kind == 'youth_opportunity':
            return 'kept' if sum(a.minutes >= 15 for a in games) >= 1 else 'broken'
        threshold = .55 if kind == 'starter_role' else .35
        return 'kept' if participation >= threshold else 'broken'
    # Negotiations/loans cannot be forced onto another club/player.
    return 'broken'


def _assess_promises(session, state: ManagerInbox) -> None:
    now = session.current_date
    roster = _players(session)
    members = session.dressing_room.members
    labels = {'playing_time':'playing-time', 'starter_role':'starting-role',
              'youth_opportunity':'young-player opportunity', 'renewal':'contract-renewal',
              'loan_move':'loan-move'}
    for commitment in state.promises:
        if commitment.status != 'active':
            continue
        player = roster.get(commitment.player_id)
        outcome = _promise_outcome(session, commitment, player, members.get(commitment.player_id))
        if outcome is None:
            continue
        commitment.status, commitment.assessed_on = outcome, now
        rel = state.relations.setdefault(commitment.player_id,
                                         ManagerRelation(commitment.player_id, last_updated=now))
        if outcome == 'kept':
            rel.trust = min(65., rel.trust + 3.)
            if player: player.state.adjust_morale(1.5)
        elif outcome == 'broken':
            rel.trust = max(35., rel.trust - 5.)
            if player: player.state.adjust_morale(-2.5)
        text = {'kept':'Real career events met the commitment.',
                'broken':'The expected real career action did not happen before the deadline.',
                'void':'The commitment ended without a fair opportunity to assess it.'}[outcome]
        _notice(state, now, 'conversations', f'{labels[commitment.kind].capitalize()} promise: {outcome}',
                text, f'promise:{commitment.promise_id}:{outcome}', player_id=commitment.player_id)
    # Bound multi-decade histories without discarding active commitments.
    if len(state.promises) > 900:
        active = [pr for pr in state.promises if pr.status == 'active']
        settled = [pr for pr in state.promises if pr.status != 'active'][-(950-len(active)):]
        state.promises = sorted(active + settled, key=lambda pr: pr.promise_id)


def _pending(state: ManagerInbox, player_id: str | None = None) -> list[InboxMessage]:
    return [m for m in state.messages if m.requires_reply and not m.resolved
            and (player_id is None or m.player_id == player_id)]


def _request_topic(message: InboxMessage) -> str:
    source = message.source_key
    if source.startswith('dressing:') or source.startswith('request:minutes:'):
        return 'minutes'
    if source.startswith('request:contract:'):
        return 'future'
    if source.startswith('request:injury:'):
        return 'recovery'
    return 'support'


def _create_player_requests(session, state: ManagerInbox, players: dict) -> None:
    """Sparse, grounded player-initiated discussions, never random spam."""
    now = session.current_date
    if (now - state.started_on).days < 14:
        return
    if len(_pending(state)) >= 5:
        return
    for pid, player in sorted(players.items()):
        if _pending(state, pid):
            continue
        if len(_pending(state)) >= 5:
            break
        rel = state.relations.get(pid)
        if rel and rel.last_talk and (now - rel.last_talk).days < 12:
            continue
        contract = session._world_squads.contracts.get(pid)
        expiring = contract and contract.club_id == session.home_club.id and 0 <= (contract.expires_on-now).days <= 75
        if expiring and player.personality.ambition >= 65:
            _notice(state, now, 'conversations', f'{player.full_name} wants clarity about the future',
                    'The player has an approaching contract deadline and has asked to discuss plans. '
                    'Any renewal still requires the actual negotiation system.',
                    f'request:contract:{pid}:{contract.expires_on}', player_id=pid, reply=True)
        elif (player.state.morale <= 43 and player.state.form <= 55
              and player.personality.pressure_resistance <= 65
              and pid in session.dressing_room.members
              and (now-session.dressing_room.members[pid].joined_on).days >= 30):
            _notice(state, now, 'conversations', f'{player.full_name} requests a check-in',
                    'The player is struggling with form and morale and would like to speak with you.',
                    f'request:form:{pid}:{now.strftime("%Y-%m")}', player_id=pid, reply=True)


def _expire_requests(session, state: ManagerInbox, players: dict) -> None:
    now = session.current_date
    for message in list(_pending(state)):
        if (now-message.day).days < 28 and message.player_id in players:
            continue
        message.resolved = True
        if message.player_id in players and message.source_key.startswith(('request:', 'dressing:')):
            player = players[message.player_id]
            player.state.adjust_morale(-.5)
            rel = state.relations.setdefault(message.player_id,
                                             ManagerRelation(message.player_id, last_updated=now))
            rel.trust = max(35., rel.trust - .8)
            _notice(state, now, 'conversations', 'Unanswered player request expired',
                    f'{player.full_name} moved on after waiting for a discussion.',
                    f'request-expired:{message.message_id}', player_id=message.player_id)


def synchronize_manager_inbox(session) -> None:
    state = session.manager_inbox
    now = session.current_date
    if now < state.last_synced:
        raise ValueError('cannot rewind inbox clock')
    _age_relations(state, now)
    players = _players(session)

    injuries = {pid: p.state.injury for pid, p in players.items() if p.state.injury}
    for pid in sorted(set(state.injuries) | set(injuries)):
        before, after = state.injuries.get(pid), injuries.get(pid)
        if before == after or pid not in players:
            continue
        who = players[pid].full_name
        if after:
            _notice(state, now, 'medical', f'Injury: {who}', f'{who} is unavailable: {after}.',
                    f'injury:{pid}:{now}:on:{after}', player_id=pid)
            if (players[pid].personality.pressure_resistance < 45
                    and players[pid].state.morale < 55 and len(_pending(state)) < 4):
                _notice(state, now, 'conversations', f'{who} requests a recovery check-in',
                        f'The player would like to discuss the recorded injury: {after}.',
                        f'request:injury:{pid}:{now}:{after}', player_id=pid, reply=True)
        else:
            _notice(state, now, 'medical', f'{who} returns to availability',
                    f'The injury recorded for {who} has cleared.', f'injury:{pid}:{now}:off', player_id=pid)
    state.injuries = injuries
    # A relapse keeps the same injury label; the ordinary injury diff cannot
    # detect it, so surface the confirmed TS-26 outcome exactly once.
    support = session._world_squads.club_support.get(session.home_club.id)
    if support is not None:
        for pid, decision in support.treatments.items():
            if pid in players and decision.status == 'relapsed':
                _notice(state, now, 'medical', f'Rehabilitation setback: {players[pid].full_name}',
                        'The early-return treatment led to a setback. The medical centre has updated the recovery date.',
                        f'treatment:relapse:{decision.episode_id}', player_id=pid)
                rel = state.relations.get(pid)
                # Only apply consequences once, when creating the notice.
                if rel is not None and not any(m.source_key == f'treatment:relapse:trust:{decision.episode_id}' for m in state.messages):
                    rel.trust = max(35., rel.trust - 1.5)
                    players[pid].state.morale = max(1., players[pid].state.morale - .8)
                    _notice(state, now, 'conversations', f'{players[pid].full_name} is frustrated',
                            'The failed accelerated rehabilitation has damaged confidence slightly.',
                            f'treatment:relapse:trust:{decision.episode_id}', player_id=pid)

    # Manager staff need only occasional expiry reminders, not a weekly chore.
    # AI clubs extend their existing personnel automatically in the month-end
    # financial review; the human manager can always renew or release staff.
    if support is not None:
        for staff in support.members.values():
            remaining = (staff.contract_until - now).days
            if 0 <= remaining <= 120:
                stage = 14 if remaining <= 14 else 45 if remaining <= 45 else 120
                _notice(state, now, 'contracts', f'Staff contract expiring: {staff.name}',
                        f'{staff.name} ({staff.role}) has {remaining} days remaining. Renew in Staff if desired.',
                        f'staff:expiry:{staff.member_id}:{staff.contract_until}:{stage}')

    contracts = {pid: c.expires_on.isoformat() for pid, c in session._world_squads.contracts.items()
                 if pid in players}
    for pid, expiration in sorted(contracts.items()):
        previous = state.contracts.get(pid)
        if previous and previous != expiration and expiration > previous:
            _notice(state, now, 'contracts', f'Contract extended: {players[pid].full_name}',
                    f'The registered contract expiry moved from {previous} to {expiration}.',
                    f'contract:renewed:{pid}:{expiration}', player_id=pid)
    state.contracts = contracts
    for pid, expiration in sorted(contracts.items()):
        days = (date.fromisoformat(expiration)-now).days
        if days < 0 or days > 180:
            continue
        # Thresholds, not a daily avalanche of reminders.
        stage = 30 if days <= 30 else 90 if days <= 90 else 180
        _notice(state, now, 'contracts', f'Contract watch: {players[pid].full_name}',
                f'{players[pid].full_name} has {days} days remaining. Contract discussions do not renew it automatically.',
                f'contract:{pid}:{expiration}:{stage}', player_id=pid)

    candidates, reports = _scouts(session)
    youth = session._world_squads.youth
    new_candidates = [pid for pid in sorted(candidates - state.scouting_candidates)
                      if youth is not None and pid in youth.candidates]
    if new_candidates:
        sample = ', '.join(youth.candidates[pid].preview.full_name for pid in new_candidates[:3])
        from hashlib import sha256
        signature = sha256('\0'.join(new_candidates).encode('utf-8')).hexdigest()[:14]
        _notice(state, now, 'scouting', 'Youth scout discoveries',
                f'{len(new_candidates)} genuine scouting candidates added: {sample}. See Youth Academy for the actual reports.',
                f'scout:candidates:{now}:{signature}')
    for sid, total in sorted(reports.items()):
        if total > state.scout_report_counts.get(sid, 0):
            _notice(state, now, 'scouting', 'Your scout has reported',
                    f'{sid} delivered {total-state.scout_report_counts.get(sid,0)} new report(s). Open Youth Academy to review discoveries.',
                    f'scout:reports:{sid}:{total}')
    state.scouting_candidates, state.scout_report_counts = candidates, reports
    if youth is not None:
        academy = youth.academies.get(session.home_club.id)
        academy_promoted = set(academy.graduates) if academy is not None else set()
        manually_promoted = {pid for pid, cid in youth.promoted_to_first.items()
                             if cid == session.home_club.id}
        for pid in sorted(academy_promoted | manually_promoted):
            key = f'academy:first:{pid}'
            member = session.dressing_room.members.get(pid)
            if (pid in players and member is not None
                    and 0 <= (now-member.joined_on).days <= 2):
                _notice(state, now, 'academy', 'Academy player joins the first team',
                        f'{players[pid].full_name} was registered with the senior squad.',
                        key, player_id=pid)
            else:
                # Historical graduations from an existing save are not new alerts.
                state.known_sources.add(key)

    upcoming = _fixtures(session)
    for fid, when in sorted(upcoming.items()):
        previous = state.fixtures.get(fid)
        if previous is not None and previous != when:
            _notice(state, now, 'calendar', 'Fixture rescheduled',
                    f'{fid} moved from {previous.isoformat()} to {when.isoformat()} in the actual career calendar.',
                    f'fixture:{fid}:{when}')
    state.fixtures = upcoming

    cid = session.home_club.id
    matches = {key for key, fixture in session._world.fixtures.items()
               if cid in (fixture.home_club_id, fixture.away_club_id) and key in session._world.results}
    for fid in sorted(matches-state.results):
        fixture = session._world.fixtures[fid]
        score = session._world.results[fid]
        home = session._world_club_names.get(fixture.home_club_id, fixture.home_club_id)
        away = session._world_club_names.get(fixture.away_club_id, fixture.away_club_id)
        _notice(state, now, 'results', 'Match result recorded',
                f'{home} {score.home_goals}-{score.away_goals} {away}. Official result in the career ledger.',
                f'result:{fid}')
    state.results = matches

    offers = _offers(session)
    for deal_id, status in sorted(offers.items()):
        if status != state.offers.get(deal_id):
            _notice(state, now, 'market', 'Transfer negotiation update',
                    f'Negotiation {deal_id}: {status.replace(":", ", personal status ")}. Review Transfers for the real terms.',
                    f'offer:{deal_id}:{status}')
    state.offers = offers

    # Headline moves elsewhere in the world only when a real transfer was
    # completed and the fee is sizeable; older historical moves are not replayed.
    global_moves = [deal for deal in session._world_squads.transfer_offers.values()
                    if deal.status == 'completed' and deal.terms.fixed_gbp >= 5_000_000
                    and session.home_club.id not in (deal.seller_id, deal.buyer_id)
                    and deal.started_on >= state.started_on and deal.personal_events
                    and 0 <= (now-deal.personal_events[-1].on_date).days <= 21]
    for deal in sorted(global_moves, key=lambda item:(item.personal_events[-1].on_date, item.deal_id))[-5:]:
        source = f'world-transfer:{deal.deal_id}'
        # Reports are grounded in completed transactions, never preliminary bids.
        seller = session._world_club_names.get(deal.seller_id, deal.seller_id)
        buyer = session._world_club_names.get(deal.buyer_id, deal.buyer_id)
        _notice(state, now, 'market', 'Major transfer completed',
                f'{seller} sold a player to {buyer} for GBP {deal.terms.fixed_gbp:,}.', source)
    for loan_id, loan in sorted(session._world_squads.loans.items()):
        if session.home_club.id not in (loan.parent_id, loan.borrower_id):
            continue
        if loan.started_on >= state.started_on:
            _notice(state, now, 'market', 'Player loan recorded',
                    f'Loan {loan_id}: {loan.parent_id} to {loan.borrower_id} until {loan.ends_on}.',
                    f'loan:{loan_id}:{loan.started_on}')
        if loan.completed_on is not None and loan.completed_on >= state.started_on:
            _notice(state, now, 'market', 'Player loan completed',
                    f'Loan {loan_id} ended with status {loan.status}.',
                    f'loan:complete:{loan_id}:{loan.completed_on}:{loan.status}')

    if state.social_sequence > session.dressing_room.event_sequence:
        state.social_sequence = 0  # a freshly re-established squad history
    relevant_events = [e for e in session.dressing_room.events if e.sequence > state.social_sequence]
    for event in relevant_events[-12:]:  # don't flood the inbox during long simulations
        pid = next((identifier for identifier in event.player_ids if identifier in players), None)
        if event.kind == 'participation' and pid:
            if not _pending(state, pid):
                _notice(state, now, 'dressing_room', 'A player is concerned about playing time',
                        event.message, f'dressing:{event.sequence}:{event.day}', player_id=pid, reply=True)
        elif event.kind in ('arrival', 'departure', 'hierarchy', 'integration'):
            _notice(state, now, 'dressing_room', 'Squad atmosphere update',
                    event.message, f'social:{event.sequence}:{event.day}', player_id=pid)
    state.social_sequence = session.dressing_room.event_sequence
    _expire_requests(session, state, players)
    _create_player_requests(session, state, players)
    _assess_promises(session, state)
    state.last_synced = now


def conversation_options():
    return [
        {'id':'praise', 'label':'Praise recent form'},
        {'id':'support', 'label':'Offer support during a difficult period'},
        {'id':'future', 'label':'Discuss contract and future',
         'promise_kind':'renewal', 'promise_label':'Commit to reaching a renewal by the deadline'},
        {'id':'minutes', 'label':'Discuss playing time',
         'promise_kind':'playing_time', 'promise_label':'Promise meaningful minutes over eight weeks'},
        {'id':'role', 'label':'Clarify first-team role',
         'promise_kind':'starter_role', 'promise_label':'Promise regular starts/majority minutes'},
        {'id':'criticism', 'label':'Address a poor run of form'},
        {'id':'development', 'label':'Discuss development and opportunities',
         'promise_kind':'youth_opportunity', 'promise_label':'Promise a real first-team opportunity'},
        {'id':'leadership', 'label':'Ask a leader to support the squad'},
        {'id':'loan', 'label':'Explore an outgoing loan',
         'promise_kind':'loan_move', 'promise_label':'Commit to arranging a real loan'},
        {'id':'transfer', 'label':'Discuss a potential transfer'},
        {'id':'recovery', 'label':'Check in during injury recovery'},
    ]


PROMISE_TOPICS = {'minutes':'playing_time', 'role':'starter_role', 'future':'renewal',
                  'development':'youth_opportunity', 'loan':'loan_move'}


def conversation(session, player_id: str, topic: str, *, promise: bool = False,
                 promise_kind: str | None = None) -> dict:
    if topic not in TOPICS or type(promise) is not bool:
        raise ValueError('Unsupported conversation option')
    if promise_kind is not None and (not isinstance(promise_kind, str)
                                     or promise_kind != PROMISE_TOPICS.get(topic)):
        raise ValueError('Incompatible commitment for conversation topic')
    if promise and topic != 'minutes':
        raise ValueError('Legacy playing-time promise only applies to minutes talks')
    kind = promise_kind or ('playing_time' if promise else None)
    players = _players(session)
    player = players.get(player_id)
    if player is None:
        raise ValueError('Player is not registered at the managed club')
    day = session.current_date
    state = session.manager_inbox
    rel = state.relations.setdefault(player_id, ManagerRelation(player_id, last_updated=day))
    _age_relations(state, day)
    if kind and any(p.player_id == player_id and p.status == 'active' for p in state.promises):
        raise ValueError('An active commitment to this player already exists')
    if kind == 'youth_opportunity' and player.age_on(day) > 21:
        raise ValueError('A youth opportunity is available only for players aged 21 or younger')
    if kind == 'renewal' and not session._world_squads.contracts.get(player_id):
        raise ValueError('An existing contract is required to promise renewal')
    if kind == 'loan_move' and any(loan.player_id == player_id and loan.status == 'active'
                                   for loan in session._world_squads.loans.values()):
        raise ValueError('A loan is already in progress for this player')
    today_count = sum(m.category == 'conversations' and m.day == day
                      and m.source_key.startswith(f'talk:{player_id}:') for m in state.messages)
    if today_count >= 3:
        raise ValueError('The player needs space after several conversations today')
    age = (day-rel.last_talk).days if rel.last_talk else 99
    repeat = (day-rel.last_topics[topic]).days if topic in rel.last_topics else 99
    sensitivity = player.personality.pressure_resistance / 100
    extra_pressure = (25 if age < 3 else 12 if age < 8 else 0) + (18 if repeat < 14 else 0)
    rel.pressure = min(100., rel.pressure + 7 + extra_pressure)
    overwhelmed = rel.pressure > (51 + 18*sensitivity)
    professional = player.personality.professionalism / 100
    morale = player.state.morale
    if topic == 'praise':
        supported = player.state.form >= 70
        effect = .7 if supported else -.25
        description = 'The praise was appreciated.' if supported else 'The praise felt unearned.'
    elif topic == 'support':
        supported = morale < 75 or player.state.injury is not None
        effect = .65 if supported else .1
        description = 'The player appreciated the support.' if supported else 'The player did not need reassurance.'
    elif topic == 'criticism':
        supported = player.state.form < 58
        effect = (.25 if professional >= .6 else -.5) if supported else -1.1
        description = 'The player reflected on the feedback.' if supported and professional >= .6 else 'The criticism was not welcomed.'
    elif topic == 'future':
        contract = session._world_squads.contracts.get(player_id)
        days = (contract.expires_on-day).days if contract else None
        description = (f'The contract expires in {days} days. The player is willing to discuss plans, '
                       'but a renewal requires the actual contract process.' if days is not None
                       else 'You discussed future plans. Contractual status remains unchanged.')
        effect = 0.0
    elif topic == 'role':
        description, effect = 'You discussed first-team expectations. Selections matter more than words.', .15
    elif topic == 'minutes':
        description, effect = 'You discussed playing time. Actual match appearances will determine satisfaction.', .2
    elif topic == 'development':
        description, effect = 'You discussed progress and opportunities; development and appearances remain decisive.', .25
    elif topic == 'loan':
        description, effect = 'A potential loan was discussed; a real loan deal must still be arranged.', 0.
    elif topic == 'transfer':
        description, effect = 'The player understands the club may consider offers. No transfer was authorized.', -.1 if player.personality.loyalty > 75 else 0.
    elif topic == 'leadership':
        member = session.dressing_room.members.get(player_id)
        leading = member and member.tier in ('leaders','influential') and player.personality.leadership >= 65
        description = ('The established player is receptive to setting an example.' if leading
                       else 'The player does not yet feel ready to lead teammates.')
        effect = .25 if leading else -.1
    else:
        injured = player.state.injury is not None
        description = ('The player appreciated being checked on during recovery.' if injured
                       else 'The player is currently healthy and did not need a medical check-in.')
        effect = .5 if injured else -.1
    if overwhelmed:
        effect = min(effect, -.7)
        description = 'The player feels overwhelmed by too many conversations. ' + description
    elif repeat < 8:
        effect = min(effect, 0.)
        description = 'This topic was raised again too soon. ' + description
    elif topic == 'leadership' and effect > 0:
        # At most three small, genuine settling-in boosts among teammates who
        # already have a working link with this leader. Never change ability,
        # match results, money, or anyone else's base morale.
        supported = 0
        for teammate_id, teammate in sorted(session.dressing_room.members.items()):
            if supported == 3:
                break
            link = session.dressing_room.links.get(tuple(sorted((player_id, teammate_id))))
            if (teammate_id != player_id and teammate.integration < 55
                    and link is not None and link.affinity >= 50):
                teammate.integration = min(100., teammate.integration + .3)
                supported += 1
        if supported:
            description += f' {supported} unsettled teammate(s) received modest support.'
    # Relationships influence how later feedback is received, never contract
    # consent or player ability; the total conversation effect stays tiny.
    if not overwhelmed and repeat >= 8:
        if rel.trust >= 57 and topic in ('support', 'development', 'role', 'recovery'):
            effect += .12
        elif rel.trust <= 43 and topic in ('criticism', 'role', 'transfer'):
            effect -= .15
    effect = max(-1.25, min(.8, effect))
    player.state.adjust_morale(effect)
    trust_delta = max(-2., min(1.1, effect * 1.5))
    rel.trust = max(35., min(65., rel.trust + trust_delta))
    rel.conversations += 1
    rel.last_talk = day
    rel.last_topics[topic] = day
    rel.last_updated = day
    if kind:
        due = day + timedelta(days=70 if kind in ('starter_role','loan_move') else 90 if kind == 'renewal'
                              else 56)
        commitment = ManagerPromise(state.next_promise_id, player_id, day, due, kind=kind)
        state.next_promise_id += 1
        state.promises.append(commitment)
        description += f' You made a {kind.replace("_", "-")} commitment until {due.isoformat()}.'
    for m in _pending(state, player_id):
        # Talking about unrelated matters must not dismiss a real player request.
        if topic == _request_topic(m) or (topic == 'support' and _request_topic(m) == 'recovery'):
            m.resolved, m.read = True, True
    _notice(state, day, 'conversations', f'Conversation with {player.full_name}',
            f'{topic.capitalize()}: {description}',
            f'talk:{player_id}:{rel.conversations}', player_id=player_id)
    return {'player_id':player_id, 'name':player.full_name, 'topic':topic,
            'reaction':description, 'morale_delta':round(effect,2),
            'trust':round(rel.trust,1), 'pressure':round(rel.pressure,1),
            'active_promise':kind is not None, 'promise_kind':kind}


def respond_to_request(session, message_id: int, choice: str) -> dict:
    if type(message_id) is not int:
        raise ValueError('Valid request ID required')
    state = session.manager_inbox
    message = next((item for item in _pending(state) if item.message_id == message_id), None)
    if message is None:
        raise ValueError('Player request was already handled or does not exist')
    if message.player_id not in _players(session):
        raise ValueError('The requesting player is no longer registered')
    if choice == 'discuss':
        # Use the same grounded, anti-spam conversation path as voluntary talks.
        reply = conversation(session, message.player_id, _request_topic(message))
        return {'updated':message_id, 'status':'discussed', **reply}
    if choice != 'decline':
        raise ValueError('Unknown response choice')
    player = _players(session)[message.player_id]
    rel = state.relations.setdefault(player.id, ManagerRelation(player.id, last_updated=session.current_date))
    player.state.adjust_morale(-.55)
    rel.trust = max(35., rel.trust - .9)
    message.read, message.resolved = True, True
    _notice(state, session.current_date, 'conversations', f'Request declined: {player.full_name}',
            'You explained that you cannot meet the request. The player may be disappointed.',
            f'request-declined:{message_id}', player_id=player.id)
    return {'updated':message_id, 'status':'declined', 'morale_delta':-.55,
            'trust':round(rel.trust,1)}


def inbox_command(session, command: dict) -> dict:
    action = command.get('action')
    state = session.manager_inbox
    if action == 'talk':
        return conversation(session, command.get('player_id'), command.get('topic'),
                            promise=command.get('promise', False),
                            promise_kind=command.get('promise_kind'))
    if action == 'respond':
        return respond_to_request(session, command.get('message_id'), command.get('choice'))
    if action in ('read', 'resolve'):
        mid = command.get('message_id')
        if type(mid) is not int:
            raise ValueError('Valid inbox message ID required')
        target = next((m for m in state.messages if m.message_id == mid), None)
        if target is None:
            raise ValueError('Inbox message not found')
        target.read = True
        if action == 'resolve':
            if target.requires_reply:
                raise ValueError('Respond to the player through a conversation instead')
            target.resolved = True
        return {'updated':mid, 'status':'resolved' if target.resolved else 'read'}
    raise ValueError('Unknown inbox command')


def inbox_read_model(session) -> dict:
    state = session.manager_inbox
    active = _players(session)
    records = []
    for m in reversed(state.messages):
        records.append({'id':m.message_id, 'date':m.day.isoformat(), 'category':m.category,
                        'title':m.title, 'body':m.body, 'source_key':m.source_key, 'player_id':m.player_id,
                        'read':m.read, 'requires_reply':m.requires_reply, 'resolved':m.resolved,
                        'suggested_topic':_request_topic(m) if m.requires_reply else None,
                        'decision_due':(m.day+timedelta(days=28)).isoformat() if m.requires_reply and not m.resolved else None})
    players = []
    for pid, p in sorted(active.items(), key=lambda item:item[1].full_name):
        rel = state.relations.get(pid)
        contract = session._world_squads.contracts.get(pid)
        players.append({'id':pid, 'name':p.full_name,
                        'position':p.primary_position.value,
                        'morale':round(p.state.effective_morale,1),
                        'trust':round(rel.trust,1) if rel else 50.,
                        'pressure':round(rel.pressure,1) if rel else 0.,
                        'contract_until':contract.expires_on.isoformat() if contract else None,
                        'active_promise':any(pr.player_id==pid and pr.status=='active' for pr in state.promises),
                        'promise_kinds':[pr.kind for pr in state.promises if pr.player_id==pid and pr.status=='active'],
                        'pending_requests':sum(m.player_id==pid for m in _pending(state))})
    return {'source':'python-manager-inbox', 'date':session.current_date.isoformat(),
            'club':session.home_club.name, 'unread':sum(not m.read for m in state.messages),
            'requests':sum(m.requires_reply and not m.resolved for m in state.messages),
            'messages':records, 'players':players, 'topics':conversation_options(),
            'active_promises':[{'id':pr.promise_id,'player_id':pr.player_id,'kind':pr.kind,
                                'due':pr.due_on.isoformat()} for pr in state.promises if pr.status=='active'],
            'notice':'Only implemented world events are reported; international call-ups are not simulated yet.'}
