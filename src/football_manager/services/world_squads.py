"""Selection, one-time bootstrap and season binding for TS-21.1.

Selection solves a maximum-weight bipartite assignment. A versatile player
cannot fill two simultaneous vacancies. This module never changes OVR/ACT.
"""
from __future__ import annotations

from copy import deepcopy
from datetime import date
from random import Random

from football_manager.data.english_players import (
    CB, CM, FB, WB, WIDE, STYLE_FORMATIONS, generate_club, make_identity,
    make_player, stable_seed, target_quality,
)
from football_manager.domain.club import Club
from football_manager.domain.enums import Position
from football_manager.domain.tactical_catalogue import development_formations
from football_manager.domain.football_world import FootballWorld
from football_manager.domain.lineup import LineupEntry, MatchLineup
from football_manager.domain.player_ratings import CurrentRatingContext, CurrentRatingBatch
from football_manager.domain.season_cycle import TIER_IDS
from football_manager.domain.tactics import Tactic
from football_manager.services.player_condition import recover_player_between_matches


def english_participants(world) -> dict[str, int]:
    return {club_id: tier for tier, league_id in enumerate(TIER_IDS, 1)
            for club_id in world.leagues[league_id].participant_club_ids}


def maximum_assignment(weights: list[list[float]]) -> tuple[int, ...]:
    """Rectangular Hungarian algorithm, O(rows**2 * columns), standard library."""
    n = len(weights)
    if n == 0:
        return ()
    m = len(weights[0])
    if n > m or any(len(row) != m for row in weights):
        raise ValueError('assignment requires a rectangular matrix with rows <= columns')
    u, v = [0.0] * (n + 1), [0.0] * (m + 1)
    p, way = [0] * (m + 1), [0] * (m + 1)
    for i in range(1, n + 1):
        p[0] = i
        j0 = 0
        minv, used = [float('inf')] * (m + 1), [False] * (m + 1)
        while True:
            used[j0] = True
            i0, delta, j1 = p[j0], float('inf'), 0
            for j in range(1, m + 1):
                if used[j]:
                    continue
                cur = -weights[i0 - 1][j - 1] - u[i0] - v[j]
                if cur < minv[j]:
                    minv[j], way[j] = cur, j0
                if minv[j] < delta:
                    delta, j1 = minv[j], j
            for j in range(m + 1):
                if used[j]:
                    u[p[j]] += delta; v[j] -= delta
                else:
                    minv[j] -= delta
            j0 = j1
            if p[j0] == 0:
                break
        while True:
            j1 = way[j0]
            p[j0] = p[j1]
            j0 = j1
            if j0 == 0:
                break
    answer = [0] * n
    for j in range(1, m + 1):
        if p[j]:
            answer[p[j] - 1] = j - 1
    return tuple(answer)


def position_family(position: Position) -> str:
    if position in CB:
        return 'CB'
    if position in CM | {Position.DM, Position.AM}:
        return 'MID'
    if position in FB | WB:
        return 'FB'
    if position in WIDE:
        return 'WIDE'
    if position in {Position.ST, Position.SS}:
        return 'ST'
    return 'GK'


def _score(player, slot, tactic, current: bool, *, _ratings: CurrentRatingBatch | None = None) -> float:
    p = slot.position
    if (p is Position.GK) != (player.primary_position is Position.GK):
        return -100000.0
    fam = player.familiarity_for(p)
    role_id = tactic.role_for_slot(slot.slot_id).role_id
    if current:
        context = CurrentRatingContext(assigned_position=p, role_id=role_id, tactic_id=tactic.tactic_id)
        quality = (player.current_rating(context) if _ratings is None
                   else _ratings.rating(player, context)).current
    else:
        quality = player.overall_rating_for(p, role_id)
    # Football selection preferences, not additional rating/simulation modifiers.
    return (quality + .09 * fam - (30.0 if fam < 70 else 0.0)
            + (2.0 if position_family(player.primary_position) == position_family(p) else 0)
            - (.06 * player.state.fatigue if current else 0.0))


class _SelectionScores:
    """Read-only, call-scoped memo. Never reuse after player/tactic mutations.

    Different slots may ask for the exact same position/role. Bench ranking and
    primary/alternative evaluation must reuse the matrix, not recalculate ACT.
    No player references or mutable ratings survive a selection call.
    """

    def __init__(self) -> None:
        self.values: dict[tuple, float] = {}
        self.ratings = CurrentRatingBatch()

    def score(self, player, slot, tactic, current: bool) -> float:
        key = (id(player), slot.position, tactic.role_for_slot(slot.slot_id).role_id,
               tactic.tactic_id, current)
        if key not in self.values:
            self.values[key] = _score(player, slot, tactic, current, _ratings=self.ratings)
        return self.values[key]


def select_lineup(club: Club, tactic: Tactic, *, excluded: frozenset[str] = frozenset(),
                  current: bool = True, bench_size: int = 7,
                  _scores: _SelectionScores | None = None) -> MatchLineup:
    players = sorted((p for p in club.squad.players if p.state.is_available and p.id not in excluded),
                     key=lambda p: p.id)
    if len(players) < 11 or not any(p.primary_position is Position.GK for p in players):
        raise ValueError(f'{club.name} cannot field 11 available players and a goalkeeper')
    scores = _scores if _scores is not None else _SelectionScores()
    weights = [[scores.score(player, slot, tactic, current) for player in players]
               for slot in tactic.formation.slots]
    best_by_player = {p.id: max(row[index] for row in weights)
                      for index, p in enumerate(players)}
    assignments = maximum_assignment(weights)
    entries = tuple(LineupEntry(slot.slot_id, players[index])
                    for slot, index in zip(tactic.formation.slots, assignments, strict=True))
    used = {entry.player.id for entry in entries}
    remaining = [p for p in players if p.id not in used]
    # Reserve goalkeeper, then positional cover; no duplicate substitute IDs.
    bench = []
    for family in ('GK', 'CB', 'FB', 'MID', 'WIDE', 'ST', 'MID'):
        options = [p for p in remaining if position_family(p.primary_position) == family]
        if options and len(bench) < bench_size:
            best = max(options, key=lambda p: (best_by_player[p.id], p.id))
            bench.append(best); remaining.remove(best)
    remaining.sort(key=lambda p: (-p.overall_rating, p.id))
    bench.extend(remaining[:max(0, bench_size - len(bench))])
    return MatchLineup(club.id, tactic.formation, entries, tuple(bench))


def select_team(club: Club, identity):
    """Use the alternative only when available personnel execute it better."""
    candidates = []
    scores = _SelectionScores()
    for order, tactic in enumerate((identity.primary, identity.alternative)):
        try:
            lineup = select_lineup(club, tactic, _scores=scores)
        except ValueError:
            continue
        value = sum(scores.score(e.player, tactic.formation.slot(e.slot_id), tactic, True)
                    for e in lineup.starters) / 11 - order * 3.0
        candidates.append((value, -order, lineup, tactic))
    if not candidates:
        raise ValueError(f'{club.name} has no valid lineup')
    _, _, lineup, tactic = max(candidates, key=lambda item: item[:2])
    return lineup, tactic


def coverage_report(club: Club, tactic: Tactic) -> dict:
    """Two simultaneous complete XIs, not 22 individually satisfiable promises."""
    players = sorted(club.squad.players, key=lambda p: p.id)
    slots = tuple(tactic.formation.slots) * 2
    if len(players) < len(slots):
        return {'complete': False, 'minimum_familiarity': 0, 'assignments': []}
    weights = [[(p.familiarity_for(s.position) if (s.position is Position.GK) ==
                 (p.primary_position is Position.GK) else -100000)
                for p in players] for s in slots]
    assigned = maximum_assignment(weights)
    scores = [weights[i][j] for i, j in enumerate(assigned)]
    assignments = [{'layer': i // 11 + 1, 'slot_id': slots[i].slot_id,
                    'player_id': players[j].id, 'familiarity': round(scores[i], 1)}
                   for i, j in enumerate(assigned)]
    return {'complete': min(scores) >= 75, 'minimum_familiarity': round(min(scores), 1),
            'assignments': assignments}


def _complete_existing(club: Club, identity, quality: float, seed: int, on_date: date) -> None:
    """Fill missing places, preserving every existing identity/attribute/role."""
    if len(club.squad) >= 22:
        return
    slots = tuple(identity.primary.formation.slots) * 2
    existing = list(club.squad.players)
    weights = [[p.familiarity_for(s.position) if (s.position is Position.GK) ==
                (p.primary_position is Position.GK) else -100000 for s in slots]
               for p in existing]
    used = set(maximum_assignment(weights))
    for index, slot in enumerate(slots):
        if index in used:
            continue
        player_id = f'ew1-{stable_seed(seed, club.id, "supplement", index):016x}'
        if club.squad.contains(player_id):
            raise ValueError('duplicate generated supplement ID')
        club.squad.add(make_player(
            player_id=player_id, position=slot.position,
            role_id=identity.primary.role_for_slot(slot.slot_id).role_id,
            quality=max(25, quality - 7), age=19 + index % 12, on_date=on_date,
            seed=seed, style=identity.style_key, versatile=True,
            tactics=(identity.primary, identity.alternative),
        ))


def create_football_world(session, *, migration: bool = False) -> FootballWorld:
    world = session._world
    tiers = english_participants(world)
    start = session.current_date if migration else min(
        f.match_date for f in world.fixtures.values() if f.match_date is not None)
    registry = FootballWorld(world.seed, start, world.season_label, tracked_from=start)
    registry.statistics.start_season(world.season_label, start, complete=not migration)
    preserve = {session.home_club.id: (session.home_club, session.home_lineup, session.home_tactic)}
    if migration and session.away_club.id in tiers:
        preserve[session.away_club.id] = (session.away_club, session.away_lineup, session.away_tactic)
    styles = tuple(STYLE_FORMATIONS)
    for tier in (1, 2, 3, 4):
        clubs = sorted((cid for cid, t in tiers.items() if t == tier),
                       key=lambda cid: (world.strengths[cid], cid))
        rotation = stable_seed(world.seed, 'style-order', tier) % len(styles)
        for rank, club_id in enumerate(clubs):
            quality = target_quality(tier, rank, len(clubs))
            style = styles[(rank + rotation) % len(styles)]
            if club_id in preserve:
                club, lineup, tactic = preserve[club_id]
                style = tactic.preset_origin.value
                if style not in STYLE_FORMATIONS:
                    style = 'balanced'
                identity = make_identity(club_id, club.name, tier, style, world.seed,
                                         lineup.formation.formation_id if lineup.formation.formation_id in
                                         {f.formation_id for f in development_formations()} else None)
                identity.primary = deepcopy(tactic)
                identity.source = 'preserved-manager-save' if migration else 'preserved-opening-squad'
                quality = sum(e.player.overall_rating_for(lineup.formation.slot(e.slot_id).position,
                                                         tactic.role_for_slot(e.slot_id).role_id)
                              for e in lineup.starters) / 11
                _complete_existing(club, identity, quality, world.seed, start)
            else:
                club, identity = generate_club(
                    club_id=club_id, name=session._world_club_names[club_id], tier=tier,
                    quality=quality, seed=world.seed, on_date=start, style=style,
                )
            registry.clubs[club_id] = club
            registry.identities[club_id] = identity
            registry.last_recovery[club_id] = start
    # A migration does not invent appearances for already resolved fixtures.
    if migration:
        registry.processed_fixtures = {fid: True for fid in world.results
                                      if {world.fixtures[fid].home_club_id,
                                          world.fixtures[fid].away_club_id} & registry.clubs.keys()}
    if not migration:
        from football_manager.services.opening_balance import BALANCE_ID
        registry.balance_adjustments[BALANCE_ID] = {'date': start.isoformat(), 'source': 'new-career-opening-data'}
    from football_manager.services.player_development import initialize_world_development
    initialize_world_development(registry, session.current_date)
    from football_manager.services.youth_academy import initialize_youth
    initialize_youth(registry, session.current_date, session.home_club.id)
    from football_manager.services.market_valuation import initialize_market
    initialize_market(registry, session.current_date)
    from football_manager.services.club_economy import initialize_finances
    initialize_finances(registry, session.current_date)
    from football_manager.services.transfer_negotiation import initialize_transfer_market
    initialize_transfer_market(registry, session.current_date)
    from football_manager.services.club_support import initialize_club_support
    initialize_club_support(registry, session.current_date)
    from football_manager.services.career_recognition import record_rating_snapshots
    record_rating_snapshots(registry, session.current_date)
    registry.validate(tiers)
    return registry


def install_football_world(session, *, migration: bool = False) -> None:
    session._world_squads = create_football_world(session, migration=migration)
    session._world.football_world = session._world_squads
    if migration:
        # Extend TS-20 membership without resetting the existing social graph
        # or changing existing player-state values during save migration.
        from football_manager.services.dressing_room import sync_roster
        room = session.dressing_room
        old_members = deepcopy(room.members)
        offsets = {p.id: p.state.dressing_room_morale for p in session.home_club.squad.players}
        sync_roster(room, session.home_club.squad.players)
        room.members.update(old_members)
        for player in session.home_club.squad.players:
            player.state.dressing_room_morale = offsets[player.id]



def _refresh_inactive_club_recovery(registry, on_date: date) -> None:
    """Keep physical clocks current for clubs outside professional fixtures.

    A non-league club can spend many years without a registered senior match,
    but its academy continues developing genuine young professionals. A stale
    ``last_recovery`` date would then precede a graduate's actual birthday,
    failing world validation and making any subsequent return to the pyramid
    attempt decades of redundant day-by-day fatigue recovery.
    """
    for club_id, identity in registry.identities.items():
        if identity.tier != 0:
            continue
        previous = registry.last_recovery[club_id]
        if previous > on_date:
            raise ValueError(f'inactive club recovery clock is ahead of season: {club_id}')
        elapsed = (on_date - previous).days
        if not elapsed:
            continue
        # Thirty match-free days safely restore even very tired players.
        # This records elapsed off-season time, not simulated matches, signings
        # or fabricated footballers; avoid looping through decades of days.
        for player in registry.clubs[club_id].squad.players:
            recover_player_between_matches(player, days=min(elapsed, 30))
        registry.last_recovery[club_id] = on_date


def bind_football_world(session) -> None:
    registry = session._world_squads
    world = session._world
    participants = english_participants(world)
    start = min(f.match_date for f in world.fixtures.values() if f.match_date is not None)
    changing_season = registry.season_label != world.season_label
    if changing_season:
        # TS-24.7: close the old clubs' finances/development BEFORE adding
        # newly promoted non-league entrants. Those clubs did not yet exist in
        # the economic ledger for the months being closed. Adding them first
        # made renewals fail (missing account) or incorrectly backdated income.
        world.football_world = registry
        from football_manager.services.player_development import advance_world_development
        advance_world_development(world, start)
    for club_id in sorted(set(participants) - set(registry.clubs)):
        # The pre-existing season policy introduces two external NL clubs.
        # Bootstrap ONLY new entrants, not new players in existing squads.
        tier = participants[club_id]
        styles = tuple(STYLE_FORMATIONS)
        style = styles[stable_seed(registry.seed, club_id, 'style') % len(styles)]
        quality = {1:75, 2:65, 3:55, 4:45}[tier]
        club, identity = generate_club(club_id=club_id, name=session._career.club_names[club_id],
            tier=tier, quality=quality, seed=registry.seed, on_date=start, style=style)
        identity.source = 'fictional-external-entrant-v1'
        registry.clubs[club_id] = club
        registry.identities[club_id] = identity
        registry.last_recovery[club_id] = start
    from football_manager.services.club_support import initialize_club_support
    initialize_club_support(registry, start)
    from football_manager.services.player_development import initialize_world_development
    initialize_world_development(registry, start)
    if registry.youth is None:
        from football_manager.services.youth_academy import initialize_youth
        initialize_youth(registry, session.current_date, session.home_club.id)
    if changing_season:
        from football_manager.services.player_aging import finalize_season_retirements, repair_managed_unavailable
        # While clubs are in non-league they may not play any senior fixture
        # for years. Refresh their physical clock BEFORE graduating younger
        # academy players and before changing who is currently active.
        _refresh_inactive_club_recovery(registry, start)
        # Align divisions with new membership BEFORE drawing youth fixtures.
        for cid, record in registry.identities.items():
            record.tier = participants.get(cid, 0)
        # Allow academy graduates to replace veterans before retirements.
        from football_manager.services.youth_academy import roll_youth_season
        roll_youth_season(registry, start, session.home_club.id, new_label=world.season_label)
        retired = finalize_season_retirements(world, start, managed_club_id=session.home_club.id,
                                              managed_tactic=session.home_tactic)
        if retired:
            repair_managed_unavailable(session)
            from football_manager.services.dressing_room import sync_roster
            sync_roster(session.dressing_room, session.home_club.squad.players)
    from football_manager.services.club_economy import sync_financial_rosters, rebase_finances_for_new_season
    if registry.finance_review_on is not None:
        # Entrants' contracts and accounts begin at the first new-season date.
        # No July wages, revenue or renewals are charged before their entry.
        sync_financial_rosters(registry,start)
        if changing_season:
            rebase_finances_for_new_season(registry,start)
    registry.adopt_season(world.season_label, participants)
    from football_manager.services.career_recognition import record_rating_snapshots
    record_rating_snapshots(registry, start)
    registry.statistics.start_season(world.season_label, start, complete=True)
    world.football_world = registry


def recover_world_club(world, club_id: str, on_date: date) -> None:
    registry = world.football_world
    if club_id not in registry.clubs:
        return
    previous = registry.last_recovery[club_id]
    if on_date < previous:
        raise ValueError(f'cannot rewind physical state for {club_id}')
    days = (on_date - previous).days
    # Daily rounding matches repeated one-day progression, even if a club was
    # previewed between its two fixtures. Merely changing click cadence cannot
    # confer a physical advantage on the next opponent.
    for player in registry.clubs[club_id].squad.players:
        for _ in range(days):
            recover_player_between_matches(player, days=1)
    world._put(registry.last_recovery, club_id, on_date)


def reset_results_only_tracking(session) -> None:
    """Results JSON has no player history. Explicitly restart tracking on import.

    Keep existing players and attributes, but never pretend the imported scores
    contain minutes, physical history or the historical squads of a full save.
    """
    world, registry = session._world, session._world_squads
    pending = [f.match_date for fid, f in world.fixtures.items()
               if fid not in world.results and f.match_date is not None]
    start = min(pending, default=session.current_date)
    from football_manager.domain.season_statistics import SeasonStatisticsLedger
    registry.statistics = SeasonStatisticsLedger()
    registry.statistics.start_season(world.season_label, start, complete=False)
    registry.usage.clear()
    from football_manager.services.player_development import restart_results_only_tracking
    restart_results_only_tracking(registry, start)
    registry.tracked_from = start
    registry.last_recovery = {cid: start for cid in registry.clubs}
    if registry.youth is not None:
        # Scores-only does not contain a reliable youth history; restart fixtures.
        registry.youth.last_processed = start
    registry.processed_fixtures = {
        fid: True for fid in world.results
        if {world.fixtures[fid].home_club_id, world.fixtures[fid].away_club_id}
        & registry.clubs.keys()
    }


def dev_handicap_copy(club, lineup):
    """Legacy debug aid only; shared original players are never modified."""
    from dataclasses import fields, replace
    club_copy, lineup_copy = deepcopy((club, lineup))
    for player in club_copy.squad.players:
        changes = {}
        for group in ("technical", "mental", "physical", "goalkeeping"):
            attrs = getattr(player.attributes, group)
            if attrs is not None:
                changes[group] = replace(attrs, **{f.name: max(1, getattr(attrs, f.name) - 18)
                                                  for f in fields(attrs)})
        player.attributes = replace(player.attributes, **changes)
    return club_copy, lineup_copy
