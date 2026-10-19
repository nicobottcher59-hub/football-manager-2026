"""Lossless score validation shared by match and persistence boundaries.

A goal count or shootout score must be an actual Python integer. In
particular, int(1.75), int(True), and int('2') must never silently change
an imported or simulated result.
"""
from __future__ import annotations


def require_nonnegative_integer_score(value: object, field: str) -> int:
    """Return a validated score, rejecting bools, floats and text."""
    if type(value) is not int:
        raise ValueError(f"{field} must be a nonnegative integer")
    if value < 0:
        raise ValueError(f"{field} cannot be negative")
    return value
