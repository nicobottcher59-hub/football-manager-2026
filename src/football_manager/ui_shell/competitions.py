"""Read-only competition centre for the portable UI (UI-3.3).

All tables, fixtures, draws, scores, and tie outcomes are projected from the
canonical WorldSeasonRunner. No standings, bracket seeding, results, or future
draws are simulated or constructed by this module.
"""
from __future__ import annotations

from collections import defaultdict

from football_manager.dev_ui.session import DevelopmentSession
from football_manager.domain.knockout import resolve_knockout_tie


def _pretty(name: str) -> str:
    return name.replace(" (development)", "").replace(" (fictional clubs)", "")



# UI-3.3.2: directory metadata describes only competitions already registered in
# WorldSeasonRunner. The DEV world currently has English domestic competitions
# and UEFA European club competitions; no national-team tournament is present.
# New countries/continents must be classified when their leagues are added,
# rather than silently displaying them under England.
_ENGLISH_LEAGUE_DIVISIONS = {
    "dev-premier": 1,
    "dev-championship": 2,
    "dev-league-one": 3,
    "dev-league-two": 4,
}
_ENGLISH_CUPS = frozenset({"fa-cup", "carabao-cup", "efl-trophy"})
_UEFA_COMPETITIONS = frozenset({
    "champions-league", "europa-league", "conference-league",
})


def _directory_metadata(competition_id: str) -> dict:
    """Classify existing DEV competitions for the club/world explorer."""
    base = {"participant_type": "clubs", "scope": "unknown",
            "continent": None, "country": None, "division": None,
            "competition_type": "unknown"}
    if competition_id in _ENGLISH_LEAGUE_DIVISIONS:
        return {**base, "scope": "national", "continent": "Europe",
                "country": "England",
                "division": _ENGLISH_LEAGUE_DIVISIONS[competition_id],
                "competition_type": "league"}
    if competition_id in _ENGLISH_CUPS:
        return {**base, "scope": "national", "continent": "Europe",
                "country": "England", "competition_type": "cup"}
    if competition_id in _UEFA_COMPETITIONS:
        return {**base, "scope": "international", "continent": "Europe",
                "competition_type": "continental"}
    return base


def competition_options(session: DevelopmentSession) -> dict:
    """Present the controlled club's registered competitions first.

    Cup entry can occur in a *later* round, before a tie is drawn. In that
    case the club is already registered, even though it has no cup fixture yet.
    Expose other competitions separately in the read-only world explorer.
    """
    world = session._world
    managed = session.home_club.id
    items = []
    for cid, edition in world.leagues.items():
        items.append({"id": cid, "name": _pretty(edition.competition.name), "kind": "league",
                      "family": "domestic", "participants": len(edition.participant_club_ids),
                      "managed": managed in edition.participant_club_ids,
                      **_directory_metadata(cid)})
    for cid, cup in world.cups.items():
        involved = (any(managed in rule.entrants for rule in cup.rounds)
                    or any(managed in (tie.club_a_id, tie.club_b_id)
                           for plan in cup.plans for tie in plan.ties))
        items.append({"id": cid, "name": _pretty(cup.name), "kind": "cup",
                      "family": "domestic", "participants": len({c for rule in cup.rounds for c in rule.entrants}),
                      "managed": involved, **_directory_metadata(cid)})
    for cid, stage in world.staged.items():
        items.append({"id": cid, "name": stage.name, "kind": "multi",
                      "family": "uefa" if stage.kind == "uefa" else "trophy",
                      "participants": len(stage.participants),
                      "managed": managed in stage.participants, **_directory_metadata(cid)})
    # The portable UI must never silently fall back to an old combined list.
    # Explicit schema marker allows a clear, actionable error for stale servers.
    return {"source": "python-world-runner", "schema_version": 2,
            "season": world.season_label, "date": session.current_date.isoformat(),
            "managed_club": session.home_club.name, "managed_id": managed,
            "competitions": [item for item in items if item["managed"]],
            "other_competitions": [item for item in items if not item["managed"]],
            "persistent": False}


def _table_rows(session: DevelopmentSession, rows, *, routes: dict[int, str] | None = None) -> list[dict]:
    names = session._world_club_names
    return [{"position": r.position, "club_id": r.club_id, "club": names.get(r.club_id, r.club_id),
             "played": r.played, "won": r.won, "drawn": r.drawn, "lost": r.lost,
             "gf": r.goals_for, "ga": r.goals_against, "gd": r.goal_difference,
             "points": r.points, "route": (routes or {}).get(r.position),
             "managed": r.club_id == session.home_club.id} for r in rows]


def _match(session: DevelopmentSession, fixture) -> dict:
    world = session._world
    names = session._world_club_names
    result = world.result_for(fixture.fixture_id)
    kick = fixture.kickoff
    return {"id": fixture.fixture_id, "competition_id": fixture.competition_id,
            "stage_id": fixture.stage_id,
            "round_number": fixture.round_number, "leg": fixture.leg_number,
            "date": kick.date().isoformat() if kick else None,
            "kickoff": kick.isoformat() if kick else None,
            "home_id": fixture.home_club_id, "away_id": fixture.away_club_id,
            "home": names.get(fixture.home_club_id, fixture.home_club_id),
            "away": names.get(fixture.away_club_id, fixture.away_club_id),
            "managed": session.home_club.id in (fixture.home_club_id, fixture.away_club_id),
            "source": fixture.source.value, "status": fixture.status.value,
            "score": {"home": result.home_goals, "away": result.away_goals} if result else None,
            "penalties": {"home": result.penalties_home, "away": result.penalties_away}
            if result and (result.penalties_home or result.penalties_away) else None}


def _round_matches(session: DevelopmentSession, cid: str, *, stage: str | None = None) -> dict[int, list[dict]]:
    by_round = defaultdict(list)
    for fixture in session._world.fixtures.values():
        if fixture.competition_id != cid or (stage is not None and fixture.stage_id != stage):
            continue
        if fixture.round_number is None:
            continue
        by_round[fixture.round_number].append(_match(session, fixture))
    for rows in by_round.values():
        rows.sort(key=lambda r: (r["kickoff"] or "", r["id"]))
    return by_round


def _league_routes(edition) -> dict[int, str]:
    routes = {}
    for rule in edition.qualification_rules:
        # Only the regulation itself can assign a qualifying/relegation zone.
        for position in getattr(rule, "standing_positions", ()):
            routes[position] = str(getattr(rule, "kind", ""))
    return routes


def _league(session: DevelopmentSession, cid: str) -> dict:
    world = session._world
    edition = world.leagues[cid]
    grouped = _round_matches(session, cid)
    max_round = max((f.round_number or 0 for f in edition.fixtures), default=0)
    rounds = [{"id": str(i), "label": f"Matchday {i}", "number": i,
               "matches": grouped.get(i, [])} for i in range(1, max_round + 1)]
    return {"kind": "league", "name": _pretty(edition.competition.name),
            "stages": [{"id": "league", "label": "League Table", "mode": "table"}],
            "table": _table_rows(session, world.standings(cid), routes=_league_routes(edition)),
            "rounds": rounds, "knockout": [], "groups": []}


def _tie(session: DevelopmentSession, tie, *, round_label: str) -> dict:
    world = session._world
    results = [world.result_for(f.fixture_id) for f in tie.fixtures]
    resolved = resolve_knockout_tie(tie, [r.knockout_result() for r in results if r is not None])
    return {"id": tie.tie_id, "round": round_label,
            "club_a_id": tie.club_a_id, "club_b_id": tie.club_b_id,
            "club_a": session._world_club_names.get(tie.club_a_id, tie.club_a_id),
            "club_b": session._world_club_names.get(tie.club_b_id, tie.club_b_id),
            "managed": session.home_club.id in (tie.club_a_id, tie.club_b_id),
            "winner_id": resolved.winner_club_id,
            "complete": resolved.complete, "penalties": resolved.decided_by_penalties,
            "aggregate": {"a": resolved.aggregate_a_goals, "b": resolved.aggregate_b_goals}
            if any(r is not None for r in results) else None,
            "legs": [_match(session, world.fixtures[f.fixture_id]) for f in tie.fixtures]}


def _bracket_rounds(session: DevelopmentSession, definitions, plans) -> list[dict]:
    plans_by_id = {plan.definition.round_id: plan for plan in plans}
    rounds = []
    for idx, (round_id, label) in enumerate(definitions):
        plan = plans_by_id.get(round_id)
        ties = [_tie(session, tie, round_label=label) for tie in plan.ties] if plan else []
        matches = sorted((leg for tie in ties for leg in tie["legs"]),
                         key=lambda m: (m["kickoff"] or "", m["id"]))
        rounds.append({"id": round_id, "label": label, "number": idx + 1,
                       "drawn": plan is not None, "ties": ties, "matches": matches,
                       "source": plan.source.value if plan else None})
    return rounds


def _cup(session: DevelopmentSession, cid: str) -> dict:
    cup = session._world.cups[cid]
    definitions = [(rule.round_id, rule.label) for rule in cup.rounds]
    club_id = session.home_club.id
    club_entry = next((rule for rule in cup.rounds if club_id in rule.entrants), None)
    return {"kind": "cup", "name": _pretty(cup.name),
            "stages": [{"id": "knockout", "label": "Knockout Bracket", "mode": "bracket"}],
            "table": [], "rounds": [],
            "knockout": _bracket_rounds(session, definitions, cup.plans), "groups": [],
            "managed_entry_round_id": club_entry.round_id if club_entry else None,
            "managed_entry_round_label": club_entry.label if club_entry else None,
            "champion_id": cup.champion_club_id, "fixed_bracket": False}


def _staged(session: DevelopmentSession, cid: str) -> dict:
    staged = session._world.staged[cid]
    group_items = [{"id": gid, "label": gid.replace('-', ' ').title(),
                    "managed": session.home_club.id in members,
                    "table": _table_rows(session, staged.standings(session._world.results, gid),
                                         routes={1: "advance", 2: "advance", 3: "eliminated", 4: "eliminated"})}
                   for gid, members in staged.groups.items()]
    first_group = next((g["id"] for g in group_items if g["managed"]), None)
    if first_group is None and group_items:
        first_group = group_items[0]["id"]
    if first_group:
        table = _table_rows(session, staged.standings(session._world.results, first_group),
                            routes={1: "advance", 2: "advance", 3: "eliminated", 4: "eliminated"})
    else:
        table = _table_rows(session, staged.standings(session._world.results),
                            routes={**{n: "direct" for n in range(1, 9)},
                                    **{n: "playoff" for n in range(9, 25)},
                                    **{n: "eliminated" for n in range(25, 37)}})
    by_round = _round_matches(session, cid, stage=staged.primary_stage_id)
    total = 8 if staged.kind == "uefa" and cid != "conference-league" else 6 if staged.kind == "uefa" else 3
    rounds = [{"id": str(i), "label": f"Matchday {i}", "number": i,
               "matches": by_round.get(i, [])} for i in range(1, total + 1)]
    definitions = [(rid, {"playoff": "Knockout play-offs", "r32": "Round of 32",
                          "r16": "Round of 16", "qf": "Quarter-finals", "sf": "Semi-finals",
                          "final": "Final"}.get(rid, rid.title())) for rid in staged.rounds]
    return {"kind": "multi", "name": staged.name, "format": staged.kind,
            "stages": [{"id": "primary", "label": "League Phase" if staged.kind == "uefa" else "Group Stage", "mode": "table"},
                       {"id": "knockout", "label": "Knockout Stage", "mode": "bracket"}],
            "primary_stage_id": staged.primary_stage_id, "table": table, "rounds": rounds,
            "groups": group_items, "group_id": first_group,
            "knockout": _bracket_rounds(session, definitions, staged.knockout_plans),
            "champion_id": staged.champion_club_id, "fixed_bracket": False,
            "qualifications_note": "Positions 1–8 direct R16 · 9–24 knockout play-offs · 25–36 eliminated"
            if staged.kind == "uefa" else "Top two teams advance from each group"}


def competition_read_model(session: DevelopmentSession, competition_id: str) -> dict:
    """One actual competition, fetched on demand to keep the local UI responsive."""
    world = session._world
    if competition_id in world.leagues:
        data = _league(session, competition_id)
    elif competition_id in world.cups:
        data = _cup(session, competition_id)
    elif competition_id in world.staged:
        data = _staged(session, competition_id)
    else:
        raise KeyError("unknown competition")
    return {"source": "python-world-runner", "persistent": False,
            "id": competition_id, "season": world.season_label,
            "date": session.current_date.isoformat(),
            "managed_id": session.home_club.id, "managed_club": session.home_club.name,
            "fictional_participants": True, "bracket_prediction_supported": False,
            **data}
