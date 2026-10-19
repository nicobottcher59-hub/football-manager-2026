import pytest

from football_manager.domain import (
    CompetitionDefinition,
    CompetitionEdition,
    CompetitionFixture,
    CompetitionFormat,
    CompetitionScope,
    CompetitionStage,
    CompetitionStageKind,
    CompetitionStatus,
    MatchDecider,
    QualificationFallback,
    QualificationKind,
    QualificationRule,
    QualificationSource,
)


def make_club_ids(count: int = 20) -> tuple[str, ...]:
    return tuple(f"club-{index:02d}" for index in range(1, count + 1))


def make_definition() -> CompetitionDefinition:
    return CompetitionDefinition(
        competition_id="eng-premier",
        name="English Premier Division",
        short_name="EPD",
        scope=CompetitionScope.DOMESTIC,
        format=CompetitionFormat.LEAGUE,
        country="England",
    )


def make_stage(club_ids: tuple[str, ...]) -> CompetitionStage:
    return CompetitionStage(
        stage_id="league",
        name="League",
        kind=CompetitionStageKind.ROUND_ROBIN,
        order=1,
        participant_club_ids=club_ids,
        match_decider=MatchDecider.DRAW_ALLOWED,
    )


def test_competition_definition_has_stable_identity_and_round_trips() -> None:
    competition = make_definition()

    restored = CompetitionDefinition.from_dict(competition.to_dict())

    assert restored == competition
    assert restored.competition_id == "eng-premier"
    assert restored.scope is CompetitionScope.DOMESTIC
    assert restored.format is CompetitionFormat.LEAGUE


def test_competition_edition_validates_stage_participants() -> None:
    club_ids = make_club_ids(4)
    bad_stage = CompetitionStage(
        stage_id="league",
        name="League",
        kind=CompetitionStageKind.ROUND_ROBIN,
        order=1,
        participant_club_ids=club_ids + ("outsider",),
    )

    with pytest.raises(ValueError, match="outside edition"):
        CompetitionEdition(
            edition_id="eng-premier-2026-27",
            competition=make_definition(),
            season_label="2026/27",
            participant_club_ids=club_ids,
            stages=(bad_stage,),
        )


def test_stage_order_must_be_unique_and_contiguous() -> None:
    club_ids = make_club_ids(4)
    stages = (
        CompetitionStage("stage-1", "First", CompetitionStageKind.GROUP_STAGE, 1),
        CompetitionStage("stage-3", "Third", CompetitionStageKind.KNOCKOUT, 3),
    )

    with pytest.raises(ValueError, match="contiguous"):
        CompetitionEdition(
            edition_id="multi-2026",
            competition=CompetitionDefinition(
                "multi", "Multi", "MUL", CompetitionScope.CONTINENTAL, CompetitionFormat.MULTI_STAGE
            ),
            season_label="2026/27",
            participant_club_ids=club_ids,
            stages=stages,
        )


def test_league_positions_can_define_european_qualification_berths() -> None:
    club_ids = make_club_ids()
    champions_rule = QualificationRule(
        rule_id="ucl-league-places",
        label="Champions competition league places",
        kind=QualificationKind.CONTINENTAL,
        source=QualificationSource.STANDING_POSITION,
        target_competition_id="uefa-champions",
        target_stage_id="league-phase",
        standing_positions=(1, 2, 3, 4),
        priority=10,
    )
    europa_rule = QualificationRule(
        rule_id="uel-league-place",
        label="Europa competition league place",
        kind=QualificationKind.CONTINENTAL,
        source=QualificationSource.STANDING_POSITION,
        target_competition_id="uefa-europa",
        target_stage_id="league-phase",
        standing_positions=(5,),
        priority=20,
    )
    edition = CompetitionEdition(
        edition_id="eng-premier-2026-27",
        competition=make_definition(),
        season_label="2026/27",
        participant_club_ids=club_ids,
        stages=(make_stage(club_ids),),
        qualification_rules=(champions_rule, europa_rule),
    )

    assert edition.qualification_rules_for_position(1) == (champions_rule,)
    assert edition.qualification_rules_for_position(4) == (champions_rule,)
    assert edition.qualification_rules_for_position(5) == (europa_rule,)
    assert edition.qualification_rules_for_position(6) == ()
    assert edition.qualification_rules_by_kind(QualificationKind.CONTINENTAL) == (
        champions_rule,
        europa_rule,
    )


def test_cup_winner_route_can_fallback_to_next_eligible_league_position() -> None:
    rule = QualificationRule(
        rule_id="fa-cup-europa",
        label="Domestic cup winner Europa berth",
        kind=QualificationKind.CONTINENTAL,
        source=QualificationSource.CUP_WINNER,
        source_competition_id="eng-fa-cup",
        target_competition_id="uefa-europa",
        fallback=QualificationFallback.NEXT_ELIGIBLE_STANDING_POSITION,
        priority=5,
    )

    assert rule.source is QualificationSource.CUP_WINNER
    assert rule.fallback is QualificationFallback.NEXT_ELIGIBLE_STANDING_POSITION


def test_standing_qualification_rejects_invalid_positions() -> None:
    with pytest.raises(ValueError, match="must be positive"):
        QualificationRule(
            rule_id="bad",
            label="Bad",
            kind=QualificationKind.CONTINENTAL,
            source=QualificationSource.STANDING_POSITION,
            target_competition_id="uefa-champions",
            standing_positions=(0,),
        )

    club_ids = make_club_ids(4)
    impossible = QualificationRule(
        rule_id="too-low",
        label="Too low",
        kind=QualificationKind.RELEGATION,
        source=QualificationSource.STANDING_POSITION,
        target_competition_id="eng-second-tier",
        standing_positions=(5,),
    )
    with pytest.raises(ValueError, match="exceeds edition participant count"):
        CompetitionEdition(
            edition_id="small-2026",
            competition=make_definition(),
            season_label="2026/27",
            participant_club_ids=club_ids,
            stages=(make_stage(club_ids),),
            qualification_rules=(impossible,),
        )


def test_fixture_is_sporting_structure_without_schedule_data() -> None:
    fixture = CompetitionFixture(
        fixture_id="fixture-001",
        edition_id="eng-premier-2026-27",
        stage_id="league",
        home_club_id="club-01",
        away_club_id="club-02",
        round_number=1,
    )

    assert not hasattr(fixture, "kickoff")
    assert CompetitionFixture.from_dict(fixture.to_dict()) == fixture


def test_edition_validates_and_filters_fixtures_by_stage() -> None:
    club_ids = make_club_ids(4)
    stage = make_stage(club_ids)
    fixture = CompetitionFixture(
        fixture_id="fixture-001",
        edition_id="eng-premier-2026-27",
        stage_id="league",
        home_club_id=club_ids[0],
        away_club_id=club_ids[1],
        round_number=1,
    )
    edition = CompetitionEdition(
        edition_id="eng-premier-2026-27",
        competition=make_definition(),
        season_label="2026/27",
        participant_club_ids=club_ids,
        stages=(stage,),
        fixtures=(fixture,),
        status=CompetitionStatus.ACTIVE,
    )

    assert edition.has_participant(club_ids[2])
    assert edition.stage("league") == stage
    assert edition.fixtures_for_stage("league") == (fixture,)


def test_edition_round_trip_preserves_rules_stages_fixtures_and_status() -> None:
    club_ids = make_club_ids(4)
    rule = QualificationRule(
        rule_id="relegation",
        label="Relegation",
        kind=QualificationKind.RELEGATION,
        source=QualificationSource.STANDING_POSITION,
        target_competition_id="eng-second-tier",
        standing_positions=(4,),
    )
    fixture = CompetitionFixture(
        fixture_id="fixture-001",
        edition_id="eng-premier-2026-27",
        stage_id="league",
        home_club_id=club_ids[0],
        away_club_id=club_ids[1],
        round_number=1,
    )
    edition = CompetitionEdition(
        edition_id="eng-premier-2026-27",
        competition=make_definition(),
        season_label="2026/27",
        participant_club_ids=club_ids,
        stages=(make_stage(club_ids),),
        qualification_rules=(rule,),
        fixtures=(fixture,),
        status=CompetitionStatus.ACTIVE,
    )

    restored = CompetitionEdition.from_dict(edition.to_dict())

    assert restored == edition


def test_fixture_rejects_unknown_stage_or_outside_club() -> None:
    club_ids = make_club_ids(4)
    stage = make_stage(club_ids)
    unknown_stage_fixture = CompetitionFixture(
        fixture_id="fixture-001",
        edition_id="eng-premier-2026-27",
        stage_id="unknown",
        home_club_id=club_ids[0],
        away_club_id=club_ids[1],
    )
    with pytest.raises(ValueError, match="unknown stage"):
        CompetitionEdition(
            edition_id="eng-premier-2026-27",
            competition=make_definition(),
            season_label="2026/27",
            participant_club_ids=club_ids,
            stages=(stage,),
            fixtures=(unknown_stage_fixture,),
        )

    outside_fixture = CompetitionFixture(
        fixture_id="fixture-002",
        edition_id="eng-premier-2026-27",
        stage_id="league",
        home_club_id=club_ids[0],
        away_club_id="outsider",
    )
    with pytest.raises(ValueError, match="outside competition edition"):
        CompetitionEdition(
            edition_id="eng-premier-2026-27",
            competition=make_definition(),
            season_label="2026/27",
            participant_club_ids=club_ids,
            stages=(stage,),
            fixtures=(outside_fixture,),
        )


def test_edition_builds_match_context_from_competition_rules() -> None:
    from football_manager.domain import CompetitionRegulations

    club_ids = make_club_ids(4)
    stage = CompetitionStage(
        stage_id="semi-final",
        name="Semi-final",
        kind=CompetitionStageKind.KNOCKOUT,
        order=1,
        participant_club_ids=club_ids,
        match_decider=MatchDecider.EXTRA_TIME_AND_PENALTIES,
    )
    edition = CompetitionEdition(
        edition_id="cup-2026",
        competition=CompetitionDefinition(
            "cup", "Domestic Cup", "CUP", CompetitionScope.DOMESTIC, CompetitionFormat.KNOCKOUT
        ),
        season_label="2026/27",
        participant_club_ids=club_ids,
        stages=(stage,),
        regulations=CompetitionRegulations(
            substitution_limit=5,
            extra_time_additional_substitutions=1,
        ),
    )

    context = edition.context_snapshot("semi-final")

    assert context.competition_id == "cup"
    assert context.competition_name == "Domestic Cup"
    assert context.season_label == "2026/27"
    assert context.stage_label == "Semi-final"
    assert context.match_decider is MatchDecider.EXTRA_TIME_AND_PENALTIES
    assert context.substitution_limit == 5
    assert context.extra_time_additional_substitutions == 1
