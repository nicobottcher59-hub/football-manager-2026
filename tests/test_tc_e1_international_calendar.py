"""TC-E1: stable FIFA windows, release-only tournaments, world integration."""
from __future__ import annotations

from dataclasses import replace
from datetime import date, datetime, time, timezone
import json

import pytest

from football_manager.data.future_seasons import round_dates
from football_manager.domain.calendar import (ScheduleSource, SchedulingWindow)
from football_manager.domain.international_calendar import (
    InternationalCallUp, InternationalCalendar, InternationalDateSource,
    InternationalDutyRegistry, InternationalImpact, build_international_calendar,
)
from football_manager.domain.world_runner import WorldSeasonRunner
from tools.stress_world_calendar import add_cup_proxy, add_staged, create_world, measure


def test_fifa_2026_through_2030_official_dates_and_combined_sep_oct() -> None:
    expected = {
        2026: ((9, 21), (10, 6)),
        2027: ((9, 20), (10, 5)),
        2028: ((9, 18), (10, 3)),
        2029: ((9, 24), (10, 9)),
        2030: ((9, 23), (10, 8)),
    }
    master = build_international_calendar(2026, 2030)
    for year, (start, end) in expected.items():
        item = master.event(f"fifa-sep-oct-{year}")
        assert item.start_date == date(year, *start)
        assert item.end_date == date(year, *end)
        assert item.source is InternationalDateSource.OFFICIAL
        assert item.impact is InternationalImpact.CLUB_BREAK
        assert (item.end_date - item.start_date).days == 15
        assert master.stops_club_football(item.start_date)
    assert not master.stops_club_football(date(2027, 10, 6))


def test_projected_fifa_windows_repeat_weeks_after_2030() -> None:
    master = build_international_calendar(2031, 2050)
    for year in range(2031, 2051):
        events = [e for e in master.events if e.event_id.startswith("fifa-")
                  and e.event_id.endswith(f"-{year}")]
        assert len(events) == 4
        assert all(e.source is InternationalDateSource.PROJECTED for e in events)
        assert all(e.start_date.weekday() == 0 for e in events)
        assert [((e.end_date - e.start_date).days + 1) for e in events] == [9, 9, 16, 9]


def test_major_tournament_cycles_and_release_only_semantics() -> None:
    master = build_international_calendar(2026, 2040)
    assert [y for y in range(2026, 2041) if f"world-cup-{y}" in
            {e.event_id for e in master.events}] == [2026, 2030, 2034, 2038]
    assert [y for y in range(2026, 2041) if f"euro-{y}" in
            {e.event_id for e in master.events}] == [2028, 2032, 2036, 2040]
    assert [y for y in range(2026, 2041) if f"asian-cup-{y}" in
            {e.event_id for e in master.events}] == [2027, 2031, 2035, 2039]
    assert [y for y in range(2026, 2041) if f"afcon-{y}" in
            {e.event_id for e in master.events}] == [2027, 2028, 2032, 2036, 2040]
    asian = master.event("asian-cup-2027")
    assert (asian.start_date, asian.end_date) == (date(2027, 1, 7), date(2027, 2, 5))
    assert asian.source is InternationalDateSource.OFFICIAL
    assert not master.stops_club_football(date(2027, 1, 15))
    assert master.event("afcon-2027").start_date == date(2027, 6, 19)
    assert master.event("euro-2028").end_date == date(2028, 7, 9)
    assert master.event("copa-america-2028").source is InternationalDateSource.PROJECTED
    assert master.event("afcon-2028").source is InternationalDateSource.PROJECTED
    assert master.event("world-cup-2026").duty_start == date(2026, 5, 25)
    assert not master.stops_club_football(date(2026, 6, 30))


def test_overrides_do_not_alter_unrelated_windows_and_are_serializable() -> None:
    event_id = "afcon-2032"
    calendar = build_international_calendar(
        2032, 2032,
        overrides={event_id: (date(2032, 1, 10), date(2032, 2, 12))},
    )
    event = calendar.event(event_id)
    assert event.source is InternationalDateSource.OVERRIDE
    assert event.start_date == date(2032, 1, 10)
    assert event.impact is InternationalImpact.RELEASE_ONLY
    assert InternationalCalendar.from_dict(json.loads(json.dumps(calendar.to_dict()))) == calendar
    with pytest.raises(ValueError, match="unknown override"):
        build_international_calendar(2032, 2032, overrides={"missing": (date(2032, 1, 1), date(2032, 1, 2))})
    with pytest.raises(ValueError, match="end cannot precede"):
        build_international_calendar(2032, 2032, overrides={event_id: (date(2032, 2, 2), date(2032, 1, 1))})


def test_explicit_callups_remove_only_selected_players_and_allow_early_return() -> None:
    master = build_international_calendar(2027, 2027)
    item = InternationalCallUp(
        "player-a", "national-team-a", "asian-cup-2027",
        date(2027, 1, 7), date(2027, 1, 21),
    )
    registry = InternationalDutyRegistry(master, (item,))
    assert not registry.unavailable("player-a", date(2027, 1, 6))
    assert registry.unavailable("player-a", date(2027, 1, 15))
    assert not registry.unavailable("player-b", date(2027, 1, 15))
    assert not registry.unavailable("player-a", date(2027, 1, 22))
    assert len(registry.active(date(2027, 1, 15))) == 1
    assert not master.stops_club_football(date(2027, 1, 15))
    with pytest.raises(ValueError, match="overlapping"):
        InternationalDutyRegistry(master, (item, item))
    with pytest.raises(ValueError, match="fit event"):
        InternationalDutyRegistry(master, (replace(item, last_unavailable_day=date(2027, 2, 6)),))
    assert InternationalDutyRegistry(master).active(date(2027, 1, 15)) == ()


@pytest.mark.parametrize("year", [2027, 2028, 2029, 2030, 2031, 2035])
def test_future_english_league_rounds_avoid_only_fifa_breaks(year: int) -> None:
    master = build_international_calendar(year, year + 1)
    for round_count in (38, 46):
        dates = round_dates(year, round_count)
        assert len(dates) == len(set(dates)) == round_count
        assert all(not master.stops_club_football(day) for day in dates)
        assert all(date(year, 8, 1) <= day <= date(year + 1, 5, 31) for day in dates)


def test_world_runner_checks_new_generated_league_kickoffs() -> None:
    world, _ = create_world(leagues=1, seed=6060, year=2027, master_calendar=True)
    first = next(iter(world.fixtures))
    original = world.fixtures[first]
    assert original.kickoff is not None
    assert not world.international_window_violations()
    # A fixture illegally moved by external code is visible to audits.
    forbidden = datetime(2027, 9, 22, 15, tzinfo=timezone.utc)
    world.fixtures[first] = replace(original, kickoff=forbidden)
    assert first in world.international_window_violations()
    # Registration also rejects a generated league fixture inside a FIFA break.
    new_world, _ = create_world(leagues=1, seed=6060, year=2027, master_calendar=True)
    edition = next(iter(new_world.leagues.values()))
    scheduled = new_world.calendar
    fresh = WorldSeasonRunner(season_label="2027/28", international_calendar=new_world.international_calendar)
    from football_manager.domain.calendar import SeasonCalendar
    revised = SeasonCalendar(scheduled.season_label, scheduled.timezone_name, tuple(
        replace(f, kickoff=forbidden) if f.fixture_id == first else f for f in scheduled.fixtures
    ))
    with pytest.raises(ValueError, match="international club break"):
        fresh.register_league(edition, revised, new_world.strengths)


def test_world_runner_cups_uefa_and_reprogramming_respect_master() -> None:
    world, _ = create_world(leagues=4, seed=6060, year=2027, master_calendar=True)
    add_staged(world, seed=6060, count=1, year=2027)
    add_cup_proxy(world, seed=6060, year=2027)
    assert not world.international_window_violations()
    assert not world.calendar.detect_conflicts(minimum_rest_hours=48)
    fixture = next(f for f in world.fixtures.values() if f.competition_id in world.leagues)
    original = fixture.kickoff
    assert original is not None
    # Demand a kickoff exclusively inside a FIFA break; state must not mutate.
    window = SchedulingWindow("fifa-only", date(2027, 9, 20), date(2027, 10, 5))
    with pytest.raises(ValueError, match="no available kickoff"):
        world.reschedule_league_fixture(fixture.fixture_id, window)
    assert world.fixtures[fixture.fixture_id].kickoff == original
    restored = WorldSeasonRunner.from_dict(world.to_dict())
    assert restored.international_calendar == world.international_calendar
    assert not restored.international_window_violations()


def test_multi_country_stress_with_master_calendar_has_no_window_violations() -> None:
    summary = measure(
        leagues=4, seed=6060, year=2027, master_calendar=True,
        staged_competitions=1, cup_proxy=True, postponements=2, simulate=True,
    )
    assert summary.status == "pass", summary.error
    assert summary.final_fixtures == summary.results
    assert summary.blackout_league_violations == 0
    assert summary.blackout_staged_violations == 0
    assert summary.blackout_cup_proxy_violations == 0
    assert summary.blackout_postponement_violations == 0
    assert summary.conflicts_48h == 0


def test_future_calendar_is_generated_normally_then_reprogrammed_with_provenance() -> None:
    from football_manager.data.future_seasons import normal_round_dates, generated_edition
    from football_manager.dev_ui.session import DevelopmentSession

    for count in (38, 46):
        original = normal_round_dates(2027, count)
        final = round_dates(2027, count)
        assert len(original) == len(final) == count
        changed = [n for n in range(1, count + 1) if original[n - 1] != final[n - 1]]
        assert changed, "FIFA overlay should actually move some of the natural matchweeks"
        assert len(changed) < count // 2, "unaffected natural rounds should stay where they were"
        assert all((final[i] - final[i - 1]).days >= 3 for i in range(1, count))
        previous = DevelopmentSession()._world.leagues[
            "dev-premier" if count == 38 else "dev-championship"
        ]
        edition, calendar = generated_edition(previous, previous.participant_club_ids, 2027)
        by_round = {}
        for fixture in calendar.fixtures:
            by_round.setdefault(fixture.round_number, []).append(fixture)
            if count == 46:  # EFL preserves its existing round-date policy.
                assert fixture.kickoff.date() == final[fixture.round_number - 1]
                if fixture.round_number in changed:
                    assert fixture.is_rescheduled
                    assert fixture.original_kickoff.date() == original[fixture.round_number - 1]
                else:
                    assert fixture.original_kickoff is None
        if count == 38:
            # The Premier now uses all TEN distinct published matchweek slots,
            # not the former one-Saturday-per-round policy.
            from football_manager.data.premier_calendar import premier_reference_slots
            template = premier_reference_slots(2027)
            for number, group in by_round.items():
                assert sorted(f.kickoff for f in group) == list(template[number])
            assert any(f.kickoff.weekday() == 4 for f in calendar.fixtures)
            assert any(f.kickoff.weekday() == 6 for f in calendar.fixtures)
        assert len(by_round) == count
        assert len(edition.fixtures) == len(calendar.fixtures)


def test_world_calendar_markers_are_small_read_only_metadata() -> None:
    from football_manager.dev_ui.session import DevelopmentSession
    from football_manager.ui_shell.calendar import calendar_read_model
    from pathlib import Path

    model = calendar_read_model(DevelopmentSession())
    assert len(model["fifa_windows"]) == 4
    assert all(w["id"].startswith("fifa-") for w in model["fifa_windows"])
    assert {"matches", "date", "season"}.issubset(model)
    # Marker is an indicator, not a fixture tile or a fake competition result.
    script = (Path(__file__).resolve().parents[1] / "frontend/portable/calendar.js").read_text(encoding="utf-8")
    assert 'class="cal-fifa-mark"' in script
    assert "games.map(fixture).join" in script
    assert "snapshot?.fifa_windows" in script


def test_postgeneration_reflow_reports_impossible_window_without_mutating_source() -> None:
    from football_manager.domain.calendar import (
        CalendarBlock, LeagueSchedulingPolicy, reprogram_round_dates_for_blackouts,
    )

    base = {n: datetime(2027, 9, n + 9, 15, tzinfo=timezone.utc)
            for n in range(1, 4)}
    policy = LeagueSchedulingPolicy(
        season_start=date(2027, 9, 10), season_end=date(2027, 9, 13),
        blackout_periods=(CalendarBlock(date(2027, 9, 10), date(2027, 9, 13)),),
    )
    with pytest.raises(ValueError, match="cannot fit all competition rounds"):
        reprogram_round_dates_for_blackouts(base, policy)
    assert tuple(base) == (1, 2, 3)
    assert base[1].date() == date(2027, 9, 10)
