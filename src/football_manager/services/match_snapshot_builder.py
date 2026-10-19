from __future__ import annotations

from typing import Mapping

from football_manager.domain.club import Club
from football_manager.domain.lineup import LineupEntry, MatchLineup
from football_manager.domain.match_context import MatchContextSnapshot
from football_manager.domain.match_snapshot import (
    MatchSnapshot,
    PlayerFamiliaritySnapshot,
    PlayerMatchSnapshot,
    PlayerStateSnapshot,
    Position,
    RoleExecutionSnapshot,
    TacticalSlotSnapshot,
    TacticMatchSnapshot,
    TeamMatchSnapshot,
)
from football_manager.domain.player import Player
from football_manager.domain.player_ratings import CurrentRatingContext
from football_manager.domain.roles import evaluate_role_context
from football_manager.domain.tactics import Tactic


def _snapshot_state(player: Player) -> PlayerStateSnapshot:
    state = player.state
    return PlayerStateSnapshot(
        fitness=state.fitness,
        fatigue=state.fatigue,
        form=state.form,
        # Freeze effective morale once. Mid-match reassignment reconstructs a
        # neutral-offset temporary Player and must not apply TS-20 twice.
        morale=state.effective_morale,
        confidence=state.confidence,
        match_sharpness=state.match_sharpness,
        injury=state.injury,
        suspended_matches=state.suspended_matches,
    )


def _snapshot_familiarity(player: Player) -> PlayerFamiliaritySnapshot:
    # Snapshots carry effective position familiarity so ACT, role execution and
    # the fast simulator all use the same sparse-data transfer rules.
    positions = tuple((position, player.familiarity_for(position)) for position in Position)
    roles = tuple(sorted(player.tactical_familiarity.role_values.items()))
    tactics = tuple(sorted(player.tactical_familiarity.tactic_values.items()))
    return PlayerFamiliaritySnapshot(
        positions=positions,
        roles=roles,
        tactics=tactics,
    )


def _base_player_snapshot(player: Player) -> dict[str, object]:
    return {
        "player_id": player.id,
        "full_name": player.full_name,
        "birth_date": player.identity.birth_date,
        "nationality": player.identity.nationality,
        "dominant_foot": player.identity.dominant_foot,
        "attributes": player.attributes,
        "state": _snapshot_state(player),
        "familiarity": _snapshot_familiarity(player),
        "overall_rating": player.overall_rating,
        "current_rating": player.current_rating().current,
        "original_position": player.original_position,
    }


def _snapshot_starter(
    entry: LineupEntry,
    lineup: MatchLineup,
    tactic: Tactic,
    chemistry_by_player: Mapping[str, float] | None = None,
) -> PlayerMatchSnapshot:
    player = entry.player
    position = lineup.formation.slot(entry.slot_id).position
    role = tactic.role_for_slot(entry.slot_id)
    role_context = evaluate_role_context(
        player=player,
        position=position,
        role=role,
        tactic_id=tactic.tactic_id,
    )
    base = _base_player_snapshot(player)
    rating = player.current_rating(
        CurrentRatingContext(
            assigned_position=position,
            role_id=role.role_id,
            tactic_id=tactic.tactic_id,
            chemistry=(chemistry_by_player or {}).get(player.id, 65.0),
        )
    )
    # Starter snapshots carry OVR for the actual tactical job, not the player's
    # generic/natural-position OVR. Fast sim and 2D therefore consume the same
    # role-specific quality that the UI displays.
    base["overall_rating"] = rating.overall
    base["current_rating"] = rating.current
    return PlayerMatchSnapshot(
        **base,
        assigned_slot_id=entry.slot_id,
        assigned_position=position,
        role_id=role.role_id,
        role_name=role.name,
        effective_instructions=tactic.effective_player_instructions(entry.slot_id),
        role_context=RoleExecutionSnapshot(
            position_familiarity=role_context.position_familiarity,
            role_familiarity=role_context.role_familiarity,
            tactic_familiarity=role_context.tactic_familiarity,
            role_suitability=role_context.role_suitability,
        ),
        rating_chemistry=(chemistry_by_player or {}).get(player.id, 65.0),
    )


def _snapshot_bench_player(
    player: Player,
    chemistry_by_player: Mapping[str, float] | None = None,
) -> PlayerMatchSnapshot:
    return PlayerMatchSnapshot(
        **_base_player_snapshot(player),
        rating_chemistry=(chemistry_by_player or {}).get(player.id, 65.0),
    )


def _snapshot_tactic(tactic: Tactic) -> TacticMatchSnapshot:
    slots = tuple(
        TacticalSlotSnapshot(
            slot_id=slot.slot_id,
            position=slot.position,
            role_id=tactic.role_for_slot(slot.slot_id).role_id,
            role_name=tactic.role_for_slot(slot.slot_id).name,
            effective_instructions=tactic.effective_player_instructions(slot.slot_id),
        )
        for slot in tactic.formation.slots
    )
    return TacticMatchSnapshot(
        tactic_id=tactic.tactic_id,
        name=tactic.name,
        formation=tactic.formation,
        preset_origin=tactic.preset_origin,
        team_instructions=tactic.team_instructions,
        slots=slots,
        style=tactic.analyze_style(),
        phase_shapes=tactic.phase_shapes,
    )


def build_team_match_snapshot(
    *,
    club: Club,
    lineup: MatchLineup,
    tactic: Tactic,
    chemistry_by_player: Mapping[str, float] | None = None,
    set_piece_preferences: Mapping[str, tuple[str, ...]] | None = None,
) -> TeamMatchSnapshot:
    club.validate_lineup(lineup)
    if tactic.formation != lineup.formation:
        raise ValueError("tactic formation must match submitted lineup formation")

    return TeamMatchSnapshot(
        club_id=club.club_id,
        club_name=club.name,
        club_short_name=club.short_name,
        country=club.country,
        formation=lineup.formation,
        starters=tuple(
            _snapshot_starter(
                entry,
                lineup=lineup,
                tactic=tactic,
                chemistry_by_player=chemistry_by_player,
            )
            for entry in lineup.starters
        ),
        bench=tuple(
            _snapshot_bench_player(player, chemistry_by_player) for player in lineup.bench
        ),
        tactic=_snapshot_tactic(tactic),
        set_piece_preferences=dict(set_piece_preferences or {}),
    )


def build_match_snapshot(
    *,
    match_id: str,
    seed: int,
    context: MatchContextSnapshot,
    home_club: Club,
    home_lineup: MatchLineup,
    home_tactic: Tactic,
    away_club: Club,
    away_lineup: MatchLineup,
    away_tactic: Tactic,
    home_chemistry_by_player: Mapping[str, float] | None = None,
    away_chemistry_by_player: Mapping[str, float] | None = None,
    home_set_piece_preferences: Mapping[str, tuple[str, ...]] | None = None,
    away_set_piece_preferences: Mapping[str, tuple[str, ...]] | None = None,
) -> MatchSnapshot:
    home_team = build_team_match_snapshot(
        club=home_club,
        lineup=home_lineup,
        tactic=home_tactic,
        chemistry_by_player=home_chemistry_by_player,
        set_piece_preferences=home_set_piece_preferences,
    )
    away_team = build_team_match_snapshot(
        club=away_club,
        lineup=away_lineup,
        tactic=away_tactic,
        chemistry_by_player=away_chemistry_by_player,
        set_piece_preferences=away_set_piece_preferences,
    )
    return MatchSnapshot(
        match_id=match_id,
        seed=seed,
        context=context,
        home_team=home_team,
        away_team=away_team,
    )
