from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum

from football_manager.domain.score_validation import require_nonnegative_integer_score


class FastMatchDecision(StrEnum):
    DRAW = "draw"
    REGULATION = "regulation"
    EXTRA_TIME = "extra_time"
    PENALTIES = "penalties"


class FastCardType(StrEnum):
    YELLOW = "yellow"
    RED = "red"


@dataclass(frozen=True, slots=True)
class FastGoalEvent:
    minute: int
    club_id: str
    scorer_player_id: str
    assist_player_id: str | None
    xg: float
    extra_time: bool = False

    def __post_init__(self) -> None:
        if self.minute < 1 or self.minute > 120:
            raise ValueError("goal minute must be between 1 and 120")
        if not self.club_id.strip():
            raise ValueError("goal club_id cannot be empty")
        if not self.scorer_player_id.strip():
            raise ValueError("goal scorer_player_id cannot be empty")
        if self.assist_player_id is not None and not self.assist_player_id.strip():
            raise ValueError("goal assist_player_id cannot be blank")
        if not 0.0 <= self.xg <= 1.0:
            raise ValueError("goal xG must be between 0 and 1")


@dataclass(frozen=True, slots=True)
class FastCardEvent:
    minute: int
    club_id: str
    player_id: str
    card: FastCardType

    def __post_init__(self) -> None:
        if self.minute < 1 or self.minute > 120:
            raise ValueError("card minute must be between 1 and 120")
        if not self.club_id.strip():
            raise ValueError("card club_id cannot be empty")
        if not self.player_id.strip():
            raise ValueError("card player_id cannot be empty")
        if not isinstance(self.card, FastCardType):
            object.__setattr__(self, "card", FastCardType(self.card))


@dataclass(frozen=True, slots=True)
class FastSubstitutionEvent:
    minute: int
    club_id: str
    player_out_id: str
    player_in_id: str
    position: str
    extra_time: bool = False

    def __post_init__(self) -> None:
        if self.minute < 1 or self.minute > 120:
            raise ValueError("substitution minute must be between 1 and 120")
        if not self.club_id.strip():
            raise ValueError("substitution club_id cannot be empty")
        if not self.player_out_id.strip() or not self.player_in_id.strip():
            raise ValueError("substitution player IDs cannot be empty")
        if self.player_out_id == self.player_in_id:
            raise ValueError("substitution must replace a different player")
        if not self.position.strip():
            raise ValueError("substitution position cannot be empty")


@dataclass(frozen=True, slots=True)
class FastPenaltyKickEvent:
    sequence: int
    round_number: int
    club_id: str
    taker_player_id: str
    goalkeeper_player_id: str
    scored: bool
    sudden_death: bool
    pressure: float
    score_after_home: int
    score_after_away: int

    def __post_init__(self) -> None:
        if self.sequence < 1:
            raise ValueError("penalty sequence must be positive")
        if self.round_number < 1:
            raise ValueError("penalty round_number must be positive")
        if not self.club_id.strip():
            raise ValueError("penalty club_id cannot be empty")
        if not self.taker_player_id.strip() or not self.goalkeeper_player_id.strip():
            raise ValueError("penalty player IDs cannot be empty")
        if not 0.0 <= self.pressure <= 1.0:
            raise ValueError("penalty pressure must be between 0 and 1")
        if self.score_after_home < 0 or self.score_after_away < 0:
            raise ValueError("penalty running score cannot be negative")


@dataclass(frozen=True, slots=True)
class FastTeamStatistics:
    possession_pct: float
    passes_attempted: int
    passes_completed: int
    shots: int
    shots_on_target: int
    xg: float
    goals: int
    saves: int
    fouls: int
    yellow_cards: int
    red_cards: int
    corners: int

    def __post_init__(self) -> None:
        if not 0.0 <= self.possession_pct <= 100.0:
            raise ValueError("possession must be between 0 and 100")
        integer_fields = (
            "passes_attempted",
            "passes_completed",
            "shots",
            "shots_on_target",
            "goals",
            "saves",
            "fouls",
            "yellow_cards",
            "red_cards",
            "corners",
        )
        for field_name in integer_fields:
            if getattr(self, field_name) < 0:
                raise ValueError(f"{field_name} cannot be negative")
        if self.passes_completed > self.passes_attempted:
            raise ValueError("completed passes cannot exceed attempted passes")
        if self.shots_on_target > self.shots:
            raise ValueError("shots on target cannot exceed shots")
        if self.goals > self.shots_on_target:
            raise ValueError("goals cannot exceed shots on target")
        if self.xg < 0.0:
            raise ValueError("xG cannot be negative")

    @property
    def pass_completion_pct(self) -> float:
        if self.passes_attempted == 0:
            return 0.0
        return self.passes_completed / self.passes_attempted * 100.0


@dataclass(frozen=True, slots=True)
class FastPlayerStatistics:
    player_id: str
    club_id: str
    minutes: int
    goals: int
    assists: int
    shots: int
    shots_on_target: int
    xg: float
    passes_attempted: int
    passes_completed: int
    fouls: int
    yellow_cards: int
    red_cards: int
    match_rating: float
    condition_after: float
    fatigue_after: float

    def __post_init__(self) -> None:
        if not self.player_id.strip():
            raise ValueError("player_id cannot be empty")
        if not self.club_id.strip():
            raise ValueError("club_id cannot be empty")
        if self.minutes < 0 or self.minutes > 120:
            raise ValueError("minutes must be between 0 and 120")
        for field_name in (
            "goals",
            "assists",
            "shots",
            "shots_on_target",
            "passes_attempted",
            "passes_completed",
            "fouls",
            "yellow_cards",
            "red_cards",
        ):
            if getattr(self, field_name) < 0:
                raise ValueError(f"{field_name} cannot be negative")
        if self.shots_on_target > self.shots:
            raise ValueError("player shots on target cannot exceed shots")
        if self.goals > self.shots_on_target:
            raise ValueError("player goals cannot exceed shots on target")
        if self.passes_completed > self.passes_attempted:
            raise ValueError("player completed passes cannot exceed attempts")
        if self.xg < 0.0:
            raise ValueError("player xG cannot be negative")
        if not 1.0 <= self.match_rating <= 10.0:
            raise ValueError("match_rating must be between 1 and 10")
        if not 0.0 <= self.condition_after <= 100.0:
            raise ValueError("condition_after must be between 0 and 100")
        if not 0.0 <= self.fatigue_after <= 100.0:
            raise ValueError("fatigue_after must be between 0 and 100")

    @property
    def pass_completion_pct(self) -> float:
        if self.passes_attempted == 0:
            return 0.0
        return self.passes_completed / self.passes_attempted * 100.0


@dataclass(frozen=True, slots=True)
class FastTacticalEvent:
    minute: int
    club_id: str
    plan: str
    name: str
    applied: bool
    condition: str
    own_goals: int
    opponent_goals: int

    def __post_init__(self) -> None:
        if type(self.minute) is not int or not 1 <= self.minute <= 119:
            raise ValueError("invalid plan event minute")
        if self.plan not in ('A', 'B', 'C') or not self.club_id or not self.name:
            raise ValueError("invalid plan event identity")
        if type(self.applied) is not bool or self.condition not in ('always', 'leading', 'level', 'trailing'):
            raise ValueError("invalid plan event condition")
        require_nonnegative_integer_score(self.own_goals, 'own_goals')
        require_nonnegative_integer_score(self.opponent_goals, 'opponent_goals')


@dataclass(frozen=True, slots=True)
class FastRoleSegment:
    club_id: str
    player_id: str
    slot_id: str
    position: str
    role_id: str
    start_minute: int
    end_minute: int

    def __post_init__(self) -> None:
        from football_manager.domain.enums import Position
        from football_manager.domain.roles import get_role
        if not self.club_id or not self.player_id or not self.slot_id:
            raise ValueError("invalid role segment identity")
        if type(self.start_minute) is not int or type(self.end_minute) is not int or not 0 <= self.start_minute < self.end_minute <= 120:
            raise ValueError("invalid role segment interval")
        if not get_role(self.role_id).supports(Position(self.position)):
            raise ValueError("role segment is incompatible with its position")

    @property
    def minutes(self) -> int:
        return self.end_minute - self.start_minute


@dataclass(frozen=True, slots=True)
class FastMatchResult:
    match_id: str
    home_club_id: str
    away_club_id: str
    home_goals: int
    away_goals: int
    aggregate_home_goals: int
    aggregate_away_goals: int
    winner_club_id: str | None
    decision: FastMatchDecision
    penalties_home: int
    penalties_away: int
    regulation_home_goals: int
    regulation_away_goals: int
    extra_time_home_goals: int
    extra_time_away_goals: int
    statistics_home: FastTeamStatistics
    statistics_away: FastTeamStatistics
    goals: tuple[FastGoalEvent, ...]
    cards: tuple[FastCardEvent, ...]
    substitutions: tuple[FastSubstitutionEvent, ...]
    penalty_kicks: tuple[FastPenaltyKickEvent, ...]
    player_statistics: tuple[FastPlayerStatistics, ...]
    tactical_events: tuple[FastTacticalEvent, ...] = ()
    role_segments: tuple[FastRoleSegment, ...] = ()

    def __post_init__(self) -> None:
        if not self.match_id.strip():
            raise ValueError("match_id cannot be empty")
        if not self.home_club_id.strip() or not self.away_club_id.strip():
            raise ValueError("result club IDs cannot be empty")
        if self.home_club_id == self.away_club_id:
            raise ValueError("home and away clubs must be different")
        for field_name in (
            "home_goals",
            "away_goals",
            "aggregate_home_goals",
            "aggregate_away_goals",
            "penalties_home",
            "penalties_away",
            "regulation_home_goals",
            "regulation_away_goals",
            "extra_time_home_goals",
            "extra_time_away_goals",
        ):
            require_nonnegative_integer_score(getattr(self, field_name), field_name)
        if not isinstance(self.decision, FastMatchDecision):
            object.__setattr__(self, "decision", FastMatchDecision(self.decision))
        if self.statistics_home.goals != self.home_goals:
            raise ValueError("home statistics goals must match final score")
        if self.statistics_away.goals != self.away_goals:
            raise ValueError("away statistics goals must match final score")
        if self.regulation_home_goals + self.extra_time_home_goals != self.home_goals:
            raise ValueError("home regulation + extra-time goals must match final score")
        if self.regulation_away_goals + self.extra_time_away_goals != self.away_goals:
            raise ValueError("away regulation + extra-time goals must match final score")
        if self.decision is FastMatchDecision.PENALTIES:
            if self.penalties_home == self.penalties_away:
                raise ValueError("a penalty shootout must produce a winner")
            if not self.penalty_kicks:
                raise ValueError("penalty decision requires penalty kick events")
        elif self.penalties_home or self.penalties_away or self.penalty_kicks:
            raise ValueError("penalty data is only valid for penalty decisions")
        if abs((self.statistics_home.possession_pct + self.statistics_away.possession_pct) - 100.0) > 0.11:
            raise ValueError("team possession must sum to 100")
        home_goal_events = sum(goal.club_id == self.home_club_id for goal in self.goals)
        away_goal_events = sum(goal.club_id == self.away_club_id for goal in self.goals)
        if home_goal_events != self.home_goals or away_goal_events != self.away_goals:
            raise ValueError("goal events must match final score")
        if self.winner_club_id is not None and self.winner_club_id not in {
            self.home_club_id,
            self.away_club_id,
        }:
            raise ValueError("winner_club_id must belong to this match")
        # Two-legged ties are decided by their aggregate score, not just
        # this leg's goals. Penalty shootouts decide aggregate draws only.
        if self.decision is FastMatchDecision.PENALTIES:
            if self.aggregate_home_goals != self.aggregate_away_goals:
                raise ValueError("penalties require a tied aggregate score")
            expected_winner = (self.home_club_id if self.penalties_home > self.penalties_away
                               else self.away_club_id)
        elif self.aggregate_home_goals > self.aggregate_away_goals:
            expected_winner = self.home_club_id
        elif self.aggregate_away_goals > self.aggregate_home_goals:
            expected_winner = self.away_club_id
        else:
            expected_winner = None
        if self.decision is FastMatchDecision.DRAW and expected_winner is not None:
            raise ValueError("draw decision requires a tied aggregate score")
        if self.decision in (FastMatchDecision.REGULATION, FastMatchDecision.EXTRA_TIME) and expected_winner is None:
            raise ValueError("non-draw decision requires an aggregate winner")
        if self.winner_club_id != expected_winner:
            raise ValueError("winner_club_id contradicts aggregate or penalty score")
        clubs = {self.home_club_id, self.away_club_id}
        for event in self.tactical_events:
            if not isinstance(event, FastTacticalEvent) or event.club_id not in clubs:
                raise ValueError("invalid tactical event club")
            event.__post_init__()
        if self.role_segments:
            by_player = {}
            for segment in self.role_segments:
                if not isinstance(segment, FastRoleSegment) or segment.club_id not in clubs:
                    raise ValueError("invalid role segment")
                segment.__post_init__()
                by_player.setdefault((segment.club_id, segment.player_id), []).append(segment)
            stats = {(p.club_id, p.player_id): p for p in self.player_statistics}
            for key, segments in by_player.items():
                segments.sort(key=lambda x: x.start_minute)
                if key not in stats or sum(s.minutes for s in segments) != stats[key].minutes:
                    raise ValueError("role segments must match actual played minutes")
                if any(a.end_minute > b.start_minute for a, b in zip(segments, segments[1:])):
                    raise ValueError("overlapping player role segments")
            if set(by_player) != {k for k, v in stats.items() if v.minutes > 0}:
                raise ValueError("role segments must cover every participant")

    @property
    def total_goals(self) -> int:
        return self.home_goals + self.away_goals

    def statistics_for(self, club_id: str) -> FastTeamStatistics:
        if club_id == self.home_club_id:
            return self.statistics_home
        if club_id == self.away_club_id:
            return self.statistics_away
        raise KeyError(f"club {club_id!r} is not part of match {self.match_id!r}")

    def player_stat(self, player_id: str, *, club_id: str | None = None) -> FastPlayerStatistics:
        """Find match statistics without confusing identical IDs at rival clubs.

        Passing club_id is recommended. Legacy ID-only lookups still work if
        unambiguous; collisions raise rather than returning the wrong team.
        """
        matches = [item for item in self.player_statistics
                   if item.player_id == player_id
                   and (club_id is None or item.club_id == club_id)]
        if len(matches) == 1:
            return matches[0]
        if len(matches) > 1:
            raise ValueError(f"ambiguous player ID {player_id!r}; pass club_id")
        raise KeyError(f"player {player_id!r} has no fast-match statistics"
                       + (f" for club {club_id!r}" if club_id else ""))
