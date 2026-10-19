import pytest

from football_manager.domain.player_state import PlayerState


def test_player_is_available_by_default() -> None:
    assert PlayerState().is_available is True


def test_injured_player_is_not_available() -> None:
    state = PlayerState(injury="hamstring strain")
    assert state.is_available is False


def test_fatigue_changes_fatigue_and_fitness() -> None:
    state = PlayerState(fitness=100, fatigue=0)
    state.apply_fatigue(20)
    assert state.fatigue == 20
    assert state.fitness == 89


def test_state_values_are_bounded() -> None:
    with pytest.raises(ValueError):
        PlayerState(fitness=101)
