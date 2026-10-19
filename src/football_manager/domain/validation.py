from __future__ import annotations


def validate_range(name: str, value: float, minimum: float, maximum: float) -> float:
    if not minimum <= value <= maximum:
        raise ValueError(f"{name} must be between {minimum} and {maximum}; got {value}")
    return value


def validate_non_negative(name: str, value: int | float) -> int | float:
    if value < 0:
        raise ValueError(f"{name} must be non-negative; got {value}")
    return value
