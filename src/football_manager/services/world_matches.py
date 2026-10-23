"""Run registered English clubs through the same fast simulator as the manager.

Results and participation commit together. Fixtures without professional English
clubs keep the old external-world resolver, outside the TS-21.1 data scope.
"""
from __future__ import annotations

from football_manager.data.english_players import generate_club, stable_seed
from football_manager.domain.football_world import PlayerSeasonUsage
from football_manager.domain.enums import Position
from football_manager.domain.lineup import LineupEntry, MatchLineup
from football_manager.domain.match_context import (
    CompetitionContextSnapshot, CupTieContextSnapshot, MatchDecider,
    MatchContextSnapshot, StadiumSnapshot, SurfaceType, MatchConditionsSnapshot,
    WeatherSnapshot, WeatherType, RefereeSnapshot, MatchKitSelectionSnapshot,
    KitSnapshot, KitType,
)
from football_manager.fast_simulation import FastMatchSimulator
from football_manager.services.managed_match_transaction import capture_player_state, restore_player_state
from football_manager.services.match_snapshot_builder import build_match_snapshot
from football_manager.services.player_condition import set_post_match_condition
from football_manager.services.player_match_progression import apply_player_match_progression
from football_manager.services.world_squads import select_team, recover_world_club


def competition_context(world, fixture_id: str) -> CompetitionContextSnapshot:
    f = world.fixtures[fixture_id]
    if f.competition_id in world.leagues:
        edition = world.leagues[f.competition_id]
        return edition.context_snapshot(f.stage_id)
    competition = world.cups.get(f.competition_id) or world.staged[f.competition_id]
    if f.competition_id in world.staged and f.stage_id == competition.primary_stage_id:
        return CompetitionContextSnapshot(
            f.competition_id, competition.name, world.season_label, f.stage_id,
            match_decider=(MatchDecider.PENALTIES_AFTER_90 if competition.kind == 'efl-trophy'
                           else MatchDecider.DRAW_ALLOWED),
        )
    plan = competition.plan_for_fixture(fixture_id)
    tie = plan.tie_for_fixture(fixture_id)
    home_before = away_before = 0
    for prior in tie.fixtures:
        if prior.leg_number >= f.leg_number:
            continue
        record = world.results[prior.fixture_id]
        if prior.home_club_id == f.home_club_id:
            home_before += record.home_goals; away_before += record.away_goals
        else:
            home_before += record.away_goals; away_before += record.home_goals
    return CompetitionContextSnapshot(
        f.competition_id, competition.name, world.season_label, plan.definition.name,
        cup_tie=CupTieContextSnapshot(plan.definition.name, f.leg_number, home_before, away_before),
        match_decider=(plan.definition.deciding_match_decider
                       if f.leg_number == plan.definition.leg_count else MatchDecider.DRAW_ALLOWED),
    )


def _development_rotation(world, club, lineup, tactic, fixture_id: str) -> MatchLineup:
    """One earned U23 start in a subset of real AI fixtures.

    This does not award imaginary appearances: if the real fast match is not
    played or is rolled back, nothing is recorded. The manager's selections
    are never changed. A youth player must be match-fit, position-familiar
    and within an explicit quality range of the normal starter.
    """
    registry = world.football_world
    fixture = world.fixtures[fixture_id]
    if fixture.match_date is None or (registry.youth and club.id == registry.youth.managed_club_id):
        return lineup
    # Roughly one match in three, deterministic for a saved fixture/world.
    if stable_seed(world.seed,'ts248-rotation',club.id,fixture_id) % 3 != 0:
        return lineup
    used = {e.player.id for e in lineup.starters}
    candidates=[]
    for young in club.squad.players:
        if (young.id in used or not young.state.is_available or
                young.age_on(fixture.match_date) >= 23 or young.primary_position is Position.GK):
            continue
        minutes = registry.usage.get(young.id)
        # Avoid turning a fixture into a guaranteed promotional event; reward
        # genuinely ready U23s and prefer those with fewer senior minutes.
        for entry in lineup.starters:
            position = lineup.formation.slot(entry.slot_id).position
            if position is Position.GK or young.familiarity_for(position) < 75:
                continue
            role = tactic.role_for_slot(entry.slot_id).role_id
            gap = (entry.player.overall_rating_for(position,role)
                   - young.overall_rating_for(position,role))
            if gap > 16:
                continue
            priority = (-(minutes.minutes if minutes else 0)/180
                        - max(0,gap)*.8 + young.familiarity_for(position)*.05
                        + (22-young.age_on(fixture.match_date))*.35)
            candidates.append((priority,young.id,entry.slot_id,young))
    if not candidates:
        return lineup
    _,_,slot_id,young=max(candidates,key=lambda row:(row[0],row[1],row[2]))
    previous=next(e.player for e in lineup.starters if e.slot_id==slot_id)
    starters=tuple(LineupEntry(e.slot_id,young if e.slot_id==slot_id else e.player)
                   for e in lineup.starters)
    bench=[p for p in lineup.bench if p.id!=young.id and p.id!=previous.id]
    # The previous starter remains available as a replacement, even when the
    # selected youngster originally sat outside the matchday 18.
    bench=bench[:max(0,len(lineup.bench)-1)]
    if lineup.bench:
        bench.append(previous)
    result=MatchLineup(club.id,lineup.formation,starters,tuple(bench))
    club.validate_lineup(result)
    return result


def _administrative_result(world, fixture_id: str):
    """Only for an AI team unable to present eleven AVAILABLE players and a GK.

    No fake professional is created and no senior playing minutes are awarded.
    The underlying fixture explicitly records an administrative resolver, so
    subsequent views/archives can tell this from a played 3-0 result.
    """
    from football_manager.domain.world_runner import WorldMatchResult
    reg=world.football_world
    fixture=world.fixtures[fixture_id]
    manager=reg.youth.managed_club_id if reg.youth else None
    failing=[]
    for cid in (fixture.home_club_id,fixture.away_club_id):
        if cid not in reg.clubs:
            continue
        club=reg.clubs[cid]
        ready=[p for p in club.squad.players if p.state.is_available]
        if len(ready)<11 or not any(p.primary_position is Position.GK for p in ready):
            if cid==manager:
                # Never resolve the human manager's lineup on their behalf.
                raise ValueError('Managed club cannot field eleven eligible players and a goalkeeper')
            failing.append(cid)
    if not failing:
        return None
    if len(failing)==2:
        # Administrative tie-break is deterministic when both clubs default;
        # it is not a normal match and no real minutes are awarded.
        losing_home=stable_seed(world.seed,'ts2411-double-default',fixture_id)%2==0
    else:
        losing_home=fixture.home_club_id in failing
    for margin in range(3,16):
        goals=(0,margin) if losing_home else (margin,0)
        candidate=WorldMatchResult(fixture_id,*goals,resolver='administrative')
        try:
            world._validate_result_semantics(candidate,world.results)
        except ValueError:
            continue
        return world.record_result(fixture_id,*goals,resolver='administrative')
    raise ValueError('Unable to settle an administrative result under knockout rules')


def opponent_side(world, club_id: str, name: str | None = None, *, fixture_id: str | None = None):
    registry = world.football_world
    if club_id in registry.clubs:
        club, identity = registry.clubs[club_id], registry.identities[club_id]
    else:
        # Explicit provisional visitor. Never relative to the manager's strength;
        # never inserted into the 92-club professional registry or counted as one.
        club, identity = generate_club(
            club_id=club_id, name=name or club_id.replace('-', ' ').title(), tier=1,
            quality=float(world.strengths[club_id]), seed=registry.seed,
            on_date=registry.created_on, style='balanced', formation_id='dev-4-3-3',
        )
    lineup, tactic = select_team(club, identity)
    if fixture_id is not None and club_id in registry.clubs:
        lineup = _development_rotation(world,club,lineup,tactic,fixture_id)
    return club, lineup, tactic


def result_morale(result, club, lineup) -> None:
    margin = (result.home_goals - result.away_goals) * (1 if club.id == result.home_club_id else -1)
    base = (2.6 + min(1.4, .35 * margin) if margin > 0 else
            -2.2 - min(1.3, .30 * abs(margin)) if margin < 0 else .35)
    starters = {e.player.id for e in lineup.starters}
    for player in club.squad.players:
        multiplier = 1.1 if player.id in starters else .75
        player.state.adjust_morale(base * multiplier - .18 * (player.state.morale - 72.0))


def _persist_side(result, club, lineup, tactic) -> None:
    stats = {s.player_id: s for s in result.player_statistics if s.club_id == club.id}
    starter_roles = {e.player.id: tactic.role_for_slot(e.slot_id).role_id for e in lineup.starters}
    starter_positions = {e.player.id: lineup.formation.slot(e.slot_id).position for e in lineup.starters}
    segments = {}
    for segment in result.role_segments:
        if segment.club_id == club.id:
            segments.setdefault(segment.player_id, []).append(segment)
    for player in club.squad.players:
        stat = stats.get(player.id)
        if stat is None or stat.minutes <= 0:
            continue
        set_post_match_condition(player, condition=stat.condition_after, fatigue=stat.fatigue_after)
        role_minutes = None
        if player.id in segments:
            role_minutes = {}
            for segment in segments[player.id]:
                player.record_position_minutes(Position(segment.position), float(segment.minutes))
                role_minutes[segment.role_id] = role_minutes.get(segment.role_id, 0) + segment.minutes
        elif player.id in starter_positions:
            player.record_position_minutes(starter_positions[player.id], float(stat.minutes))
        apply_player_match_progression(
            player, minutes=stat.minutes, match_rating=stat.match_rating,
            role_id=starter_roles.get(player.id), tactic_id=tactic.tactic_id, role_minutes=role_minutes,
        )
    result_morale(result, club, lineup)


def record_world_usage(world, fixture_id: str, result, lineups) -> None:
    registry = world.football_world
    if registry is None:
        return
    if fixture_id in registry.processed_fixtures:
        raise ValueError('fixture participation has already been committed')
    participants = []
    starter_ids = {e.player.id for lineup in lineups for e in lineup.starters}
    for stat in result.player_statistics:
        club = registry.clubs.get(stat.club_id)
        if club is None or stat.minutes <= 0:
            continue
        if not club.squad.contains(stat.player_id):
            raise ValueError('match participant is not registered with the club')
        previous = registry.usage.get(stat.player_id, PlayerSeasonUsage())
        summary = PlayerSeasonUsage(
            previous.appearances + 1, previous.starts + int(stat.player_id in starter_ids),
            previous.minutes + stat.minutes, previous.goals + stat.goals,
            previous.assists + stat.assists, previous.rating_total + stat.match_rating,
        )
        world._put(registry.usage, stat.player_id, summary)
        from football_manager.services.youth_match_development import record_participation
        record_participation(world, stat.player_id, world.fixtures[fixture_id].match_date, stat.minutes)
        participants.append(stat.club_id)
    for club_id in set(participants):
        world._put(registry.last_recovery, club_id, world.fixtures[fixture_id].match_date)
    from football_manager.services.season_statistics import record_season_statistics
    record_season_statistics(world, fixture_id, result, lineups)
    from football_manager.services.player_development import record_development_exposure
    record_development_exposure(world, fixture_id, result, lineups)
    from football_manager.services.player_aging import record_postmatch_health
    record_postmatch_health(world, fixture_id, result)
    world._put(registry.processed_fixtures, fixture_id, True)


def simulate_registered_fixture(world, fixture_id: str):
    fixture = world.fixtures[fixture_id]
    if fixture_id in world.results:
        raise ValueError('cannot simulate a fixture twice')
    registry = world.football_world
    registered = tuple(registry.clubs[cid] for cid in (fixture.home_club_id, fixture.away_club_id)
                       if cid in registry.clubs)
    if fixture.match_date is None:
        raise ValueError('cannot simulate a fixture without a match date')
    with world.transaction():
        from football_manager.services.player_development import advance_world_development
        advance_world_development(world, fixture.match_date)
        # Join the OUTERMOST world journal, so a later error in a composed
        # transaction also restores player state from earlier successful games.
        journal = world._active_journal
        for club in registered:
            key = ('club-players', id(club))
            if key not in journal.undo_callbacks:
                saved = capture_player_state((club,))
                journal.undo_callbacks[key] = lambda saved=saved: restore_player_state(saved)
        for club in registered:
            recover_world_club(world, club.id, fixture.match_date)
        administrative=_administrative_result(world,fixture_id)
        if administrative is not None:
            return administrative
        home, home_lineup, home_tactic = opponent_side(world, fixture.home_club_id, fixture_id=fixture_id)
        away, away_lineup, away_tactic = opponent_side(world, fixture.away_club_id, fixture_id=fixture_id)
        context = MatchContextSnapshot(
            kickoff=fixture.kickoff, competition=competition_context(world, fixture_id),
            stadium=StadiumSnapshot(f'{home.id}-ground', f'{home.name} Ground', 105.0, 68.0,
                                    SurfaceType.HYBRID_GRASS, city='England'),
            conditions=MatchConditionsSnapshot(WeatherSnapshot(WeatherType.CLOUDY, 18.0, 11.0, 62.0)),
            referee=RefereeSnapshot('world-ref', 'Development Referee'),
            kits=MatchKitSelectionSnapshot(
                KitSnapshot(f'{home.id}-home', home.id, 'Home', KitType.HOME),
                KitSnapshot(f'{away.id}-away', away.id, 'Away', KitType.AWAY)),
        )
        snapshot = build_match_snapshot(
            match_id=fixture_id, seed=stable_seed(world.seed, fixture_id, 'fast-world-v1'),
            context=context, home_club=home, home_lineup=home_lineup, home_tactic=home_tactic,
            away_club=away, away_lineup=away_lineup, away_tactic=away_tactic,
        )
        from football_manager.fast_simulation.ai_coaching import coach_for_match
        ai_coaches = {team.club_id: coach_for_match(
            world.seed, team.club_id, team.tactic.preset_origin.value, fixture_id)
            for team in (snapshot.home_team, snapshot.away_team)}
        result = FastMatchSimulator().simulate(snapshot, ai_coaches=ai_coaches)
        record = world.record_result(
            fixture_id, result.home_goals, result.away_goals,
            penalties_home=result.penalties_home, penalties_away=result.penalties_away,
            resolver='background',
        )
        for club, lineup, tactic in ((home, home_lineup, home_tactic), (away, away_lineup, away_tactic)):
            if club.id in registry.clubs:
                _persist_side(result, club, lineup, tactic)
        record_world_usage(world, fixture_id, result, (home_lineup, away_lineup))
        return record
