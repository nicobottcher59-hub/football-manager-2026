"""TS-27: bounded, deterministic coach behaviour for *AI-controlled* sides.

No hidden knowledge of the human tactic, no rerolling favourable outcomes,
no roster changes. Adjusts existing score-dependent fast-sim decisions only.
"""
from __future__ import annotations

from dataclasses import dataclass, replace
from hashlib import sha256


@dataclass(frozen=True, slots=True)
class AICoach:
    club_id: str
    approach: str
    judgement: int
    variation: float

    def __post_init__(self) -> None:
        if self.approach not in ('attacking', 'cautious', 'balanced', 'pragmatic'):
            raise ValueError('unknown coach approach')
        if type(self.judgement) is not int or not 25 <= self.judgement <= 90:
            raise ValueError('coach judgement out of range')
        if not -1 <= self.variation <= 1:
            raise ValueError('coach variation out of range')


def _roll(*parts: object) -> int:
    value = '|'.join(map(str, parts)).encode('utf-8')
    return int.from_bytes(sha256(value).digest()[:8], 'big')


def coach_for_match(seed: int, club_id: str, preset: str, fixture_id: str) -> AICoach:
    if preset in ('constant_press', 'counterpress', 'wide_attack', 'direct_play'):
        approach = 'attacking'
    elif preset in ('catenaccio', 'low_block', 'direct_counter'):
        approach = 'cautious'
    elif preset in ('counter_attack', 'balanced'):
        approach = 'pragmatic'
    else:
        approach = 'balanced'
    if _roll(seed, club_id, 'coach/approach') % 6 == 0:
        approach = ('attacking', 'cautious', 'pragmatic', 'balanced')[_roll(seed, club_id, 'coach/variant') % 4]
    judgement = 35 + _roll(seed, club_id, 'coach/judgement') % 51
    variation = ((_roll(seed, club_id, fixture_id, 'coach/decision') % 2001) - 1000) / 1000.0
    return AICoach(club_id, approach, judgement, variation)


def adjusted_profile(profile, coach: AICoach, *, importance: float = 0.5, opponent_current: float = 65.0):
    """Apply small approach-dependent alterations to existing late-game levers.

    The game still determines whether a team leads/trails at each relevant
    minute. Quality reduces erratic decisions but never guarantees success.
    """
    coach.__post_init__()
    importance = max(0.0, min(1.0, importance))
    quality = (coach.judgement - 50.0) / 40.0
    noise = coach.variation * (1.0 - max(0.0, quality) * .55)
    strength_gap = max(-1.0, min(1.0, (profile.current - opponent_current) / 28.0))
    risk = {'attacking': 6.0, 'cautious': -6.0, 'balanced': 0.0, 'pragmatic': -2.0}[coach.approach]
    waste = {'attacking': -4.0, 'cautious': 7.0, 'balanced': 1.0, 'pragmatic': 4.0}[coach.approach]
    urgency = {'attacking': 8.0, 'cautious': -4.0, 'balanced': 2.0, 'pragmatic': 4.0}[coach.approach]
    # In decisive matches even cautious coaches have reason to chase a loss.
    urgency += 4.0 * importance - 1.0 * strength_gap + quality * 1.8 + noise * 3.5
    waste += (2.0 * importance + quality * 1.1 - noise * 2.5)
    risk += noise * 2.0 + quality * 0.9
    clamp = lambda v, low, high: max(low, min(high, v))
    return replace(profile,
        urgency_when_trailing=clamp(profile.urgency_when_trailing + urgency, 40.0, 100.0),
        time_wasting=clamp(profile.time_wasting + waste, 0.0, 85.0),
        risk_when_leading=clamp(profile.risk_when_leading + risk, 20.0, 85.0),
    )
