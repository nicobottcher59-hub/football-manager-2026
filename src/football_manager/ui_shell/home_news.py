"""TS-28.1: factual career news, derived from canonical saved game ledgers.

No second news ledger, invented events, fake timestamps or gameplay mutations.
Rebuilding the feed after save/load is deterministic and intentionally cheap:
only the active season and the most recent archived report are considered.
"""
from __future__ import annotations

from datetime import date
from typing import Any


MAX_STORIES = 24


def _competition(world, cid: str) -> str:
    if cid in world.leagues:
        return world.leagues[cid].competition.name
    if cid in world.cups:
        return world.cups[cid].name
    if cid in world.staged:
        return world.staged[cid].name
    return cid.replace('-', ' ').title()


def _player_name(registry, player_id: str, buyer_id: str) -> str | None:
    # A player may have moved again or retired; never attribute a transfer to
    # the *current* buyer when the historical name is no longer resolvable.
    club = registry.clubs.get(buyer_id)
    if club is not None:
        player = next((p for p in club.squad.players if p.id == player_id), None)
        if player is not None:
            return player.full_name
    for other in registry.clubs.values():
        player = next((p for p in other.squad.players if p.id == player_id), None)
        if player is not None:
            return player.full_name
    retired = registry.retired_players.get(player_id)
    if retired is not None:
        return retired.player.full_name
    return None


def home_news_read_model(session, limit: int = MAX_STORIES) -> dict[str, Any]:
    """A read-only, deduplicated feed of verified results, moves and titles.

    ``date`` is omitted for archived season awards: SeasonReport knows the
    season but not the exact day the title was mathematically secured.
    """
    if not isinstance(limit, int) or not 1 <= limit <= MAX_STORIES:
        raise ValueError('News limit must be between 1 and 24')
    today = session.current_date
    world = session._world
    names = session._world_club_names
    managed = session.home_club.id
    events: list[dict[str, Any]] = []

    def add(event_id: str, category: str, title: str, body: str, *,
            when: date | None, priority: int, competition_id: str | None = None,
            club_id: str | None = None, season: str | None = None, player_id: str | None = None):
        events.append({'id': event_id, 'category': category, 'title': title,
                       'body': body, 'date': when.isoformat() if when else None,
                       'season': season, 'priority': priority,
                       'competition_id': competition_id, 'club_id': club_id, 'player_id': player_id,
                       '_sort_on': when.isoformat() if when else (f'{int(season[:4])+1}-06-30' if season else ''),
                       'route': 'Competitions' if competition_id else 'Scouting' if category == 'transfer' else None})

    # Match stories: one match event has exactly one immutable fixture ID.
    # Minor AI fixtures are intentionally not newsworthy; managed results are.
    # No claims about individual scorers because WorldMatchResult stores scores,
    # not verified scorer identities for *every* background fixture.
    for fid, score in world.results.items():
        fixture = world.fixtures.get(fid)
        if fixture is None or fixture.kickoff is None:
            continue
        played_on = fixture.kickoff.date()
        if played_on > today:
            continue
        home_id, away_id = fixture.home_club_id, fixture.away_club_id
        owner = managed in (home_id, away_id)
        margin = abs(score.home_goals - score.away_goals)
        goals = score.home_goals + score.away_goals
        winner = (home_id if score.home_goals > score.away_goals else
                  away_id if score.away_goals > score.home_goals else None)
        strengths = world.strengths
        underdog = (winner is not None and
                    strengths.get(winner, 50) + 15 <= strengths.get(away_id if winner == home_id else home_id, 50))
        knockout = fixture.competition_id in world.cups or fixture.competition_id in world.staged
        late_round = 'semi' in fixture.stage_id.lower() or 'final' in fixture.stage_id.lower()
        notable = owner or underdog or margin >= 4 or (goals >= 7 and margin >= 2) or (knockout and late_round)
        if not notable:
            continue
        home = names.get(home_id, home_id)
        away = names.get(away_id, away_id)
        comp = _competition(world, fixture.competition_id)
        scoreline = f'{home} {score.home_goals}-{score.away_goals} {away}'
        if score.penalties_home or score.penalties_away:
            scoreline += f' (penalties {score.penalties_home}-{score.penalties_away})'
        if owner:
            title = f'{home} vs {away}: result confirmed'
            priority = 65
        elif underdog:
            title = f'{names.get(winner, winner)} win against higher-rated opposition'
            priority = 58
        elif knockout and late_round:
            title = f'{comp}: knockout result'
            priority = 48
        else:
            title = f'{comp}: emphatic result'
            priority = 36
        add(f'match:{fid}', 'result', title, f'{scoreline}. {comp}.',
            when=played_on, priority=priority,
            competition_id=fixture.competition_id,
            club_id=winner)

    # Transfer stories are only emitted for *completed* contracts with player
    # consent, not bids, counteroffers or unsigned agreements.
    registry = session._world_squads
    for deal in registry.transfer_offers.values():
        if deal.status != 'completed' or deal.personal_status != 'completed' or not deal.personal_events:
            continue
        when = deal.personal_events[-1].on_date
        fee = deal.terms.fixed_gbp
        involved = managed in (deal.seller_id, deal.buyer_id)
        if when > today or (not involved and fee < 5_000_000):
            continue
        buyer = names.get(deal.buyer_id, deal.buyer_id)
        seller = names.get(deal.seller_id, deal.seller_id)
        player = _player_name(registry, deal.player_id, deal.buyer_id)
        label = player or 'A player'
        add(f'transfer:{deal.deal_id}', 'transfer',
            f'{label} joins {buyer}',
            f'{seller} transferred {label.lower() if player is None else player} to {buyer} for GBP {fee:,} guaranteed.',
            when=when, priority=82 if involved else 72,
            club_id=deal.buyer_id, player_id=deal.player_id)

    # Cup title dates are recovered from the final *played* competition result.
    # A champion ID alone is not used to guess an announcement date.
    for cid, competition in (*world.cups.items(), *world.staged.items()):
        champion = competition.champion_club_id
        if champion is None:
            continue
        finish_dates = [f.kickoff.date() for fid, f in world.fixtures.items()
                        if fid in world.results and f.competition_id == cid and f.kickoff]
        if not finish_dates:
            continue
        achieved_on = max(finish_dates)
        if achieved_on > today:
            continue
        club = names.get(champion, champion)
        add(f'title:{world.season_label}:{cid}', 'title',
            f'{club} win {_competition(world, cid)}',
            f'{club} are confirmed as {_competition(world, cid)} champions for {world.season_label}.',
            when=achieved_on, priority=95,
            competition_id=cid, club_id=champion, season=world.season_label)

    # Completed seasons also preserve cup winners in SeasonReport. This is
    # the canonical source after the previous season's fixture ledger rotates.
    # The report records the season, *not* the winning day: never fake a date.
    for report in session.archived_season_reports[-1:]:
        for cid, champion in report.champions.items():
            if not champion:
                continue
            club = names.get(champion, champion)
            competition = (_competition(world, cid) if cid in world.leagues or
                           cid in world.cups or cid in world.staged else
                           cid.removeprefix('dev-').replace('-', ' ').title())
            add(f'archive-title:{report.season_label}:{cid}', 'title',
                f'{club} crowned {competition} champions',
                f'{club} won {competition} in the completed {report.season_label} season.',
                when=None, priority=92 if champion == managed else 88,
                season=report.season_label, club_id=champion)

    # Within one day titles and confirmed transfers outrank routine results;
    # at most two background match reports per day keep the front page legible.
    events.sort(key=lambda e: (e['_sort_on'], e['priority'], e['id']), reverse=True)
    result_days: dict[str, int] = {}
    selected = []
    for item in events:
        if item['category'] == 'result' and not item['id'].startswith('match:'):  # defensive
            continue
        if item['category'] == 'result' and item['priority'] != 65:
            key = item['date']
            if result_days.get(key, 0) >= 2:
                continue
            result_days[key] = result_days.get(key, 0) + 1
        selected.append({key: val for key, val in item.items() if key not in ('_sort_on', 'priority')})
        if len(selected) >= limit:
            break
    return {'source': 'career-ledgers', 'date': today.isoformat(),
            'season': world.season_label, 'stories': selected,
            'total_displayed': len(selected), 'limit': limit}
