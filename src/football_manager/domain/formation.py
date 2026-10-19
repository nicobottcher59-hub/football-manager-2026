from __future__ import annotations

from dataclasses import dataclass

from .enums import Position


@dataclass(frozen=True, slots=True)
class FormationSlot:
    """One named place in a formation.

    slot_id is intentionally independent from Position so a formation can contain
    repeated positions, such as two centre-backs or two strikers.
    """

    slot_id: str
    position: Position

    def __post_init__(self) -> None:
        if not self.slot_id.strip():
            raise ValueError("slot_id cannot be empty")


@dataclass(frozen=True, slots=True)
class Formation:
    formation_id: str
    name: str
    slots: tuple[FormationSlot, ...]

    def __post_init__(self) -> None:
        if not self.formation_id.strip():
            raise ValueError("formation_id cannot be empty")
        if not self.name.strip():
            raise ValueError("formation name cannot be empty")
        if len(self.slots) != 11:
            raise ValueError("a formation must contain exactly 11 slots")

        slot_ids = [slot.slot_id for slot in self.slots]
        if len(set(slot_ids)) != len(slot_ids):
            raise ValueError("formation slot IDs must be unique")

        goalkeeper_slots = sum(slot.position is Position.GK for slot in self.slots)
        if goalkeeper_slots != 1:
            raise ValueError("a formation must contain exactly one goalkeeper slot")

    def slot(self, slot_id: str) -> FormationSlot:
        for slot in self.slots:
            if slot.slot_id == slot_id:
                return slot
        raise KeyError(f"formation slot {slot_id!r} does not exist")

    @property
    def slot_ids(self) -> frozenset[str]:
        return frozenset(slot.slot_id for slot in self.slots)
