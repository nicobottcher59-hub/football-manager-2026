from __future__ import annotations

from datetime import date

from football_manager.domain import (
    Foot,
    MentalAttributes,
    PhysicalAttributes,
    Player,
    PlayerAttributes,
    PlayerIdentity,
    PlayerState,
    Position,
    PositionalFamiliarity,
    TacticalFamiliarity,
    TechnicalAttributes,
)
from football_manager.domain.player_ratings import CurrentRatingContext


def make_attributes(level: int = 80, adaptability: int = 65) -> PlayerAttributes:
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


def make_player(*, adaptability: int = 65) -> Player:
    return Player(
        identity=PlayerIdentity(
            player_id="demo-winger",
            first_name="Demo",
            last_name="Winger",
            birth_date=date(2002, 6, 15),
            nationality="Argentina",
            dominant_foot=Foot.RIGHT,
        ),
        attributes=make_attributes(adaptability=adaptability),
        positional_familiarity=PositionalFamiliarity(
            {
                Position.LW: 100,
                Position.ST: 35,
                Position.CB: 0,
            }
        ),
        original_position=Position.LW,
        primary_position=Position.LW,
        state=PlayerState(),
        tactical_familiarity=TacticalFamiliarity(
            role_values={"winger": 100, "advanced_forward": 35, "central_defender": 0},
            tactic_values={"main_system": 100, "new_system": 35},
        ),
    )


def show(label: str, player: Player, context: CurrentRatingContext) -> None:
    rating = player.current_rating(context)
    print(f"\n{label}")
    print(f"OVR {rating.overall:.1f} | ACT {rating.current:.1f}")
    print(
        " | ".join(
            f"{name}={value:+.2f}"
            for name, value in rating.adjustments
            if abs(value) >= 0.01
        )
        or "all contextual adjustments neutral"
    )


def main() -> None:
    player = make_player()

    neutral_context = CurrentRatingContext(
        assigned_position=Position.LW,
        role_id="winger",
        tactic_id="main_system",
        chemistry=65,
    )

    player.state.form = 65
    player.state.confidence = 65
    player.state.morale = 65
    player.state.match_sharpness = 65
    player.state.fitness = 100
    player.positional_familiarity.set_score(Position.LW, 65)
    player.tactical_familiarity.set_role_score("winger", 65)
    player.tactical_familiarity.set_tactic_score("main_system", 65)
    show("Neutral baseline", player, neutral_context)

    player.state.form = 92
    player.state.confidence = 100
    player.state.morale = 85
    player.state.match_sharpness = 90
    player.positional_familiarity.set_score(Position.LW, 100)
    player.tactical_familiarity.set_role_score("winger", 100)
    player.tactical_familiarity.set_tactic_score("main_system", 100)
    show(
        "Flying in a familiar system",
        player,
        CurrentRatingContext(
            assigned_position=Position.LW,
            role_id="winger",
            tactic_id="main_system",
            chemistry=92,
        ),
    )

    player.state.form = 100
    player.state.confidence = 100
    player.state.morale = 100
    player.state.match_sharpness = 100
    player.state.fitness = 100
    show(
        "Perfect total alignment",
        player,
        CurrentRatingContext(
            assigned_position=Position.LW,
            role_id="winger",
            tactic_id="main_system",
            chemistry=100,
        ),
    )

    player.state.form = 38
    player.state.confidence = 30
    player.state.morale = 45
    player.state.match_sharpness = 55
    player.state.fitness = 62
    show(
        "Forced into an unfamiliar striker role",
        player,
        CurrentRatingContext(
            assigned_position=Position.ST,
            role_id="advanced_forward",
            tactic_id="new_system",
            chemistry=48,
        ),
    )

    show(
        "Same footballer forced at centre-back",
        player,
        CurrentRatingContext(
            assigned_position=Position.CB,
            role_id="central_defender",
            tactic_id="new_system",
            chemistry=48,
        ),
    )


if __name__ == "__main__":
    main()
