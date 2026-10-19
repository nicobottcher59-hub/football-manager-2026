"""Compact Home competition cards; no full bracket/event dump and no predictions."""
from __future__ import annotations
from .competitions import competition_options, _table_rows, _league_routes, _tie


def home_competition_read_model(session, competition_id=None) -> dict:
    index = competition_options(session)
    options = index['competitions']
    upcoming = sorted((f for fid, f in session._world.fixtures.items()
                       if fid not in session._world.results and f.match_date is not None
                       and session.home_club.id in (f.home_club_id, f.away_club_id)),
                      key=lambda f: (f.kickoff, f.fixture_id))
    ids = {c['id'] for c in options}
    if competition_id and competition_id not in ids:
        raise KeyError('Competition is not registered for the managed club')
    default = next((f.competition_id for f in upcoming if f.competition_id in ids), options[0]['id'] if options else None)
    cid = competition_id or default
    result = {'options': options, 'default_id': default, 'id': cid, 'date': session.current_date.isoformat(),
              'managed_id': session.home_club.id, 'season': session._world.season_label,
              'name': next((c['name'] for c in options if c['id'] == cid), ''),
              'table': [], 'tie': None, 'next_tie': None, 'mode': 'empty'}
    if cid is None:
        return result
    world, managed = session._world, session.home_club.id
    if cid in world.leagues:
        edition = world.leagues[cid]
        return {**result, 'mode': 'table', 'table': _table_rows(session, world.standings(cid), routes=_league_routes(edition))}
    staged = world.staged.get(cid)
    cup = world.cups.get(cid)
    plans = staged.knockout_plans if staged else cup.plans
    own = [(i, plan, tie) for i, plan in enumerate(plans) for tie in plan.ties
           if managed in (tie.club_a_id, tie.club_b_id)]
    if staged and not own:
        group_id = next((gid for gid, members in staged.groups.items() if managed in members), None)
        table = _table_rows(session, staged.standings(world.results, group_id))
        primary_fixtures = [f for f in world.fixtures.values() if f.competition_id == cid and f.stage_id == staged.primary_stage_id]
        primary_done = bool(primary_fixtures) and all(f.fixture_id in world.results for f in primary_fixtures)
        row = next((r for r in table if r['managed']), None)
        cutoff = 2 if staged.groups else 24
        status = 'Eliminated in the league/group phase.' if primary_done and row and row['position'] > cutoff else 'Awaiting knockout draw.' if primary_done else None
        return {**result, 'mode': 'table', 'table': table, 'status': status,
                'phase': 'Group stage' if staged.groups else 'League phase'}
    if not own:
        entry = next((rule.label for rule in cup.rounds if managed in rule.entrants), None) if cup else None
        return {**result, 'mode': 'knockout', 'status': f'{entry}: draw pending.' if entry else 'Draw pending.',
                'next_status': 'Next opponent: pending draw.'}
    projected = [(i, _tie(session, tie, round_label=plan.definition.name)) for i, plan, tie in own]
    pending = [item for item in projected if not item[1]['complete']]
    _, selected = pending[0] if pending else projected[-1]
    lost = selected['complete'] and selected['winner_id'] != managed
    champion = getattr(staged or cup, 'champion_club_id', None) == managed
    return {**result, 'mode': 'knockout', 'tie': selected,
            'status': 'Eliminated' if lost else 'Winners' if champion else 'Qualified' if selected['complete'] else 'Your tie',
            'next_status': None if lost or champion else 'Next opponent: pending draw.',
            'bracket_prediction_supported': False}
