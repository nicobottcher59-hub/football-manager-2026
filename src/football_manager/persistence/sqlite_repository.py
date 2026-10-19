"""Opt-in SQLite snapshot repository for game-state adapters.

The database uses explicit schema migration and SQLite transactions; sections
are canonical UTF-8 JSON with SHA-256 checksums. Each slot is protected by an
optimistic revision number. This is a foundation, not a full manager save.
"""
from __future__ import annotations

from contextlib import closing
from datetime import datetime, timezone
from hashlib import sha256
from hmac import compare_digest
import json
from pathlib import Path
import os
import tempfile
import sqlite3
from typing import Any, Mapping

from .models import (
    EntityKey, EntityLink, SaveConflictError, SaveDocument, SaveIntegrityError,
    SaveMetadata, SaveSection, StoredSave, UnsupportedSaveVersionError, _text,
)

DB_SCHEMA_VERSION = 1
_TABLES = frozenset({"save_slots", "save_sections", "save_entities", "save_links"})


def _check_json_tree(value: Any) -> None:
    """Do not permit JSON's silent conversion of non-string dict keys."""
    if isinstance(value, Mapping):
        for key, child in value.items():
            if not isinstance(key, str):
                raise ValueError("save payload JSON object keys must be strings")
            _check_json_tree(child)
    elif isinstance(value, (list, tuple)):
        for child in value:
            _check_json_tree(child)
    elif value is None or isinstance(value, (str, bool, int, float)):
        pass
    else:
        raise ValueError(f"unsupported save payload type: {type(value).__name__}")


def _encode(payload: Mapping[str, Any]) -> tuple[str, str]:
    _check_json_tree(payload)
    try:
        text = json.dumps(payload, ensure_ascii=False, sort_keys=True,
                          separators=(",", ":"), allow_nan=False)
    except (ValueError, TypeError, OverflowError) as exc:
        raise ValueError("save contains non-JSON or non-finite values") from exc
    return text, sha256(text.encode("utf-8")).hexdigest()


def _decode(value: str, checksum: str) -> Mapping[str, Any]:
    if not compare_digest(sha256(value.encode("utf-8")).hexdigest(), checksum):
        raise SaveIntegrityError("save section checksum mismatch")
    def reject_nonfinite(_value: str):
        raise ValueError("non-finite JSON constant")

    try:
        payload = json.loads(value, parse_constant=reject_nonfinite)
    except (ValueError, TypeError) as exc:
        raise SaveIntegrityError("save section is invalid JSON") from exc
    if not isinstance(payload, dict):
        raise SaveIntegrityError("save section must decode to a JSON object")
    return payload


_SCHEMA_STATEMENTS = (
    """CREATE TABLE save_slots (
        slot_id TEXT PRIMARY KEY,
        display_name TEXT NOT NULL,
        revision INTEGER NOT NULL CHECK (revision >= 1),
        kind TEXT NOT NULL,
        document_version INTEGER NOT NULL,
        created_at_utc TEXT NOT NULL,
        updated_at_utc TEXT NOT NULL
    )""",
    """CREATE TABLE save_sections (
        slot_id TEXT NOT NULL REFERENCES save_slots(slot_id) ON DELETE CASCADE,
        section_name TEXT NOT NULL,
        section_version INTEGER NOT NULL CHECK (section_version >= 1),
        payload_json TEXT NOT NULL,
        sha256 TEXT NOT NULL,
        PRIMARY KEY (slot_id, section_name)
    )""",
    """CREATE TABLE save_entities (
        slot_id TEXT NOT NULL REFERENCES save_slots(slot_id) ON DELETE CASCADE,
        kind TEXT NOT NULL,
        scope TEXT NOT NULL,
        entity_id TEXT NOT NULL,
        PRIMARY KEY (slot_id, kind, scope, entity_id)
    )""",
    """CREATE TABLE save_links (
        slot_id TEXT NOT NULL,
        source_kind TEXT NOT NULL,
        source_scope TEXT NOT NULL,
        source_id TEXT NOT NULL,
        relation TEXT NOT NULL,
        target_kind TEXT NOT NULL,
        target_scope TEXT NOT NULL,
        target_id TEXT NOT NULL,
        PRIMARY KEY (slot_id, source_kind, source_scope, source_id, relation,
                     target_kind, target_scope, target_id),
        FOREIGN KEY (slot_id, source_kind, source_scope, source_id)
            REFERENCES save_entities(slot_id, kind, scope, entity_id) ON DELETE CASCADE,
        FOREIGN KEY (slot_id, target_kind, target_scope, target_id)
            REFERENCES save_entities(slot_id, kind, scope, entity_id) ON DELETE CASCADE
    )""",
)


def _migrate(connection: sqlite3.Connection) -> None:
    version = connection.execute("PRAGMA user_version").fetchone()[0]
    if version == DB_SCHEMA_VERSION:
        # Normal load/list operations must not need a write lock.
        actual = {row[0] for row in connection.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%'")}
        if not _TABLES.issubset(actual):
            raise SaveIntegrityError("SQLite save schema is missing required tables")
        return
    if version != 0:
        raise UnsupportedSaveVersionError(f"unsupported SQLite save schema: {version}")
    # Acquire the write lock and RECHECK the version. Another process might
    # have initialized this file since the first PRAGMA above.
    connection.execute("BEGIN IMMEDIATE")
    try:
        version = connection.execute("PRAGMA user_version").fetchone()[0]
        if version == DB_SCHEMA_VERSION:
            connection.commit()
            return _migrate(connection)
        if version != 0:
            raise UnsupportedSaveVersionError(f"unsupported SQLite save schema: {version}")
        actual = {row[0] for row in connection.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%'")}
        if actual:
            raise UnsupportedSaveVersionError("refusing to repurpose a nonempty unversioned database")
        # executescript() commits implicitly, so each DDL statement is executed
        # individually to keep initial schema creation atomic.
        for statement in _SCHEMA_STATEMENTS:
            connection.execute(statement)
        connection.execute("PRAGMA user_version=1")
        connection.commit()
    except BaseException:
        connection.rollback()
        raise


def _metadata(row: sqlite3.Row) -> SaveMetadata:
    return SaveMetadata(row["slot_id"], row["display_name"], row["revision"],
                        row["kind"], row["created_at_utc"], row["updated_at_utc"])


class SQLiteSaveRepository:
    """Transactional repository for local, single-player save slots.

    expected_revision=0 creates a slot. An update must supply the exact
    revision returned by its previous save/load. This prevents silent lost
    updates from multiple processes or concurrent simulation commands.
    """

    def __init__(self, path: str | Path) -> None:
        self.path = Path(path)
        if self.path.exists() and self.path.is_dir():
            raise ValueError("SQLite save path must point to a file")

    def backup_to(self, destination: str | Path) -> Path:
        """Create an atomic, consistent SQLite backup without copying a live DB file.

        The SQLite online backup API includes committed WAL changes. An
        interrupted backup never replaces a prior good backup.
        """
        target = Path(destination)
        if self.path.resolve() == target.resolve():
            raise ValueError("backup destination must differ from save database")
        target.parent.mkdir(parents=True, exist_ok=True)
        temporary: str | None = None
        try:
            with tempfile.NamedTemporaryFile(prefix=target.name + ".", suffix=".tmp",
                                             dir=target.parent, delete=False) as file:
                temporary = file.name
            with closing(self._connect()) as source, closing(sqlite3.connect(temporary)) as backup:
                source.backup(backup)
                result = backup.execute("PRAGMA integrity_check").fetchone()[0]
                if result != 'ok':
                    raise SaveIntegrityError('SQLite backup failed integrity check')
            os.replace(temporary, target)
            return target
        finally:
            if temporary and os.path.exists(temporary):
                os.unlink(temporary)

    def _connect(self) -> sqlite3.Connection:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        connection = sqlite3.connect(self.path, timeout=10, isolation_level=None)
        connection.row_factory = sqlite3.Row
        try:
            connection.execute("PRAGMA foreign_keys=ON")
            connection.execute("PRAGMA busy_timeout=10000")
            _migrate(connection)
        except BaseException:
            connection.close()
            raise
        return connection

    def save(self, slot_id: str, display_name: str, document: SaveDocument, *,
             expected_revision: int) -> SaveMetadata:
        _text(slot_id, "slot ID")
        _text(display_name, "save display name")
        if not isinstance(document, SaveDocument):
            raise TypeError("save requires a SaveDocument")
        if type(expected_revision) is not int or expected_revision < 0:
            raise ValueError("expected_revision must be a nonnegative integer")
        # Encode *before* opening a transaction, so invalid values never touch
        # an existing save and checksums describe exactly the stored JSON.
        sections = [(section.name, section.version, *_encode(section.payload))
                    for section in document.sections]
        timestamp = datetime.now(timezone.utc).isoformat(timespec="microseconds")
        with closing(self._connect()) as conn, conn:
            conn.execute("BEGIN IMMEDIATE")
            previous = conn.execute(
                "SELECT revision, created_at_utc FROM save_slots WHERE slot_id=?", (slot_id,),
            ).fetchone()
            actual = 0 if previous is None else previous["revision"]
            if actual != expected_revision:
                raise SaveConflictError(
                    f"save slot {slot_id!r} revision mismatch: expected {expected_revision}, found {actual}"
                )
            revision = actual + 1
            created_at = timestamp if previous is None else previous["created_at_utc"]
            if previous is None:
                conn.execute("INSERT INTO save_slots VALUES (?, ?, ?, ?, ?, ?, ?)",
                             (slot_id, display_name, revision, document.kind, document.version,
                              created_at, timestamp))
            else:
                conn.execute("UPDATE save_slots SET display_name=?,revision=?,kind=?,"
                             "document_version=?,updated_at_utc=? WHERE slot_id=?",
                             (display_name, revision, document.kind, document.version,
                              timestamp, slot_id))
                conn.execute("DELETE FROM save_links WHERE slot_id=?", (slot_id,))
                conn.execute("DELETE FROM save_entities WHERE slot_id=?", (slot_id,))
                conn.execute("DELETE FROM save_sections WHERE slot_id=?", (slot_id,))
            conn.executemany("INSERT INTO save_sections VALUES (?, ?, ?, ?, ?)",
                             ((slot_id, name, version, data, digest)
                              for name, version, data, digest in sections))
            conn.executemany("INSERT INTO save_entities VALUES (?, ?, ?, ?)",
                             ((slot_id, entity.kind, entity.scope, entity.entity_id)
                              for entity in document.entities))
            conn.executemany("INSERT INTO save_links VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                             ((slot_id, link.source.kind, link.source.scope, link.source.entity_id,
                               link.relation, link.target.kind, link.target.scope, link.target.entity_id)
                              for link in document.links))
            return SaveMetadata(slot_id, display_name, revision, document.kind,
                                created_at, timestamp)

    def load(self, slot_id: str) -> StoredSave:
        _text(slot_id, "slot ID")
        with closing(self._connect()) as conn, conn:
            row = conn.execute("SELECT * FROM save_slots WHERE slot_id=?", (slot_id,)).fetchone()
            if row is None:
                raise KeyError(f"save slot {slot_id!r} does not exist")
            if row["document_version"] != 1:
                raise UnsupportedSaveVersionError("unsupported save document version")
            parts = tuple(SaveSection(p["section_name"], p["section_version"],
                                      _decode(p["payload_json"], p["sha256"]))
                          for p in conn.execute(
                              "SELECT * FROM save_sections WHERE slot_id=? ORDER BY section_name", (slot_id,)
                          ))
            entities = tuple(EntityKey(e["kind"], e["entity_id"], e["scope"])
                             for e in conn.execute(
                                 "SELECT * FROM save_entities WHERE slot_id=? "
                                 "ORDER BY kind,scope,entity_id", (slot_id,)
                             ))
            links = tuple(EntityLink(EntityKey(e["source_kind"], e["source_id"], e["source_scope"]),
                                     e["relation"],
                                     EntityKey(e["target_kind"], e["target_id"], e["target_scope"]))
                          for e in conn.execute(
                              "SELECT * FROM save_links WHERE slot_id=? "
                              "ORDER BY source_kind,source_scope,source_id,relation,target_kind,target_scope,target_id",
                              (slot_id,)
                          ))
            try:
                document = SaveDocument(kind=row["kind"], version=row["document_version"],
                                        sections=parts, entities=entities, links=links)
            except ValueError as exc:
                raise SaveIntegrityError("save document has invalid relationships or metadata") from exc
            return StoredSave(_metadata(row), document)

    def list_slots(self) -> tuple[SaveMetadata, ...]:
        with closing(self._connect()) as conn, conn:
            return tuple(_metadata(row) for row in conn.execute(
                "SELECT * FROM save_slots ORDER BY updated_at_utc DESC,slot_id"
            ))

    def delete(self, slot_id: str, *, expected_revision: int) -> None:
        _text(slot_id, "slot ID")
        if type(expected_revision) is not int or expected_revision < 1:
            raise ValueError("delete requires a positive expected_revision")
        with closing(self._connect()) as conn, conn:
            conn.execute("BEGIN IMMEDIATE")
            row = conn.execute("SELECT revision FROM save_slots WHERE slot_id=?",
                               (slot_id,)).fetchone()
            if row is None:
                raise KeyError(f"save slot {slot_id!r} does not exist")
            if row["revision"] != expected_revision:
                raise SaveConflictError("save slot changed before deletion")
            conn.execute("DELETE FROM save_slots WHERE slot_id=?", (slot_id,))
