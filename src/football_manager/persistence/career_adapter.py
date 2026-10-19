"""Results-only WorldCareer adapter for the opt-in SQLite repository.

This intentionally does not attempt to save a DevelopmentSession, lineups,
players, tactics, finances, buildings or a current UI date. TS-15 will define
that separate versioned manager-state contract before exposing Load/Save in UI.
"""
from __future__ import annotations

from typing import Mapping

from football_manager.domain.career import WorldCareer
from football_manager.domain.career_transition import CareerSeasonTransition

from .models import EntityKey, EntityLink, SaveDocument, SaveIntegrityError, SaveSection
from .sqlite_repository import SQLiteSaveRepository


def world_career_document(career: WorldCareer) -> SaveDocument:
    """Index stable club/season identities without denormalizing match results."""
    career.validate_integrity()
    clubs = set(career.club_names)
    links: set[EntityLink] = set()
    seasons: set[str] = set()
    for world in career.worlds:
        seasons.add(world.season_label)
        participants = set(world.strengths)
        for fixture in world.fixtures.values():
            participants.update((fixture.home_club_id, fixture.away_club_id))
        clubs.update(participants)
        season_key = EntityKey("season", world.season_label)
        for club_id in participants:
            links.add(EntityLink(EntityKey("club", club_id), "participates_in", season_key))
    entities = tuple([*(EntityKey("club", club_id) for club_id in sorted(clubs)),
                      *(EntityKey("season", label) for label in sorted(seasons))])
    return SaveDocument(
        kind="world_results",
        sections=(SaveSection("world_results", 1, career.to_dict()),),
        entities=entities,
        links=tuple(sorted(links, key=lambda x: (
            x.source.kind, x.source.entity_id, x.relation, x.target.entity_id))),
    )


def save_world_results(repository: SQLiteSaveRepository, *, slot_id: str,
                       display_name: str, career: WorldCareer,
                       expected_revision: int):
    """Store a validated world results timeline, not a complete manager career."""
    return repository.save(slot_id, display_name, world_career_document(career),
                           expected_revision=expected_revision)


def load_world_results(repository: SQLiteSaveRepository, slot_id: str, *,
                       transitions: Mapping[str, CareerSeasonTransition] | None = None):
    """Reconstruct and validate results; never change the active game session."""
    stored = repository.load(slot_id)
    document = stored.document
    if document.kind != "world_results" or len(document.sections) != 1:
        raise SaveIntegrityError("slot is not a results-only WorldCareer archive")
    section = document.sections[0]
    if section.name != "world_results" or section.version != 1:
        raise SaveIntegrityError("unsupported results-only career section")
    try:
        career = WorldCareer.from_dict(section.payload, transitions=transitions)
        career.validate_integrity()
    except (ValueError, TypeError, KeyError, IndexError) as exc:
        raise SaveIntegrityError("saved WorldCareer failed domain validation") from exc
    # Rebuild the entity catalog from the canonical world and compare it with
    # the relational index. A corrupted index must not be treated as truth.
    expected = world_career_document(career)
    if set(document.entities) != set(expected.entities) or set(document.links) != set(expected.links):
        raise SaveIntegrityError("save entity index does not match WorldCareer")
    return stored.metadata, career
