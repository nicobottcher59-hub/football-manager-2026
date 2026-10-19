from __future__ import annotations

from datetime import date, datetime, timezone

import pytest

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
from football_manager.simulation import (
    DEFAULT_TIMESTEP_SECONDS,
    MatchClock,
    PitchDimensions,
    SpatialMatchEngine,
    TeamSide,
    Vector2,
    create_initial_match_state,
)


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


def make_formation() -> Formation:
    return Formation(
        formation_id="4-3-3-spatial",
        name="4-3-3 Spatial",
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


def make_side(club_id: str, prefix: str, formation: Formation):
    starters = [make_player(f"{prefix}-{slot.slot_id}", slot.position) for slot in formation.slots]
    club = Club(
        club_id=club_id,
        name=f"Club {club_id}",
        short_name=club_id.upper(),
        country="Argentina",
        squad=Squad.from_players(starters),
    )
    lineup = MatchLineup(
        club_id=club_id,
        formation=formation,
        starters=tuple(
            LineupEntry(slot.slot_id, player)
            for slot, player in zip(formation.slots, starters, strict=True)
        ),
    )
    tactic = Tactic.from_preset(
        tactic_id=f"{club_id}-tactic",
        name=f"{club_id} tactic",
        formation=formation,
        preset=TacticalPreset.TIKI_TAKA,
    )
    return club, lineup, tactic


def make_context(
    home_club_id: str = "home",
    away_club_id: str = "away",
    *,
    pitch_length_m: float = 105.0,
    pitch_width_m: float = 68.0,
) -> MatchContextSnapshot:
    return MatchContextSnapshot(
        kickoff=datetime(2026, 10, 17, 21, 30, tzinfo=timezone.utc),
        competition=CompetitionContextSnapshot(
            competition_id="league-1",
            competition_name="Liga Demo",
            season_label="2026",
            stage_label="Fecha 21",
        ),
        stadium=StadiumSnapshot(
            stadium_id="stadium-1",
            name="Estadio Demo",
            pitch_length_m=pitch_length_m,
            pitch_width_m=pitch_width_m,
            surface=SurfaceType.HYBRID_GRASS,
            city="Buenos Aires",
        ),
        conditions=MatchConditionsSnapshot(
            weather=WeatherSnapshot(
                weather_type=WeatherType.CLEAR,
                temperature_c=20,
            ),
            pitch_condition=PitchCondition.GOOD,
        ),
        referee=RefereeSnapshot(referee_id="ref-1", name="Ref Demo"),
        kits=MatchKitSelectionSnapshot(
            home=KitSnapshot("home-kit", home_club_id, "Home", KitType.HOME),
            away=KitSnapshot("away-kit", away_club_id, "Away", KitType.AWAY),
        ),
    )


def make_snapshot(
    seed: int = 12345,
    *,
    home_prefix: str = "home",
    away_prefix: str = "away",
    pitch_length_m: float = 105.0,
    pitch_width_m: float = 68.0,
):
    formation = make_formation()
    home_club, home_lineup, home_tactic = make_side("home", home_prefix, formation)
    away_club, away_lineup, away_tactic = make_side("away", away_prefix, formation)
    return build_match_snapshot(
        match_id="spatial-match",
        seed=seed,
        context=make_context(
            pitch_length_m=pitch_length_m,
            pitch_width_m=pitch_width_m,
        ),
        home_club=home_club,
        home_lineup=home_lineup,
        home_tactic=home_tactic,
        away_club=away_club,
        away_lineup=away_lineup,
        away_tactic=away_tactic,
    )


def test_vector_math_supports_spatial_engine() -> None:
    vector = Vector2(3.0, 4.0)

    assert vector.magnitude == 5.0
    assert vector.normalized().x == pytest.approx(0.6)
    assert vector.normalized().y == pytest.approx(0.8)
    assert vector.distance_to(Vector2.zero()) == 5.0
    assert vector.scale(2.0) == Vector2(6.0, 8.0)


def test_match_clock_uses_fixed_quarter_second_ticks() -> None:
    clock = MatchClock()

    clock.advance(240)

    assert clock.tick_seconds == DEFAULT_TIMESTEP_SECONDS == 0.25
    assert clock.elapsed_seconds == 60.0
    assert clock.display == "01:00"


def test_pitch_geometry_has_centre_clamp_and_mirror() -> None:
    pitch = PitchDimensions(105.0, 68.0)

    assert pitch.centre == Vector2(52.5, 34.0)
    assert pitch.clamp(Vector2(-2.0, 80.0)) == Vector2(0.0, 68.0)
    assert pitch.mirror(Vector2(20.0, 10.0)) == Vector2(85.0, 58.0)


def test_initial_state_contains_exactly_22_active_agents() -> None:
    state = create_initial_match_state(make_snapshot())

    assert len(state.players) == 22
    assert len(state.home_players) == 11
    assert len(state.away_players) == 11


def test_initial_players_and_ball_are_inside_pitch() -> None:
    state = create_initial_match_state(make_snapshot())

    assert all(state.pitch.contains(agent.location) for agent in state.players.values())
    assert state.pitch.contains(state.ball.location)
    assert state.ball.location == state.pitch.centre


def test_initial_state_uses_stadium_pitch_dimensions() -> None:
    state = create_initial_match_state(
        make_snapshot(pitch_length_m=100.0, pitch_width_m=64.0)
    )

    assert state.pitch == PitchDimensions(100.0, 64.0)
    assert state.ball.location == Vector2(50.0, 32.0)


def test_agents_keep_snapshot_identity_slot_and_position() -> None:
    state = create_initial_match_state(make_snapshot())
    striker = state.player_for_slot(TeamSide.HOME, "st")

    assert striker.player.player_id == "home-st"
    assert striker.slot_id == "st"
    assert striker.assigned_position is Position.ST
    assert striker.side is TeamSide.HOME


def test_away_shape_is_180_degree_mirror_of_home_shape() -> None:
    state = create_initial_match_state(make_snapshot())
    home_left_back = state.player_for_slot(TeamSide.HOME, "lb")
    away_left_back = state.player_for_slot(TeamSide.AWAY, "lb")

    assert away_left_back.location == state.pitch.mirror(home_left_back.location)
    assert home_left_back.facing == Vector2(1.0, 0.0)
    assert away_left_back.facing == Vector2(-1.0, 0.0)


def test_same_snapshot_and_seed_create_identical_initial_state() -> None:
    snapshot = make_snapshot(seed=90210)

    first = SpatialMatchEngine(snapshot)
    second = SpatialMatchEngine(snapshot)

    assert first.state.signature() == second.state.signature()


def test_kickoff_side_is_deterministic_and_sets_initial_team_possession() -> None:
    snapshot = make_snapshot(seed=777)
    first = SpatialMatchEngine(snapshot).state
    second = SpatialMatchEngine(snapshot).state

    assert first.kickoff_side == second.kickoff_side
    assert first.possession.team_side == first.kickoff_side
    assert first.possession.owner_agent_id is None
    assert first.ball.owner_agent_id is None


def test_side_scoped_agent_ids_prevent_cross_team_player_id_collisions() -> None:
    state = create_initial_match_state(
        make_snapshot(home_prefix="shared", away_prefix="shared")
    )

    assert len(state.players) == 22
    assert "home:shared-st" in state.players
    assert "away:shared-st" in state.players


def test_engine_fixed_step_integrates_player_velocity_and_facing() -> None:
    engine = SpatialMatchEngine(make_snapshot())
    player = engine.state.player_for_slot(TeamSide.HOME, "cm")
    initial = player.location
    engine.set_player_velocity(player.agent_id, Vector2(4.0, 0.0))

    engine.step()

    assert player.location == Vector2(initial.x + 1.0, initial.y)
    assert player.facing == Vector2(1.0, 0.0)
    assert engine.state.clock.tick_count == 1
    assert engine.state.clock.elapsed_seconds == 0.25


def test_engine_fixed_step_integrates_ball_velocity() -> None:
    engine = SpatialMatchEngine(make_snapshot())
    initial = engine.state.ball.location
    engine.set_ball_velocity(Vector2(0.0, -8.0))

    engine.step()

    assert engine.state.ball.location == Vector2(initial.x, initial.y - 2.0)


def test_playback_chunking_does_not_change_simulation_path() -> None:
    snapshot = make_snapshot(seed=2468)
    x1 = SpatialMatchEngine(snapshot)
    x4 = SpatialMatchEngine(snapshot)

    x1_player = x1.state.player_for_slot(TeamSide.HOME, "rw")
    x4_player = x4.state.player_for_slot(TeamSide.HOME, "rw")
    x1.set_player_velocity(x1_player.agent_id, Vector2(2.0, -1.0))
    x4.set_player_velocity(x4_player.agent_id, Vector2(2.0, -1.0))

    for _ in range(4):
        x1.advance_ticks(1)
    x4.advance_ticks(4)

    assert x1.state.signature() == x4.state.signature()


def test_advance_ticks_rejects_negative_values() -> None:
    engine = SpatialMatchEngine(make_snapshot())

    with pytest.raises(ValueError, match="ticks must be non-negative"):
        engine.advance_ticks(-1)
