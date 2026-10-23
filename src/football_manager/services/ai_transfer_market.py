"""TS-24.5 autonomous inter-club trading, driven by tactical squad shortages.

Only AI-owned buyers and sellers settle automatically. Manager acquisitions and
sales ALWAYS require the user's existing inter-club and player agreements.
Monthly calls are inside WorldSeasonRunner's undo journal, not page reads.
"""
from __future__ import annotations

from collections import defaultdict
from dataclasses import replace
from datetime import date, timedelta

from football_manager.domain.club_economy import PlayerContract
from football_manager.domain.transfer_negotiation import (
    TransferTerms, NegotiationEvent, TransferNegotiation,
)
from football_manager.domain.transfer_personal import PersonalEvent, PersonalTerms
from football_manager.domain.enums import Position
from football_manager.services.ai_squad_planning import squad_plan, can_spare, imminent_succession_needs
from football_manager.services.club_economy import _date_plus_months, weekly_payroll
from football_manager.services.transfer_negotiation import (
    _availability, _player, _quote, _seller_target, _unit,
)
from football_manager.services.transfer_personal import (
    agent_demand, _player_interest, career_player_totals, _sell_on_payout,
)

WINDOW_MONTHS = frozenset((1, 7, 8))  # compatibility constant; calendar is authoritative
MAX_AI_TRANSFERS_PER_MONTH = 28
MAX_BUYS_PER_CLUB_MONTH = 2
MAX_SQUAD_SIZE = 32  # independent of wider 45-player registration ceiling


def window_open(day: date) -> bool:
    """Compatibility adapter for the world-wide English simulation market."""
    from football_manager.services.transfer_windows import window_open as registered_window
    return registered_window(day)


def _eligible_at_position(player, position: Position) -> bool:
    if (player.primary_position is Position.GK) != (position is Position.GK):
        return False
    return player.familiarity_for(position) >= 70


def _check_seller(registry, seller_id: str, pid: str, cache: dict) -> bool:
    identity = registry.identities[seller_id]
    club = registry.clubs[seller_id]
    key=(seller_id,pid)
    if key in cache:
        return cache[key]
    state = cache.get((seller_id,'plan'))
    if state is None:
        state = squad_plan(club, identity.primary)
        cache[(seller_id,'plan')] = state
    value=can_spare(club, identity.primary, pid, before=state)
    cache[key]=value
    return value


def _journal_move(world, deal_id: str, source_id: str, target_id: str, player):
    """Undo squad membership and mutable dressing morale with the world journal."""
    registry = world.football_world
    seller = registry.clubs[source_id]
    buyer = registry.clubs[target_id]
    if not seller.squad.contains(player.id) or buyer.squad.contains(player.id):
        raise ValueError('Player owner changed during AI market review')
    morale = player.state.dressing_room_morale
    def undo():
        buyer.squad._players.pop(player.id, None)
        seller.squad._players[player.id] = player
        player.state.dressing_room_morale = morale
    world._active_journal.undo_callbacks[('ts245-squad',deal_id)] = undo
    seller.squad.remove(player.id)
    buyer.squad.add(player)


def _finalize(world, seller_id: str, buyer_id: str, player, fee: int,
              demand: dict, today: date) -> dict:
    """One journaled AI-to-AI sale, contract, club payment, and audit record."""
    registry = world.football_world
    if world._active_journal is None:
        raise RuntimeError('Autonomous transfers require a world transaction')
    if registry.youth and registry.youth.managed_club_id in (seller_id,buyer_id):
        raise ValueError('User-managed club may not be traded autonomously')
    if len(registry.clubs[buyer_id].squad) >= MAX_SQUAD_SIZE:
        raise ValueError('Buyer squad is full')
    _player(registry, player.id, seller_id)
    account = registry.club_finances[buyer_id]
    if not demand['interested']:
        raise ValueError('Player declined AI destination')
    wage = demand['weekly_wage_gbp']
    if (fee > _availability(registry,buyer_id,today) or fee > account.cash_gbp
            or weekly_payroll(registry,buyer_id)+wage > account.wage_budget_weekly_gbp):
        raise ValueError('Buying club cannot finance transfer and weekly wage')
    if len(registry.clubs[seller_id].squad) <= 20:
        raise ValueError('Seller has insufficient remaining players')
    terms = TransferTerms(fee)
    personal = PersonalTerms(wage,demand['years'],demand['role'],0)
    number = registry.transfer_next_id
    world._active_journal.undo_callbacks.setdefault(
        ('ts245-sequence',id(registry)),
        lambda old=number:setattr(registry,'transfer_next_id',old))
    registry.transfer_next_id += 1
    deal_id=f't24-{number:06d}'
    deal_date=today-timedelta(days=1)  # previous month's window closing date
    first=TransferNegotiation(deal_id,player.id,seller_id,buyer_id,deal_date,deal_date,
        'completed',buyer_id,terms,
        (NegotiationEvent(deal_date,buyer_id,terms,'AI buyer offers guaranteed cash for positional need'),),
        reason='AI player and both clubs agreed; transfer settled',
        personal_status='completed',personal_terms=personal,
        personal_events=(PersonalEvent(deal_date,'agent',personal,'AI agent agreed sporting role and salary'),),
        bonus_baseline=career_player_totals(registry,player.id),
        buyer_tier_at_signing=registry.identities[buyer_id].tier)
    beneficiary, share = _sell_on_payout(registry,first)
    completed=replace(first,sell_on_paid_gbp=share)
    completed.validate()
    old_buyer=registry.club_finances[buyer_id]
    old_seller=registry.club_finances[seller_id]
    contract=PlayerContract(player.id,buyer_id,today,
        _date_plus_months(today,personal.years*12),wage,personal.role,'professional')
    contract.validate()
    # Perform in one journal. The original seller's prior month wages have
    # already been paid by review_finances immediately before this boundary.
    _journal_move(world,deal_id,seller_id,buyer_id,player)
    world._put(registry.contracts,player.id,contract)
    world._put(registry.club_finances,buyer_id,replace(old_buyer,
        cash_gbp=old_buyer.cash_gbp-fee,
        transfer_budget_gbp=old_buyer.transfer_budget_gbp-fee))
    world._put(registry.club_finances,seller_id,replace(old_seller,
        cash_gbp=old_seller.cash_gbp+fee-share,
        transfer_budget_gbp=old_seller.transfer_budget_gbp+fee-share))
    if beneficiary in registry.club_finances and share:
        previous=registry.club_finances[beneficiary]
        world._put(registry.club_finances,beneficiary,replace(previous,
            cash_gbp=previous.cash_gbp+share,
            transfer_budget_gbp=previous.transfer_budget_gbp+share))
    if player.id in registry.medical_followups:
        _,due=registry.medical_followups[player.id]
        world._put(registry.medical_followups,player.id,(buyer_id,due))
    for key,record in tuple(registry.transfer_offers.items()):
        if record.player_id==player.id and record.status in ('manager_turn','agreed','pending_window'):
            world._put(registry.transfer_offers,key,
                replace(record,status='expired',reason='Player joined another club'))
    world._put(registry.transfer_offers,deal_id,completed)
    return {'deal_id':deal_id,'player_id':player.id,'seller_id':seller_id,
            'buyer_id':buyer_id,'fee_gbp':fee,'wage_weekly_gbp':wage}


def _pool(registry, skip_id: str):
    """Available professional stock, indexed by primary and genuine secondary fit."""
    indexed = defaultdict(list)
    for seller_id in sorted(registry.clubs):
        # The managed club is included only as a possible source of OFFERS.
        # _finalize explicitly prohibits taking its players automatically.
        club=registry.clubs[seller_id]
        for player in club.squad.players:
            contract=registry.contracts.get(player.id)
            if contract is None or contract.kind!='professional' or contract.club_id!=seller_id:
                continue
            # A flexible player appears in several lists but will sign only once.
            positions={player.primary_position,*player.secondary_positions}
            for pos in positions:
                if _eligible_at_position(player,pos):
                    indexed[pos].append((seller_id,player))
    return indexed


def process_ai_market(world, today: date) -> list[dict]:
    """One autonomous monthly window pass, after the prior month closes.

    Buyer wants tactical coverage BEFORE quality upgrades. Seller protection
    prevents losing starting-place coverage; no artificial cash is injected.
    Transfers remain deterministic for the same saved seed/date/state.
    """
    registry=world.football_world
    if registry is None or world._active_journal is None:
        raise RuntimeError('AI market requires the world journal')
    # The review runs on the first day of the next month: it settles the
    # preceding month's window (August recruitment is visible on September 1).
    window = today-timedelta(days=1)
    if not window_open(window):
        return []
    manager=registry.youth.managed_club_id if registry.youth else None
    stock=_pool(registry,manager or '')
    seller_cache={}
    changed=set()
    buys=defaultdict(int)
    sales=defaultdict(int)
    outcomes=[]
    # Single-offer scarcity: clubs scout widely but bother the manager only
    # for a justified need. Transfer-listed players receive priority.
    previous_incoming=[d for d in registry.transfer_offers.values() if d.seller_id==manager]
    manager_bids_this_review=0
    manager_bids_window=sum(d.started_on.year==window.year and d.started_on.month in (1,7,8)
                            and (d.started_on.month==1)==(window.month==1)
                            and d.seller_id==manager for d in previous_incoming)
    manager_unlisted_window=sum(d.started_on.year==window.year and d.started_on.month in (1,7,8)
                            and (d.started_on.month==1)==(window.month==1)
                            and d.seller_id==manager
                            and registry.manager_sale_posture.get(d.player_id,'normal')!='transfer_listed'
                            for d in previous_incoming)
    buyers=[cid for cid in registry.clubs if cid != manager and registry.identities[cid].tier in (1,2,3,4)]
    buyers.sort(key=lambda cid:(_unit(registry.seed,'ai-buyer',today,cid),cid))
    # A second pass lets clubs that just sold a backup seek a replacement
    # before the same window closes, even when their first turn was earlier.
    for _round in range(2):
        for buyer_id in buyers:
            if len(outcomes)>=MAX_AI_TRANSFERS_PER_MONTH:
                break
            club=registry.clubs[buyer_id]
            if len(club.squad)>=MAX_SQUAD_SIZE:
                continue
            plan=squad_plan(club,registry.identities[buyer_id].primary)
            needed=plan['vacancies'][:4]
            # TS-24.9: source genuine successors for requested retirements
            # while contracts and availability still allow an orderly exit.
            future=imminent_succession_needs(club,registry.identities[buyer_id].primary,today,plan)
            seen={(v['layer'],v['position']) for v in needed}
            needed.extend(v for v in future if (v['layer'],v['position']) not in seen)
            # Once both XIs are covered, a club may still seek an upgrade for an
            # underperforming starter. This is SECONDARY to filling true gaps.
            # The opening 92 squads already start with 22 suited professionals;
            # trading must not rely on pretending their initial third GK is urgent.
            if all(v['layer']==3 for v in needed):
                starters=[row for row in plan['assignments'] if row['layer']==1
                          and row['position']!='GK']
                starters.sort(key=lambda row:(club.squad.get(row['player_id']).overall_rating,row['slot_id']))
                for row in starters[:2]:
                    needed.append({'layer':4,'position':row['position'],
                                   'slot_id':row['slot_id'],
                                   'replace_ovr':club.squad.get(row['player_id']).overall_rating})
            if not needed:
                continue
            strength=sum(sorted((p.overall_rating for p in club.squad.players),reverse=True)[:11])/11
            capacity=_availability(registry,buyer_id,today)
            budget=registry.club_finances[buyer_id]
            room=budget.wage_budget_weekly_gbp-weekly_payroll(registry,buyer_id)
            if capacity<5_000 or room<75:
                continue
            # Spread purchases across clubs; each buyer is limited to two per monthly pass.
            for need in needed:
                if buys[buyer_id]>=MAX_BUYS_PER_CLUB_MONTH or len(outcomes)>=MAX_AI_TRANSFERS_PER_MONTH:
                    break
                position=Position(need['position'])
                layer=need['layer']
                # Third GK is desirable but below urgent starting/bench holes.
                if layer==3:
                    if buys[buyer_id]:
                        continue
                    if not any(sum(x.primary_position is Position.GK for x in registry.clubs[cid].squad.players)>2
                               for cid,_ in stock[position] if cid!=buyer_id):
                        continue
                prelim=[]
                if layer==4:
                    if len(club.squad)>=25:
                        continue
                    fit_count=sum(_eligible_at_position(p,position) for p in club.squad.players)
                    natural_slots=sum(s.position is position for s in registry.identities[buyer_id].primary.formation.slots)
                    if fit_count>=natural_slots*2+1:
                        continue
                for seller_id,player in stock[position]:
                    if seller_id==buyer_id or player.id in changed or sales[seller_id]>=2:
                        continue
                    if seller_id==manager and registry.manager_sale_posture.get(player.id)=='untouchable':
                        continue
                    if seller_id != manager and len(registry.clubs[seller_id].squad)<=20:
                        continue
                    if player.primary_position is Position.GK and seller_id!=manager:
                        if sum(p.primary_position is Position.GK for p in registry.clubs[seller_id].squad.players)<=2:
                            continue
                    if need.get('succession') and player.age_on(today) > 32:
                        continue  # a future replacement must not be another near-retiree
                    if layer==4:
                        if player.overall_rating < need['replace_ovr']+5:
                            continue
                    elif player.overall_rating < strength - (12 if layer==1 else 20):
                        continue
                    market = _quote(registry,player).value_gbp
                    if market > capacity*1.25:
                        continue
                    score=(player.familiarity_for(position)*.35+player.overall_rating*.80
                           - (market/max(1,capacity))*14
                           + (4 if player.age_on(today) < 24 and layer <= 2 else 0)
                           + _unit(registry.seed,'target',buyer_id,player.id,today)*2
                           + (20 if seller_id==manager and registry.manager_sale_posture.get(player.id)=='transfer_listed' else 0))
                    prelim.append((score,seller_id,player))
                # Only evaluate expensive contracts/asking bands/coverage for a
                # short ranked shortlist, rather than all 2000+ professionals.
                prelim.sort(key=lambda item:(-item[0],item[2].id))
                contenders=[]
                for score,seller_id,player in prelim[:35]:
                    if any(d.player_id==player.id and d.status in ('agreed','pending_window') and d.expires_on>=today
                           for d in registry.transfer_offers.values()):
                        continue
                    player_ok,_ = _player_interest(registry,player,seller_id,buyer_id,today)
                    if not player_ok:
                        continue
                    required = agent_demand(registry,player,seller_id,buyer_id,today)
                    if required['weekly_wage_gbp'] > room:
                        continue
                    contract=registry.contracts[player.id]
                    ask=_seller_target(registry,seller_id,buyer_id,player,contract,today)
                    if ask<5_000 or ask>capacity or ask>budget.cash_gbp:
                        continue
                    if ask>max(5_000,capacity*.80) and layer>1:
                        continue
                    if seller_id!=manager and not _check_seller(registry,seller_id,player.id,seller_cache):
                        continue
                    score=score-(ask/max(1,capacity))
                    contenders.append((score,seller_id,player,ask,required))
                if not contenders:
                    continue
                _,seller_id,player,fee,demand=max(contenders,key=lambda item:(item[0],item[2].id))
                if seller_id==manager:
                    posture=registry.manager_sale_posture.get(player.id,'normal')
                    if manager_bids_this_review>=1 or manager_bids_window>=3:
                        continue
                    if posture!='transfer_listed':
                        if manager_unlisted_window>=1:
                            continue
                        if _unit(registry.seed,'unsolicited-bid',buyer_id,player.id,registry.season_label)<.83:
                            continue
                    # Only an OFFER. No AI can accept on behalf of the manager.
                    if any(d.player_id==player.id and d.buyer_id==buyer_id
                           and ((d.status in ('manager_turn','agreed','pending_window') and d.expires_on>=today)
                                or (today-d.events[-1].on_date).days<120)
                           for d in registry.transfer_offers.values()):
                        continue
                    number=registry.transfer_next_id
                    world._active_journal.undo_callbacks.setdefault(
                        ('ts245-sequence',id(registry)),
                        lambda old=number:setattr(registry,'transfer_next_id',old))
                    registry.transfer_next_id+=1
                    key=f't24-{number:06d}'
                    terms=TransferTerms(fee)
                    incoming=TransferNegotiation(key,player.id,seller_id,buyer_id,window,
                        window+timedelta(days=21),'manager_turn',buyer_id,terms,
                        (NegotiationEvent(window,buyer_id,terms,'AI scouting: position in need of cover'),),
                        reason='AI buyer submitted a real bid; manager decision required')
                    incoming.validate()
                    world._put(registry.transfer_offers,key,incoming)
                    # Do not mark as a completed purchase or change budgets.
                    changed.add(player.id)
                    buys[buyer_id]+=1
                    manager_bids_this_review+=1
                    manager_bids_window+=1
                    if posture!='transfer_listed':manager_unlisted_window+=1
                    continue
                result=_finalize(world,seller_id,buyer_id,player,fee,demand,today)
                outcomes.append(result)
                changed.add(player.id)
                buys[buyer_id]+=1
                sales[seller_id]+=1
                for key in tuple(seller_cache):
                    if key[0]==seller_id:
                        seller_cache.pop(key,None)
                # Re-evaluate the buyer's tactical coverage after this signing.
                break
    return outcomes
