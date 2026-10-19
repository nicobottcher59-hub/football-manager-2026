from __future__ import annotations

from .spatial_state import MatchState, TeamSide


def render_team_tactical_ascii(
    state: MatchState,
    side: TeamSide,
    *,
    use_targets: bool = True,
    columns: int = 72,
    rows: int = 24,
) -> str:
    """Render a deliberately crude terminal pitch for spatial debugging.

    This is not a user-facing match viewer. It exists so engine development can
    visually inspect tactical shapes before the real frontend is built.
    """

    if columns < 30 or rows < 12:
        raise ValueError("debug pitch is too small")

    side = TeamSide(side)
    inner_columns = columns - 2
    inner_rows = rows - 2
    grid = [[" " for _ in range(inner_columns)] for _ in range(inner_rows)]

    # Halfway line and centre spot are useful orientation references.
    halfway = round((state.pitch.length_m / 2.0) / state.pitch.length_m * (inner_columns - 1))
    for row in range(inner_rows):
        grid[row][halfway] = "│"
    centre_row = inner_rows // 2
    grid[centre_row][halfway] = "┼"

    for agent in state.active_players:
        if agent.side is not side:
            continue
        location = agent.tactical_target if use_targets and agent.tactical_target else agent.location
        col = round(location.x / state.pitch.length_m * (inner_columns - 1))
        row = round(location.y / state.pitch.width_m * (inner_rows - 1))
        row = min(max(row, 0), inner_rows - 1)
        col = min(max(col, 0), inner_columns - 1)
        label = agent.slot_id.upper()[:3]
        start = min(max(col - len(label) // 2, 0), inner_columns - len(label))
        for index, char in enumerate(label):
            grid[row][start + index] = char

    top = "┌" + "─" * inner_columns + "┐"
    bottom = "└" + "─" * inner_columns + "┘"
    body = ["│" + "".join(row) + "│" for row in grid]
    phase = next(
        (
            agent.tactical_phase.value
            for agent in state.active_players
            if agent.side is side and agent.tactical_phase is not None
        ),
        "unknown",
    )
    direction = "+X →" if side is TeamSide.HOME else "← -X"
    header = f"{side.value.upper()} | {phase} | attack {direction}"
    return "\n".join((header, top, *body, bottom))
