"""UI-only read models/commands. All ratings and tactical rules stay in Python.

The development world/session remains ephemeral: this is NOT a career save system.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass, field, fields, replace
from enum import Enum
from statistics import mean
from football_manager.services.tactical_studio import STUDIO_ACTIONS, apply_studio_command, studio_read_model
from football_manager.services.match_preparation import opponent_report, set_piece_view, assign_order
from football_manager.domain.tactical_geometry import base_points

from football_manager.services.season_statistics import player_statistics, statistics_options
from football_manager.domain.enums import Position
from football_manager.domain.tactical_instructions import (
    PlayerInstructionOverrides, TargetKind, TacticalTarget,
)
from football_manager.domain.tactical_presets import TacticalPreset
from football_manager.dev_ui.session import DevelopmentSession
from football_manager.dev_ui.formations import formation_board_layouts, formation_slot_label, development_formations


GROUPS = ("in_possession", "transition", "out_of_possession", "game_management")


def _display(value: object) -> str:
    if isinstance(value, bool):
        return "on" if value else "off"
    if isinstance(value, Enum):
        return str(value.value) if isinstance(value.value, str) else value.name.lower()
    if isinstance(value, TacticalTarget):
        return f"{value.kind.value}:{value.target_id}"
    return "" if value is None else str(value)


def _options(value: object) -> list[str]:
    if isinstance(value, bool):
        return ["off", "on"]
    if isinstance(value, Enum):
        return [_display(item) for item in type(value)]
    return []


def _round(value: float) -> float:
    return round(float(value), 1)


# These fields are displayed but are not yet recorded as a career-season ledger.
# A missing statistic must be null / "not available", never made-up zero.
SEASON_STAT_KEYS = (
    "appearances", "starts", "minutes", "goals", "assists", "clean_sheets",
    "xg", "xa", "pass_completion", "shots", "shots_on_target", "tackles",
    "yellow_cards", "red_cards", "average_match_rating",
)
TRANSFER_STATUSES = ("normal", "transfer_listed", "loan_listed", "untouchable")


@dataclass
class UIRosterAdmin:
    """Ephemeral UI metadata; never masquerades as a career transfer/contract system."""
    numbers: dict[str, int] = field(default_factory=dict)
    transfer_statuses: dict[str, str] = field(default_factory=dict)


def squad_read_model(session: DevelopmentSession, admin: UIRosterAdmin | None = None, *, season: str | None = None, competition: str | None = None) -> dict:
    """Stable JSON boundary for the Squad and Team Tactics panels.

    Uses DevelopmentSession's real ratings, roles, shape and instruction values;
    does not invent bench members or fabricate a set-piece assignment.
    """
    lineup = session.home_lineup
    tactic = session.home_tactic
    state = session.tactical_team_state()
    tactical = session.tactical_view()
    xi_rows = {r.player_id: r for r in session.squad_rows()}
    admin = admin or UIRosterAdmin()
    slot_by_player = {entry.player.id: entry.slot_id for entry in lineup.starters}
    selected_ids = {p.id for p in lineup.selected_players}
    from football_manager.services.market_valuation import player_market_view
    from football_manager.services.club_economy import contract_view

    def player_payload(player) -> dict:
        row = xi_rows[player.id]
        slot_id = slot_by_player.get(player.id)
        role = tactic.role_for_slot(slot_id) if slot_id is not None else None
        position = lineup.formation.slot(slot_id).position if slot_id is not None else player.primary_position
        familiarity = player.positional_familiarity
        position_codes = {player.primary_position, *player.secondary_positions, *familiarity.values.keys()}
        familiarities = [
            {"position": pos.value, "effective": _round(familiarity.effective_score(pos)),
             "stored": _round(familiarity.score(pos)) if pos in familiarity.values else None,
             "peak": _round(familiarity.peak_values.get(pos, 0.0)) if pos in familiarity.values else None,
             "minutes": _round(familiarity.minutes_for(pos)),
             "is_primary": pos == player.primary_position,
             "is_secondary": pos in player.secondary_positions}
            for pos in sorted(position_codes, key=lambda pos: (pos != player.primary_position, pos.value))
        ]
        return {
            "id": player.id,
            "name": player.full_name,
            "short_name": player.identity.last_name,
            "position": position.value,
            "primary_position": player.primary_position.value,
            "secondary_positions": [p.value for p in player.secondary_positions],
            "slot_id": slot_id,
            "role_id": role.role_id if role else None,
            "role": role.name if role else None,
            "ovr": _round(row.overall),
            "base_ovr": _round(player.overall_rating),
            "number": admin.numbers.get(player.id),
            "transfer_status": admin.transfer_statuses.get(player.id, "normal"),
            **player_market_view(session._world_squads, player, session.current_date),
            "contract": (f"{contract_view(session._world_squads, player.id, session.current_date)['weekly_wage']}/w · until "
                         f"{contract_view(session._world_squads, player.id, session.current_date)['expires_on']}"
                         if contract_view(session._world_squads, player.id, session.current_date) else None),
            "contract_details": contract_view(session._world_squads, player.id, session.current_date),
            "happiness": None,  # separate happiness metric does not exist; morale != happiness
            "familiarities": familiarities,
            "season_stats": player_statistics(session._world_squads, player.id, season=season, competition=competition),
            "act": _round(row.current),
            "role_fit": _round(row.role_fit),
            "familiarity": _round(row.assigned_familiarity),
            "role_familiarity": _round(player.tactical_familiarity.role_score(role.role_id)) if role else None,
            "condition": _round(player.state.condition),
            "fatigue": _round(player.state.fatigue),
            "morale": _round(player.state.effective_morale),
            "form": _round(player.state.form),
            "sharpness": _round(player.state.match_sharpness),
            "nationality": player.identity.nationality,
            "age": player.age_on(session.current_date),
            "birth_date": player.identity.birth_date.isoformat(),
            "foot": player.identity.dominant_foot.value,
            "injury": player.state.injury,
            "suspension": player.state.suspended_matches,
            "available": player.state.is_available,
            "attributes": {category: values for category, values in asdict(player.attributes).items() if values},
        }

    team_fields = []
    for group in GROUPS:
        instance = getattr(tactic.team_instructions, group)
        for field in fields(instance):
            value = getattr(instance, field.name)
            team_fields.append({
                "group": group, "field": field.name,
                "label": field.name.replace("_", " ").title(),
                "value": _display(value), "options": _options(value),
                "kind": "bool" if isinstance(value, bool) else (
                    "level" if isinstance(value.value, int) else "choice"
                ),
            })

    player_slots = []
    board_coordinates = base_points(lineup.formation)
    for entry in lineup.starters:
        slot_id = entry.slot_id
        role = tactic.role_for_slot(slot_id)
        assignment = tactic.role_assignments[slot_id]
        effective = tactic.effective_player_instructions(slot_id)
        individual = []
        for field in fields(effective):
            value = getattr(effective, field.name)
            override = getattr(assignment.overrides, field.name)
            individual.append({
                "field": field.name, "label": field.name.replace("_", " ").title(),
                "effective": _display(value),
                "override": _display(override) if override is not None else None,
                "options": _options(value),
                "kind": "target" if field.name in ("marking", "pressing_target") else (
                    "level" if isinstance(value.value, int) else "choice"
                ),
            })
        coords = board_coordinates.get(slot_id)
        player_slots.append({
            "slot_id": slot_id,
            "position": lineup.formation.slot(slot_id).position.value,
            "label": formation_slot_label(lineup.formation.formation_id, slot_id,
                                            lineup.formation.slot(slot_id).position.value),
            "base_x": _round(coords[0] * 100) if coords else None,
            "base_y": _round(coords[1] * 100) if coords else None,
            "player_id": entry.player.id,
            "role_id": role.role_id,
            "roles": [{"id": r.role_id, "name": r.name} for r in session.role_options_for_slot(slot_id)],
            "individual": individual,
        })

    starters = [player_payload(entry.player) for entry in lineup.starters]
    bench = [player_payload(player) for player in lineup.bench]
    outside = [player_payload(p) for p in session.home_club.squad.players if p.id not in selected_ids]
    roster = [player_payload(p) for p in session.home_club.squad.players]
    # Formation thumbnails use authoritative slot coordinates from the same
    # catalogue as the live board. Read-only UI metadata; no tactical mutation.
    layouts = formation_board_layouts()
    formation_previews = [
        {
            "id": formation.formation_id, "name": formation.name,
            "slots": [
                {
                    "slot_id": slot.slot_id,
                    "label": formation_slot_label(formation.formation_id, slot.slot_id, slot.position.value),
                    "x": _round(layouts[formation.formation_id][slot.slot_id][0] * 100),
                    "y": _round(layouts[formation.formation_id][slot.slot_id][1] * 100),
                }
                for slot in formation.slots
            ],
        }
        for formation in development_formations()
    ]
    # TS-UI-02.2: Expose the managed club's scheduled competitions for a short,
    # relevant season selector. This is read-only calendar data, never a new rule.
    stats_options = statistics_options(session._world_squads, session._world)
    club_competitions = sorted({fx.competition_id for fx in session._world.fixtures.values()
                                if session.home_club.id in (fx.home_club_id, fx.away_club_id)})
    if club_competitions:
        stats_options["club_competitions"] = {session._world_squads.season_label: club_competitions}
    return {
        "source": "python-development-session", "persistent": True,
        "club_id": session.home_club.id, "readonly": False,
        "statistics": stats_options,
        "stats_selection": {"season": season or session._world_squads.season_label, "competition": competition or "all"},
        "club": session.home_club.name, "date": session.current_date.isoformat(),
        "next_match": session.next_match_label,
        "formation": {"id": lineup.formation.formation_id, "name": lineup.formation.name},
        "formations": formation_previews,
        "slots": player_slots,
        "starters": starters, "bench": bench, "outside": outside,
        "roster": roster,
        "roster_capabilities": {
            "squad_numbers": "dev_only", "transfer_flags": "dev_only",
            "market_values": True, "contracts": True, "happiness": False,
            "training": False, "development_focus": True, "conversations": False, "season_player_ledger": True,
        },
        "season_stat_keys": list(SEASON_STAT_KEYS),
        "squad_status": {
            "morale": _round(state.xi_morale),
            "condition": _round(state.xi_condition),
            "chemistry": _round(state.xi_chemistry),
            "form": _round(mean(p.state.form for p in lineup.starting_players)),
            "tactical_familiarity": _round(state.xi_familiarity),
            "tired": state.condition_below_75,
        },
        "studio": studio_read_model(session),
        "tactics": {
            "preset": tactic.preset_origin.value,
            "presets": [{"id": preset.value, "name": preset.value.replace("_", " ").title()} for preset in session.tactical_presets],
            "style": tactical.style_label,
            "style_scores": {k: _round(getattr(tactical, k)) for k in ("possession", "pressing", "directness", "defensive_depth", "tempo", "width", "risk")},
            "fields": team_fields,
        },
        "targets": {
            "positions": [pos.value for pos in Position],
            "players": [{"id": p.id, "name": p.full_name} for p in session.away_club.squad.players],
            "roles": sorted({r.role_id for s in player_slots for r in session.role_options_for_slot(s["slot_id"])})
        },
        "set_pieces": set_piece_view(session),
        "match_preparation": opponent_report(session),
    }


def _parse_target(raw: str) -> TacticalTarget | None:
    if not raw:
        return None
    kind, separator, target_id = raw.partition(":")
    if not separator or not target_id:
        raise ValueError("target must use kind:id")
    if kind not in {member.value for member in TargetKind}:
        raise ValueError("invalid target kind")
    return TacticalTarget(TargetKind(kind), target_id)


def _parse_player_value(current, raw: str):
    if isinstance(current, Enum):
        for option in type(current):
            if _display(option) == raw:
                return option
        raise ValueError(f"invalid player-instruction option: {raw}")
    if current is None or isinstance(current, TacticalTarget):
        return _parse_target(raw)
    raise ValueError("unsupported player-instruction type")


def apply_squad_command(session: DevelopmentSession, command: dict, admin: UIRosterAdmin | None = None) -> dict:
    """Validated commands. Deliberately never simulates or saves a world."""
    if not isinstance(command, dict):
        raise ValueError("request must be a JSON object")
    action = command.get("action")
    if action in STUDIO_ACTIONS:
        apply_studio_command(session, command)
    elif action == "set_piece":
        assign_order(session, command)
    elif action == "formation":
        session.set_formation(str(command.get("id", "")))
    elif action == "preset":
        session.set_tactical_preset(str(command.get("id", "")))
    elif action == "team_instruction":
        session.set_team_instruction(
            str(command.get("group", "")), str(command.get("field", "")), str(command.get("value", ""))
        )
    elif action == "role":
        session.set_role(str(command.get("slot_id", "")), str(command.get("role_id", "")))
    elif action == "swap_starters":
        session.swap_starting_slots(str(command.get("first", "")), str(command.get("second", "")))
    elif action == "swap_bench":
        session.swap_lineup(str(command.get("starter_id", "")), str(command.get("bench_id", "")))
    elif action == "swap_reserve":
        session.swap_with_reserve(str(command.get("player_id", "")), str(command.get("reserve_id", "")))
    elif action == "swap_bench_slots":
        session.swap_bench_slots(str(command.get("first_id", "")), str(command.get("second_id", "")))
    elif action in ("squad_number", "transfer_status"):
        if admin is None:
            raise ValueError("UI administration state is unavailable")
        player_id = command.get("player_id")
        if not isinstance(player_id, str) or not session.home_club.squad.contains(player_id):
            raise ValueError("unknown roster player")
        if action == "squad_number":
            number = command.get("number")
            if number is None:
                admin.numbers.pop(player_id, None)
            else:
                if isinstance(number, bool) or not isinstance(number, int) or not 1 <= number <= 99:
                    raise ValueError("shirt number must be 1..99 or null")
                if any(pid != player_id and n == number and session.home_club.squad.contains(pid) for pid, n in admin.numbers.items()):
                    raise ValueError("shirt number is already allocated")
                admin.numbers[player_id] = number
        else:
            status = command.get("status")
            if status not in TRANSFER_STATUSES:
                raise ValueError("unknown transfer availability")
            if status == "normal":
                admin.transfer_statuses.pop(player_id, None)
            else:
                admin.transfer_statuses[player_id] = status
            # Mirror disposition inside the world runner, where AI buyers run
            # without access to UI-only administration state.
            session._world_squads.manager_sale_posture[player_id] = status
    elif action in ("player_instruction", "reset_player_instructions"):
        slot_id = str(command.get("slot_id", ""))
        assignment = session.home_tactic.role_assignments.get(slot_id)
        if assignment is None:
            raise ValueError("unknown formation slot")
        if action == "reset_player_instructions":
            overrides = PlayerInstructionOverrides()
        else:
            field_name = str(command.get("field", ""))
            if field_name not in {f.name for f in fields(PlayerInstructionOverrides)}:
                raise ValueError("unknown player instruction")
            effective = session.home_tactic.effective_player_instructions(slot_id)
            current = getattr(effective, field_name)
            raw = command.get("value")
            if raw is None or raw == "default":
                parsed = None  # inherit the role's instruction
            else:
                if not isinstance(raw, str):
                    raise ValueError("instruction value must be a string")
                parsed = _parse_player_value(current, raw)
                if isinstance(parsed, TacticalTarget):
                    if parsed.kind is TargetKind.PLAYER and parsed.target_id not in {p.id for p in session.away_club.squad.players}:
                        raise ValueError("unknown opponent player target")
                    if parsed.kind is TargetKind.ROLE and parsed.target_id not in squad_read_model(session, admin)["targets"]["roles"]:
                        raise ValueError("unknown role target")
            overrides = replace(assignment.overrides, **{field_name: parsed})
        session.home_tactic.set_player_overrides(slot_id, overrides)
        session.home_tactic.preset_origin = TacticalPreset.CUSTOM
    else:
        raise ValueError("unsupported command")
    session.tactical_studio.revision += 1
    return squad_read_model(session, admin)
