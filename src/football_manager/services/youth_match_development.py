"""TS-FIX-01: chronological academy games, rotation and real exposure.

Youth remains a lightweight match model, not a disguised senior simulation.
All mutations join the world journal; read models never advance this clock.
Histories are capped at 28 days and no historical appearances are invented.
"""
from __future__ import annotations

from datetime import date, timedelta
from dataclasses import replace
from random import Random

from football_manager.data.english_players import stable_seed
from football_manager.domain.conditioning import match_condition_state, recover_condition_state
from football_manager.domain.enums import Position
from football_manager.domain.match_rhythm import after_match, after_inactivity
from football_manager.domain.player_development import add_match_exposure, reference_overall
from football_manager.domain.roles import default_role_for_position

POSITIONS = (Position.GK, Position.RB, Position.RCB, Position.LCB, Position.LB,
             Position.DM, Position.RCM, Position.LCM, Position.RW, Position.ST, Position.LW)
HISTORY_DAYS = 28


def _checkpoint(world, player):
    journal = world._active_journal
    if journal is None:
        raise RuntimeError('academy progression requires a world transaction')
    key = ('youth-state', player.id)
    if key not in journal.undo_callbacks:
        old = (player.development, player.aging, player.state.fitness, player.state.fatigue,
               player.state.match_sharpness, player.state.injury)
        def undo():
            (player.development, player.aging, player.state.fitness, player.state.fatigue,
             player.state.match_sharpness, player.state.injury) = old
        journal.undo_callbacks[key] = undo


def record_participation(world, player_id: str, on_date: date, minutes: int):
    """One genuine appearance per calendar day, including senior appearances."""
    youth = world.football_world.youth
    if youth is None or minutes <= 0:
        return
    history = youth.recent_participation.get(player_id, ())
    if any(day == on_date for day, _ in history):
        raise ValueError('Player already participated on this date; review the match squad')
    if history and history[-1][0] > on_date:
        raise ValueError('Player participation cannot move backwards in time')
    keep = tuple((day, played) for day, played in history
                 if day >= on_date - timedelta(days=HISTORY_DAYS))
    world._put(youth.recent_participation, player_id, (*keep, (on_date, minutes)))
    world._put(youth.state_dates, player_id, on_date)


def _eligible(academy, level, on_date, youth):
    season_start = date(on_date.year if on_date.month >= 8 else on_date.year - 1, 8, 1)
    result = []
    for player in getattr(academy, level).values():
        history = youth.recent_participation.get(player.id, ()) if youth else ()
        if (player.age_on(season_start) > (17 if level == 'u17' else 21)
                or not player.state.is_available or player.state.condition < 45
                or (player.development and player.development.started_on > on_date)
                or any(day == on_date for day, _ in history)):
            continue
        # A full appearance yesterday is a real workload, even after a move
        # from the first team or another academy category.
        if sum(minutes for day, minutes in history if 0 <= (on_date - day).days <= 2) > 110:
            continue
        result.append(player)
    return result


def _selection_value(player, position, on_date, youth, overall):
    history = youth.recent_participation.get(player.id, ()) if youth else ()
    recent = sum(minutes for day, minutes in history if 0 <= (on_date - day).days <= 14)
    last = max((day for day, _ in history if day < on_date), default=None)
    rest = min(14, (on_date - last).days) if last else 14
    return (overall[player.id] * .70 + player.familiarity_for(position) * .24
            + player.state.condition * .10 - recent * .045 + rest * .30)


def select_youth_team(academy, level, on_date, youth=None):
    available = _eligible(academy, level, on_date, youth)
    if len(available) < 11 or not any(p.primary_position is Position.GK for p in available):
        return ()
    overall = {p.id: reference_overall(p) for p in available}
    selected = []
    for position in POSITIONS:
        suitable = [p for p in available
                    if (p.primary_position is Position.GK) == (position is Position.GK)]
        if not suitable:
            return ()
        player = max(suitable, key=lambda p: (_selection_value(p, position, on_date, youth, overall), p.id))
        selected.append(player)
        available.remove(player)
    return tuple(selected)


def _recover_rosters(world, youth, through):
    registry = world.football_world
    for club_id, academy in youth.academies.items():
        environment = registry.development_environments[club_id]
        for player in (*academy.u17.values(), *academy.u21.values()):
            initial = max(youth.match_clock or youth.last_processed,
                          player.development.started_on if player.development else youth.last_processed)
            previous = youth.state_dates.get(player.id, initial)
            days = (through - previous).days
            if days <= 0:
                continue
            _checkpoint(world, player)
            episode = player.aging.active_injury if player.aging else None
            injured_days = days if player.state.injury else 0
            if episode and episode.return_on is not None:
                injured_days = max(0, min(days, (episode.return_on - previous).days))
            value = after_inactivity(player.state.match_sharpness, injured_days,
                                     training_quality=environment.training_quality, injured=True)
            player.state.match_sharpness = after_inactivity(value, days - injured_days,
                                     training_quality=environment.training_quality, injured=False)
            # Round at each calendar day, just like day-by-day advancement;
            # skipping a week must not change which players are considered fit.
            for _ in range(days):
                physical = recover_condition_state(condition=player.state.condition,
                    fatigue=player.state.fatigue, stamina=player.attributes.physical.stamina,
                    natural_fitness=player.attributes.physical.natural_fitness, days=1)
                player.state.fitness, player.state.fatigue = physical.condition, physical.fatigue
                if physical.condition == 100. and physical.fatigue == 0.:
                    break
            # Close a dated youth absence without a retrospective appearance.
            # Attribute/ageing reviews remain with the existing monthly engine.
            if episode and episode.return_on is not None and episode.return_on <= through:
                from football_manager.domain.player_aging import MAX_MEDICAL_HISTORY
                player.aging = replace(player.aging, active_injury=None,
                    medical_history=(*player.aging.medical_history, episode)[-MAX_MEDICAL_HISTORY:])
                if player.state.injury == episode.label:
                    player.state.injury = None
            world._put(youth.state_dates, player.id, through)


def _participation_plan(team, academy, level, on_date, youth, seed):
    """Conserve 11 x 90 minutes; keep a goalkeeper and avoid unsuitable subs."""
    used = {p.id for p in team}
    bench = [p for p in _eligible(academy, level, on_date, youth)
             if p.id not in used and p.primary_position is not Position.GK]
    overall = {p.id: reference_overall(p) for p in (*team, *bench)}
    active = list(team)
    minutes = {p.id: 90 for p in team}
    players = {p.id: p for p in team}
    positions = {p.id: position for p, position in zip(team, POSITIONS)}
    # Five replacements in three stoppages, only if suitable players exist.
    for index, minute in enumerate((55, 65, 65, 75, 75)):
        candidates = []
        for slot, (outgoing, position) in enumerate(zip(active, POSITIONS)):
            if position is Position.GK or outgoing.id not in used:
                continue
            for incoming in bench:
                familiarity = incoming.familiarity_for(position)
                if familiarity < 55:
                    continue
                quality_gap = overall[incoming.id] - overall[outgoing.id]
                if quality_gap < -22 and outgoing.state.condition >= 75:
                    continue
                prior = sum(m for day, m in youth.recent_participation.get(incoming.id, ())
                            if 0 <= (on_date - day).days <= 14)
                value = familiarity * .15 + quality_gap * .4 - prior * .035
                value += (100 - outgoing.state.condition) * .15
                value += stable_seed(seed, incoming.id, outgoing.id, index) % 100 / 1000
                candidates.append((value, incoming.id, slot, outgoing, incoming, position))
        if not candidates:
            break
        _, _, slot, outgoing, incoming, position = max(candidates, key=lambda row: (row[0], row[1], row[2]))
        minutes[outgoing.id] = minute
        minutes[incoming.id] = 90 - minute
        players[incoming.id] = incoming
        positions[incoming.id] = position
        active[slot] = incoming
        bench.remove(incoming)
        used.remove(outgoing.id)  # Replacements cannot themselves be replaced here.
    assert sum(minutes.values()) == 990
    return tuple((players[pid], played, positions[pid]) for pid, played in minutes.items())


def advance_youth_matches(world, through: date) -> tuple[int, int]:
    """Play due fixtures before ``through``, exactly once, in date/ID order."""
    registry = world.football_world
    youth = registry.youth if registry else None
    if youth is None:
        return 0, 0
    clock = youth.match_clock or youth.last_processed
    if through <= clock:
        return 0, 0
    journal = world._active_journal
    if journal is None:
        raise RuntimeError('academy progression requires a world transaction')
    previous = youth.match_clock
    journal.undo_callbacks.setdefault(('youth-match-clock', id(youth)),
                                       lambda: setattr(youth, 'match_clock', previous))
    fixtures = sorted((f for f in youth.fixtures.values()
                       if f.home_goals is None and clock <= f.match_date < through),
                      key=lambda f: (f.match_date, f.fixture_id))
    matches, appearances = 0, 0
    recovery_date = None
    for fixture in fixtures:
        if recovery_date != fixture.match_date:
            _recover_rosters(world, youth, fixture.match_date)
            recovery_date = fixture.match_date
        home, away = youth.academies.get(fixture.home_club_id), youth.academies.get(fixture.away_club_id)
        if home is None or away is None:
            continue
        first = select_youth_team(home, fixture.level, fixture.match_date, youth)
        second = select_youth_team(away, fixture.level, fixture.match_date, youth)
        if not first or not second:
            continue  # No fabricated match or phantom minutes for a missing XI.
        plans = [_participation_plan(team, academy, fixture.level, fixture.match_date, youth,
                                    stable_seed(registry.seed, fixture.fixture_id, academy.club_id))
                 for team, academy in ((first, home), (second, away))]
        strength = [sum(reference_overall(p) * minutes for p, minutes, _ in plan) / 990 for plan in plans]
        difference = (strength[0] - strength[1]) / 20
        rng = Random(stable_seed(23, registry.seed, fixture.fixture_id, 'result'))
        goals = (max(0, min(7, round(rng.gauss(1.4 + difference * .6, 1.0)))),
                 max(0, min(7, round(rng.gauss(1.15 - difference * .6, 1.0)))))
        old = fixture.home_goals, fixture.away_goals
        journal.undo_callbacks.setdefault(('youth-fixture', fixture.fixture_id),
            lambda obj=fixture, prior=old: (setattr(obj, 'home_goals', prior[0]), setattr(obj, 'away_goals', prior[1])))
        fixture.home_goals, fixture.away_goals = goals
        matches += 1
        for plan, scored in zip(plans, goals):
            for player, minutes, position in plan:
                _checkpoint(world, player)
                role = default_role_for_position(position).role_id
                challenge = .70 if fixture.level == 'u17' else .83
                rating = max(3., min(9.5, 6.3 + rng.uniform(-.7, .7) + .08 * scored))
                player.development = add_match_exposure(player, minutes=minutes, rating=rating,
                    role_minutes={role: minutes}, challenge=challenge)
                player.state.match_sharpness = after_match(player.state.match_sharpness, minutes,
                                                          rate=.18 * challenge)
                physical = match_condition_state(starting_condition=player.state.condition,
                    starting_fatigue=player.state.fatigue, stamina=player.attributes.physical.stamina,
                    minutes=minutes, workload_factor=(.35 if position is Position.GK else challenge))
                player.state.fitness, player.state.fatigue = physical.condition, physical.fatigue
                record_participation(world, player.id, fixture.match_date, minutes)
                appearances += 1
    _recover_rosters(world, youth, through)
    # Prune immutable histories and clocks of released/retired players. The
    # active professional/youth registry is bounded; saves cannot grow per game.
    oldest = through - timedelta(days=HISTORY_DAYS)
    for player_id, history in tuple(youth.recent_participation.items()):
        recent = tuple((day, minutes) for day, minutes in history if day >= oldest)
        if recent != history:
            world._put(youth.recent_participation, player_id, recent)
    if through.month != clock.month:
        active = {p.id for club in registry.clubs.values() for p in club.squad.players}
        active.update(p.id for a in youth.academies.values() for p in (*a.u17.values(), *a.u21.values()))
        for mapping in (youth.recent_participation, youth.state_dates):
            for player_id in tuple(mapping):
                if player_id not in active:
                    previous_value = mapping.pop(player_id)
                    journal.undo_callbacks.setdefault(('youth-prune', id(mapping), player_id),
                        lambda m=mapping, pid=player_id, old=previous_value: m.__setitem__(pid, old))
    youth.match_clock = through
    return matches, appearances
