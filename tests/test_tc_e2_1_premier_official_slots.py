"""TC-E2.1: Published Premier date slots remain the baseline, results stay live."""
from __future__ import annotations

from collections import Counter, defaultdict
from datetime import date, timezone

from football_manager.data.official_schedule import load_premier_league_2026_27
from football_manager.data.premier_calendar import (
    build_premier_calendar, premier_reference_slots,
)
from football_manager.data.future_seasons import generated_edition
from football_manager.dev_ui.session import DevelopmentSession
from football_manager.domain.calendar import ScheduleSource, ScheduledFixtureStatus
from football_manager.domain.international_calendar import build_international_calendar
from football_manager.ui_shell.calendar import calendar_read_model
from football_manager.ui_shell.progression import progression_read_model


def _premier(session):
    return [f for f in session._world.fixtures.values() if f.competition_id == "dev-premier"]


def test_first_season_uses_all_380_real_time_slots_without_real_clubs() -> None:
    game = DevelopmentSession()
    source = load_premier_league_2026_27()
    template = premier_reference_slots(2026)
    fixtures = _premier(game)
    assert len(fixtures) == 380
    assert sum(len(group) for group in template.values()) == 380
    assert {f.home_club_id for f in fixtures}.isdisjoint(source.club_names)
    assert {f.away_club_id for f in fixtures}.isdisjoint(source.club_names)
    assert all(f.source == ScheduleSource.GENERATED for f in fixtures)
    raw_dates = Counter(f.kickoff.astimezone(timezone.utc) for f in source.calendar.fixtures)
    baseline_dates = Counter(f.original_kickoff or f.kickoff for f in fixtures)
    assert raw_dates == baseline_dates
    assert {f.kickoff.weekday() for f in fixtures}.issuperset({0, 1, 2, 3, 4, 5, 6})
    assert not game._world.international_window_violations()
    assert not game._world.calendar.detect_conflicts(minimum_rest_hours=48)


def test_matchday_is_bound_to_canonical_first_friday_instead_of_old_saturday() -> None:
    game = DevelopmentSession()
    assert game.current_date == date(2026, 8, 21)
    assert game._active_match.match_date == game.current_date
    state = progression_read_model(game)
    assert state["match_day"] and state["button_label"] == "Go to Match"
    assert state["pending_match"]["date"] == "2026-08-21"
    assert calendar_read_model(game)["date"] == "2026-08-21"
    canonical = game._world.fixtures[game._active_match.fixture.fixture_id]
    clock = canonical.kickoff.astimezone(timezone.utc).strftime("%H:%M UTC")
    assert f" | {clock} | " in game.next_match_meta
    assert "15:00 | " not in game.next_match_meta


def test_future_year_reuses_published_weekday_and_time_slot_pattern() -> None:
    game = DevelopmentSession()
    previous = game._world.leagues["dev-premier"]
    projected = premier_reference_slots(2027)
    edition, calendar = generated_edition(previous, previous.participant_club_ids, 2027)
    assert edition.edition_id != previous.edition_id
    assert Counter(f.kickoff for f in calendar.fixtures) == Counter(
        kickoff for group in projected.values() for kickoff in group
    )
    assert all(f.original_kickoff is None for f in calendar.fixtures)
    assert all(f.source == ScheduleSource.GENERATED for f in calendar.fixtures)
    assert not calendar.detect_conflicts(minimum_rest_hours=48)


def test_fifa_overlay_moves_only_blocked_slots_and_records_the_original() -> None:
    game = DevelopmentSession()
    previous = game._world.leagues["dev-premier"]
    year = 2028
    edition, calendar = generated_edition(previous, previous.participant_club_ids, year)
    baseline = premier_reference_slots(year)
    master = build_international_calendar(year, year + 1)
    by_round = defaultdict(list)
    for f in calendar.fixtures:
        by_round[f.round_number].append(f)
        assert not master.stops_club_football(f.kickoff.date())
    for round_number, group in by_round.items():
        assert sorted(f.original_kickoff or f.kickoff for f in group) == list(baseline[round_number])
    shifted = [f for f in calendar.fixtures if f.is_rescheduled]
    assert shifted
    assert all(master.stops_club_football(f.original_kickoff.date()) for f in shifted)
    assert not calendar.detect_conflicts(minimum_rest_hours=48)


def test_winner_driven_cup_rounds_adjust_future_premier_dates_not_finished_matches() -> None:
    game = DevelopmentSession()
    initial = {f.fixture_id: f.kickoff for f in _premier(game)}
    already_played = {f.fixture_id: f.kickoff for f in _premier(game)
                      if f.status == ScheduledFixtureStatus.PLAYED}
    game.simulate_remaining_season()
    world = game._world
    after = {f.fixture_id: f for f in _premier(game)}
    changed = [f for fid, f in after.items() if f.kickoff != initial[fid]]
    assert changed, "a later cup/UEFA progression should cause at least one postponement"
    assert all(f.original_kickoff == initial[f.fixture_id] for f in changed)
    assert all(after[fid].kickoff == kickoff for fid, kickoff in already_played.items())
    assert all(f.status == ScheduledFixtureStatus.PLAYED for f in after.values())
    assert set(world.fixtures) == set(world.results)
    assert len(world.fixtures) == 2959
    assert not world.international_window_violations()
    assert not world.calendar.detect_conflicts(minimum_rest_hours=48)
