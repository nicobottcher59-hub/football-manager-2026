"""TS-21.3: individual ageing and dated medical absences, independent of leagues.

Parameters are game-design choices, not medical/real-player predictions. No
fatigue/OVR formula is modified. Profiles and random decisions are stable across
loads. Annual loss is integrated over elapsed days, never on birthdays/load.
"""
from __future__ import annotations

from copy import copy
from dataclasses import dataclass, field, replace
from datetime import date, timedelta
from typing import TYPE_CHECKING

from .enums import Position
from .player_development import (
    INNATE_ATTRIBUTES, MAX_ANNUAL_HISTORY, MAX_MONTHLY_HISTORY,
    DevelopmentEnvironment, DevelopmentReview, attribute_values, ability_weights,
    current_ability, reference_overall, finite, require_date, stable_random, review_player,
)

if TYPE_CHECKING:
    from .player import Player

AGING_VERSION = 1
MAX_MEDICAL_HISTORY = 48


@dataclass(frozen=True, slots=True)
class InjuryEpisode:
    episode_id: str
    label: str
    started_on: date
    return_on: date | None
    source: str = 'postmatch-assessment-v1'
    # Determined once when recorded; applied only after the return date.
    sequelae: dict[str, float] = field(default_factory=dict)

    def validate(self) -> None:
        if not isinstance(self.episode_id, str) or not self.episode_id or not isinstance(self.label, str) or not self.label:
            raise ValueError('medical episode needs identity and description')
        require_date(self.started_on)
        if self.return_on is not None:
            require_date(self.return_on)
            if not 1 <= (self.return_on - self.started_on).days <= 730:
                raise ValueError('invalid medical recovery interval')
        if self.source not in ('postmatch-assessment-v1', 'imported-medical-v1', 'legacy-undated-v1'):
            raise ValueError('unsupported medical source')
        if self.return_on is None and self.source != 'legacy-undated-v1':
            raise ValueError('a new medical episode needs a return date')
        if not isinstance(self.sequelae, dict):
            raise ValueError('invalid medical sequelae')
        for key, loss in self.sequelae.items():
            if key not in ('physical.pace', 'physical.acceleration', 'physical.agility', 'physical.stamina'):
                raise ValueError('unsupported medical attribute')
            finite('medical attribute loss', loss, 0, 3)
        if self.return_on is None and self.sequelae:
            raise ValueError('cannot infer sequelae from an undated legacy injury')


@dataclass(frozen=True, slots=True)
class PlayerAging:
    seed: int
    started_on: date
    last_review: date
    physical_decline_age: float
    technical_decline_age: float
    mental_decline_age: float
    decline_rate: float
    retirement_age: float
    policy_version: int = AGING_VERSION
    loss_residuals: dict[str, float] = field(default_factory=dict)
    active_injury: InjuryEpisode | None = None
    medical_history: tuple[InjuryEpisode, ...] = ()
    injury_burden: float = 0.0
    retirement_status: str = 'active'
    retirement_requested_on: date | None = None
    retirement_checked_on: date | None = None
    retired_on: date | None = None

    def validate(self, player: Player | None = None) -> None:
        if type(self.seed) is not int or self.policy_version != AGING_VERSION:
            raise ValueError('unsupported ageing profile')
        require_date(self.started_on); require_date(self.last_review)
        if self.last_review < self.started_on:
            raise ValueError('invalid ageing chronology')
        finite('physical decline age', self.physical_decline_age, 26, 38)
        finite('technical decline age', self.technical_decline_age, self.physical_decline_age, 43)
        finite('mental decline age', self.mental_decline_age, self.technical_decline_age, 46)
        finite('decline rate', self.decline_rate, .45, 1.7)
        finite('retirement age', self.retirement_age, 32, 46)
        finite('injury burden', self.injury_burden, 0, 1.5)
        if not isinstance(self.loss_residuals, dict):
            raise ValueError('invalid loss accumulator')
        valid = dict(ability_weights(player.original_position if player is not None else Position.GK))
        for key, value in self.loss_residuals.items():
            if key not in valid or key in INNATE_ATTRIBUTES:
                raise ValueError('invalid ageing attribute')
            finite('loss residual', value, 0, 1 - 1e-10)
        if not isinstance(self.medical_history, tuple) or len(self.medical_history) > MAX_MEDICAL_HISTORY:
            raise ValueError('medical history limit exceeded')
        previous_end = None
        ids = set()
        for episode in (*self.medical_history, *((self.active_injury,) if self.active_injury else ())):
            if not isinstance(episode, InjuryEpisode):
                raise ValueError('invalid medical episode type')
            episode.validate()
            if episode.episode_id in ids or (previous_end and episode.started_on < previous_end):
                raise ValueError('duplicate or overlapping medical episodes')
            ids.add(episode.episode_id)
            previous_end = episode.return_on
        if any(e.return_on is None for e in self.medical_history):
            raise ValueError('completed medical history requires a closing date')
        if self.retirement_status not in ('active', 'requested', 'deferred', 'retired'):
            raise ValueError('invalid retirement status')
        for day in (self.retirement_requested_on, self.retirement_checked_on, self.retired_on):
            if day is not None:
                require_date(day)
                if day < self.started_on:
                    raise ValueError('retirement predates tracking')
        if (self.retirement_status == 'active') != (self.retirement_requested_on is None):
            raise ValueError('retirement request/status mismatch')
        if (self.retirement_status == 'retired') != (self.retired_on is not None):
            raise ValueError('retirement date/status mismatch')
        if self.retired_on and self.retired_on < self.retirement_requested_on:
            raise ValueError('retirement before decision')
        if player is not None and self.started_on < player.identity.birth_date:
            raise ValueError('ageing initialized before birth')


@dataclass(frozen=True, slots=True)
class RetiredPlayer:
    player: Player
    club_id: str
    retired_on: date

    def validate(self) -> None:
        require_date(self.retired_on)
        if not self.club_id or self.player.aging is None:
            raise ValueError('incomplete retired-player archive')
        self.player.aging.validate(self.player)
        if self.player.aging.retired_on != self.retired_on:
            raise ValueError('retirement archive date mismatch')
        if self.player.development is None:
            raise ValueError('retirement archive has no development data')
        self.player.development.validate(self.player)
        self.player.identity.__post_init__()
        self.player.state._validate()
        self.player.personality.validate()
        for group in (self.player.attributes.technical, self.player.attributes.mental,
                      self.player.attributes.physical, self.player.attributes.goalkeeping):
            if group is not None:
                group.__post_init__()
        if self.player.identity.birth_date > self.retired_on:
            raise ValueError('retirement precedes birth')


def initialize_aging(player: Player, on_date: date, seed: int, **overrides) -> PlayerAging:
    """One-time adapter for existing/future/real players; never edits attributes."""
    require_date(on_date)
    if player.aging is not None:
        player.aging.validate(player)
        return player.aging
    allowed = {'physical_decline_age', 'technical_decline_age', 'mental_decline_age', 'decline_rate', 'retirement_age'}
    if set(overrides) - allowed:
        raise ValueError('unknown imported ageing parameter')
    rng = stable_random(seed, player.id, 'aging-profile-v1')
    fitness = player.attributes.physical.natural_fitness
    diligence = player.personality.professionalism
    keeper = player.original_position is Position.GK
    physical = max(26.0, min(38.0, rng.triangular(27.0, 33.0, 29.6) + (1.5 if keeper else 0)
                   + (fitness - 60) / 55 + (diligence - 60) / 110))
    technical = min(43.0, physical + rng.uniform(3.0, 5.0))
    mental = min(46.0, technical + rng.uniform(1.0, 2.5))
    retirement = min(45.5, max(32.0, rng.triangular(33.0, 40.0, 36.0)
                     + (2.0 if keeper else 0) + (fitness - 60) / 60 + (diligence - 60) / 120))
    values = dict(physical_decline_age=physical, technical_decline_age=technical,
                  mental_decline_age=mental, decline_rate=rng.uniform(.75, 1.22), retirement_age=retirement)
    values.update(overrides)
    legacy = (InjuryEpisode(f'legacy:{player.id}:{on_date}', str(player.state.injury), on_date, None,
                           'legacy-undated-v1') if player.state.injury else None)
    profile = PlayerAging(seed, on_date, on_date, **values, active_injury=legacy)
    profile.validate(player)
    player.aging = profile
    return profile


def injury_availability(player: Player, start: date, end: date) -> float:
    """Fraction of the observation interval free of a recorded injury."""
    if end <= start:
        return 1.0
    profile = player.aging
    if profile is None:
        return 0.0 if player.state.injury else 1.0
    episodes = (*profile.medical_history, *((profile.active_injury,) if profile.active_injury else ()))
    days = sum(max(0, (min(end, ep.return_on or end) - max(start, ep.started_on)).days) for ep in episodes)
    if player.state.injury and profile.active_injury is None:
        return 0.0  # External/unknown flag: do not invent the absence history.
    return max(0.0, min(1.0, 1 - days / (end - start).days))


def create_injury(player: Player, on_date: date, episode_id: str, duration_days: int, label: str,
                  *, source: str = 'postmatch-assessment-v1') -> PlayerAging:
    profile = player.aging
    require_date(on_date)
    if profile is None or profile.active_injury is not None or player.state.injury is not None:
        raise ValueError('initialize ageing and close the previous injury first')
    if profile.retired_on is not None or on_date < max(profile.started_on, profile.last_review):
        raise ValueError('invalid medical registration date')
    if type(duration_days) is not int or not 1 <= duration_days <= 730:
        raise ValueError('invalid injury duration')
    rng = stable_random(profile.seed, player.id, episode_id, 'medical-consequence-v1')
    losses = {}
    # Most injuries have no attribute sequelae; long absences only create a risk.
    chance = min(.65, max(0, duration_days - 35) / 220)
    chance *= .7 + player.personality.injury_susceptibility / 100 * .6
    if rng.random() < chance:
        severity = min(2.4, duration_days / 85) * rng.uniform(.6, 1.1)
        losses = {key: min(3.0, severity * rng.uniform(.55, 1.0)) for key in
                  ('physical.pace', 'physical.acceleration', 'physical.agility', 'physical.stamina')}
    episode = InjuryEpisode(episode_id, label, on_date, on_date + timedelta(days=duration_days), source, losses)
    candidate = replace(profile, active_injury=episode)
    candidate.validate(player)
    return candidate


def _annual_loss(player: Player, key: str, age: float) -> float:
    a = player.aging
    if key in INNATE_ATTRIBUTES:
        return 0.0
    if key in ('physical.pace', 'physical.acceleration', 'physical.agility'):
        onset, rate = a.physical_decline_age, 1.1
    elif key == 'physical.stamina':
        onset, rate = a.physical_decline_age + .8, .85
    elif key.startswith('physical.'):
        onset, rate = a.physical_decline_age + 2.0, .55
    elif key in ('goalkeeping.reflexes', 'goalkeeping.one_on_ones'):
        onset, rate = a.physical_decline_age + 1.2, .80
    elif key.startswith('mental.') or key in ('goalkeeping.goalkeeper_positioning', 'goalkeeping.command_of_area'):
        onset, rate = a.mental_decline_age, .35
    else:
        onset, rate = a.technical_decline_age, .45
    years = max(0.0, age - onset)
    ramp = min(1.0, years / 2) * min(3.4, 1 + years * .18)
    return rate * ramp * a.decline_rate * (1 + .18 * a.injury_burden)


def review_career(player: Player, through: date, environment: DevelopmentEnvironment, *, mentoring=0.0):
    """Pure monthly growth + age loss + consequences, published atomically by service."""
    profile = player.aging
    if profile is None:
        raise ValueError('missing individual ageing profile')
    if profile.retired_on is not None:
        raise ValueError('retired players cannot develop')
    old_dev = player.development
    availability = injury_availability(player, old_dev.last_review, through)
    attrs, dev = review_player(player, through, environment, mentoring=mentoring, availability=availability)
    episodes = (*profile.medical_history, *((profile.active_injury,) if profile.active_injury else ()))
    age_now = (through-player.identity.birth_date).days / 365.2425
    if (age_now < min(profile.physical_decline_age, profile.retirement_age-1.1)
            and not profile.loss_residuals
            and not any(e.return_on is not None and profile.last_review < e.return_on <= through for e in episodes)):
        # Common young-player path: reuse growth output instead of rebuilding
        # every attribute group to apply a provably zero ageing loss.
        return attrs, dev, replace(profile, last_review=through)
    values = attribute_values(attrs)
    original = attribute_values(player.attributes)
    start = max(profile.started_on, profile.last_review)
    years_elapsed = max(0, (through - start).days) / 365.2425
    middle_age = ((start - player.identity.birth_date).days + max(0, (through - start).days) / 2) / 365.2425
    losses = {key: _annual_loss(player, key, middle_age) * years_elapsed for key in values}
    burden = profile.injury_burden
    episodes = (*profile.medical_history, *((profile.active_injury,) if profile.active_injury else ()))
    for episode in episodes:
        if episode.return_on is not None and start < episode.return_on <= through:
            for key, loss in episode.sequelae.items():
                losses[key] += loss
            if episode.source != 'legacy-undated-v1':
                burden = min(1.5, burden + max(0, (episode.return_on - episode.started_on).days - 28) / 365)
    residuals = dict(profile.loss_residuals)
    growth_residuals = dict(dev.residuals)
    for key, loss in losses.items():
        raw = residuals.get(key, 0) + loss
        if raw <= 0:
            continue
        # Cancel fractional learning first. Keep a single net direction; never
        # double-count hidden CA or award a later point from already lost credit.
        cancel = min(raw, growth_residuals.get(key, 0))
        raw -= cancel
        remaining_growth = growth_residuals.get(key, 0) - cancel
        if remaining_growth > 1e-12:
            growth_residuals[key] = remaining_growth
        else:
            growth_residuals.pop(key, None)
        raw = min(raw, max(0, values[key] - 1))
        whole = int(raw)
        values[key] -= whole
        remainder = raw - whole
        if remainder > 1e-12:
            residuals[key] = remainder
        else:
            residuals.pop(key, None)
    groups = {}
    for group in ('technical', 'mental', 'physical', 'goalkeeping'):
        old = getattr(attrs, group)
        updates = {k.split('.')[1]: v for k, v in values.items() if k.startswith(group + '.') and v != getattr(old, k.split('.')[1])}
        if updates:
            groups[group] = replace(old, **updates)
    attrs = replace(attrs, **groups) if groups else attrs
    probe = copy(player); probe.attributes = attrs; probe.development = dev
    ability = current_ability(probe)
    changes = {k: values[k] - v for k, v in original.items() if values[k] != v}
    reason = dev.history[-1].reason
    if any(v < 0 for v in changes.values()):
        reason = 'mixed' if any(v > 0 for v in changes.values()) else 'declining'
    elif availability < 1 and reason in ('mature', 'ceiling', 'consolidating'):
        reason = 'recovering' if availability else 'injured'
    review = DevelopmentReview(through, ability, reference_overall(probe), ability-current_ability(player), old_dev.exposure.minutes, reason)
    annual = old_dev.annual_history
    if through.month == 7:
        annual = (*annual, review)[-MAX_ANNUAL_HISTORY:]
    dev = replace(dev, residuals=growth_residuals, last_changes=changes,
                  history=(*old_dev.history, review)[-MAX_MONTHLY_HISTORY:], annual_history=annual)
    status, requested = profile.retirement_status, profile.retirement_requested_on
    age = (through-player.identity.birth_date).days / 365.2425
    # A request is considered at the season transition, never halfway through a
    # fixture. Strong participation can delay the initial decision slightly.
    target = profile.retirement_age - .7 * burden + (.55 if old_dev.exposure.minutes >= 180 else 0)
    if status == 'active' and age >= target:
        status, requested = 'requested', through
    aging = replace(profile, last_review=through, loss_residuals=residuals, injury_burden=burden,
                    retirement_status=status, retirement_requested_on=requested)
    probe.development, probe.aging = dev, aging
    dev.validate(probe); aging.validate(probe)
    return attrs, dev, aging


def aging_read_model(player: Player) -> dict:
    a = player.aging
    if a is None:
        return {'registered': False}
    active = a.active_injury
    messages = {'active': '', 'requested': 'Decided to retire at the next season transition.',
                'deferred': 'Retirement already decided; will be honored at the next season transition.',
                'retired': 'Retired; preserved in the career archive.'}
    return {'registered': True, 'status': a.retirement_status,
            'retired_on': a.retired_on.isoformat() if a.retired_on else None,
            'message': messages[a.retirement_status],
            'injury': ({'description': active.label, 'since': active.started_on.isoformat(),
                        'return_on': active.return_on.isoformat() if active.return_on else None,
                        'source': active.source} if active else None),
            'medical_history': [{'description': e.label, 'since': e.started_on.isoformat(),
                                 'return_on': e.return_on.isoformat()} for e in a.medical_history[-6:]]}
