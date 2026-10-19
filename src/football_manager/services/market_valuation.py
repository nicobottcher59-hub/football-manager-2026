"""Global monthly market quote clock; all clubs share one pricing policy.

No price recalculation on a squad GET or per fixture. Dates, money and quotes
persist in the normal SQLite manager save. No fake contract data is generated.
"""
from __future__ import annotations

from datetime import date

from football_manager.domain.market_valuation import market_value_for_player, MarketQuote


def iter_market_players(registry):
    """The same prices cover all professional and U17/U21 academy players.

    Previews in U15 are intentionally excluded: they are not registered
    footballers and cannot be transferred. IDs remain unique across squads.
    """
    for club in registry.clubs.values():
        yield from club.squad.players
    if registry.youth is not None:
        for academy in registry.youth.academies.values():
            yield from academy.u17.values()
            yield from academy.u21.values()


def initialize_market(registry, on_date: date) -> None:
    """One-time on new career or compatible save migration. No player changes."""
    if registry.market_review_on is not None:
        return
    on_month = on_date.replace(day=1)
    quotes: dict[str, MarketQuote] = {}
    for player in iter_market_players(registry):
        quotes[player.id] = market_value_for_player(player, on_date, registry.seed)
    registry.market_values = quotes
    registry.market_review_on = on_month


def review_market(world, on_date: date) -> int:
    """Refresh monthly once; must participate in the active season journal."""
    registry = world.football_world
    if registry is None or registry.market_review_on is None or on_date.replace(day=1) <= registry.market_review_on:
        return 0
    if world._active_journal is None:
        raise RuntimeError('market review needs world transaction')
    previous = registry.market_review_on
    world._active_journal.undo_callbacks.setdefault(
        ('market-clock', id(registry)),
        lambda: setattr(registry, 'market_review_on', previous),
    )
    count = 0
    active_ids: set[str] = set()
    for player in iter_market_players(registry):
        new_quote = market_value_for_player(player, on_date, registry.seed)
        world._put(registry.market_values, player.id, new_quote)
        active_ids.add(player.id)
        count += 1
    # Reclaim snapshots for retired/released players, not their histories.
    # Undo callbacks participate in the same atomic world transaction.
    for pid in tuple(registry.market_values):
        if pid not in active_ids:
            previous_quote = registry.market_values[pid]
            world._active_journal.undo_callbacks.setdefault(
                ('market-prune', id(registry), pid),
                lambda key=pid, old=previous_quote: registry.market_values.__setitem__(key, old),
            )
            del registry.market_values[pid]
    registry.market_review_on = on_date.replace(day=1)
    return count


def player_market_view(registry, player, as_of: date) -> dict:
    """Presentation-only, with no speculative asking prices or hidden PA."""
    quote = registry.market_values.get(player.id)
    if quote is None:
        # New entrants/promotions may join between scheduled monthly reviews;
        # read-only bootstrap fallback, no mutation or retroactive fees.
        quote = market_value_for_player(player, as_of, registry.seed)
    provisional = player.id not in registry.market_values
    return {'market_value': format_gbp(quote.value_gbp),
            'market_value_gbp': quote.value_gbp,
            'market_value_as_of': quote.as_of.isoformat(),
            'market_value_status': 'provisional' if provisional else 'monthly_estimate',
            'market_value_note': ('Provisional until the next monthly review. ' if provisional else '')
                 + 'Estimated market value. The seller has not quoted an asking price; the contract does not guarantee a sale.'}


def format_gbp(amount: int) -> str:
    if amount >= 1_000_000:
        return f'£{amount / 1_000_000:,.1f}M'.replace('.0M','M')
    if amount >= 1_000:
        return f'£{amount / 1_000:,.0f}K'
    return f'£{amount:,}'
