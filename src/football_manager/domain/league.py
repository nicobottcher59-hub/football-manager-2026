from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from random import Random
from typing import Any, Iterable, Mapping, Sequence

from .competition import CompetitionEdition, CompetitionFixture, CompetitionStageKind
from .match_context import StandingRowSnapshot
from .score_validation import require_nonnegative_integer_score


class FixturePlanSource(StrEnum):
    """Where the sporting round-robin fixture order came from."""

    SEEDED = "seeded"
    GENERATED = "generated"


class LeagueTiebreaker(StrEnum):
    GOAL_DIFFERENCE = "goal_difference"
    GOALS_FOR = "goals_for"
    WINS = "wins"


@dataclass(frozen=True, slots=True)
class LeaguePointsRule:
    win: int = 3
    draw: int = 1
    loss: int = 0

    def __post_init__(self) -> None:
        if min(self.win, self.draw, self.loss) < 0:
            raise ValueError("league points cannot be negative")


@dataclass(frozen=True, slots=True)
class LeagueResult:
    fixture_id: str
    home_goals: int
    away_goals: int

    def __post_init__(self) -> None:
        if not self.fixture_id.strip():
            raise ValueError("fixture_id cannot be empty")
        require_nonnegative_integer_score(self.home_goals, "home_goals")
        require_nonnegative_integer_score(self.away_goals, "away_goals")

    def to_dict(self) -> dict[str, Any]:
        return {
            "fixture_id": self.fixture_id,
            "home_goals": self.home_goals,
            "away_goals": self.away_goals,
        }

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> "LeagueResult":
        return cls(
            fixture_id=str(data["fixture_id"]),
            home_goals=data["home_goals"],
            away_goals=data["away_goals"],
        )


@dataclass(frozen=True, slots=True)
class LeagueStandingRow:
    position: int
    club_id: str
    played: int
    won: int
    drawn: int
    lost: int
    goals_for: int
    goals_against: int
    points: int

    @property
    def goal_difference(self) -> int:
        return self.goals_for - self.goals_against

    def to_snapshot(self, *, club_name: str | None = None) -> StandingRowSnapshot:
        return StandingRowSnapshot(
            position=self.position,
            club_id=self.club_id,
            club_name=club_name or self.club_id,
            played=self.played,
            won=self.won,
            drawn=self.drawn,
            lost=self.lost,
            goals_for=self.goals_for,
            goals_against=self.goals_against,
            points=self.points,
        )


@dataclass(frozen=True, slots=True)
class RoundRobinFixturePlan:
    """Sporting round-robin plan plus provenance for season setup."""

    source: FixturePlanSource
    fixtures: tuple[CompetitionFixture, ...]
    template: "RoundRobinTemplate"

    def __post_init__(self) -> None:
        if not isinstance(self.source, FixturePlanSource):
            object.__setattr__(self, "source", FixturePlanSource(self.source))

    @classmethod
    def seeded(
        cls,
        *,
        fixtures: Sequence[CompetitionFixture],
        participant_club_ids: Sequence[str],
    ) -> "RoundRobinFixturePlan":
        normalized = tuple(fixtures)
        template = RoundRobinTemplate.from_fixtures(normalized, participant_club_ids)
        return cls(source=FixturePlanSource.SEEDED, fixtures=normalized, template=template)

    @classmethod
    def generated(
        cls,
        *,
        edition_id: str,
        stage_id: str,
        participant_club_ids: Sequence[str],
        seed: int | None = None,
    ) -> "RoundRobinFixturePlan":
        fixtures = generate_double_round_robin(
            edition_id=edition_id,
            stage_id=stage_id,
            participant_club_ids=participant_club_ids,
            seed=seed,
        )
        template = RoundRobinTemplate.from_fixtures(fixtures, participant_club_ids)
        return cls(source=FixturePlanSource.GENERATED, fixtures=fixtures, template=template)


@dataclass(frozen=True, slots=True)
class RoundRobinTemplate:
    """Round/venue structure independent of concrete club identities.

    A real first-season fixture list can be converted to this template. Later
    editions can instantiate the same sporting structure with a different slot
    assignment, including promoted/relegated clubs, without copying dates.
    """

    participant_count: int
    slot_fixtures: tuple[tuple[int, int, int], ...]

    def __post_init__(self) -> None:
        if self.participant_count < 2 or self.participant_count % 2 != 0:
            raise ValueError("round-robin template requires an even participant count >= 2")
        expected = self.participant_count * (self.participant_count - 1)
        if len(self.slot_fixtures) != expected:
            raise ValueError(
                f"round-robin template requires {expected} fixtures for {self.participant_count} clubs"
            )
        rounds = 2 * (self.participant_count - 1)
        seen_per_round: dict[int, set[int]] = {number: set() for number in range(1, rounds + 1)}
        pair_counts: dict[tuple[int, int], int] = {}
        venue_counts: set[tuple[int, int]] = set()
        for round_number, home_slot, away_slot in self.slot_fixtures:
            if round_number not in seen_per_round:
                raise ValueError("template round_number outside expected double round-robin range")
            if not (0 <= home_slot < self.participant_count) or not (
                0 <= away_slot < self.participant_count
            ):
                raise ValueError("template slot index outside participant range")
            if home_slot == away_slot:
                raise ValueError("template fixture cannot pair a slot with itself")
            if home_slot in seen_per_round[round_number] or away_slot in seen_per_round[round_number]:
                raise ValueError("template club slot appears more than once in a round")
            seen_per_round[round_number].update((home_slot, away_slot))
            pair = tuple(sorted((home_slot, away_slot)))
            pair_counts[pair] = pair_counts.get(pair, 0) + 1
            venue = (home_slot, away_slot)
            if venue in venue_counts:
                raise ValueError("template repeats the same home/away pairing")
            venue_counts.add(venue)

        expected_round_size = self.participant_count
        if any(len(slots) != expected_round_size for slots in seen_per_round.values()):
            raise ValueError("every template round must include every participant exactly once")
        if any(count != 2 for count in pair_counts.values()):
            raise ValueError("every template pairing must occur exactly twice")

    @classmethod
    def from_fixtures(
        cls,
        fixtures: Sequence[CompetitionFixture],
        participant_club_ids: Sequence[str],
    ) -> "RoundRobinTemplate":
        participants = tuple(participant_club_ids)
        validate_double_round_robin(fixtures, participants)
        slot_by_club = {club_id: index for index, club_id in enumerate(participants)}
        ordered = sorted(fixtures, key=lambda item: (item.round_number or 0, item.fixture_id))
        return cls(
            participant_count=len(participants),
            slot_fixtures=tuple(
                (
                    int(fixture.round_number or 0),
                    slot_by_club[fixture.home_club_id],
                    slot_by_club[fixture.away_club_id],
                )
                for fixture in ordered
            ),
        )

    def instantiate(
        self,
        *,
        edition_id: str,
        stage_id: str,
        participant_club_ids: Sequence[str],
        seed: int | None = None,
    ) -> tuple[CompetitionFixture, ...]:
        participants = list(participant_club_ids)
        if len(participants) != self.participant_count:
            raise ValueError("participant count does not match round-robin template")
        _validate_participants(participants)
        if seed is not None:
            Random(seed).shuffle(participants)

        fixtures = tuple(
            CompetitionFixture(
                fixture_id=(
                    f"{edition_id}-{stage_id}-r{round_number:02d}-"
                    f"m{match_number:02d}"
                ),
                edition_id=edition_id,
                stage_id=stage_id,
                home_club_id=participants[home_slot],
                away_club_id=participants[away_slot],
                round_number=round_number,
            )
            for match_number, (round_number, home_slot, away_slot) in enumerate(
                self.slot_fixtures, start=1
            )
        )
        validate_double_round_robin(fixtures, participants)
        return fixtures


def generate_double_round_robin(
    *,
    edition_id: str,
    stage_id: str,
    participant_club_ids: Sequence[str],
    seed: int | None = None,
) -> tuple[CompetitionFixture, ...]:
    """Generate a balanced sporting fixture order using the circle method.

    Dates are deliberately excluded. Phase 6.5 will place these sporting rounds
    onto the world calendar.
    """

    participants = list(participant_club_ids)
    _validate_participants(participants)
    if len(participants) % 2 != 0:
        raise ValueError("Phase 6.2 double round-robin requires an even number of clubs")
    if seed is not None:
        Random(seed).shuffle(participants)

    first_half: list[tuple[int, str, str]] = []
    rotation = list(participants)
    match_number = 1
    for round_index in range(len(participants) - 1):
        round_number = round_index + 1
        for pair_index in range(len(participants) // 2):
            left = rotation[pair_index]
            right = rotation[-(pair_index + 1)]
            if pair_index == 0:
                home, away = (left, right) if round_index % 2 == 0 else (right, left)
            else:
                home, away = (
                    (left, right)
                    if (round_index + pair_index) % 2 == 0
                    else (right, left)
                )
            first_half.append((round_number, home, away))
            match_number += 1

        # Keep one anchor and rotate the remaining slots clockwise.
        rotation = [rotation[0], rotation[-1], *rotation[1:-1]]

    fixtures: list[CompetitionFixture] = []
    sequence = 1
    for round_number, home, away in first_half:
        fixtures.append(
            CompetitionFixture(
                fixture_id=f"{edition_id}-{stage_id}-r{round_number:02d}-m{sequence:03d}",
                edition_id=edition_id,
                stage_id=stage_id,
                home_club_id=home,
                away_club_id=away,
                round_number=round_number,
            )
        )
        sequence += 1

    second_half_offset = len(participants) - 1
    for round_number, home, away in first_half:
        return_round = round_number + second_half_offset
        fixtures.append(
            CompetitionFixture(
                fixture_id=f"{edition_id}-{stage_id}-r{return_round:02d}-m{sequence:03d}",
                edition_id=edition_id,
                stage_id=stage_id,
                home_club_id=away,
                away_club_id=home,
                round_number=return_round,
            )
        )
        sequence += 1

    generated = tuple(fixtures)
    validate_double_round_robin(generated, participants)
    return generated


def validate_double_round_robin(
    fixtures: Sequence[CompetitionFixture],
    participant_club_ids: Sequence[str],
) -> None:
    participants = tuple(participant_club_ids)
    _validate_participants(participants)
    if len(participants) % 2 != 0:
        raise ValueError("double round-robin validation requires an even number of clubs")

    expected_fixture_count = len(participants) * (len(participants) - 1)
    expected_round_count = 2 * (len(participants) - 1)
    expected_matches_per_round = len(participants) // 2
    if len(fixtures) != expected_fixture_count:
        raise ValueError(
            f"double round-robin requires {expected_fixture_count} fixtures, got {len(fixtures)}"
        )

    participant_set = set(participants)
    round_clubs: dict[int, set[str]] = {
        number: set() for number in range(1, expected_round_count + 1)
    }
    round_matches: dict[int, int] = {
        number: 0 for number in range(1, expected_round_count + 1)
    }
    directed_pairings: set[tuple[str, str]] = set()
    unordered_pair_counts: dict[tuple[str, str], int] = {}
    fixture_ids: set[str] = set()

    for fixture in fixtures:
        if fixture.fixture_id in fixture_ids:
            raise ValueError("double round-robin fixture IDs must be unique")
        fixture_ids.add(fixture.fixture_id)
        if fixture.home_club_id not in participant_set or fixture.away_club_id not in participant_set:
            raise ValueError("double round-robin fixture contains unknown participant")
        if fixture.round_number is None or fixture.round_number not in round_clubs:
            raise ValueError("double round-robin fixture has invalid round_number")
        if (
            fixture.home_club_id in round_clubs[fixture.round_number]
            or fixture.away_club_id in round_clubs[fixture.round_number]
        ):
            raise ValueError("club appears more than once in the same round")
        round_clubs[fixture.round_number].update((fixture.home_club_id, fixture.away_club_id))
        round_matches[fixture.round_number] += 1

        directed = (fixture.home_club_id, fixture.away_club_id)
        if directed in directed_pairings:
            raise ValueError("same home/away pairing appears more than once")
        directed_pairings.add(directed)
        unordered = tuple(sorted(directed))
        unordered_pair_counts[unordered] = unordered_pair_counts.get(unordered, 0) + 1

    if any(count != expected_matches_per_round for count in round_matches.values()):
        raise ValueError("every round must contain the expected number of matches")
    if any(len(clubs) != len(participants) for clubs in round_clubs.values()):
        raise ValueError("every club must play exactly once per round")

    expected_pairs = len(participants) * (len(participants) - 1) // 2
    if len(unordered_pair_counts) != expected_pairs or any(
        count != 2 for count in unordered_pair_counts.values()
    ):
        raise ValueError("every pair of clubs must meet exactly twice")
    for first in participants:
        for second in participants:
            if first == second:
                continue
            if (first, second) not in directed_pairings:
                raise ValueError("every pair must meet once at each venue")


def build_league_table(
    *,
    participant_club_ids: Sequence[str],
    fixtures: Sequence[CompetitionFixture],
    results: Sequence[LeagueResult],
    points_rule: LeaguePointsRule = LeaguePointsRule(),
    tiebreakers: Sequence[LeagueTiebreaker] = (
        LeagueTiebreaker.GOAL_DIFFERENCE,
        LeagueTiebreaker.GOALS_FOR,
        LeagueTiebreaker.WINS,
    ),
) -> tuple[LeagueStandingRow, ...]:
    participants = tuple(participant_club_ids)
    _validate_participants(participants)
    fixture_by_id = {fixture.fixture_id: fixture for fixture in fixtures}
    if len(fixture_by_id) != len(fixtures):
        raise ValueError("league fixtures must have unique fixture IDs")

    normalized_tiebreakers = tuple(LeagueTiebreaker(value) for value in tiebreakers)
    if len(set(normalized_tiebreakers)) != len(normalized_tiebreakers):
        raise ValueError("league tiebreakers must be unique")

    stats = {
        club_id: {
            "played": 0,
            "won": 0,
            "drawn": 0,
            "lost": 0,
            "goals_for": 0,
            "goals_against": 0,
            "points": 0,
        }
        for club_id in participants
    }
    seen_results: set[str] = set()

    for result in results:
        if result.fixture_id in seen_results:
            raise ValueError("a league fixture cannot have more than one final result")
        seen_results.add(result.fixture_id)
        try:
            fixture = fixture_by_id[result.fixture_id]
        except KeyError as exc:
            raise ValueError(f"result references unknown fixture {result.fixture_id}") from exc
        if fixture.home_club_id not in stats or fixture.away_club_id not in stats:
            raise ValueError("result fixture contains club outside league participants")

        home = stats[fixture.home_club_id]
        away = stats[fixture.away_club_id]
        home["played"] += 1
        away["played"] += 1
        home["goals_for"] += result.home_goals
        home["goals_against"] += result.away_goals
        away["goals_for"] += result.away_goals
        away["goals_against"] += result.home_goals

        if result.home_goals > result.away_goals:
            home["won"] += 1
            away["lost"] += 1
            home["points"] += points_rule.win
            away["points"] += points_rule.loss
        elif result.home_goals < result.away_goals:
            away["won"] += 1
            home["lost"] += 1
            away["points"] += points_rule.win
            home["points"] += points_rule.loss
        else:
            home["drawn"] += 1
            away["drawn"] += 1
            home["points"] += points_rule.draw
            away["points"] += points_rule.draw

    provisional = [
        LeagueStandingRow(position=0, club_id=club_id, **club_stats)
        for club_id, club_stats in stats.items()
    ]

    def sort_key(row: LeagueStandingRow) -> tuple[Any, ...]:
        key: list[Any] = [-row.points]
        for tiebreaker in normalized_tiebreakers:
            if tiebreaker is LeagueTiebreaker.GOAL_DIFFERENCE:
                key.append(-row.goal_difference)
            elif tiebreaker is LeagueTiebreaker.GOALS_FOR:
                key.append(-row.goals_for)
            elif tiebreaker is LeagueTiebreaker.WINS:
                key.append(-row.won)
        # Stable deterministic fallback only; not intended as a sporting rule.
        key.append(row.club_id)
        return tuple(key)

    ordered = sorted(provisional, key=sort_key)
    return tuple(
        LeagueStandingRow(
            position=index,
            club_id=row.club_id,
            played=row.played,
            won=row.won,
            drawn=row.drawn,
            lost=row.lost,
            goals_for=row.goals_for,
            goals_against=row.goals_against,
            points=row.points,
        )
        for index, row in enumerate(ordered, start=1)
    )


def standings_snapshots(
    standings: Iterable[LeagueStandingRow],
    *,
    club_names: Mapping[str, str] | None = None,
) -> tuple[StandingRowSnapshot, ...]:
    names = club_names or {}
    return tuple(
        row.to_snapshot(club_name=names.get(row.club_id, row.club_id)) for row in standings
    )


def validate_round_robin_edition(edition: CompetitionEdition, stage_id: str) -> None:
    stage = edition.stage(stage_id)
    if stage.kind is not CompetitionStageKind.ROUND_ROBIN:
        raise ValueError("league stage must be ROUND_ROBIN")
    stage_participants = stage.participant_club_ids or edition.participant_club_ids
    validate_double_round_robin(edition.fixtures_for_stage(stage_id), stage_participants)


def _validate_participants(participant_club_ids: Sequence[str]) -> None:
    participants = tuple(participant_club_ids)
    if len(participants) < 2:
        raise ValueError("league requires at least two participants")
    if any(not club_id.strip() for club_id in participants):
        raise ValueError("league participant IDs cannot be empty")
    if len(set(participants)) != len(participants):
        raise ValueError("league participant IDs must be unique")
