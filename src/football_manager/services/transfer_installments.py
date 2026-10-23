"""TS-FIX-02: exact, dated guaranteed liabilities, independent of player ownership.

Payment 1 is one interval AFTER registration, never after negotiations start.
All mutations go through the existing world transaction journal. Integer pounds
are distributed with the remainder on the final payment. Reloading, reselling,
retiring or demoting the player never deletes a club's financial obligation.
"""
from __future__ import annotations

from dataclasses import replace
from datetime import date


def schedule(terms, settled_on: date) -> list[tuple[date, int]]:
    from football_manager.services.club_economy import _date_plus_months
    if not terms.installments_gbp:
        return []
    each, remainder = divmod(terms.installments_gbp, terms.installment_count)
    return [(_date_plus_months(settled_on, (i + 1) * terms.installment_interval_months),
             each + (remainder if i == terms.installment_count - 1 else 0))
            for i in range(terms.installment_count)]


def paid_deferred(deal) -> int:
    if not deal.terms.installments_gbp or not deal.installments_paid:
        return 0
    each, remainder = divmod(deal.terms.installments_gbp, deal.terms.installment_count)
    return each * deal.installments_paid + (remainder if deal.installments_paid == deal.terms.installment_count else 0)


def outstanding_deferred(registry, club_id: str, now: date, exclude_id: str = '') -> int:
    manager = registry.youth.managed_club_id if registry.youth else None
    return sum(d.terms.installments_gbp - paid_deferred(d)
               for d in registry.transfer_offers.values()
               if d.deal_id != exclude_id and d.buyer_id == club_id
               and (d.status == 'completed' or
                    (d.expires_on >= now and (d.status == 'agreed' or
                     (d.status == 'manager_turn' and d.seller_id == manager)))))


def deferred_capacity(registry, club_id: str, now: date, exclude_id: str = '') -> int:
    """Board credit policy, not a price hint: 25% of annual recurring income.

    The public finance allowance is cumulative across pending/closed deals; it
    prevents unlimited signings with tiny upfront fees and huge deferred debt.
    """
    account = registry.club_finances[club_id]
    allowance = account.recurring_income_gbp * 3
    return max(0, allowance - outstanding_deferred(registry, club_id, now, exclude_id))


def validate_financing(registry, buyer_id: str, terms, now: date, exclude_id: str = '') -> None:
    from football_manager.services.transfer_negotiation import _availability
    if terms.fixed_gbp > _availability(registry, buyer_id, now, exclude_id):
        raise ValueError('Upfront payment exceeds the available transfer budget')
    if terms.installments_gbp > deferred_capacity(registry, buyer_id, now, exclude_id):
        raise ValueError('Deferred payments exceed board credit: 25% of annual recurring income, less existing commitments')


def settle_due_installments(world, through: date) -> int:
    registry = world.football_world
    if registry is None:
        return 0
    if world._active_journal is None:
        raise RuntimeError('Installment settlements require a world transaction')
    count = 0
    # Chronological cash movements keep both bank balances and audit history
    # deterministic even if a caller advances several years in one operation.
    pending = []
    for deal in registry.transfer_offers.values():
        if deal.status != 'completed' or not deal.terms.installments_gbp:
            continue
        for i, (due, amount) in enumerate(schedule(deal.terms, deal.settled_on)):
            if i >= deal.installments_paid and due <= through:
                pending.append((due, deal.deal_id, i, amount))
    from football_manager.services.transfer_personal import _sell_on_payout
    for due, key, index, amount in sorted(pending):
        deal = registry.transfer_offers[key]
        if index != deal.installments_paid:
            raise ValueError('Installment ledger is not sequential')
        updated = replace(deal, installments_paid=index + 1)
        beneficiary, share = _sell_on_payout(registry, updated)
        payer = registry.club_finances[deal.buyer_id]
        payee = registry.club_finances[deal.seller_id]
        world._put(registry.club_finances, deal.buyer_id, replace(payer,
            cash_gbp=payer.cash_gbp - amount,
            transfer_budget_gbp=max(0, payer.transfer_budget_gbp - amount)))
        world._put(registry.club_finances, deal.seller_id, replace(payee,
            cash_gbp=payee.cash_gbp + amount - share,
            transfer_budget_gbp=payee.transfer_budget_gbp + amount - share))
        if share and beneficiary in registry.club_finances:
            third = registry.club_finances[beneficiary]
            world._put(registry.club_finances, beneficiary, replace(third,
                cash_gbp=third.cash_gbp + share,
                transfer_budget_gbp=third.transfer_budget_gbp + share))
        updated = replace(updated, sell_on_paid_gbp=deal.sell_on_paid_gbp + share)
        updated.validate()
        world._put(registry.transfer_offers, key, updated)
        count += 1
    return count


def finance_summary(registry, club_id: str, now: date) -> dict:
    rows = []
    for deal in registry.transfer_offers.values():
        if deal.status != 'completed' or not deal.terms.installments_gbp:
            continue
        if club_id not in (deal.buyer_id, deal.seller_id):
            continue
        for i, (due, amount) in enumerate(schedule(deal.terms, deal.settled_on)):
            rows.append({'deal_id': deal.deal_id, 'player_id': deal.player_id,
                'number': i + 1, 'due_on': due.isoformat(), 'amount_gbp': amount,
                'paid': i < deal.installments_paid,
                'direction': 'payable' if club_id == deal.buyer_id else 'receivable',
                'counterparty_id': deal.seller_id if club_id == deal.buyer_id else deal.buyer_id})
    rows.sort(key=lambda x: (x['due_on'], x['deal_id'], x['number']))
    return {'payments': rows,
        'outstanding_payable_gbp': sum(r['amount_gbp'] for r in rows if not r['paid'] and r['direction'] == 'payable'),
        'outstanding_receivable_gbp': sum(r['amount_gbp'] for r in rows if not r['paid'] and r['direction'] == 'receivable'),
        'available_credit_gbp': deferred_capacity(registry, club_id, now),
        'credit_policy': '25% of annual recurring income, less existing deferred commitments'}
