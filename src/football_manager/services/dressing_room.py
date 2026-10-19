"""Automatic, non-blocking dressing room progression (TS-20).

One social contribution enters the existing morale channel. It is REPLACED,
not accumulated, and never changes base morale, confidence, chemistry, ability,
injury status or football formulas. Clock updates use actual calendar days;
only committed matches count as appearances. Reading a screen does nothing.
"""
from __future__ import annotations

from datetime import date, timedelta
from hashlib import sha256
from itertools import combinations
from math import exp
from typing import Iterable, Mapping

from football_manager.domain.dressing_room import (
    DressingRoomState, SocialMember, SocialLink, SocialAppearance, SocialEvent,
    MAX_EVENTS, MAX_APPEARANCES, MAX_FIXTURE_MEMORY, MAX_MORALE_EFFECT,
    TIER_LABELS, TIERS, require_day,
)
from football_manager.domain.player import Player


def clamp(value: float, low: float = 0.0, high: float = 100.0) -> float:
    return max(low, min(high, value))


def roster(players: Iterable[Player]) -> dict[str, Player]:
    values = list(players)
    result = {p.id: p for p in values}
    if len(values) != len(result):
        raise ValueError('duplicate social player IDs')
    return dict(sorted(result.items()))


def _tier(score: float) -> str:
    return ('leaders' if score >= 76 else 'influential' if score >= 64
            else 'core' if score >= 50 else 'emerging')


def _base_influence(player: Player, integration: float) -> float:
    m = player.attributes.mental
    return .55 * player.personality.leadership + .20 * m.teamwork + .15 * m.composure + .10 * integration


def _initial_link(a: str, b: str, *, new: bool = False) -> SocialLink:
    # Modest, unlabelled initial working rapport, not fabricated historical
    # friendship. Stable per pair, with no dependence on names/nationality/age.
    key = '\0'.join((a, b)).encode('utf-8')
    variation = sha256(b'fm-rapport-v1:' + key).digest()[0] / 255
    return SocialLink(a, b, (43.0 if new else 49.0) + 8 * variation)


def create_dressing_room(club_id: str, players: Iterable[Player], on_date: date) -> DressingRoomState:
    """Neutral new-game/migration baseline; never invent prior appearances."""
    require_day(on_date)
    current = roster(players)
    state = DressingRoomState(club_id, on_date, on_date, on_date)
    for pid, player in current.items():
        influence = _base_influence(player, 65.0)
        state.members[pid] = SocialMember(pid, on_date, influence=influence,
            previous_influence=influence, tier=_tier(influence), tier_since=on_date)
        player.state.dressing_room_morale = 0.0
    state.links = {pair: _initial_link(*pair) for pair in combinations(current, 2)}
    state.validate(set(current), on_date)
    return state


def _event(state: DressingRoomState, kind: str, day: date, ids: tuple[str, ...], message: str) -> None:
    state.event_sequence += 1
    state.events.append(SocialEvent(state.event_sequence, day, kind, ids, message))
    del state.events[:-MAX_EVENTS]


def sync_roster(state: DressingRoomState, players: Iterable[Player]) -> bool:
    """Reconcile a completed squad registration change on the current room day.

    Transfer/loan UI flags are deliberately irrelevant. Real transfer services
    must call this after registering/unregistering, on that event's date.
    """
    current = roster(players)
    added = set(current) - set(state.members)
    removed = set(state.members) - set(current)
    if not added and not removed:
        return False
    day = state.last_updated
    for pid in sorted(removed):
        leaving = state.members[pid]
        # A familiar influential departure can matter; an ordinary registration
        # correction or a recently arrived player cannot upset everyone.
        influential = leaving.influence >= 64 and (day - leaving.joined_on).days >= 28
        affected = []
        if influential:
            for other in sorted(set(current) & set(state.members)):
                link = state.links.get(tuple(sorted((pid, other))))
                if link is None or link.affinity < 60:
                    continue
                member = state.members[other]
                loyalty = current[other].personality.loyalty / 100
                disruption = min(1.0, (link.affinity - 50) / 40 * (.5 + .5 * loyalty))
                member.departure_disruption = max(member.departure_disruption, disruption)
                affected.append(other)
        if affected:
            _event(state, 'departure', day, (pid, *affected),
                'An influential departure has unsettled some close teammates. The effect is small and temporary.')
    for pid in removed:
        del state.members[pid]
    for pair in list(state.links):
        if set(pair) & removed:
            del state.links[pair]
    for member in state.members.values():
        if member.support_player_id in removed:
            member.support_player_id = None
    for pid in sorted(added):
        player = current[pid]
        # Leadership potential persists on the player, but club influence has
        # to be earned. Even a veteran starts as a newcomer to this group.
        influence = min(49.0, _base_influence(player, 30.0) * .6)
        state.members[pid] = SocialMember(pid, day, integration=30.0,
            influence=influence, previous_influence=influence, tier='emerging', tier_since=day)
        player.state.dressing_room_morale = 0.0
        _event(state, 'arrival', day, (pid,), f'{player.full_name} has joined the group. Integration will develop automatically.')
    for pair in combinations(sorted(current), 2):
        if pair not in state.links:
            state.links[pair] = _initial_link(*pair, new=True)
    _select_support(state, current, day)
    _apply_effects(state, current, day)
    state.revision += 1
    return True


def participation_concern(member: SocialMember, player: Player, day: date) -> float:
    """Only a sustained, recent absence while available creates modest concern."""
    if (day - member.joined_on).days < 28:
        return 0.0
    recent = [a for a in member.appearances if a.eligible and 0 <= (day - a.day).days <= 42]
    if len(recent) < 4:
        return 0.0
    window = recent[-4:]
    # One rotation / one experiment is never a social event.
    if sum(a.minutes < 15 for a in window) < 3:
        return 0.0
    ratio = sum(a.minutes for a in window) / (90 * len(window))
    if ratio >= .20:
        return 0.0
    return clamp((.20 - ratio) / .20 * (.35 + .65 * player.personality.ambition / 100), 0, 1)


def _select_support(state: DressingRoomState, players: dict[str, Player], day: date) -> None:
    # Integrating players need support; not a manually assigned mentorship
    # programme. Age is only an eligibility aid, never a leadership multiplier.
    candidates = [pid for pid, member in state.members.items()
        if member.integration >= 60 and member.influence >= 64
        and players[pid].age_on(day) >= 24 and players[pid].personality.professionalism >= 50]
    assigned = {pid: 0 for pid in candidates}
    for pid in sorted(state.members):
        member = state.members[pid]
        member.support_player_id = None
        if member.integration >= 85 or (players[pid].age_on(day) > 23 and (day - member.joined_on).days >= 90):
            continue
        options = [q for q in candidates if q != pid and assigned[q] < 3]
        if options:
            best = max(options, key=lambda q: (
                state.links[tuple(sorted((q, pid)))].affinity + state.members[q].influence * .15, q))
            member.support_player_id = best
            assigned[best] += 1


def _review_hierarchy(state: DressingRoomState, players: dict[str, Player], day: date) -> None:
    for pid in sorted(state.members):
        member, player = state.members[pid], players[pid]
        linked = [link.affinity for pair, link in state.links.items() if pid in pair]
        peer = sum(linked) / len(linked) if linked else 50.0
        recent = [a for a in member.appearances if a.eligible and (day-a.day).days <= 56]
        participation = min(100.0, sum(a.minutes for a in recent[-8:]) / (90 * len(recent[-8:])) * 100) if recent else 50.0
        tenure = min(100.0, (day-member.joined_on).days / 1.8)
        # Neutral/no-history inputs stay near the bootstrap score. Do not
        # demote leaders merely because the first weekly review uses a
        # different averaging formula. New evidence supplies bounded changes.
        target = clamp(_base_influence(player, member.integration)
                       + .16 * (peer-55) + .06 * (participation-50) + .02 * tenure)
        member.previous_influence = member.influence
        member.influence = clamp(member.influence + clamp((target-member.influence)*.20, -1.5, 1.5))
        candidate = _tier(member.influence)
        if candidate != member.tier and (day-member.tier_since).days >= 14:
            # Hysteresis: cannot oscillate around a threshold on every review.
            old_index, next_index = TIERS.index(member.tier), TIERS.index(candidate)
            boundaries = (76, 64, 50)
            if next_index < old_index:
                accepted = member.influence >= boundaries[next_index] + 1.0
            else:
                accepted = member.influence < boundaries[old_index] - 1.0
            if accepted:
                member.tier, member.tier_since = candidate, day
                _event(state, 'hierarchy', day, (pid,),
                    f'{player.full_name} is now part of {TIER_LABELS[candidate].lower()}. Influence changes gradually with life in the squad.')
    state.last_review = day
    _select_support(state, players, day)


def _apply_effects(state: DressingRoomState, players: dict[str, Player], day: date) -> None:
    for pid, member in state.members.items():
        player = players[pid]
        components = {
            'integration': clamp((member.integration - 65.0) / 65.0, -.55, .30),
            'participation': -1.10 * participation_concern(member, player, day),
            'atmosphere': clamp((state.atmosphere - 65.0) / 50.0, -.40, .40),
            'departure': -member.departure_disruption,
            'response': member.result_response,
        }
        member.morale_components = components
        # Replacement rather than +/- mutation: no daily stacking, no extra
        # confidence/chemistry/ACT bonus, and no loss of the underlying morale.
        player.state.dressing_room_morale = round(clamp(sum(components.values()), -MAX_MORALE_EFFECT, MAX_MORALE_EFFECT), 6)


def advance_dressing_room(state: DressingRoomState, players: Iterable[Player], to_date: date) -> None:
    """Daily fixed steps give identical results for daily/fast-forward clocks."""
    require_day(to_date)
    if to_date < state.last_updated:
        raise ValueError('cannot rewind dressing room history')
    if (to_date - state.last_updated).days > 366 * 30:
        raise ValueError('social clock jump exceeds 30 years')
    current = roster(players)
    sync_roster(state, current.values())
    while state.last_updated < to_date:
        day = state.last_updated + timedelta(days=1)
        # Work from the same previous-day signals for every pair/player. Sorting
        # and a fixed step make squad insertion order immaterial.
        concerns = {pid: participation_concern(member, current[pid], day)
                    for pid, member in state.members.items()}
        for (a, b), link in state.links.items():
            pa, pb = current[a].personality, current[b].personality
            compatibility = 1 - (abs(pa.professionalism-pb.professionalism) + abs(pa.ambition-pb.ambition)) / 200
            teamwork = (current[a].attributes.mental.teamwork + current[b].attributes.mental.teamwork) / 200
            shared = min(1.0, link.shared_minutes / 1800)
            # Friction requires a continuing real difference in participation,
            # not a random conflict or a player's ethnicity/nationality.
            friction = abs(concerns[a]-concerns[b]) * (1-compatibility) * 24
            target = 43 + 12 * compatibility + 10 * teamwork + 10 * shared - friction
            link.affinity = clamp(link.affinity + (target-link.affinity) * .012, 25, 90)
        for pid, member in state.members.items():
            player = current[pid]
            support = member.support_player_id in current and member.support_player_id != pid
            professionalism = player.personality.professionalism / 100
            adaptation = player.attributes.mental.adaptability / 100
            rate = .003 * (.65 + .45 * professionalism + .25 * adaptation) * (1.15 if support else 1)
            previous = member.integration
            member.integration += (95.0-member.integration) * rate
            # Loyalty can make a meaningful departure felt longer, but its
            # contribution still fades automatically and is never permanent.
            half_life = 6 + player.personality.loyalty / 100 * 4
            member.departure_disruption *= exp(-.69314718056 / half_life)
            member.result_response *= .82
            if previous < 65 <= member.integration and member.joined_on > state.started_on:
                _event(state, 'integration', day, (pid,), f'{player.full_name} is now settled into the group.')
            # A quiet, rate-limited note, never an inbox decision or modal.
            if concerns[pid] >= .65 and (member.last_concern_on is None or (day-member.last_concern_on).days >= 42):
                member.last_concern_on = day
                _event(state, 'participation', day, (pid,),
                    f'{player.full_name} would welcome more playing time after several available matches. This is a mild, recoverable concern.')
        if (day-state.last_review).days >= 7:
            _review_hierarchy(state, current, day)
        affinity = (sum(l.affinity for l in state.links.values()) / len(state.links)) if state.links else 55.0
        concern = sum(concerns.values()) / len(concerns) if concerns else 0.0
        disruption = sum(m.departure_disruption for m in state.members.values()) / len(state.members) if state.members else 0.0
        target = clamp(65 + (affinity-55)*.6 - concern*4 - disruption*4, 48, 78)
        state.atmosphere += (target-state.atmosphere) * .06
        state.last_updated = day
        state.revision += 1
        _apply_effects(state, current, day)


def record_dressing_room_match(
    state: DressingRoomState, players: Iterable[Player], *, fixture_id: str,
    on_date: date, minutes: Mapping[str, int], eligible: Mapping[str, bool],
    intervals: Mapping[str, tuple[tuple[int, int], ...]] | None = None,
    outcome: int = 0,
) -> bool:
    """Call only inside the managed-match transaction, after result validation.

    Shared playing time is counted from overlapping actual stints, never from
    min(total minutes) (substitutes may have played at different times).
    """
    require_day(on_date)
    if not isinstance(fixture_id, str) or not fixture_id:
        raise ValueError('fixture identity required')
    if fixture_id in state.processed_fixtures:
        return False
    if on_date < state.last_updated:
        raise ValueError('cannot append a past social result')
    if type(outcome) is not int or outcome not in (-1, 0, 1):
        raise ValueError('outcome must be -1, 0 or 1')
    current = roster(players)
    if set(minutes) - set(current) or set(eligible) != set(current):
        raise ValueError('social participation must use the registered squad')
    for pid in current:
        SocialAppearance(fixture_id, on_date, minutes.get(pid, 0), eligible[pid]).validate()
    segments = intervals or {}
    if set(segments) - set(current):
        raise ValueError('unknown player in social stints')
    for pid, parts in segments.items():
        previous = 0
        for start, end in parts:
            if type(start) is not int or type(end) is not int or not previous <= start < end <= 120:
                raise ValueError('invalid social playing intervals')
            previous = end
        if sum(end-start for start, end in parts) != minutes.get(pid, 0):
            raise ValueError('social stints differ from recorded minutes')
    advance_dressing_room(state, current.values(), on_date)
    for pid, member in state.members.items():
        actual = minutes.get(pid, 0)
        member.appearances.append(SocialAppearance(fixture_id, on_date, actual, eligible[pid]))
        del member.appearances[:-MAX_APPEARANCES]
        if actual:
            member.integration = clamp(member.integration + (100-member.integration)*.004 * min(1, actual/90))
            pressure = current[pid].personality.pressure_resistance / 100
            # A mild difference in settling after defeats, not a second result
            # morale award and never an invisible finishing/finals multiplier.
            if outcome < 0:
                member.result_response = clamp((pressure-.60)*.4, -.24, .16)
            elif outcome > 0:
                member.result_response *= .5
    for (a, b), link in state.links.items():
        together = sum(max(0, min(a1, b1)-max(a0, b0))
            for a0, a1 in segments.get(a, ()) for b0, b1 in segments.get(b, ()))
        if together:
            link.shared_minutes = min(100_000_000, link.shared_minutes + together)
            link.affinity = clamp(link.affinity + (90-link.affinity)*.006*min(1, together/90), 25, 90)
    state.processed_fixtures[fixture_id] = on_date
    while len(state.processed_fixtures) > MAX_FIXTURE_MEMORY:
        oldest = min(state.processed_fixtures, key=lambda k: (state.processed_fixtures[k], k))
        del state.processed_fixtures[oldest]
    state.revision += 1
    _apply_effects(state, current, on_date)
    return True


def record_session_match(session, result, eligible: dict[str, bool]) -> None:
    """Session adapter: the persisted competition fixture, not the RNG match ID."""
    stats = {s.player_id: s.minutes for s in result.player_statistics
             if s.club_id == session.home_club.id}
    intervals = {}
    for segment in result.role_segments:
        if segment.club_id == session.home_club.id:
            intervals.setdefault(segment.player_id, []).append((segment.start_minute, segment.end_minute))
    # Old/custom result producers may have no stints. Keep their appearances,
    # but do not manufacture pair overlap for those results.
    intervals = {pid: tuple(sorted(parts)) for pid, parts in intervals.items()}
    difference = result.home_goals-result.away_goals
    if result.away_club_id == session.home_club.id:
        difference *= -1
    outcome = (difference > 0) - (difference < 0)
    record_dressing_room_match(session.dressing_room, session.home_club.squad.players,
        fixture_id=session._active_match.fixture.fixture_id, on_date=session.current_date,
        minutes=stats, eligible=eligible, intervals=intervals, outcome=outcome)
