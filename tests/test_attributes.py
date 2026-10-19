import pytest

from football_manager.domain.attributes import (
    GoalkeepingAttributes,
    MentalAttributes,
    PhysicalAttributes,
    PlayerAttributes,
    TechnicalAttributes,
)


def build_attributes() -> PlayerAttributes:
    return PlayerAttributes(
        technical=TechnicalAttributes(
            passing=70,
            technique=71,
            finishing=72,
            first_touch=73,
            dribbling=74,
            crossing=75,
            tackling=76,
            heading=77,
            long_shots=78,
            shot_power=79,
            marking=80,
            set_pieces=81,
            penalties=82,
        ),
        mental=MentalAttributes(
            vision=65,
            decisions=66,
            anticipation=67,
            concentration=68,
            composure=69,
            positioning=70,
            off_the_ball=71,
            teamwork=72,
            work_rate=73,
            aggression=74,
            bravery=75,
            creativity=76,
            tactical_intelligence=77,
        ),
        physical=PhysicalAttributes(
            pace=80,
            acceleration=81,
            strength=82,
            stamina=83,
            agility=84,
            balance=85,
            jumping_reach=86,
            natural_fitness=87,
        ),
    )


def test_outfield_average_is_computed_from_outfield_groups() -> None:
    attributes = build_attributes()
    assert 65 < attributes.outfield_average() < 88
    assert attributes.average() == attributes.outfield_average()


def test_outfield_player_has_no_goalkeeping_average_by_default() -> None:
    attributes = build_attributes()
    assert attributes.goalkeeping is None
    assert attributes.goalkeeping_average() is None


def test_goalkeeping_average_is_available_for_goalkeepers() -> None:
    base = build_attributes()
    attributes = PlayerAttributes(
        technical=base.technical,
        mental=base.mental,
        physical=base.physical,
        goalkeeping=GoalkeepingAttributes(
            reflexes=85,
            handling=80,
            one_on_ones=82,
            aerial_reach=78,
            command_of_area=79,
            kicking=74,
            throwing=76,
            goalkeeper_positioning=83,
        ),
    )
    assert attributes.goalkeeping_average() is not None
    assert 75 < attributes.goalkeeping_average() < 86


def test_attribute_outside_scale_is_rejected() -> None:
    with pytest.raises(ValueError):
        TechnicalAttributes(
            passing=0,
            technique=70,
            finishing=70,
            first_touch=70,
            dribbling=70,
            crossing=70,
            tackling=70,
            heading=70,
            long_shots=70,
            shot_power=70,
            marking=70,
            set_pieces=70,
            penalties=70,
        )
