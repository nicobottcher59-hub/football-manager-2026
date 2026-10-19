"""Transactional async progress feed for UI-3.4.1 Calendar auto-simulation.

All fixtures are resolved on a private session copy. Poll responses contain only
actual WorldSeasonRunner results, in chronological order. The public session is
replaced only after a completely successful simulation.
"""
from __future__ import annotations

from datetime import date
from threading import Lock, Thread
from uuid import uuid4

from football_manager.dev_ui.session import DevelopmentSession
from .progression import simulate_until


class SimulationJob:
    def __init__(self, working_session: DevelopmentSession, target: date) -> None:
        self.id = uuid4().hex
        self.session = working_session
        self.target = target
        self.start_date = working_session.current_date
        self.total_days = (target - self.start_date).days + 1
        self.lock = Lock()
        self.status = 'running'
        self.current_day = self.start_date.isoformat()
        self.days_completed = 0
        self.events: list[dict] = []
        self.result: dict | None = None
        self.error: str | None = None

    def _day_finished(self, day: date, results: list[dict]) -> None:
        with self.lock:
            self.current_day = day.isoformat()
            self.days_completed = (day - self.start_date).days + 1
            for item in results:
                # Sequence is stable and starts at one. The server serves events
                # in bounded pages so neither the UI nor HTTP response explodes.
                self.events.append({'seq': len(self.events) + 1, **item})

    def snapshot(self, after: int = 0, limit: int = 80) -> dict:
        with self.lock:
            if not 0 <= after <= len(self.events):
                raise ValueError('Invalid event cursor')
            if not 1 <= limit <= 100:
                raise ValueError('Invalid event page size')
            entries = list(self.events[after:after + limit])
            return {
                'job_id': self.id, 'status': self.status,
                'from_date': self.start_date.isoformat(),
                'target_date': self.target.isoformat(),
                'current_day': self.current_day,
                'days_completed': self.days_completed,
                'total_days': self.total_days,
                'percent': round(100 * self.days_completed / self.total_days, 1),
                'results_available': len(self.events),
                'events': entries,
                'next_cursor': after + len(entries),
                'has_more': after + len(entries) < len(self.events),
                'result': self.result if self.status == 'completed' else None,
                'error': self.error if self.status == 'failed' else None,
                'committed': self.status == 'completed',
            }

    def start(self, runtime) -> None:
        Thread(target=self._run, args=(runtime,), daemon=True, name=f'fm-auto-sim-{self.id[:8]}').start()

    def _run(self, runtime) -> None:
        # The private copy is retained only while it is being simulated. Keeping
        # finished jobs for polling must not retain entire previous worlds.
        working = self.session
        try:
            output = simulate_until(working, self.target, on_day=self._day_finished)
            # Publish world and final job status in the same critical section:
            # no request can observe the new world while its job is 'running'.
            # Lock order: runtime then job. The polling endpoint releases
            # runtime.lock before taking the job lock, avoiding inversion.
            with runtime.lock:
                with self.lock:
                    runtime.session = working
                    self.result = output
                    self.status = 'completed'
                    self.session = None
                    if runtime.active_job is self:
                        runtime.active_job = None
        except Exception as exc:
            # The public world stays untouched. Preserve progress events and
            # the error for clients, but drop the failed private session.
            with runtime.lock:
                with self.lock:
                    self.status = 'failed'
                    self.error = f'{type(exc).__name__}: {exc}'
                    self.session = None
                    if runtime.active_job is self:
                        runtime.active_job = None
