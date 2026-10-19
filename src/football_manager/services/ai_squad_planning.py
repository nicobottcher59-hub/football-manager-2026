"""TS-24.5: tactical squad-depth planning for all registered English clubs.

Coverage is an assignment problem, not a positional headcount. One versatile
player may cover ONE of the 23 slots (11 starters, 11 backups, third keeper).
This is a read-only model, independent of fatigue and hidden player PA.
"""
from __future__ import annotations

from collections import Counter

from football_manager.domain.enums import Position
from football_manager.services.world_squads import maximum_assignment

MIN_FAMILIARITY = 70.0


def squad_plan(club, tactic, *, excluded_id: str = '') -> dict:
    """Project two tactical XIs and an extra GK, without double-counting.

    The best fit is assigned across all 23 slots jointly. Starters get first
    priority, then backups, then the third keeper. Injuries do not make a
    contracted employee vanish from the transfer market planning ledger.
    """
    slots = [(layer, slot.slot_id, slot.position) for layer in (1, 2)
             for slot in tactic.formation.slots]
    slots.append((3, 'third-keeper', Position.GK))
    players = sorted((p for p in club.squad.players if p.id != excluded_id),
                     key=lambda p: p.id)
    # Rectangular assignment: dummy columns represent vacancies and beat
    # out-of-position players. There can never be a duplicated player ID.
    weights = []
    for layer, _, position in slots:
        row = []
        for player in players:
            if (player.primary_position is Position.GK) != (position is Position.GK):
                row.append(-100_000.0)
                continue
            familiarity = player.familiarity_for(position)
            if familiarity < MIN_FAMILIARITY:
                row.append(-100_000.0)
                continue
            # Lexical priority by tactical layer, then familiarity and OVR.
            base = 400 if layer == 1 else 210 if layer == 2 else 65
            row.append(base + familiarity * .7 + player.overall_rating * .5)
        row.extend([0.0] * len(slots))
        weights.append(row)
    assigned = maximum_assignment(weights)
    covered = []
    vacant = []
    player_ids = set()
    for i, (layer, slot_id, position) in enumerate(slots):
        choice = assigned[i]
        player = players[choice] if choice < len(players) and weights[i][choice] > 0 else None
        item = {'layer': layer, 'slot_id': slot_id, 'position': position.value,
                'player_id': player.id if player else None,
                'player_name': player.full_name if player else None,
                'familiarity': round(player.familiarity_for(position), 1) if player else 0.0}
        (covered if player else vacant).append(item)
        if player:
            player_ids.add(player.id)
    by_position = Counter(p.primary_position.value for p in players)
    needs = sorted(vacant, key=lambda item: (item['layer'], item['position'], item['slot_id']))
    return {'formation_id': tactic.formation.formation_id,
            'formation': tactic.formation.name,
            'squad_size': len(players), 'target_size': 23,
            'starters_covered': sum(i['layer'] == 1 for i in covered),
            'backups_covered': sum(i['layer'] == 2 for i in covered),
            'third_keeper_covered': any(i['layer'] == 3 for i in covered),
            'vacancies': needs,
            'assignments': covered,
            'unallocated_ids': sorted(p.id for p in players if p.id not in player_ids),
            'natural_position_counts': dict(sorted(by_position.items()))}


def first_need(plan: dict) -> dict | None:
    """A missing starter is more urgent than any bench/depth upgrade."""
    return next(iter(plan['vacancies']), None)


def can_spare(club, tactic, player_id: str, *, before: dict | None = None) -> bool:
    """No club should sell itself out of a tactical starting position.

    Selling a backup may be considered only when the remaining squad can still
    put out the same number of natural/tactically proficient starters. A club
    with fewer than 20 professional players cannot supply the AI market.
    """
    if len(club.squad) <= 20 or not club.squad.contains(player_id):
        return False
    old = before if before is not None else squad_plan(club, tactic)
    newer = squad_plan(club, tactic, excluded_id=player_id)
    if newer['starters_covered'] < old['starters_covered']:
        return False
    # TS-24.8: a club may part with ONE deputy from an otherwise complete
    # two-XI squad, but cannot keep exporting backups while already short.
    # The vacant slot becomes first priority for the buyer AI next window.
    minimum_backups = min(10, old['backups_covered'])
    if newer['backups_covered'] < minimum_backups:
        return False
    # Never sell a second keeper if that would leave the first XI unsafe.
    if club.squad.get(player_id).primary_position is Position.GK:
        keepers=sum(p.primary_position is Position.GK and p.id!=player_id
                    for p in club.squad.players)
        return (keepers >= 2 and newer['starters_covered'] == 11
                and newer['backups_covered'] == 11)
    return True


def club_planning_view(session, club_id: str | None = None) -> dict:
    """Read-only scouting/club-profile summary for manual inspection."""
    registry = session._world_squads
    cid = club_id or session.home_club.id
    if cid not in registry.clubs:
        raise KeyError(cid)
    identity = registry.identities[cid]
    tactic = session.home_tactic if cid == session.home_club.id else identity.primary
    report = squad_plan(registry.clubs[cid], tactic)
    return {'club_id': cid, 'club': registry.clubs[cid].name,
            'date': session.current_date.isoformat(), **report}


def imminent_succession_needs(club, tactic, on_date, plan: dict | None = None) -> list[dict]:
    """Identify real XI/deputy positions at risk from requested retirements.

    The caller may scout BEFORE a veteran leaves, but this does not invent a
    roster vacancy or force a contract. A versatile successor is counted only
    after an actual signing via squad_plan's one-player-one-slot assignment.
    """
    if plan is None:
        plan = squad_plan(club, tactic)
    covered = [row for row in plan['assignments'] if row['layer'] <= 2]
    prospects = []
    for row in covered:
        player = club.squad.get(row['player_id'])
        profile = player.aging
        if (profile is None or profile.retirement_status not in ('requested','deferred')
                or profile.retirement_requested_on is None
                or profile.retirement_requested_on > on_date
                or player.age_on(on_date) < 37):
            continue
        # Only target a successor if the remaining team would actually lose
        # positional coverage, rather than reflexively buying every veteran.
        after = squad_plan(club, tactic, excluded_id=player.id)
        if (after['starters_covered'] >= plan['starters_covered']
                and after['backups_covered'] >= plan['backups_covered']):
            continue
        # Positions genuinely uncovered after this departure, not arbitrary
        # projections from an ageing player's primary position.
        holes = [v for v in after['vacancies'] if v['layer'] <= 2]
        if not holes:
            continue
        slot = next((v for v in holes if v['position'] == row['position']
                     and v['layer'] == row['layer']), holes[0])
        prospects.append({**slot, 'succession': True, 'retiring_id': player.id})
    # Prioritise starters and the oldest departure; cap independent plans to
    # avoid hiring a whole new second XI on a single monthly pass.
    prospects.sort(key=lambda x: (x['layer'], club.squad.get(x['retiring_id']).identity.birth_date, x['position']))
    return prospects[:2]
