from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum

from .validation import validate_non_negative, validate_range


class KitType(StrEnum):
    HOME = "home"
    AWAY = "away"
    THIRD = "third"
    CUSTOM = "custom"


class WeatherType(StrEnum):
    CLEAR = "clear"
    CLOUDY = "cloudy"
    RAIN = "rain"
    HEAVY_RAIN = "heavy_rain"
    STORM = "storm"
    FOG = "fog"
    SNOW = "snow"


class PitchCondition(StrEnum):
    DRY = "dry"
    GOOD = "good"
    WET = "wet"
    HEAVY = "heavy"
    WATERLOGGED = "waterlogged"


class SurfaceType(StrEnum):
    NATURAL_GRASS = "natural_grass"
    HYBRID_GRASS = "hybrid_grass"
    ARTIFICIAL = "artificial"


class MatchDecider(StrEnum):
    """Competition-derived rule for resolving a tied match/tie.

    This is frozen competition metadata, not a user-configurable pre-match
    setting.
    """

    DRAW_ALLOWED = "draw_allowed"
    EXTRA_TIME_AND_PENALTIES = "extra_time_and_penalties"
    PENALTIES_AFTER_90 = "penalties_after_90"


@dataclass(frozen=True, slots=True)
class KitSnapshot:
    kit_id: str
    club_id: str
    name: str
    kit_type: KitType
    asset_key: str | None = None
    primary_color: str | None = None
    secondary_color: str | None = None

    def __post_init__(self) -> None:
        if not self.kit_id.strip():
            raise ValueError("kit_id cannot be empty")
        if not self.club_id.strip():
            raise ValueError("kit club_id cannot be empty")
        if not self.name.strip():
            raise ValueError("kit name cannot be empty")
        if not isinstance(self.kit_type, KitType):
            object.__setattr__(self, "kit_type", KitType(self.kit_type))
        for name in ("asset_key", "primary_color", "secondary_color"):
            value = getattr(self, name)
            if value is not None and not value.strip():
                raise ValueError(f"{name} cannot be blank when provided")


@dataclass(frozen=True, slots=True)
class MatchKitSelectionSnapshot:
    home: KitSnapshot
    away: KitSnapshot


@dataclass(frozen=True, slots=True)
class WeatherSnapshot:
    weather_type: WeatherType
    temperature_c: float
    wind_kph: float = 0.0
    humidity: float = 50.0
    precipitation_intensity: float = 0.0

    def __post_init__(self) -> None:
        if not isinstance(self.weather_type, WeatherType):
            object.__setattr__(self, "weather_type", WeatherType(self.weather_type))
        validate_range("temperature_c", float(self.temperature_c), -60.0, 60.0)
        validate_range("wind_kph", float(self.wind_kph), 0.0, 250.0)
        validate_range("humidity", float(self.humidity), 0.0, 100.0)
        validate_range(
            "precipitation_intensity",
            float(self.precipitation_intensity),
            0.0,
            100.0,
        )


@dataclass(frozen=True, slots=True)
class MatchConditionsSnapshot:
    weather: WeatherSnapshot
    pitch_condition: PitchCondition = PitchCondition.GOOD

    def __post_init__(self) -> None:
        if not isinstance(self.pitch_condition, PitchCondition):
            object.__setattr__(self, "pitch_condition", PitchCondition(self.pitch_condition))


@dataclass(frozen=True, slots=True)
class StadiumSnapshot:
    stadium_id: str
    name: str
    pitch_length_m: float
    pitch_width_m: float
    surface: SurfaceType = SurfaceType.NATURAL_GRASS
    city: str | None = None

    def __post_init__(self) -> None:
        if not self.stadium_id.strip():
            raise ValueError("stadium_id cannot be empty")
        if not self.name.strip():
            raise ValueError("stadium name cannot be empty")
        if self.pitch_length_m <= 0:
            raise ValueError("pitch_length_m must be positive")
        if self.pitch_width_m <= 0:
            raise ValueError("pitch_width_m must be positive")
        if not isinstance(self.surface, SurfaceType):
            object.__setattr__(self, "surface", SurfaceType(self.surface))
        if self.city is not None and not self.city.strip():
            raise ValueError("stadium city cannot be blank when provided")


@dataclass(frozen=True, slots=True)
class RefereeSnapshot:
    referee_id: str
    name: str
    strictness: float = 50.0
    contact_tolerance: float = 50.0
    card_tendency: float = 50.0
    penalty_tendency: float = 50.0
    advantage_tendency: float = 50.0

    def __post_init__(self) -> None:
        if not self.referee_id.strip():
            raise ValueError("referee_id cannot be empty")
        if not self.name.strip():
            raise ValueError("referee name cannot be empty")
        for field_name in (
            "strictness",
            "contact_tolerance",
            "card_tendency",
            "penalty_tendency",
            "advantage_tendency",
        ):
            validate_range(field_name, float(getattr(self, field_name)), 0.0, 100.0)


@dataclass(frozen=True, slots=True)
class StandingRowSnapshot:
    position: int
    club_id: str
    club_name: str
    played: int
    won: int
    drawn: int
    lost: int
    goals_for: int
    goals_against: int
    points: int

    def __post_init__(self) -> None:
        if self.position < 1:
            raise ValueError("standing position must be at least 1")
        if not self.club_id.strip():
            raise ValueError("standing club_id cannot be empty")
        if not self.club_name.strip():
            raise ValueError("standing club_name cannot be empty")
        for field_name in (
            "played",
            "won",
            "drawn",
            "lost",
            "goals_for",
            "goals_against",
            "points",
        ):
            validate_non_negative(field_name, getattr(self, field_name))

    @property
    def goal_difference(self) -> int:
        return self.goals_for - self.goals_against


@dataclass(frozen=True, slots=True)
class CupTieContextSnapshot:
    round_label: str
    leg_number: int
    home_aggregate_goals_before_match: int = 0
    away_aggregate_goals_before_match: int = 0

    def __post_init__(self) -> None:
        if not self.round_label.strip():
            raise ValueError("cup round_label cannot be empty")
        if self.leg_number < 1:
            raise ValueError("cup leg_number must be at least 1")
        validate_non_negative(
            "home_aggregate_goals_before_match",
            self.home_aggregate_goals_before_match,
        )
        validate_non_negative(
            "away_aggregate_goals_before_match",
            self.away_aggregate_goals_before_match,
        )


@dataclass(frozen=True, slots=True)
class CompetitionContextSnapshot:
    competition_id: str
    competition_name: str
    season_label: str
    stage_label: str
    standings: tuple[StandingRowSnapshot, ...] = ()
    cup_tie: CupTieContextSnapshot | None = None
    match_decider: MatchDecider = MatchDecider.DRAW_ALLOWED
    substitution_limit: int = 5
    extra_time_additional_substitutions: int = 1
    substitution_window_limit: int = 3
    extra_time_additional_windows: int = 1

    def __post_init__(self) -> None:
        if not self.competition_id.strip():
            raise ValueError("competition_id cannot be empty")
        if not self.competition_name.strip():
            raise ValueError("competition_name cannot be empty")
        if not self.season_label.strip():
            raise ValueError("season_label cannot be empty")
        if not self.stage_label.strip():
            raise ValueError("stage_label cannot be empty")
        if not isinstance(self.match_decider, MatchDecider):
            object.__setattr__(self, "match_decider", MatchDecider(self.match_decider))
        if self.substitution_limit < 0:
            raise ValueError("substitution_limit cannot be negative")
        if self.extra_time_additional_substitutions < 0:
            raise ValueError("extra_time_additional_substitutions cannot be negative")
        for name in ('substitution_limit', 'extra_time_additional_substitutions',
                     'substitution_window_limit', 'extra_time_additional_windows'):
            if type(getattr(self, name)) is not int or getattr(self, name) < 0:
                raise ValueError(f'{name} must be a non-negative integer')

        positions = [row.position for row in self.standings]
        if len(set(positions)) != len(positions):
            raise ValueError("standings cannot contain duplicate positions")
        club_ids = [row.club_id for row in self.standings]
        if len(set(club_ids)) != len(club_ids):
            raise ValueError("standings cannot contain duplicate clubs")

    def standing_for(self, club_id: str) -> StandingRowSnapshot | None:
        for row in self.standings:
            if row.club_id == club_id:
                return row
        return None


@dataclass(frozen=True, slots=True)
class MatchContextSnapshot:
    kickoff: datetime
    competition: CompetitionContextSnapshot
    stadium: StadiumSnapshot
    conditions: MatchConditionsSnapshot
    referee: RefereeSnapshot
    kits: MatchKitSelectionSnapshot

    def __post_init__(self) -> None:
        if self.kickoff.tzinfo is None or self.kickoff.utcoffset() is None:
            raise ValueError("kickoff must be timezone-aware")
