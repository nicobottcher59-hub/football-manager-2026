from __future__ import annotations

from dataclasses import dataclass, fields, replace

from football_manager.domain import MatchSnapshot, PlayerAttributes, PlayerMatchSnapshot, TeamMatchSnapshot


@dataclass(frozen=True, slots=True)
class BenchmarkScenario:
    """Controlled strength matchup used by the calibration harness.

    Deltas are deliberately simple in Phase 5.10A: every attribute in a side is
    shifted by the same amount. This is useful for detecting sensitivity and
    regressions, but it is not intended to model a realistic squad-quality
    distribution. Later calibration phases can add heterogeneous profiles.
    """

    name: str
    home_attribute_delta: int = 0
    away_attribute_delta: int = 0
    description: str = ""

    @property
    def strength_gap(self) -> int:
        return self.home_attribute_delta - self.away_attribute_delta


DEFAULT_BENCHMARK_SCENARIOS: tuple[BenchmarkScenario, ...] = (
    BenchmarkScenario(
        name="equal",
        description="Reference team against an identical-strength opponent.",
    ),
    BenchmarkScenario(
        name="home_weaker_10",
        home_attribute_delta=-10,
        description="Home side is 10 attribute points weaker across the controlled benchmark.",
    ),
    BenchmarkScenario(
        name="home_stronger_10",
        home_attribute_delta=10,
        description="Home side is 10 attribute points stronger across the controlled benchmark.",
    ),
)

STRENGTH_CURVE_SCENARIOS: tuple[BenchmarkScenario, ...] = tuple(
    BenchmarkScenario(
        name=(
            "equal_heterogeneous"
            if gap == 0
            else f"home_{'stronger' if gap > 0 else 'weaker'}_{abs(gap)}_heterogeneous"
        ),
        home_attribute_delta=gap,
        description=(
            "Mirrored heterogeneous squads at equal mean strength."
            if gap == 0
            else f"Mirrored heterogeneous squads with the home side shifted {gap:+d} points."
        ),
    )
    for gap in (-20, -10, -5, 0, 5, 10, 20)
)


def strength_curve_scenario(name: str) -> BenchmarkScenario:
    for scenario in STRENGTH_CURVE_SCENARIOS:
        if scenario.name == name:
            return scenario
    choices = ", ".join(item.name for item in STRENGTH_CURVE_SCENARIOS)
    raise KeyError(f"unknown strength-curve scenario {name!r}; choose one of: {choices}")


def benchmark_scenario(name: str) -> BenchmarkScenario:
    for scenario in DEFAULT_BENCHMARK_SCENARIOS:
        if scenario.name == name:
            return scenario
    choices = ", ".join(item.name for item in DEFAULT_BENCHMARK_SCENARIOS)
    raise KeyError(f"unknown calibration scenario {name!r}; choose one of: {choices}")


def _shift_group(group, delta: int):
    if delta == 0:
        return group
    values = {
        field.name: max(1, min(100, int(getattr(group, field.name)) + delta))
        for field in fields(group)
    }
    return replace(group, **values)


def shift_player_attributes(attributes: PlayerAttributes, delta: int) -> PlayerAttributes:
    """Return a clamped copy with every attribute shifted by ``delta`` points."""

    if delta == 0:
        return attributes
    return replace(
        attributes,
        technical=_shift_group(attributes.technical, delta),
        mental=_shift_group(attributes.mental, delta),
        physical=_shift_group(attributes.physical, delta),
        goalkeeping=(
            _shift_group(attributes.goalkeeping, delta)
            if attributes.goalkeeping is not None
            else None
        ),
    )


def shift_player(player: PlayerMatchSnapshot, delta: int) -> PlayerMatchSnapshot:
    if delta == 0:
        return player
    return replace(player, attributes=shift_player_attributes(player.attributes, delta))


def shift_team(team: TeamMatchSnapshot, delta: int) -> TeamMatchSnapshot:
    """Shift starter and bench attributes without mutating the immutable snapshot."""

    if delta == 0:
        return team
    return replace(
        team,
        starters=tuple(shift_player(player, delta) for player in team.starters),
        bench=tuple(shift_player(player, delta) for player in team.bench),
    )


def _stable_jitter(key: str, field_name: str, *, radius: int = 4) -> int:
    """Small deterministic profile variation independent of Python hash randomization."""

    value = sum((index + 1) * ord(char) for index, char in enumerate(f"{key}:{field_name}"))
    return value % (radius * 2 + 1) - radius


def _shape_group(group, *, key: str, team_delta: int):
    values = {
        field.name: max(1, min(100, int(getattr(group, field.name)) + team_delta + _stable_jitter(key, field.name)))
        for field in fields(group)
    }
    return replace(group, **values)


def shape_player_attributes(
    attributes: PlayerAttributes,
    *,
    profile_key: str,
    team_delta: int = 0,
) -> PlayerAttributes:
    """Create a deterministic heterogeneous skill profile around the team mean.

    Both sides use matching slot keys, so a zero-gap benchmark remains mirrored,
    while players and attributes are no longer all identical 70s.
    """

    return replace(
        attributes,
        technical=_shape_group(attributes.technical, key=f"{profile_key}:technical", team_delta=team_delta),
        mental=_shape_group(attributes.mental, key=f"{profile_key}:mental", team_delta=team_delta),
        physical=_shape_group(attributes.physical, key=f"{profile_key}:physical", team_delta=team_delta),
        goalkeeping=(
            _shape_group(attributes.goalkeeping, key=f"{profile_key}:goalkeeping", team_delta=team_delta)
            if attributes.goalkeeping is not None
            else None
        ),
    )


def shape_team_heterogeneous(team: TeamMatchSnapshot, delta: int = 0) -> TeamMatchSnapshot:
    def shaped(player: PlayerMatchSnapshot, index: int, *, bench: bool) -> PlayerMatchSnapshot:
        profile_key = (
            player.assigned_slot_id
            if player.assigned_slot_id is not None
            else f"bench:{index}:{player.assigned_position.value if player.assigned_position else 'na'}"
        )
        if bench:
            profile_key = f"bench:{index}:{player.player_id.rsplit('-', 1)[-1]}"
        return replace(
            player,
            attributes=shape_player_attributes(
                player.attributes,
                profile_key=profile_key,
                team_delta=delta,
            ),
        )

    return replace(
        team,
        starters=tuple(shaped(player, index, bench=False) for index, player in enumerate(team.starters)),
        bench=tuple(shaped(player, index, bench=True) for index, player in enumerate(team.bench)),
    )


def build_strength_curve_snapshot(
    base: MatchSnapshot,
    scenario: BenchmarkScenario,
    *,
    seed: int,
) -> MatchSnapshot:
    """Build mirrored heterogeneous squads, then apply the controlled strength gap."""

    return replace(
        base,
        match_id=f"{base.match_id}-strength-{scenario.name}-{seed}",
        seed=seed,
        home_team=shape_team_heterogeneous(base.home_team, scenario.home_attribute_delta),
        away_team=shape_team_heterogeneous(base.away_team, scenario.away_attribute_delta),
    )


def build_benchmark_snapshot(
    base: MatchSnapshot,
    scenario: BenchmarkScenario,
    *,
    seed: int,
) -> MatchSnapshot:
    """Clone ``base`` into a deterministic controlled benchmark matchup."""

    return replace(
        base,
        match_id=f"{base.match_id}-cal-{scenario.name}-{seed}",
        seed=seed,
        home_team=shift_team(base.home_team, scenario.home_attribute_delta),
        away_team=shift_team(base.away_team, scenario.away_attribute_delta),
    )
