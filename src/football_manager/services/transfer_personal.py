"""TS-24.4: agent negotiations, consent and atomic full-transfer settlement.

The caller mutates a cloned DevelopmentSession. Neither GET nor failed commands
move assets. Both managed purchases and managed sales use the same agent model.
"""
from __future__ import annotations

from dataclasses import replace
from datetime import date, timedelta
from math import ceil

from football_manager.domain.club_economy import CONTRACT_ROLES, PlayerContract
from football_manager.domain.transfer_personal import PersonalTerms, PersonalEvent
from football_manager.services.club_economy import (
    _date_plus_months, _round_wage, _month_wage, wage_expectation, weekly_payroll,
)
from football_manager.services.transfer_negotiation import _availability, _player

ROLE_ORDER = {name: index for index, name in enumerate(CONTRACT_ROLES)}


def _player_interest(registry, player, seller_id: str, buyer_id: str, now: date) -> tuple[bool, str]:
    """Ability, ambition and division, with reduced barriers for older players.

    A salary cannot purchase the consent of a top-level player to League Two.
    It is deterministic and does not inspect hidden PA or temporary condition.
    """
    if (player.aging is not None and
            player.aging.retirement_status in ('requested','deferred','retired')):
        return False, 'Player has already decided to retire'
    tier = registry.identities[buyer_id].tier
    origin = registry.identities[seller_id].tier
    age = player.age_on(now)
    ovr = player.overall_rating
    ambition = player.personality.ambition
    loyalty = player.personality.loyalty
    capacity = {0: 62, 1: 99, 2: 83, 3: 76, 4: 69}[tier]
    capacity += (3 if age >= 34 else 1 if age >= 31 else 0)
    capacity += round((50 - ambition) / 25)
    if ovr > capacity + 4:
        return False, 'Player considers this division too far below his sporting level'
    if tier > origin and tier >= 3 and ambition >= 80 and ovr > capacity - 2 and age < 32:
        return False, 'Player is unwilling to drop divisions during his peak years'
    if (tier > origin and tier >= 3 and loyalty >= 90 and age < 27
            and ovr >= capacity - 1):
        return False, 'Player prefers to stay with his current club and development pathway'
    return True, 'Player is willing to discuss personal terms'


def _expected_role(registry, player, buyer_id: str) -> str:
    team = sorted((p.overall_rating for p in registry.clubs[buyer_id].squad.players), reverse=True)
    rank = sum(r > player.overall_rating for r in team)
    return 'star' if rank <= 2 else 'important' if rank <= 7 else 'regular' if rank <= 15 else 'rotation'


def agent_demand(registry, player, seller_id: str, buyer_id: str, on_date: date) -> dict:
    """An agent's opening request, recalculated read-only from stable state."""
    current = registry.contracts[player.id]
    possible, reason = _player_interest(registry, player, seller_id, buyer_id, on_date)
    role = _expected_role(registry, player, buyer_id)
    tier_gap = max(0, registry.identities[buyer_id].tier - registry.identities[seller_id].tier)
    step_down = 1 + .10 * tier_gap * (.65 + player.personality.ambition / 120)
    fair = wage_expectation(player, on_date, registry.seed, role=role)
    demand = _round_wage(max(fair * step_down, current.weekly_wage_gbp * (.92 if tier_gap == 0 else 1.02)))
    age = player.age_on(on_date)
    max_years = 2 if age >= 35 else 3 if age >= 32 else 5
    # Signing bonus is negotiable, not a mandatory precondition.
    suggested_bonus = max(0, round(demand * (3 if age >= 30 else 5) / 5_000) * 5_000)
    return {'interested': possible, 'reason': reason, 'weekly_wage_gbp': demand,
            'role': role, 'years': min(max_years, 3), 'max_years': max_years,
            'suggested_signing_bonus_gbp': min(50_000_000,suggested_bonus),
            'current_weekly_gbp': current.weekly_wage_gbp,
            'buyer_tier':registry.identities[buyer_id].tier,'date':on_date}


def _from_data(raw: object) -> PersonalTerms:
    from football_manager.services.contract_bargaining import terms_from_json
    return terms_from_json(raw)


def _financing(registry, deal, terms: PersonalTerms, now: date) -> None:
    from football_manager.services.transfer_installments import validate_financing
    validate_financing(registry,deal.buyer_id,deal.terms,now,deal.deal_id)
    account=registry.club_finances[deal.buyer_id]
    required=deal.terms.fixed_gbp+terms.signing_bonus_gbp
    if required > _availability(registry,deal.buyer_id,now,deal.deal_id):
        raise ValueError('Transfer budget cannot cover fixed fee and signing-on fee')
    if account.cash_gbp < required:
        raise ValueError('Club cash cannot cover fixed fee and signing-on fee')
    wages = weekly_payroll(registry,deal.buyer_id)+terms.weekly_wage_gbp
    if wages > account.wage_budget_weekly_gbp:
        raise ValueError('Club wage budget cannot cover the new contract')


def career_player_totals(registry, player_id: str) -> tuple[int, int, int]:
    """All recorded professional seasons: starts are not appearances."""
    results = [ledger.get(player_id) for ledger in registry.history.values()]
    results.append(registry.usage.get(player_id))
    return tuple(sum(getattr(u, field) for u in results if u is not None)
                 for field in ('appearances','goals','assists'))


def _sell_on_payout(registry, deal) -> tuple[str|None,int]:
    """Previously negotiated gross/profit sell-on triggers on a subsequent sale.

    Only the most recent incoming completed transfer can own this obligation.
    Player identity is stable and the next seller is the previous buyer.
    """
    previous = [d for d in registry.transfer_offers.values()
                if d.player_id == deal.player_id and d.status == 'completed'
                and d.buyer_id == deal.seller_id and d.deal_id != deal.deal_id]
    if not previous:
        return None,0
    source=max(previous,key=lambda d:(d.started_on,d.deal_id))
    if source.terms.sell_on_type=='none' or source.seller_id==deal.seller_id:
        return None,0
    # Conditional bonuses already earned are actual acquisition/sale costs.
    # Unpaid, speculative bonuses do not count in profit calculations.
    from football_manager.services.transfer_installments import paid_deferred
    proceeds = deal.terms.fixed_gbp+paid_deferred(deal)+sum(b.amount_gbp for b in deal.terms.bonuses
                                        if b.kind in deal.bonus_paid)
    cost = source.terms.guaranteed_gbp+sum(b.amount_gbp for b in source.terms.bonuses
                                      if b.kind in source.bonus_paid)
    basis=(proceeds if source.terms.sell_on_type=='gross' else max(0,proceeds-cost))
    total=round(basis*source.terms.sell_on_percent/100)
    # Amount already paid when the original fixed fee cleared cannot be
    # charged again when a later variable becomes due.
    delta=max(0,total-deal.sell_on_paid_gbp)
    return source.seller_id,min(delta,proceeds)


def _repair_selected_team(session, club_id: str) -> None:
    """Keep canonical squads, tactical XI, bench and dressing room synchronized."""
    from football_manager.services.player_aging import repair_managed_unavailable
    from football_manager.services.world_squads import select_team
    from football_manager.services.dressing_room import sync_roster
    if club_id == session.home_club.id:
        repair_managed_unavailable(session)
        session._home_base_tactic_familiarity={p.id:p.tactical_familiarity.tactic_score(session.home_tactic.tactic_id)
                                                  for p in session.home_club.squad.players}
        starter_ids={p.id for p in session.home_lineup.starting_players}
        session._home_chemistry={p.id:session._home_chemistry.get(p.id,65.) for p in session.home_club.squad.players}
        sync_roster(session.dressing_room,session.home_club.squad.players)
        session._sync_effective_tactic_familiarity(home=True)
        session.home_club.validate_lineup(session.home_lineup)
    if club_id == session.away_club.id and club_id != session.home_club.id:
        identity=session._world_squads.identities[club_id]
        session.away_lineup,session.away_tactic=select_team(session.away_club,identity)[0:2]
        session._away_base_tactic_familiarity={p.id:p.tactical_familiarity.tactic_score(session.away_tactic.tactic_id)
                                                  for p in session.away_club.squad.players}
        session._away_chemistry={p.id:65. for p in session.away_club.squad.players}
        session._sync_effective_tactic_familiarity(home=False)


def _finish(session, deal, terms: PersonalTerms) -> dict:
    """Runs against a transactionally cloned session supplied by GameApplication."""
    registry=session._world_squads
    now=session.current_date
    if deal.status!='agreed' or deal.expires_on<now:
        raise ValueError('Club agreement expired or is no longer valid')
    player,old_contract=_player(registry,deal.player_id,deal.seller_id)
    can_move,reason=_player_interest(registry,player,deal.seller_id,deal.buyer_id,now)
    if not can_move:
        raise ValueError(reason)
    demand=agent_demand(registry,player,deal.seller_id,deal.buyer_id,now)
    if terms.years>demand['max_years']:
        raise ValueError('Player declines an excessively long contract')
    if terms.weekly_wage_gbp < 75:
        raise ValueError('A registered professional contract requires a positive wage')
    _financing(registry,deal,terms,now)
    seller=registry.clubs[deal.seller_id]
    buyer=registry.clubs[deal.buyer_id]
    if buyer.squad.contains(player.id):
        raise ValueError('Player is already registered with the buying club')
    remaining = [p for p in seller.squad.players if p.id!=player.id and p.state.is_available]
    if len(remaining)<11 or not any(p.primary_position.value=='GK' for p in remaining):
        raise ValueError('Selling club must retain eleven available players including a goalkeeper')
    if len(buyer.squad)>=45:
        raise ValueError('The first-team squad registration limit is 45 players')
    seller_acc=registry.club_finances[deal.seller_id]
    buyer_acc=registry.club_finances[deal.buyer_id]
    payment=deal.terms.fixed_gbp
    beneficiary, sell_on = _sell_on_payout(registry,deal)
    # Settle seller's already-earned wages in the unfinished finance month.
    # The buyer signs a NEW contract today, so the normal monthly review pays
    # only buyer wages from today onward. Otherwise transfer could erase salary
    # liability for the previous club or charge old wages to the new club.
    from_day=max(registry.finance_review_on,registry.finance_started_on)
    accrued=_month_wage(old_contract,from_day,now-timedelta(days=1)) if now>from_day else 0
    new_contract=PlayerContract(player.id,deal.buyer_id,now,
        _date_plus_months(now,terms.years*12),terms.weekly_wage_gbp,terms.role,'professional')
    new_contract.validate()
    seller.squad.remove(player.id)
    buyer.squad.add(player)
    registry.contracts[player.id]=new_contract
    from football_manager.services.contract_incentives import record_contract_bonuses
    record_contract_bonuses(registry,player.id,deal.buyer_id,now,terms.bonuses)
    registry.club_finances[deal.seller_id]=replace(seller_acc,
        cash_gbp=seller_acc.cash_gbp + payment-sell_on-accrued,
        transfer_budget_gbp=seller_acc.transfer_budget_gbp+payment-sell_on,
        season_wages_gbp=seller_acc.season_wages_gbp+accrued)
    required=payment+terms.signing_bonus_gbp
    registry.club_finances[deal.buyer_id]=replace(buyer_acc,
        cash_gbp=buyer_acc.cash_gbp-required,
        transfer_budget_gbp=buyer_acc.transfer_budget_gbp-required,
        season_operations_gbp=buyer_acc.season_operations_gbp+terms.signing_bonus_gbp)
    if sell_on and beneficiary in registry.club_finances:
        previous=registry.club_finances[beneficiary]
        registry.club_finances[beneficiary]=replace(previous,
            cash_gbp=previous.cash_gbp+sell_on,
            transfer_budget_gbp=previous.transfer_budget_gbp+sell_on)
    if player.id in registry.medical_followups:
        _,due=registry.medical_followups[player.id]
        registry.medical_followups[player.id]=(deal.buyer_id,due)
    for club_id in (deal.seller_id,deal.buyer_id):
        _repair_selected_team(session,club_id)
    if deal.buyer_id==session.home_club.id:
        from football_manager.services.contract_promises import record_contract_role_promise
        record_contract_role_promise(session,player.id,terms.role)
    for key,other in tuple(registry.transfer_offers.items()):
        if key!=deal.deal_id and other.player_id==player.id and other.status in ('agreed','manager_turn'):
            registry.transfer_offers[key]=replace(other,status='expired',reason='Player transferred to another club')
    completed=replace(deal,status='completed',personal_status='completed',
        personal_terms=terms,reason='Transfer completed after player consent',settled_on=now,
        sell_on_paid_gbp=sell_on,bonus_baseline=career_player_totals(registry,player.id),
        buyer_tier_at_signing=registry.identities[deal.buyer_id].tier)
    completed.validate()
    registry.transfer_offers[deal.deal_id]=completed
    registry.validate()
    return {'deal_id':deal.deal_id,'status':'completed','player_id':player.id,
        'player':player.full_name,'from_club':seller.name,'to_club':buyer.name,
        'fixed_gbp':payment,'weekly_wage_gbp':terms.weekly_wage_gbp,
        'signing_bonus_gbp':terms.signing_bonus_gbp,'sell_on_paid_gbp':sell_on,
        'expires_on':new_contract.expires_on.isoformat(),
        'note':'Registration, fee and contract committed; contingent bonuses are retained for future settlement.'}


def personal_command(session,command:dict)->dict:
    """Manager-initiated purchase talk or managed sale to an AI buyer."""
    registry=session._world_squads
    manager=session.home_club.id
    now=session.current_date
    deal_id=command.get('deal_id')
    if type(deal_id) is not str or deal_id not in registry.transfer_offers:
        raise ValueError('Negotiation not found')
    deal=registry.transfer_offers[deal_id]
    if manager not in (deal.buyer_id,deal.seller_id) or deal.status!='agreed' or deal.expires_on<now:
        raise ValueError('An active, agreed club deal is required before personal terms')
    player,_=_player(registry,deal.player_id,deal.seller_id)
    quote=agent_demand(registry,player,deal.seller_id,deal.buyer_id,now)
    action=command.get('action')
    if action=='personal_resolve':
        if deal.seller_id != manager or deal.personal_status!='not_started':
            raise ValueError('Only managed sales can auto-resolve buyer personal negotiations')
        if not quote['interested']:
            registry.transfer_offers[deal_id]=replace(deal,status='failed',personal_status='declined',reason=quote['reason'])
            return {'deal_id':deal_id,'status':'failed','reason':quote['reason']}
        account=registry.club_finances[deal.buyer_id]
        wages_left=account.wage_budget_weekly_gbp-weekly_payroll(registry,deal.buyer_id)
        if wages_left < quote['weekly_wage_gbp'] or deal.terms.fixed_gbp > _availability(registry,deal.buyer_id,now,deal_id):
            reason='The buying club cannot meet the player wage or transfer requirement'
            registry.transfer_offers[deal_id]=replace(deal,status='failed',personal_status='declined',reason=reason)
            return {'deal_id':deal_id,'status':'failed','reason':reason}
        terms=PersonalTerms(quote['weekly_wage_gbp'],quote['years'],quote['role'],0)
        event=PersonalEvent(now,'agent',terms,'Player and buying club agreed personal terms')
        return _finish(session,replace(deal,personal_terms=terms,personal_events=(*deal.personal_events,event)),terms)
    if deal.buyer_id != manager:
        raise ValueError('Only the buying manager may negotiate their own contract offer')
    if action=='personal_accept':
        if deal.personal_status!='counter' or deal.personal_terms is None:
            raise ValueError('No active agent counteroffer to accept')
        if not quote['interested']:
            raise ValueError(quote['reason'])
        return _finish(session,deal,deal.personal_terms)
    if action!='personal_offer':
        raise ValueError('Unsupported player negotiation action')
    if deal.personal_patience<=0:
        raise ValueError('Agent has closed negotiations')
    terms=_from_data(command.get('terms'))
    from football_manager.services.contract_bargaining import validate_player_bonuses
    validate_player_bonuses(player,terms)
    if terms.years>quote['max_years']:
        raise ValueError('Player will not accept that contract duration')
    event=PersonalEvent(now,'club',terms,'Club proposes personal contract terms')
    history=(*deal.personal_events,event)
    if not quote['interested']:
        updated=replace(deal,status='failed',personal_status='declined',personal_terms=terms,
                        personal_events=history,reason=quote['reason'])
        registry.transfer_offers[deal_id]=updated
        return {'deal_id':deal_id,'status':'failed','reason':quote['reason']}
    _financing(registry,deal,terms,now)
    from football_manager.services.contract_bargaining import agent_response, terms_json
    outcome,counter,patience,reason=agent_response(
        player,terms,quote,deal.personal_patience,deal.personal_refusals)
    if outcome=='accept':
        history+=(PersonalEvent(now,'agent',terms,reason),)
        return _finish(session,replace(deal,personal_terms=terms,
            personal_patience=patience,personal_events=history),terms)
    if outcome=='end':
        updated=replace(deal,status='failed',personal_status='declined',personal_terms=terms,
                        personal_events=history,personal_refusals=deal.personal_refusals+1,
                        personal_patience=0,reason=reason)
        updated.validate()
        registry.transfer_offers[deal_id]=updated
        return {'deal_id':deal_id,'status':'failed','reason':reason,'patience':0}
    history+=(PersonalEvent(now,'agent',counter,reason),)
    updated=replace(deal,personal_status='counter',personal_terms=counter,
                    personal_events=history,personal_refusals=deal.personal_refusals+1,
                    personal_patience=patience,reason=reason)
    updated.validate()
    registry.transfer_offers[deal_id]=updated
    return {'deal_id':deal_id,'status':'counter','personal_terms':terms_json(counter),
            'reason':reason,'patience':patience}
