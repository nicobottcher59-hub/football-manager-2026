"""Phase 6.7: real EFL promotion rules, persistent world and DEV season controls."""
from __future__ import annotations

from datetime import date
from types import SimpleNamespace

import pytest

from football_manager.data.future_seasons import generated_edition, round_dates
from football_manager.dev_ui import DevelopmentSession
from football_manager.domain.career import WorldCareer, next_season_world
from football_manager.domain.knockout import KnockoutLegFormat, KnockoutMatchResult
from football_manager.domain.season_cycle import (
    EuropeanAccessPolicy, PLAYOFF_IDS, TIER_IDS, create_efl_playoffs,
    european_qualifiers, finalize_season,
)


@pytest.fixture(scope="module")
def completed_world():
    """A completed 2026/27 world shared by integration tests; no state mutations."""
    world = DevelopmentSession()._world
    world.advance_until(date(2027, 6, 30))
    assert len(world.fixtures) == len(world.results) == 2959
    return world


@pytest.mark.parametrize(
    ("league_id", "expected_seed_pairs", "expected_fixtures"),
    [
        ("dev-championship", (("05", "08"), ("06", "07")), 7),
        ("dev-league-one", (("06", "03"), ("05", "04")), 5),
        ("dev-league-two", (("07", "04"), ("06", "05")), 5),
    ],
)
def test_efl_playoff_entry_and_seed_rules(league_id, expected_seed_pairs, expected_fixtures):
    standings = tuple(f"club-{n:02d}" for n in range(1, 25))
    cup = create_efl_playoffs(league_id, standings, 2026)
    plan = cup.start()
    pairings = tuple((tie.club_a_id[-2:], tie.club_b_id[-2:]) for tie in plan.ties)
    assert pairings == expected_seed_pairs
    assert cup.cup_id == PLAYOFF_IDS[league_id]
    assert len(cup.rounds) == (3 if league_id == "dev-championship" else 2)
    assert sum(r.leg_format.leg_count * count for r, count in zip(
        cup.rounds, (2, 2, 1) if league_id == "dev-championship" else (2, 1)
    )) == expected_fixtures
    assert "GENERATED" in cup.qualification_note
    assert cup.to_dict()["pairing_strategy"] == "promotion-playoffs"


@pytest.mark.parametrize(
    ("first_winner", "second_winner", "third_opponent", "fourth_opponent"),
    [
        ("05", "06", "06", "05"),  # higher eliminator seed must face fourth
        ("08", "06", "08", "06"),  # eighth eliminates fifth
        ("05", "07", "07", "05"),
        ("08", "07", "08", "07"),
    ],
)
def test_championship_semifinal_pairings_reseed_by_eliminator_finish(
    first_winner, second_winner, third_opponent, fourth_opponent,
):
    clubs = tuple(f"c{n:02d}" for n in range(1, 25))
    cup = create_efl_playoffs("dev-championship", clubs, 2026)
    eliminators = cup.start()
    first, second = eliminators.fixtures
    results = {
        first.fixture_id: KnockoutMatchResult(
            first.fixture_id, 1 if first_winner == "05" else 0,
            0 if first_winner == "05" else 1,
        ),
        second.fixture_id: KnockoutMatchResult(
            second.fixture_id, 1 if second_winner == "06" else 0,
            0 if second_winner == "06" else 1,
        ),
    }
    semifinals = cup.after_results(results)
    assert semifinals is not None
    assert semifinals.definition.leg_format is KnockoutLegFormat.TWO_LEGGED
    assert tuple((tie.club_a_id, tie.club_b_id) for tie in semifinals.ties) == (
        (f"c{third_opponent}", "c03"), (f"c{fourth_opponent}", "c04"),
    )
    # Strongest seeds host the return legs.
    assert all(tie.fixtures[1].home_club_id in ("c03", "c04") for tie in semifinals.ties)


def test_cannot_finalize_before_all_world_games_and_playoffs():
    with pytest.raises(ValueError, match="unplayed fixtures"):
        finalize_season(DevelopmentSession()._world)


def test_european_access_deduplicates_with_league_and_cup_fallback():
    table = tuple(f"premier-{n:02d}" for n in range(1, 21))
    tables = {TIER_IDS[0]: table}
    tables.update({cid: tuple(f"{cid}-team-{n:02d}" for n in range(1, 25)) for cid in TIER_IDS[1:]})
    cups = {cid: SimpleNamespace(champion_club_id=club)
            for cid, club in (("fa-cup", table[0]), ("carabao-cup", table[7]))}
    stages = {cid: SimpleNamespace(champion_club_id=None) for cid in
              ("champions-league", "europa-league", "conference-league")}
    access = european_qualifiers(
        SimpleNamespace(cups=cups, staged=stages), tables,
        EuropeanAccessPolicy(performance_spot=True),
    )
    assert access["champions-league"] == table[:5]
    assert access["europa-league"] == (table[5], table[6])
    assert access["conference-league"] == (table[7],)
    all_access = [club for group in access.values() for club in group]
    assert len(all_access) == len(set(all_access))


def test_future_league_calendar_is_newly_generated_not_date_shift():
    prev = DevelopmentSession()._world.leagues["dev-premier"]
    promoted_roster = ("incoming-club", *prev.participant_club_ids[:-1])
    next_edition, schedule = generated_edition(prev, promoted_roster, 2027, seed=6700)
    assert len(next_edition.fixtures) == len(schedule.fixtures) == 380
    assert next_edition.season_label == "2027/28"
    assert "incoming-club" in next_edition.participant_club_ids
    assert set(f.fixture_id for f in next_edition.fixtures).isdisjoint(
        f.fixture_id for f in prev.fixtures)
    from football_manager.data.premier_calendar import premier_reference_slots
    reference = premier_reference_slots(2027)
    assert {f.kickoff for f in schedule.fixtures} == {
        kickoff for slots in reference.values() for kickoff in slots
    }
    assert {f.kickoff.weekday() for f in schedule.fixtures} >= {4, 5, 6, 0}
    assert all(f.source.value == "generated" for f in schedule.fixtures)
    assert len(round_dates(2027, 46)) == 46
    assert len(set(round_dates(2027, 46))) == 46


def test_playoffs_are_registered_and_complete_in_shared_runner(completed_world):
    world = completed_world
    assert tuple(sorted(PLAYOFF_IDS.values())) == tuple(sorted(set(world.cups) - {"fa-cup", "carabao-cup"}))
    assert all(world.cups[cid].champion_club_id for cid in PLAYOFF_IDS.values())
    assert sum(len(cup.plans[-1].fixtures) for cid, cup in world.cups.items()
               if cid in PLAYOFF_IDS.values()) == 3
    for league, cup_id in PLAYOFF_IDS.items():
        standings = tuple(row.club_id for row in world.standings(league))
        assert world.cups[cup_id].champion_club_id in standings[2:8]
    assert not world.calendar.detect_conflicts(minimum_rest_hours=48)


def test_season_report_moves_correct_clubs_and_preserves_92_professional_slots(completed_world):
    report = finalize_season(completed_world)
    assert report.season_label == "2026/27"
    assert set(report.next_tiers) == set(TIER_IDS)
    assert tuple(map(lambda cid: len(report.next_tiers[cid]), TIER_IDS)) == (20, 24, 24, 24)
    assert len(set().union(*(set(v) for v in report.next_tiers.values()))) == 92
    for league in PLAYOFF_IDS:
        assert completed_world.cups[PLAYOFF_IDS[league]].champion_club_id in report.promoted[league]
    assert len(report.promoted["dev-championship"]) == 3
    assert len(report.promoted["dev-league-one"]) == 3
    assert len(report.promoted["dev-league-two"]) == 4
    assert len(report.relegated["dev-premier"]) == 3
    assert len(report.relegated["dev-league-one"]) == 4
    assert len(report.relegated["dev-league-two"]) == 2
    assert set(report.relegated["dev-premier"]).issubset(report.next_tiers["dev-championship"])
    assert set(report.relegated["dev-league-two"]).isdisjoint(
        set().union(*(set(v) for v in report.next_tiers.values())))
    assert len(report.external_national_league_promotions) == 2
    assert len([club for group in report.europe.values() for club in group]) == len(set(
        club for group in report.europe.values() for club in group))
    assert type(report).from_dict(report.to_dict()) == report


def test_career_transition_creates_fresh_connected_competitions(completed_world):
    report = finalize_season(completed_world)
    names = {club: club for club in completed_world.strengths}
    new_world = next_season_world(completed_world, report, names)
    assert new_world.season_label == "2027/28"
    assert {cid: tuple(e.participant_club_ids) for cid, e in new_world.leagues.items()} == report.next_tiers
    assert not set(new_world.fixtures).intersection(completed_world.fixtures)
    assert len(new_world.fixtures) > 2500
    assert len(new_world.staged["champions-league"].participants) == 36
    assert len(new_world.staged["europa-league"].participants) == 36
    assert len(new_world.staged["conference-league"].participants) == 36
    assert {"fa-cup", "carabao-cup"}.issubset(new_world.cups)
    assert new_world.promotion_playoff_leagues == completed_world.promotion_playoff_leagues
    assert not new_world.calendar.detect_conflicts(minimum_rest_hours=48)
    assert set(report.external_national_league_promotions).issubset(names)


def test_results_only_career_archive_reloads_season_transition(completed_world, tmp_path):
    names = {club: club for club in completed_world.strengths}
    career = WorldCareer(completed_world, names)
    archived = career.begin_next_season()
    path = tmp_path / "history" / "career_results.json"
    career.save_json(path)
    restored = WorldCareer.load_json(path)
    assert restored.reports == [archived]
    assert restored.current.season_label == "2027/28"
    assert restored.worlds[0].results.keys() == completed_world.results.keys()
    assert tuple(restored.current.leagues["dev-premier"].participant_club_ids) == archived.next_tiers["dev-premier"]
    payload = career.to_dict()
    payload["worlds"].pop()
    with pytest.raises(ValueError, match="timeline"):
        WorldCareer.from_dict(payload)


def test_dev_advantage_changes_only_opponent_snapshot_never_persistent_squad():
    session = DevelopmentSession()
    source_strengths = dict(session._world.strengths)
    # Normalize the initial reference opponent through the same generated
    # opponent preparation path used after a DEV checkbox change.
    session._prepare_development_opponent()
    def snapshot_strength():
        snapshot = session._build_snapshot()
        team = snapshot.away_team if session.managed_is_home else snapshot.home_team
        return sum(p.overall_rating for p in team.starters)
    opponent = snapshot_strength()
    original_attributes = {p.id: p.attributes for p in session.away_club.squad.players}
    session.set_dev_favorable_mode(True)
    weaker = snapshot_strength()
    assert weaker < opponent
    assert original_attributes == {p.id: p.attributes for p in session.away_club.squad.players}
    assert session._world.strengths == source_strengths
    assert not session.match_played
    session.set_dev_favorable_mode(False)
    assert snapshot_strength() == opponent


def test_managed_one_click_runs_fast_sim_and_can_start_next_season():
    session = DevelopmentSession()
    session.set_dev_favorable_mode(True)
    progression: list[int] = []
    managed = session.simulate_remaining_season(on_progress=progression.append)
    assert managed >= 38
    assert progression == list(range(1, managed + 1))
    assert session.season_finished
    assert session.match_summary() is not None  # no active fixture after bulk completion
    assert session.match_summary().scoreline
    assert len(session._world.results) == len(session._world.fixtures) == 2959
    managed_world_results = [r for r in session._world.results.values() if r.resolver == "managed"]
    assert len(managed_world_results) == managed
    assert any(f.competition_key == "champions-league" for f in session._managed_schedule.values())
    report = session.begin_next_season()
    assert report.season_label == "2026/27"
    assert session._world.season_label == "2027/28"
    assert session.archived_season_reports == (report,)
    assert session.can_quick_sim
    assert not session.season_finished
