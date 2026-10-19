import pytest

from football_manager.domain.enums import Position
from football_manager.domain.positional_familiarity import PositionalFamiliarity


def test_unknown_position_defaults_to_zero() -> None:
    familiarity = PositionalFamiliarity({Position.LW: 90})
    assert familiarity.score(Position.ST) == 0


def test_improvement_is_capped_at_one_hundred() -> None:
    familiarity = PositionalFamiliarity({Position.ST: 98})
    assert familiarity.improve(Position.ST, 10) == 100


def test_best_position_returns_highest_familiarity() -> None:
    familiarity = PositionalFamiliarity({Position.LW: 90, Position.ST: 72})
    assert familiarity.best_position() is Position.LW


def test_effective_familiarity_transfers_between_mirrored_wingers() -> None:
    familiarity = PositionalFamiliarity({Position.LW: 90})

    assert familiarity.score(Position.RW) == 0
    assert familiarity.effective_score(Position.RW) == pytest.approx(81.0)


def test_explicit_target_familiarity_overrides_transfer_floor() -> None:
    familiarity = PositionalFamiliarity({Position.LW: 90, Position.RW: 40})

    assert familiarity.effective_score(Position.RW) == 40


def test_goalkeeper_familiarity_never_transfers_from_outfield() -> None:
    familiarity = PositionalFamiliarity({Position.ST: 95, Position.CB: 80})

    assert familiarity.effective_score(Position.GK) == 0


def test_new_position_requires_minutes_before_becoming_secondary() -> None:
    familiarity = PositionalFamiliarity({Position.LW: 90})

    for _ in range(4):
        familiarity.record_minutes(Position.RW, 90, adaptability=80)
    assert Position.RW not in familiarity.secondary_positions(Position.LW)

    familiarity.record_minutes(Position.RW, 90, adaptability=80)
    assert Position.RW in familiarity.secondary_positions(Position.LW)
    assert familiarity.score(Position.RW) > 81.0


def test_unused_position_decays_only_after_grace_and_keeps_memory_floor() -> None:
    familiarity = PositionalFamiliarity(
        {Position.CB: 95, Position.DM: 85},
        played_minutes={Position.CB: 4000, Position.DM: 3000},
    )

    for _ in range(10):
        familiarity.record_minutes(Position.DM, 90, adaptability=65)
    assert familiarity.score(Position.CB) == pytest.approx(95.0)

    for _ in range(40):
        familiarity.record_minutes(Position.DM, 90, adaptability=65)
    assert familiarity.score(Position.CB) < 95.0
    assert familiarity.score(Position.CB) > 70.0
