"""TS-26 manager controls. Bounded influence, deterministic offers, no daily chores."""
from __future__ import annotations

from dataclasses import replace
from datetime import date, timedelta
from hashlib import sha256

from football_manager.domain.club_support import (
    ROLES, INTENSITIES, ClubSupport, StaffMember, MedicalDecision, TrainingPolicy,
)
from football_manager.domain.player_development import stable_random, FOCUSES
from football_manager.services.player_condition import recover_player_between_matches

NAMES = ('Alex Morgan', 'Jordan Reed', 'Sam Bennett', 'Robin Ellis', 'Taylor Walsh',
         'Jamie Cooper', 'Casey Clarke', 'Drew Foster', 'Charlie Brooks', 'Morgan Price',
         'Avery Hughes', 'Riley Parker', 'Blair Turner', 'Dylan Mason', 'Jesse Nolan')


def _seed_value(*items: object) -> int:
    return int.from_bytes(sha256('|'.join(map(str, items)).encode('utf-8')).digest()[:8], 'big')


def staff_capacity_for_tier(initial_tier: int) -> dict[str, int]:
    """Interim slots only; future club facilities can replace these numbers."""
    return {1: {'coach': 3, 'medic': 2, 'fitness': 2, 'scout': 3},
            2: {'coach': 2, 'medic': 2, 'fitness': 2, 'scout': 3},
            3: {'coach': 2, 'medic': 1, 'fitness': 2, 'scout': 2},
            4: {'coach': 1, 'medic': 1, 'fitness': 1, 'scout': 1},
            0: {'coach': 1, 'medic': 1, 'fitness': 1, 'scout': 1}}[initial_tier].copy()


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


def upgrade_club_support_scouts(registry, on_date: date) -> None:
    """TS-26 -> TS-26.1: add only missing professional scout slots/contract.

    Preserve all existing coaches, treatment decisions, training and staff costs.
    The initial scout is included in the old operating-cost proxy, just like
    the initial TS-26 employees; extra hired scouts cost additional wages.
    """
    for cid, dept in registry.club_support.items():
        if 'scout' in dept.capacity:
            continue
        tier = registry.identities[cid].initial_tier
        dept.capacity['scout'] = staff_capacity_for_tier(tier)['scout']
        code = _seed_value(registry.seed, cid, 'scout', 'starter')
        quality = 48 + code % 28
        member = StaffMember(f'staff:{cid}:scout:starter', cid, NAMES[code % len(NAMES)],
                             'scout', quality, staff_wage(quality, tier), on_date,
                             on_date + timedelta(days=730))
        dept.members[member.member_id] = member
        dept.baseline_weekly_gbp += member.wage_weekly_gbp


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


def _auto_training_profile(policy: TrainingPolicy, condition: float,
                           fatigue: float, days_to_match: int | None,
                           sharpness: float | None) -> tuple[str, str]:
    """Single automatic plan, independent of the selected XI or substitutes.

    Recovery/energy thresholds win when sharpness and condition both call for
    adjustments. Near a match, never schedule the maximum-performance workout.
    """
    if condition < policy.energy_max:
        return 'light', 'energy_max'
    if condition < policy.energy_focus:
        return 'balanced', 'energy_focus'
    if sharpness is not None:
        if sharpness < policy.performance_max and (days_to_match is None or days_to_match > 2):
            return 'intense', 'performance_max'
        if sharpness < policy.performance_focus:
            return 'balanced', 'performance_focus'
    if condition < 76 or fatigue > 50 or (days_to_match is not None and days_to_match <= 2):
        return 'light', 'match_or_fatigue'
    return 'balanced', 'balanced'


def effective_intensity(policy: TrainingPolicy, condition: float, fatigue: float,
                        days_to_match: int | None, *, player_id: str | None = None,
                        sharpness: float | None = None) -> str:
    """Personal workload > shared automatic plan; injured players skip training.

    The removed group policy and removed safety override cannot silently
    override a player's manual selection. Automatic still recovers low-energy
    players before choosing performance intensity.
    """
    policy.validate()
    specific = policy.individual_intensities.get(player_id) if player_id else None
    if specific is not None and specific != 'auto':
        return specific
    return _auto_training_profile(policy, condition, fatigue, days_to_match, sharpness)[0]


def _ordered_training_thresholds(policy: TrainingPolicy, updates: dict, changed: str | None) -> dict[str, int]:
    """Push the adjacent boundary automatically rather than crossing ranges.

    The edited handle wins whenever feasible. Both server and browser apply
    this rule so hand-crafted API calls cannot persist overlapping bands.
    """
    keys = ('performance_max', 'performance_focus', 'energy_max', 'energy_focus')
    if not isinstance(updates, dict) or not updates or set(updates) - set(keys):
        raise ValueError('invalid automatic training thresholds')
    if changed is not None and (changed not in keys or changed not in updates):
        raise ValueError('invalid edited threshold')
    if any(type(v) is not int or not 0 <= v <= 100 for v in updates.values()):
        raise ValueError('automatic training thresholds must be whole numbers from 0 to 100')
    values = {key: getattr(policy, key) for key in keys}
    values.update(updates)
    for low, high in (('performance_max', 'performance_focus'), ('energy_max', 'energy_focus')):
        if values[low] < values[high]:
            continue
        if changed == high:
            values[high] = max(1, values[high])
            values[low] = values[high] - 1
        else:
            values[low] = min(99, values[low])
            values[high] = values[low] + 1
    return values


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
            mode = effective_intensity(dept.training, player.state.condition, player.state.fatigue,
                                       till, player_id=player.id, sharpness=player.state.match_sharpness)
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
    # Unique names within each current role market; stable under refresh.
    name = NAMES[(_seed_value('staff-name', registry.seed, cid, role, year) + index) % len(NAMES)]
    ident = f'candidate:{cid}:{role}:{year}:{index}'
    return StaffMember(ident, cid, name, role, quality, staff_wage(quality, tier),
                       on_date, on_date + timedelta(days=730))


STAFF_MARKET_SIZE = 8
STAFF_CONTRACT_YEARS = (1, 2, 3, 4)


def _staff_target_wage(registry, member: StaffMember, *, existing: bool, day: date) -> int:
    """Reproducible expectations. Extensions demand more than the old salary.

    Never expose the exact private acceptance threshold to the browser.
    Quoted demand is visible and reproducible across saves and refreshes.
    """
    if not existing:
        return member.wage_weekly_gbp
    premium = 1.08 + max(0, member.quality - 70) / 400
    if (member.contract_until - day).days < 120:
        premium += .04
    return min(50_000, max(100, int(round(member.wage_weekly_gbp * premium / 25) * 25)))


def _staff_market(registry, cid: str, role: str, day: date) -> list[StaffMember]:
    return [candidate for idx in range(STAFF_MARKET_SIZE)
            if (candidate := _candidate(registry, cid, role, idx, day.year, day)).member_id
                not in registry.club_support[cid].members]


def _staff_terms(registry, employee: StaffMember, *, existing: bool, day: date) -> dict:
    demand = _staff_target_wage(registry, employee, existing=existing, day=day)
    return {'id': employee.member_id, 'name': employee.name, 'role': employee.role,
            'quality': employee.quality, 'wage_weekly_gbp': employee.wage_weekly_gbp,
            'wage_demand_weekly_gbp': demand, 'preferred_years': 2,
            'until': employee.contract_until.isoformat()}


def staff_read_model(session) -> dict:
    registry = session._world_squads
    cid, day = session.home_club.id, session.current_date
    dept = registry.club_support[cid]
    staff = []
    market = {}
    for role in ROLES:
        employees = active_staff(dept, role, day)
        staff.extend(_staff_terms(registry, employee, existing=True, day=day)
                     for employee in employees)
        market[role] = [_staff_terms(registry, candidate, existing=False, day=day)
                        for candidate in _staff_market(registry, cid, role, day)]
    account = registry.club_finances[cid]
    weekly = sum(m['wage_weekly_gbp'] for m in staff)
    return {'club_id': cid, 'club': session.home_club.name, 'date': day.isoformat(),
            'capacity': dict(dept.capacity), 'capacity_source': dept.capacity_source,
            'members': staff, 'market': market, 'weekly_payroll_gbp': weekly,
            'cash_gbp': account.cash_gbp,
            'bonuses': {role: round(department_bonus(dept, role, day), 3) for role in ROLES},
            'note': 'Staff improvements influence the real training, medical and scouting calculations. Contract offers alter club finances.'}


def _staff_acceptance_threshold(registry, member: StaffMember, target: int,
                                years: int, day: date) -> int:
    """Deterministic individual expectations, adjusted for long-term security.

    The bonus counts at a capped fraction, so wages remain the main component.
    """
    variation = _seed_value('staff-expectation-v2', registry.seed, member.member_id) % 13
    ratio = .93 + variation / 100 - min(3, years - 1) * .012
    return max(100, int(round(target * ratio / 25) * 25))


def staff_command(session, command: dict) -> dict:
    day = session.current_date
    registry = session._world_squads
    dept = registry.club_support[session.home_club.id]
    action, ident = command.get('action'), command.get('member_id')
    if action in ('hire', 'renew'):
        # Retired immediate actions are not an alternative API bypass.
        raise ValueError('Staff appointments and extensions require a negotiated contract offer')
    if action == 'offer':
        if set(command) != {'action','member_id','weekly_wage_gbp','years','signing_bonus_gbp'}:
            raise ValueError('Offer must include salary, term and signing bonus')
        wage, years, bonus = (command['weekly_wage_gbp'], command['years'], command['signing_bonus_gbp'])
        if (type(wage) is not int or type(years) is not int or type(bonus) is not int
                or wage < 100 or wage > 50_000 or years not in STAFF_CONTRACT_YEARS
                or bonus < 0 or bonus > 200_000):
            raise ValueError('Invalid staff contract offer')
        current = dept.members.get(ident)
        existing = current is not None and current.contract_until >= day
        if current is not None and not existing:
            raise ValueError('Expired staff must be recruited through the market')
        member = (current if existing else next((candidate for role in ROLES
                  for candidate in _staff_market(registry, dept.club_id, role, day)
                  if candidate.member_id == ident), None))
        if member is None:
            raise ValueError('This staff candidate is no longer available')
        if not existing and len(active_staff(dept, member.role, day)) >= dept.capacity[member.role]:
            raise ValueError('The department has no free staff places')
        account = registry.club_finances[dept.club_id]
        # Two months of staff salary reserve, plus any up-front commitment.
        if account.cash_gbp < bonus + wage * 8:
            raise ValueError('Club cash is insufficient for this staff contract')
        demand = _staff_target_wage(registry, member, existing=existing, day=day)
        minimum = _staff_acceptance_threshold(registry, member, demand, years, day)
        bonus_credit = min(bonus / max(1, years * 26), wage * .15)
        if wage + bonus_credit < minimum:
            counter = max(100, min(50_000, int(round((minimum - bonus_credit + 24) / 25) * 25)))
            return {'accepted': False, 'member_id': ident, 'name': member.name,
                    'counter_wage_weekly_gbp': counter,
                    'message': 'The offer was declined. The candidate is seeking improved terms.'}
        end = (max(day, member.contract_until) + timedelta(days=365 * years)
               if existing else day + timedelta(days=365 * years))
        updated = replace(member, wage_weekly_gbp=wage,
                          hired_on=member.hired_on if existing else day, contract_until=end)
        updated.validate()
        # Atomic application: validate everything before changing cash/member.
        if bonus:
            from dataclasses import replace as replace_account
            new_cash = account.cash_gbp - bonus
            registry.club_finances[dept.club_id] = replace_account(account,
                cash_gbp=new_cash, transfer_budget_gbp=min(account.transfer_budget_gbp,max(0,new_cash)))
        dept.members[ident] = updated
        if member.role == 'scout' and not existing:
            from football_manager.services.professional_scouting import _rebalance
            _rebalance(dept, day)
        return {'accepted': True, 'member_id': ident, 'name': member.name,
                'kind': 'extension' if existing else 'appointment',
                'weekly_wage_gbp': wage, 'signing_bonus_paid_gbp': bonus,
                'until': updated.contract_until.isoformat(),
                'message': 'Contract agreed. The weekly wage is now included in the club finances.'}
    if action == 'release':
        if set(command) != {'action', 'member_id'}:
            raise ValueError('Invalid release command')
        if ident not in dept.members:
            raise ValueError('Staff member not found')
        member = dept.members.pop(ident)
        settlement = member.wage_weekly_gbp * 2 if member.contract_until >= day else 0
        account = registry.club_finances[dept.club_id]
        from dataclasses import replace as replace_account
        registry.club_finances[dept.club_id] = replace_account(account,
            cash_gbp=account.cash_gbp - settlement,
            transfer_budget_gbp=min(account.transfer_budget_gbp, max(0, account.cash_gbp - settlement)))
        if member.role == 'scout':
            from football_manager.services.professional_scouting import _rebalance
            _rebalance(dept, day)
        return {'released': ident, 'settlement_gbp': settlement}
    raise ValueError('Unsupported staff command')

def training_read_model(session) -> dict:
    dept = session._world_squads.club_support[session.home_club.id]
    from football_manager.ui_shell.progression import pending_managed_match
    fixture = pending_managed_match(session)
    till = (fixture.match_date - session.current_date).days if fixture else None
    players = []
    for player in session.home_club.squad.players:
        mode = effective_intensity(dept.training, player.state.condition, player.state.fatigue,
                                   till, player_id=player.id, sharpness=player.state.match_sharpness)
        _score, count = dept.training_days.get(player.id, (0., 0))
        specific = dept.training.individual_intensities.get(player.id)
        automatic = specific is None or specific == 'auto'
        plan = (_auto_training_profile(dept.training, player.state.condition,
                 player.state.fatigue, till, player.state.match_sharpness)[1] if automatic else None)
        players.append({'id': player.id, 'name': player.full_name,
                        'position': player.primary_position.value,
                        'condition': round(player.state.condition, 1),
                        'sharpness': round(player.state.match_sharpness, 1),
                        'fatigue': round(player.state.fatigue, 1),
                        'effective': mode, 'individual_intensity': specific,
                        'focus_editable': bool(player.development),
                        'intensity_source': 'individual' if specific is not None else 'automatic',
                        'automatic_plan': plan,
                        'individual_focus': player.development.focus if player.development else 'balanced',
                        'days_trained': count, 'injured': bool(player.state.injury)})
    policy = dept.training
    # TS-UI-04.01: actual active staff contracts, not presentation estimates.
    staff_counts = {role: len(active_staff(dept, role, session.current_date))
                    for role in ('coach', 'fitness')}
    return {'club_id': session.home_club.id, 'club': session.home_club.name,
            'date': session.current_date.isoformat(),
            'training_staff': {'coaches': staff_counts['coach'],
                               'fitness': staff_counts['fitness'],
                               'total': sum(staff_counts.values()),
                               'capacity': dept.capacity['coach'] + dept.capacity['fitness']},
            'focus_options': list(FOCUSES),
            'auto_thresholds': {key: getattr(policy, key) for key in
                                ('performance_max', 'performance_focus', 'energy_max', 'energy_focus')},
            'individual_override_count': sum(p['individual_intensity'] is not None for p in players),
            'players': players, 'next_match_days': till,
            'note': 'One automatic workload plan for every player unless an individual exception is saved. Actual training is applied during date progression.'}


def training_command(session, command: dict) -> dict:
    dept = session._world_squads.club_support[session.home_club.id]
    action = command.get('action')
    # Validate a replacement first; rejected commands leave career state intact.
    policy = replace(dept.training, individual_intensities={pid: mode for pid, mode in
                     dept.training.individual_intensities.items() if session.home_club.squad.contains(pid)})
    if action == 'individual':
        if set(command) - {'action', 'player_id', 'intensity'}:
            raise ValueError('invalid training command fields')
        player_id = command.get('player_id')
        choice = command.get('intensity')
        if (not isinstance(player_id, str) or not session.home_club.squad.contains(player_id)
                or choice not in (*INTENSITIES, 'default')):
            raise ValueError('invalid managed-player training override')
        if choice == 'default':
            policy.individual_intensities.pop(player_id, None)
        else:
            policy.individual_intensities[player_id] = choice
    elif action == 'configure':
        if set(command) - {'action', 'auto_thresholds', 'changed_field'} or 'auto_thresholds' not in command:
            raise ValueError('Only automatic thresholds can be configured')
        thresholds = _ordered_training_thresholds(policy, command['auto_thresholds'],
                                                   command.get('changed_field'))
        for key, value in thresholds.items():
            setattr(policy, key, value)
    else:
        raise ValueError('Unsupported training operation')
    policy.validate()
    dept.training = policy
    model = training_read_model(session)
    return {'configured': True, 'auto_thresholds': model['auto_thresholds'],
            'individual_override_count': model['individual_override_count']}


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
    players = session.home_club.squad.players
    # Counts/conditions come from the same live squad used by Training and Squad.
    # Never extrapolate injuries or invent an injury-risk forecast.
    conditions = [max(0., min(100., float(player.state.condition))) for player in players]
    current_ids = {player.id: player.full_name for player in players}
    decisions = sorted((decision for pid, decision in dept.treatments.items()
                        if pid in current_ids), key=lambda decision: decision.decided_on, reverse=True)
    staff_count = {role: len(active_staff(dept, role, session.current_date))
                   for role in ('medic', 'fitness')}
    return {'club_id': session.home_club.id, 'club': session.home_club.name,
            'date': session.current_date.isoformat(),
            'squad_size': len(players), 'available_count': len(players) - len(cases),
            'average_condition': round(sum(conditions) / len(conditions), 1) if conditions else None,
            'condition_bands': {'high': sum(x >= 90 for x in conditions),
                                'medium': sum(75 <= x < 90 for x in conditions),
                                'low': sum(x < 75 for x in conditions)},
            'staffing': {'medical': staff_count['medic'], 'medical_capacity': dept.capacity['medic'],
                         'fitness': staff_count['fitness'], 'fitness_capacity': dept.capacity['fitness']},
            'recent_treatments': [
                {'player_id': d.player_id, 'player': current_ids[d.player_id],
                 'decided_on': d.decided_on.isoformat(), 'method': d.method,
                 'planned_return': d.planned_return.isoformat(), 'status': d.status}
                for d in decisions[:8]],
            'cases': sorted(cases, key=lambda c: (c['days_left'] is None, -(c['days_left'] or 0))),
            'medical_bonus': round(department_bonus(dept, 'medic', session.current_date), 2),
            'medical_staff_count': staff_count['medic'],
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
