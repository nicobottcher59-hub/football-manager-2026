"""Phase 6.5a: published EFL kickoff slots + strictly fictional club pairings."""
from collections import Counter
from datetime import date, datetime, timezone
from pathlib import Path

import pytest

from football_manager.data import (
    SPECS_BY_KEY,
    build_all_development_efl_2026_27,
    build_development_efl_2026_27,
    load_efl_2026_27_slots,
    tier_strength,
)
from football_manager.dev_ui import DevelopmentSession
from football_manager.domain import (
    FixturePlanSource,
    RoundRobinFixturePlan,
    ScheduleSource,
    ScheduledFixtureStatus,
    build_league_table,
)


@pytest.fixture(scope="module")
def divisions():
    return build_all_development_efl_2026_27()


@pytest.mark.parametrize("key", ("championship", "league-one", "league-two"))
def test_slot_templates_have_all_forty_six_rounds_and_552_kickoffs(key):
    slots = load_efl_2026_27_slots(key)
    assert len(slots) == 46
    assert all(len(round_kickoffs) == 12 for round_kickoffs in slots)
    assert all(item.tzinfo is timezone.utc for rnd in slots for item in rnd)
    assert min(item.date() for rnd in slots for item in rnd) == SPECS_BY_KEY[key].first_date
    assert max(item.date() for rnd in slots for item in rnd) == SPECS_BY_KEY[key].last_date


def test_championship_published_first_and_last_matchweeks():
    slots = load_efl_2026_27_slots("championship")
    assert slots[0][0] == datetime(2026, 8, 14, 19, 0, tzinfo=timezone.utc)
    assert slots[-1] == (datetime(2027, 5, 1, 11, 30, tzinfo=timezone.utc),) * 12
    assert any(item.date() != slots[5][0].date() for item in slots[5])


@pytest.mark.parametrize("key", ("league-one", "league-two"))
def test_league_one_and_two_finish_on_eighth_may(key):
    assert load_efl_2026_27_slots(key)[-1][0].date() == date(2027, 5, 8)


def test_templates_preserve_real_world_outlier_dates_without_changing_matchweek():
    one = load_efl_2026_27_slots("league-one")
    two = load_efl_2026_27_slots("league-two")
    assert any(item.date() == date(2026, 11, 4) for item in one[2])  # Round 3 delayed match
    assert any(item.date() == date(2026, 11, 24) for item in one[7])  # Round 8 delayed match
    assert any(item.date() == date(2026, 11, 24) for item in two[7])  # Round 8 delayed match


@pytest.mark.parametrize("key", ("championship", "league-one", "league-two"))
def test_generated_sporting_fixtures_are_complete_fictional_double_round_robin(divisions, key):
    d = divisions[key]
    assert len(d.club_names) == 24
    assert len(set(d.club_names.values())) == 24
    assert len(d.edition.fixtures) == len(d.calendar.fixtures) == 552
    assert set(d.club_names) == set(d.edition.participant_club_ids)
    assert all(fixture.home_club_id.startswith("dev-") for fixture in d.edition.fixtures)
    assert all(fixture.away_club_id.startswith("dev-") for fixture in d.edition.fixtures)
    assert RoundRobinFixturePlan.seeded(
        fixtures=d.edition.fixtures, participant_club_ids=d.edition.participant_club_ids
    ).source is FixturePlanSource.SEEDED
    assert all(len([x for x in d.edition.fixtures if x.round_number == n]) == 12 for n in range(1, 47))
    assert len(d.calendar.detect_conflicts(minimum_rest_hours=24)) == 0


@pytest.mark.parametrize("key", ("championship", "league-one", "league-two"))
def test_calendar_retains_published_date_multiplicity_but_not_real_club_pairings(divisions, key):
    d = divisions[key]
    template = load_efl_2026_27_slots(key)
    for number in (1, 2, 3, 8, 9, 23, 46):
        matching = [x for x in d.calendar.fixtures if x.round_number == number]
        assert Counter(x.kickoff for x in matching) == Counter(template[number - 1])
    assert all(x.source is ScheduleSource.GENERATED for x in d.calendar.fixtures)
    assert d.fixture_source is ScheduleSource.GENERATED
    assert d.slot_source_url.startswith("https://")


def test_fictional_quality_ranges_are_separated_and_show_variation():
    for tier in range(1, 5):
        qualities = [tier_strength(tier, index) for index in range(24)]
        assert len(set(qualities)) >= 4
        if tier < 4:
            assert min(qualities) > max(tier_strength(tier + 1, i) for i in range(24))
    assert min(tier_strength(1, index) for index in range(24)) > 70
    with pytest.raises(ValueError):
        tier_strength(5, 0)
    with pytest.raises(ValueError):
        tier_strength(1, -1)


def test_regenerating_the_same_division_is_deterministic(divisions):
    first = divisions["championship"]
    again = build_development_efl_2026_27("championship")
    assert first.edition.fixtures == again.edition.fixtures
    assert first.calendar.fixtures == again.calendar.fixtures
    assert dict(first.strengths) == dict(again.strengths)


def test_unknown_division_is_rejected():
    with pytest.raises(ValueError, match="unknown EFL division"):
        load_efl_2026_27_slots("unknown")
    with pytest.raises(ValueError, match="unknown EFL division"):
        build_development_efl_2026_27("unknown")


def test_slot_loader_fails_closed_on_incomplete_or_duplicate_source(tmp_path, monkeypatch):
    import football_manager.data.efl_2026_27 as efl

    original = Path("/unused")
    monkeypatch.setattr(efl, "files", lambda _: tmp_path)
    target = tmp_path / "official" / "england" / "efl_slots"
    target.mkdir(parents=True)
    slots = target / "championship_2026_27.slots"
    slots.write_text("01 0814-1900x12\n")
    with pytest.raises(ValueError, match="rounds 1..46"):
        efl.load_efl_2026_27_slots("championship")
    slots.write_text("01 0814-1900x13\n")
    with pytest.raises(ValueError, match="multiplicity"):
        efl.load_efl_2026_27_slots("championship")
    slots.write_text("01 0814-1900x12\n01 0814-1900x12\n")
    with pytest.raises(ValueError, match="repeats round"):
        efl.load_efl_2026_27_slots("championship")


def test_sandbox_exposes_three_efl_divisions_without_disturbing_managed_premier():
    session = DevelopmentSession()
    assert len(session.efl_division_options) == 3
    assert len(session.official_calendar_rows) == 380
    assert len(session.calendar_rows) >= 38
    assert len(session.efl_calendar_rows("championship")) == 552
    assert len(session.efl_table_rows("league-two")) == 24
    assert "GENERATED" in session.efl_calendar_summary("league-one")
    names = [name for name, _, _ in session.competition_rows]
    assert any("Championship" in name for name in names)
    assert any("League One" in name for name in names)
    assert any("League Two" in name for name in names)


def test_sandbox_can_simulate_a_division_round_and_updates_table_and_calendar():
    session = DevelopmentSession()
    before_date = session.current_date
    # The Runner may already have played EFL fixtures dated before the initial
    # managed Premier kickoff, so the first inspected round is not always 1.
    starting = session.efl_current_round("championship")
    other_start = session.efl_current_round("league-one")
    assert session.simulate_next_efl_round("championship") == starting
    assert session.efl_current_round("championship") > starting
    rows = session.efl_table_rows("championship")
    assert sum(x.played for x in rows) >= 24
    assert sum(x.won for x in rows) == sum(x.lost for x in rows)
    assert all("Played" in item.status for item in session.efl_fixture_rows("championship", starting))
    assert session.current_date == before_date
    assert session.efl_current_round("league-one") == other_start
    with pytest.raises(ValueError, match="round_number"):
        session.efl_fixture_rows("championship", 47)


def test_sandbox_efl_inspector_can_complete_all_46_rounds_without_duplicates():
    session = DevelopmentSession()
    start = session.efl_current_round("league-two")
    for number in range(start, 47):
        assert session.simulate_next_efl_round("league-two") == number
    assert session.efl_current_round("league-two") == 47
    assert sum(item.played for item in session.efl_table_rows("league-two")) == 1104
    assert len(session._efl_results["league-two"]) == 552
    assert all(
        item.status is ScheduledFixtureStatus.PLAYED
        for item in session._efl_divisions["league-two"].calendar.fixtures
    )
    with pytest.raises(RuntimeError, match="already complete"):
        session.simulate_next_efl_round("league-two")
    session.reset()
    assert session.efl_current_round("league-two") == start
    assert len(session._efl_results["league-two"]) < 552
