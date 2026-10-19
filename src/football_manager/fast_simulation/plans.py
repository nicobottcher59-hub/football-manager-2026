"""Prepared match-only plan changes. No plan carries purchases or substitutions."""
from __future__ import annotations
from dataclasses import dataclass
from football_manager.domain.match_snapshot import TeamMatchSnapshot
from football_manager.domain.tactical_studio import PlanRule


@dataclass(frozen=True, slots=True)
class FastTacticalChange:
    rule: PlanRule
    name: str
    team: TeamMatchSnapshot

    def __post_init__(self):
        self.rule.__post_init__()
        if not isinstance(self.name, str) or not self.name.strip():
            raise ValueError('match plan needs a name')


def validate_changes(snapshot, changes):
    if not isinstance(changes, tuple) or len(changes) > 12:
        raise ValueError('invalid match tactical changes')
    sides = {snapshot.home_team.club_id: snapshot.home_team,
             snapshot.away_team.club_id: snapshot.away_team}
    seen = set()
    for change in changes:
        if not isinstance(change, FastTacticalChange):
            raise ValueError('invalid match tactical change')
        change.__post_init__()
        team = change.team
        if team.club_id not in sides:
            raise ValueError('plan belongs to a club outside this match')
        original = sides[team.club_id]
        if {p.player_id for p in team.starters} != {p.player_id for p in original.starters}:
            raise ValueError('match plans must use the same starting players')
        if {p.player_id for p in team.bench} != {p.player_id for p in original.bench}:
            raise ValueError('match plans must preserve the bench')
        key = (team.club_id, change.rule.minute)
        if key in seen:
            raise ValueError('duplicate plan change at the same minute')
        seen.add(key)
