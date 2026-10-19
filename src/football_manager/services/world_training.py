"""TS-21.4: club-wide training opportunity, independent of nationality or division.

No staff or facilities are invented: quality is explicitly marked as a proxy
based on the opening squad and a stable club-specific perturbation. An imported
verified environment takes precedence. The proxy is calculated only at creation
or a one-time save migration, never after each promotion or player improvement.
"""
from __future__ import annotations

from dataclasses import replace
from datetime import date
from hashlib import sha256

from football_manager.domain.player_development import (
    DevelopmentEnvironment, current_ability,
)

PROXY_SOURCE = 'estimated-squad-support-v1'
NEUTRAL_SOURCE = 'provisional-neutral-v1'


def _jitter(seed: int, club_id: str, kind: str) -> float:
    payload = f'club-support-v1|{seed}|{club_id}|{kind}'.encode('utf-8')
    bucket = int.from_bytes(sha256(payload).digest()[:8], 'big') / (2**64 - 1)
    return (2 * bucket - 1) * 5.0


def _bounded(value: float) -> float:
    return round(min(76.0, max(44.0, value)), 2)


def estimated_training_environment(registry, club_id: str) -> DevelopmentEnvironment:
    """Opening-club *estimate*; not a claim about real facilities or coaches."""
    club = registry.clubs[club_id]
    players = club.squad.players
    if not players:
        return DevelopmentEnvironment()
    ability = sum(current_ability(player) for player in players) / len(players)
    return DevelopmentEnvironment(
        training_quality=_bounded(58.0 + (ability - 65.0) * .35 + _jitter(registry.seed, club_id, 'training')),
        coaching_quality=_bounded(58.0 + (ability - 65.0) * .32 + _jitter(registry.seed, club_id, 'coaching')),
        source=PROXY_SOURCE,
    )


def initialize_club_training(registry, *, upgrade_neutral: bool = False) -> int:
    """One-time new-club initialization or v8 migration; preserves imported data.

    `upgrade_neutral` is only for the explicit v8 -> v9 save migration. In a
    new world the environment map starts empty; existing saves do not get
    rescaled on every load. Clubs without a football identity stay neutral.
    """
    changed = 0
    for club_id in registry.clubs:
        existing = registry.development_environments.get(club_id)
        if existing is None or (upgrade_neutral and existing.source == NEUTRAL_SOURCE):
            if club_id in registry.identities:
                registry.development_environments[club_id] = estimated_training_environment(registry, club_id)
            else:
                registry.development_environments[club_id] = DevelopmentEnvironment()
            changed += 1
    return changed


def month_club_fixtures(world, boundary: date) -> dict[str, int]:
    """Count actual recorded fixtures of the month about to close (all cups).

    One pass over the world's completed fixtures, never one scan per player.
    Reads the committed fixture ledger, so replay/save reads cannot award days.
    """
    registry = world.football_world
    if registry is None:
        return {}
    if boundary.month == 1:
        year, month = boundary.year - 1, 12
    else:
        year, month = boundary.year, boundary.month - 1
    counts: dict[str, int] = {}
    for fixture_id in world.results:
        fixture = world.fixtures.get(fixture_id)
        if fixture is None or fixture.match_date.year != year or fixture.match_date.month != month:
            continue
        for club_id in (fixture.home_club_id, fixture.away_club_id):
            if club_id in registry.clubs:
                counts[club_id] = counts.get(club_id, 0) + 1
    return counts


def effective_training_environment(environment: DevelopmentEnvironment, matches: int) -> DevelopmentEnvironment:
    """Small fixture-congestion effect; 0-4 games is the neutral opportunity.

    Reduces training time at 5+ games rather than punishing the same player
    twice for his minutes, fatigue and injury. No fictional training sessions.
    """
    if type(matches) is not int or matches < 0:
        raise ValueError('monthly fixture count must be a nonnegative integer')
    environment.validate()
    if matches <= 4:
        return environment
    multiplier = max(.78, 1.0 - .025 * (matches - 4))
    return replace(environment, training_quality=round(environment.training_quality * multiplier, 4))
