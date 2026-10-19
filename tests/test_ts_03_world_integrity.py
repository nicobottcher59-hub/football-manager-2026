"""TS-03: saved results cannot bypass the rules applied during live play."""
from copy import deepcopy
from datetime import date

import pytest

from football_manager.data.staged_2026_27 import build_efl_trophy_2026_27
from football_manager.dev_ui import DevelopmentSession
from football_manager.domain.domestic_cups import DomesticCupRound, DomesticCupSeason
from football_manager.domain.world_runner import WorldSeasonRunner


def _finished_final() -> tuple[WorldSeasonRunner, str]:
    world = WorldSeasonRunner()
    cup = DomesticCupSeason(
        "integrity-final", "Integrity test final", "2026/27",
        (DomesticCupRound("final", "Final", (date(2027, 5, 20),), entrants=("a", "b")),),
    )
    world.register_cup(cup, strengths={"a": 75, "b": 75})
    fixture = cup.plans[0].fixtures[0]
    world.record_result(fixture.fixture_id, 2, 1)
    return world, fixture.fixture_id


def test_reject_saved_cup_champion_that_does_not_match_decided_final():
    world, _ = _finished_final()
    archive = world.to_dict()
    cup = archive["cups"]["integrity-final"]
    cup["champion_club_id"] = "not-the-final-winner"
    with pytest.raises(ValueError, match="champion does not match final"):
        WorldSeasonRunner.from_dict(archive)


def test_reject_saved_knockout_draw_without_required_decider():
    world, fixture_id = _finished_final()
    archive = world.to_dict()
    saved = next(r for r in archive["results"] if r["fixture_id"] == fixture_id)
    saved["home_goals"] = 1
    saved["away_goals"] = 1
    with pytest.raises(ValueError, match="must produce a winner"):
        WorldSeasonRunner.from_dict(archive)


def test_reject_saved_league_result_with_penalties():
    world = DevelopmentSession()._world
    league_id = next(iter(world.leagues))
    fixture_id = world.leagues[league_id].fixtures[0].fixture_id
    world.record_result(fixture_id, 2, 0)
    archive = world.to_dict()
    result = next(r for r in archive["results"] if r["fixture_id"] == fixture_id)
    result.update(penalties_home=5, penalties_away=4)
    with pytest.raises(ValueError, match="league fixtures cannot have penalties"):
        WorldSeasonRunner.from_dict(archive)


def test_reject_saved_efl_trophy_group_draw_without_shootout():
    league_one = tuple(f"l1-{i}" for i in range(24))
    league_two = tuple(f"l2-{i}" for i in range(24))
    comp = build_efl_trophy_2026_27(league_one, league_two)
    world = WorldSeasonRunner()
    world.register_staged(comp, strengths={club: 70 for club in comp.participants})
    fixture_id = comp.primary_fixtures[0].fixture_id
    world.record_result(fixture_id, 1, 1, penalties_home=5, penalties_away=4)
    archive = world.to_dict()
    result = next(r for r in archive["results"] if r["fixture_id"] == fixture_id)
    result.update(penalties_home=0, penalties_away=0)
    with pytest.raises(ValueError, match="drawn group matches require a shootout"):
        WorldSeasonRunner.from_dict(archive)


def test_save_fails_closed_on_orphan_fixture_before_creating_file(tmp_path):
    world, fid = _finished_final()
    from dataclasses import replace
    world.fixtures["orphan-fixture"] = replace(world.fixtures[fid], fixture_id="orphan-fixture")
    target = tmp_path / "invalid.json"
    with pytest.raises(ValueError, match="fixture ledger differs"):
        world.save_json(target)
    assert not target.exists()


def test_valid_completed_final_survives_integrity_check_and_file_roundtrip(tmp_path):
    world, _ = _finished_final()
    world.validate_integrity()
    target = tmp_path / "valid.json"
    world.save_json(target)
    loaded = WorldSeasonRunner.load_json(target)
    assert loaded.to_dict() == world.to_dict()
    loaded.validate_integrity()
