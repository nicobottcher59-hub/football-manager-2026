"""Calendar/match integration for TS-21.3. No league-specific ageing rules."""
from __future__ import annotations

from dataclasses import replace
from datetime import date, timedelta

from football_manager.domain.enums import Position
from football_manager.domain.player_aging import (
    MAX_MEDICAL_HISTORY, RetiredPlayer, create_injury, initialize_aging,
)
from football_manager.domain.player_development import stable_random


def initialize_world_aging(registry, on_date: date) -> None:
    """Migration/new-entrant adapter: identity, attributes and old medical flags stay put."""
    for club in registry.clubs.values():
        for player in club.squad.players:
            initialize_aging(player, on_date, registry.seed)


def _checkpoint(world, player):
    from football_manager.services.player_development import _checkpoint as checkpoint
    checkpoint(world, player)


def _mapping_checkpoint(world, mapping):
    """Small secondary indexes only, not snapshots of the whole football world."""
    journal = world._active_journal
    if journal is None:
        raise RuntimeError('career changes require a transaction')
    key = ('aging-index', id(mapping))
    if key not in journal.undo_callbacks:
        saved = dict(mapping)
        def undo():
            mapping.clear(); mapping.update(saved)
        journal.undo_callbacks[key] = undo


def recover_medical_absences(world, through: date) -> int:
    registry = world.football_world
    if registry is None or not registry.medical_followups:
        return 0
    recovered = 0
    with world.transaction():
        for player_id, (club_id, due) in tuple(registry.medical_followups.items()):
            if due > through:
                continue
            club = registry.clubs[club_id]
            player = club.squad.get(player_id)
            profile, episode = player.aging, player.aging.active_injury
            if episode is None or episode.return_on != due:
                raise ValueError('medical follow-up index mismatch')
            # A risky TS-26 accelerated return may provoke one deterministic
            # setback. Resolve only on the scheduled return, never on a GET.
            support = registry.club_support.get(club_id)
            decision = support.treatments.get(player_id) if support else None
            if (decision is not None and decision.episode_id == episode.episode_id
                    and decision.status == 'active' and decision.will_relapse):
                new_due = due + timedelta(days=decision.relapse_days)
                if (new_due - episode.started_on).days <= 730:
                    _checkpoint(world, player)
                    player.aging = replace(profile, active_injury=replace(episode, return_on=new_due))
                    world._put(registry.medical_followups, player_id, (club_id, new_due))
                    # The support object must follow the world's transactional journal.
                    original = decision.status
                    world._active_journal.undo_callbacks.setdefault(
                        ('ts26-medical', id(decision)),
                        lambda target=decision, old=original: setattr(target, 'status', old))
                    decision.status = 'relapsed'
                    continue
            if decision is not None and decision.episode_id == episode.episode_id:
                original = decision.status
                world._active_journal.undo_callbacks.setdefault(
                    ('ts26-medical', id(decision)),
                    lambda target=decision, old=original: setattr(target, 'status', old))
                decision.status = 'completed'
            _checkpoint(world, player)
            player.aging = replace(profile, active_injury=None,
                medical_history=(*profile.medical_history, episode)[-MAX_MEDICAL_HISTORY:])
            # Only clear the flag owned by this episode, never an external injury.
            if player.state.injury == episode.label:
                player.state.injury = None
            world._active_journal.entries.append((registry.medical_followups, player_id, registry.medical_followups[player_id]))
            registry.medical_followups.pop(player_id)
            recovered += 1
    return recovered


def register_medical_absence(world, club_id: str, player_id: str, on_date: date,
                             *, episode_id: str, duration_days: int, label: str,
                             source: str = 'imported-medical-v1') -> None:
    registry = world.football_world
    player = registry.clubs[club_id].squad.get(player_id)
    candidate = create_injury(player, on_date, episode_id, duration_days, label, source=source)
    with world.transaction():
        _checkpoint(world, player)
        player.aging = candidate
        player.state.injury = candidate.active_injury.label
        world._put(registry.medical_followups, player_id, (club_id, candidate.active_injury.return_on))


def record_postmatch_health(world, fixture_id, result) -> None:
    """Post-match assessments, not invented in-match injury events/substitutions.

    Rates are bounded calibration parameters. Identical fixture/player IDs yield
    identical decisions. Maximum one new absence/club/match, with availability
    guardrails while youth replacements do not exist.
    """
    registry = world.football_world
    day = world.fixtures[fixture_id].match_date
    hits = {}
    for stat in result.player_statistics:
        club = registry.clubs.get(stat.club_id)
        if club is None or stat.minutes <= 0:
            continue
        player = club.squad.get(stat.player_id)
        if player.aging is None or player.aging.active_injury is not None or player.state.injury is not None:
            continue
        if day < player.aging.started_on:
            continue
        rng = stable_random(player.aging.seed, player.id, fixture_id, 'postmatch-health-v1')
        load = 1 + max(0, 65-stat.condition_after)/65 + max(0, stat.fatigue_after-45)/120
        susceptibility = .65 + .7 * player.personality.injury_susceptibility/100
        risk = min(.055, .012 * stat.minutes/90 * susceptibility * load)
        roll = rng.random()
        if roll >= risk:
            continue
        severity = rng.random()
        if severity < .50:
            duration, label = rng.randint(2, 6), 'Minor knock'
        elif severity < .82:
            duration, label = rng.randint(7, 21), 'Muscle strain'
        elif severity < .96:
            duration, label = rng.randint(22, 55), 'Moderate injury'
        else:
            duration, label = rng.randint(60, 150), 'Serious injury'
        hits.setdefault(club.id, []).append((roll/risk, player.id, duration, label))
    for club_id, candidates in hits.items():
        club = registry.clubs[club_id]
        available = [p for p in club.squad.players if p.state.is_available]
        if len(available) <= 13:
            continue
        goalkeepers = sum(p.original_position is Position.GK for p in available)
        for _, player_id, duration, label in sorted(candidates):
            player = club.squad.get(player_id)
            if player.original_position is Position.GK and goalkeepers <= 1:
                continue
            from football_manager.services.club_support import department_bonus
            medical_delta = department_bonus(registry.club_support.get(club_id), 'medic', day)
            duration = max(2, round(duration * (1 - .075 * max(0., medical_delta))))
            register_medical_absence(world, club_id, player_id, day,
                episode_id=f'{fixture_id}:{player_id}', duration_days=duration,
                label=label, source='postmatch-assessment-v1')
            break


def finalize_season_retirements(world, on_date: date, *, managed_club_id=None,
                                managed_tactic=None) -> tuple[str, ...]:
    """Honor each footballer's *own* retirement decision at the season boundary.

    A confirmed retirement is never subject to the club's finances, selection,
    reserve depth, goalkeeper count, injuries or transfer strategy. Clubs own
    the consequences, not the decision. The legacy ``deferred`` state in v16
    saves represents a previously confirmed retirement and is honored too.

    Terminate any active loan and remove the player from medical follow-ups,
    live transfer proposals and the contractual roster. Every change is
    journaled so a failed transition restores the original world.
    """
    registry = world.football_world
    retired = []
    with world.transaction():
        from football_manager.services.loan_market import active_loan
        for club_id, club in registry.clubs.items():
            candidates = [p for p in club.squad.players
                          if p.aging is not None
                          and p.aging.retirement_status in ('requested', 'deferred')
                          and p.aging.retirement_requested_on <= on_date
                          and p.aging.retirement_checked_on != on_date]
            candidates.sort(key=lambda p: (p.identity.birth_date, p.id))
            for player in candidates:
                _checkpoint(world, player)
                loan = active_loan(registry, player.id)
                if loan is not None:
                    # A loan can never force someone to continue playing.
                    # The final club is the borrower; contractual ownership
                    # expires as part of the annual finance roster sync.
                    world._put(registry.loans, loan.loan_id,
                               replace(loan, status='retired', completed_on=on_date))
                player.aging = replace(player.aging, retirement_status='retired',
                                       retirement_checked_on=on_date, retired_on=on_date)
                archive = RetiredPlayer(player, club_id, on_date)
                archive.validate()
                _mapping_checkpoint(world, club.squad._players)
                club.squad._players.pop(player.id)
                if player.id in registry.medical_followups:
                    saved = registry.medical_followups.pop(player.id)
                    world._active_journal.undo_callbacks[('retired-medical', player.id)] = (
                        lambda pid=player.id, record=saved: registry.medical_followups.__setitem__(pid, record))
                # Terminate an unresolved bid; an agreement cannot buy a
                # player who is already recorded in the retirement archive.
                for deal_id, deal in tuple(registry.transfer_offers.items()):
                    if deal.player_id == player.id and deal.status in ('manager_turn', 'agreed', 'pending_window'):
                        world._put(registry.transfer_offers, deal_id,
                                   replace(deal, status='expired', reason='Player retired'))
                world._put(registry.retired_players, player.id, archive)
                retired.append(player.id)
        # Retirees are no longer registered employees; preserve wages earned
        # before the boundary, without inventing compensation or an extension.
        if retired and registry.finance_review_on is not None:
            from football_manager.services.club_economy import sync_financial_rosters
            sync_financial_rosters(registry, on_date, world=world)
    return tuple(retired)


def repair_managed_unavailable(session) -> bool:
    """Calendar auto-sim helper: replace only unavailable selections, not tactics.

    Manual match submission retains the existing availability validation. Healthy
    chosen starters stay in their slots; the auto-sim cannot field an injured one.
    """
    from football_manager.services.world_squads import maximum_assignment, _SelectionScores
    from football_manager.domain.lineup import LineupEntry, MatchLineup
    lineup = session.home_lineup
    squad = session.home_club.squad
    invalid = [p for p in lineup.selected_players if not squad.contains(p.id) or not p.state.is_available]
    if not invalid:
        return False
    fixed = {e.player.id for e in lineup.starters if squad.contains(e.player.id) and e.player.state.is_available}
    vacant = [e for e in lineup.starters if e.player.id not in fixed]
    available = sorted([p for p in squad.players if p.state.is_available and p.id not in fixed], key=lambda p:p.id)
    if len(available) < len(vacant):
        raise ValueError('not enough available players to continue; review the squad')
    scores = _SelectionScores()
    if vacant:
        rows = [[scores.score(p, lineup.formation.slot(e.slot_id), session.home_tactic, True) for p in available] for e in vacant]
        assigned = maximum_assignment(rows)
        replacements = {e.slot_id: available[index] for e, index in zip(vacant, assigned)}
    else:
        replacements = {}
    starters = tuple(LineupEntry(e.slot_id, replacements.get(e.slot_id, e.player)) for e in lineup.starters)
    used = {e.player.id for e in starters}
    bench = [p for p in lineup.bench if squad.contains(p.id) and p.state.is_available and p.id not in used]
    existing = used | {p.id for p in bench}
    candidates = sorted((p for p in available if p.id not in existing), key=lambda p: (p.original_position is not Position.GK, -p.overall_rating, p.id))
    bench.extend(candidates[:max(0, len(lineup.bench)-len(bench))])
    session.home_lineup = MatchLineup(lineup.club_id, lineup.formation, starters, tuple(bench))
    session.home_club.validate_lineup(session.home_lineup)
    return True


def restart_aging_observation(registry, on_date: date) -> None:
    """Scores-only load is not a medical timeline; keep live state, no replay."""
    from football_manager.domain.player_aging import InjuryEpisode
    registry.medical_followups.clear()
    for club in registry.clubs.values():
        for player in club.squad.players:
            profile = initialize_aging(player, on_date, registry.seed)
            episode = (InjuryEpisode(f'legacy:{player.id}:{on_date}', str(player.state.injury), on_date,
                                     None, 'legacy-undated-v1') if player.state.injury else None)
            requested = on_date if profile.retirement_requested_on is not None else None
            player.aging = replace(profile, started_on=on_date, last_review=on_date,
                active_injury=episode, medical_history=(), retirement_requested_on=requested,
                retirement_checked_on=None)
