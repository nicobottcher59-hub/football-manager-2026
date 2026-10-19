"""TS-01: world operations fail as a unit, including mutable tournament history."""
from __future__ import annotations

from dataclasses import replace
from datetime import date

import pytest

from football_manager.data.staged_2026_27 import build_uefa_2026_27
from football_manager.domain.domestic_cups import DomesticCupRound, DomesticCupSeason
from football_manager.domain.world_runner import WorldSeasonRunner


def _cup(cup_id: str = "atomic-test-cup", entrants: tuple[str, ...] = ("a", "b", "c", "d")) -> DomesticCupSeason:
    return DomesticCupSeason(
        cup_id=cup_id, name="Atomic cup", season_label="2026/27", draw_seed=8021,
        rounds=(
            DomesticCupRound("semi", "Semifinals", (date(2026, 9, 10),), entrants=entrants),
            DomesticCupRound("final", "Final", (date(2026, 10, 10),)),
        ),
    )


def _cause_failure_after_scheduling(monkeypatch, world: WorldSeasonRunner, method_name: str) -> None:
    actual = getattr(world, method_name)

    def fail_after(*args, **kwargs):
        actual(*args, **kwargs)
        raise RuntimeError("injected failure after scheduling")

    monkeypatch.setattr(world, method_name, fail_after)


def test_cup_registration_restores_tournament_strengths_and_fixtures_after_partial_insert(monkeypatch) -> None:
    world = WorldSeasonRunner()
    world.strengths["a"] = 32
    cup = _cup()
    plans_ref = cup.plans
    snapshot = world.to_dict()
    actual = world._insert_cup_match
    count = 0

    def fail_second(**kwargs):
        nonlocal count
        count += 1
        if count == 2:
            raise RuntimeError("injected second fixture failure")
        return actual(**kwargs)

    monkeypatch.setattr(world, "_insert_cup_match", fail_second)
    with pytest.raises(RuntimeError, match="second fixture"):
        world.register_cup(cup, strengths={"a": 90, "b": 70, "c": 70, "d": 70})
    assert count == 2
    assert world.to_dict() == snapshot
    assert cup.plans is plans_ref
    assert cup.plans == []
    assert cup.champion_club_id is None
    assert world._cup_fixture_ids == {}
    assert world._active_journal is None

    monkeypatch.undo()
    world.register_cup(cup, strengths={"a": 90, "b": 70, "c": 70, "d": 70})
    assert len(world.fixtures) == 2
    assert world.cups[cup.cup_id] is cup
    assert len(cup.plans) == 1


def test_staged_registration_restores_all_entries_when_later_window_is_invalid() -> None:
    clubs = tuple(f"uefa-{i:02}" for i in range(36))
    stage = build_uefa_2026_27("champions-league", clubs, seed=8021)
    # Schedule at least one fixture successfully before hitting an impossible window.
    stage = replace(stage, primary_dates=(stage.primary_dates[0], date(2027, 7, 10), *stage.primary_dates[2:]))
    world = WorldSeasonRunner()
    snapshot = world.to_dict()
    with pytest.raises(ValueError, match="no free staged fixture window"):
        world.register_staged(stage, strengths={club: 75 for club in clubs})
    assert world.to_dict() == snapshot
    assert stage.knockout_plans == []
    assert world._staged_fixture_ids == {}
    assert world._active_journal is None


def test_cup_result_rolls_back_generated_round_and_retry_is_deterministic(monkeypatch) -> None:
    world = WorldSeasonRunner()
    cup = _cup()
    world.register_cup(cup, strengths={club: 65 for club in ("a", "b", "c", "d")})
    opening = [fixture.fixture_id for fixture in cup.plans[0].fixtures]
    assert len(opening) == 2
    world.record_result(opening[0], 1, 0)
    snapshot = world.to_dict()
    plans_ref = cup.plans
    first_plan = cup.current_plan
    _cause_failure_after_scheduling(monkeypatch, world, "_schedule_cup_plan")

    with pytest.raises(RuntimeError, match="after scheduling"):
        world.record_result(opening[1], 2, 1)
    assert world.to_dict() == snapshot
    assert cup.plans is plans_ref and cup.current_plan is first_plan
    assert len(cup.plans) == 1
    assert world._active_journal is None

    monkeypatch.undo()
    expected = WorldSeasonRunner.from_dict(snapshot)
    assert world.record_result(opening[1], 2, 1) == expected.record_result(opening[1], 2, 1)
    assert world.to_dict() == expected.to_dict()


def test_staged_result_restores_qualifiers_draw_and_new_fixtures(monkeypatch) -> None:
    clubs = tuple(f"uefa-{i:02}" for i in range(36))
    stage = build_uefa_2026_27("europa-league", clubs, seed=8021)
    world = WorldSeasonRunner()
    world.register_staged(stage, strengths={club: 77 for club in clubs})
    last = stage.primary_fixtures[-1].fixture_id
    for fixture in stage.primary_fixtures[:-1]:
        world.record_result(fixture.fixture_id, 2, 1)
    assert stage.knockout_plans == []
    snapshot = world.to_dict()
    plans_ref = stage.knockout_plans
    _cause_failure_after_scheduling(monkeypatch, world, "_schedule_staged_plan")

    with pytest.raises(RuntimeError, match="after scheduling"):
        world.record_result(last, 2, 1)
    assert world.to_dict() == snapshot
    assert stage.knockout_plans is plans_ref and stage.knockout_plans == []
    assert stage.direct_qualifiers == ()
    assert world._active_journal is None

    monkeypatch.undo()
    expected = WorldSeasonRunner.from_dict(snapshot)
    assert world.record_result(last, 2, 1) == expected.record_result(last, 2, 1)
    assert world.to_dict() == expected.to_dict()


def test_champion_assignment_undoes_if_cup_processing_raises(monkeypatch) -> None:
    cup = DomesticCupSeason(
        "single-final", "Final", "2026/27",
        (DomesticCupRound("final", "Final", (date(2027, 5, 22),), entrants=("a", "b")),),
    )
    world = WorldSeasonRunner()
    world.register_cup(cup, strengths={"a": 80, "b": 80})
    fixture = cup.plans[0].fixtures[0]
    snapshot = world.to_dict()
    actual = DomesticCupSeason.after_results

    def fail_after_champion(self, results):
        outcome = actual(self, results)
        assert self.champion_club_id in ("a", "b")
        raise RuntimeError("injected champion processing failure")

    monkeypatch.setattr(DomesticCupSeason, "after_results", fail_after_champion)
    with pytest.raises(RuntimeError, match="champion processing"):
        world.record_result(fixture.fixture_id, 2, 0)
    assert world.to_dict() == snapshot
    assert cup.champion_club_id is None
    assert world._active_journal is None


def test_invalid_playoff_configuration_does_not_register_partial_entries() -> None:
    world = WorldSeasonRunner()
    world.leagues["dev-championship"] = object()  # Configuration validates only IDs.
    with pytest.raises(ValueError, match="unknown EFL playoff league"):
        world.configure_promotion_playoffs(("dev-championship", "nonexistent-efl-league"))
    assert world.promotion_playoff_leagues == {}
    assert world._active_journal is None


def test_nested_atomic_command_rolls_back_inner_success_when_outer_fails() -> None:
    world = WorldSeasonRunner()
    cup = _cup()
    original = world.to_dict()
    with pytest.raises(RuntimeError, match="outer failure"):
        with world._atomic():
            world.register_cup(cup, strengths={club: 72 for club in ("a", "b", "c", "d")})
            assert cup.cup_id in world.cups
            raise RuntimeError("outer failure")
    assert world.to_dict() == original
    assert cup.plans == []
    assert world._active_journal is None


def test_partial_staged_registration_restores_league_fixture_that_was_moved(monkeypatch) -> None:
    from datetime import datetime, time, timezone

    from football_manager.domain.calendar import ScheduleSource, ScheduledFixture

    clubs = tuple(f"foreign-{i:02}" for i in range(36))
    stage = build_uefa_2026_27("champions-league", clubs, seed=991)
    opening = stage.primary_fixtures[0]
    window = stage.primary_dates[0]
    world = WorldSeasonRunner()
    world.leagues["test-league"] = object()  # Only fixture ownership is relevant.
    existing = ScheduledFixture(
        "league-to-restore", "test-league", "test-league-2026-27", "league",
        opening.home_club_id, "extra-team",
        datetime.combine(window, time(15), tzinfo=timezone.utc), ScheduleSource.GENERATED,
    )
    world.fixtures[existing.fixture_id] = existing
    original_conflicts = world._matching_conflicts
    original_insert = world._schedule_staged_fixture
    original_replacement = world._find_league_replacement
    replacements = []
    scheduled_count = 0

    def force_priority_conflict(kickoff, home, away):
        if (home, away) == (opening.home_club_id, opening.away_club_id):
            return [existing]
        return original_conflicts(kickoff, home, away)

    def log_replacement(item, anchor):
        moved = original_replacement(item, anchor)
        replacements.append(moved)
        return moved

    def fail_on_second(competition, fixture, day):
        nonlocal scheduled_count
        scheduled_count += 1
        if scheduled_count == 2:
            raise RuntimeError("injected later staged failure")
        return original_insert(competition, fixture, day)

    monkeypatch.setattr(world, "_matching_conflicts", force_priority_conflict)
    monkeypatch.setattr(world, "_find_league_replacement", log_replacement)
    monkeypatch.setattr(world, "_schedule_staged_fixture", fail_on_second)
    with pytest.raises(RuntimeError, match="later staged failure"):
        world.register_staged(stage, strengths={club: 70 for club in clubs})
    assert scheduled_count == 2
    assert replacements, "setup must have actually moved a league fixture"
    assert world.fixtures == {existing.fixture_id: existing}
    assert world.strengths == {}
    assert world.staged == {}
    assert world._staged_fixture_ids == {}
    assert world._active_journal is None
