from __future__ import annotations

from dataclasses import dataclass
from functools import lru_cache
from typing import TYPE_CHECKING

from .attributes import PlayerAttributes
from .enums import Foot, Position
from .validation import validate_range

if TYPE_CHECKING:
    from .player import Player


# TS-21.1.1: bounded memoization of pure numeric modifiers only. All mutable
# player state is still read on every rating call; no OVR/ACT formula changes.
_RATING_MIN = 1.0
_RATING_MAX = 100.0
_CONTEXT_NEUTRAL = 65.0
_CONDITION_PENALTY_START = 75.0
_POSITION_FAMILIARITY_MAX_PENALTY = 14.0

# Side/foot is deliberately a small modifier. Position/role attributes are the
# main source of OVR; familiarity is secondary; dominant foot is a tie-breaker.
_RIGHT_SIDE_POSITIONS = frozenset({Position.RB, Position.RWB, Position.RW})
_LEFT_SIDE_POSITIONS = frozenset({Position.LB, Position.LWB, Position.LW})
_RIGHT_HALF_POSITIONS = frozenset({Position.RCB, Position.RCM})
_LEFT_HALF_POSITIONS = frozenset({Position.LCB, Position.LCM})
_INVERTED_ROLES = frozenset(
    {
        "inverted_fullback",
        "inverted_wingback",
        "inverted_winger",
        "inside_forward",
    }
)


@dataclass(frozen=True, slots=True)
class CurrentRatingContext:
    """Context required to estimate OVR-in-role and current effective level.

    ``overall`` is contextual: it answers how good this player is for this
    position/role assignment. ACT then applies the short/medium-term execution
    layer (form, confidence, condition, learned role/tactic familiarity and
    chemistry). Position familiarity belongs to OVR, so it is not penalised a
    second time inside ACT.
    """

    assigned_position: Position | None = None
    role_id: str | None = None
    tactic_id: str | None = None
    chemistry: float = _CONTEXT_NEUTRAL

    def __post_init__(self) -> None:
        validate_range("chemistry", self.chemistry, 0.0, 100.0)
        if self.role_id is not None and not self.role_id.strip():
            raise ValueError("role_id cannot be empty")
        if self.tactic_id is not None and not self.tactic_id.strip():
            raise ValueError("tactic_id cannot be empty")


@dataclass(frozen=True, slots=True)
class OverallRatingBreakdown:
    overall: float
    attribute_fit: float
    position_familiarity: float
    position_adjustment: float
    side_adjustment: float
    position: Position
    role_id: str


@dataclass(frozen=True, slots=True)
class PlayerRatingBreakdown:
    overall: float
    current: float
    adjustments: tuple[tuple[str, float], ...]
    overall_components: tuple[tuple[str, float], ...] = ()

    def adjustment(self, name: str) -> float:
        for adjustment_name, value in self.adjustments:
            if adjustment_name == name:
                return value
        raise KeyError(name)

    def overall_component(self, name: str) -> float:
        for component_name, value in self.overall_components:
            if component_name == name:
                return value
        raise KeyError(name)


def _attribute_value(attributes: PlayerAttributes, path: str) -> float:
    group_name, attribute_name = path.split(".", maxsplit=1)
    group = getattr(attributes, group_name)
    if group is None:
        # An outfielder used as a goalkeeper must not inherit a generic outfield
        # average as specialist goalkeeping ability.
        return 1.0
    return float(getattr(group, attribute_name))


def _weighted_rating(
    attributes: PlayerAttributes,
    weights: tuple[tuple[str, float], ...],
) -> float:
    weighted_total = 0.0
    total_weight = 0.0
    for path, weight in weights:
        weighted_total += _attribute_value(attributes, path) * weight
        total_weight += weight
    return weighted_total / total_weight


@lru_cache(maxsize=8192)
def _position_familiarity_adjustment(score: float, adaptability: float) -> float:
    """Bounded OVR penalty for spatial unfamiliarity.

    Attributes remain the dominant driver. A completely alien position can cost
    meaningful OVR, but a mirrored/nearby position only costs a small amount.
    Adaptability softens the penalty without creating a bonus by itself.
    """

    score = validate_range("position familiarity", score, 0.0, 100.0)
    adaptability = validate_range("adaptability", adaptability, 0.0, 100.0)
    missing = (100.0 - score) / 100.0
    penalty = -(missing**1.5) * _POSITION_FAMILIARITY_MAX_PENALTY
    adaptability_multiplier = 1.0 + ((_CONTEXT_NEUTRAL - adaptability) / 300.0)
    adaptability_multiplier = max(0.85, min(1.22, adaptability_multiplier))
    return penalty * adaptability_multiplier


def _preferred_side_foot(position: Position, role_id: str) -> Foot | None:
    if position in _RIGHT_SIDE_POSITIONS:
        regular = Foot.RIGHT
    elif position in _LEFT_SIDE_POSITIONS:
        regular = Foot.LEFT
    elif position in _RIGHT_HALF_POSITIONS:
        return Foot.RIGHT
    elif position in _LEFT_HALF_POSITIONS:
        return Foot.LEFT
    else:
        return None

    if role_id in _INVERTED_ROLES:
        return Foot.LEFT if regular is Foot.RIGHT else Foot.RIGHT
    return regular


@lru_cache(maxsize=8192)
def _side_adjustment_for_foot(dominant: Foot, position: Position, role_id: str) -> float:
    preferred = _preferred_side_foot(position, role_id)
    if preferred is None or dominant is Foot.BOTH or dominant is preferred:
        return 0.0
    if position in _RIGHT_HALF_POSITIONS or position in _LEFT_HALF_POSITIONS:
        return -0.15
    return -0.25


def calculate_assignment_overall(
    *,
    attributes: PlayerAttributes,
    dominant_foot: Foot,
    position_familiarity: float,
    adaptability: float,
    position: Position,
    role_id: str,
) -> OverallRatingBreakdown:
    """Pure contextual OVR calculation usable by players and match snapshots."""

    from .roles import get_role

    definition = get_role(role_id)
    if not definition.supports(position):
        raise ValueError(
            f"role {definition.role_id!r} is not compatible with position {position.value}"
        )
    attribute_fit = _weighted_rating(attributes, definition.attribute_weights)
    position_adjustment = _position_familiarity_adjustment(position_familiarity, adaptability)
    side_adjustment = _side_adjustment_for_foot(dominant_foot, position, definition.role_id)
    rating = attribute_fit + position_adjustment + side_adjustment
    overall = round(max(_RATING_MIN, min(_RATING_MAX, rating)), 1)
    return OverallRatingBreakdown(
        overall=overall,
        attribute_fit=round(attribute_fit, 1),
        position_familiarity=round(position_familiarity, 1),
        position_adjustment=round(position_adjustment, 2),
        side_adjustment=round(side_adjustment, 2),
        position=position,
        role_id=definition.role_id,
    )


def calculate_overall_breakdown(
    player: Player,
    assigned_position: Position | None = None,
    role_id: str | None = None,
) -> OverallRatingBreakdown:
    """Return contextual OVR for one position/role assignment.

    OVR is intentionally not a permanent hidden ability number. The player's
    attributes are permanent inputs; OVR is the derived answer to "how good is
    this player at the job I am asking him to do?". This means the same centre-
    back can rate much better as a defensive full-back or anchor than as a winger
    when his actual attributes support those jobs.
    """

    from .roles import default_role_for_position, get_role

    position = assigned_position or player.primary_position
    definition = (
        default_role_for_position(position)
        if role_id is None
        else get_role(role_id)
    )
    return calculate_assignment_overall(
        attributes=player.attributes,
        dominant_foot=player.identity.dominant_foot,
        position_familiarity=player.familiarity_for(position),
        adaptability=float(player.attributes.mental.adaptability),
        position=position,
        role_id=definition.role_id,
    )


def calculate_overall(
    player: Player,
    assigned_position: Position | None = None,
    role_id: str | None = None,
) -> float:
    return calculate_overall_breakdown(player, assigned_position, role_id).overall


@lru_cache(maxsize=8192)
def _bidirectional_adjustment(
    score: float,
    *,
    max_penalty: float,
    max_bonus: float,
    neutral: float = _CONTEXT_NEUTRAL,
    penalty_exponent: float = 1.7,
    bonus_exponent: float = 1.0,
) -> float:
    """Map a contextual score around a neutral point with a soft middle.

    Most normal below-neutral values should only nudge ACT rather than destroy it.
    Penalties therefore use a curved response: the effect stays modest through
    ordinary bad spells and only approaches ``max_penalty`` near the extreme end
    of the scale. Bonuses are also bounded and never rewrite the player's OVR.
    """

    score = validate_range("rating factor", score, 0.0, 100.0)
    neutral = validate_range("neutral rating factor", neutral, 0.0, 100.0)
    if neutral <= 0.0 or neutral >= 100.0:
        raise ValueError("neutral rating factor must be between 0 and 100")
    if penalty_exponent <= 0.0 or bonus_exponent <= 0.0:
        raise ValueError("rating exponents must be positive")

    if score >= neutral:
        ratio = (score - neutral) / (100.0 - neutral)
        return (ratio**bonus_exponent) * max_bonus

    ratio = (neutral - score) / neutral
    return -(ratio**penalty_exponent) * max_penalty


@lru_cache(maxsize=8192)
def _confidence_adjustment(confidence: float) -> float:
    """Confidence is usually a modifier, but near-zero confidence can collapse.

    The 5-65 range is deliberately gentle. A player on 30 confidence is struggling,
    not suddenly half the footballer he was. Below 5, however, the curve becomes
    sharply punitive to represent a player who is psychologically devastated.
    """

    confidence = validate_range("confidence", confidence, 0.0, 100.0)
    if confidence >= _CONTEXT_NEUTRAL:
        ratio = (confidence - _CONTEXT_NEUTRAL) / (100.0 - _CONTEXT_NEUTRAL)
        return ratio * 1.2

    if confidence >= 5.0:
        ratio = (_CONTEXT_NEUTRAL - confidence) / (_CONTEXT_NEUTRAL - 5.0)
        return -(ratio**1.35) * 4.0

    collapse = (5.0 - confidence) / 5.0
    return -4.0 - collapse * 8.0


@lru_cache(maxsize=8192)
def _condition_adjustment(condition: float, max_penalty: float = 28.0) -> float:
    """Condition is one-sided: freshness prevents penalties but gives no bonus.

    No standalone bonus at 75-100. Below 75, fatigue now decays steeply
    enough for rotating a fresh substitute to matter in congested schedules.
    At 65 condition the penalty is already significant, and morale cannot
    erase it because morale uses a small bounded adjustment.
    """

    condition = validate_range("condition", condition, 0.0, 100.0)
    if condition >= _CONDITION_PENALTY_START:
        return 0.0
    missing_ratio = (_CONDITION_PENALTY_START - condition) / _CONDITION_PENALTY_START
    return -(missing_ratio**0.70) * max_penalty


def _adaptability_penalty_multiplier(adaptability: float) -> float:
    """Adaptability changes how harsh unfamiliarity is, not base OVR.

    A highly adaptable player copes better while still learning. A player with
    poor adaptability suffers more from the same unfamiliar context. Once the
    contextual familiarity is neutral or better, adaptability does not create an
    extra performance bonus by itself.
    """

    adaptability = validate_range("adaptability", adaptability, 0.0, 100.0)
    return 1.0 + ((_CONTEXT_NEUTRAL - adaptability) / 400.0)


@lru_cache(maxsize=8192)
def _familiarity_adjustment(
    score: float,
    *,
    max_penalty: float,
    max_bonus: float,
    adaptability: float | None = None,
    penalty_exponent: float = 1.7,
) -> float:
    adjustment = _bidirectional_adjustment(
        score,
        max_penalty=max_penalty,
        max_bonus=max_bonus,
        penalty_exponent=penalty_exponent,
    )
    if adjustment < 0.0 and adaptability is not None:
        adjustment *= _adaptability_penalty_multiplier(adaptability)
    return adjustment


def _state_adjustments(player: Player) -> list[tuple[str, float]]:
    state = player.state
    return [
        (
            "form",
            _bidirectional_adjustment(state.form, max_penalty=5.0, max_bonus=1.0),
        ),
        (
            "confidence",
            _confidence_adjustment(state.confidence),
        ),
        (
            "morale",
            _bidirectional_adjustment(state.effective_morale, max_penalty=2.5, max_bonus=0.4),
        ),
        ("condition", _condition_adjustment(state.condition)),
        (
            "match_sharpness",
            _bidirectional_adjustment(
                state.match_sharpness,
                max_penalty=3.0,
                max_bonus=0.6,
            ),
        ),
    ]



def _context_excellence_bonus(
    player: Player,
    context: CurrentRatingContext,
    *,
    position_score: float | None,
    role_score: float | None,
    tactic_score: float | None,
    max_bonus: float = 10.6,
) -> float:
    """Reward exceptional total alignment without letting one factor inflate ACT.

    Individual positive modifiers are intentionally small. The larger upside is
    unlocked only when *every* relevant dimension is well above neutral at the
    same time. The multiplicative alignment score means a merely good value in
    one dimension sharply limits the exceptional bonus, while an all-100 context
    can unlock the full amount. Physical condition never adds points directly; it
    only gates this exceptional state, so 75-100 still has no standalone bonus.
    """

    if position_score is None or role_score is None or tactic_score is None:
        return 0.0

    scores = (
        player.state.form,
        player.state.confidence,
        player.state.effective_morale,
        player.state.match_sharpness,
        position_score,
        role_score,
        tactic_score,
        context.chemistry,
    )

    alignment = 1.0
    for score in scores:
        normalized = max(0.0, (score - _CONTEXT_NEUTRAL) / (100.0 - _CONTEXT_NEUTRAL))
        alignment *= normalized

    condition_gate = max(
        0.0,
        min(1.0, (player.state.condition - _CONDITION_PENALTY_START) / (100.0 - _CONDITION_PENALTY_START)),
    )
    alignment *= condition_gate
    return alignment * max_bonus

def _execution_scores(player: Player, context: CurrentRatingContext):
    return (
        player.familiarity_for(context.assigned_position) if context.assigned_position is not None else None,
        player.tactical_familiarity.role_score(context.role_id) if context.role_id is not None else None,
        player.tactical_familiarity.tactic_score(context.tactic_id) if context.tactic_id is not None else None,
    )


def _rounded_execution_adjustments(player: Player, context: CurrentRatingContext, scores):
    position_score, role_score, tactic_score = scores
    adjustments = _state_adjustments(player)
    adaptability = float(player.attributes.mental.adaptability)
    if role_score is not None:
        adjustments.append(("role_familiarity", _familiarity_adjustment(
            role_score, max_penalty=6.0, max_bonus=0.6,
            adaptability=adaptability, penalty_exponent=1.8)))
    if tactic_score is not None:
        adjustments.append(("tactic_familiarity", _familiarity_adjustment(
            tactic_score, max_penalty=5.0, max_bonus=0.6,
            adaptability=adaptability, penalty_exponent=1.8)))
    adjustments.append(("chemistry", _bidirectional_adjustment(
        context.chemistry, max_penalty=3.0, max_bonus=0.8)))
    adjustments.append(("context_excellence", _context_excellence_bonus(
        player, context, position_score=position_score, role_score=role_score,
        tactic_score=tactic_score)))
    return tuple((name, round(value, 2)) for name, value in adjustments)


def _rating_breakdown(overall_breakdown, rounded_adjustments):
    overall = overall_breakdown.overall
    current = overall + sum(value for _, value in rounded_adjustments)
    current = round(max(_RATING_MIN, min(_RATING_MAX, current)), 1)
    return PlayerRatingBreakdown(
        overall=overall, current=current, adjustments=rounded_adjustments,
        overall_components=(
            ("attribute_fit", overall_breakdown.attribute_fit),
            ("position_familiarity", overall_breakdown.position_familiarity),
            ("position_adjustment", overall_breakdown.position_adjustment),
            ("side_adjustment", overall_breakdown.side_adjustment),
        ),
    )


def calculate_current_rating(
    player: Player,
    context: CurrentRatingContext | None = None,
) -> PlayerRatingBreakdown:
    """Existing ACT formula: contextual OVR plus rounded execution modifiers.

    The arithmetic, modifier ordering and clamping are shared with batch
    selection; position familiarity remains in OVR, never penalized twice.
    """
    context = context or CurrentRatingContext()
    overall = calculate_overall_breakdown(player, context.assigned_position, context.role_id)
    return _rating_breakdown(overall, _rounded_execution_adjustments(
        player, context, _execution_scores(player, context)))


class CurrentRatingBatch:
    """Evaluate a read-only selection batch; discard before any state changes.

    Same numeric inputs share execution modifiers even across positions/roles.
    No formula is approximated, and this is not a permanent player cache. Its
    lifetime is one select_lineup/select_team call, so fatigue, learning, role
    edits and future development are automatically observed on the next call.
    """

    def __init__(self) -> None:
        self._overall = {}
        self._execution = {}
        self._positions = {}

    def rating(self, player: Player, context: CurrentRatingContext) -> PlayerRatingBreakdown:
        pid = id(player)
        key = (pid, context.assigned_position, context.role_id)
        if key not in self._overall:
            self._overall[key] = calculate_overall_breakdown(
                player, context.assigned_position, context.role_id)
        pkey = (pid, context.assigned_position)
        if pkey not in self._positions:
            self._positions[pkey] = (player.familiarity_for(context.assigned_position)
                                    if context.assigned_position is not None else None)
        scores = (
            self._positions[pkey],
            player.tactical_familiarity.role_score(context.role_id) if context.role_id is not None else None,
            player.tactical_familiarity.tactic_score(context.tactic_id) if context.tactic_id is not None else None,
        )
        execution_key = (pid, *scores, context.chemistry)
        if execution_key not in self._execution:
            self._execution[execution_key] = _rounded_execution_adjustments(player, context, scores)
        return _rating_breakdown(self._overall[key], self._execution[execution_key])
