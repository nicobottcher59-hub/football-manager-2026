from __future__ import annotations

from dataclasses import dataclass, fields, replace

from football_manager.domain import (
    GoalkeepingAttributes,
    Level,
    MatchSnapshot,
    PlayerMatchSnapshot,
    PlayerStateSnapshot,
    Position,
    RoleExecutionSnapshot,
    TeamInstructions,
    TeamMatchSnapshot,
)
from football_manager.domain.tactics import analyze_tactical_style


FAST_STRENGTH_GAPS: tuple[int, ...] = (-20, -10, -5, 0, 5, 10, 20)
FAST_ACT_GAPS: tuple[int, ...] = (-20, -10, 0, 10, 20)
FAST_EXECUTION_LEVELS: tuple[int, ...] = (20, 40, 65, 85, 100)


@dataclass(frozen=True, slots=True)
class FastTacticalAblation:
    name: str
    description: str
    style_changes: tuple[tuple[str, float], ...] = ()
    crossing_frequency: Level | None = None
    defensive_aggression: Level | None = None


FAST_TACTICAL_ABLATIONS: tuple[FastTacticalAblation, ...] = (
    FastTacticalAblation(
        "possession",
        "Increase possession orientation only.",
        style_changes=(("possession", 85.0),),
    ),
    FastTacticalAblation(
        "directness",
        "Increase vertical/direct play only.",
        style_changes=(("directness", 82.5),),
    ),
    FastTacticalAblation(
        "pressing",
        "Increase pressing intensity only.",
        style_changes=(("pressing", 87.5),),
    ),
    FastTacticalAblation(
        "tempo",
        "Increase tempo only.",
        style_changes=(("tempo", 82.5),),
    ),
    FastTacticalAblation(
        "width",
        "Increase attacking width only.",
        style_changes=(("width", 85.0),),
    ),
    FastTacticalAblation(
        "crossing_frequency",
        "Increase crossing frequency only.",
        crossing_frequency=Level.VERY_HIGH,
    ),
)

@dataclass(frozen=True, slots=True)
class FastTacticalMatchup:
    name: str
    description: str
    home_style_changes: tuple[tuple[str, float], ...]
    difficult_away_style_changes: tuple[tuple[str, float], ...]
    favorable_away_style_changes: tuple[tuple[str, float], ...]


FAST_TACTICAL_MATCHUPS: tuple[FastTacticalMatchup, ...] = (
    FastTacticalMatchup(
        "direct_vs_line",
        "Direct play should create more danger against a high line than a deep compact block.",
        (("directness", 85.0), ("tempo", 70.0)),
        (("defensive_depth", 20.0), ("defensive_compactness", 85.0)),
        (("defensive_depth", 85.0), ("defensive_compactness", 55.0)),
    ),
    FastTacticalMatchup(
        "possession_vs_press",
        "Possession build-up should breathe more easily against a passive block than an organised high press.",
        (("possession", 85.0), ("directness", 25.0), ("tempo", 40.0)),
        (("pressing", 90.0), ("defensive_depth", 75.0)),
        (("pressing", 20.0), ("defensive_depth", 40.0)),
    ),
    FastTacticalMatchup(
        "press_vs_build",
        "High pressing should disrupt possession build-up more than direct play that can bypass the press.",
        (("pressing", 90.0), ("defensive_depth", 75.0)),
        (("possession", 30.0), ("directness", 85.0), ("tempo", 70.0)),
        (("possession", 85.0), ("directness", 25.0), ("tempo", 40.0)),
    ),
    FastTacticalMatchup(
        "wide_vs_compact",
        "Width should be more useful for stretching a narrow compact block than an already spread defence.",
        (("width", 90.0),),
        (("defensive_compactness", 20.0), ("defensive_depth", 40.0)),
        (("defensive_compactness", 90.0), ("defensive_depth", 40.0)),
    ),
)



def tactical_ablation(name: str) -> FastTacticalAblation:
    for item in FAST_TACTICAL_ABLATIONS:
        if item.name == name:
            return item
    choices = ", ".join(item.name for item in FAST_TACTICAL_ABLATIONS)
    raise KeyError(f"unknown fast tactical ablation {name!r}; choose one of: {choices}")


def _clamp(value: float) -> float:
    return max(1.0, min(100.0, value))


def _set_group(group, level: int):
    return replace(group, **{field.name: level for field in fields(group)})


def _shift_group(group, delta: int):
    return replace(
        group,
        **{
            field.name: int(max(1, min(100, int(getattr(group, field.name)) + delta)))
            for field in fields(group)
        },
    )


def _neutral_player(player: PlayerMatchSnapshot, *, rating: int) -> PlayerMatchSnapshot:
    attributes = replace(
        player.attributes,
        technical=_set_group(player.attributes.technical, rating),
        mental=_set_group(player.attributes.mental, rating),
        physical=_set_group(player.attributes.physical, rating),
        goalkeeping=(
            GoalkeepingAttributes(
                reflexes=rating,
                handling=rating,
                one_on_ones=rating,
                aerial_reach=rating,
                command_of_area=rating,
                kicking=rating,
                throwing=rating,
                goalkeeper_positioning=rating,
            )
            if player.assigned_position is Position.GK or player.attributes.goalkeeping is not None
            else None
        ),
    )
    state = PlayerStateSnapshot(
        fitness=100.0,
        fatigue=0.0,
        form=65.0,
        morale=65.0,
        confidence=65.0,
        match_sharpness=65.0,
        injury=None,
        suspended_matches=0,
    )
    role_context = player.role_context
    if role_context is not None:
        role_context = RoleExecutionSnapshot(
            position_familiarity=65.0,
            role_familiarity=65.0,
            tactic_familiarity=65.0,
            role_suitability=float(rating),
        )
    return replace(
        player,
        attributes=attributes,
        state=state,
        overall_rating=float(rating),
        current_rating=float(rating),
        role_context=role_context,
    )


def neutralize_fast_team(team: TeamMatchSnapshot, *, rating: int = 70) -> TeamMatchSnapshot:
    instructions = TeamInstructions()
    tactic = replace(
        team.tactic,
        team_instructions=instructions,
        style=analyze_tactical_style(instructions),
    )
    return replace(
        team,
        starters=tuple(_neutral_player(player, rating=rating) for player in team.starters),
        bench=tuple(_neutral_player(player, rating=rating) for player in team.bench),
        tactic=tactic,
    )


def neutralize_fast_snapshot(base: MatchSnapshot, *, rating: int = 70, seed: int | None = None) -> MatchSnapshot:
    resolved_seed = base.seed if seed is None else seed
    return replace(
        base,
        seed=resolved_seed,
        match_id=f"{base.match_id}-fast-neutral-{resolved_seed}",
        home_team=neutralize_fast_team(base.home_team, rating=rating),
        away_team=neutralize_fast_team(base.away_team, rating=rating),
    )


def shift_player_quality(player: PlayerMatchSnapshot, delta: int) -> PlayerMatchSnapshot:
    attributes = replace(
        player.attributes,
        technical=_shift_group(player.attributes.technical, delta),
        mental=_shift_group(player.attributes.mental, delta),
        physical=_shift_group(player.attributes.physical, delta),
        goalkeeping=_shift_group(player.attributes.goalkeeping, delta) if player.attributes.goalkeeping else None,
    )
    role_context = player.role_context
    if role_context is not None:
        role_context = replace(role_context, role_suitability=_clamp(role_context.role_suitability + delta))
    return replace(
        player,
        attributes=attributes,
        overall_rating=_clamp(player.overall_rating + delta),
        current_rating=_clamp(player.current_rating + delta),
        role_context=role_context,
    )


def shift_team_quality(team: TeamMatchSnapshot, delta: int) -> TeamMatchSnapshot:
    if delta == 0:
        return team
    return replace(
        team,
        starters=tuple(shift_player_quality(player, delta) for player in team.starters),
        bench=tuple(shift_player_quality(player, delta) for player in team.bench),
    )


def shift_team_current(team: TeamMatchSnapshot, delta: int) -> TeamMatchSnapshot:
    if delta == 0:
        return team
    return replace(
        team,
        starters=tuple(replace(player, current_rating=_clamp(player.current_rating + delta)) for player in team.starters),
        bench=tuple(replace(player, current_rating=_clamp(player.current_rating + delta)) for player in team.bench),
    )


def set_team_tactical_execution(team: TeamMatchSnapshot, score: float) -> TeamMatchSnapshot:
    score = max(0.0, min(100.0, float(score)))

    def updated(player: PlayerMatchSnapshot) -> PlayerMatchSnapshot:
        if player.role_context is None:
            return player
        return replace(
            player,
            role_context=replace(
                player.role_context,
                position_familiarity=score,
                role_familiarity=score,
                tactic_familiarity=score,
            ),
        )

    return replace(
        team,
        starters=tuple(updated(player) for player in team.starters),
        bench=tuple(updated(player) for player in team.bench),
    )


def apply_tactical_ablation(team: TeamMatchSnapshot, definition: FastTacticalAblation) -> TeamMatchSnapshot:
    style = replace(team.tactic.style, **dict(definition.style_changes))
    instructions = team.tactic.team_instructions
    if definition.crossing_frequency is not None:
        instructions = replace(
            instructions,
            in_possession=replace(
                instructions.in_possession,
                crossing_frequency=definition.crossing_frequency,
            ),
        )
    if definition.defensive_aggression is not None:
        instructions = replace(
            instructions,
            out_of_possession=replace(
                instructions.out_of_possession,
                defensive_aggression=definition.defensive_aggression,
            ),
        )
    return replace(team, tactic=replace(team.tactic, style=style, team_instructions=instructions))


def with_seed(snapshot: MatchSnapshot, seed: int, *, label: str = "fast-cal") -> MatchSnapshot:
    return replace(snapshot, seed=seed, match_id=f"{snapshot.match_id}-{label}-{seed}")



_MIXED_STYLES: tuple[tuple[str, dict[str, float], Level | None], ...] = (
    ("balanced", {}, None),
    ("possession", {"possession": 82.5, "directness": 25.0, "tempo": 42.5, "risk": 45.0}, None),
    ("direct", {"possession": 30.0, "directness": 85.0, "tempo": 72.5, "risk": 65.0}, None),
    ("press", {"pressing": 87.5, "defensive_depth": 72.5, "tempo": 67.5, "risk": 60.0}, None),
    ("low_block", {"pressing": 30.0, "defensive_depth": 25.0, "defensive_compactness": 82.5, "risk": 40.0}, None),
    ("wide", {"width": 85.0, "directness": 55.0}, Level.HIGH),
)


def _apply_mixed_style(team: TeamMatchSnapshot, style_index: int) -> TeamMatchSnapshot:
    _, changes, crossing = _MIXED_STYLES[style_index % len(_MIXED_STYLES)]
    style = replace(team.tactic.style, **changes) if changes else team.tactic.style
    instructions = team.tactic.team_instructions
    if crossing is not None:
        instructions = replace(
            instructions,
            in_possession=replace(instructions.in_possession, crossing_frequency=crossing),
        )
    return replace(team, tactic=replace(team.tactic, style=style, team_instructions=instructions))


def build_mixed_snapshot(base: MatchSnapshot, *, seed: int) -> MatchSnapshot:
    """Create a deterministic heterogeneous matchup for realistic-batch checks.

    Quality, ACT, tactical style and tactical execution vary independently. The
    matchup remains fully seeded and the match itself still owns all randomness.
    """

    quality_values = (-8, -4, 0, 4, 8)
    act_values = (-6, -3, 0, 3, 6)
    execution_values = (45, 65, 85)

    hq = quality_values[(seed * 3 + 1) % len(quality_values)]
    aq = quality_values[(seed * 7 + 2) % len(quality_values)]
    ha = act_values[(seed * 5 + 3) % len(act_values)]
    aa = act_values[(seed * 11 + 1) % len(act_values)]
    he = execution_values[(seed * 13 + 1) % len(execution_values)]
    ae = execution_values[(seed * 17 + 2) % len(execution_values)]

    home = shift_team_current(shift_team_quality(base.home_team, hq), ha)
    away = shift_team_current(shift_team_quality(base.away_team, aq), aa)
    home = set_team_tactical_execution(_apply_mixed_style(home, seed), he)
    away = set_team_tactical_execution(_apply_mixed_style(away, seed // 3 + 2), ae)
    return replace(
        with_seed(base, seed, label="mixed"),
        home_team=home,
        away_team=away,
    )

def build_strength_snapshot(base: MatchSnapshot, gap: int, *, seed: int) -> MatchSnapshot:
    return replace(
        with_seed(base, seed, label=f"strength-{gap:+d}"),
        home_team=shift_team_quality(base.home_team, gap),
    )


def build_act_snapshot(base: MatchSnapshot, gap: int, *, seed: int) -> MatchSnapshot:
    return replace(
        with_seed(base, seed, label=f"act-{gap:+d}"),
        home_team=shift_team_current(base.home_team, gap),
    )


def build_execution_snapshot(base: MatchSnapshot, score: int, *, seed: int) -> MatchSnapshot:
    # Use a coherent, non-neutral plan so this experiment measures how strongly
    # familiarity/execution expresses tactical instructions. With a perfectly
    # neutral style there is intentionally almost nothing to scale.
    plan_style = replace(
        base.home_team.tactic.style,
        possession=80.0,
        pressing=80.0,
        directness=55.0,
        tempo=70.0,
        risk=60.0,
    )
    planned = replace(
        base.home_team,
        tactic=replace(base.home_team.tactic, style=plan_style),
    )
    return replace(
        with_seed(base, seed, label=f"execution-{score}"),
        home_team=set_team_tactical_execution(planned, score),
    )


def build_tactical_snapshot(
    base: MatchSnapshot,
    definition: FastTacticalAblation,
    *,
    treatment: bool,
    seed: int,
) -> MatchSnapshot:
    home = apply_tactical_ablation(base.home_team, definition) if treatment else base.home_team
    variant = "treatment" if treatment else "control"
    return replace(
        with_seed(base, seed, label=f"tactic-{definition.name}-{variant}"),
        home_team=home,
    )


def tactical_matchup(name: str) -> FastTacticalMatchup:
    for item in FAST_TACTICAL_MATCHUPS:
        if item.name == name:
            return item
    choices = ", ".join(item.name for item in FAST_TACTICAL_MATCHUPS)
    raise KeyError(f"unknown fast tactical matchup {name!r}; choose one of: {choices}")


def build_tactical_matchup_snapshot(
    base: MatchSnapshot,
    definition: FastTacticalMatchup,
    *,
    favorable: bool,
    seed: int,
    execution: float = 85.0,
) -> MatchSnapshot:
    """Build paired equal-quality fixtures where only the tactical opponent fit changes."""

    home_style = replace(base.home_team.tactic.style, **dict(definition.home_style_changes))
    away_changes = (
        definition.favorable_away_style_changes
        if favorable
        else definition.difficult_away_style_changes
    )
    away_style = replace(base.away_team.tactic.style, **dict(away_changes))
    home = replace(base.home_team, tactic=replace(base.home_team.tactic, style=home_style))
    away = replace(base.away_team, tactic=replace(base.away_team.tactic, style=away_style))
    home = set_team_tactical_execution(home, execution)
    away = set_team_tactical_execution(away, execution)
    variant = "favorable" if favorable else "difficult"
    return replace(
        with_seed(base, seed, label=f"matchup-{definition.name}-{variant}"),
        home_team=home,
        away_team=away,
    )


FAST_COACH_VS_SQUAD_SCENARIOS: tuple[str, ...] = (
    "quality_baseline",
    "better_coach",
    "wrong_plan",
)


def _with_style(team: TeamMatchSnapshot, **changes: float) -> TeamMatchSnapshot:
    return replace(team, tactic=replace(team.tactic, style=replace(team.tactic.style, **changes)))


def _coach_vs_squad_teams(
    base: MatchSnapshot,
    scenario: str,
) -> tuple[TeamMatchSnapshot, TeamMatchSnapshot]:
    """Return (stronger_team, weaker_team) for the coach-vs-squad benchmark.

    Player quality is held fixed across scenarios: the stronger side is +10
    structural quality and the weaker side stays at the neutral 70 baseline.
    Only the weaker coach's plan/execution changes between scenarios.
    """

    if scenario not in FAST_COACH_VS_SQUAD_SCENARIOS:
        choices = ", ".join(FAST_COACH_VS_SQUAD_SCENARIOS)
        raise KeyError(f"unknown coach-vs-squad scenario {scenario!r}; choose one of: {choices}")

    # The stronger team owns a consistent possession/high-line identity.  It is
    # deliberately fixed in all three scenarios so the benchmark isolates what
    # the weaker coach does differently, rather than changing both teams at once.
    stronger = shift_team_quality(base.home_team, 10)
    stronger = _with_style(
        stronger,
        possession=82.0,
        directness=28.0,
        tempo=48.0,
        pressing=62.0,
        defensive_depth=82.0,
        defensive_compactness=58.0,
        risk=58.0,
        width=55.0,
    )
    stronger = set_team_tactical_execution(stronger, 65.0)

    weaker = base.away_team
    if scenario == "quality_baseline":
        # Generic, neutrally learned plan: the quality gap should dominate.
        weaker = set_team_tactical_execution(weaker, 65.0)
    elif scenario == "better_coach":
        # Explicitly attack the high line, bypass build-up pressure, and press
        # the stronger team's possession-oriented first phase.
        weaker = _with_style(
            weaker,
            possession=30.0,
            directness=88.0,
            pressing=90.0,
            tempo=75.0,
            defensive_depth=38.0,
            defensive_compactness=72.0,
            risk=58.0,
            width=50.0,
        )
        weaker = set_team_tactical_execution(weaker, 95.0)
    else:  # wrong_plan
        # Same high execution, but a plan that plays into the stronger side's
        # strengths instead of attacking its structural weaknesses.
        weaker = _with_style(
            weaker,
            possession=88.0,
            directness=20.0,
            pressing=25.0,
            tempo=38.0,
            defensive_depth=72.0,
            defensive_compactness=55.0,
            risk=52.0,
            width=50.0,
        )
        weaker = set_team_tactical_execution(weaker, 95.0)

    return stronger, weaker


def build_coach_vs_squad_snapshot(
    base: MatchSnapshot,
    scenario: str,
    *,
    seed: int,
    weaker_home: bool,
) -> MatchSnapshot:
    """Build one leg of the paired coach-vs-squad experiment.

    Each seed is run once with the stronger team at home and once with the
    weaker team at home.  Using paired seeds across all scenarios lets the
    calibration compare tactical decisions while cancelling most home/away and
    random-sequence noise.
    """

    stronger, weaker = _coach_vs_squad_teams(base, scenario)
    if not weaker_home:
        return replace(
            with_seed(base, seed, label=f"coach-{scenario}-strong-home"),
            home_team=stronger,
            away_team=weaker,
        )

    swapped_context = replace(
        base.context,
        kits=replace(
            base.context.kits,
            home=base.context.kits.away,
            away=base.context.kits.home,
        ),
    )
    return replace(
        with_seed(base, seed, label=f"coach-{scenario}-weak-home"),
        context=swapped_context,
        home_team=weaker,
        away_team=stronger,
    )
