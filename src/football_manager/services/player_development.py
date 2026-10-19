"""TS-21.2 integration: one monthly clock, actual match exposure, shared rules.

Reads registered club membership, never English tiers or player-ID prefixes.
No progression on GET/preview, no historical guesses on migration. Writes join
WorldSeasonRunner's journal so failed matches/months roll back in place.
"""
from __future__ import annotations

from dataclasses import replace
from football_manager.services.club_support import department_bonus
from football_manager.services.world_training import (
    initialize_club_training, month_club_fixtures, effective_training_environment,
)
from datetime import date

from football_manager.domain.player_development import (
    DevelopmentEnvironment, PlayerDevelopment, FOCUSES,
    initialize_development, next_month, current_ability,
    reference_overall, review_player, add_match_exposure,
)
from football_manager.domain.roles import default_role_for_position
from football_manager.domain.player_aging import review_career


def initialize_world_development(registry, on_date: date) -> None:
    """Import adapter: preserve IDs, birthdays, all attributes and provided PA."""
    if registry.development_next_review is None:
        registry.development_next_review = next_month(on_date)
    initialize_club_training(registry)
    for club_id, club in registry.clubs.items():
        for player in club.squad.players:
            initialize_development(player, on_date, registry.seed)
            from football_manager.domain.player_aging import initialize_aging
            initialize_aging(player, on_date, registry.seed)


def _checkpoint(world, player) -> None:
    journal = world._active_journal
    if journal is None:
        raise RuntimeError('development mutations require a world transaction')
    key = ('player-development', id(player))
    if key not in journal.undo_callbacks:
        attributes, profile, aging, injury = player.attributes, player.development, player.aging, player.state.injury
        def undo():
            player.attributes = attributes
            player.development = profile
            player.aging = aging
            player.state.injury = injury
        journal.undo_callbacks[key] = undo


def _mentoring_support(club, on_date: date) -> float:
    # Same automatic veteran-presence rule for every club. Uses TS-20's existing
    # personality, not a second social graph or a manager-only mentorship bonus.
    return max((max(0, (p.personality.professionalism - 60) / 40)
                * max(0, (p.personality.leadership - 50) / 50)
                for p in club.squad.players if p.age_on(on_date) >= 27), default=0.0)


def advance_world_development(world, through: date) -> int:
    """Close elapsed months BEFORE fixtures on the new month's first day.

    Calling with the same date is O(1) and idempotent. Empty months still update
    every club; catch-up loops month-by-month rather than rewarding a whole skip
    using its final month's appearances. Offseason uses the same calendar clock.
    """
    registry = world.football_world
    if registry is None or registry.development_next_review is None:
        return 0
    if through < registry.development_next_review:
        from football_manager.services.player_aging import recover_medical_absences
        recover_medical_absences(world, through)
        return 0
    reviews = 0
    with world.transaction():
        previous = registry.development_next_review
        world._active_journal.undo_callbacks.setdefault(
            ('development-clock', id(registry)),
            lambda: setattr(registry, 'development_next_review', previous))
        while registry.development_next_review <= through:
            boundary = registry.development_next_review
            monthly_match_counts = month_club_fixtures(world, boundary)
            from football_manager.services.club_economy import review_finances
            review_finances(world, boundary)
            from football_manager.services.transfer_negotiation import review_transfers
            review_transfers(world, boundary)
            from football_manager.services.youth_academy import process_youth_month
            process_youth_month(world, boundary)
            for club_id, club in registry.clubs.items():
                environment = effective_training_environment(
                    registry.development_environments[club_id], monthly_match_counts.get(club_id, 0))
                support = registry.club_support.get(club_id)
                if support is not None:
                    coach_delta = 3.0 * department_bonus(support, 'coach', boundary)
                    environment = replace(environment,
                        coaching_quality=max(0., min(100., environment.coaching_quality + coach_delta)))
                mentoring = _mentoring_support(club, boundary)
                for player in club.squad.players:
                    profile = player.development
                    if profile is None:
                        raise ValueError('uninitialized player; register development on import')
                    if boundary <= profile.last_review:
                        continue  # Entrant initialized later than this boundary.
                    player_environment = environment
                    if support is not None and player.id in support.training_days:
                        score, days = support.training_days[player.id]
                        if days:
                            player_environment = replace(environment, training_quality=max(0., min(100.,
                                environment.training_quality + max(-2., min(2., score / days)))))
                    attributes, candidate, aging = review_career(player, boundary, player_environment, mentoring=mentoring)
                    _checkpoint(world, player)
                    # A young professional who sits without minutes loses
                    # match rhythm (ACT), never permanent CA/OVR. Reserve games
                    # restore rhythm through their own real youth exposure.
                    if (player.age_on(boundary) <= 22 and profile.exposure.minutes == 0
                            and boundary > profile.last_review):
                        old_sharpness = player.state.match_sharpness
                        world._active_journal.undo_callbacks.setdefault(
                            ('young-first-rhythm', player.id),
                            lambda p=player, value=old_sharpness:
                                setattr(p.state, 'match_sharpness', value))
                        player.state.match_sharpness = max(42., old_sharpness - 2.5)
                    player.attributes, player.development, player.aging = attributes, candidate, aging
                    reviews += 1
            # Monthly ledger is consumed once and must roll back with the world.
            for support in registry.club_support.values():
                if support.training_days:
                    saved = dict(support.training_days)
                    def restore_training_ledger(target=support, previous=saved):
                        target.training_days.clear()
                        target.training_days.update(previous)
                    world._active_journal.undo_callbacks.setdefault(
                        ('ts26-training-month', id(support)), restore_training_ledger)
                    support.training_days.clear()
            from football_manager.services.player_aging import recover_medical_absences
            recover_medical_absences(world, boundary)
            from football_manager.services.market_valuation import review_market
            review_market(world, boundary)
            # Youth moves and AI signings this month require contracts, but
            # their wages cannot be charged for the month just closed.
            from football_manager.services.club_economy import sync_financial_rosters
            sync_financial_rosters(registry,boundary,world=world)
            registry.development_next_review = next_month(boundary)
        from football_manager.services.player_aging import recover_medical_absences
        recover_medical_absences(world, through)
    return reviews



def catch_up_unsigned_player(player, through: date, *, world=None) -> int:
    """Age a returning free agent through *each* month spent without a club.

    A signed free agent is outside the registered squad/youth review loops, so
    his last_review can be many months behind the global clock. Never teleport
    that old profile directly to the present or give him phantom match minutes.
    Use a low-quality, unattached training environment until the month of his
    new agreement; keep the normal ageing/retirement equations. In a world
    transaction the entire player change rolls back alongside the transfer.
    """
    profile = player.development
    if profile is None or player.aging is None:
        raise ValueError('Unsigned player lacks development/ageing history')
    through = through.replace(day=1)
    if profile.last_review >= through:
        return 0
    if world is not None:
        _checkpoint(world, player)
    unattached = DevelopmentEnvironment(0, 0, 'unattached-free-agent-v1')
    reviews = 0
    while next_month(player.development.last_review) <= through:
        boundary = next_month(player.development.last_review)
        attrs, candidate, aging = review_career(player, boundary, unattached)
        player.attributes, player.development, player.aging = attrs, candidate, aging
        reviews += 1
    return reviews


def record_development_exposure(world, fixture_id, result, lineups) -> None:
    """Called once by the existing participation commit, never by a UI read."""
    registry = world.football_world
    day = world.fixtures[fixture_id].match_date
    slots = {(lineup.club_id, e.player.id): default_role_for_position(lineup.formation.slot(e.slot_id).position).role_id
             for lineup in lineups for e in lineup.starters}
    segments = {}
    for segment in result.role_segments:
        if segment.minutes > 0:
            key = (segment.club_id, segment.player_id)
            roles = segments.setdefault(key, {})
            roles[segment.role_id] = roles.get(segment.role_id, 0) + segment.minutes
    qualities = {lineup.club_id: sum(current_ability(e.player) for e in lineup.starters) / 11 for lineup in lineups}
    for stat in result.player_statistics:
        club = registry.clubs.get(stat.club_id)
        if club is None or stat.minutes <= 0:
            continue
        player = club.squad.get(stat.player_id)
        profile = player.development
        if profile is None:
            raise ValueError('missing development profile')
        if day < profile.started_on:
            continue  # Pre-career fixtures/legacy imports never grant retroactive growth.
        if day < profile.last_review or day >= next_month(profile.last_review):
            raise ValueError('match is outside the open development month; advance chronologically')
        role = slots.get((stat.club_id, player.id), default_role_for_position(player.primary_position).role_id)
        role_minutes = segments.get((stat.club_id, player.id), {role: stat.minutes})
        rival_id = result.away_club_id if stat.club_id == result.home_club_id else result.home_club_id
        challenge = max(.65, min(1.25, 1 + (qualities.get(rival_id, current_ability(player)) - current_ability(player)) / 100))
        candidate = add_match_exposure(player, minutes=stat.minutes, rating=stat.match_rating,
                                      role_minutes=role_minutes, challenge=challenge)
        _checkpoint(world, player)
        player.development = candidate


def development_read_model(player, on_date: date) -> dict:
    """Public attributes/history only. Neither exact PA nor latent curve leaks."""
    profile = player.development
    if profile is None:
        return {'available': False, 'message': 'Development is not registered for this player.'}
    last = profile.history[-1] if profile.history else None
    delta = round(last.overall - (profile.history[-2].overall if len(profile.history) > 1 else profile.baseline_overall), 2) if last else None
    messages = {
        'developing': 'Recorded attribute improvement in the last review.',
        'consolidating': 'Small training gains are accumulating; no whole attribute point yet.',
        'mature': 'No recorded attribute change this month.',
        'ceiling': 'No recorded attribute change this month.',
        'injured': 'No development opportunity during the recorded medical absence.',
        'too_young': 'Development reviews start at age 15.',
        'declining': 'Recorded attribute losses: ageing and/or recovery consequences, not temporary fatigue.',
        'mixed': 'Some attributes improved while others declined in the last review.',
        'recovering': 'Injury absence reduced development opportunities this month.',
    }
    from football_manager.domain.player_aging import aging_read_model
    career = aging_read_model(player)
    return {'career': career, 'available': bool(last), 'registered': True,
            'birth_date': player.identity.birth_date.isoformat(), 'age': player.age_on(on_date),
            'tracking_since': profile.started_on.isoformat(), 'last_review': profile.last_review.isoformat() if last else None,
            'next_review': next_month(profile.last_review).isoformat() if not (player.aging and player.aging.retired_on) else 'Retired', 'focus': profile.focus,
            'focus_options': list(FOCUSES), 'period_minutes': profile.exposure.minutes,
            'reference_ovr': reference_overall(player), 'reference_ovr_delta': delta,
            'last_changes': dict(profile.last_changes),
            'history': [{'date': h.on_date.isoformat(), 'reference_ovr': h.overall, 'minutes': h.minutes} for h in profile.history],
            'annual_history': [{'date': h.on_date.isoformat(), 'reference_ovr': h.overall} for h in profile.annual_history],
            'message': messages[last.reason] if last else 'First review at the start of next month. Exact potential is hidden; development is not guaranteed.',
            'note': 'Reference OVR uses original-position role attributes only: fatigue, form and familiarity are excluded. Coaching/training use a persistent estimated club environment (not verified staff or facilities data) until detailed infrastructure is implemented. Age losses and dated medical absences use the same global clock. Retirement is reviewed at season transition; missing replacements postpone departures until youth intake exists.'}


def set_development_focus(session, player_id: str, focus: str) -> dict:
    """Only a managed-club training emphasis, never an editor for PA/curves."""
    if focus not in FOCUSES or not isinstance(player_id, str):
        raise ValueError('invalid development focus')
    if not session.home_club.squad.contains(player_id):
        raise ValueError('only managed-club players can change development focus')
    player = session.home_club.squad.get(player_id)
    profile = player.development
    if profile is None:
        raise ValueError('missing development profile')
    # Applies to the next monthly review; no immediate boost, no reset of credit.
    player.development = replace(profile, focus=focus)
    return {'player_id': player_id, 'focus': focus, 'save_required': True,
            'effective_review': next_month(profile.last_review).isoformat()}


def restart_results_only_tracking(registry, on_date: date) -> None:
    """Scores-only import has no valid development timeline. Keep actual ability,
    PA, curve, identities and fractional learning, but start a new observation
    window. Never replay score-only history as if it contained player minutes.
    """
    from football_manager.domain.player_development import DevelopmentExposure
    registry.development_next_review = next_month(on_date)
    for club in registry.clubs.values():
        for player in club.squad.players:
            if player.development is None:
                initialize_development(player, on_date, registry.seed)
            else:
                player.development = replace(player.development, started_on=on_date, last_review=on_date,
                    baseline_ability=current_ability(player), baseline_overall=reference_overall(player),
                    exposure=DevelopmentExposure(), history=(), annual_history=(), last_changes={})


    # This block belongs to restart_results_only_tracking: preserve current
    # attributes/curve, but never replay dated medical effects from a scores-only archive.
    from football_manager.services.player_aging import restart_aging_observation
    restart_aging_observation(registry, on_date)
