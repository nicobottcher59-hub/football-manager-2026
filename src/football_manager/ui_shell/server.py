"""Loopback-only HTTP transport for the Football Manager application."""
from __future__ import annotations

from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from datetime import date
from urllib.parse import unquote, urlsplit, parse_qs
import json
import mimetypes
import sqlite3
import webbrowser

from football_manager.dev_ui.session import DevelopmentSession
from football_manager.persistence import SQLiteSaveRepository
from .application import GameApplication
from .runtime import UIRuntime, default_save_path
from .static_assets import resolve_static_asset
from .models import squad_read_model
from .dressing_room import dressing_room_read_model
from .calendar import calendar_read_model
from .competitions import competition_options, competition_read_model
from .world_squads import world_squads_index, club_squad_read_model
from .progression import progression_read_model, advance_day, simulate_until, pending_managed_match
from .match import prematch_read_model
from .club_profiles import club_profile_read_model
from .player_profiles import player_profile_read_model
from .home_competition import home_competition_read_model
from football_manager.services.opening_balance import preview_opening_balance

HOST = "127.0.0.1"
PORT = 8765
MAX_REQUEST = 4096


# The HTTP adapter maps URLs to transport-independent application commands.
POST_COMMANDS = {
    '/api/squad': 'squad.command',
    '/api/progression': 'progression.command',
    '/api/progression/jobs': 'progression.job',
    '/api/match': 'match.command',
    '/api/career/save': 'career.save',
    '/api/career/load': 'career.load',
    '/api/balance': 'career.balance',
    '/api/development/focus': 'development.focus',
    '/api/youth': 'youth.command',
    '/api/finances': 'finances.command',
    '/api/transfers': 'transfers.command',
    '/api/loans': 'loans.command',
    '/api/inbox': 'inbox.command',
    '/api/staff': 'staff.command',
    '/api/training': 'training.command',
    '/api/medical': 'medical.command',
}


class FootballUIHandler(BaseHTTPRequestHandler):
    runtime: UIRuntime

    def _allowed_origin(self) -> bool:
        host = self.headers.get("Host", "")
        host_ok = host in {f"127.0.0.1:{self.server.server_port}", f"localhost:{self.server.server_port}"}
        origin = self.headers.get("Origin")
        return host_ok and (origin is None or origin in {
            f"http://127.0.0.1:{self.server.server_port}",
            f"http://localhost:{self.server.server_port}",
            "http://127.0.0.1:5173",  # optional Vite dev server proxy
            "http://localhost:5173",
        })

    def _write(self, code: int, data: bytes, content_type: str = "application/json; charset=utf-8") -> None:
        self.send_response(code)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(data)))
        self.send_header("Cache-Control", "no-store")
        self.send_header("X-Content-Type-Options", "nosniff")
        self.send_header("X-Frame-Options", "SAMEORIGIN")
        self.end_headers()
        self.wfile.write(data)

    def _json(self, code: int, payload: dict) -> None:
        self._write(code, json.dumps(payload, ensure_ascii=False, allow_nan=False).encode("utf-8"))

    def do_GET(self) -> None:
        if not self._allowed_origin():
            self._json(403, {"error": "Only local application access is allowed"})
            return
        path = unquote(urlsplit(self.path).path)
        if path.startswith("/api/progression/jobs/"):
            job_id = path.removeprefix('/api/progression/jobs/')
            with self.runtime.lock:
                job = self.runtime.jobs.get(job_id)
            if job is None:
                self._json(404, {"error": "Simulation job not found"})
                return
            try:
                query = parse_qs(urlsplit(self.path).query)
                after = int(query.get('after', ['0'])[0])
                limit = int(query.get('limit', ['80'])[0])
                data = job.snapshot(after, limit)
            except (ValueError, TypeError):
                self._json(400, {"error": "Invalid progress pagination"})
                return
            self._json(200, data)
            return
        if path == "/api/career/saves":
            try:
                with self.runtime.lock:
                    payload = GameApplication(self.runtime, prematch_builder=prematch_read_model).list_saves()
            except (ValueError, sqlite3.Error, OSError):
                self._json(503, {'error': 'Career storage is unavailable'})
                return
            self._json(200, payload)
            return
        if path == "/api/match":
            with self.runtime.lock:
                commands = self.runtime._match_commands_for_current_fixture()
                if commands or pending_managed_match(self.runtime.session) and pending_managed_match(self.runtime.session).match_date <= self.runtime.session.current_date:
                    try:
                        payload = prematch_read_model(self.runtime.session, self.runtime.admin, commands)
                        payload['kits'] = dict(self.runtime.match_kits)
                    except (ValueError, KeyError) as exc:
                        self._json(409, {'error':str(exc)})
                        return
                elif self.runtime.last_match_summary and self.runtime.last_match_summary['match']['date'] == self.runtime.session.current_date.isoformat():
                    payload = self.runtime.last_match_summary
                else:
                    payload = prematch_read_model(self.runtime.session,self.runtime.admin)
                self._json(200, payload)
            return
        if path == "/api/progression":
            with self.runtime.lock:
                self._json(200, progression_read_model(self.runtime.session))
            return
        if path == "/api/calendar":
            with self.runtime.lock:
                self._json(200, calendar_read_model(self.runtime.session))
            return
        if path == "/api/competitions":
            with self.runtime.lock:
                self._json(200, competition_options(self.runtime.session))
            return
        if path.startswith("/api/competitions/"):
            competition_id = path[len("/api/competitions/"):]
            if not competition_id or "/" in competition_id:
                self._json(404, {"error": "Competition not found"})
                return
            with self.runtime.lock:
                try:
                    payload = competition_read_model(self.runtime.session, competition_id)
                except KeyError:
                    self._json(404, {"error": "Competition not found"})
                    return
                self._json(200, payload)
            return
        if path == '/api/loans':
            from football_manager.services.loan_market import loan_read_model
            with self.runtime.lock:
                self._json(200, loan_read_model(self.runtime.session))
            return
        if path == '/api/transfers':
            from football_manager.services.transfer_negotiation import transfer_read_model
            with self.runtime.lock:
                self._json(200, transfer_read_model(self.runtime.session))
            return
        if path == '/api/finances':
            from football_manager.services.club_economy import finances_read_model
            with self.runtime.lock:
                try:
                    query = parse_qs(urlsplit(self.path).query)
                    payload = finances_read_model(self.runtime.session,query.get('club',[None])[0])
                except KeyError:
                    self._json(404,{'error':'Club financial information not available'})
                    return
                self._json(200,payload)
            return
        if path == '/api/youth':
            from football_manager.services.youth_academy import youth_read_model
            with self.runtime.lock:
                try:
                    query = parse_qs(urlsplit(self.path).query)
                    payload = youth_read_model(self.runtime.session, query.get('club',[None])[0])
                except KeyError:
                    self._json(404,{'error':'Youth academy not available'})
                    return
                self._json(200,payload)
            return
        if path == "/api/world-squads":
            with self.runtime.lock:
                self._json(200, world_squads_index(self.runtime.session))
            return
        if path.startswith("/api/world-squads/"):
            club_id = path.removeprefix("/api/world-squads/")
            with self.runtime.lock:
                try:
                    payload = club_squad_read_model(self.runtime.session, club_id)
                except KeyError:
                    self._json(404, {"error": "Club is not in the persistent English world"})
                    return
                self._json(200, payload)
            return
        if path == '/api/home-competition':
            query = parse_qs(urlsplit(self.path).query)
            with self.runtime.lock:
                try:
                    payload = home_competition_read_model(self.runtime.session, query.get('id', [None])[0])
                except KeyError:
                    self._json(404, {'error': 'Competition is unavailable'})
                    return
                self._json(200, payload)
            return
        if path == '/api/balance':
            with self.runtime.lock:
                self._json(200, preview_opening_balance(self.runtime.session))
            return
        if path.startswith('/api/clubs/'):
            parts = path.removeprefix('/api/clubs/').split('/')
            query = parse_qs(urlsplit(self.path).query)
            with self.runtime.lock:
                try:
                    if len(parts) == 1:
                        payload = club_profile_read_model(self.runtime.session, parts[0],
                            season=query.get('season', [None])[0], competition=query.get('competition', [None])[0])
                    elif len(parts) == 3 and parts[1] == 'players':
                        payload = player_profile_read_model(self.runtime.session, parts[0], parts[2],
                            position=query.get('position', [None])[0], role_id=query.get('role', [None])[0])
                    else:
                        raise KeyError('Unknown club endpoint')
                except KeyError:
                    self._json(404, {'error': 'Club or player unavailable'})
                    return
                except ValueError as exc:
                    self._json(400, {'error': str(exc)})
                    return
                self._json(200, payload)
            return
        if path == '/api/staff':
            from football_manager.services.club_support import staff_read_model
            with self.runtime.lock:
                self._json(200, staff_read_model(self.runtime.session))
            return
        if path == '/api/training':
            from football_manager.services.club_support import training_read_model
            with self.runtime.lock:
                self._json(200, training_read_model(self.runtime.session))
            return
        if path == '/api/medical':
            from football_manager.services.club_support import medical_read_model
            with self.runtime.lock:
                self._json(200, medical_read_model(self.runtime.session))
            return
        if path == '/api/inbox':
            from football_manager.services.manager_inbox import inbox_read_model
            with self.runtime.lock:
                self._json(200, inbox_read_model(self.runtime.session))
            return
        if path == "/api/dressing-room":
            with self.runtime.lock:
                self._json(200, dressing_room_read_model(self.runtime.session))
            return
        if path == "/api/squad":
            with self.runtime.lock:
                query = parse_qs(urlsplit(self.path).query)
                self._json(200, squad_read_model(self.runtime.session, self.runtime.admin,
                    season=query.get('season', [None])[0], competition=query.get('competition', [None])[0]))
            return
        # The portable document uses relative CSS/JS URLs (and must also work
        # when opened as a file). Serving it *at* / makes those URLs resolve to
        # /styles.css instead of /portable/styles.css. Redirect the browser to
        # the real directory so all relative references resolve correctly.
        if path == "/":
            self.send_response(302)
            self.send_header("Location", "/portable/")
            self.send_header("Cache-Control", "no-store")
            self.send_header("Content-Length", "0")
            self.end_headers()
            return
        file = resolve_static_asset(path, self.runtime.frontend_root)
        if file is None:
            self._json(404, {"error": "Resource not found"})
            return
        content_type = mimetypes.guess_type(file.name)[0] or "application/octet-stream"
        if content_type.startswith("text/") or content_type in ("application/javascript", "image/svg+xml"):
            content_type += "; charset=utf-8"
        self._write(200, file.read_bytes(), content_type)

    @staticmethod
    def _validate_target(command: dict) -> date:
        return GameApplication.validate_target(command)

    def _match_command(self, command: dict) -> dict:
        return GameApplication(self.runtime, prematch_builder=prematch_read_model).match_command(command)

    def do_POST(self) -> None:
        path = urlsplit(self.path).path
        if not self._allowed_origin() or path not in POST_COMMANDS:
            self._json(403, {"error": "Unauthorized request"})
            return
        if self.headers.get("Content-Type", "").split(";")[0].strip().lower() != "application/json":
            self._json(415, {"error": "JSON request required"})
            return
        try:
            length = int(self.headers.get("Content-Length", "0"))
            if not 0 < length <= MAX_REQUEST:
                raise ValueError("Invalid request size")
            command = json.loads(self.rfile.read(length))
            if not isinstance(command, dict):
                raise ValueError("JSON object required")
            with self.runtime.lock:
                if self.runtime.simulation_running():
                    self._json(409, {"error": "A calendar simulation is already running"})
                    return
                result = GameApplication(
                    self.runtime, prematch_builder=prematch_read_model,
                    simulate_until_fn=simulate_until, advance_day_fn=advance_day,
                ).command(POST_COMMANDS[path], command)
        except (TypeError, ValueError, KeyError, json.JSONDecodeError) as exc:
            self._json(400, {"error": str(exc)})
            return
        except RuntimeError as exc:
            self._json(409, {"error": str(exc)})
            return
        except (sqlite3.Error, OSError):
            self._json(503, {"error": "Career storage is unavailable"})
            return
        self._json(200, result)


def create_server(port: int = PORT, session: DevelopmentSession | None = None,
                  save_repository: SQLiteSaveRepository | None = None,
                  frontend_root: Path | None = None):
    runtime = UIRuntime(session, save_repository, frontend_root)

    class Handler(FootballUIHandler):
        pass

    Handler.runtime = runtime
    return ThreadingHTTPServer((HOST, port), Handler)


def main() -> None:
    try:
        server = create_server()
    except OSError as exc:
        raise SystemExit(f"Could not start local UI on 127.0.0.1:{PORT}: {exc}") from exc
    print(f"FM Project UI: http://{HOST}:{PORT}/", flush=True)
    print("Career saves are opt-in through /api/career/save and /api/career/load.", flush=True)
    print("Closing the window does not autosave the session.", flush=True)
    webbrowser.open(f"http://{HOST}:{PORT}/")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()


if __name__ == "__main__":
    main()
