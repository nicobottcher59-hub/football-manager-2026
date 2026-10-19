"""Per-server mutable state; independent of the HTTP transport layer.

The UI API and future desktop adapters must share one runtime instance. Access
mutations under ``runtime.lock`` (jobs have a separate lock for their feed).
"""
from __future__ import annotations

from pathlib import Path
import os
from threading import Lock

from football_manager.dev_ui.session import DevelopmentSession
from football_manager.persistence import SQLiteSaveRepository
from .models import UIRosterAdmin
from .progression import pending_managed_match
from .simulation_jobs import SimulationJob
from .static_assets import find_frontend_root


def default_save_path() -> Path:
    """Local user data, not in the Git repository or a synced project folder."""
    override = os.environ.get('FM_SAVE_DATABASE')
    if override:
        return Path(override).expanduser()
    if os.name == 'nt':
        return Path(os.environ.get('LOCALAPPDATA') or (Path.home() / 'AppData' / 'Local')) / 'FootballManagerGame' / 'saves.sqlite3'
    return Path.home() / '.local' / 'share' / 'football-manager-game' / 'saves.sqlite3'


class UIRuntime:
    def __init__(self, session: DevelopmentSession | None = None,
                 save_repository: SQLiteSaveRepository | None = None,
                 frontend_root: Path | None = None):
        self.session = session or DevelopmentSession()
        self._save_repository = save_repository
        self.frontend_root = find_frontend_root(frontend_root)
        self.admin = UIRosterAdmin()
        self.lock = Lock()
        self.jobs: dict[str, SimulationJob] = {}
        self.active_job: SimulationJob | None = None
        self.match_commands: list[dict] = []
        self.match_fixture_id: str | None = None
        self.match_kits: dict[str, str] = {'home':'default', 'away':'default'}
        self.last_match_summary: dict | None = None

    @property
    def save_repository(self) -> SQLiteSaveRepository:
        if self._save_repository is None:
            self._save_repository = SQLiteSaveRepository(default_save_path())
        return self._save_repository

    def _match_commands_for_current_fixture(self) -> list[dict]:
        fixture = pending_managed_match(self.session)
        fixture_id = fixture.fixture.fixture_id if fixture and fixture.match_date <= self.session.current_date else None
        if fixture_id != self.match_fixture_id:
            self.match_commands.clear()
            self.match_kits = {'home':'default','away':'default'}
            self.match_fixture_id = fixture_id
        return self.match_commands

    def simulation_running(self) -> bool:
        return self.active_job is not None and self.active_job.status == 'running'
