from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum

from football_manager.domain import MatchSnapshot, PitchCondition, SurfaceType, WeatherType

from .geometry import Vector2
from .spatial_state import MatchState, PlayerAgentState, TeamSide


def _clamp(value: float, minimum: float = 0.0, maximum: float = 100.0) -> float:
    return min(max(value, minimum), maximum)


def _clamp01(value: float) -> float:
    return min(max(value, 0.0), 1.0)


class CardType(StrEnum):
    YELLOW = "yellow"
    SECOND_YELLOW_RED = "second_yellow_red"
    RED = "red"


@dataclass(frozen=True, slots=True)
class MatchContextConfig:
    base_fatigue_per_second: float = 0.00065
    running_fatigue_per_second: float = 0.0024
    sprint_reference_mps: float = 7.2
    fitness_loss_per_fatigue_point: float = 0.34
    home_pressure_resilience_points: float = 1.4
    penalty_area_depth_m: float = 16.5
    penalty_area_width_m: float = 40.32

    def __post_init__(self) -> None:
        if self.base_fatigue_per_second < 0.0:
            raise ValueError("base fatigue rate cannot be negative")
        if self.running_fatigue_per_second < 0.0:
            raise ValueError("running fatigue rate cannot be negative")
        if self.sprint_reference_mps <= 0.0:
            raise ValueError("sprint reference must be positive")
        if self.fitness_loss_per_fatigue_point < 0.0:
            raise ValueError("fitness loss factor cannot be negative")
        if self.penalty_area_depth_m <= 0.0 or self.penalty_area_width_m <= 0.0:
            raise ValueError("penalty-area dimensions must be positive")


@dataclass(frozen=True, slots=True)
class FoulAssessment:
    defender_agent_id: str
    attacker_agent_id: str
    location: Vector2
    foul_probability: float
    severity: float
    yellow_probability: float
    red_probability: float
    advantage_probability: float
    is_penalty_area: bool


class MatchContextSystem:
    """Consume frozen match context without rewriting player base attributes.

    Phase 5.8 makes weather, pitch, current match fatigue, home context and the
    referee affect concrete situations. The immutable PlayerMatchSnapshot remains
    untouched; only mutable in-match agent state evolves.
    """

    def __init__(
        self,
        snapshot: MatchSnapshot,
        config: MatchContextConfig | None = None,
    ) -> None:
        self.snapshot = snapshot
        self.config = config or MatchContextConfig()
        self.conditions = snapshot.context.conditions
        self.referee = snapshot.context.referee
        self._team_tactics = {
            TeamSide.HOME: snapshot.home_team.tactic,
            TeamSide.AWAY: snapshot.away_team.tactic,
        }

    # ------------------------------------------------------------------
    # Live condition / fatigue
    # ------------------------------------------------------------------
    def update_player_condition(self, state: MatchState, dt: float) -> None:
        if dt <= 0.0:
            raise ValueError("context timestep must be positive")

        climate = self._fatigue_climate_multiplier()
        pitch = self._fatigue_pitch_multiplier()
        for agent in state.active_players:
            physical = agent.player.attributes.physical
            speed_fraction = min(agent.velocity.magnitude / self.config.sprint_reference_mps, 1.25)
            exertion = (
                self.config.base_fatigue_per_second
                + self.config.running_fatigue_per_second * speed_fraction * speed_fraction
            )
            stamina_resistance = 1.10 - physical.stamina / 100.0 * 0.38
            natural_resistance = 1.06 - physical.natural_fitness / 100.0 * 0.22
            delta = exertion * stamina_resistance * natural_resistance * climate * pitch * dt
            agent.current_fatigue = min(100.0, agent.current_fatigue + delta)
            agent.current_fitness = max(
                0.0,
                agent.current_fitness - delta * self.config.fitness_loss_per_fatigue_point,
            )

    def movement_speed_multiplier(self, agent: PlayerAgentState) -> float:
        pitch = {
            PitchCondition.DRY: 1.00,
            PitchCondition.GOOD: 1.00,
            PitchCondition.WET: 0.985,
            PitchCondition.HEAVY: 0.94,
            PitchCondition.WATERLOGGED: 0.86,
        }[self.conditions.pitch_condition]
        surface = {
            SurfaceType.NATURAL_GRASS: 1.00,
            SurfaceType.HYBRID_GRASS: 1.00,
            SurfaceType.ARTIFICIAL: 1.01,
        }[self.snapshot.context.stadium.surface]
        weather = {
            WeatherType.CLEAR: 1.00,
            WeatherType.CLOUDY: 1.00,
            WeatherType.RAIN: 0.99,
            WeatherType.HEAVY_RAIN: 0.965,
            WeatherType.STORM: 0.94,
            WeatherType.FOG: 0.99,
            WeatherType.SNOW: 0.93,
        }[self.conditions.weather.weather_type]
        fatigue_penalty = max(agent.current_fatigue - 18.0, 0.0) * 0.0021
        fitness_penalty = max(72.0 - agent.current_fitness, 0.0) * 0.0013
        return min(max(pitch * surface * weather * (1.0 - fatigue_penalty - fitness_penalty), 0.72), 1.03)

    # ------------------------------------------------------------------
    # Ball / execution context
    # ------------------------------------------------------------------
    def ball_speed_multiplier(self, *, aerial: bool = False) -> float:
        pitch = {
            PitchCondition.DRY: 0.99,
            PitchCondition.GOOD: 1.00,
            PitchCondition.WET: 1.035,
            PitchCondition.HEAVY: 0.94,
            PitchCondition.WATERLOGGED: 0.84,
        }[self.conditions.pitch_condition]
        surface = {
            SurfaceType.NATURAL_GRASS: 1.00,
            SurfaceType.HYBRID_GRASS: 1.00,
            SurfaceType.ARTIFICIAL: 1.015,
        }[self.snapshot.context.stadium.surface]
        weather = self.conditions.weather
        if aerial:
            wind_penalty = min(weather.wind_kph / 250.0 * 0.12, 0.12)
            return max(pitch * surface * (1.0 - wind_penalty * 0.35), 0.75)
        return max(pitch * surface, 0.75)

    def execution_adjustment(
        self,
        agent: PlayerAgentState,
        *,
        pressure: float = 0.0,
        distance_m: float = 0.0,
        aerial: bool = False,
    ) -> float:
        weather = self.conditions.weather
        precipitation = weather.precipitation_intensity / 100.0
        rain_penalty = {
            WeatherType.CLEAR: 0.0,
            WeatherType.CLOUDY: 0.0,
            WeatherType.RAIN: 1.2,
            WeatherType.HEAVY_RAIN: 2.8,
            WeatherType.STORM: 4.0,
            WeatherType.FOG: 1.2,
            WeatherType.SNOW: 3.0,
        }[weather.weather_type]
        pitch_penalty = {
            PitchCondition.DRY: 0.0,
            PitchCondition.GOOD: 0.0,
            PitchCondition.WET: 0.8,
            PitchCondition.HEAVY: 2.0,
            PitchCondition.WATERLOGGED: 4.2,
        }[self.conditions.pitch_condition]
        wind_penalty = 0.0
        if aerial or distance_m >= 22.0:
            wind_penalty = min(weather.wind_kph / 18.0, 4.0) * min(distance_m / 35.0, 1.4)

        fatigue_penalty = max(agent.current_fatigue - 20.0, 0.0) * 0.045
        fatigue_penalty += max(70.0 - agent.current_fitness, 0.0) * 0.035
        home_relief = 0.0
        if agent.side is TeamSide.HOME and pressure > 0.0:
            home_relief = self.config.home_pressure_resilience_points * _clamp01(pressure)

        return home_relief - rain_penalty * (0.55 + precipitation * 0.45) - pitch_penalty - wind_penalty - fatigue_penalty

    def error_multiplier(self, *, distance_m: float, aerial: bool = False) -> float:
        weather = self.conditions.weather
        multiplier = 1.0
        if self.conditions.pitch_condition is PitchCondition.WET:
            multiplier += 0.05
        elif self.conditions.pitch_condition is PitchCondition.HEAVY:
            multiplier += 0.11
        elif self.conditions.pitch_condition is PitchCondition.WATERLOGGED:
            multiplier += 0.22

        if weather.weather_type in {WeatherType.HEAVY_RAIN, WeatherType.STORM, WeatherType.SNOW}:
            multiplier += 0.08
        if aerial or distance_m >= 22.0:
            multiplier += min(weather.wind_kph / 100.0, 0.38) * min(distance_m / 35.0, 1.2)
        return min(max(multiplier, 1.0), 1.65)

    def awareness_multiplier(self) -> float:
        weather = self.conditions.weather.weather_type
        return {
            WeatherType.CLEAR: 1.00,
            WeatherType.CLOUDY: 1.00,
            WeatherType.RAIN: 0.98,
            WeatherType.HEAVY_RAIN: 0.94,
            WeatherType.STORM: 0.91,
            WeatherType.FOG: 0.86,
            WeatherType.SNOW: 0.93,
        }[weather]

    def first_touch_adjustment(self, agent: PlayerAgentState) -> float:
        pitch_penalty = {
            PitchCondition.DRY: 0.0,
            PitchCondition.GOOD: 0.0,
            PitchCondition.WET: 1.4,
            PitchCondition.HEAVY: 2.8,
            PitchCondition.WATERLOGGED: 5.0,
        }[self.conditions.pitch_condition]
        weather = self.conditions.weather
        rain_penalty = weather.precipitation_intensity / 100.0 * 2.2
        fatigue_penalty = max(agent.current_fatigue - 25.0, 0.0) * 0.035
        return -(pitch_penalty + rain_penalty + fatigue_penalty)

    # ------------------------------------------------------------------
    # Referee / discipline
    # ------------------------------------------------------------------
    def foul_assessment(
        self,
        state: MatchState,
        defender: PlayerAgentState,
        attacker: PlayerAgentState,
    ) -> FoulAssessment:
        if defender.side is attacker.side:
            raise ValueError("foul assessment requires opponents")
        out = self._team_tactics[defender.side].team_instructions.out_of_possession
        mental = defender.player.attributes.mental
        technical = defender.player.attributes.technical
        distance = defender.location.distance_to(attacker.location)
        aggression = mental.aggression / 100.0
        team_aggression = float(out.defensive_aggression) / 100.0
        fatigue = defender.current_fatigue / 100.0
        tackle_control = technical.tackling / 100.0

        base_contact = (
            0.010
            + aggression * 0.030
            + team_aggression * 0.024
            + fatigue * 0.018
            + max(1.4 - distance, 0.0) * 0.010
            - tackle_control * 0.012
        )
        strictness = (self.referee.strictness - 50.0) / 50.0
        tolerance = (self.referee.contact_tolerance - 50.0) / 50.0
        foul_probability = base_contact * (1.0 + strictness * 0.24 - tolerance * 0.24)

        penalty_area = self.is_attacking_penalty_area(state, attacker.side, attacker.location)
        if penalty_area:
            penalty_bias = (self.referee.penalty_tendency - 50.0) / 50.0
            foul_probability *= 1.0 + penalty_bias * 0.16

        severity = _clamp01(
            0.18
            + aggression * 0.34
            + team_aggression * 0.22
            + fatigue * 0.12
            + (1.0 - tackle_control) * 0.14
        )
        card_bias = self.referee.card_tendency / 100.0
        # Card probabilities are conditional on an already-called foul. Keep
        # bookings meaningful without turning routine contact into a card flood.
        yellow_probability = _clamp01(0.02 + severity * 0.20 + card_bias * 0.08)
        red_probability = _clamp01(max(severity - 0.78, 0.0) * 0.08 + card_bias * 0.003)

        progress = self._attacking_progress(state, attacker)
        advantage_probability = _clamp01(
            self.referee.advantage_tendency / 100.0 * (0.30 + progress * 0.55)
        )
        if penalty_area:
            advantage_probability = 0.0

        return FoulAssessment(
            defender_agent_id=defender.agent_id,
            attacker_agent_id=attacker.agent_id,
            location=attacker.location,
            foul_probability=min(max(foul_probability, 0.003), 0.18),
            severity=severity,
            yellow_probability=yellow_probability,
            red_probability=red_probability,
            advantage_probability=advantage_probability,
            is_penalty_area=penalty_area,
        )

    def is_attacking_penalty_area(
        self,
        state: MatchState,
        attacking_side: TeamSide,
        location: Vector2,
    ) -> bool:
        attacking_side = TeamSide(attacking_side)
        half_width = self.config.penalty_area_width_m / 2.0
        centre_y = state.pitch.width_m / 2.0
        within_width = centre_y - half_width <= location.y <= centre_y + half_width
        if attacking_side is TeamSide.HOME:
            within_depth = location.x >= state.pitch.length_m - self.config.penalty_area_depth_m
        else:
            within_depth = location.x <= self.config.penalty_area_depth_m
        return within_width and within_depth

    def choose_card(self, assessment: FoulAssessment, random_value: float) -> CardType | None:
        random_value = _clamp01(random_value)
        if random_value <= assessment.red_probability:
            return CardType.RED
        if random_value <= assessment.red_probability + assessment.yellow_probability:
            return CardType.YELLOW
        return None

    # ------------------------------------------------------------------
    # Internal multipliers
    # ------------------------------------------------------------------
    def _fatigue_climate_multiplier(self) -> float:
        weather = self.conditions.weather
        heat = max(weather.temperature_c - 22.0, 0.0) / 18.0
        cold = max(5.0 - weather.temperature_c, 0.0) / 20.0
        humidity = max(weather.humidity - 55.0, 0.0) / 45.0
        return min(1.0 + heat * 0.28 + humidity * 0.18 + cold * 0.08, 1.55)

    def _fatigue_pitch_multiplier(self) -> float:
        pitch = {
            PitchCondition.DRY: 1.00,
            PitchCondition.GOOD: 1.00,
            PitchCondition.WET: 1.04,
            PitchCondition.HEAVY: 1.13,
            PitchCondition.WATERLOGGED: 1.24,
        }[self.conditions.pitch_condition]
        surface = {
            SurfaceType.NATURAL_GRASS: 1.00,
            SurfaceType.HYBRID_GRASS: 1.00,
            SurfaceType.ARTIFICIAL: 1.03,
        }[self.snapshot.context.stadium.surface]
        return pitch * surface

    @staticmethod
    def _attacking_progress(state: MatchState, attacker: PlayerAgentState) -> float:
        if attacker.side is TeamSide.HOME:
            return _clamp01(attacker.location.x / state.pitch.length_m)
        return _clamp01((state.pitch.length_m - attacker.location.x) / state.pitch.length_m)
