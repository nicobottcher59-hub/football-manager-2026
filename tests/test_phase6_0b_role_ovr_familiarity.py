from __future__ import annotations

from dataclasses import replace
from datetime import date

import pytest

from football_manager.dev_ui import DevelopmentSession
from football_manager.domain import CurrentRatingContext, Foot, Position
from football_manager.domain.attributes import (
    MentalAttributes,
    PhysicalAttributes,
    PlayerAttributes,
    TechnicalAttributes,
)
from football_manager.domain.player import Player, PlayerIdentity
from football_manager.domain.positional_familiarity import PositionalFamiliarity


def _technical(level: int = 50, **changes: int) -> TechnicalAttributes:
    base = TechnicalAttributes(
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
    )
    return replace(base, **changes)


def _mental(level: int = 50, **changes: int) -> MentalAttributes:
    base = MentalAttributes(
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
        adaptability=65,
    )
    return replace(base, **changes)


def _physical(level: int = 50, **changes: int) -> PhysicalAttributes:
    base = PhysicalAttributes(
        pace=level,
        acceleration=level,
        strength=level,
        stamina=level,
        agility=level,
        balance=level,
        jumping_reach=level,
        natural_fitness=level,
    )
    return replace(base, **changes)


def _player(
    *,
    technical: TechnicalAttributes,
    mental: MentalAttributes,
    physical: PhysicalAttributes,
    familiarities: dict[Position, float],
    primary: Position,
    foot: Foot = Foot.RIGHT,
) -> Player:
    return Player(
        identity=PlayerIdentity(
            player_id="phase-6-0b-player",
            first_name="Contextual",
            last_name="Tester",
            birth_date=date(2000, 1, 1),
            nationality="Argentina",
            dominant_foot=foot,
        ),
        attributes=PlayerAttributes(
            technical=technical,
            mental=mental,
            physical=physical,
        ),
        positional_familiarity=PositionalFamiliarity(familiarities),
        original_position=primary,
        primary_position=primary,
    )


def test_defensive_attributes_make_cb_fit_anchor_and_fullback_better_than_winger() -> None:
    player = _player(
        technical=_technical(
            45,
            tackling=92,
            marking=91,
            passing=58,
            first_touch=55,
            dribbling=22,
            crossing=25,
            heading=88,
            finishing=24,
        ),
        mental=_mental(
            55,
            positioning=91,
            anticipation=88,
            concentration=90,
            decisions=76,
            tactical_intelligence=84,
            work_rate=78,
        ),
        physical=_physical(
            60,
            pace=70,
            acceleration=64,
            stamina=80,
            strength=90,
            jumping_reach=87,
        ),
        familiarities={
            Position.CB: 95.0,
            Position.RB: 88.0,
            Position.DM: 88.0,
            Position.RW: 88.0,
        },
        primary=Position.CB,
    )

    defensive_fullback = player.overall_rating_for(Position.RB, "defensive_fullback")
    anchor = player.overall_rating_for(Position.DM, "anchor")
    winger = player.overall_rating_for(Position.RW, "winger")

    assert defensive_fullback > winger + 15.0
    assert anchor > winger + 20.0


def test_stats_can_make_a_natural_winger_viable_as_defensive_fullback() -> None:
    player = _player(
        technical=_technical(
            65,
            tackling=80,
            marking=78,
            passing=78,
            crossing=84,
            dribbling=85,
            first_touch=82,
        ),
        mental=_mental(
            70,
            positioning=80,
            decisions=81,
            work_rate=86,
            off_the_ball=82,
            adaptability=82,
        ),
        physical=_physical(
            72,
            pace=89,
            acceleration=88,
            stamina=88,
            agility=84,
        ),
        familiarities={Position.LW: 96.0, Position.LB: 72.0},
        primary=Position.LW,
        foot=Foot.LEFT,
    )

    winger = player.overall_rating_for(Position.LW, "winger")
    defensive_fullback = player.overall_rating_for(Position.LB, "defensive_fullback")

    assert defensive_fullback >= 75.0
    assert winger - defensive_fullback < 8.0


def test_same_position_role_changes_ovr_from_attribute_profile() -> None:
    player = _player(
        technical=_technical(
            55,
            passing=91,
            first_touch=88,
            tackling=79,
            marking=72,
            crossing=43,
            dribbling=42,
        ),
        mental=_mental(
            65,
            decisions=92,
            tactical_intelligence=91,
            vision=86,
            positioning=79,
        ),
        physical=_physical(62, pace=64, stamina=75),
        familiarities={Position.RB: 95.0},
        primary=Position.RB,
    )

    inverted = player.overall_rating_for(Position.RB, "inverted_fullback")
    wingback = player.overall_rating_for(Position.RB, "wingback")

    assert inverted > wingback + 12.0


def test_mirrored_winger_is_close_but_not_identical() -> None:
    player = _player(
        technical=_technical(75, dribbling=84, crossing=82),
        mental=_mental(74, off_the_ball=82),
        physical=_physical(76, pace=87, acceleration=86),
        familiarities={Position.LW: 95.0},
        primary=Position.LW,
        foot=Foot.RIGHT,
    )

    natural_side = player.overall_rating_for(Position.LW, "winger")
    opposite_side = player.overall_rating_for(Position.RW, "winger")

    assert opposite_side < natural_side
    assert natural_side - opposite_side < 2.0


def test_contextual_ovr_is_the_base_for_act_not_a_second_position_penalty() -> None:
    player = _player(
        technical=_technical(76),
        mental=_mental(76),
        physical=_physical(76),
        familiarities={Position.CB: 95.0, Position.RB: 55.0},
        primary=Position.CB,
    )

    breakdown = player.current_rating(
        CurrentRatingContext(
            assigned_position=Position.RB,
            role_id="defensive_fullback",
        )
    )

    assert breakdown.overall == player.overall_rating_for(Position.RB, "defensive_fullback")
    assert "position_familiarity" not in {name for name, _ in breakdown.adjustments}
    assert breakdown.overall_component("position_familiarity") == pytest.approx(55.0)


def test_match_snapshot_starter_uses_same_contextual_ovr_as_dev_ui() -> None:
    session = DevelopmentSession()
    row = next(item for item in session.squad_rows() if item.squad_status == "XI" and item.slot == "RCB")

    snapshot_player = session._build_snapshot().home_team.player(row.player_id)

    assert snapshot_player.overall_rating == pytest.approx(row.overall)
    assert snapshot_player.current_rating == pytest.approx(row.current)
    assert snapshot_player.role_context is not None
    assert snapshot_player.role_context.role_suitability == pytest.approx(row.role_fit, abs=0.05)


def test_quick_sim_minutes_begin_learning_a_new_explicit_position() -> None:
    session = DevelopmentSession()
    before = {item.slot: item for item in session.squad_rows() if item.squad_status == "XI"}
    striker_id = before["ST"].player_id
    striker = next(player for player in session.home_club.squad.players if player.id == striker_id)
    explicit_before = striker.positional_familiarity.score(Position.RCB)

    session.swap_starting_slots("st", "rcb")
    session.quick_simulate()

    assert striker.positional_familiarity.score(Position.RCB) > explicit_before
    assert striker.positional_familiarity.minutes_for(Position.RCB) > 0.0


def test_primary_position_conversion_requires_sustained_superior_familiarity() -> None:
    player = _player(
        technical=_technical(70),
        mental=_mental(70, adaptability=85),
        physical=_physical(70),
        familiarities={Position.CB: 90.0, Position.DM: 72.0},
        primary=Position.CB,
    )

    for _ in range(10):
        player.record_position_minutes(Position.DM, 90.0)
    assert player.primary_position is Position.CB

    for _ in range(50):
        player.record_position_minutes(Position.DM, 90.0)

    assert player.primary_position is Position.DM
    assert Position.CB in player.secondary_positions
