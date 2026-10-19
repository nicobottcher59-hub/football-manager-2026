from datetime import date

from football_manager.domain.attributes import (
    MentalAttributes,
    PhysicalAttributes,
    PlayerAttributes,
    TechnicalAttributes,
)
from football_manager.domain.enums import Foot, Position
from football_manager.domain.player import Player, PlayerIdentity
from football_manager.domain.positional_familiarity import PositionalFamiliarity


def make_player() -> Player:
    return Player(
        identity=PlayerIdentity(
            player_id="p1",
            first_name="Test",
            last_name="Player",
            birth_date=date(2000, 10, 5),
            nationality="Argentina",
            dominant_foot=Foot.RIGHT,
        ),
        attributes=PlayerAttributes(
            technical=TechnicalAttributes(
                passing=70,
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
            ),
            mental=MentalAttributes(
                vision=70,
                decisions=70,
                anticipation=70,
                concentration=70,
                composure=70,
                positioning=70,
                off_the_ball=70,
                teamwork=70,
                work_rate=70,
                aggression=70,
                bravery=70,
                creativity=70,
                tactical_intelligence=70,
            ),
            physical=PhysicalAttributes(
                pace=70,
                acceleration=70,
                strength=70,
                stamina=70,
                agility=70,
                balance=70,
                jumping_reach=70,
                natural_fitness=70,
            ),
        ),
        positional_familiarity=PositionalFamiliarity({Position.LW: 80, Position.ST: 50}),
        original_position=Position.LW,
        primary_position=Position.LW,
    )


def test_age_on_date() -> None:
    player = make_player()
    assert player.age_on(date(2026, 10, 2)) == 25
    assert player.age_on(date(2026, 10, 5)) == 26


def test_primary_position_changes_only_after_sustained_minutes_and_clear_superiority() -> None:
    player = make_player()

    for _ in range(30):
        player.record_position_minutes(Position.ST, 90)
    assert player.primary_position is Position.LW
    assert Position.ST in player.secondary_positions

    for _ in range(20):
        player.record_position_minutes(Position.ST, 90)
    assert player.primary_position is Position.ST
    assert Position.LW in player.secondary_positions


def test_primary_position_does_not_change_on_small_difference_even_with_minutes() -> None:
    player = make_player()
    player.positional_familiarity.set_score(Position.ST, 83)
    player.positional_familiarity.played_minutes[Position.ST] = 2000
    assert player.recalculate_primary_position(minimum_margin=5) is Position.LW
