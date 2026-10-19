"""Development formation catalogue and shared frontend pitch coordinates.

This module adds *shapes*, not tactical modifiers. Slot positions deliberately
use the existing Position enum and role/familiarity rules. In particular, the
existing engine represents wide midfielders with RW/LW slots shown deeper on
the diagram: no new player positions or rating formula are introduced here.
"""
from __future__ import annotations

from functools import lru_cache

from football_manager.domain.enums import Position as P
from football_manager.domain.formation import Formation, FormationSlot

# Normalized coordinates: x is left-to-right flank across a pitch; y runs from
# the opposition goal (0) to our goalkeeper (1). A slot ID represents a *place*
# and is not a player ID.
Slot = tuple[str, P, float, float]

GK: tuple[Slot, ...] = (("gk", P.GK, .50, .90),)
BACK4: tuple[Slot, ...] = (
    ("rb", P.RB, .85, .72), ("rcb", P.RCB, .62, .72),
    ("lcb", P.LCB, .38, .72), ("lb", P.LB, .15, .72),
)
BACK3: tuple[Slot, ...] = (
    ("rcb", P.RCB, .70, .72), ("cb", P.CB, .50, .75),
    ("lcb", P.LCB, .30, .72),
)
WINGBACKS: tuple[Slot, ...] = (("rwb", P.RWB, .86, .50), ("lwb", P.LWB, .14, .50))
WINGBACKS_DEEP: tuple[Slot, ...] = (("rwb", P.RWB, .86, .61), ("lwb", P.LWB, .14, .61))
FULLBACKS_FIVE: tuple[Slot, ...] = (("rb", P.RB, .86, .72), ("lb", P.LB, .14, .72))
ONE_DM: tuple[Slot, ...] = (("dm", P.DM, .50, .56),)
TWO_DM: tuple[Slot, ...] = (("rdm", P.DM, .62, .55), ("ldm", P.DM, .38, .55))
TWO_CM: tuple[Slot, ...] = (("rcm", P.RCM, .62, .45), ("lcm", P.LCM, .38, .45))
THREE_CM: tuple[Slot, ...] = (
    ("rcm", P.RCM, .65, .45), ("cm", P.CM, .50, .48), ("lcm", P.LCM, .35, .45),
)
ONE_CM: tuple[Slot, ...] = (("cm", P.CM, .50, .47),)
WIDE_MID: tuple[Slot, ...] = (("rm", P.RW, .84, .46), ("lm", P.LW, .16, .46))
WIDE_HIGH: tuple[Slot, ...] = (("rw", P.RW, .83, .27), ("lw", P.LW, .17, .27))
ONE_AM: tuple[Slot, ...] = (("am", P.AM, .50, .31),)
TWO_AM: tuple[Slot, ...] = (("ram", P.AM, .63, .31), ("lam", P.AM, .37, .31))
ONE_ST: tuple[Slot, ...] = (("st", P.ST, .50, .13),)
TWO_ST: tuple[Slot, ...] = (("rst", P.ST, .62, .16), ("lst", P.ST, .38, .16))

# The first four IDs, names, slot order and shapes are intentionally preserved.
# Any saved career referencing them continues to deserialize unchanged.
_CATALOGUE: tuple[tuple[str, str, tuple[Slot, ...]], ...] = (
    ("dev-4-3-3", "4-3-3 DM Wide", GK + BACK4 + ONE_DM +
     (("rcm", P.RCM, .66, .42), ("lcm", P.LCM, .34, .42),
      ("rw", P.RW, .82, .20), ("st", P.ST, .50, .14), ("lw", P.LW, .18, .20))),
    ("dev-4-2-3-1", "4-2-3-1 Wide", GK + BACK4 +
     (("rdm", P.DM, .62, .55), ("ldm", P.DM, .38, .55),
      ("rw", P.RW, .82, .34), ("am", P.AM, .50, .33),
      ("lw", P.LW, .18, .34), ("st", P.ST, .50, .13))),
    ("dev-4-4-2", "4-4-2", GK + BACK4 +
     (("rw", P.RW, .84, .45), ("rcm", P.RCM, .62, .45),
      ("lcm", P.LCM, .38, .45), ("lw", P.LW, .16, .45),
      ("rst", P.ST, .62, .18), ("lst", P.ST, .38, .18))),
    ("dev-3-4-2-1", "3-4-2-1", GK + BACK3 +
     (("rwb", P.RWB, .86, .50), ("rcm", P.RCM, .62, .50),
      ("lcm", P.LCM, .38, .50), ("lwb", P.LWB, .14, .50),
      ("ram", P.AM, .62, .30), ("lam", P.AM, .38, .30),
      ("st", P.ST, .50, .12))),

    # Additional four-defender setups, kept distinct by their actual slot roles.
    ("dev-4-1-4-1", "4-1-4-1", GK + BACK4 + ONE_DM + WIDE_MID + TWO_CM + ONE_ST),
    ("dev-4-3-1-2", "4-3-1-2 (3 CM)", GK + BACK4 + THREE_CM + ONE_AM + TWO_ST),
    ("dev-4-4-2-diamond", "4-4-2 Diamond", GK + BACK4 + ONE_DM + TWO_CM + ONE_AM + TWO_ST),
    ("dev-4-2-2-2", "4-2-2-2", GK + BACK4 + TWO_DM + TWO_AM + TWO_ST),
    ("dev-4-2-3-1-narrow", "4-2-3-1 Narrow", GK + BACK4 + TWO_DM +
     (("ram", P.AM, .67, .32), ("am", P.AM, .50, .29),
      ("lam", P.AM, .33, .32)) + ONE_ST),
    ("dev-4-3-2-1", "4-3-2-1 Christmas Tree", GK + BACK4 + THREE_CM + TWO_AM + ONE_ST),
    ("dev-4-4-1-1", "4-4-1-1", GK + BACK4 + WIDE_MID + TWO_CM +
     (("ss", P.SS, .50, .31),) + ONE_ST),
    ("dev-4-2-4", "4-2-4", GK + BACK4 + TWO_CM +
     (("rw", P.RW, .84, .29), ("lw", P.LW, .16, .29)) + TWO_ST),
    ("dev-4-5-1", "4-5-1 Flat", GK + BACK4 + WIDE_MID + THREE_CM + ONE_ST),
    ("dev-4-1-3-2", "4-1-3-2", GK + BACK4 + ONE_DM + WIDE_MID + ONE_CM + TWO_ST),

    # Three-defender variants: wingbacks remain distinct from centre-backs.
    ("dev-3-5-2", "3-5-2", GK + BACK3 + WINGBACKS + THREE_CM + TWO_ST),
    ("dev-3-4-3", "3-4-3", GK + BACK3 + WINGBACKS + TWO_CM + WIDE_HIGH + ONE_ST),
    ("dev-3-4-1-2", "3-4-1-2 (2 CM)", GK + BACK3 + WINGBACKS + TWO_CM + ONE_AM + TWO_ST),
    ("dev-3-1-4-2", "3-1-4-2", GK + BACK3 + ONE_DM + WINGBACKS + TWO_CM + TWO_ST),
    ("dev-3-4-1-2-dm", "3-4-1-2 (2 DM)", GK + BACK3 + WINGBACKS + TWO_DM + ONE_AM + TWO_ST),

    # Five-back variants; deeper wingbacks visually distinguish a back five.
    ("dev-5-3-2", "5-3-2", GK + BACK3 + FULLBACKS_FIVE + THREE_CM + TWO_ST),
    ("dev-5-2-3", "5-2-3", GK + BACK3 + FULLBACKS_FIVE + TWO_CM + WIDE_HIGH + ONE_ST),
    ("dev-5-4-1", "5-4-1", GK + BACK3 + FULLBACKS_FIVE + WIDE_MID +
     (("dm", P.DM, .60, .52), ("cm", P.CM, .40, .45)) + ONE_ST),
    ("dev-5-2-1-2", "5-2-1-2", GK + BACK3 + FULLBACKS_FIVE + TWO_CM + ONE_AM + TWO_ST),
    ("dev-5-3-1-1", "5-3-1-1", GK + BACK3 + WINGBACKS_DEEP + THREE_CM +
     (("ss", P.SS, .50, .30),) + ONE_ST),

    # Specifically requested: two DMs, deep wide midfield, two central AMs.
    ("dev-4-3-3-double-dm", "4-3-3 (2 DM + 1 CM)", GK + BACK4 + TWO_DM + ONE_CM + WIDE_HIGH + ONE_ST),
    ("dev-4-4-2-double-dm", "4-4-2 (2 DM)", GK + BACK4 + TWO_DM + WIDE_MID + TWO_ST),
    ("dev-4-5-1-am-duo", "4-5-1 (2 AM + LM/RM)", GK + BACK4 + ONE_CM + TWO_AM + WIDE_MID + ONE_ST),
    ("dev-5-2-2-1", "5-2-2-1 (2 Central AM)", GK + BACK3 + FULLBACKS_FIVE + TWO_CM + TWO_AM + ONE_ST),
)


@lru_cache(maxsize=1)
def development_formations() -> tuple[Formation, ...]:
    formations = tuple(
        Formation(formation_id=formation_id, name=name,
                  slots=tuple(FormationSlot(slot_id, position) for slot_id, position, _, _ in slots))
        for formation_id, name, slots in _CATALOGUE
    )
    if len({item.formation_id for item in formations}) != len(formations):
        raise ValueError('duplicate formation ID')
    if len({item.name for item in formations}) != len(formations):
        raise ValueError('duplicate formation name')
    for formation, (_, _, slots) in zip(formations, _CATALOGUE, strict=True):
        if not all(0.0 <= x <= 1.0 and 0.0 <= y <= 1.0 for _, _, x, y in slots):
            raise ValueError(f'formation coordinates outside field: {formation.formation_id}')
    return formations


@lru_cache(maxsize=1)
def formation_board_layouts() -> dict[str, dict[str, tuple[float, float]]]:
    """Positions shared by Tkinter and the live portable frontend."""
    return {
        formation_id: {slot_id: (x, y) for slot_id, _, x, y in slots}
        for formation_id, _, slots in _CATALOGUE
    }


def formation_slot_label(formation_id: str, slot_id: str, fallback: str) -> str:
    """UI label only: the existing RW/LW engine positions serve wide midfield."""
    if slot_id == 'rm':
        return 'RM'
    if slot_id == 'lm':
        return 'LM'
    return fallback
