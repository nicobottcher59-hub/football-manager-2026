from __future__ import annotations

from datetime import date

from football_manager.data import load_premier_league_2026_27
from football_manager.domain import FixturePlanSource, RoundRobinFixturePlan, ScheduleSource


def test_official_premier_2026_27_loads_full_competition_and_calendar() -> None:
    bundle = load_premier_league_2026_27()

    assert bundle.metadata.season_label == "2026/27"
    assert bundle.metadata.competition_name == "Premier League"
    assert len(bundle.club_names) == 20
    assert len(bundle.edition.fixtures) == 380
    assert len(bundle.calendar.fixtures) == 380


def test_official_premier_dataset_has_expected_season_bounds() -> None:
    bundle = load_premier_league_2026_27()
    dates = [fixture.match_date for fixture in bundle.calendar.fixtures]

    assert min(dates) == date(2026, 8, 21)
    assert max(dates) == date(2027, 5, 30)
    assert bundle.calendar.timezone_name == "Europe/London"


def test_official_premier_opening_and_final_arsenal_fixtures_match_source() -> None:
    bundle = load_premier_league_2026_27()
    arsenal = bundle.calendar.fixtures_for_club("arsenal")

    assert len(arsenal) == 38
    assert arsenal[0].home_club_id == "arsenal"
    assert arsenal[0].away_club_id == "coventry-city"
    assert arsenal[0].match_date == date(2026, 8, 21)
    assert arsenal[-1].home_club_id == "arsenal"
    assert arsenal[-1].away_club_id == "brighton-hove-albion"
    assert arsenal[-1].match_date == date(2027, 5, 30)


def test_every_official_matchweek_has_ten_matches_and_twenty_clubs() -> None:
    bundle = load_premier_league_2026_27()

    for matchweek in range(1, 39):
        fixtures = [
            fixture
            for fixture in bundle.edition.fixtures
            if fixture.round_number == matchweek
        ]
        clubs = {
            club_id
            for fixture in fixtures
            for club_id in (fixture.home_club_id, fixture.away_club_id)
        }
        assert len(fixtures) == 10
        assert len(clubs) == 20


def test_official_premier_calendar_has_official_provenance_and_no_same_time_club_conflicts() -> None:
    bundle = load_premier_league_2026_27()

    assert all(item.source is ScheduleSource.OFFICIAL for item in bundle.calendar.fixtures)
    assert bundle.calendar.detect_conflicts() == ()


def test_official_premier_sporting_plan_is_seeded_and_valid_double_round_robin() -> None:
    bundle = load_premier_league_2026_27()
    plan = RoundRobinFixturePlan.seeded(
        fixtures=bundle.edition.fixtures,
        participant_club_ids=bundle.edition.participant_club_ids,
    )

    assert plan.source is FixturePlanSource.SEEDED
    assert len(plan.fixtures) == 380
    assert plan.template.participant_count == 20


def test_official_premier_metadata_keeps_authoritative_source_reference() -> None:
    bundle = load_premier_league_2026_27()

    assert bundle.metadata.published_date == date(2026, 6, 19)
    assert bundle.metadata.snapshot_date == date(2026, 10, 8)
    assert bundle.metadata.source_url.startswith("https://www.premierleague.com/")
    assert "380 fixtures" in bundle.metadata.source_title
