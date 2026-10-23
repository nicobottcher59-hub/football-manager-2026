"""TS-FIX-01: minute-based match rhythm, separate from physical condition.

Rates are explicit game-design parameters, not physiological predictions.
The senior gain keeps its existing calibration; youth uses a stronger
competitive exposure and a dated training/inactivity clock.
"""
from __future__ import annotations
from math import isfinite


def after_match(value: float, minutes: int, *, rate: float = .018) -> float:
    if (not isfinite(value) or not 0 <= value <= 100 or type(minutes) is not int
            or not 0 <= minutes <= 120 or not isfinite(rate) or not 0 <= rate <= .5):
        raise ValueError('invalid match rhythm input')
    return max(0., min(100., value + (100. - value) * rate * min(1.25, minutes / 90.)))


def after_inactivity(value: float, days: int, *, training_quality: float, injured: bool) -> float:
    if (not isfinite(value) or not 0 <= value <= 100 or type(days) is not int or days < 0
            or not isfinite(training_quality) or not 0 <= training_quality <= 100):
        raise ValueError('invalid inactivity rhythm input')
    # Training maintains a base but cannot substitute for competitive minutes.
    target = 22. if injured else 44. + training_quality * .22
    rate = .018 if injured else .012
    return max(0., min(100., target + (value - target) * (1. - rate) ** days))
