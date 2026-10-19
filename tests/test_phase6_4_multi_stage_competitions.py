from __future__ import annotations

from datetime import date

import pytest

from football_manager.domain import (
    CompetitionDefinition,
    CompetitionEdition,
    CompetitionFormat,
    CompetitionScope,
    CompetitionStage,
    CompetitionStageKind,
    LeagueStandingRow,
    StageRouteKind,
    StandingRouteRule,
    merge_stage_participants,
    next_stage_id,
    resolve_standing_stage_transition,
    validate_multi_stage_edition,
)


def standings(count: int = 8) -> tuple[LeagueStandingRow, ...]:
    return tuple(
        LeagueStandingRow(
            position=position,
            club_id=f"club-{position:02d}",
            played=7,
            won=max(0, 8-position),
            drawn=0,
            lost=max(0, position-1),
            goals_for=20-position,
            goals_against=position,
            points=max(0, (8-position)*3),
        )
        for position in range(1, count + 1)
    )


def edition() -> CompetitionEdition:
    clubs = tuple(f"club-{index:02d}" for index in range(1, 9))
    return CompetitionEdition(
        edition_id="dev-multi-2026-27",
        competition=CompetitionDefinition(
            competition_id="dev-multi",
            name="Development Continental",
            short_name="DMC",
            scope=CompetitionScope.CONTINENTAL,
            format=CompetitionFormat.MULTI_STAGE,
        ),
        season_label="2026/27",
        participant_club_ids=clubs,
        stages=(
            CompetitionStage("league-phase", "League phase", CompetitionStageKind.LEAGUE_PHASE, 1, clubs),
            CompetitionStage("playoff", "Playoff", CompetitionStageKind.PLAYOFF, 2),
            CompetitionStage("semifinal", "Semi-final", CompetitionStageKind.KNOCKOUT, 3),
            CompetitionStage("final", "Final", CompetitionStageKind.KNOCKOUT, 4),
        ),
    )


def routes() -> tuple[StandingRouteRule, ...]:
    return (
        StandingRouteRule(
            "direct-semi",
            "Direct semi-final",
            "league-phase",
            (1, 2),
            StageRouteKind.ADVANCE,
            "semifinal",
        ),
        StandingRouteRule(
            "playoff",
            "Playoff",
            "league-phase",
            (3, 4, 5, 6),
            StageRouteKind.PLAYOFF,
            "playoff",
        ),
        StandingRouteRule(
            "out",
            "Eliminated",
            "league-phase",
            (7, 8),
            StageRouteKind.ELIMINATED,
        ),
    )


def test_multi_stage_edition_and_routes_validate() -> None:
    validate_multi_stage_edition(edition(), routes())


def test_standings_route_direct_playoff_and_eliminated_bands() -> None:
    transition = resolve_standing_stage_transition(standings(), routes())

    assert transition.for_target("semifinal") == ("club-01", "club-02")
    assert transition.for_target("playoff") == (
        "club-03",
        "club-04",
        "club-05",
        "club-06",
    )
    assert transition.eliminated_club_ids == ("club-07", "club-08")
    assert transition.assignment_for_club("club-03").route is StageRouteKind.PLAYOFF


def test_unmatched_positions_are_eliminated_by_default() -> None:
    transition = resolve_standing_stage_transition(standings(), routes()[:2])
    assert transition.eliminated_club_ids == ("club-07", "club-08")


def test_unmatched_positions_can_be_rejected_strictly() -> None:
    with pytest.raises(ValueError, match="has no route"):
        resolve_standing_stage_transition(
            standings(), routes()[:2], eliminate_unmatched=False
        )


def test_overlapping_standing_routes_are_rejected() -> None:
    overlapping = (
        *routes(),
        StandingRouteRule(
            "bad-overlap",
            "Bad overlap",
            "league-phase",
            (2, 3),
            StageRouteKind.PLAYOFF,
            "playoff",
        ),
    )
    with pytest.raises(ValueError, match="overlapping routes"):
        resolve_standing_stage_transition(standings(), overlapping)


def test_merge_stage_participants_combines_direct_qualifiers_and_playoff_winners() -> None:
    participants = merge_stage_participants(
        ("club-01", "club-02"),
        ("club-03", "club-05"),
    )
    assert participants == ("club-01", "club-02", "club-03", "club-05")


def test_merge_stage_participants_rejects_duplicate_club() -> None:
    with pytest.raises(ValueError, match="duplicate stage participant"):
        merge_stage_participants(("club-01", "club-02"), ("club-02", "club-03"))


def test_next_stage_follows_edition_order() -> None:
    item = edition()
    assert next_stage_id(item, "league-phase") == "playoff"
    assert next_stage_id(item, "playoff") == "semifinal"
    assert next_stage_id(item, "final") is None


def test_route_serialization_round_trip() -> None:
    original = routes()[0]
    assert StandingRouteRule.from_dict(original.to_dict()) == original


def test_validation_rejects_backward_route() -> None:
    bad = StandingRouteRule(
        "back",
        "Backward",
        "league-phase",
        (1, 2),
        StageRouteKind.ADVANCE,
        "league-phase",
    )
    with pytest.raises(ValueError, match="later stage"):
        validate_multi_stage_edition(edition(), (bad,))


def test_dev_calendar_exposes_full_league_and_cross_competition_schedule() -> None:
    from football_manager.dev_ui import DevelopmentSession

    session = DevelopmentSession()
    rows = session.calendar_rows

    assert sum(row.competition == "Premier League" for row in rows) == 38
    assert sum(row.competition == "UEFA Champions League" for row in rows) == 8
    assert not any(row.competition == "Development Continental" for row in rows)
    assert any(row.competition == "Carabao Cup" for row in rows)
    assert not any(row.competition == "Development Cup" for row in rows)
    assert len(rows) >= 47  # future UEFA rounds appear only after actual qualification


def test_dev_continue_reaches_cup_instead_of_playing_only_league() -> None:
    from football_manager.dev_ui import DevelopmentSession

    session = DevelopmentSession()
    visited = []
    for _ in range(8):
        visited.append((session.current_date, session._active_match.competition_key))
        if session._active_match.competition_key in ("carabao-cup", "fa-cup"):
            break
        session.quick_simulate()
        session.continue_to_next_match()

    assert any(key == "carabao-cup" and date(2026, 8, 24) <= played <= date(2026, 8, 30)
               for played, key in visited)


def test_dev_morale_moves_with_managed_result() -> None:
    from football_manager.dev_ui import DevelopmentSession

    session = DevelopmentSession()
    before = session.tactical_team_state().squad_morale
    result = session.quick_simulate()
    after = session.tactical_team_state().squad_morale

    if result.home_club_id == session.home_club.id:
        managed_goals, opponent_goals = result.home_goals, result.away_goals
    else:
        managed_goals, opponent_goals = result.away_goals, result.home_goals
    if managed_goals > opponent_goals:
        assert after > before
    elif managed_goals < opponent_goals:
        assert after < before
    else:
        assert after > before


def test_dev_multistage_league_phase_creates_transition_and_playoff() -> None:
    from football_manager.dev_ui import DevelopmentSession

    session = DevelopmentSession()
    for round_number in range(1, 8):
        session._complete_continental_league_round(round_number)
    session._finish_continental_league_phase()

    assert len(session._continental_league_results) == 28
    assert session._continental_transition is not None
    assert len(session._continental_transition.for_target("semifinal")) == 2
    assert len(session._continental_transition.for_target("playoff")) == 4
    assert session._continental_rounds[0].definition.name == "Playoff"
