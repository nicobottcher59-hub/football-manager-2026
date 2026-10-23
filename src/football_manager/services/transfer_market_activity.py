"""TS-FIX-02: live incoming interest and dated transfer obligations.

Read requests never create offers. Actual calendar progression evaluates buyer
needs weekly in an open window. The managed club's willingness/ability to sell
is NOT a filter for another club's interest; registration safety is checked at
completion. AI-to-AI trading continues to use the established monthly planner.
"""
from __future__ import annotations
from dataclasses import replace
from datetime import date, timedelta

from football_manager.domain.transfer_negotiation import TransferTerms, TransferNegotiation, NegotiationEvent


def create_incoming_interest(world, today: date) -> int:
    from football_manager.services.ai_transfer_market import window_open, _eligible_at_position
    from football_manager.services.ai_squad_planning import squad_plan
    from football_manager.services.transfer_negotiation import _availability, _quote, _unit
    from football_manager.services.transfer_personal import agent_demand
    from football_manager.services.club_economy import weekly_payroll
    from football_manager.domain.enums import Position
    registry = world.football_world
    manager = registry.youth.managed_club_id if registry.youth else None
    if not manager or not window_open(today):
        return 0
    if world._active_journal is None:
        raise RuntimeError('Incoming interest requires a world transaction')
    previous = [d for d in registry.transfer_offers.values() if d.seller_id == manager]
    live = [d for d in previous if d.status in ('manager_turn', 'agreed', 'pending_window')
            and d.expires_on >= today]
    is_winter = today.month == 1
    in_window = [d for d in previous if d.started_on.year == today.year
                 and (d.started_on.month == 1 if is_winter else d.started_on.month in (7, 8))]
    unsolicited = sum(registry.manager_sale_posture.get(d.player_id,'normal') != 'transfer_listed'
                      for d in in_window)
    # All paths share the same scarcity budget, including monthly AI bids:
    # three per window, one unsolicited, and no weekly barrage of live offers.
    if (len(live) >= 2 or len(in_window) >= 3
            or any(0 <= (today-d.started_on).days < 14 for d in previous)):
        return 0
    stock = [p for p in registry.clubs[manager].squad.players
             if p.id in registry.contracts and registry.contracts[p.id].club_id == manager
             and registry.contracts[p.id].kind == 'professional'
             and registry.manager_sale_posture.get(p.id,'normal') != 'untouchable']
    buyers = [cid for cid in registry.clubs if cid != manager and registry.identities[cid].tier > 0]
    buyers.sort(key=lambda cid: (_unit(registry.seed, 'incoming-review', today, cid), cid))
    created = 0
    for buyer_id in buyers:
        if created >= 1 or len(in_window) + created >= 3:
            break
        club = registry.clubs[buyer_id]
        if len(club.squad) >= 32:
            continue
        # A real decision already pending for this buyer should be answered first.
        if any(d.buyer_id == buyer_id for d in live):
            continue
        budget = _availability(registry, buyer_id, today)
        wage_room = registry.club_finances[buyer_id].wage_budget_weekly_gbp - weekly_payroll(registry, buyer_id)
        if budget < 5_000 or wage_room <= 0:
            continue
        plan = squad_plan(club, registry.identities[buyer_id].primary)
        needs = [(v['position'], None, v['layer']) for v in plan['vacancies'] if v['layer'] <= 2]
        starters = sorted((r for r in plan['assignments'] if r['layer'] == 1),
                          key=lambda r: club.squad.get(r['player_id']).overall_rating)
        # Quality upgrades compete with filling holes, and require a real gain.
        needs.extend((r['position'], club.squad.get(r['player_id']).overall_rating, 4)
                     for r in starters[:3])
        candidates = []
        strength = sum(sorted((p.overall_rating for p in club.squad.players), reverse=True)[:11]) / 11
        for player in stock:
            posture=registry.manager_sale_posture.get(player.id,'normal')
            if posture != 'transfer_listed':
                if unsolicited >= 1 or _unit(registry.seed,'fix06-weekly-unlisted',buyer_id,player.id,
                        today.year,'winter' if is_winter else 'summer') < .85:
                    continue
            recent = any(d.player_id == player.id and d.buyer_id == buyer_id
                         and (d.status in ('manager_turn', 'agreed', 'pending_window') and d.expires_on >= today
                              or (today - d.events[-1].on_date).days < 120)
                         for d in registry.transfer_offers.values())
            if recent:
                continue
            matches = [(pos, old, layer) for pos, old, layer in needs
                       if _eligible_at_position(player, Position(pos))
                       and (player.overall_rating >= old + 3 if old is not None
                            else player.overall_rating >= strength - (9 if layer == 1 else 15))]
            if not matches:
                continue
            value = _quote(registry, player).value_gbp
            fee = max(5_000, round(value * (.92 + .16 * _unit(registry.seed, buyer_id, player.id, today)) / 5000) * 5000)
            if fee > budget * .85:
                continue
            demand = agent_demand(registry, player, manager, buyer_id, today)
            if not demand['interested'] or demand['weekly_wage_gbp'] > wage_room:
                continue
            urgency = max(9 if layer == 1 else 5 if layer == 2 else 0 for _, _, layer in matches)
            score = player.overall_rating + urgency - 12 * fee / max(1, budget)
            if posture == 'transfer_listed':
                score += 16
            candidates.append((score, player.id, player, fee))
        if not candidates:
            continue
        _, _, player, fee = max(candidates, key=lambda row: (row[0], row[1]))
        number = registry.transfer_next_id
        world._active_journal.undo_callbacks.setdefault(('ts245-sequence', id(registry)),
            lambda old=number: setattr(registry, 'transfer_next_id', old))
        registry.transfer_next_id += 1
        key = f't24-{number:06d}'
        terms = TransferTerms(fee)
        deal = TransferNegotiation(key, player.id, manager, buyer_id, today,
            today + timedelta(days=14), 'manager_turn', buyer_id, terms,
            (NegotiationEvent(today, buyer_id, terms, 'Incoming bid: identified squad need or first-team upgrade'),),
            reason='A buying club submitted a real offer. Your decision is required; no player has moved.')
        deal.validate()
        world._put(registry.transfer_offers, key, deal)
        if registry.manager_sale_posture.get(player.id,'normal') != 'transfer_listed':
            unsolicited += 1
        created += 1
    return created


def advance_transfer_activity(world, through: date) -> int:
    registry = world.football_world
    if registry is None or registry.transfer_last_review_on is None:
        return 0
    previous = registry.transfer_interest_review_on
    if previous is not None and previous >= through:
        return 0
    if world._active_journal is None:
        raise RuntimeError('Transfer activity requires a world transaction')
    world._active_journal.undo_callbacks.setdefault(('fix02-market-clock', id(registry)),
        lambda: setattr(registry, 'transfer_interest_review_on', previous))
    from football_manager.services.transfer_installments import settle_due_installments
    cursor = (previous + timedelta(days=1)) if previous else through
    created = 0
    while cursor <= through:
        settle_due_installments(world, cursor)
        for key, deal in tuple(registry.transfer_offers.items()):
            if deal.status in ('manager_turn', 'agreed') and deal.expires_on < cursor:
                world._put(registry.transfer_offers, key, replace(deal, status='expired',
                    reason='Negotiation expired without completion'))
        if cursor.day in (1, 8, 15, 22, 29):
            created += create_incoming_interest(world, cursor)
        cursor += timedelta(days=1)
    registry.transfer_interest_review_on = through
    return created
