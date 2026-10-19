"""Phase 6.6a/6.6b: physical balance, authentic formats, one persistent world."""
from __future__ import annotations

from collections import Counter
from datetime import date

import pytest

from football_manager.data import build_efl_trophy_2026_27, build_uefa_2026_27
from football_manager.dev_ui import DevelopmentSession
from football_manager.domain.calendar import ScheduleSource
from football_manager.domain.knockout import KnockoutDrawSource, KnockoutLegFormat
from football_manager.domain.world_runner import WorldSeasonRunner


def test_uefa_league_phases_have_correct_cardinality_and_balanced_venues():
    clubs = tuple(f"club-{i:02d}" for i in range(36))
    for comp_id, matchdays in (("champions-league", 8), ("europa-league", 8),
                               ("conference-league", 6)):
        comp = build_uefa_2026_27(comp_id, clubs)
        assert len(comp.primary_fixtures) == matchdays * 18
        assert len(comp.primary_dates) == len(comp.primary_fixtures)
        home, away = Counter(), Counter()
        opponents = {c: set() for c in clubs}
        rounds = {}
        for f in comp.primary_fixtures:
            home[f.home_club_id] += 1
            away[f.away_club_id] += 1
            opponents[f.home_club_id].add(f.away_club_id)
            opponents[f.away_club_id].add(f.home_club_id)
            rounds.setdefault(f.round_number, []).extend((f.home_club_id, f.away_club_id))
        assert all(home[c] == away[c] == matchdays // 2 for c in clubs)
        assert all(len(opponents[c]) == matchdays for c in clubs)
        assert set(rounds) == set(range(1, matchdays + 1))
        assert all(set(ids) == set(clubs) and len(ids) == 36 for ids in rounds.values())


def test_generated_uefa_schedule_is_deterministic_but_seed_sensitive():
    clubs = tuple(f"club-{i:02d}" for i in range(36))
    first = build_uefa_2026_27("champions-league", clubs, seed=812)
    duplicate = build_uefa_2026_27("champions-league", clubs, seed=812)
    changed = build_uefa_2026_27("champions-league", clubs, seed=813)
    assert first.primary_fixtures == duplicate.primary_fixtures
    assert first.primary_fixtures != changed.primary_fixtures
    assert len(first.knockout_windows) == 5


@pytest.mark.parametrize("bad", ["unknown", "uefa-cup"])
def test_uefa_rejects_unsupported_competitions(bad):
    with pytest.raises(ValueError, match="unsupported"):
        build_uefa_2026_27(bad, tuple(f"club-{i}" for i in range(36)))


def test_efl_trophy_uses_exact_48_seniors_and_16_youth_invitees():
    l1 = tuple(f"l1-{i:02d}" for i in range(24))
    l2 = tuple(f"l2-{i:02d}" for i in range(24))
    trophy = build_efl_trophy_2026_27(l1, l2)
    assert len(trophy.participants) == 64
    assert len(trophy.groups) == 16
    assert len(trophy.primary_fixtures) == 96
    assert len(set(trophy.participants)) == 64
    for group in trophy.groups.values():
        assert len(group) == 4
        assert len([c for c in group if "-u21-" in c]) == 1
        games = [f for f in trophy.primary_fixtures if f.home_club_id in group]
        assert len(games) == 6
        assert all(f.away_club_id in group for f in games)
        assert all(len([f for f in games if c in (f.home_club_id, f.away_club_id)]) == 3 for c in group)


def _build_empty_trophy_runner():
    l1 = tuple(f"l1-{i:02d}" for i in range(24))
    l2 = tuple(f"l2-{i:02d}" for i in range(24))
    comp = build_efl_trophy_2026_27(l1, l2)
    world = WorldSeasonRunner()
    world.register_staged(comp, strengths={c: 48 for c in comp.participants})
    return world, comp


def test_trophy_drawn_group_match_requires_shootout_and_awards_2_and_1_points():
    world, comp = _build_empty_trophy_runner()
    f = comp.primary_fixtures[0]
    with pytest.raises(ValueError, match="require a shootout"):
        world.record_result(f.fixture_id, 1, 1)
    with pytest.raises(ValueError, match="require a shootout"):
        world.record_result(f.fixture_id, 2, 1, penalties_home=4, penalties_away=3)
    world.record_result(f.fixture_id, 1, 1, penalties_home=5, penalties_away=4)
    group_id = next(key for key, clubs in comp.groups.items() if f.home_club_id in clubs)
    table = {r.club_id: r for r in world.standings("efl-trophy", group_id)}
    assert table[f.home_club_id].points == 2
    assert table[f.away_club_id].points == 1
    assert table[f.home_club_id].drawn == table[f.away_club_id].drawn == 1


def test_world_staged_uefa_shootouts_only_in_knockout():
    clubs = tuple(f"team-{i:02d}" for i in range(36))
    competition = build_uefa_2026_27("europa-league", clubs)
    world = WorldSeasonRunner()
    world.register_staged(competition, strengths={club: 75 for club in clubs})
    f = competition.primary_fixtures[0]
    with pytest.raises(ValueError, match="never has shootouts"):
        world.record_result(f.fixture_id, 1, 1, penalties_home=4, penalties_away=3)
    assert world.record_result(f.fixture_id, 1, 1).fixture_id == f.fixture_id
    assert world.result_for(f.fixture_id) is not None


def test_competition_progression_to_final_and_generated_draw_provenance():
    clubs = tuple(f"team-{i:02d}" for i in range(36))
    competition = build_uefa_2026_27("conference-league", clubs)
    world = WorldSeasonRunner()
    world.register_staged(competition, strengths={club: 65 for club in clubs})
    world.advance_until(date(2027, 6, 15))
    assert len(competition.knockout_plans) == 5
    assert [p.definition.round_id for p in competition.knockout_plans] == list(competition.rounds)
    assert all(plan.source is KnockoutDrawSource.GENERATED for plan in competition.knockout_plans)
    assert all(p.definition.leg_format is (KnockoutLegFormat.SINGLE_LEG if p.definition.round_id == "final"
                                           else KnockoutLegFormat.TWO_LEGGED)
               for p in competition.knockout_plans)
    assert competition.champion_club_id in competition.participants
    assert not world.calendar.detect_conflicts(minimum_rest_hours=48)


def test_trophy_draw_keeps_north_and_south_separate_through_r16():
    world, trophy = _build_empty_trophy_runner()
    # Complete the group phase, then its first knockout round.
    world.advance_until(date(2026, 12, 3))
    first = trophy.knockout_plans[0]
    assert first.definition.round_id == "r32"
    north = {c for name, ids in trophy.groups.items() if name.startswith("north") for c in ids}
    south = set(trophy.participants) - north
    for tie in first.ties:
        assert ({tie.club_a_id, tie.club_b_id} <= north or
                {tie.club_a_id, tie.club_b_id} <= south)
    world.advance_until(date(2026, 12, 25))
    second = trophy.knockout_plans[1]
    assert second.definition.round_id == "r16"
    for tie in second.ties:
        assert ({tie.club_a_id, tie.club_b_id} <= north or
                {tie.club_a_id, tie.club_b_id} <= south)
    world.advance_until(date(2027, 5, 1))
    assert trophy.champion_club_id in trophy.participants


def test_staged_world_save_midseason_preserves_ties_and_continue(tmp_path):
    clubs = tuple(f"team-{i:02d}" for i in range(36))
    competition = build_uefa_2026_27("champions-league", clubs)
    world = WorldSeasonRunner()
    world.register_staged(competition, strengths={club: 80 for club in clubs})
    world.advance_until(date(2027, 2, 1))
    assert competition.knockout_plans[0].definition.round_id == "playoff"
    saved = tmp_path / "world.json"
    world.save_json(saved)
    restored = WorldSeasonRunner.load_json(saved)
    assert restored.to_dict() == world.to_dict()
    restored.advance_until(date(2027, 6, 15))
    assert restored.staged["champions-league"].champion_club_id
    assert len(restored.results) == len(restored.fixtures)


def test_staged_world_runner_maintains_four_leagues_and_six_cups():
    session = DevelopmentSession()
    assert len(session._world.leagues) == 4
    assert len(session._world.cups) == 2
    assert set(session._world.staged) == {
        "champions-league", "europa-league", "conference-league", "efl-trophy",
    }
    assert len(session._world.fixtures) == 2620
    assert all(f.source is ScheduleSource.GENERATED
               for f in session._world.fixtures.values())
    names = {r.competition for r in session.calendar_rows}
    assert "UEFA Champions League" in names
    assert "Development Continental" not in names
    assert "Carabao Cup" in names
    assert all("Conditional" not in r.status for r in session.calendar_rows)


def test_managed_uefa_competition_is_recorded_in_canonical_world():
    session = DevelopmentSession()
    while session._active_match.competition_key != "champions-league":
        session.quick_simulate()
        session.continue_to_next_match()
    item = session._active_match
    result = session.quick_simulate()
    stored = session._world.result_for(item.fixture.fixture_id)
    assert stored is not None and stored.resolver == "managed"
    assert (stored.home_goals, stored.away_goals) == (result.home_goals, result.away_goals)
    assert any(r.competition == "UEFA Champions League" and "Played" in r.status
               for r in session.calendar_rows)
    assert len(session.staged_competition_table_rows("champions-league")) == 36


@pytest.mark.parametrize("home,away,ph,pa,managed_home,expected", [
    (2, 1, 0, 0, True, "V"), (2, 1, 0, 0, False, "D"),
    (0, 0, 0, 0, True, "E"), (1, 1, 4, 3, True, "V"),
    (1, 1, 4, 3, False, "D"), (3, 3, 2, 5, True, "D"),
])
def test_calendar_result_color_codes_include_shootout_outcomes(home, away, ph, pa, managed_home, expected):
    assert DevelopmentSession.outcome_for_result(
        home, away, managed_home=managed_home,
        penalties_home=ph, penalties_away=pa,
    ) == expected


def test_no_stale_fixed_conditional_calendar_entries_after_european_progression():
    session = DevelopmentSession()
    assert not any("TBD if qualified" in r.opponent for r in session.calendar_rows)
    world = session._world
    world.advance_until(date(2027, 6, 15))
    session._sync_world_view()
    assert not any("TBD if qualified" in r.opponent for r in session.calendar_rows)
    assert not any("Conditional" in r.status for r in session.calendar_rows)
    stages = session._world.staged["champions-league"]
    for plan in stages.knockout_plans:
        expected = [f.fixture_id for f in plan.fixtures if session.home_club.id in
                    (f.home_club_id, f.away_club_id)]
        for f in expected:
            assert sum(f == row.fixture.fixture_id for row in session._managed_schedule.values()) == 1


@pytest.mark.parametrize("condition", [100, 75, 50, 25])
def test_fitness_has_progressively_penalized_actual_rating(condition):
    session = DevelopmentSession()
    player = session.home_lineup.starters[0].player
    player.state.fitness = condition
    player.state.morale = 100
    evaluation = player.current_rating()
    assert evaluation.overall == pytest.approx(player.overall_rating)
    if condition == 75:
        assert evaluation.adjustment("condition") == 0
    if condition <= 50:
        assert evaluation.adjustment("condition") <= -10


def test_condition_penalty_reaches_match_snapshot_and_is_not_erased_by_morale():
    session = DevelopmentSession()
    player = session.home_lineup.starters[0].player
    player.state.morale = 100
    samples = []
    for fitness in (100, 75, 50, 25):
        player.state.fitness = fitness
        snapshot = session._build_snapshot()
        side = snapshot.home_team if snapshot.home_team.club_id == session.home_club.id else snapshot.away_team
        samples.append(side.player(player.id).current_rating)
    assert samples[0] == samples[1]
    assert samples[1] - samples[2] > 10
    assert samples[2] - samples[3] > 5


def test_morale_after_repeated_wins_does_not_permanently_clamp_at_100():
    session = DevelopmentSession()
    winner = session.home_lineup.starters[0].player
    winner.state.morale = 100
    fake = type("WonMatch", (), {"home_club_id": session.home_club.id,
                                  "home_goals": 2, "away_goals": 0})()
    session._apply_managed_result_morale(fake)
    assert winner.state.morale < 100
    for _ in range(50):
        session._apply_managed_result_morale(fake)
    assert winner.state.morale < 99


def test_managed_champions_final_remains_playable_after_last_premier_match():
    """Regression: unknown late knockouts must not be skipped by Continue."""
    session = DevelopmentSession()
    played = []
    for _ in range(90):
        item = session._active_match
        fixture = item.fixture
        goals_home, goals_away = ((7, 0) if fixture.home_club_id == session.home_club.id
                                  else (0, 7))
        # Force a direct finalist, checking calendar/runner chronology rather than
        # the random result of one Fast Simulator seed.
        session._world.record_result(fixture.fixture_id, goals_home, goals_away, resolver="managed")
        session._sync_world_view()
        session.match_played = True
        played.append((item.match_date, item.competition_key, item.stage_id))
        try:
            session.continue_to_next_match()
        except RuntimeError as error:
            assert "no remaining managed fixtures" in str(error)
            break
    else:
        pytest.fail("managed world did not complete after 90 scheduled games")
    assert any(key == "champions-league" and stage == "final" and d == date(2027, 6, 5)
               for d, key, stage in played)
    assert session._world.staged["champions-league"].champion_club_id == session.home_club.id
    assert len(session._world.fixtures) == len(session._world.results) == 2959
    assert not session._world.calendar.detect_conflicts(minimum_rest_hours=48)
