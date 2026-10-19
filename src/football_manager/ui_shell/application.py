"""Application service used by the local HTTP UI and future desktop shells.

The caller holds ``runtime.lock`` while invoking these synchronous methods.
Validation and transactions live here, not in HTTP request handlers. The
injected progression and preview functions preserve deterministic behavior
and allow existing tests / other adapters to substitute implementations.
"""
from __future__ import annotations

from copy import deepcopy
from dataclasses import asdict
from datetime import date
from typing import Callable

from football_manager.persistence import load_manager_career, save_manager_career
from .match import _match_meta, result_read_model
from .models import apply_squad_command
from .progression import advance_day, season_cutoff, simulate_until
from .simulation_jobs import SimulationJob
from .transactions import apply_squad_command_atomically


class GameApplication:
    def __init__(self, runtime, *, prematch_builder: Callable,
                 simulate_until_fn: Callable = simulate_until,
                 advance_day_fn: Callable = advance_day):
        self.runtime = runtime
        self.prematch_builder = prematch_builder
        self.simulate_until_fn = simulate_until_fn
        self.advance_day_fn = advance_day_fn

    @staticmethod
    def validate_target(command: dict) -> date:
        raw = command.get('date')
        if not isinstance(raw, str) or len(raw) != 10:
            raise ValueError('date must be YYYY-MM-DD')
        try:
            return date.fromisoformat(raw)
        except ValueError as exc:
            raise ValueError('date must be a valid YYYY-MM-DD date') from exc

    def list_saves(self) -> dict:
        return {'slots': [asdict(item) for item in self.runtime.save_repository.list_slots()
                          if item.kind == 'manager_career']}

    def command(self, action: str, command: dict) -> dict:
        runtime = self.runtime
        if action == 'career.save':
            metadata = save_manager_career(
                runtime.save_repository,
                slot_id=command.get('slot_id'),
                display_name=command.get('display_name'),
                session=runtime.session,
                admin=runtime.admin,
                last_match_summary=runtime.last_match_summary,
                expected_revision=command.get('expected_revision'),
            )
            return {'saved': True, 'slot': asdict(metadata)}
        if action == 'career.load':
            loaded = load_manager_career(runtime.save_repository, command.get('slot_id'))
            # Prepare the complete archive before publishing any live state.
            runtime.session = loaded.session
            runtime.admin = loaded.admin
            runtime.last_match_summary = loaded.last_match_summary
            runtime.match_commands = []
            runtime.match_fixture_id = None
            runtime.match_kits = {'home': 'default', 'away': 'default'}
            return {'loaded': True, 'slot': asdict(loaded.metadata),
                    'date': loaded.session.current_date.isoformat()}
        if action in ('staff.command', 'training.command', 'medical.command', 'scouting.command'):
            from football_manager.services.club_support import staff_command, training_command, medical_command
            from football_manager.services.professional_scouting import scouting_command
            tentative = deepcopy(runtime.session)
            action_handlers = {'staff.command': staff_command,
                               'training.command': training_command,
                               'medical.command': medical_command,
                               'scouting.command': scouting_command}
            result = action_handlers[action](tentative, command)
            runtime.session = tentative
            return result
        if action == 'inbox.command':
            from football_manager.services.manager_inbox import inbox_command
            tentative = deepcopy(runtime.session)
            result = inbox_command(tentative, command)
            runtime.session = tentative
            return result
        if action == 'career.balance':
            from football_manager.services.opening_balance import apply_opening_balance
            if runtime.match_commands:
                raise ValueError('Finish or reset pending match-only tactics before rebalancing')
            tentative = deepcopy(runtime.session)
            result = apply_opening_balance(tentative, command.get('confirmation'))
            from football_manager.services.manager_inbox import synchronize_manager_inbox
            synchronize_manager_inbox(tentative)
            runtime.session = tentative
            return result
        if action == 'loans.command':
            from football_manager.services.loan_market import loan_command
            tentative = deepcopy(runtime.session)
            result = loan_command(tentative, command)
            from football_manager.services.manager_inbox import synchronize_manager_inbox
            synchronize_manager_inbox(tentative)
            runtime.session = tentative
            return result
        if action == 'transfers.command':
            from football_manager.services.transfer_negotiation import negotiate
            tentative = deepcopy(runtime.session)
            result = negotiate(tentative, command)
            from football_manager.services.manager_inbox import synchronize_manager_inbox
            synchronize_manager_inbox(tentative)
            runtime.session = tentative
            return result
        if action == 'finances.command':
            from football_manager.services.club_economy import renew_contract
            if command.get('action') != 'renew':
                raise ValueError('Unsupported financial operation')
            tentative = deepcopy(runtime.session)
            result = renew_contract(tentative,command)
            from football_manager.services.manager_inbox import synchronize_manager_inbox
            synchronize_manager_inbox(tentative)
            runtime.session = tentative
            return result
        if action == 'youth.command':
            from football_manager.services.youth_academy import youth_command
            tentative = deepcopy(runtime.session)
            result = youth_command(tentative,command)
            from football_manager.services.manager_inbox import synchronize_manager_inbox
            synchronize_manager_inbox(tentative)
            runtime.session = tentative
            return result
        if action == 'development.focus':
            from football_manager.services.player_development import set_development_focus
            return set_development_focus(runtime.session, command.get('player_id'), command.get('focus'))
        if action == 'match.command':
            return self.match_command(command)
        if action == 'squad.command':
            return apply_squad_command_atomically(runtime.session, command, runtime.admin)
        if action == 'progression.job':
            if command.get('action') != 'simulate_until':
                raise ValueError('unsupported simulation job action')
            target = self.validate_target(command)
            start = runtime.session.current_date
            if not start <= target <= season_cutoff(runtime.session):
                raise ValueError('Target must be between current date and the end of the season')
            if (target - start).days > 370:
                raise ValueError('Requested simulation interval is too long')
            job = SimulationJob(deepcopy(runtime.session), target)
            runtime.active_job = job
            runtime.jobs[job.id] = job
            while len(runtime.jobs) > 3:
                runtime.jobs.pop(next(iter(runtime.jobs)))
            job.start(runtime)
            return {'job_id': job.id, 'status': 'running',
                    'from_date': start.isoformat(), 'target_date': target.isoformat()}
        if action == 'progression.command':
            tentative = deepcopy(runtime.session)
            if command.get('action') == 'advance_day':
                result = self.advance_day_fn(tentative)
            elif command.get('action') == 'simulate_until':
                result = self.simulate_until_fn(tentative, self.validate_target(command))
            else:
                raise ValueError('unsupported progression command')
            from football_manager.services.manager_inbox import synchronize_manager_inbox
            synchronize_manager_inbox(tentative)
            runtime.session = tentative
            return result
        raise ValueError('unsupported application command')

    def match_command(self, command: dict) -> dict:
        """Validate temporary tactical edits and commit match results transactionally."""
        action = command.get('action')
        runtime = self.runtime
        commands = runtime._match_commands_for_current_fixture()
        if action == 'quick_sim' and runtime.last_match_summary and command.get('fixture_id') == runtime.last_match_summary.get('match', {}).get('fixture_id'):
            return runtime.last_match_summary
        current = _match_meta(runtime.session)
        if current is None:
            raise ValueError('No managed match is waiting today')
        if command.get('fixture_id') != current['fixture_id']:
            raise ValueError('Outdated match tab; reload this match before making changes')
        if action == 'match_tactic':
            tactic = command.get('command')
            allowed = {'formation','preset','role','team_instruction','player_instruction','reset_player_instructions','swap_bench','swap_starters','studio_activate_plan','studio_rules'}
            if not isinstance(tactic,dict) or tactic.get('action') not in allowed:
                raise ValueError('Unsupported match-only tactical adjustment')
            if len(commands) >= 100:
                raise ValueError('Too many temporary tactical changes')
            # Render/validate the candidate before changing the pending plan.
            # Failed previews must not leave a command that the manager did not see.
            candidate_commands = [*commands, tactic]
            payload = self.prematch_builder(runtime.session, runtime.admin, candidate_commands)
            payload['kits'] = dict(runtime.match_kits)
            commands.append(tactic)
            return payload
        if action == 'reset_match_tactics':
            payload = self.prematch_builder(runtime.session, runtime.admin)
            payload['kits'] = dict(runtime.match_kits)
            commands.clear()
            return payload
        if action == 'match_kits':
            home, away = command.get('home'), command.get('away')
            allowed = ('default','dark','light','blue','red','purple','yellow','green')
            if home not in allowed or away not in allowed:
                raise ValueError('Unknown kit option')
            payload = self.prematch_builder(runtime.session, runtime.admin, commands)
            candidate_kits = {'home': home, 'away': away}
            payload['kits'] = dict(candidate_kits)
            runtime.match_kits = candidate_kits
            return payload
        if action == 'quick_sim':
            temp = deepcopy(runtime.session)
            # Match-only commands may mutate this Tactic in place. Keeping its
            # reference would retain those changes as the permanent tactic.
            baseline_lineup, baseline_tactic = temp.home_lineup, deepcopy(temp.home_tactic)
            baseline_studio = deepcopy(temp.tactical_studio)
            before_injury = {p.id:p.state.injury for p in temp.home_club.squad.players}
            for tactic in commands:
                apply_squad_command(temp,tactic)
            unavailable = [p.full_name for p in temp.home_lineup.starting_players if not p.state.is_available]
            if unavailable:
                raise ValueError('Unavailable players cannot start: ' + ', '.join(unavailable))
            result = temp.quick_simulate()  # Engine commits result to cloned WorldRunner only
            summary = result_read_model(temp,current,result,before_injury)
            temp.home_lineup, temp.home_tactic = baseline_lineup, baseline_tactic
            temp.tactical_studio = baseline_studio
            temp._sync_effective_tactic_familiarity(home=True)
            from football_manager.services.manager_inbox import synchronize_manager_inbox
            synchronize_manager_inbox(temp)
            runtime.session = temp  # Atomic in-memory replacement on successful completion
            runtime.last_match_summary = summary
            runtime.match_commands = []
            runtime.match_fixture_id = None
            runtime.match_kits = {'home':'default','away':'default'}
            return summary
        raise ValueError('Unsupported match action')

