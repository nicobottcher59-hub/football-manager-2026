"""Versioned persistence contracts, independent of UI and game simulation.

TS-14 deliberately models result-only archives. A full manager career is NOT
serializable yet and must receive an explicit contract in a later version.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Mapping

DOCUMENT_VERSION = 1


class SaveConflictError(RuntimeError):
    """A caller attempted to overwrite a slot based on an obsolete revision."""


class SaveIntegrityError(ValueError):
    """Persisted bytes or relational metadata failed a consistency check."""


class UnsupportedSaveVersionError(ValueError):
    """The on-disk schema or document is newer or otherwise unsupported."""


def _text(value: str, field: str) -> None:
    if not isinstance(value, str) or not value or value != value.strip():
        raise ValueError(f"{field} must be a nonempty unpadded string")
    if len(value) > 256 or any(ord(char) < 32 for char in value):
        raise ValueError(f"{field} contains invalid characters or is too long")


def _positive_version(value: int, field: str) -> None:
    if type(value) is not int or value < 1:
        raise ValueError(f"{field} must be a positive integer")


@dataclass(frozen=True, slots=True)
class EntityKey:
    """Stable identity, with scope for engines where IDs repeat across clubs.

    An identity is NOT derived from a player's name, a fixture date or a row
    position. The three fields form one compound key.
    """

    kind: str
    entity_id: str
    scope: str = "global"

    def __post_init__(self) -> None:
        for field in ("kind", "entity_id", "scope"):
            _text(getattr(self, field), field)


@dataclass(frozen=True, slots=True)
class EntityLink:
    source: EntityKey
    relation: str
    target: EntityKey

    def __post_init__(self) -> None:
        if not isinstance(self.source, EntityKey) or not isinstance(self.target, EntityKey):
            raise ValueError("entity links require EntityKey endpoints")
        _text(self.relation, "relation")


@dataclass(frozen=True, slots=True)
class SaveSection:
    """A separately versioned JSON document owned by one game subsystem."""

    name: str
    version: int
    payload: Mapping[str, Any]

    def __post_init__(self) -> None:
        _text(self.name, "section name")
        _positive_version(self.version, "section version")
        if not isinstance(self.payload, Mapping):
            raise ValueError("section payload must be a JSON object")


@dataclass(frozen=True, slots=True)
class SaveDocument:
    """One consistent snapshot; all sections and references commit together."""

    kind: str
    sections: tuple[SaveSection, ...]
    entities: tuple[EntityKey, ...] = ()
    links: tuple[EntityLink, ...] = ()
    version: int = DOCUMENT_VERSION

    def __post_init__(self) -> None:
        _text(self.kind, "save kind")
        _positive_version(self.version, "document version")
        if self.version != DOCUMENT_VERSION:
            raise UnsupportedSaveVersionError("unsupported save document version")
        if not self.sections or any(not isinstance(part, SaveSection) for part in self.sections):
            raise ValueError("save requires at least one versioned section")
        if len({part.name for part in self.sections}) != len(self.sections):
            raise ValueError("duplicate save section")
        if any(not isinstance(entity, EntityKey) for entity in self.entities):
            raise ValueError("invalid save entity")
        if len(set(self.entities)) != len(self.entities):
            raise ValueError("duplicate entity identity in save")
        if any(not isinstance(link, EntityLink) for link in self.links):
            raise ValueError("invalid save relationship")
        if len(set(self.links)) != len(self.links):
            raise ValueError("duplicate entity relationship in save")
        catalog = set(self.entities)
        if any(link.source not in catalog or link.target not in catalog for link in self.links):
            raise ValueError("save relationship references an unknown entity")


@dataclass(frozen=True, slots=True)
class SaveMetadata:
    slot_id: str
    display_name: str
    revision: int
    kind: str
    created_at_utc: str
    updated_at_utc: str


@dataclass(frozen=True, slots=True)
class StoredSave:
    metadata: SaveMetadata
    document: SaveDocument
