"""TS-21.2: data-source-independent, deterministic individual development.

Design parameters, not empirical football forecasts. CA is a stable attribute
budget, not OVR/ACT. PA is private. No club/division/name or match RNG appears in
these rules. Ageing losses and retirement are composed by TS-21.3; youth intake remains separate.
"""
from __future__ import annotations

from dataclasses import dataclass, field, fields, replace
from datetime import date
from functools import lru_cache
from hashlib import sha256
from math import exp, isfinite
from random import Random
from typing import TYPE_CHECKING

from .enums import Position
from .attributes import PlayerAttributes

if TYPE_CHECKING:
    from .player import Player

POLICY_VERSION = 1
FOCUSES = ('balanced', 'technical', 'mental', 'physical')
# Persist summaries rather than replaying matches or storing 35 attributes/month.
MAX_MONTHLY_HISTORY = 12
MAX_ANNUAL_HISTORY = 40
INNATE_ATTRIBUTES = frozenset({'physical.natural_fitness', 'mental.aggression', 'mental.bravery'})


def _get_role(role_id):
    from .roles import get_role
    return get_role(role_id)


def require_date(value: date) -> None:
    if type(value) is not date:
        raise ValueError('development requires a calendar date')


def finite(name: str, value: float, low: float, high: float) -> None:
    if type(value) not in (int, float) or not isfinite(value) or not low <= value <= high:
        raise ValueError(f'{name} must be finite and within [{low}, {high}]')


def next_month(day: date) -> date:
    require_date(day)
    return date(day.year + (day.month == 12), day.month % 12 + 1, 1)


def stable_random(*parts) -> Random:
    token = '|'.join(str(p) for p in ('development-v1', *parts))
    return Random(int.from_bytes(sha256(token.encode('utf-8')).digest()[:16], 'big'))


@lru_cache(maxsize=8192)
def _aptitudes(seed: int, player_id: str, position: Position) -> dict[str, float]:
    # Pure, bounded cache: no player, attributes, condition or mutable state.
    return {key: .65 + .70 * int.from_bytes(sha256(
        f'dev-aptitude-v1:{seed}:{player_id}:{key}'.encode('utf-8')).digest()[:8], 'big') / (2**64 - 1)
        for key, _ in ability_weights(position)}


def attribute_values(attributes: PlayerAttributes) -> dict[str, int]:
    return {f'{group}.{item.name}': getattr(values, item.name)
            for group in ('technical', 'mental', 'physical', 'goalkeeping')
            if (values := getattr(attributes, group)) is not None
            for item in fields(values)}


@lru_cache(maxsize=32)
def ability_weights(position: Position) -> tuple[tuple[str, float], ...]:
    """Stable reference-position budget; all real attributes have a positive cost.

    Average the catalogue's roles at the ORIGINAL position (85%), plus a broad
    attribute base (15%). Selecting another position/role or changing condition
    cannot change CA or manufacture PA headroom. Version before changing policy.
    """
    from .attributes import TechnicalAttributes, MentalAttributes, PhysicalAttributes, GoalkeepingAttributes
    groups = [('technical', TechnicalAttributes), ('mental', MentalAttributes), ('physical', PhysicalAttributes)]
    if position is Position.GK:
        groups.append(('goalkeeping', GoalkeepingAttributes))
    weights = {f'{name}.{f.name}': 0.15 / sum(len(fields(t)) for _, t in groups)
               for name, typ in groups for f in fields(typ)}
    from .roles import roles_for_position
    roles = roles_for_position(position)
    for role in roles:
        total = sum(w for _, w in role.attribute_weights)
        for key, weight in role.attribute_weights:
            if key in weights:
                weights[key] += .85 * weight / total / len(roles)
    norm = sum(weights.values())
    return tuple((key, w / norm) for key, w in sorted(weights.items()))


def current_ability(player: Player) -> float:
    position = player.development.reference_position if player.development else player.original_position
    values = attribute_values(player.attributes)
    return max(1.0, min(100.0, sum(values.get(key, 1) * weight for key, weight in ability_weights(position))))


def reference_overall(player: Player) -> float:
    """Attribute-only OVR reference, with neutral familiarity; not match ACT."""
    from .roles import default_role_for_position
    position = player.development.reference_position if player.development else player.original_position
    role = default_role_for_position(position)
    values = attribute_values(player.attributes)
    weights = role.attribute_weights
    return round(sum(values.get(k, 1) * w for k, w in weights) / sum(w for _, w in weights), 3)


@dataclass(frozen=True, slots=True)
class DevelopmentEnvironment:
    training_quality: float = 60.0
    coaching_quality: float = 60.0
    # Neutral, explicit stand-in until training facilities/staff are implemented.
    source: str = 'provisional-neutral-v1'

    def validate(self) -> None:
        finite('training quality', self.training_quality, 0, 100)
        finite('coaching quality', self.coaching_quality, 0, 100)
        if not isinstance(self.source, str) or not self.source:
            raise ValueError('development environment requires its data source')


@dataclass(frozen=True, slots=True)
class DevelopmentExposure:
    minutes: int = 0
    appearances: int = 0
    rating_total: float = 0.0
    role_minutes: dict[str, int] = field(default_factory=dict)
    # Minutes weighted by opponent attribute quality, not league membership.
    challenge_minutes: float = 0.0

    def validate(self) -> None:
        if any(type(x) is not int or x < 0 for x in (self.minutes, self.appearances)):
            raise ValueError('invalid development participation')
        if self.minutes > 120 * self.appearances or self.appearances > 31:
            raise ValueError('inconsistent monthly participation')
        finite('ratings', self.rating_total, 0, 10 * self.appearances)
        finite('challenge minutes', self.challenge_minutes, 0, 1.25 * self.minutes)
        if not isinstance(self.role_minutes, dict):
            raise ValueError('role minutes must be a mapping')
        for role, minutes in self.role_minutes.items():
            _get_role(role)
            if type(minutes) is not int or minutes < 0:
                raise ValueError('invalid role exposure')
        if sum(self.role_minutes.values()) > self.minutes:
            raise ValueError('role exposure exceeds played minutes')


@dataclass(frozen=True, slots=True)
class DevelopmentReview:
    on_date: date
    ability: float
    overall: float
    ability_gain: float
    minutes: int
    reason: str

    def validate(self) -> None:
        require_date(self.on_date)
        finite('review ability', self.ability, 1, 100)
        finite('review overall', self.overall, 1, 100)
        finite('ability gain', self.ability_gain, -5, 5)
        if type(self.minutes) is not int or not 0 <= self.minutes <= 3720:
            raise ValueError('invalid review minutes')
        if self.reason not in ('developing', 'consolidating', 'mature', 'ceiling', 'injured', 'too_young', 'declining', 'mixed', 'recovering'):
            raise ValueError('invalid development review reason')


@dataclass(frozen=True, slots=True)
class PlayerDevelopment:
    reference_position: Position
    potential: float
    growth_peak_age: float
    growth_end_age: float
    growth_rate: float
    seed: int
    started_on: date
    last_review: date
    baseline_ability: float
    baseline_overall: float
    focus: str = 'balanced'
    source: str = 'generated-profile-v1'
    policy_version: int = POLICY_VERSION
    residuals: dict[str, float] = field(default_factory=dict)
    exposure: DevelopmentExposure = field(default_factory=DevelopmentExposure)
    history: tuple[DevelopmentReview, ...] = ()
    annual_history: tuple[DevelopmentReview, ...] = ()
    last_changes: dict[str, int] = field(default_factory=dict)

    def validate(self, player: Player | None = None) -> None:
        if self.policy_version != POLICY_VERSION or not isinstance(self.reference_position, Position):
            raise ValueError('unsupported development profile')
        finite('potential', self.potential, 1, 100)
        finite('growth peak age', self.growth_peak_age, 17, 27)
        finite('growth end age', self.growth_end_age, self.growth_peak_age + 2, 35)
        finite('growth rate', self.growth_rate, .3, 2.4)
        finite('baseline ability', self.baseline_ability, 1, 100)
        finite('baseline overall', self.baseline_overall, 1, 100)
        if self.baseline_ability > self.potential + 1e-8:
            raise ValueError('potential below initial ability')
        if type(self.seed) is not int or not isinstance(self.source, str) or not self.source:
            raise ValueError('invalid development identity/source')
        if self.focus not in FOCUSES:
            raise ValueError('unknown development focus')
        require_date(self.started_on); require_date(self.last_review)
        if self.last_review < self.started_on:
            raise ValueError('development clock before initialization')
        if self.last_review != self.started_on and self.last_review.day != 1:
            raise ValueError('reviews must close a calendar month')
        self.exposure.validate()
        weights = dict(ability_weights(self.reference_position))
        if not isinstance(self.residuals, dict) or not isinstance(self.last_changes, dict):
            raise ValueError('development progress must be a mapping')
        for key, value in self.residuals.items():
            if key not in weights or key in INNATE_ATTRIBUTES:
                raise ValueError('invalid development attribute')
            finite('fractional progress', value, 0, 1 - 1e-10)
        for key, value in self.last_changes.items():
            if key not in weights or type(value) is not int or not -5 <= value <= 5 or value == 0:
                raise ValueError('invalid recorded attribute change')
        for history, limit in ((self.history, MAX_MONTHLY_HISTORY), (self.annual_history, MAX_ANNUAL_HISTORY)):
            if not isinstance(history, tuple) or len(history) > limit:
                raise ValueError('invalid development history window')
            previous = self.started_on
            for review in history:
                review.validate()
                if not previous < review.on_date <= self.last_review:
                    raise ValueError('invalid development history chronology')
                previous = review.on_date
        if player is not None:
            if self.started_on < player.identity.birth_date:
                raise ValueError('development before birth')
            latent = current_ability(player) + sum(weights[k] * v for k, v in self.residuals.items())
            if latent > self.potential + 1e-6:
                raise ValueError('ability exceeds saved potential')


def initialize_development(player: Player, on_date: date, seed: int, *,
                           potential: float | None = None,
                           growth_peak_age: float | None = None,
                           growth_end_age: float | None = None,
                           growth_rate: float | None = None,
                           source: str = 'generated-profile-v1') -> PlayerDevelopment:
    """One-time initialization; no attribute edits or retroactive progression."""
    require_date(on_date)
    if player.development is not None:
        player.development.validate(player)
        return player.development
    age = player.age_on(on_date)
    ability = current_ability(player)
    rng = stable_random(seed, player.id, 'profile')
    roll = rng.random()
    # Diversity, not quotas: limited / ordinary / high / exceptional headroom.
    if roll < .48:
        room = rng.uniform(0, 6)
    elif roll < .83:
        room = rng.uniform(6, 17)
    elif roll < .975:
        room = rng.uniform(17, 29)
    elif roll < .9995:
        room = rng.uniform(29, 39)
    else:
        room = max(0, rng.uniform(94, 99.5) - ability)
    room *= exp(-max(0, age - 18) / 5.5)
    if age >= 30:
        room = min(room, 1.0)
    pa = min(100.0, ability + room) if potential is None else potential
    peak = (rng.triangular(18, 25, 21) + (1.6 if player.original_position is Position.GK else 0)) if growth_peak_age is None else growth_peak_age
    end = min(35.0, peak + rng.uniform(5.0, 8.0)) if growth_end_age is None else growth_end_age
    rate = rng.uniform(.7, 1.3) if growth_rate is None else growth_rate
    if growth_rate is None and roll >= .975 and age <= 21:
        rate = rng.uniform(1.35, 2.05)
    profile = PlayerDevelopment(player.original_position, pa, peak, end, rate, seed,
                                on_date, on_date, ability, reference_overall(player), source=source)
    profile.validate()
    # Validate before publication: a bad real-data import cannot half-change a player.
    if pa < ability - 1e-8:
        raise ValueError('imported potential must not be below existing ability')
    player.development = profile
    return profile


def add_match_exposure(player: Player, *, minutes: int, rating: float,
                       role_minutes: dict[str, int], challenge: float = 1.0) -> PlayerDevelopment:
    if player.development is None:
        raise ValueError('initialize development before recording participation')
    if type(minutes) is not int or not 0 <= minutes <= 120:
        raise ValueError('invalid played development minutes')
    finite('match rating', rating, 0, 10); finite('challenge', challenge, .65, 1.25)
    if minutes == 0:
        return player.development
    previous = player.development.exposure
    roles = dict(previous.role_minutes)
    if sum(role_minutes.values()) > minutes:
        raise ValueError('role segments exceed played minutes')
    for key, value in role_minutes.items():
        _get_role(key)
        if type(value) is not int or value < 0:
            raise ValueError('invalid role minutes')
        roles[key] = roles.get(key, 0) + value
    exposure = DevelopmentExposure(previous.minutes + minutes, previous.appearances + 1,
        previous.rating_total + rating, roles, previous.challenge_minutes + minutes * challenge)
    exposure.validate()
    return replace(player.development, exposure=exposure)


def growth_budget(player: Player, through: date, environment: DevelopmentEnvironment,
                  *, mentoring: float = 0.0, availability: float | None = None) -> tuple[float, str]:
    """Monthly CA budget, bounded by age, opportunity, load and remaining PA."""
    profile = player.development
    require_date(through); environment.validate(); finite('mentoring', mentoring, 0, 1)
    if profile is None or through != next_month(profile.last_review):
        raise ValueError('development reviews must be sequential month boundaries')
    age = (through - player.identity.birth_date).days / 365.2425
    if player.age_on(through) < 15:
        return 0.0, 'too_young'
    if availability is not None:
        finite('medical availability', availability, 0, 1)
    if (availability is None and player.state.injury is not None) or availability == 0:
        return 0.0, 'injured'
    if age >= profile.growth_end_age:
        return 0.0, 'mature'
    weights = dict(ability_weights(profile.reference_position))
    gap = profile.potential - current_ability(player) - sum(weights[k] * v for k, v in profile.residuals.items())
    if gap <= 1e-8:
        return 0.0, 'ceiling'
    birth = player.identity.birth_date
    try:
        fifteenth_birthday = date(birth.year + 15, birth.month, birth.day)
    except ValueError:  # Same March 1 policy as age_on for February 29 births.
        fifteenth_birthday = date(birth.year + 15, 3, 1)
    eligible_from = max(profile.last_review, fifteenth_birthday)
    months = (through - eligible_from).days / 365.2425 * 12
    if months <= 0:
        return 0.0, 'too_young'
    width = 5.0
    curve = exp(-.5 * ((age - profile.growth_peak_age) / width) ** 2)
    # Smooth taper; a birthday never produces a one-off boost or a cliff in OVR.
    curve *= min(1.0, max(0, (profile.growth_end_age - age) / 4))
    personality = player.personality
    diligence = .40 + .65 * personality.professionalism / 100 + .15 * personality.ambition / 100
    coaching = .60 + .40 * environment.coaching_quality / 60
    training = .60 + .40 * environment.training_quality / 60
    exposure = profile.exposure
    optimal = (150 if age < 18 else 240) * months
    played = exposure.challenge_minutes
    opportunity = (.68 if age < 18 else .48) + .55 * min(1.0, played / max(1, optimal))
    # Diminishing returns and overload: more matches is not always better.
    safe_load = (240 if age < 18 else 450) * months
    overload = max(0, exposure.minutes - safe_load) / max(1, safe_load)
    opportunity *= max(.35, 1 - .60 * overload)
    performance = 1.0 if not exposure.appearances else max(.92, min(1.08, 1 + (exposure.rating_total / exposure.appearances - 6.5) * .025))
    variance = stable_random(profile.seed, player.id, through.isoformat(), 'month').uniform(.85, 1.15)
    remaining = min(1, gap / 12) ** .65
    budget = 4.8 / 12 * months * profile.growth_rate * curve * remaining * diligence * coaching * training * opportunity * performance * variance
    budget *= 1 + (.05 * mentoring if age < 23 else 0)
    if availability is not None:
        budget *= availability
    # Absolute safe cap, including exceptional imported prodigies.
    return min(gap, 1.6 * months, max(0, budget)), 'developing'


def review_player(player: Player, through: date, environment: DevelopmentEnvironment,
                  *, mentoring: float = 0.0, availability: float | None = None) -> tuple[PlayerAttributes, PlayerDevelopment]:
    """Pure candidate computation. Caller publishes attributes/profile atomically."""
    profile = player.development
    budget, reason = growth_budget(player, through, environment, mentoring=mentoring, availability=availability)
    values = attribute_values(player.attributes)
    weights = dict(ability_weights(profile.reference_position))
    priorities = {}
    roles = profile.exposure.role_minutes
    role_priorities = {}
    total_minutes = sum(roles.values())
    for role_id, minutes in roles.items():
        role = _get_role(role_id)
        total_weights = sum(w for _, w in role.attribute_weights)
        for key, weight in role.attribute_weights:
            role_priorities[key] = role_priorities.get(key, 0) + weight / total_weights * minutes / max(1, total_minutes)
    age = (through - player.identity.birth_date).days / 365.2425
    aptitudes = _aptitudes(profile.seed, player.id, profile.reference_position)
    for key, weight in weights.items():
        if key not in values or key in INNATE_ATTRIBUTES or values[key] >= 100:
            continue
        group = key.split('.')[0]
        # Differentiated accumulation, not +N to every attribute. The stable
        # aptitude prevents a new lottery on save/load or on each lineup change.
        aptitude = aptitudes[key]
        age_group = (1.20 if age < 20 else .65 if age > 25 else 1.0) if group == 'physical' else (1.15 if group == 'mental' and age >= 21 else 1.0)
        focus = 1.65 if profile.focus == group else .88 if profile.focus != 'balanced' else 1.0
        priorities[key] = aptitude * age_group * focus * (.70 + 6 * role_priorities.get(key, weight))
    norm = sum(weights[key] * p for key, p in priorities.items())
    residuals = dict(profile.residuals)
    changes = {}
    if budget and norm:
        for key, priority in priorities.items():
            raw = residuals.get(key, 0) + budget * priority / norm
            # Never spend more than the remaining capacity of this attribute.
            monthly_attribute_limit = 2.5 * (through - profile.last_review).days / 30.436875
            raw = min(float(100 - values[key]), residuals.get(key, 0) + monthly_attribute_limit, raw)
            whole = int(raw)
            if whole:
                changes[key] = whole
            remainder = raw - whole
            if remainder > 1e-12:
                residuals[key] = remainder
            else:
                residuals.pop(key, None)
    groups = {}
    for group in ('technical', 'mental', 'physical', 'goalkeeping'):
        attrs = getattr(player.attributes, group)
        updates = {key.split('.')[1]: values[key] + delta for key, delta in changes.items() if key.startswith(group + '.')}
        if updates:
            groups[group] = replace(attrs, **updates)
    updated = replace(player.attributes, **groups) if groups else player.attributes
    before = current_ability(player)
    updated_values = attribute_values(updated)
    after = max(1.0, min(100.0, sum(updated_values.get(key, 1) * weight for key, weight in weights.items())))
    from .roles import default_role_for_position
    rw = default_role_for_position(profile.reference_position).attribute_weights
    overall = sum(updated_values.get(key, 1) * w for key, w in rw) / sum(w for _, w in rw)
    if reason == 'developing' and not changes:
        reason = 'consolidating'
    review = DevelopmentReview(through, after, round(overall, 3), max(0, after-before), profile.exposure.minutes, reason)
    annual = profile.annual_history
    if through.month == 7:
        annual = (*annual, review)[-MAX_ANNUAL_HISTORY:]
    candidate = replace(profile, last_review=through, residuals=residuals, exposure=DevelopmentExposure(),
        history=(*profile.history, review)[-MAX_MONTHLY_HISTORY:], annual_history=annual, last_changes=changes)
    candidate.validate()
    latent = after + sum(weights[k] * v for k, v in residuals.items())
    if latent > candidate.potential + 1e-7:
        raise ValueError('development budget exceeded potential')
    return updated, candidate
