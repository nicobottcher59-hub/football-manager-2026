"""Record once, read in O(competitions * roster), never replay history on a GET."""
from __future__ import annotations

from football_manager.domain.season_statistics import SeasonPlayerStatistics, SeasonStatisticsLedger

SUPPORTED_STATS = ('appearances', 'starts', 'minutes', 'goals', 'assists', 'clean_sheets',
                   'xg', 'pass_completion', 'shots', 'shots_on_target',
                   'yellow_cards', 'red_cards', 'average_match_rating')
BASIC_STATS = ('appearances', 'starts', 'minutes', 'goals', 'assists', 'average_match_rating')


def record_season_statistics(world, fixture_id, result, lineups) -> bool:
    registry = world.football_world
    if registry is None:
        return False
    ledger = registry.statistics
    season = world.season_label
    fixture = world.fixtures[fixture_id]
    token = f'{season}:{fixture_id}'
    if token in ledger.recorded_fixtures:
        return False
    if season not in ledger.seasons:
        # All writes join WorldSeasonRunner's transaction, including first use.
        world._put(ledger.seasons, season, {})
        world._put(ledger.coverage_from, season, fixture.match_date)
        world._put(ledger.complete_seasons, season, True)
    competitions = ledger.seasons[season]
    cid = fixture.competition_id
    if cid not in competitions:
        world._put(competitions, cid, {})
    totals = competitions[cid]
    competition = world.leagues.get(cid) or world.cups.get(cid) or world.staged.get(cid)
    name = getattr(competition, 'name', None) or getattr(getattr(competition, 'competition', None), 'name', cid)
    world._put(ledger.competition_names, cid, name.replace(' (development)', ''))
    starting = {(lineup.club_id, e.player.id): lineup.formation.slot(e.slot_id).position.value
                for lineup in lineups for e in lineup.starters}
    positions = dict(starting)
    for event in result.substitutions:
        positions[(event.club_id, event.player_in_id)] = event.position
    defensive = {'GK', 'CB', 'LCB', 'RCB', 'LB', 'RB', 'LWB', 'RWB'}
    for stat in result.player_statistics:
        club = registry.clubs.get(stat.club_id)
        if club is None or stat.minutes <= 0:
            continue
        if not club.squad.contains(stat.player_id):
            raise ValueError('unregistered participant in statistics')
        conceded = result.away_goals if stat.club_id == result.home_club_id else result.home_goals
        # Explicit definition: GK/defenders, >=60 minutes, team conceded zero.
        # Shoot-out kicks are not goals, shots, xG or assists in the match ledger.
        clean = int(stat.minutes >= 60 and conceded == 0 and positions.get((stat.club_id, stat.player_id)) in defensive)
        one = SeasonPlayerStatistics(
            appearances=1, starts=int((stat.club_id, stat.player_id) in starting),
            minutes=stat.minutes, goals=stat.goals, assists=stat.assists,
            shots=stat.shots, shots_on_target=stat.shots_on_target, xg=stat.xg,
            passes_attempted=stat.passes_attempted, passes_completed=stat.passes_completed,
            fouls=stat.fouls, yellow_cards=stat.yellow_cards, red_cards=stat.red_cards,
            rating_total=stat.match_rating, clean_sheets=clean,
        )
        world._put(totals, stat.player_id, totals.get(stat.player_id, SeasonPlayerStatistics()).plus(one))
    # A footballer may represent two different clubs during one season.
    # Record only clubs for which an actual match appearance was stored.
    if season not in registry.player_season_clubs:
        world._put(registry.player_season_clubs, season, {})
    affiliations = registry.player_season_clubs[season]
    for stat in result.player_statistics:
        if stat.minutes <= 0 or stat.club_id not in registry.clubs:
            continue
        previous = affiliations.get(stat.player_id, ())
        if stat.club_id not in previous:
            world._put(affiliations, stat.player_id, (*previous, stat.club_id))
    world._put(ledger.recorded_fixtures, token, True)
    return True


def statistics_options(registry, world=None) -> dict:
    ledger = registry.statistics
    seasons = sorted({registry.season_label, *registry.history, *ledger.seasons}, reverse=True)
    names = dict(ledger.competition_names)
    if world is not None:
        for cid, entry in {**world.leagues, **world.cups, **world.staged}.items():
            name = getattr(entry, 'name', None) or getattr(getattr(entry, 'competition', None), 'name', cid)
            names[cid] = name.replace(' (development)', '')
    return {'current_season': registry.season_label, 'seasons': seasons,
            'competitions': [{'id': cid, 'name': name} for cid, name in sorted(names.items())],
            'supported': list(SUPPORTED_STATS), 'unsupported': ['xa', 'tackles'],
            'clean_sheet_definition': 'Goalkeeper/defender: 60+ minutes and zero team goals conceded (shoot-outs excluded).',
            'coverage': {season: {'from': ledger.coverage_from[season].isoformat(),
                                  'complete': ledger.complete_seasons[season]}
                         for season in ledger.seasons}}


def player_statistics(registry, player_id: str, *, season: str | None = None, competition: str | None = None) -> dict:
    season = season or registry.season_label
    ledger = registry.statistics
    competitions = ledger.seasons.get(season, {})
    total = SeasonPlayerStatistics()
    for cid, players in competitions.items():
        if not competition or competition == 'all' or cid == competition:
            total = total.plus(players.get(player_id, SeasonPlayerStatistics()))
    view = total.view()
    complete = ledger.complete_seasons.get(season, False)
    usage = (registry.usage if season == registry.season_label else registry.history.get(season, {})).get(player_id)
    if not competition or competition == 'all':
        if usage is not None:
            # Preserve verified legacy basics. Detailed fields have no value if
            # only a subset of this player's appearances has detailed coverage.
            for key in BASIC_STATS:
                view[key] = (round(usage.rating_total / usage.appearances, 2) if usage.appearances else None) if key == 'average_match_rating' else getattr(usage, key)
            if total.appearances < usage.appearances:
                for key in view:
                    if key not in BASIC_STATS:
                        view[key] = None
        elif not complete:
            # A missing legacy row is unknown, not evidence of zero appearances.
            view = {key: None for key in view}
    elif not complete and total.appearances == 0:
        view = {key: None for key in view}
    view['coverage'] = {'complete_season': complete, 'recorded_appearances': total.appearances,
                        'from': ledger.coverage_from[season].isoformat() if season in ledger.coverage_from else None,
                        'scope': 'season' if complete else 'recorded_matches',
                        'detailed_complete': complete or (usage is not None and total.appearances == usage.appearances)}
    return view


def migrate_statistics(session) -> None:
    registry = session._world_squads
    registry.statistics = SeasonStatisticsLedger()
    registry.statistics.start_season(registry.season_label, session.current_date, complete=False)
    # Legacy totals in registry.usage/history are kept exactly as saved.
    # Old FastMatchResult lacks the original starter lineup after subsequent
    # tactics changes: do not guess it or re-run a completed game to backfill.
