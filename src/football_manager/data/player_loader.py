from __future__ import annotations

import json
from datetime import date
from pathlib import Path
from typing import Any

from football_manager.domain.attributes import (
    GoalkeepingAttributes,
    MentalAttributes,
    PhysicalAttributes,
    PlayerAttributes,
    TechnicalAttributes,
)
from football_manager.domain.enums import Foot, Position
from football_manager.domain.player import Player, PlayerIdentity
from football_manager.domain.player_state import PlayerState
from football_manager.domain.personality import Personality
from football_manager.domain.positional_familiarity import PositionalFamiliarity


def load_player(payload: dict[str, Any]) -> Player:
    identity_data = payload["identity"]
    attributes_data = payload["attributes"]

    identity = PlayerIdentity(
        player_id=str(identity_data["id"]),
        first_name=identity_data["first_name"],
        last_name=identity_data["last_name"],
        birth_date=date.fromisoformat(identity_data["birth_date"]),
        nationality=identity_data["nationality"],
        dominant_foot=Foot(identity_data["dominant_foot"]),
    )

    goalkeeping_data = attributes_data.get("goalkeeping")
    attributes = PlayerAttributes(
        technical=TechnicalAttributes(**attributes_data["technical"]),
        mental=MentalAttributes(**attributes_data["mental"]),
        physical=PhysicalAttributes(**attributes_data["physical"]),
        goalkeeping=(
            GoalkeepingAttributes(**goalkeeping_data)
            if goalkeeping_data is not None
            else None
        ),
    )

    positional_familiarity = PositionalFamiliarity(
        {Position(position): value for position, value in payload["positions"].items()}
    )

    state = PlayerState(**payload.get("state", {}))

    player = Player(
        identity=identity,
        attributes=attributes,
        positional_familiarity=positional_familiarity,
        original_position=Position(payload["original_position"]),
        primary_position=Position(payload["primary_position"]),
        state=state,
        personality=(Personality(**payload["personality"]) if "personality" in payload else None),
    )
    if "development" in payload:
        from football_manager.domain.player_development import initialize_development
        config = payload["development"]
        allowed = {"as_of", "seed", "potential", "growth_peak_age", "growth_end_age", "growth_rate"}
        if not isinstance(config, dict) or set(config) - allowed or "as_of" not in config:
            raise ValueError("development import requires as_of and known profile fields")
        initialize_development(player, date.fromisoformat(config["as_of"]), config.get("seed", 0),
            source="imported-profile-v1", **{k: v for k, v in config.items() if k not in {"as_of", "seed"}})
    if "aging" in payload:
        from football_manager.domain.player_aging import initialize_aging
        config = payload["aging"]
        allowed = {"as_of", "seed", "physical_decline_age", "technical_decline_age", "mental_decline_age", "decline_rate", "retirement_age"}
        if not isinstance(config, dict) or set(config) - allowed or "as_of" not in config:
            raise ValueError("ageing import requires as_of and known profile fields")
        initialize_aging(player, date.fromisoformat(config["as_of"]), config.get("seed", 0),
                         **{k: v for k, v in config.items() if k not in {"as_of", "seed"}})
    return player


def load_players(path: str | Path) -> list[Player]:
    file_path = Path(path)
    with file_path.open("r", encoding="utf-8") as handle:
        payload = json.load(handle)

    if not isinstance(payload, list):
        raise ValueError("Players JSON must contain a list")

    players = [load_player(item) for item in payload]
    ids = [player.id for player in players]
    if len(ids) != len(set(ids)):
        raise ValueError("Player IDs must be unique")
    return players
