"""TS-06: country-independent career orchestration with England compatibility."""
from __future__ import annotations

from dataclasses import dataclass

import pytest

from football_manager.domain.career import WorldCareer, ENGLISH_CAREER_TRANSITION
from football_manager.domain.season_cycle import SeasonReport
from tools.stress_world_calendar import create_world


@dataclass(frozen=True)
class SyntheticCountryTransition:
    transition_id: str = "synthetic-country-v1"
    fail: bool = False

    def finish(self, world, *, european_policy):
        next_tiers = {cid: tuple(edition.participant_club_ids)
                      for cid, edition in world.leagues.items()}
        return SeasonReport(
            season_label=world.season_label,
            league_tables=next_tiers,
            champions={}, promoted={}, relegated={}, next_tiers=next_tiers,
            europe={}, external_national_league_promotions=(),
            fixture_count=len(world.results),
        )

    def build_next(self, previous, report, names):
        names["new-club"] = "Provisional new club"
        if self.fail:
            raise RuntimeError("injected country transition failure")
        next_year = int(previous.season_label[:4]) + 1
        future, _ = create_world(leagues=1, seed=previous.seed, year=next_year)
        return future


def test_default_english_transition_is_preserved_in_new_and_old_archives():
    world, _ = create_world(leagues=1, seed=2002)
    career = WorldCareer(world, {"club-a": "Club A"})
    payload = career.to_dict()
    assert payload["transition_id"] == ENGLISH_CAREER_TRANSITION.transition_id
    assert WorldCareer.from_dict(payload).transition == ENGLISH_CAREER_TRANSITION
    payload.pop("transition_id")
    assert WorldCareer.from_dict(payload).transition == ENGLISH_CAREER_TRANSITION


def test_custom_transition_supports_non_english_season_and_archive(tmp_path):
    world, _ = create_world(leagues=1, seed=5111)
    world.advance_until(__import__("datetime").date(2027, 6, 30))
    strategy = SyntheticCountryTransition()
    career = WorldCareer(world, {}, transition=strategy)
    report = career.begin_next_season()
    assert len(report.next_tiers) == 1
    assert len(career.worlds) == 2
    assert "new-club" in career.club_names
    path = tmp_path / "country-career.json"
    career.save_json(path)
    with pytest.raises(ValueError, match="unknown career transition"):
        WorldCareer.load_json(path)
    recovered = WorldCareer.load_json(path, transitions={strategy.transition_id: strategy})
    assert recovered.current.season_label == "2027/28"
    assert recovered.reports == [report]
    assert recovered.club_names == career.club_names


def test_failed_country_transition_does_not_commit_names_or_world():
    world, _ = create_world(leagues=1, seed=5111)
    strategy = SyntheticCountryTransition(fail=True)
    career = WorldCareer(world, {"existing": "Existing"}, transition=strategy)
    with pytest.raises(RuntimeError, match="injected country transition"):
        career.begin_next_season()
    assert career.club_names == {"existing": "Existing"}
    assert career.worlds == [world]
    assert career.reports == []


def test_invalid_transition_catalog_or_unknown_roster_rejected():
    world, _ = create_world(leagues=1, seed=5111)
    career = WorldCareer(world, {})
    data = career.to_dict()
    data["transition_id"] = "unknown-country-v7"
    with pytest.raises(ValueError, match="unknown career transition"):
        WorldCareer.from_dict(data)
    data["transition_id"] = ENGLISH_CAREER_TRANSITION.transition_id
    with pytest.raises(ValueError, match="reserved ID"):
        WorldCareer.from_dict(data, transitions={
            ENGLISH_CAREER_TRANSITION.transition_id: SyntheticCountryTransition(
                ENGLISH_CAREER_TRANSITION.transition_id,
            ),
        })
