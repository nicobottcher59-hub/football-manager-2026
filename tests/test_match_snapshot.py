from __future__ import annotations

from datetime import date, datetime, timezone

import pytest

from football_manager.domain import (
    Club,
    CompetitionContextSnapshot,
    CupTieContextSnapshot,
    Foot,
    Formation,
    FormationSlot,
    KitSnapshot,
    KitType,
    Level,
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
    StandingRowSnapshot,
    SurfaceType,
    TacticalFamiliarity,
    TacticalPreset,
    TechnicalAttributes,
    WeatherSnapshot,
    WeatherType,
    Tactic,
)
from football_manager.services import build_match_snapshot


def make_player(player_id: str, position: Position) -> Player:
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


def make_formation(formation_id: str = "4-3-3-snapshot") -> Formation:
    return Formation(
        formation_id=formation_id,
        name="4-3-3 Snapshot",
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


def make_side(club_id: str, prefix: str, formation: Formation | None = None):
    formation = formation or make_formation()
    starters = [make_player(f"{prefix}-{slot.slot_id}", slot.position) for slot in formation.slots]
    bench = [make_player(f"{prefix}-b{i}", Position.CM) for i in range(1, 6)]
    players = starters + bench
    club = Club(
        club_id=club_id,
        name=f"Club {prefix}",
        short_name=prefix.upper(),
        country="Argentina",
        squad=Squad.from_players(players),
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
        tactic_id=f"{prefix}-tactic",
        name=f"{prefix} tactic",
        formation=formation,
        preset=TacticalPreset.TIKI_TAKA,
    )
    for entry in lineup.starters:
        role_id = tactic.role_for_slot(entry.slot_id).role_id
        entry.player.tactical_familiarity.set_tactic_score(tactic.tactic_id, 72)
        entry.player.tactical_familiarity.set_role_score(role_id, 55)
    return club, lineup, tactic


def make_context(home_club_id: str = "home", away_club_id: str = "away") -> MatchContextSnapshot:
    standings = (
        StandingRowSnapshot(1, home_club_id, "Home Club", 20, 13, 4, 3, 40, 18, 43),
        StandingRowSnapshot(2, away_club_id, "Away Club", 20, 12, 4, 4, 37, 20, 40),
    )
    return MatchContextSnapshot(
        kickoff=datetime(2026, 10, 17, 21, 30, tzinfo=timezone.utc),
        competition=CompetitionContextSnapshot(
            competition_id="league-1",
            competition_name="Liga Demo",
            season_label="2026",
            stage_label="Fecha 21",
            standings=standings,
        ),
        stadium=StadiumSnapshot(
            stadium_id="stadium-1",
            name="Estadio Demo",
            pitch_length_m=105,
            pitch_width_m=68,
            surface=SurfaceType.HYBRID_GRASS,
            city="Buenos Aires",
        ),
        conditions=MatchConditionsSnapshot(
            weather=WeatherSnapshot(
                weather_type=WeatherType.RAIN,
                temperature_c=14,
                wind_kph=19,
                humidity=82,
                precipitation_intensity=55,
            ),
            pitch_condition=PitchCondition.WET,
        ),
        referee=RefereeSnapshot(
            referee_id="ref-1",
            name="Martin Gomez",
            strictness=76,
            contact_tolerance=32,
            card_tendency=81,
            penalty_tendency=67,
            advantage_tendency=58,
        ),
        kits=MatchKitSelectionSnapshot(
            home=KitSnapshot(
                kit_id="home-kit",
                club_id=home_club_id,
                name="Titular",
                kit_type=KitType.HOME,
                primary_color="#FFFFFF",
            ),
            away=KitSnapshot(
                kit_id="away-kit",
                club_id=away_club_id,
                name="Suplente",
                kit_type=KitType.AWAY,
                primary_color="#111111",
            ),
        ),
    )


def build_demo_snapshot():
    formation = make_formation()
    home_club, home_lineup, home_tactic = make_side("home", "home", formation)
    away_club, away_lineup, away_tactic = make_side("away", "away", formation)
    snapshot = build_match_snapshot(
        match_id="match-001",
        seed=20261017,
        context=make_context(),
        home_club=home_club,
        home_lineup=home_lineup,
        home_tactic=home_tactic,
        away_club=away_club,
        away_lineup=away_lineup,
        away_tactic=away_tactic,
    )
    return snapshot, home_club, home_lineup, home_tactic, away_club, away_lineup, away_tactic


def test_build_match_snapshot_freezes_full_pre_match_context() -> None:
    snapshot, *_ = build_demo_snapshot()

    assert snapshot.match_id == "match-001"
    assert snapshot.seed == 20261017
    assert snapshot.context.competition.stage_label == "Fecha 21"
    assert snapshot.context.conditions.weather.weather_type is WeatherType.RAIN
    assert snapshot.context.conditions.pitch_condition is PitchCondition.WET
    assert snapshot.context.referee.card_tendency == 81
    assert snapshot.context.stadium.pitch_width_m == 68
    assert snapshot.context.kits.home.kit_id == "home-kit"
    assert snapshot.context.competition.standing_for("home").points == 43
    assert len(snapshot.home_team.starters) == 11
    assert len(snapshot.home_team.bench) == 5


def test_starter_snapshot_contains_role_instructions_and_execution_context() -> None:
    snapshot, *_ = build_demo_snapshot()
    starter = snapshot.home_team.player_for_slot("st")

    assert starter.assigned_position is Position.ST
    assert starter.role_id is not None
    assert starter.role_name is not None
    assert starter.effective_instructions is not None
    assert starter.role_context is not None
    assert starter.role_context.position_familiarity == 90
    assert starter.role_context.role_familiarity == 55
    assert starter.role_context.tactic_familiarity == 72
    assert 1 <= starter.role_context.role_suitability <= 100
    assert starter.overall_rating == pytest.approx(69.6)
    assert starter.overall_rating < starter.role_context.role_suitability
    assert starter.current_rating == pytest.approx(69.5)
    assert starter.state.confidence == 65
    assert starter.state.condition == 100


def test_bench_snapshot_keeps_player_data_without_starting_assignment() -> None:
    snapshot, *_ = build_demo_snapshot()
    bench_player = snapshot.home_team.bench[0]

    assert not bench_player.is_starter
    assert bench_player.assigned_slot_id is None
    assert bench_player.assigned_position is None
    assert bench_player.role_id is None
    assert bench_player.attributes.technical.passing == 70


def test_snapshot_is_not_changed_by_later_player_or_tactic_mutation() -> None:
    snapshot, _, home_lineup, home_tactic, *_ = build_demo_snapshot()
    source_player = home_lineup.player_for_slot("lb")
    frozen_player = snapshot.home_team.player_for_slot("lb")
    original_team_instructions = snapshot.home_team.tactic.team_instructions
    original_role_id = frozen_player.role_id
    original_current_rating = frozen_player.current_rating

    source_player.state.fitness = 12
    source_player.positional_familiarity.set_score(Position.LB, 25)
    source_player.tactical_familiarity.set_tactic_score(home_tactic.tactic_id, 5)
    home_tactic.update_in_possession(tempo=Level.VERY_HIGH)

    assert frozen_player.state.fitness == 100
    assert frozen_player.familiarity.position_score(Position.LB) == 90
    assert frozen_player.familiarity.tactic_score(home_tactic.tactic_id) == 72
    assert frozen_player.role_id == original_role_id
    assert frozen_player.current_rating == original_current_rating
    assert snapshot.home_team.tactic.team_instructions is original_team_instructions
    assert snapshot.home_team.tactic.team_instructions.in_possession.tempo is not Level.VERY_HIGH


def test_team_snapshot_rejects_tactic_for_different_formation() -> None:
    formation = make_formation()
    home_club, home_lineup, _ = make_side("home", "home", formation)
    other_formation = make_formation("other-formation")
    wrong_tactic = Tactic.from_preset(
        tactic_id="wrong",
        name="Wrong",
        formation=other_formation,
        preset=TacticalPreset.COUNTER_ATTACK,
    )
    away_club, away_lineup, away_tactic = make_side("away", "away", formation)

    with pytest.raises(ValueError, match="tactic formation must match"):
        build_match_snapshot(
            match_id="match",
            seed=1,
            context=make_context(),
            home_club=home_club,
            home_lineup=home_lineup,
            home_tactic=wrong_tactic,
            away_club=away_club,
            away_lineup=away_lineup,
            away_tactic=away_tactic,
        )


def test_match_snapshot_rejects_selected_kit_from_wrong_club() -> None:
    formation = make_formation()
    home_club, home_lineup, home_tactic = make_side("home", "home", formation)
    away_club, away_lineup, away_tactic = make_side("away", "away", formation)
    context = make_context(home_club_id="someone-else", away_club_id="away")

    with pytest.raises(ValueError, match="home kit belongs"):
        build_match_snapshot(
            match_id="match",
            seed=1,
            context=context,
            home_club=home_club,
            home_lineup=home_lineup,
            home_tactic=home_tactic,
            away_club=away_club,
            away_lineup=away_lineup,
            away_tactic=away_tactic,
        )


def test_match_snapshot_rejects_same_club_on_both_sides() -> None:
    formation = make_formation()
    club, lineup, tactic = make_side("same", "same", formation)
    base = make_context()
    context = MatchContextSnapshot(
        kickoff=base.kickoff,
        competition=CompetitionContextSnapshot(
            competition_id="friendly",
            competition_name="Friendly",
            season_label="2026",
            stage_label="Match",
        ),
        stadium=base.stadium,
        conditions=base.conditions,
        referee=base.referee,
        kits=MatchKitSelectionSnapshot(
            home=KitSnapshot("same-home", "same", "Home", KitType.HOME),
            away=KitSnapshot("same-away", "same", "Away", KitType.AWAY),
        ),
    )

    with pytest.raises(ValueError, match="must be different"):
        build_match_snapshot(
            match_id="match",
            seed=1,
            context=context,
            home_club=club,
            home_lineup=lineup,
            home_tactic=tactic,
            away_club=club,
            away_lineup=lineup,
            away_tactic=tactic,
        )


def test_match_context_requires_timezone_aware_kickoff() -> None:
    base = make_context()

    with pytest.raises(ValueError, match="timezone-aware"):
        MatchContextSnapshot(
            kickoff=datetime(2026, 10, 17, 21, 30),
            competition=base.competition,
            stadium=base.stadium,
            conditions=base.conditions,
            referee=base.referee,
            kits=base.kits,
        )


def test_competition_context_rejects_duplicate_table_positions() -> None:
    rows = (
        StandingRowSnapshot(1, "a", "A", 1, 1, 0, 0, 1, 0, 3),
        StandingRowSnapshot(1, "b", "B", 1, 0, 1, 0, 0, 0, 1),
    )
    with pytest.raises(ValueError, match="duplicate positions"):
        CompetitionContextSnapshot("c", "Competition", "2026", "Fecha 1", rows)


def test_cup_context_can_freeze_round_leg_and_aggregate_before_kickoff() -> None:
    context = CompetitionContextSnapshot(
        competition_id="cup",
        competition_name="Copa Demo",
        season_label="2026",
        stage_label="Semifinal - Vuelta",
        cup_tie=CupTieContextSnapshot(
            round_label="Semifinal",
            leg_number=2,
            home_aggregate_goals_before_match=1,
            away_aggregate_goals_before_match=2,
        ),
    )

    assert context.cup_tie is not None
    assert context.cup_tie.leg_number == 2
    assert context.cup_tie.home_aggregate_goals_before_match == 1
    assert context.cup_tie.away_aggregate_goals_before_match == 2


def test_referee_tendencies_are_validated() -> None:
    with pytest.raises(ValueError, match="strictness"):
        RefereeSnapshot(referee_id="ref", name="Ref", strictness=120)


def test_weather_values_are_validated() -> None:
    with pytest.raises(ValueError, match="humidity"):
        WeatherSnapshot(WeatherType.CLEAR, temperature_c=20, humidity=101)


def test_match_seed_must_be_non_negative() -> None:
    formation = make_formation()
    home_club, home_lineup, home_tactic = make_side("home", "home", formation)
    away_club, away_lineup, away_tactic = make_side("away", "away", formation)

    with pytest.raises(ValueError, match="seed"):
        build_match_snapshot(
            match_id="match",
            seed=-1,
            context=make_context(),
            home_club=home_club,
            home_lineup=home_lineup,
            home_tactic=home_tactic,
            away_club=away_club,
            away_lineup=away_lineup,
            away_tactic=away_tactic,
        )
