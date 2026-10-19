"""Frozen pre-TS-21.1.1 reference paths, for regression tests only."""
from __future__ import annotations
from football_manager.domain.club import Club
from football_manager.domain.enums import Position
from football_manager.domain.lineup import MatchLineup, LineupEntry
from football_manager.domain.tactics import Tactic
from football_manager.domain.player import Player
from football_manager.domain.player_ratings import (
    CurrentRatingContext, PlayerRatingBreakdown, calculate_overall_breakdown,
    _state_adjustments, _familiarity_adjustment, _bidirectional_adjustment,
    _context_excellence_bonus, _RATING_MIN, _RATING_MAX,
)
from football_manager.services.world_squads import _score, maximum_assignment, position_family

def legacy_select_lineup(club: Club, tactic: Tactic, *, excluded: frozenset[str] = frozenset(),
                  current: bool = True, bench_size: int = 7) -> MatchLineup:
    players = sorted((p for p in club.squad.players if p.state.is_available and p.id not in excluded),
                     key=lambda p: p.id)
    if len(players) < 11 or not any(p.primary_position is Position.GK for p in players):
        raise ValueError(f'{club.name} cannot field 11 available players and a goalkeeper')
    weights = [[_score(player, slot, tactic, current) for player in players]
               for slot in tactic.formation.slots]
    assignments = maximum_assignment(weights)
    entries = tuple(LineupEntry(slot.slot_id, players[index])
                    for slot, index in zip(tactic.formation.slots, assignments, strict=True))
    used = {entry.player.id for entry in entries}
    remaining = [p for p in players if p.id not in used]
    # Reserve goalkeeper, then positional cover; no duplicate substitute IDs.
    bench = []
    for family in ('GK', 'CB', 'FB', 'MID', 'WIDE', 'ST', 'MID'):
        options = [p for p in remaining if position_family(p.primary_position) == family]
        if options and len(bench) < bench_size:
            best = max(options, key=lambda p: (max(_score(p, s, tactic, current)
                                                for s in tactic.formation.slots), p.id))
            bench.append(best); remaining.remove(best)
    remaining.sort(key=lambda p: (-p.overall_rating, p.id))
    bench.extend(remaining[:max(0, bench_size - len(bench))])
    return MatchLineup(club.id, tactic.formation, entries, tuple(bench))


def legacy_select_team(club: Club, identity):
    """Use the alternative only when available personnel execute it better."""
    candidates = []
    for order, tactic in enumerate((identity.primary, identity.alternative)):
        try:
            lineup = legacy_select_lineup(club, tactic)
        except ValueError:
            continue
        value = sum(_score(e.player, tactic.formation.slot(e.slot_id), tactic, True)
                    for e in lineup.starters) / 11 - order * 3.0
        candidates.append((value, -order, lineup, tactic))
    if not candidates:
        raise ValueError(f'{club.name} has no valid lineup')
    _, _, lineup, tactic = max(candidates, key=lambda item: item[:2])
    return lineup, tactic



def legacy_current_rating(
    player: Player,
    context: CurrentRatingContext | None = None,
) -> PlayerRatingBreakdown:
    """Estimate ACT from contextual OVR plus current execution modifiers.

    The role/position assignment establishes OVR first. ACT then answers how much
    of that role-specific quality is available right now. Position familiarity is
    already part of OVR and therefore is not applied a second time here.
    """

    context = context or CurrentRatingContext()
    overall_breakdown = calculate_overall_breakdown(
        player,
        assigned_position=context.assigned_position,
        role_id=context.role_id,
    )
    overall = overall_breakdown.overall
    adjustments = _state_adjustments(player)
    adaptability = float(player.attributes.mental.adaptability)
    position_score: float | None = None
    role_score: float | None = None
    tactic_score: float | None = None

    if context.assigned_position is not None:
        position_score = player.familiarity_for(context.assigned_position)

    if context.role_id is not None:
        role_score = player.tactical_familiarity.role_score(context.role_id)
        adjustments.append(
            (
                "role_familiarity",
                _familiarity_adjustment(
                    role_score,
                    max_penalty=6.0,
                    max_bonus=0.6,
                    adaptability=adaptability,
                    penalty_exponent=1.8,
                ),
            )
        )

    if context.tactic_id is not None:
        tactic_score = player.tactical_familiarity.tactic_score(context.tactic_id)
        adjustments.append(
            (
                "tactic_familiarity",
                _familiarity_adjustment(
                    tactic_score,
                    max_penalty=5.0,
                    max_bonus=0.6,
                    adaptability=adaptability,
                    penalty_exponent=1.8,
                ),
            )
        )

    adjustments.append(
        (
            "chemistry",
            _bidirectional_adjustment(
                context.chemistry,
                max_penalty=3.0,
                max_bonus=0.8,
            ),
        )
    )
    adjustments.append(
        (
            "context_excellence",
            _context_excellence_bonus(
                player,
                context,
                position_score=position_score,
                role_score=role_score,
                tactic_score=tactic_score,
            ),
        )
    )

    rounded_adjustments = tuple((name, round(value, 2)) for name, value in adjustments)
    current = overall + sum(value for _, value in rounded_adjustments)
    current = round(max(_RATING_MIN, min(_RATING_MAX, current)), 1)
    return PlayerRatingBreakdown(
        overall=overall,
        current=current,
        adjustments=rounded_adjustments,
        overall_components=(
            ("attribute_fit", overall_breakdown.attribute_fit),
            ("position_familiarity", overall_breakdown.position_familiarity),
            ("position_adjustment", overall_breakdown.position_adjustment),
            ("side_adjustment", overall_breakdown.side_adjustment),
        ),
    )
