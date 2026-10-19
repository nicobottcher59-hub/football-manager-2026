from __future__ import annotations

import pytest

from football_manager.domain import (
    CompetitionDefinition,
    CompetitionEdition,
    CompetitionFormat,
    CompetitionScope,
    CompetitionStage,
    CompetitionStageKind,
    LeaguePointsRule,
    LeagueResult,
    LeagueTiebreaker,
    FixturePlanSource,
    RoundRobinFixturePlan,
    RoundRobinTemplate,
    build_league_table,
    generate_double_round_robin,
    standings_snapshots,
    validate_double_round_robin,
    validate_round_robin_edition,
)


def club_ids(count: int = 20) -> tuple[str, ...]:
    return tuple(f"club-{index:02d}" for index in range(1, count + 1))


def make_edition(fixtures, participants=None) -> CompetitionEdition:
    participants = participants or club_ids()
    return CompetitionEdition(
        edition_id="eng-premier-2026-27",
        competition=CompetitionDefinition(
            competition_id="eng-premier",
            name="Development Premier League",
            short_name="DPL",
            scope=CompetitionScope.DOMESTIC,
            format=CompetitionFormat.LEAGUE,
            country="England",
        ),
        season_label="2026/27",
        participant_club_ids=participants,
        stages=(
            CompetitionStage(
                stage_id="league",
                name="League",
                kind=CompetitionStageKind.ROUND_ROBIN,
                order=1,
                participant_club_ids=participants,
            ),
        ),
        fixtures=tuple(fixtures),
    )


def test_twenty_clubs_generate_38_rounds_and_380_fixtures() -> None:
    participants = club_ids()
    fixtures = generate_double_round_robin(
        edition_id="eng-premier-2026-27",
        stage_id="league",
        participant_club_ids=participants,
        seed=2026,
    )

    assert len(fixtures) == 380
    assert {fixture.round_number for fixture in fixtures} == set(range(1, 39))
    for round_number in range(1, 39):
        round_fixtures = [f for f in fixtures if f.round_number == round_number]
        assert len(round_fixtures) == 10
        involved = {
            club_id
            for fixture in round_fixtures
            for club_id in (fixture.home_club_id, fixture.away_club_id)
        }
        assert involved == set(participants)


def test_every_pair_meets_once_at_each_venue() -> None:
    participants = club_ids(6)
    fixtures = generate_double_round_robin(
        edition_id="league-2026",
        stage_id="league",
        participant_club_ids=participants,
    )

    validate_double_round_robin(fixtures, participants)
    for first in participants:
        for second in participants:
            if first == second:
                continue
            assert sum(
                fixture.home_club_id == first and fixture.away_club_id == second
                for fixture in fixtures
            ) == 1


def test_second_half_reverses_first_half_venues() -> None:
    participants = club_ids(6)
    fixtures = generate_double_round_robin(
        edition_id="league-2026",
        stage_id="league",
        participant_club_ids=participants,
    )
    first_half = [fixture for fixture in fixtures if fixture.round_number <= 5]
    second_half = [fixture for fixture in fixtures if fixture.round_number > 5]

    for fixture in first_half:
        assert any(
            candidate.home_club_id == fixture.away_club_id
            and candidate.away_club_id == fixture.home_club_id
            and candidate.round_number == fixture.round_number + 5
            for candidate in second_half
        )


def test_generation_is_reproducible_for_same_seed_and_varies_for_new_seed() -> None:
    participants = club_ids(8)
    first = generate_double_round_robin(
        edition_id="league-2026",
        stage_id="league",
        participant_club_ids=participants,
        seed=11,
    )
    same = generate_double_round_robin(
        edition_id="league-2026",
        stage_id="league",
        participant_club_ids=participants,
        seed=11,
    )
    other = generate_double_round_robin(
        edition_id="league-2026",
        stage_id="league",
        participant_club_ids=participants,
        seed=12,
    )

    assert first == same
    assert [(f.home_club_id, f.away_club_id) for f in first] != [
        (f.home_club_id, f.away_club_id) for f in other
    ]


def test_round_robin_template_can_be_extracted_from_seeded_first_season() -> None:
    participants = club_ids(6)
    seeded = generate_double_round_robin(
        edition_id="league-2026",
        stage_id="league",
        participant_club_ids=participants,
        seed=26,
    )

    template = RoundRobinTemplate.from_fixtures(seeded, participants)

    assert template.participant_count == 6
    assert len(template.slot_fixtures) == 30


def test_template_can_generate_next_season_with_promoted_clubs() -> None:
    original = club_ids(6)
    first_season = generate_double_round_robin(
        edition_id="league-2026",
        stage_id="league",
        participant_club_ids=original,
        seed=26,
    )
    template = RoundRobinTemplate.from_fixtures(first_season, original)
    next_season = ("club-01", "club-02", "club-03", "club-04", "promoted-a", "promoted-b")

    generated = template.instantiate(
        edition_id="league-2027",
        stage_id="league",
        participant_club_ids=next_season,
        seed=27,
    )

    validate_double_round_robin(generated, next_season)
    assert len(generated) == 30
    assert {f.home_club_id for f in generated} | {f.away_club_id for f in generated} == set(
        next_season
    )


def test_template_seed_changes_slot_assignment_without_changing_round_structure() -> None:
    participants = club_ids(8)
    seeded = generate_double_round_robin(
        edition_id="league-2026",
        stage_id="league",
        participant_club_ids=participants,
        seed=26,
    )
    template = RoundRobinTemplate.from_fixtures(seeded, participants)

    season_a = template.instantiate(
        edition_id="league-2027",
        stage_id="league",
        participant_club_ids=participants,
        seed=1,
    )
    season_b = template.instantiate(
        edition_id="league-2028",
        stage_id="league",
        participant_club_ids=participants,
        seed=2,
    )

    assert [f.round_number for f in season_a] == [f.round_number for f in season_b]
    assert [(f.home_club_id, f.away_club_id) for f in season_a] != [
        (f.home_club_id, f.away_club_id) for f in season_b
    ]


def test_invalid_double_round_robin_is_rejected() -> None:
    participants = club_ids(4)
    fixtures = list(
        generate_double_round_robin(
            edition_id="league-2026",
            stage_id="league",
            participant_club_ids=participants,
        )
    )
    fixtures.pop()

    with pytest.raises(ValueError, match="requires 12 fixtures"):
        validate_double_round_robin(fixtures, participants)


def test_league_table_applies_win_draw_loss_points_and_goals() -> None:
    participants = club_ids(4)
    fixtures = generate_double_round_robin(
        edition_id="league-2026",
        stage_id="league",
        participant_club_ids=participants,
    )
    first_round = [fixture for fixture in fixtures if fixture.round_number == 1]
    results = (
        LeagueResult(first_round[0].fixture_id, 2, 0),
        LeagueResult(first_round[1].fixture_id, 1, 1),
    )

    table = build_league_table(
        participant_club_ids=participants,
        fixtures=fixtures,
        results=results,
    )

    assert sum(row.points for row in table) == 5
    assert sum(row.goals_for for row in table) == 4
    assert sum(row.goals_against for row in table) == 4
    assert all(row.played == 1 for row in table)
    assert table[0].points == 3


def test_table_supports_custom_points_rules() -> None:
    participants = club_ids(4)
    fixtures = generate_double_round_robin(
        edition_id="league-2026",
        stage_id="league",
        participant_club_ids=participants,
    )
    fixture = fixtures[0]
    table = build_league_table(
        participant_club_ids=participants,
        fixtures=fixtures,
        results=(LeagueResult(fixture.fixture_id, 1, 1),),
        points_rule=LeaguePointsRule(win=2, draw=1, loss=0),
    )

    involved = {fixture.home_club_id, fixture.away_club_id}
    assert all(row.points == 1 for row in table if row.club_id in involved)


def test_table_orders_by_points_goal_difference_goals_for_then_wins() -> None:
    participants = club_ids(4)
    fixtures = generate_double_round_robin(
        edition_id="league-2026",
        stage_id="league",
        participant_club_ids=participants,
    )
    fixture_by_pair = {
        (fixture.home_club_id, fixture.away_club_id): fixture for fixture in fixtures
    }

    # Create two clubs on 3 points. club-01 has the better goal difference.
    f1 = fixture_by_pair[("club-01", "club-02")]
    f2 = fixture_by_pair[("club-03", "club-04")]
    table = build_league_table(
        participant_club_ids=participants,
        fixtures=fixtures,
        results=(LeagueResult(f1.fixture_id, 4, 0), LeagueResult(f2.fixture_id, 1, 0)),
    )

    assert table[0].club_id == "club-01"
    assert table[1].club_id == "club-03"


def test_table_rejects_duplicate_result_for_same_fixture() -> None:
    participants = club_ids(4)
    fixtures = generate_double_round_robin(
        edition_id="league-2026",
        stage_id="league",
        participant_club_ids=participants,
    )
    result = LeagueResult(fixtures[0].fixture_id, 1, 0)

    with pytest.raises(ValueError, match="more than one final result"):
        build_league_table(
            participant_club_ids=participants,
            fixtures=fixtures,
            results=(result, result),
        )


def test_table_rejects_result_for_unknown_fixture() -> None:
    participants = club_ids(4)
    fixtures = generate_double_round_robin(
        edition_id="league-2026",
        stage_id="league",
        participant_club_ids=participants,
    )

    with pytest.raises(ValueError, match="unknown fixture"):
        build_league_table(
            participant_club_ids=participants,
            fixtures=fixtures,
            results=(LeagueResult("missing", 1, 0),),
        )


def test_standing_rows_convert_to_match_context_snapshots() -> None:
    participants = club_ids(4)
    fixtures = generate_double_round_robin(
        edition_id="league-2026",
        stage_id="league",
        participant_club_ids=participants,
    )
    table = build_league_table(
        participant_club_ids=participants,
        fixtures=fixtures,
        results=(),
    )

    snapshots = standings_snapshots(table, club_names={"club-01": "Club One"})

    assert snapshots[0].position == 1
    assert next(row for row in snapshots if row.club_id == "club-01").club_name == "Club One"


def test_round_robin_edition_validation_uses_phase_6_1_framework() -> None:
    participants = club_ids(4)
    fixtures = generate_double_round_robin(
        edition_id="eng-premier-2026-27",
        stage_id="league",
        participant_club_ids=participants,
    )
    edition = make_edition(fixtures, participants)

    validate_round_robin_edition(edition, "league")


def test_custom_tiebreaker_order_is_supported() -> None:
    participants = club_ids(4)
    fixtures = generate_double_round_robin(
        edition_id="league-2026",
        stage_id="league",
        participant_club_ids=participants,
    )
    fixture_by_pair = {
        (fixture.home_club_id, fixture.away_club_id): fixture for fixture in fixtures
    }
    f1 = fixture_by_pair[("club-01", "club-02")]
    f2 = fixture_by_pair[("club-03", "club-04")]

    table = build_league_table(
        participant_club_ids=participants,
        fixtures=fixtures,
        results=(LeagueResult(f1.fixture_id, 2, 1), LeagueResult(f2.fixture_id, 3, 2)),
        tiebreakers=(LeagueTiebreaker.GOALS_FOR, LeagueTiebreaker.GOAL_DIFFERENCE),
    )

    assert table[0].club_id == "club-03"


def test_fixture_plan_records_seeded_vs_generated_provenance() -> None:
    participants = club_ids(6)
    generated = RoundRobinFixturePlan.generated(
        edition_id="league-2026",
        stage_id="league",
        participant_club_ids=participants,
        seed=26,
    )
    seeded = RoundRobinFixturePlan.seeded(
        fixtures=generated.fixtures,
        participant_club_ids=participants,
    )

    assert generated.source is FixturePlanSource.GENERATED
    assert seeded.source is FixturePlanSource.SEEDED
    assert seeded.template == generated.template


def test_development_sandbox_exposes_twenty_club_league_and_round_one() -> None:
    from football_manager.dev_ui import DevelopmentSession

    session = DevelopmentSession()

    assert len(session.league_table_rows()) == 20
    assert len(session.league_fixture_rows(1)) == 10
    assert "20 clubs" in session.league_summary
    assert "380 fixtures" in session.league_summary
    assert any(row.home == "Northbridge FC" and row.away == "Riverside Athletic" for row in session.league_fixture_rows(1))


def test_quick_sim_result_flows_into_development_league_table() -> None:
    from football_manager.dev_ui import DevelopmentSession

    session = DevelopmentSession()
    result = session.quick_simulate()
    rows = {row.club: row for row in session.league_table_rows()}

    northbridge = rows["Northbridge FC"]
    riverside = rows["Riverside Athletic"]
    assert northbridge.played == 1
    assert riverside.played == 1
    assert northbridge.goals_for == result.home_goals
    assert riverside.goals_for == result.away_goals
    assert any(row.status == "Played" for row in session.league_fixture_rows(1))
