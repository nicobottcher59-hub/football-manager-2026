"""TS-14: SQLite persistence boundaries, atomicity, identities and legacy archives."""
from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from dataclasses import replace
import json
import sqlite3

import pytest

from football_manager.domain.career import WorldCareer
from football_manager.domain.world_runner import WorldMatchResult
from football_manager.persistence import (
    DB_SCHEMA_VERSION, EntityKey, EntityLink, SaveConflictError, SaveDocument,
    SaveIntegrityError, SaveSection, SQLiteSaveRepository,
    UnsupportedSaveVersionError, load_world_results, save_world_results,
    world_career_document,
)
from tools.stress_world_calendar import create_world


def _document(number=1):
    club = EntityKey("club", "club-123")
    player_a = EntityKey("player", "player-1", "club-123")
    player_b = EntityKey("player", "player-1", "club-456")
    return SaveDocument(
        "world_results", (SaveSection("world_results", 1, {"number": number, "label": "Cañuelas"}),),
        entities=(club, player_a, player_b),
        links=(EntityLink(player_a, "belongs_to", club),),
    )


def _repo(tmp_path):
    return SQLiteSaveRepository(tmp_path / "test-saves.sqlite3")


def test_sqlite_schema_is_versioned_with_foreign_keys(tmp_path):
    repo = _repo(tmp_path)
    assert repo.list_slots() == ()
    with sqlite3.connect(repo.path) as connection:
        assert connection.execute("PRAGMA user_version").fetchone()[0] == DB_SCHEMA_VERSION
        links_fks = connection.execute("PRAGMA foreign_key_list(save_links)").fetchall()
        assert len(links_fks) == 8  # two composite 4-column FKs
        tables = {row[0] for row in connection.execute(
            "SELECT name FROM sqlite_master WHERE type='table'")}
        assert {"save_slots", "save_sections", "save_entities", "save_links"} <= tables


def test_roundtrip_utf8_sections_and_scoped_identity(tmp_path):
    repo = _repo(tmp_path)
    meta = repo.save("my-career", "Temporada Ñ", _document(), expected_revision=0)
    assert meta.revision == 1
    stored = repo.load("my-career")
    assert stored.metadata == meta
    assert stored.document == _document()
    assert len(repo.list_slots()) == 1
    assert {entry.scope for entry in stored.document.entities if entry.kind == "player"} == {
        "club-123", "club-456"
    }


def test_update_revision_replaces_all_children_and_preserves_created_time(tmp_path):
    repo = _repo(tmp_path)
    first = repo.save("a", "Primera", _document(1), expected_revision=0)
    updated = SaveDocument("world_results", (SaveSection("world_results", 1, {"number": 2}),))
    second = repo.save("a", "Segunda", updated, expected_revision=first.revision)
    assert second.revision == 2
    assert second.created_at_utc == first.created_at_utc
    assert second.display_name == "Segunda"
    stored = repo.load("a")
    assert stored.document == updated
    assert stored.document.entities == ()
    assert stored.document.links == ()


def test_multiple_slots_are_isolated_and_delete_cascades(tmp_path):
    repo = _repo(tmp_path)
    repo.save("a", "Uno", _document(1), expected_revision=0)
    repo.save("b", "Dos", _document(2), expected_revision=0)
    assert {row.slot_id for row in repo.list_slots()} == {"a", "b"}
    repo.delete("a", expected_revision=1)
    with pytest.raises(KeyError):
        repo.load("a")
    assert repo.load("b").document.sections[0].payload["number"] == 2
    with sqlite3.connect(repo.path) as connection:
        for table in ("save_sections", "save_entities", "save_links"):
            assert connection.execute(f"SELECT COUNT(*) FROM {table} WHERE slot_id='a'").fetchone()[0] == 0


def test_stale_revisions_cannot_overwrite_or_delete(tmp_path):
    repo = _repo(tmp_path)
    first = repo.save("a", "Uno", _document(), expected_revision=0)
    repo.save("a", "Dos", _document(2), expected_revision=first.revision)
    for revision in (0, 1):
        with pytest.raises(SaveConflictError, match="revision"):
            repo.save("a", "Stale", _document(8), expected_revision=revision)
    with pytest.raises(SaveConflictError):
        repo.delete("a", expected_revision=1)
    assert repo.load("a").metadata.revision == 2
    assert repo.load("a").document.sections[0].payload["number"] == 2


def test_two_simultaneous_writers_cannot_both_replace_the_same_revision(tmp_path):
    repo = _repo(tmp_path)
    repo.save("a", "Primera", _document(), expected_revision=0)

    def update(number):
        try:
            return repo.save("a", "Versión", _document(number), expected_revision=1)
        except SaveConflictError:
            return None

    with ThreadPoolExecutor(max_workers=2) as pool:
        answers = list(pool.map(update, (2, 3)))
    assert sum(result is not None for result in answers) == 1
    assert repo.load("a").metadata.revision == 2


@pytest.mark.parametrize("bad", [float("nan"), float("inf"), {1: "numeric-key"}, {"unserializable": {1, 2}}])
def test_bad_payload_cannot_damage_existing_slot(tmp_path, bad):
    repo = _repo(tmp_path)
    repo.save("a", "Original", _document(), expected_revision=0)
    document = SaveDocument("world_results", (SaveSection("world_results", 1, {"bad": bad}),))
    with pytest.raises(ValueError):
        repo.save("a", "Broken", document, expected_revision=1)
    assert repo.load("a").document == _document()
    assert repo.load("a").metadata.revision == 1


def test_unknown_links_and_duplicate_ids_are_rejected_before_writing(tmp_path):
    a = EntityKey("player", "1", "club-a")
    b = EntityKey("player", "1", "club-b")
    section = (SaveSection("world_results", 1, {}),)
    with pytest.raises(ValueError, match="unknown entity"):
        SaveDocument("world_results", section, (a,), (EntityLink(a, "moves_to", b),))
    with pytest.raises(ValueError, match="duplicate entity"):
        SaveDocument("world_results", section, (a, a))
    with pytest.raises(ValueError, match="duplicate save section"):
        SaveDocument("world_results", section * 2)
    assert not (tmp_path / "test-saves.sqlite3").exists()


def test_database_enforces_cross_entity_references(tmp_path):
    repo = _repo(tmp_path)
    repo.save("a", "Original", _document(), expected_revision=0)
    with sqlite3.connect(repo.path) as connection:
        connection.execute("PRAGMA foreign_keys=ON")
        with pytest.raises(sqlite3.IntegrityError):
            connection.execute("INSERT INTO save_links VALUES (?,?,?,?,?,?,?,?)", (
                "a", "player", "global", "unknown", "belongs_to", "club", "global", "club-123"
            ))


def test_transaction_rolls_back_when_database_trigger_aborts(tmp_path):
    repo = _repo(tmp_path)
    first = repo.save("a", "Original", _document(), expected_revision=0)
    with sqlite3.connect(repo.path) as connection:
        connection.execute("""CREATE TRIGGER fail_link BEFORE INSERT ON save_links
            BEGIN SELECT RAISE(ABORT, 'forced-failure'); END""")
    with pytest.raises(sqlite3.IntegrityError, match="forced-failure"):
        repo.save("a", "Updated", _document(2), expected_revision=first.revision)
    assert repo.load("a").metadata == first
    assert repo.load("a").document == _document()


def test_checksum_detects_mutated_payload(tmp_path):
    repo = _repo(tmp_path)
    repo.save("a", "Original", _document(), expected_revision=0)
    with sqlite3.connect(repo.path) as connection:
        connection.execute("UPDATE save_sections SET payload_json=? WHERE slot_id='a'",
                           (json.dumps({"number": 900}),))
    with pytest.raises(SaveIntegrityError, match="checksum"):
        repo.load("a")


def test_future_schema_is_rejected_without_downgrading(tmp_path):
    repo = _repo(tmp_path)
    repo.save("a", "Original", _document(), expected_revision=0)
    with sqlite3.connect(repo.path) as connection:
        connection.execute("PRAGMA user_version=999")
    with pytest.raises(UnsupportedSaveVersionError):
        repo.list_slots()
    with sqlite3.connect(repo.path) as connection:
        assert connection.execute("PRAGMA user_version").fetchone()[0] == 999


def test_other_unversioned_database_is_not_repurposed(tmp_path):
    repo = _repo(tmp_path)
    with sqlite3.connect(repo.path) as connection:
        connection.execute("CREATE TABLE foreign_data (secret TEXT)")
    with pytest.raises(UnsupportedSaveVersionError, match="nonempty unversioned"):
        repo.save("a", "No", _document(), expected_revision=0)
    with sqlite3.connect(repo.path) as connection:
        tables = {row[0] for row in connection.execute(
            "SELECT name FROM sqlite_master WHERE type='table'")}
        assert tables == {"foreign_data"}


def test_unsupported_document_version_is_rejected(tmp_path):
    repo = _repo(tmp_path)
    with pytest.raises(UnsupportedSaveVersionError):
        replace(_document(), version=2)
    repo.save("a", "Original", _document(), expected_revision=0)
    with sqlite3.connect(repo.path) as connection:
        connection.execute("UPDATE save_slots SET document_version=2 WHERE slot_id='a'")
    with pytest.raises(UnsupportedSaveVersionError):
        repo.load("a")


def test_world_results_archive_roundtrips_but_not_manager_state(tmp_path):
    world, names = create_world(leagues=1, seed=5414)
    career = WorldCareer(world, names)
    repo = _repo(tmp_path)
    meta = save_world_results(repo, slot_id="results-1", display_name="Temporada", career=career,
                              expected_revision=0)
    assert meta.kind == "world_results"
    loaded_meta, loaded = load_world_results(repo, "results-1")
    assert loaded_meta == meta
    assert loaded.to_dict() == career.to_dict()
    assert {section.name for section in repo.load("results-1").document.sections} == {"world_results"}
    assert all(entity.kind in ("club", "season") for entity in repo.load("results-1").document.entities)


def test_world_results_adapter_rejects_corrupt_world_before_saving(tmp_path):
    world, names = create_world(leagues=1, seed=5415)
    career = WorldCareer(world, names)
    world.results["not-in-calendar"] = WorldMatchResult("not-in-calendar", 1, 0)
    repo = _repo(tmp_path)
    with pytest.raises(ValueError):
        save_world_results(repo, slot_id="invalid", display_name="Invalid",
                           career=career, expected_revision=0)
    assert not repo.path.exists()


def test_tampered_relational_catalog_is_rejected_when_loading_world(tmp_path):
    world, names = create_world(leagues=1, seed=5416)
    repo = _repo(tmp_path)
    save_world_results(repo, slot_id="a", display_name="A", career=WorldCareer(world, names),
                       expected_revision=0)
    with sqlite3.connect(repo.path) as connection:
        connection.execute("DELETE FROM save_links WHERE slot_id='a'")
    with pytest.raises(SaveIntegrityError, match="entity index"):
        load_world_results(repo, "a")


def test_json_archives_unchanged_after_using_new_sqlite_repository(tmp_path):
    world, names = create_world(leagues=1, seed=5417)
    career = WorldCareer(world, names)
    old_path = tmp_path / "original-world-career.json"
    career.save_json(old_path)
    before = old_path.read_bytes()
    repo = _repo(tmp_path)
    save_world_results(repo, slot_id="a", display_name="A", career=career, expected_revision=0)
    _metadata, loaded = load_world_results(repo, "a")
    assert old_path.read_bytes() == before
    assert WorldCareer.load_json(old_path).to_dict() == loaded.to_dict()
