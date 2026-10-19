"""Phase 6.5b + 6.6: two English cups and a single, persistent world ledger."""
from __future__ import annotations

from datetime import date
import json

import pytest

from football_manager.data.english_cups_2026_27 import (
    FA_EARLY_QUALIFYING_DATES,
    build_carabao_cup_2026_27,
    build_fa_cup_2026_27,
)
from football_manager.dev_ui import DevelopmentSession
from football_manager.domain.calendar import ScheduledFixtureStatus, ScheduleSource
from football_manager.domain.knockout import KnockoutLegFormat
from football_manager.domain.world_runner import WorldMatchResult, WorldSeasonRunner


def _tier_entrants():
    return {tier: tuple(f"tier-{tier}-{n:02}" for n in range(count))
            for tier, count in ((1, 20), (2, 24), (3, 24), (4, 24))}


def test_fa_cup_staged_entry_includes_both_professional_tiers_and_non_league():
    tiers = _tier_entrants()
    cup = build_fa_cup_2026_27(tiers)
    assert [r.round_id for r in cup.rounds] == [
        "qualifying-4", "proper-1", "proper-2", "proper-3", "proper-4",
        "proper-5", "quarterfinal", "semifinal", "final",
    ]
    assert len(cup.rounds[0].entrants) == 64
    assert len(cup.rounds[1].entrants) == 48
    assert set(cup.rounds[1].entrants) == set(tiers[3]) | set(tiers[4])
    assert set(cup.rounds[3].entrants) == set(tiers[1]) | set(tiers[2])
    assert len(FA_EARLY_QUALIFYING_DATES) == 5  # recorded windows, simulated from Q4
    assert cup.rounds[-1].dates == (date(2027, 5, 22),)


def test_carabao_2026_27_entries_rounds_and_two_legged_semifinal():
    tiers = _tier_entrants()
    nine = tiers[1][:9]
    cup = build_carabao_cup_2026_27(tiers, european_entrant_ids=nine)
    assert len(cup.rounds) == 8
    assert [len(r.entrants) for r in cup.rounds] == [4, 68, 11, 9, 0, 0, 0, 0]
    assert set(cup.rounds[3].entrants) == set(nine)
    assert cup.rounds[-2].leg_format is KnockoutLegFormat.TWO_LEGGED
    assert cup.rounds[-1].dates == (date(2027, 3, 21),)
    assert len(set(e for rule in cup.rounds for e in rule.entrants)) == 92


@pytest.mark.parametrize("count", [8, 10, 0])
def test_carabao_rejects_wrong_european_entry_count(count):
    with pytest.raises(ValueError, match="nine"):
        build_carabao_cup_2026_27(_tier_entrants(), european_entrant_ids=_tier_entrants()[1][:count])


def test_england_world_registers_four_leagues_and_both_cups():
    s = DevelopmentSession()
    world = s._world
    assert len(world.leagues) == 4
    assert set(world.cups) == {"fa-cup", "carabao-cup"}
    assert sorted(len(edition.fixtures) for edition in world.leagues.values()) == [380, 552, 552, 552]
    assert world.fixtures
    assert all(item.source is ScheduleSource.GENERATED for item in world.fixtures.values())
    assert "generated" in s.world_cup_summary("fa-cup").lower()
    assert len(s.world_cup_bracket_rows("fa-cup")) == 32
    assert len(s.world_cup_bracket_rows("carabao-cup")) >= 39


def test_world_club_strengths_are_tier_aware():
    s = DevelopmentSession()
    mean = []
    for competition_id, edition in s._world.leagues.items():
        strengths = [s._world.strengths[x] for x in edition.participant_club_ids]
        mean.append((sum(strengths) / len(strengths), competition_id))
    vals = sorted(mean, reverse=True)
    assert "premier" in vals[0][1]
    assert "championship" in vals[1][1]
    assert "league-one" in vals[2][1]
    assert "league-two" in vals[3][1]


def test_world_never_simulates_protected_club_before_managed_match():
    s = DevelopmentSession()
    fixture_id = s._active_match.fixture.fixture_id
    assert fixture_id not in s._world.results
    progress = s._world.advance_until(date(2027, 6, 1), protected_club_id=s.home_club.id)
    assert progress.stopped_for_managed_fixture_id == fixture_id
    assert fixture_id not in s._world.results


def test_runner_results_are_canonical_for_premier_and_efl():
    s = DevelopmentSession()
    first = s._active_match.fixture.fixture_id
    result = s.quick_simulate()
    assert s._world.results[first].resolver == "managed"
    assert s._world.results[first].home_goals == result.home_goals
    assert s._world.fixtures[first].status is ScheduledFixtureStatus.PLAYED
    with pytest.raises(ValueError, match="twice"):
        s._world.simulate_fixture(first)
    s.continue_to_next_match()
    assert len(s._world.results) > 70
    assert len(s._league_results) == len(s._world.league_results(s._league_edition.competition_id))


def test_managed_calendar_contains_both_cups_not_legacy_dev_cup():
    s = DevelopmentSession()
    names = {x[0] for x in s.competition_rows}
    assert {"FA Cup", "Carabao Cup", "Development Cup"} <= names
    assert all(row.competition != "Development Cup" for row in s.calendar_rows)
    while s.current_date < date(2027, 1, 9):
        s.quick_simulate()
        s.continue_to_next_match()
    competitions = {row.competition for row in s.calendar_rows}
    assert "FA Cup" in competitions
    assert "Carabao Cup" in competitions
    assert any(row.competition == "FA Cup" and any(
        status in row.status for status in ("Played", "Scheduled", "Next match"))
        for row in s.calendar_rows)


def test_world_single_simulation_determinism():
    one, two = DevelopmentSession()._world, DevelopmentSession()._world
    fixture_id = next(fid for fid in one.fixtures if fid not in one.results)
    a, b = one.simulate_fixture(fixture_id), two.simulate_fixture(fixture_id)
    assert a == b


def test_all_2026_27_world_competitions_finish_without_duplicates_or_conflicts():
    world = DevelopmentSession()._world
    progress = world.advance_until(date(2027, 6, 15))
    assert progress.stopped_for_managed_fixture_id is None
    assert len(world.fixtures) == 2959  # 2942 baseline + 17 generated EFL promotion playoff matches
    assert len(world.results) == 2959
    assert len({record.fixture_id for record in world.results.values()}) == 2959
    assert not world.calendar.detect_conflicts(minimum_rest_hours=48)
    assert sum(len(world.league_results(key)) for key in world.leagues) == 2036
    for cup in world.cups.values():
        assert cup.champion_club_id in world.strengths
        assert cup.champion_club_id
        assert len(cup.plans) == len(cup.rounds)
    for staged in world.staged.values():
        assert staged.champion_club_id in staged.participants
        assert len(staged.knockout_plans) == 5


def test_world_save_reload_midseason_keeps_draw_history_and_results(tmp_path):
    s = DevelopmentSession()
    for _ in range(5):
        s.quick_simulate()
        s.continue_to_next_match()
    path = tmp_path / "saves" / "world.json"
    s.save_world(path)
    assert path.is_file()
    restored = WorldSeasonRunner.load_json(path)
    assert restored.to_dict() == s._world.to_dict()
    assert [plan.ties for plan in restored.cups["carabao-cup"].plans] == [
        plan.ties for plan in s._world.cups["carabao-cup"].plans
    ]
    # Loaded world can deterministically continue from the same unplayed schedule.
    target = next(fid for fid in s._world.fixtures if fid not in s._world.results)
    if target in restored.fixtures:
        assert restored.simulate_fixture(target) == s._world.simulate_fixture(target)


def test_session_can_restore_world_results_without_restoring_player_state(tmp_path):
    s = DevelopmentSession()
    s.quick_simulate()
    s.continue_to_next_match()
    path = tmp_path / "world.json"
    s.save_world(path)
    loaded = DevelopmentSession()
    loaded.load_world(path)
    assert loaded.world_result_count == s.world_result_count
    assert loaded._world.to_dict() == s._world.to_dict()
    assert loaded._active_match.fixture.fixture_id == s._active_match.fixture.fixture_id


def test_invalid_world_saves_fail_closed(tmp_path):
    world = DevelopmentSession()._world
    snapshot = world.to_dict()
    bad = dict(snapshot)
    bad["schema_version"] = 999
    with pytest.raises(ValueError, match="version"):
        WorldSeasonRunner.from_dict(bad)
    bad = dict(snapshot)
    bad["calendar"] = dict(snapshot["calendar"])
    bad["calendar"]["fixtures"] = bad["calendar"]["fixtures"][:-1]
    with pytest.raises(ValueError, match="does not match"):
        WorldSeasonRunner.from_dict(bad)
    wrong_participant = json.loads(json.dumps(snapshot))
    wrong_participant["calendar"]["fixtures"][0]["home_club_id"] = "another-club"
    with pytest.raises(ValueError, match="does not match sporting fixture"):
        WorldSeasonRunner.from_dict(wrong_participant)


def test_world_match_results_validate_score_and_shootout():
    with pytest.raises(ValueError, match="negative"):
        WorldMatchResult("f", -1, 0)
    with pytest.raises(ValueError, match="level"):
        WorldMatchResult("f", 1, 1, 4, 4)
    with pytest.raises(ValueError, match="resolver"):
        WorldMatchResult("f", 1, 1, resolver="bad")


def test_english_cup_bracket_exposes_dates_and_final_result():
    s = DevelopmentSession()
    assert "2026" in s.world_cup_bracket_rows("carabao-cup")[0].status
    s._world.advance_until(date(2027, 6, 1))
    s._sync_world_view()
    for cup_id in ("fa-cup", "carabao-cup"):
        assert "Champion" in s.world_cup_summary(cup_id)
        assert all(row.score != "-" for row in s.world_cup_bracket_rows(cup_id))
