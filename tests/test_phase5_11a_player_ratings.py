from __future__ import annotations

from dataclasses import replace
from datetime import date

import pytest

from football_manager.domain.attributes import (
    MentalAttributes,
    PhysicalAttributes,
    PlayerAttributes,
    TechnicalAttributes,
)
from football_manager.domain.enums import Foot, Position
from football_manager.domain.player import Player, PlayerIdentity
from football_manager.domain.player_ratings import CurrentRatingContext
from football_manager.domain.player_state import PlayerState
from football_manager.domain.positional_familiarity import PositionalFamiliarity
from football_manager.domain.tactical_familiarity import TacticalFamiliarity


def _attributes(*, level: int = 70, adaptability: int = 65) -> PlayerAttributes:
    return PlayerAttributes(
        technical=TechnicalAttributes(
            passing=level,
            technique=level,
            finishing=level,
            first_touch=level,
            dribbling=level,
            crossing=level,
            tackling=level,
            heading=level,
            long_shots=level,
            shot_power=level,
            marking=level,
            set_pieces=level,
            penalties=level,
        ),
        mental=MentalAttributes(
            vision=level,
            decisions=level,
            anticipation=level,
            concentration=level,
            composure=level,
            positioning=level,
            off_the_ball=level,
            teamwork=level,
            work_rate=level,
            aggression=level,
            bravery=level,
            creativity=level,
            tactical_intelligence=level,
            adaptability=adaptability,
        ),
        physical=PhysicalAttributes(
            pace=level,
            acceleration=level,
            strength=level,
            stamina=level,
            agility=level,
            balance=level,
            jumping_reach=level,
            natural_fitness=level,
        ),
    )


def _player(
    *,
    level: int = 70,
    adaptability: int = 65,
    state: PlayerState | None = None,
    position_scores: dict[Position, float] | None = None,
    role_scores: dict[str, float] | None = None,
    tactic_scores: dict[str, float] | None = None,
) -> Player:
    return Player(
        identity=PlayerIdentity(
            player_id="rating-player",
            first_name="Rating",
            last_name="Player",
            birth_date=date(2000, 1, 1),
            nationality="Argentina",
            dominant_foot=Foot.RIGHT,
        ),
        attributes=_attributes(level=level, adaptability=adaptability),
        positional_familiarity=PositionalFamiliarity(
            position_scores or {Position.LW: 100.0, Position.ST: 25.0}
        ),
        original_position=Position.LW,
        primary_position=Position.LW,
        state=state or PlayerState(),
        tactical_familiarity=TacticalFamiliarity(
            role_values=role_scores or {},
            tactic_values=tactic_scores or {},
        ),
    )


def test_uniform_attributes_keep_role_attribute_fit_at_same_level() -> None:
    player = _player(level=70)
    breakdown = player.overall_breakdown_for(Position.LW, "winger")
    assert breakdown.attribute_fit == pytest.approx(70.0)
    assert 69.0 <= breakdown.overall <= 70.0


def test_overall_is_contextual_to_position_and_role() -> None:
    player = _player(level=78, position_scores={Position.LW: 100.0, Position.CB: 0.0})
    winger = player.overall_rating_for(Position.LW, "winger")
    centre_back = player.overall_rating_for(Position.CB, "central_defender")

    assert centre_back < winger
    assert player.overall_breakdown_for(Position.CB, "central_defender").position_adjustment < -10.0


def test_overall_changes_when_underlying_attributes_change() -> None:
    player = _player(level=70)
    better = replace(player, attributes=_attributes(level=82))
    assert better.overall_rating > player.overall_rating


def test_neutral_state_keeps_act_equal_to_ovr() -> None:
    player = _player(level=80, state=PlayerState(fitness=100))
    breakdown = player.current_rating()
    assert breakdown.current == pytest.approx(breakdown.overall)
    assert breakdown.adjustment("confidence") == pytest.approx(0.0)
    assert breakdown.adjustment("chemistry") == pytest.approx(0.0)


def test_contextual_scores_above_65_add_bonuses() -> None:
    state = PlayerState(
        fitness=100,
        form=100,
        morale=100,
        confidence=100,
        match_sharpness=100,
    )
    player = _player(
        level=72,
        state=state,
        position_scores={Position.LW: 100.0},
        role_scores={"winger": 100.0},
        tactic_scores={"wide_attack": 100.0},
    )
    breakdown = player.current_rating(
        CurrentRatingContext(
            assigned_position=Position.LW,
            role_id="winger",
            tactic_id="wide_attack",
            chemistry=100.0,
        )
    )
    assert breakdown.current > breakdown.overall
    for name in (
        "form",
        "confidence",
        "morale",
        "match_sharpness",
        "role_familiarity",
        "tactic_familiarity",
        "chemistry",
    ):
        assert breakdown.adjustment(name) > 0.0
    assert breakdown.overall_component("position_familiarity") == pytest.approx(100.0)
    assert breakdown.overall_component("position_adjustment") == pytest.approx(0.0)


def test_contextual_scores_below_65_apply_penalties() -> None:
    state = PlayerState(
        fitness=100,
        form=30,
        morale=30,
        confidence=30,
        match_sharpness=30,
    )
    player = _player(
        level=82,
        state=state,
        position_scores={Position.LW: 30.0},
        role_scores={"winger": 30.0},
        tactic_scores={"wide_attack": 30.0},
    )
    breakdown = player.current_rating(
        CurrentRatingContext(
            assigned_position=Position.LW,
            role_id="winger",
            tactic_id="wide_attack",
            chemistry=30.0,
        )
    )
    assert breakdown.current < breakdown.overall
    for name in (
        "form",
        "confidence",
        "morale",
        "match_sharpness",
        "role_familiarity",
        "tactic_familiarity",
        "chemistry",
    ):
        assert breakdown.adjustment(name) < 0.0
    assert breakdown.overall_component("position_familiarity") == pytest.approx(30.0)
    assert breakdown.overall_component("position_adjustment") < 0.0


def test_exactly_65_is_neutral_for_all_bidirectional_context() -> None:
    state = PlayerState(
        fitness=75,
        form=65,
        morale=65,
        confidence=65,
        match_sharpness=65,
    )
    player = _player(
        level=75,
        state=state,
        position_scores={Position.LW: 65.0},
        role_scores={"winger": 65.0},
        tactic_scores={"wide_attack": 65.0},
    )
    breakdown = player.current_rating(
        CurrentRatingContext(
            assigned_position=Position.LW,
            role_id="winger",
            tactic_id="wide_attack",
            chemistry=65.0,
        )
    )
    assert breakdown.current == pytest.approx(breakdown.overall)
    assert all(value == pytest.approx(0.0) for _, value in breakdown.adjustments)


def test_unfamiliar_position_role_and_tactic_can_pull_act_far_below_ovr() -> None:
    player = _player(
        level=84,
        adaptability=10,
        position_scores={Position.LW: 100.0, Position.CB: 0.0},
        role_scores={"central_defender": 0.0},
        tactic_scores={"high_line": 0.0},
    )
    breakdown = player.current_rating(
        CurrentRatingContext(
            assigned_position=Position.CB,
            role_id="central_defender",
            tactic_id="high_line",
        )
    )
    assert breakdown.overall_component("attribute_fit") == pytest.approx(84.0)
    assert breakdown.overall < 70.0
    assert breakdown.current < breakdown.overall
    assert breakdown.overall_component("position_adjustment") < -15.0


def test_confidence_can_raise_or_lower_act_without_rewriting_ovr() -> None:
    player = _player(level=80)
    overall = player.overall_rating

    player.state.confidence = 100.0
    high = player.current_rating().current
    player.state.confidence = 65.0
    neutral = player.current_rating().current
    player.state.confidence = 0.0
    low = player.current_rating().current

    assert high > neutral > low
    assert player.overall_rating == overall


def test_adaptability_softens_unfamiliarity_penalty_but_is_not_a_free_bonus() -> None:
    low = _player(
        adaptability=1,
        position_scores={Position.LW: 100.0, Position.ST: 0.0},
    )
    high = _player(
        adaptability=100,
        position_scores={Position.LW: 100.0, Position.ST: 0.0},
    )
    unfamiliar = CurrentRatingContext(assigned_position=Position.ST)
    assert low.current_rating(unfamiliar).current < high.current_rating(unfamiliar).current

    low.positional_familiarity.set_score(Position.ST, 100.0)
    high.positional_familiarity.set_score(Position.ST, 100.0)
    assert low.current_rating(unfamiliar).current == high.current_rating(unfamiliar).current


def test_condition_has_no_bonus_from_75_to_100() -> None:
    ratings = []
    for condition in (75.0, 80.0, 90.0, 100.0):
        player = _player(level=80, state=PlayerState(fitness=condition))
        breakdown = player.current_rating()
        ratings.append(breakdown.current)
        assert breakdown.adjustment("condition") == pytest.approx(0.0)
    assert len(set(ratings)) == 1


def test_condition_below_75_progressively_reduces_act() -> None:
    at_75 = _player(level=80, state=PlayerState(fitness=75)).current_rating()
    at_60 = _player(level=80, state=PlayerState(fitness=60)).current_rating()
    at_30 = _player(level=80, state=PlayerState(fitness=30)).current_rating()

    assert at_75.adjustment("condition") == pytest.approx(0.0)
    assert at_75.current > at_60.current > at_30.current
    assert at_60.adjustment("condition") < 0.0
    assert at_30.adjustment("condition") < at_60.adjustment("condition")


def test_fatigue_is_not_double_counted_as_a_second_act_penalty() -> None:
    fresh = _player(level=80, state=PlayerState(fitness=80, fatigue=0))
    tired_counter = _player(level=80, state=PlayerState(fitness=80, fatigue=80))
    assert fresh.current_rating().current == tired_counter.current_rating().current
    with pytest.raises(KeyError):
        fresh.current_rating().adjustment("fatigue")


def test_confidence_and_form_adjustments_are_bounded() -> None:
    state = PlayerState(confidence=95.0, form=5.0)
    assert state.adjust_confidence(20.0) == 100.0
    assert state.adjust_confidence(-150.0) == 0.0
    assert state.adjust_form(-20.0) == 0.0
    assert state.adjust_form(150.0) == 100.0


def test_rating_context_rejects_invalid_chemistry() -> None:
    with pytest.raises(ValueError):
        CurrentRatingContext(chemistry=101.0)


def test_moderate_confidence_drop_is_not_a_rating_collapse() -> None:
    player = _player(level=80, state=PlayerState(confidence=30.0))
    breakdown = player.current_rating()

    assert 79.0 <= breakdown.overall <= 80.0
    assert -3.0 < breakdown.adjustment("confidence") < 0.0
    assert breakdown.current > 77.0


def test_confidence_becomes_severe_only_below_five() -> None:
    player = _player(level=80)

    player.state.confidence = 5.0
    at_five = player.current_rating()
    player.state.confidence = 4.0
    below_five = player.current_rating()
    player.state.confidence = 0.0
    destroyed = player.current_rating()

    assert at_five.adjustment("confidence") == pytest.approx(-4.0)
    assert below_five.adjustment("confidence") < at_five.adjustment("confidence")
    assert destroyed.adjustment("confidence") <= -10.0
    assert destroyed.current < below_five.current < at_five.current


def test_moderately_bad_context_does_not_destroy_an_unfamiliar_striker() -> None:
    player = _player(
        level=80,
        state=PlayerState(
            fitness=62.0,
            form=38.0,
            morale=45.0,
            confidence=30.0,
            match_sharpness=55.0,
        ),
        position_scores={Position.LW: 100.0, Position.ST: 35.0},
        role_scores={"advanced_forward": 35.0},
        tactic_scores={"new_system": 35.0},
    )
    breakdown = player.current_rating(
        CurrentRatingContext(
            assigned_position=Position.ST,
            role_id="advanced_forward",
            tactic_id="new_system",
            chemistry=48.0,
        )
    )

    # With the Phase 6.6a physical adjustment, 62 condition must make a
    # noticeable difference even when this player's other fits are already poor.
    assert 56.0 <= breakdown.current <= 68.0
    assert breakdown.adjustment("condition") < -7.0
    assert breakdown.overall_component("position_adjustment") > -8.0
    assert breakdown.adjustment("role_familiarity") > -2.5
    assert breakdown.adjustment("confidence") > -3.0


def test_single_positive_context_factor_only_adds_a_small_bonus() -> None:
    player = _player(level=80)
    player.state.confidence = 100.0

    breakdown = player.current_rating()

    assert 79.0 <= breakdown.overall <= 80.0
    assert breakdown.current == pytest.approx(breakdown.overall + 1.2)
    assert breakdown.adjustment("confidence") == pytest.approx(1.2)
    assert breakdown.adjustment("context_excellence") == pytest.approx(0.0)


def test_very_good_context_stays_well_below_perfect_alignment_ceiling() -> None:
    player = _player(
        level=80,
        state=PlayerState(
            fitness=100.0,
            form=92.0,
            morale=85.0,
            confidence=100.0,
            match_sharpness=90.0,
        ),
        position_scores={Position.LW: 100.0},
        role_scores={"winger": 100.0},
        tactic_scores={"main_system": 100.0},
    )
    breakdown = player.current_rating(
        CurrentRatingContext(
            assigned_position=Position.LW,
            role_id="winger",
            tactic_id="main_system",
            chemistry=92.0,
        )
    )

    assert 86.0 <= breakdown.current <= 90.0
    assert breakdown.adjustment("context_excellence") < 3.0


def test_all_100_context_can_push_80_ovr_player_to_97_act() -> None:
    player = _player(
        level=80,
        state=PlayerState(
            fitness=100.0,
            form=100.0,
            morale=100.0,
            confidence=100.0,
            match_sharpness=100.0,
        ),
        position_scores={Position.LW: 100.0},
        role_scores={"winger": 100.0},
        tactic_scores={"main_system": 100.0},
    )
    breakdown = player.current_rating(
        CurrentRatingContext(
            assigned_position=Position.LW,
            role_id="winger",
            tactic_id="main_system",
            chemistry=100.0,
        )
    )

    assert 79.0 <= breakdown.overall <= 80.0
    assert breakdown.current == pytest.approx(breakdown.overall + 15.8)
    assert breakdown.adjustment("context_excellence") == pytest.approx(10.6)
