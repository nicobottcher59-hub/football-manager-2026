"""Versioned SQLite persistence, including opt-in manager career saves."""

from .career_adapter import load_world_results, save_world_results, world_career_document
from .models import (
    EntityKey, EntityLink, SaveConflictError, SaveDocument, SaveIntegrityError,
    SaveMetadata, SaveSection, StoredSave, UnsupportedSaveVersionError,
)
from .sqlite_repository import DB_SCHEMA_VERSION, SQLiteSaveRepository

__all__ = [
    "DB_SCHEMA_VERSION", "EntityKey", "EntityLink", "SaveConflictError",
    "SaveDocument", "SaveIntegrityError", "SaveMetadata", "SaveSection",
    "StoredSave", "UnsupportedSaveVersionError", "SQLiteSaveRepository",
    "world_career_document", "save_world_results", "load_world_results",
]

from .manager_career import (
    LoadedManagerCareer, load_manager_career, manager_career_document,
    save_manager_career, validate_manager_session,
)
from .session_codec import GRAPH_VERSION

__all__ += [
    'GRAPH_VERSION', 'LoadedManagerCareer', 'load_manager_career',
    'manager_career_document', 'save_manager_career', 'validate_manager_session',
]
