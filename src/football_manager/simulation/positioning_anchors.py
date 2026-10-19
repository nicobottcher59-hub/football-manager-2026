from __future__ import annotations

from football_manager.domain import Position


# Home-perspective normalized anchors used as neutral formation references.
# Tactical Positioning (Phase 5.1) transforms these anchors according to
# possession phase, team instructions and individual role instructions.
BASE_NORMALIZED: dict[Position, tuple[float, float]] = {
    Position.GK: (0.055, 0.50),
    Position.RB: (0.22, 0.82),
    Position.RCB: (0.18, 0.64),
    Position.CB: (0.18, 0.50),
    Position.LCB: (0.18, 0.36),
    Position.LB: (0.22, 0.18),
    Position.RWB: (0.31, 0.84),
    Position.LWB: (0.31, 0.16),
    Position.DM: (0.34, 0.50),
    Position.RCM: (0.41, 0.66),
    Position.CM: (0.41, 0.50),
    Position.LCM: (0.41, 0.34),
    Position.AM: (0.46, 0.50),
    Position.RW: (0.48, 0.84),
    Position.LW: (0.48, 0.16),
    Position.SS: (0.485, 0.50),
    Position.ST: (0.49, 0.50),
}


def normalized_anchor(position: Position) -> tuple[float, float]:
    try:
        return BASE_NORMALIZED[position]
    except KeyError as exc:
        raise KeyError(f"no spatial anchor configured for position {position.value!r}") from exc
