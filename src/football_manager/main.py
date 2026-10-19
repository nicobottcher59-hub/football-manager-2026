from __future__ import annotations

from pathlib import Path

from football_manager.data import load_players


def main() -> None:
    project_root = Path(__file__).resolve().parents[2]
    sample_path = project_root / "data" / "sample" / "players.json"
    players = load_players(sample_path)

    print("Football Manager Game — domain prototype v0.0.1")
    print(f"Loaded {len(players)} sample players\n")

    for player in players:
        print(
            f"- {player.full_name} | {player.primary_position.value} | "
            f"familiarity {player.familiarity_for(player.primary_position):.0f} | "
            f"fitness {player.state.fitness:.0f} | form {player.state.form:.0f}"
        )


if __name__ == "__main__":
    main()
