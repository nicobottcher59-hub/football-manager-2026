from __future__ import annotations

from datetime import date, datetime, timezone

from football_manager.domain import (
    Club,
    CompetitionContextSnapshot,
    Foot,
    Formation,
    FormationSlot,
    KitSnapshot,
    KitType,
    LineupEntry,
    MatchConditionsSnapshot,
    MatchContextSnapshot,
    MatchKitSelectionSnapshot,
    MatchLineup,
    MentalAttributes,
    PhysicalAttributes,
    PitchCondition,
    Player,
    PlayerAttributes,
    PlayerIdentity,
    Position,
    PositionalFamiliarity,
    RefereeSnapshot,
    Squad,
    StadiumSnapshot,
    SurfaceType,
    TacticalFamiliarity,
    TacticalPreset,
    TechnicalAttributes,
    WeatherSnapshot,
    WeatherType,
    Tactic,
)
from football_manager.services import build_match_snapshot


def _player(player_id: str, position: Position) -> Player:
    return Player(
        identity=PlayerIdentity(
            player_id=player_id,
            first_name="Player",
            last_name=player_id,
            birth_date=date(2000, 1, 1),
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
        positional_familiarity=PositionalFamiliarity({position: 90}),
        original_position=position,
        primary_position=position,
        tactical_familiarity=TacticalFamiliarity(),
    )


def demo_formation() -> Formation:
    return Formation(
        formation_id="demo-4-3-3",
        name="Demo 4-3-3",
        slots=(
            FormationSlot("gk", Position.GK),
            FormationSlot("rb", Position.RB),
            FormationSlot("rcb", Position.RCB),
            FormationSlot("lcb", Position.LCB),
            FormationSlot("lb", Position.LB),
            FormationSlot("rcm", Position.RCM),
            FormationSlot("cm", Position.CM),
            FormationSlot("lcm", Position.LCM),
            FormationSlot("rw", Position.RW),
            FormationSlot("st", Position.ST),
            FormationSlot("lw", Position.LW),
        ),
    )


def _side(club_id: str, formation: Formation):
    starters = [_player(f"{club_id}-{slot.slot_id}", slot.position) for slot in formation.slots]
    bench_positions = (
        Position.GK,
        Position.RB,
        Position.CB,
        Position.CM,
        Position.AM,
        Position.RW,
        Position.ST,
    )
    bench = [
        _player(f"{club_id}-sub-{index + 1}-{position.value}", position)
        for index, position in enumerate(bench_positions)
    ]
    club = Club(
        club_id=club_id,
        name=f"Club {club_id.title()}",
        short_name=club_id.upper(),
        country="Argentina",
        squad=Squad.from_players(starters + bench),
    )
    lineup = MatchLineup(
        club_id=club_id,
        formation=formation,
        starters=tuple(
            LineupEntry(slot.slot_id, player)
            for slot, player in zip(formation.slots, starters, strict=True)
        ),
        bench=tuple(bench),
    )
    tactic = Tactic.from_preset(
        tactic_id=f"{club_id}-tactic",
        name=f"{club_id.title()} Tactical Demo",
        formation=formation,
        preset=TacticalPreset.TIKI_TAKA,
    )
    return club, lineup, tactic


def build_demo_snapshot(*, configure_home=None, seed: int = 5101):
    formation = demo_formation()
    home_club, home_lineup, home_tactic = _side("home", formation)
    away_club, away_lineup, away_tactic = _side("away", formation)
    if configure_home is not None:
        configure_home(home_tactic)

    context = MatchContextSnapshot(
        kickoff=datetime(2026, 10, 17, 21, 30, tzinfo=timezone.utc),
        competition=CompetitionContextSnapshot(
            competition_id="demo-league",
            competition_name="Liga Demo",
            season_label="2026",
            stage_label="Fecha 1",
        ),
        stadium=StadiumSnapshot(
            stadium_id="demo-stadium",
            name="Estadio Demo",
            pitch_length_m=105.0,
            pitch_width_m=68.0,
            surface=SurfaceType.HYBRID_GRASS,
            city="Buenos Aires",
        ),
        conditions=MatchConditionsSnapshot(
            weather=WeatherSnapshot(weather_type=WeatherType.CLEAR, temperature_c=20),
            pitch_condition=PitchCondition.GOOD,
        ),
        referee=RefereeSnapshot(referee_id="ref-demo", name="Ref Demo"),
        kits=MatchKitSelectionSnapshot(
            home=KitSnapshot("home-kit", "home", "Home", KitType.HOME),
            away=KitSnapshot("away-kit", "away", "Away", KitType.AWAY),
        ),
    )

    return build_match_snapshot(
        match_id="phase-5-1-demo",
        seed=seed,
        context=context,
        home_club=home_club,
        home_lineup=home_lineup,
        home_tactic=home_tactic,
        away_club=away_club,
        away_lineup=away_lineup,
        away_tactic=away_tactic,
    )
