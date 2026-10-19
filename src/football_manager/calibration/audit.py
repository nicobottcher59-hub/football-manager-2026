from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable

from football_manager.simulation import MatchEvent, MatchEventType, TeamSide


_SHOT_RESOLUTION_TYPES = {
    MatchEventType.GOAL,
    MatchEventType.SAVE,
    MatchEventType.BLOCK,
    MatchEventType.WOODWORK,
    MatchEventType.OFF_TARGET,
}


@dataclass(frozen=True, slots=True)
class MatchEventAudit:
    event_count: int
    shot_attempts: int
    shot_resolutions: int
    unresolved_shots: int
    orphan_shot_resolutions: int
    duplicate_shot_resolutions: int
    invalid_xg_shots: int
    goal_events: int
    score_goals: int
    score_goal_delta: int

    @property
    def integrity_issues(self) -> int:
        return (
            self.unresolved_shots
            + self.orphan_shot_resolutions
            + self.duplicate_shot_resolutions
            + self.invalid_xg_shots
            + abs(self.score_goal_delta)
        )

    @property
    def is_consistent(self) -> bool:
        return self.integrity_issues == 0


def audit_match_events(
    events: Iterable[MatchEvent],
    *,
    home_goals: int,
    away_goals: int,
) -> MatchEventAudit:
    """Cross-check the event stream used by statistics/calibration.

    Open-play shots are linked to exactly one terminal outcome with ``shot_id``.
    Penalty kicks are self-contained ``PENALTY_KICK`` events and are therefore
    excluded from this open-play shot-link audit.  The final score is also
    compared with emitted GOAL events so a scoring path cannot silently bypass
    the observable event stream.
    """

    items = tuple(events)
    attempts: dict[str, MatchEvent] = {}
    resolutions: dict[str, int] = {}
    invalid_xg = 0
    missing_attempt_ids = 0
    orphan_without_id = 0

    for event in items:
        details = event.details
        assert details is not None
        if event.event_type is MatchEventType.SHOT:
            if not details.shot_id:
                missing_attempt_ids += 1
            else:
                attempts[details.shot_id] = event
            if details.xg is None or not 0.0 <= details.xg <= 1.0:
                invalid_xg += 1
            continue

        if event.event_type in _SHOT_RESOLUTION_TYPES:
            # Penalty goals/saves are not resolutions of an open-play SHOT.
            if details.penalty is True:
                continue
            if details.shot_id:
                resolutions[details.shot_id] = resolutions.get(details.shot_id, 0) + 1
            elif event.event_type in {
                MatchEventType.GOAL,
                MatchEventType.SAVE,
                MatchEventType.BLOCK,
                MatchEventType.WOODWORK,
                MatchEventType.OFF_TARGET,
            }:
                orphan_without_id += 1

    unresolved = missing_attempt_ids + sum(
        1 for shot_id in attempts if resolutions.get(shot_id, 0) == 0
    )
    orphan = orphan_without_id + sum(
        1 for shot_id in resolutions if shot_id not in attempts
    )
    duplicate = sum(max(0, count - 1) for count in resolutions.values())

    goal_events = sum(event.event_type is MatchEventType.GOAL for event in items)
    score_goals = int(home_goals) + int(away_goals)

    return MatchEventAudit(
        event_count=len(items),
        shot_attempts=sum(event.event_type is MatchEventType.SHOT for event in items),
        shot_resolutions=sum(resolutions.values()),
        unresolved_shots=unresolved,
        orphan_shot_resolutions=orphan,
        duplicate_shot_resolutions=duplicate,
        invalid_xg_shots=invalid_xg,
        goal_events=goal_events,
        score_goals=score_goals,
        score_goal_delta=score_goals - goal_events,
    )
