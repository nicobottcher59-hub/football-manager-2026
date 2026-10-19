from pathlib import Path

from football_manager.data import load_players
from football_manager.domain.enums import Position


def test_sample_players_can_be_loaded() -> None:
    path = Path(__file__).resolve().parents[1] / "data" / "sample" / "players.json"
    players = load_players(path)
    assert len(players) == 3
    assert players[0].primary_position is Position.ST
    assert players[1].familiarity_for(Position.ST) == 41


def test_sample_goalkeeper_loads_goalkeeping_attributes() -> None:
    path = Path(__file__).resolve().parents[1] / "data" / "sample" / "players.json"
    players = load_players(path)
    goalkeeper = players[2]
    assert goalkeeper.primary_position is Position.GK
    assert goalkeeper.attributes.goalkeeping is not None
    assert goalkeeper.attributes.goalkeeping.reflexes == 86
