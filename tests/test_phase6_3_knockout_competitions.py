from __future__ import annotations

import pytest

from football_manager.domain import (
    CompetitionDefinition,
    CompetitionEdition,
    CompetitionFormat,
    CompetitionScope,
    CompetitionStage,
    CompetitionStageKind,
    KnockoutDrawSource,
    KnockoutLegFormat,
    KnockoutMatchResult,
    KnockoutRoundDefinition,
    MatchDecider,
    advance_knockout_round,
    generate_knockout_round,
    knockout_context_for_fixture,
    resolve_knockout_round,
    resolve_knockout_tie,
    seed_knockout_round,
    validate_knockout_edition,
)


def clubs(count: int = 8) -> tuple[str, ...]:
    return tuple(f"club-{index:02d}" for index in range(1, count + 1))


def make_edition(participants: tuple[str, ...] | None = None) -> CompetitionEdition:
    participants = participants or clubs()
    return CompetitionEdition(
        edition_id="dev-cup-2026-27",
        competition=CompetitionDefinition(
            competition_id="dev-cup",
            name="Development Cup",
            short_name="DC",
            scope=CompetitionScope.DOMESTIC,
            format=CompetitionFormat.KNOCKOUT,
            country="England",
        ),
        season_label="2026/27",
        participant_club_ids=participants,
        stages=(
            CompetitionStage(
                stage_id="knockout",
                name="Knockout",
                kind=CompetitionStageKind.KNOCKOUT,
                order=1,
                participant_club_ids=participants,
                match_decider=MatchDecider.EXTRA_TIME_AND_PENALTIES,
            ),
        ),
    )


def quarterfinal(*, two_legged: bool = False) -> KnockoutRoundDefinition:
    return KnockoutRoundDefinition(
        round_id="quarterfinal",
        name="Quarter-final",
        order=1,
        leg_format=(
            KnockoutLegFormat.TWO_LEGGED
            if two_legged
            else KnockoutLegFormat.SINGLE_LEG
        ),
    )


def test_single_leg_round_pairs_every_club_once() -> None:
    plan = generate_knockout_round(
        edition_id="dev-cup-2026-27",
        stage_id="knockout",
        definition=quarterfinal(),
        participant_club_ids=clubs(),
        seed=63,
    )

    assert len(plan.ties) == 4
    assert len(plan.fixtures) == 4
    assert set(plan.participant_club_ids) == set(clubs())
    assert all(fixture.leg_number == 1 for fixture in plan.fixtures)


def test_two_legged_round_reverses_home_and_away() -> None:
    plan = generate_knockout_round(
        edition_id="dev-cup-2026-27",
        stage_id="knockout",
        definition=quarterfinal(two_legged=True),
        participant_club_ids=clubs(),
        seed=63,
    )

    assert len(plan.fixtures) == 8
    for tie in plan.ties:
        first, second = tie.fixtures
        assert first.home_club_id == second.away_club_id
        assert first.away_club_id == second.home_club_id
        assert (first.leg_number, second.leg_number) == (1, 2)




def test_seeded_round_preserves_external_pairings_exactly() -> None:
    pairings = (("club-01", "club-08"), ("club-02", "club-07"), ("club-03", "club-06"), ("club-04", "club-05"))
    plan = seed_knockout_round(
        edition_id="dev-cup-2026-27",
        stage_id="knockout",
        definition=quarterfinal(),
        pairings=pairings,
    )

    assert plan.source is KnockoutDrawSource.SEEDED
    assert tuple((tie.club_a_id, tie.club_b_id) for tie in plan.ties) == pairings
    assert tuple((f.home_club_id, f.away_club_id) for f in plan.fixtures) == pairings


def test_knockout_draw_is_reproducible_for_same_seed() -> None:
    kwargs = dict(
        edition_id="dev-cup-2026-27",
        stage_id="knockout",
        definition=quarterfinal(),
        participant_club_ids=clubs(),
    )
    first = generate_knockout_round(**kwargs, seed=11)
    same = generate_knockout_round(**kwargs, seed=11)
    other = generate_knockout_round(**kwargs, seed=12)

    assert first == same
    assert [(t.club_a_id, t.club_b_id) for t in first.ties] != [
        (t.club_a_id, t.club_b_id) for t in other.ties
    ]


def test_single_leg_tie_resolves_from_score() -> None:
    plan = generate_knockout_round(
        edition_id="dev-cup-2026-27",
        stage_id="knockout",
        definition=quarterfinal(),
        participant_club_ids=clubs(2),
    )
    tie = plan.ties[0]
    fixture = tie.fixtures[0]
    outcome = resolve_knockout_tie(
        tie,
        (KnockoutMatchResult(fixture.fixture_id, 3, 1),),
    )

    assert outcome.complete
    assert outcome.winner_club_id == fixture.home_club_id
    assert outcome.aggregate_a_goals == 3
    assert outcome.aggregate_b_goals == 1


def test_single_leg_tie_can_be_decided_by_penalties() -> None:
    plan = generate_knockout_round(
        edition_id="dev-cup-2026-27",
        stage_id="knockout",
        definition=quarterfinal(),
        participant_club_ids=clubs(2),
    )
    tie = plan.ties[0]
    fixture = tie.fixtures[0]
    outcome = resolve_knockout_tie(
        tie,
        (KnockoutMatchResult(fixture.fixture_id, 1, 1, 4, 5),),
    )

    assert outcome.complete
    assert outcome.decided_by_penalties
    assert outcome.winner_club_id == fixture.away_club_id


def test_two_legged_tie_uses_aggregate_without_away_goals_rule() -> None:
    plan = generate_knockout_round(
        edition_id="dev-cup-2026-27",
        stage_id="knockout",
        definition=quarterfinal(two_legged=True),
        participant_club_ids=clubs(2),
    )
    tie = plan.ties[0]
    first, second = tie.fixtures
    outcome = resolve_knockout_tie(
        tie,
        (
            KnockoutMatchResult(first.fixture_id, 1, 0),
            KnockoutMatchResult(second.fixture_id, 2, 1, 5, 4),
        ),
    )

    assert outcome.aggregate_a_goals == 2
    assert outcome.aggregate_b_goals == 2
    assert outcome.complete
    assert outcome.decided_by_penalties
    assert outcome.winner_club_id == second.home_club_id


def test_two_legged_tie_can_resolve_on_aggregate_without_penalties() -> None:
    plan = generate_knockout_round(
        edition_id="dev-cup-2026-27",
        stage_id="knockout",
        definition=quarterfinal(two_legged=True),
        participant_club_ids=clubs(2),
    )
    tie = plan.ties[0]
    first, second = tie.fixtures
    outcome = resolve_knockout_tie(
        tie,
        (
            KnockoutMatchResult(first.fixture_id, 2, 0),
            KnockoutMatchResult(second.fixture_id, 1, 1),
        ),
    )

    assert outcome.complete
    assert outcome.winner_club_id == first.home_club_id
    assert (outcome.aggregate_a_goals, outcome.aggregate_b_goals) == (3, 1)


def test_first_leg_allows_draw_and_second_leg_receives_reoriented_aggregate() -> None:
    participants = clubs(2)
    edition = make_edition(participants)
    plan = generate_knockout_round(
        edition_id=edition.edition_id,
        stage_id="knockout",
        definition=quarterfinal(two_legged=True),
        participant_club_ids=participants,
    )
    first, second = plan.ties[0].fixtures

    first_context = knockout_context_for_fixture(
        edition=edition,
        stage_id="knockout",
        plan=plan,
        fixture_id=first.fixture_id,
    )
    assert first_context.match_decider is MatchDecider.DRAW_ALLOWED
    assert first_context.cup_tie is not None
    assert first_context.cup_tie.home_aggregate_goals_before_match == 0

    second_context = knockout_context_for_fixture(
        edition=edition,
        stage_id="knockout",
        plan=plan,
        fixture_id=second.fixture_id,
        results=(KnockoutMatchResult(first.fixture_id, 2, 1),),
    )
    assert second_context.match_decider is MatchDecider.EXTRA_TIME_AND_PENALTIES
    assert second_context.cup_tie is not None
    # Leg two reverses venue, so the old away score becomes current-home aggregate.
    assert second_context.cup_tie.home_aggregate_goals_before_match == 1
    assert second_context.cup_tie.away_aggregate_goals_before_match == 2
    assert second_context.cup_tie.leg_number == 2


def test_later_leg_requires_previous_result() -> None:
    participants = clubs(2)
    edition = make_edition(participants)
    plan = generate_knockout_round(
        edition_id=edition.edition_id,
        stage_id="knockout",
        definition=quarterfinal(two_legged=True),
        participant_club_ids=participants,
    )
    second = plan.ties[0].fixtures[1]

    with pytest.raises(ValueError, match="prior knockout leg result"):
        knockout_context_for_fixture(
            edition=edition,
            stage_id="knockout",
            plan=plan,
            fixture_id=second.fixture_id,
        )


def test_complete_round_advances_only_winners() -> None:
    plan = generate_knockout_round(
        edition_id="dev-cup-2026-27",
        stage_id="knockout",
        definition=quarterfinal(),
        participant_club_ids=clubs(),
        seed=5,
    )
    results = tuple(
        KnockoutMatchResult(fixture.fixture_id, 2, 0) for fixture in plan.fixtures
    )
    outcome = resolve_knockout_round(plan, results)
    semi = advance_knockout_round(
        outcome,
        edition_id="dev-cup-2026-27",
        stage_id="knockout",
        next_definition=KnockoutRoundDefinition(
            round_id="semifinal",
            name="Semi-final",
            order=2,
        ),
        seed=6,
    )

    assert outcome.complete
    assert len(outcome.winner_club_ids) == 4
    assert len(semi.ties) == 2
    assert set(semi.participant_club_ids) == set(outcome.winner_club_ids)


def test_incomplete_round_cannot_advance() -> None:
    plan = generate_knockout_round(
        edition_id="dev-cup-2026-27",
        stage_id="knockout",
        definition=quarterfinal(),
        participant_club_ids=clubs(4),
    )
    partial = resolve_knockout_round(
        plan,
        (KnockoutMatchResult(plan.fixtures[0].fixture_id, 1, 0),),
    )

    assert not partial.complete
    with pytest.raises(ValueError, match="incomplete"):
        advance_knockout_round(
            partial,
            edition_id="dev-cup-2026-27",
            stage_id="knockout",
            next_definition=KnockoutRoundDefinition("final", "Final", 2),
        )


def test_knockout_result_serializes_penalty_score() -> None:
    result = KnockoutMatchResult("fixture-1", 2, 2, 6, 5)
    assert KnockoutMatchResult.from_dict(result.to_dict()) == result


def test_odd_participant_count_is_rejected() -> None:
    with pytest.raises(ValueError, match="even number"):
        generate_knockout_round(
            edition_id="dev-cup-2026-27",
            stage_id="knockout",
            definition=quarterfinal(),
            participant_club_ids=clubs(3),
        )


def test_knockout_edition_requires_knockout_stage() -> None:
    edition = make_edition(clubs(4))
    validate_knockout_edition(edition, "knockout")

    bad = CompetitionEdition(
        edition_id="bad",
        competition=edition.competition,
        season_label="2026/27",
        participant_club_ids=clubs(4),
        stages=(
            CompetitionStage(
                stage_id="league",
                name="League",
                kind=CompetitionStageKind.ROUND_ROBIN,
                order=1,
            ),
        ),
    )
    with pytest.raises(ValueError, match="KNOCKOUT"):
        validate_knockout_edition(bad, "league")


def test_development_sandbox_exposes_and_advances_knockout_bracket() -> None:
    from football_manager.dev_ui.session import DevelopmentSession

    session = DevelopmentSession()
    # The legacy eight-club inspector is independent from the real FA/Carabao schedule.
    assert session.can_simulate_cup_round is True
    assert len(session.cup_bracket_rows()) == 4
    assert any(name == "Development Cup" for name, _format, _status in session.competition_rows)
    assert "Development Cup" not in {item.competition for item in session.calendar_rows}

    session.simulate_dev_cup_round()
    assert "Semi-final" in session.cup_summary
    assert len(session.cup_bracket_rows()) == 8  # 4 QF + 2 SF ties x 2 legs


def test_development_cup_reset_rebuilds_the_initial_quarterfinal() -> None:
    from football_manager.dev_ui.session import DevelopmentSession

    session = DevelopmentSession()
    session.simulate_dev_cup_round()
    session.reset()

    assert "Quarter-final" in session.cup_summary
    assert session.can_simulate_cup_round is True
    assert all(row.score == "-" for row in session.cup_bracket_rows())
