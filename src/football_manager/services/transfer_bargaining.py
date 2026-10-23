"""TS-FIX-02 seller bargaining: packages, concessions and persistent patience.

Only explicit counteroffers/reasons are public. Internal valuations, discounted
cash weights and acceptance floors must never be sent to the client as advice.
"""
from __future__ import annotations

from dataclasses import replace
from datetime import timedelta

from football_manager.domain.transfer_negotiation import TransferBonus, TransferTerms, NegotiationEvent, MAX_FEE


def seller_policy(registry, seller_id: str, player, now) -> dict:
    account = registry.club_finances[seller_id]
    # Liquidity affects STRUCTURE, not the other side's private budget.
    monthly_cost = account.recurring_operations_gbp + account.wage_budget_weekly_gbp * 52 // 12
    urgent = account.cash_gbp < monthly_cost * 2
    young = player.age_on(now) <= 25
    return {'urgent': urgent, 'young': young}


def installment_present_value(registry, seller_id: str, player, terms, now) -> int:
    if not terms.installments_gbp:
        return 0
    from football_manager.services.transfer_installments import schedule
    annual_discount = .18 if seller_policy(registry, seller_id, player, now)['urgent'] else .09
    return round(sum(amount / (1 + annual_discount) ** ((i + 1) * terms.installment_interval_months / 12)
                     for i, (_, amount) in enumerate(schedule(terms, now))))


def _round_up(amount: float) -> int:
    return max(0, min(MAX_FEE, (int(amount) + 4_999) // 5_000 * 5_000))


def _counter_package(registry, player, offer, required: int, now, policy: dict) -> TransferTerms:
    from football_manager.services.transfer_negotiation import _quote_terms, _unit
    original = offer.terms
    # Prefer the submitted structure. The seller may substitute uncertain money,
    # shorten a long financing horizon, or add a milestone/resale participation.
    t = original
    if original.installments_gbp:
        interval = min(original.installment_interval_months, 6 if policy['urgent'] else 12)
        count = min(original.installment_count, 4)
        fixed = max(original.fixed_gbp, _round_up(required * (.65 if policy['urgent'] else .28)))
        deferred = max(original.installments_gbp, _round_up(required * (.28 if policy['urgent'] else .55)))
        t = replace(original, fixed_gbp=fixed, installments_gbp=deferred,
                    installment_count=count, installment_interval_months=interval)
    elif not policy['urgent']:
        # Existing bonus terms are retained if affordable in the technical model;
        # outrageous speculative awards are not allowed to replace secure money.
        bonuses = tuple(replace(b, amount_gbp=min(b.amount_gbp, max(10_000, _round_up(required * .4))))
                        for b in original.bonuses)
        t = replace(original, bonuses=bonuses)
        flavor = _unit(registry.seed, 'package', offer.seller_id, player.id)
        if policy['young'] and flavor < .60 and not t.sell_on_percent:
            t = replace(t, sell_on_type='profit', sell_on_percent=15)
        if not bonuses and (policy['young'] or flavor >= .60):
            t = replace(t, bonuses=(TransferBonus('appearances', 20, max(10_000, _round_up(required * .25))),))
    else:
        # Cash-poor clubs make the trade-off explicit rather than assigning full
        # value to a bonus that may never be paid.
        t = replace(t, bonuses=())

    # Solve the cash gap using the same evaluator that will judge acceptance.
    # Allow a small staged concession, never an arbitrary series of price raises.
    target = int(required * max(.96, 1.045 - offer.refusal_count * .017))
    minimum_fixed = _round_up(required * (.55 if policy['urgent'] else .20))
    t = replace(t, fixed_gbp=max(t.fixed_gbp, minimum_fixed))
    if t.guaranteed_gbp > MAX_FEE:
        t = replace(t, installments_gbp=0, installment_count=0, installment_interval_months=0,
                    fixed_gbp=min(MAX_FEE, target))
    # A buyback option cannot be priced below the complete guaranteed purchase.
    if t.buyback_gbp is not None and t.buyback_gbp <= t.guaranteed_gbp:
        t = replace(t, buyback_gbp=None, buyback_until=None)
    for _ in range(3):
        adjusted = _quote_terms(registry, player, t, offer.buyer_id, now)
        gap = target - adjusted
        if gap <= 0:
            break
        fixed = min(MAX_FEE - t.installments_gbp, _round_up(t.fixed_gbp + gap))
        t = replace(t, fixed_gbp=fixed)
        if t.buyback_gbp is not None and t.buyback_gbp <= t.guaranteed_gbp:
            t = replace(t, buyback_gbp=None, buyback_until=None)
    t.validate()
    return t


def seller_reply(registry, offer, player, required: int, now):
    from football_manager.services.transfer_negotiation import _quote_terms
    policy = seller_policy(registry, offer.seller_id, player, now)
    evaluation = _quote_terms(registry, player, offer.terms, offer.buyer_id, now)
    minimum_cash = required * (.38 if policy['urgent'] else .08)
    acceptance = int(required * max(.96, 1.0 - offer.refusal_count * .008))
    if (required > 0 and evaluation >= acceptance
            and offer.terms.guaranteed_gbp >= required * .55
            and offer.terms.fixed_gbp >= minimum_cash):
        return replace(offer, status='agreed', expires_on=now + timedelta(days=45),
            reason='Club terms agreed; awaiting player consent')
    if required <= 0:
        return replace(offer, status='rejected', reason='Seller cannot offer a valid contracted transfer')

    previous = [e for e in offer.events[:-1] if e.by_club_id == offer.buyer_id]
    ratio = evaluation / max(1, required)
    loss = 32 if ratio < .4 else 22 if ratio < .7 else 13 if ratio < .9 else 7
    if previous:
        last = _quote_terms(registry, player, previous[-1].terms, offer.buyer_id, now)
        if evaluation <= last * 1.005:
            loss += 18
        elif evaluation >= last * 1.10:
            loss = max(4, loss - 6)
    remaining = max(0, offer.tolerance_remaining - loss)
    # One visible final warning before an otherwise surprising immediate break.
    if remaining == 0 and offer.tolerance_remaining > 20:
        remaining = 10
    if remaining == 0 or len(offer.events) >= 30:
        return replace(offer, status='rejected', tolerance_remaining=0,
            reason='Talks ended: repeated unacceptable offers exhausted the selling club. New talks may open after 14 days.')

    counter = _counter_package(registry, player, offer, required, now, policy)
    if counter.installments_gbp:
        note = 'Seller counteroffer: revised upfront payment and installment schedule'
    elif counter.bonuses != offer.terms.bonuses or counter.sell_on_percent != offer.terms.sell_on_percent:
        note = 'Seller counteroffer: secure fee with performance or future-sale conditions'
    else:
        note = 'Seller counteroffer: a stronger guaranteed payment is required'
    if remaining <= 20:
        reason = 'Final warning: another unacceptable proposal may end these talks.'
    elif policy['urgent']:
        reason = 'The seller prioritizes immediate cash over uncertain or long-deferred payments.'
    elif counter.installments_gbp:
        reason = 'The seller will consider installments on the stated schedule, with a stronger guaranteed package.'
    elif counter.bonuses or counter.sell_on_percent:
        reason = 'The seller is willing to discuss a package including the conditions in this counteroffer.'
    else:
        reason = 'Your offer was declined. The club remains open to negotiation on the revised terms.'
    event = NegotiationEvent(now, offer.seller_id, counter, note)
    return replace(offer, terms=counter, proposed_by=offer.seller_id,
        events=(*offer.events, event), refusal_count=offer.refusal_count + 1,
        tolerance_remaining=remaining, expires_on=now + timedelta(days=21),
        status='manager_turn', reason=reason)


def public_tolerance(deal) -> dict:
    remaining = deal.tolerance_remaining
    if deal.status in ('rejected', 'withdrawn', 'expired', 'failed'):
        level = 'Closed'
    elif deal.status in ('agreed', 'completed'):
        level = 'Agreed'
    else:
        level = 'Open' if remaining > 75 else 'Cautious' if remaining > 50 else 'Tense' if remaining > 20 else 'Critical'
    # This describes patience, never the probability of accepting an amount.
    return {'level': level, 'remaining_percent': ((remaining + 9) // 10) * 10,
            'warning': level == 'Critical',
            'description': 'Club patience, not a price recommendation or an acceptance probability.'}
