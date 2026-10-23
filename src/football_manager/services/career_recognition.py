"""TS-28.3: factual, bounded career evolution and season-end individual awards.

Award scores use *recorded matches*, never potential, fame or OVR. Save once
at the certified season boundary; GET handlers are strictly read-only.
"""
from __future__ import annotations

from datetime import date
from football_manager.domain.career_recognition import RatingSnapshot, IndividualAward
from football_manager.domain.season_statistics import SeasonPlayerStatistics

INDICATOR_LABELS = ('Technical average','Mental average','Physical average', 'Passing', 'Finishing', 'Tackling', 'Vision', 'Decisions', 'Pace', 'Stamina')

AWARD_LABELS = {
    'player': 'Player of the Season', 'young': 'Young Player of the Season',
    'keeper': 'Goalkeeper of the Season', 'goals': 'Golden Boot',
    'assists': 'Top Assists', 'xi_gk': 'Team of the Season · GK',
    'xi_def_1': 'Team of the Season · DEF', 'xi_def_2': 'Team of the Season · DEF',
    'xi_def_3': 'Team of the Season · DEF', 'xi_def_4': 'Team of the Season · DEF',
    'xi_mid_1': 'Team of the Season · MID', 'xi_mid_2': 'Team of the Season · MID',
    'xi_mid_3': 'Team of the Season · MID', 'xi_att_1': 'Team of the Season · ATT',
    'xi_att_2': 'Team of the Season · ATT', 'xi_att_3': 'Team of the Season · ATT',
    'world_player': 'Ballon d’Or · Simulated world player of the year',
    'world_young': 'Golden Boy · Simulated world U21 player',
    'golden_shoe': 'Golden Shoe · Top-division league scorer',
}


def _players(registry):
    out = {p.id: p for club in registry.clubs.values() for p in club.squad.players}
    out.update({pid: r.player for pid, r in registry.retired_players.items()})
    out.update({pid: r.player for pid, r in registry.free_agents.items()})
    return out


def indicators_for(player) -> tuple[tuple[str, float], ...]:
    a = player.attributes
    result = (
        ('Technical average', a.technical.average()),
        ('Mental average', a.mental.average()),
        ('Physical average', a.physical.average()),
        ('Passing', a.technical.passing),
        ('Finishing', a.technical.finishing),
        ('Tackling', a.technical.tackling),
        ('Vision', a.mental.vision),
        ('Decisions', a.mental.decisions),
        ('Pace', a.physical.pace),
        ('Stamina', a.physical.stamina),
    )
    return tuple((key, round(float(value), 2)) for key, value in result)


def record_rating_snapshots(registry, on_date: date, *, final: bool = False) -> int:
    """At opening and season close. Can be called twice without duplicating.

    Keep only a few dozen points per player across multi-decade careers.
    """
    count = 0
    for pid, player in _players(registry).items():
        previous = registry.rating_history.get(pid, ())
        if previous and previous[-1].on_date == on_date:
            continue
        if previous and not final:
            # Existing players have last season's certified end-of-year point.
            # Don't double archive them on July 1; the live rating remains
            # available for comparison until this season's next final snapshot.
            continue
        point = RatingSnapshot(registry.season_label, on_date,
                               round(float(player.overall_rating), 2), tuple(v for _, v in indicators_for(player)))
        registry.rating_history[pid] = (*previous[-79:], point)
        count += 1
    return count


def _bucket(position: str) -> str:
    if position == 'GK':
        return 'gk'
    if position in {'RB', 'RCB', 'CB', 'LCB', 'LB', 'RWB', 'LWB'}:
        return 'def'
    if position in {'DM', 'RCM', 'CM', 'LCM', 'AM'}:
        return 'mid'
    return 'att'


def _sum_stats(season_ledger):
    result = {}
    for players in season_ledger.values():
        for pid, s in players.items():
            result[pid] = result.get(pid, SeasonPlayerStatistics()).plus(s)
    return result


def _scored_candidates(season, totals, players, registry):
    eligible = []
    for pid, stat in totals.items():
        p = players.get(pid)
        if p is None or stat.appearances < 3 or stat.minutes < 225:
            continue
        if pid not in registry.player_season_clubs.get(season, {}):
            # Never attribute a verified result to an unregistered player.
            continue
        rating = stat.rating_total / stat.appearances
        participation = min(1.0, stat.minutes / 2400)
        g90 = stat.goals * 90 / stat.minutes
        a90 = stat.assists * 90 / stat.minutes
        score = rating * 4.0 + participation * 3.5 + min(2, g90)*1.8 + min(2,a90)*1.25
        group = _bucket(p.primary_position.value)
        if group == 'gk':
            score += min(1.0, stat.clean_sheets / max(1, stat.appearances))
        clubs = registry.player_season_clubs[season][pid]
        # A multi-club season never gets a guessed single-club attribution.
        club_id = clubs[0] if len(clubs) == 1 else None
        eligible.append({'id': pid, 'player': p, 's': stat, 'score': score,
                         'group': group, 'club': club_id})
    return eligible


def award_season(registry, world, report, *, as_of: date) -> int:
    """One-time certificate of a finished season, not re-evaluated on profile GET."""
    season = report.season_label
    if season in registry.individual_awards:
        return 0
    ledgers = registry.statistics
    if not ledgers.complete_seasons.get(season, False):
        registry.individual_awards[season] = ()
        return 0
    recorded = ledgers.seasons.get(season, {})
    all_players = _players(registry)
    scopes = {cid: recorded.get(cid, {}) for cid in (*world.leagues,)}
    scopes.update({cid: recorded.get(cid, {}) for cid in ('champions-league', 'europa-league', 'conference-league')
                   if cid in world.staged})
    scopes['world'] = _sum_stats(recorded)
    results = []

    def add(scope, category, candidate):
        results.append(IndividualAward(season, scope, category, candidate['id'], candidate['club']))

    for scope_id, totals in scopes.items():
        candidates = _scored_candidates(season, totals, all_players, registry)
        if not candidates:
            continue
        by_score = sorted(candidates, key=lambda x: (-x['score'], -x['s'].minutes, x['id']))
        if scope_id == 'world':
            add(scope_id, 'world_player', by_score[0])
            # A Golden Boy-style annual winner is certified from actually
            # recorded season participation, not current potential or OVR.
            juniors = [x for x in by_score if x['player'].age_on(as_of) < 21]
            if juniors:
                add(scope_id, 'world_young', juniors[0])
            continue
        add(scope_id, 'player', by_score[0])
        young = [x for x in candidates if x['player'].age_on(as_of) < 23]
        if young:
            add(scope_id, 'young', max(young, key=lambda x: (x['score'], x['s'].minutes, x['id'])))
        keepers = [x for x in candidates if x['group'] == 'gk']
        if keepers:
            add(scope_id, 'keeper', max(keepers,
                key=lambda x: (x['score'] + x['s'].clean_sheets*.08, x['s'].minutes, x['id'])))
        add(scope_id, 'goals', max(candidates, key=lambda x: (x['s'].goals, x['score'], x['id'])))
        add(scope_id, 'assists', max(candidates, key=lambda x: (x['s'].assists, x['score'], x['id'])))
        for family, count in (('gk', 1), ('def', 4), ('mid', 3), ('att', 3)):
            group = [x for x in by_score if x['group'] == family][:count]
            for index, item in enumerate(group, 1):
                add(scope_id, f'xi_{family}_{index}' if family != 'gk' else 'xi_gk', item)
    # Golden Shoe: actual goals in top-tier league matches only.  In future
    # databases, each country's top division is recognized from the stable
    # club identity tier; we never count lower divisions or cup goals.
    eligible_leagues = []
    for cid, edition in world.leagues.items():
        participants = getattr(edition, 'participant_club_ids', ())
        tiers = [registry.identities.get(club_id).tier for club_id in participants
                 if registry.identities.get(club_id) is not None]
        if tiers and min(tiers) == 1:
            eligible_leagues.append(cid)
    scorers = {}
    for cid in eligible_leagues:
        for pid, stat in recorded.get(cid, {}).items():
            if pid not in all_players or stat.appearances < 3 or stat.minutes < 225:
                continue
            prior = scorers.get(pid, (0, 0))
            scorers[pid] = (prior[0]+stat.goals, prior[1]+stat.minutes)
    if scorers:
        winner_id = sorted(scorers, key=lambda pid:(-scorers[pid][0], -scorers[pid][1], pid))[0]
        clubs = registry.player_season_clubs.get(season, {}).get(winner_id, ())
        # A multi-club year must not be credited to a guessed club.
        results.append(IndividualAward(season, 'world', 'golden_shoe', winner_id,
                                       clubs[0] if len(clubs) == 1 else None))
    # The Puskas award is deliberately not fabricated: low xG is not the same
    # as an aesthetically outstanding goal.  The icon and record schema are
    # ready for a future authenticated goal-quality event feed.
    registry.individual_awards[season] = tuple(results)
    return len(results)
