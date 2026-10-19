"""TS-26 manager controls. Bounded influence, deterministic offers, no daily chores."""
from __future__ import annotations

from dataclasses import replace
from datetime import date, timedelta
from hashlib import sha256

from football_manager.domain.club_support import (
    ROLES, GROUPS, INTENSITIES, ClubSupport, StaffMember, MedicalDecision, TrainingPolicy,
)
from football_manager.domain.player_development import stable_random
from football_manager.services.player_condition import recover_player_between_matches

NAMES = ('Alex Morgan', 'Jordan Reed', 'Sam Bennett', 'Robin Ellis', 'Taylor Walsh',
         'Jamie Cooper', 'Casey Clarke', 'Drew Foster', 'Charlie Brooks', 'Morgan Price',
         'Avery Hughes', 'Riley Parker', 'Blair Turner', 'Dylan Mason', 'Jesse Nolan')


def _seed_value(*items: object) -> int:
    return int.from_bytes(sha256('|'.join(map(str, items)).encode('utf-8')).digest()[:8], 'big')


def staff_capacity_for_tier(initial_tier: int) -> dict[str, int]:
    """Interim slots only; future club facilities can replace these numbers."""
    return {1: {'coach': 3, 'medic': 2, 'fitness': 2},
            2: {'coach': 2, 'medic': 2, 'fitness': 2},
            3: {'coach': 2, 'medic': 1, 'fitness': 2},
            4: {'coach': 1, 'medic': 1, 'fitness': 1},
            0: {'coach': 1, 'medic': 1, 'fitness': 1}}[initial_tier].copy()


def staff_wage(quality: int, tier: int) -> int:
    return int(round((180 + quality * quality * .33) * {0: .7, 1: 1.2, 2: .9, 3: .75, 4: .65}[tier] / 25) * 25)


def initialize_club_support(registry, on_date: date) -> None:
    """One-time initialization: never reroll signed staff on season change/load."""
    for cid, identity in registry.identities.items():
        if cid in registry.club_support:
            continue
        dept = ClubSupport(cid, staff_capacity_for_tier(identity.initial_tier))
        for role in ROLES:
            code = _seed_value(registry.seed, cid, role, 'starter')
            quality = 48 + code % 28
            employee = StaffMember(f'staff:{cid}:{role}:starter', cid, NAMES[code % len(NAMES)],
                                   role, quality, staff_wage(quality, identity.initial_tier),
                                   on_date, on_date + timedelta(days=730))
            dept.members[employee.member_id] = employee
        dept.baseline_weekly_gbp = sum(m.wage_weekly_gbp for m in dept.members.values())
        registry.club_support[cid] = dept


def auto_extend_ai_staff(world, on_date: date, *, managed_club_id: str | None) -> int:
    """Avoid empty AI departments in long careers; never renew manager contracts.

    Called at the financial month boundary, while the world is in a transaction.
    Both the AI renewal and its rollback are deterministic.
    """
    registry = world.football_world
    if registry is None:
        return 0
    journal = world._active_journal
    if journal is None:
        raise RuntimeError('AI staff renewal requires a world transaction')
    renewed = 0
    for club_id, department in registry.club_support.items():
        if club_id == managed_club_id:
            continue
        for ident, member in tuple(department.members.items()):
            if (member.contract_until - on_date).days > 35:
                continue
            original = member
            journal.undo_callbacks.setdefault(
                ('ts26-staff-renew', club_id, ident),
                lambda target=department, key=ident, old=original: target.members.__setitem__(key, old))
            department.members[ident] = replace(member,
                contract_until=max(on_date, member.contract_until) + timedelta(days=730))
            renewed += 1
    return renewed


def active_staff(dept: ClubSupport, role: str, day: date) -> list[StaffMember]:
    return [item for item in dept.members.values() if item.role == role and item.contract_until >= day]


def department_bonus(dept: ClubSupport | None, role: str, day: date) -> float:
    """At most a few points of development / 8% of physical or medical recovery."""
    if dept is None:
        return 0.0
    staff = active_staff(dept, role, day)
    if not staff:
        return 0.0
    scores = sorted((m.quality for m in staff), reverse=True)
    quality = (scores[0] - 55) / 45.0
    coverage = sum(.34 / (i + 1) for i in range(1, len(scores)))
    return max(-.15, min(1.0, quality * .65 + coverage))


def training_group(session, player_id: str) -> str:
    if any(e.player.id == player_id for e in session.home_lineup.starters):
        return 'starters'
    if any(p.id == player_id for p in session.home_lineup.bench):
        return 'bench'
    return 'rest'


def effective_intensity(policy: TrainingPolicy, group: str, condition: float, fatigue: float,
                        days_to_match: int | None) -> str:
    policy.validate()
    mode = getattr(policy, group)
    if mode == 'auto':
        mode = ('light' if condition < 76 or fatigue > 50 or
                (days_to_match is not None and days_to_match <= 2)
                else 'intense' if group == 'rest' and condition > 90 and fatigue < 20
                and (days_to_match is None or days_to_match > 4)
                else 'balanced')
    if policy.protection:
        if condition < policy.low_condition:
            mode = 'light'
        elif condition < policy.medium_condition and mode == 'intense':
            mode = 'balanced'
    return mode


# Small training penalties/rewards are applied to the existing daily recovery.
# No added workload counter that penalizes the same player twice in the engine.
DAILY_CHANGE = {'light': (.4, -.25, -1.25),
                'balanced': (-.25, .15, 0.0),
                'intense': (-1.1, .8, 1.75)}


def recover_managed_players(session, *, days: int, start_date: date | None = None) -> None:
    """Use the same 1-day recovery as the legacy game, then a small TS-26 delta.

    No change when called with 0 days; one day repeated equals a multi-day skip.
    Updates a bounded monthly *actual training* ledger for player development.
    """
    if days < 0 or days > 370:
        raise ValueError('invalid training time interval')
    dept = session._world_squads.club_support.get(session.home_club.id)
    if dept is None:
        for player in session.home_club.squad.players:
            recover_player_between_matches(player, days=days)
        return
    first = start_date if start_date is not None else session.current_date
    # The current fixture is selected once before moving to the next date.
    from football_manager.ui_shell.progression import pending_managed_match
    upcoming = pending_managed_match(session)
    target_match = upcoming.match_date if upcoming is not None else None
    physio = department_bonus(dept, 'fitness', first)
    for index in range(days):
        day = first + timedelta(days=index + 1)
        till = max(0, (target_match - day).days) if target_match is not None and target_match >= day else None
        for player in session.home_club.squad.players:
            if player.state.injury:
                recover_player_between_matches(player, days=1)
                continue
            group = training_group(session, player.id)
            mode = effective_intensity(dept.training, group, player.state.condition, player.state.fatigue, till)
            before = player.state.condition
            fatigue = player.state.fatigue
            recover_player_between_matches(player, days=1)
            recovered = max(0., player.state.condition - before)
            # Relative boost, never a free direct increase to 100% each day.
            player.state.fitness = min(100., max(0., player.state.condition + recovered * (.075 * physio)))
            player.state.fatigue = max(0., min(100., player.state.fatigue - max(0., fatigue - player.state.fatigue) * (.075 * physio)))
            condition_shift, fatigue_shift, growth = DAILY_CHANGE[mode]
            player.state.fitness = round(min(100., max(0., player.state.condition + condition_shift)), 1)
            player.state.fatigue = round(min(100., max(0., player.state.fatigue + fatigue_shift)), 1)
            value, count = dept.training_days.get(player.id, (0., 0))
            dept.training_days[player.id] = (value + growth, count + 1)


def _candidate(registry, cid: str, role: str, index: int, year: int, on_date: date) -> StaffMember:
    code = _seed_value('staff-market-v1', registry.seed, cid, role, index, year)
    tier = registry.identities[cid].initial_tier
    quality = 48 + code % 40
    name = NAMES[(code // 3) % len(NAMES)]
    ident = f'candidate:{cid}:{role}:{year}:{index}'
    return StaffMember(ident, cid, name, role, quality, staff_wage(quality, tier),
                       on_date, on_date + timedelta(days=730))


def staff_read_model(session) -> dict:
    registry = session._world_squads
    cid, day = session.home_club.id, session.current_date
    dept = registry.club_support[cid]
    staff = []
    market = {}
    for role in ROLES:
        employees = active_staff(dept, role, day)
        staff.extend({'id': m.member_id, 'name': m.name, 'role': role, 'quality': m.quality,
                      'wage_weekly_gbp': m.wage_weekly_gbp, 'until': m.contract_until.isoformat()}
                     for m in employees)
        market[role] = [{'id': candidate.member_id, 'name': candidate.name,
                         'quality': candidate.quality, 'wage_weekly_gbp': candidate.wage_weekly_gbp,
                         'until': candidate.contract_until.isoformat()}
                        for i in range(3)
                        if (candidate := _candidate(registry, cid, role, i, day.year, day)).member_id not in dept.members]
    return {'date': day.isoformat(), 'capacity': dict(dept.capacity), 'capacity_source': dept.capacity_source,
            'members': staff, 'market': market,
            'weekly_payroll_gbp': sum(m['wage_weekly_gbp'] for m in staff),
            'bonuses': {role: round(department_bonus(dept, role, day), 3) for role in ROLES},
            'note': 'Staff effects are intentionally small. Capacity is provisional until club facilities exist.'}


def staff_command(session, command: dict) -> dict:
    day = session.current_date
    registry = session._world_squads
    dept = registry.club_support[session.home_club.id]
    action, ident = command.get('action'), command.get('member_id')
    if action == 'hire':
        candidate = next((candidate for role in ROLES for i in range(3)
                          if (candidate := _candidate(registry, dept.club_id, role, i, day.year, day)).member_id == ident), None)
        if candidate is None or ident in dept.members:
            raise ValueError('This candidate is no longer available')
        if len(active_staff(dept, candidate.role, day)) >= dept.capacity[candidate.role]:
            raise ValueError('The department has no free staff places')
        account = registry.club_finances[dept.club_id]
        if account.cash_gbp < candidate.wage_weekly_gbp * 8:
            raise ValueError('Club cash is insufficient for this staff contract')
        dept.members[ident] = candidate
        return {'hired': ident, 'name': candidate.name}
    if action == 'release':
        if ident not in dept.members:
            raise ValueError('Staff member not found')
        member = dept.members.pop(ident)
        # Small immediate settlement for an active commitment; no free resets.
        settlement = member.wage_weekly_gbp * 2 if member.contract_until >= day else 0
        account = registry.club_finances[dept.club_id]
        from dataclasses import replace as replace_account
        registry.club_finances[dept.club_id] = replace_account(account, cash_gbp=account.cash_gbp - settlement,
            transfer_budget_gbp=min(account.transfer_budget_gbp, max(0, account.cash_gbp - settlement)))
        return {'released': ident, 'settlement_gbp': settlement}
    if action == 'renew':
        member = dept.members.get(ident)
        if member is None:
            raise ValueError('Staff member not found')
        if member.contract_until < day:
            raise ValueError('Expired staff must be replaced')
        updated = replace(member, contract_until=max(day, member.contract_until) + timedelta(days=365),
                          wage_weekly_gbp=min(50_000, int(round(member.wage_weekly_gbp * 1.05 / 25) * 25)))
        dept.members[ident] = updated
        return {'renewed': ident, 'until': updated.contract_until.isoformat()}
    raise ValueError('Unsupported staff command')


def training_read_model(session) -> dict:
    dept = session._world_squads.club_support[session.home_club.id]
    from football_manager.ui_shell.progression import pending_managed_match
    fixture = pending_managed_match(session)
    till = (fixture.match_date - session.current_date).days if fixture else None
    players = []
    for player in session.home_club.squad.players:
        group = training_group(session, player.id)
        mode = effective_intensity(dept.training, group, player.state.condition, player.state.fatigue, till)
        score, count = dept.training_days.get(player.id, (0., 0))
        players.append({'id': player.id, 'name': player.full_name, 'group': group,
                        'condition': round(player.state.condition, 1), 'fatigue': round(player.state.fatigue, 1),
                        'effective': mode, 'individual_focus': player.development.focus if player.development else 'balanced',
                        'days_trained': count, 'injured': bool(player.state.injury)})
    policy = dept.training
    return {'date': session.current_date.isoformat(), 'policy': {group: getattr(policy, group) for group in GROUPS},
            'protection': policy.protection, 'low_condition': policy.low_condition,
            'medium_condition': policy.medium_condition, 'players': players,
            'next_match_days': till,
            'note': 'Group assignments reflect current selection. Training is applied during actual date progression.'}


def training_command(session, command: dict) -> dict:
    dept = session._world_squads.club_support[session.home_club.id]
    if command.get('action') != 'configure':
        raise ValueError('Unsupported training operation')
    group, intensity = command.get('group'), command.get('intensity')
    if group is not None:
        if group not in GROUPS or intensity not in INTENSITIES:
            raise ValueError('Invalid training group or intensity')
        setattr(dept.training, group, intensity)
    if 'protection' in command:
        if type(command['protection']) is not bool:
            raise ValueError('Physical protection must be enabled or disabled')
        dept.training.protection = command['protection']
    if 'low_condition' in command or 'medium_condition' in command:
        low = command.get('low_condition', dept.training.low_condition)
        medium = command.get('medium_condition', dept.training.medium_condition)
        if type(low) is not int or type(medium) is not int:
            raise ValueError('Protection thresholds must be integers')
        dept.training.low_condition, dept.training.medium_condition = low, medium
    dept.training.validate()
    return {'configured': True, 'policy': training_read_model(session)['policy']}


def treatment_preference(player) -> str:
    traits = player.personality
    if traits.injury_susceptibility >= 70 or traits.professionalism >= 83:
        return 'conservative'
    if traits.ambition >= 77 and traits.injury_susceptibility <= 58:
        return 'aggressive'
    return 'neutral'


def medical_read_model(session) -> dict:
    registry = session._world_squads
    dept = registry.club_support[session.home_club.id]
    cases = []
    for player in session.home_club.squad.players:
        episode = player.aging.active_injury if player.aging else None
        if episode is None:
            if player.state.injury:
                cases.append({'id': player.id, 'name': player.full_name, 'injury': player.state.injury,
                              'return_on': None, 'days_left': None, 'treatment_available': False})
            continue
        remaining = (episode.return_on - session.current_date).days if episode.return_on else None
        decision = dept.treatments.get(player.id)
        active = decision is not None and decision.episode_id == episode.episode_id
        preference = treatment_preference(player)
        bonus = department_bonus(dept, 'medic', session.current_date)
        base_risk = max(.09, min(.28, .15 + player.personality.injury_susceptibility * .0009 - .055 * bonus))
        cases.append({'id': player.id, 'name': player.full_name, 'injury': episode.label,
                      'return_on': episode.return_on.isoformat() if episode.return_on else None,
                      'days_left': max(0, remaining) if remaining is not None else None,
                      'preference': preference, 'treatment': decision.method if active else None,
                      'treatment_status': decision.status if active else None,
                      'treatment_available': remaining is not None and remaining >= 7 and not active,
                      'estimated_aggressive_risk_pct': round(100 * base_risk),
                      'caution': 'Earlier availability carries a chance of a longer setback.'})
    return {'date': session.current_date.isoformat(), 'cases': sorted(cases, key=lambda c: (c['days_left'] is None, -(c['days_left'] or 0))),
            'medical_bonus': round(department_bonus(dept, 'medic', session.current_date), 2),
            'medical_staff_count': len(active_staff(dept, 'medic', session.current_date)),
            'note': 'Treatments are offered for significant dated injuries, once per episode. Estimates are game probabilities.'}


def medical_command(session, command: dict) -> dict:
    if command.get('action') != 'treat' or command.get('method') not in ('conservative', 'aggressive'):
        raise ValueError('Unsupported medical treatment')
    registry = session._world_squads
    dept = registry.club_support[session.home_club.id]
    player_id = command.get('player_id')
    if not isinstance(player_id, str) or not session.home_club.squad.contains(player_id):
        raise ValueError('Player is not part of the managed first team')
    player = session.home_club.squad.get(player_id)
    episode = player.aging.active_injury if player.aging else None
    day = session.current_date
    if episode is None or episode.return_on is None or (episode.return_on - day).days < 7:
        raise ValueError('This injury does not require a treatment decision')
    if player_id in dept.treatments and dept.treatments[player_id].episode_id == episode.episode_id:
        raise ValueError('A treatment was already chosen for this injury')
    method = command['method']
    days = (episode.return_on - day).days
    bonus = department_bonus(dept, 'medic', day)
    if method == 'conservative':
        # Normal rehabilitation is the automatic safe default; deciding to
        # preserve it must never be worse than simply ignoring this screen.
        shift = 0
        risk = 0.0
    else:
        shift = -min(14, max(1, round(days * (.16 + .035 * max(0, bonus)))))
        risk = max(.09, min(.28, .15 + player.personality.injury_susceptibility * .0009 - .055 * bonus))
    due = day + timedelta(days=max(2, days + shift))
    if (due - episode.started_on).days > 730:
        raise ValueError('Treatment exceeds maximum supported recovery')
    rng = stable_random('ts26-treatment-v1', registry.seed, episode.episode_id, player_id, method)
    relapse = method == 'aggressive' and rng.random() < risk
    relapse_days = rng.randint(6, 20) if relapse else 0
    preference = treatment_preference(player)
    decision = MedicalDecision(player_id, episode.episode_id, method, day, episode.return_on,
                               due, risk, relapse, relapse_days, preference)
    decision.validate()
    player.aging = replace(player.aging, active_injury=replace(episode, return_on=due))
    registry.medical_followups[player_id] = (session.home_club.id, due)
    dept.treatments[player_id] = decision
    from football_manager.services.manager_inbox import _notice
    state = session.manager_inbox
    _notice(state, day, 'medical', f'Treatment plan: {player.full_name}',
            f'{method.capitalize()} rehabilitation selected. Estimated return: {due.isoformat()}. '
            f'Player preference: {preference}.',
            f'treatment:{episode.episode_id}:{method}', player_id=player_id)
    if preference != 'neutral':
        relation = state.relations.get(player_id)
        if relation is not None:
            relation.trust = min(100., max(35., relation.trust + (.35 if preference == method else -.75)))
        player.state.morale = min(100., max(1., player.state.morale + (.3 if preference == method else -.55)))
        if preference != method:
            _notice(state, day, 'conversations', f'{player.full_name} questions the treatment',
                    'The player preferred a different rehabilitation approach. The manager can discuss recovery in Inbox.',
                    f'treatment:opinion:{episode.episode_id}', player_id=player_id)
    return {'player_id': player_id, 'method': method, 'return_on': due.isoformat(),
            'estimated_risk_pct': round(100 * risk), 'player_preference': preference}
