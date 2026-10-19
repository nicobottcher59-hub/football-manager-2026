"""UI-3.5 pre-match and post-match views over the existing FastMatchSimulator.

No synthetic sporting events, goals or team statistics are generated here.
The display-only referee pool and weather label do not affect match RNG.
"""
from __future__ import annotations

from hashlib import sha256

from football_manager.dev_ui.session import DevelopmentSession
from football_manager.fast_simulation.models import FastMatchResult
from .models import UIRosterAdmin, squad_read_model
from .progression import pending_managed_match, progression_read_model


# Fictional staff, six per category; domestic cups draw from the four English
# tiers, not from a single arbitrary competition or imported real referee data.
ENGLISH_REFEREES = {
    'premier': ('Oliver Hart', 'Benjamin Fletcher', 'Thomas Whitfield', 'Daniel Ashford', 'James Ellison', 'Michael Rowley'),
    'championship': ('Adam Hughes', 'Peter Langley', 'Matthew Briggs', 'Samuel Preston', 'George Pearson', 'Charles Booth'),
    'league-one': ('Edward Bailey', 'William Stafford', 'Nathan Collins', 'Jonathan Reeves', 'Henry Barker', 'Robert Dixon'),
    'league-two': ('Andrew Walsh', 'Luke Bennett', 'Christopher Clarke', 'David Mercer', 'Paul Dawson', 'Stephen Marsh'),
}
UEFA_REFEREES = ('Lukas Schneider', 'Marco Bellini', 'Antoine Laurent', 'Javier Molina', 'Mikkel Andersen', 'Tomas Novak', 'Andrej Kovac', 'Matteo Ricci')


def _referee_for(fixture_id: str, competition_key: str) -> str:
    key = str(competition_key).lower()
    if any(x in key for x in ('champions', 'europa', 'conference', 'uefa')):
        candidates = UEFA_REFEREES
    elif 'fa-cup' in key or 'carabao' in key or 'trophy' in key:
        candidates = tuple(name for names in ENGLISH_REFEREES.values() for name in names)
    elif 'championship' in key:
        candidates = ENGLISH_REFEREES['championship']
    elif 'league-one' in key:
        candidates = ENGLISH_REFEREES['league-one']
    elif 'league-two' in key:
        candidates = ENGLISH_REFEREES['league-two']
    else:
        candidates = ENGLISH_REFEREES['premier']
    i = int.from_bytes(sha256(fixture_id.encode('utf-8')).digest()[:4], 'big') % len(candidates)
    return candidates[i]


def _shirt_numbers(players, assigned: dict[str, int] | None = None) -> dict[str, int]:
    assigned = assigned or {}
    used: set[int] = set()
    result = {}
    for player in players:
        val = assigned.get(player.id)
        if isinstance(val, int) and not isinstance(val, bool) and val not in used and 1 <= val <= 99:
            result[player.id] = val
            used.add(val)
    # DEV numbers are provisional and stable for a roster, not career contracts.
    candidates = (1, *range(2, 100))
    for player in players:
        if player.id not in result:
            val = next(n for n in candidates if n not in used)
            result[player.id] = val
            used.add(val)
    return result


def _club_payload(club, lineup, admin_numbers=None, managed=False, tactic=None, chemistry=None) -> dict:
    numbers = _shirt_numbers(club.squad.players, admin_numbers)
    from football_manager.domain.player_ratings import CurrentRatingContext
    from football_manager.domain.tactical_geometry import phase_points
    points = phase_points(tactic, 'in_possession') if tactic else {}
    def make_player(player, position=None, slot_id=None):
        role = tactic.role_for_slot(slot_id) if tactic and slot_id else None
        rating = player.current_rating(CurrentRatingContext(
            assigned_position=position, role_id=role.role_id if role else None,
            tactic_id=tactic.tactic_id if tactic and slot_id else None,
            chemistry=(chemistry or {}).get(player.id, 65.0) if slot_id else 65.0))
        coords = points.get(slot_id)
        return {
            'act': round(rating.current, 1), 'ovr': round(rating.overall, 1),
            'role_id': role.role_id if role else None,
            'x': round(coords[0]*100, 1) if coords else None,
            'y': round(coords[1]*100, 1) if coords else None,
            'id': player.id, 'name': player.full_name,
            'short_name': player.identity.last_name,
            'number': numbers[player.id],
            'position': position.value if position else player.primary_position.value,
            'slot_id': slot_id,
            'available': player.state.is_available,
            'injury': player.state.injury,
            'return_on': (player.aging.active_injury.return_on.isoformat() if player.aging and player.aging.active_injury and player.aging.active_injury.return_on else None),
            'suspension': player.state.suspended_matches,
            'condition': round(player.state.condition, 1),
        }
    selected = {p.id for p in lineup.selected_players}
    starters = [make_player(entry.player, lineup.formation.slot(entry.slot_id).position, entry.slot_id)
                for entry in lineup.starters]
    bench = [make_player(player) for player in lineup.bench]
    unavailable = [make_player(player) for player in club.squad.players
                   if not player.state.is_available]
    return {
        'id': club.id, 'name': club.name, 'managed': managed,
        'formation': lineup.formation.name, 'formation_id': lineup.formation.formation_id,
        'starters': starters, 'bench': bench, 'unavailable': unavailable,
        'remaining': sum(p.id not in selected for p in club.squad.players),
        'manager': 'Your team' if managed else 'AI manager',
    }


def _match_meta(session: DevelopmentSession) -> dict | None:
    item = pending_managed_match(session)
    if item is None or item.match_date > session.current_date:
        return None
    fixture = item.fixture
    is_home = fixture.home_club_id == session.home_club.id
    names = session._world_club_names
    actual_home_id = fixture.home_club_id
    return {
        'fixture_id': fixture.fixture_id,
        'date': item.match_date.isoformat(),
        'kickoff': session._world.fixtures[fixture.fixture_id].kickoff.isoformat()
            if fixture.fixture_id in session._world.fixtures and session._world.fixtures[fixture.fixture_id].kickoff else None,
        'competition': item.competition_name,
        'competition_key': item.competition_key,
        'round': item.round_label,
        'home_name': names.get(fixture.home_club_id, fixture.home_club_id),
        'away_name': names.get(fixture.away_club_id, fixture.away_club_id),
        'managed_home': is_home,
        'stadium': f"{names.get(actual_home_id, actual_home_id)} Ground",  # DEV snapshot stadium
        'referee': _referee_for(fixture.fixture_id, item.competition_key),
        'referee_note': 'Fictional display-only appointment; not used by FastMatchSimulator',
        'weather': 'Cloudy · 18°C',
        'weather_note': 'Decorative DEV conditions; do not affect FastMatchSimulator',
    }


def prematch_read_model(session: DevelopmentSession, admin: UIRosterAdmin, commands: list[dict] | None = None) -> dict:
    from .models import apply_squad_command
    from copy import deepcopy
    meta = _match_meta(session)
    if meta is None:
        return {'status': 'no_match', 'message': 'No managed match is pending on the current day.',
                'progression': progression_read_model(session)}
    preview = session
    if commands:
        preview = deepcopy(session)
        for command in commands:
            apply_squad_command(preview, command)
    managed = _club_payload(preview.home_club, preview.home_lineup, admin.numbers, True, preview.home_tactic, preview._home_chemistry)
    opponent = _club_payload(preview.away_club, preview.away_lineup, tactic=preview.away_tactic, chemistry=preview._away_chemistry)
    tactical = squad_read_model(preview, admin)
    return {'status':'prematch', 'match':meta,
            'home':managed if meta['managed_home'] else opponent,
            'away':opponent if meta['managed_home'] else managed,
            'managed':managed,
            'tactical':{
                'formation': tactical['formation'], 'formations':tactical['formations'],
                'slots':tactical['slots'], 'starters':tactical['starters'], 'bench':tactical['bench'],
                'targets':tactical['targets'],
                'tactics':tactical['tactics'],
                'studio':tactical['studio'],
            },
            'match_tactics_temporary':True,
            'kit_choices':('default','dark','light','blue','red','purple','yellow','green')}


def result_read_model(session: DevelopmentSession, metadata: dict, result: FastMatchResult,
                      injury_before: dict[str, str | None] | None = None) -> dict:
    # Player IDs are unique within a club, not necessarily across clubs.
    # Display names for match events must be keyed by BOTH identities.
    by_club_and_id = {
        (club.id, player.id): player.full_name
        for club in (session.home_club, session.away_club)
        for player in club.squad.players
    }

    def name(club_id: str, player_id: str) -> str:
        return by_club_and_id.get((club_id, player_id), player_id)
    home_id, away_id = result.home_club_id, result.away_club_id
    def event(minute, kind, club_id=None, **details):
        return {'minute':minute, 'kind':kind, 'club_id':club_id, **details}
    events = []
    for g in result.goals:
        events.append(event(g.minute,'goal',g.club_id,
                            player=name(g.club_id, g.scorer_player_id), player_id=g.scorer_player_id,
                            assist=name(g.club_id, g.assist_player_id) if g.assist_player_id else None,
                            xg=round(g.xg,2), extra_time=g.extra_time))
    for c in result.cards:
        events.append(event(c.minute,'card',c.club_id,player=name(c.club_id, c.player_id),card=c.card.value))
    for s in result.substitutions:
        events.append(event(s.minute,'substitution',s.club_id,player_out=name(s.club_id, s.player_out_id),
                            player_in=name(s.club_id, s.player_in_id),position=s.position))
    for change in result.tactical_events:
        events.append(event(change.minute, 'tactical_plan', change.club_id,
                            plan=change.plan, name=change.name, applied=change.applied,
                            condition=change.condition, own_goals=change.own_goals,
                            opponent_goals=change.opponent_goals))
    for p in result.penalty_kicks:
        # Only penalty shootout attempts are exposed; do not invent in-play penalty misses.
        events.append(event(120,'shootout_kick',p.club_id,player=name(p.club_id, p.taker_player_id),
                            scored=p.scored,sequence=p.sequence,round=p.round_number,
                            home_score=p.score_after_home,away_score=p.score_after_away))
    events.extend([event(45,'half_time'),event(120 if result.extra_time_home_goals or result.extra_time_away_goals or result.decision.value=='penalties' else 90,'full_time')])
    priority = {'tactical_plan':-1,'goal':0,'card':1,'substitution':2,'half_time':3,'shootout_kick':4,'full_time':5}
    events.sort(key=lambda e:(e['minute'],priority.get(e['kind'],9),e.get('sequence',0)))
    def stat(s):
        return {'possession':round(s.possession_pct,1),'xg':round(s.xg,2),
                'shots':s.shots,'shots_on_target':s.shots_on_target,
                'passes':s.passes_completed,'passes_attempted':s.passes_attempted,
                'pass_accuracy':round(s.pass_completion_pct,1),'corners':s.corners,
                'fouls':s.fouls,'yellow_cards':s.yellow_cards,'red_cards':s.red_cards,
                'tackles':None}
    injury_before = injury_before or {}
    new_injuries = []
    for club in (session.home_club, session.away_club):
        for player in club.squad.players:
            episode = player.aging.active_injury if player.aging else None
            if episode and episode.episode_id == f"{metadata['fixture_id']}:{player.id}":
                new_injuries.append({'player': player.full_name, 'detail': episode.label,
                                    'club_id': club.id, 'return_on': episode.return_on.isoformat() if episode.return_on else None})
    return {'status':'finished','match':metadata,
            'home':{'id':home_id,'name':metadata['home_name'],'goals':result.home_goals,
                    'statistics':stat(result.statistics_home)},
            'away':{'id':away_id,'name':metadata['away_name'],'goals':result.away_goals,
                    'statistics':stat(result.statistics_away)},
            'decision':result.decision.value,'winner_club_id':result.winner_club_id,
            'aggregate':{'home':result.aggregate_home_goals,'away':result.aggregate_away_goals},
            'penalties':{'home':result.penalties_home,'away':result.penalties_away} if result.decision.value=='penalties' else None,
            'events':events,'new_injuries':new_injuries,
            'injury_tracking_supported':True,
            'in_match_injuries_supported':False,
            'injury_tracking_scope':'Post-match medical assessments; not an in-match event stream',
            'limitations':{'tackles':'Not recorded by FastMatchSimulator',
                           'in_match_injuries':'Post-match assessments are recorded; the fast simulator still has no in-match injury event stream',
                           'in_play_penalty_misses':'Not tracked as events by current simulator'}}
