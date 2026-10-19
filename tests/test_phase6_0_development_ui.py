from __future__ import annotations

from datetime import date

import pytest

from football_manager.dev_ui import DevelopmentSession
from football_manager.domain import TacticalPreset
from football_manager.fast_simulation import FastMatchResult


def test_development_session_exposes_real_squad_state() -> None:
    session = DevelopmentSession()

    rows = session.squad_rows()

    assert len(rows) == 18
    assert sum(row.squad_status == "XI" for row in rows) == 11
    assert sum(row.squad_status == "BENCH" for row in rows) == 7
    assert all(1.0 <= row.overall <= 100.0 for row in rows)
    assert all(1.0 <= row.current <= 100.0 for row in rows)
    assert all(0.0 <= row.condition <= 100.0 for row in rows)


def test_tactical_preset_changes_real_tactical_style() -> None:
    session = DevelopmentSession()
    baseline = session.tactical_view()

    updated = session.set_tactical_preset(TacticalPreset.CONSTANT_PRESS)

    assert baseline.preset is TacticalPreset.BALANCED
    assert updated.preset is TacticalPreset.CONSTANT_PRESS
    assert updated.pressing > baseline.pressing
    assert updated.tempo > baseline.tempo
    assert len(session.home_lineup.starters) == 11


def test_lineup_swap_keeps_valid_xi_and_contextual_act_changes() -> None:
    session = DevelopmentSession()
    rows = session.squad_rows()
    striker = next(row for row in rows if row.squad_status == "XI" and row.slot == "ST")
    centre_back = next(row for row in rows if row.squad_status == "BENCH" and row.position == "CB")

    session.swap_lineup(striker.player_id, centre_back.player_id)
    updated = {row.player_id: row for row in session.squad_rows()}

    assert updated[centre_back.player_id].squad_status == "XI"
    assert updated[centre_back.player_id].slot == "ST"
    assert updated[striker.player_id].squad_status == "BENCH"
    assert updated[centre_back.player_id].current < updated[centre_back.player_id].overall
    assert len(session.home_lineup.starters) == 11
    assert len(session.home_lineup.bench) == 7


def test_quick_sim_uses_fast_simulator_and_persists_condition() -> None:
    session = DevelopmentSession()
    condition_before = {
        row.player_id: row.condition
        for row in session.squad_rows()
        if row.squad_status == "XI"
    }

    result = session.quick_simulate()

    assert isinstance(result, FastMatchResult)
    assert session.match_played is True
    assert session.can_quick_sim is False
    after = {row.player_id: row.condition for row in session.squad_rows()}
    assert any(after[player_id] < before for player_id, before in condition_before.items())
    assert session.match_summary() is not None


def test_sandbox_can_advance_to_next_managed_match_after_quick_sim() -> None:
    session = DevelopmentSession()
    first_match_id = session._active_match.fixture.fixture_id
    first_match_day = session.current_date
    first = session.quick_simulate()

    with pytest.raises(RuntimeError, match="Continue to the next match"):
        session.quick_simulate()

    # The next match may belong to a cup or UEFA, not necessarily the Premier
    # League. Choose from the actual season calendar rather than assuming a
    # league match is always next.
    expected_next = session._next_unplayed_managed_match()
    assert expected_next is not None
    assert expected_next.fixture.fixture_id != first_match_id
    assert expected_next.match_date > first_match_day
    assert session.can_continue is True
    session.continue_to_next_match()

    assert first.match_id == "dev-ui-6003"
    assert session._active_match.fixture.fixture_id == expected_next.fixture.fixture_id
    assert session._active_match.competition_key == expected_next.competition_key
    assert session.current_date == expected_next.match_date
    assert session.managed_is_home == (expected_next.fixture.home_club_id == session.home_club.id)
    assert session.can_quick_sim is True
    assert session.can_continue is False
    assert len(session._league_results) == 10
    assert all(row.played == 1 for row in session.league_table_rows())
    snapshot = session._build_snapshot()
    assert snapshot.home_team.club_id == expected_next.fixture.home_club_id
    assert snapshot.away_team.club_id == expected_next.fixture.away_club_id

    second = session.quick_simulate()
    assert second.match_id == "dev-ui-6004"
    assert session._world.result_for(expected_next.fixture.fixture_id) is not None
    assert session.can_continue is True


def test_final_round_quick_sim_records_managed_result_once_in_world_ledger() -> None:
    session = DevelopmentSession()
    final_fixture = next(
        fixture
        for fixture in session._league_edition.fixtures
        if fixture.round_number == 38
        and session.home_club.id in (fixture.home_club_id, fixture.away_club_id)
    )
    session._current_league_fixture = final_fixture
    session._active_match = next(
        item
        for item in session._managed_schedule.values()
        if item.fixture.fixture_id == final_fixture.fixture_id
    )
    session.current_date = session._active_match.match_date
    session._prepare_development_opponent()

    session.quick_simulate()

    round_38_ids = {
        fixture.fixture_id
        for fixture in session._league_edition.fixtures
        if fixture.round_number == 38
    }
    round_38_results = [
        result for result in session._league_results if result.fixture_id in round_38_ids
    ]
    assert len(round_38_results) == 1
    assert round_38_results[0].fixture_id == final_fixture.fixture_id
    assert session._world.result_for(final_fixture.fixture_id) is not None


def test_calendar_and_competition_pages_expose_dev_league_and_future_placeholders() -> None:
    session = DevelopmentSession()

    competitions = {name for name, _format, _status in session.competition_rows}
    calendar_competitions = {item.competition for item in session.calendar_rows}

    assert {"Premier League", "FA Cup", "Carabao Cup", "UEFA Champions League", "UEFA Europa League", "UEFA Conference League", "EFL Trophy"} <= competitions
    assert "Premier League" in calendar_competitions
    assert "UEFA Champions League" in calendar_competitions
    assert "Development Continental" not in calendar_competitions
    assert "Development Cup" not in calendar_competitions  # legacy inspector only
    assert "Carabao Cup" in calendar_competitions
    assert sum(item.competition == "Premier League" for item in session.calendar_rows) == 38
    assert not any("conditional" in item.status.lower() for item in session.calendar_rows)
    assert "Next match" in session.calendar_rows[0].status


def test_manual_formation_change_rebuilds_real_lineup_and_marks_custom() -> None:
    session = DevelopmentSession()

    updated = session.set_formation("dev-4-2-3-1")

    assert updated.formation_name == "4-2-3-1 Wide"
    assert updated.preset is TacticalPreset.CUSTOM
    assert session.home_lineup.formation.formation_id == "dev-4-2-3-1"
    assert len(session.home_lineup.starters) == 11
    assert {entry.slot_id for entry in session.home_lineup.starters} == set(session.home_lineup.formation.slot_ids)


def test_manual_role_change_uses_compatible_real_role_and_changes_context() -> None:
    session = DevelopmentSession()
    before = next(row for row in session.squad_rows() if row.slot == "ST")
    options = session.role_options_for_slot("st")
    alternative = next(option for option in options if option.role_id != "advanced_forward")

    session.set_role("st", alternative.role_id)
    after = next(row for row in session.squad_rows() if row.slot == "ST")

    assert session.home_tactic.preset_origin is TacticalPreset.CUSTOM
    assert session.home_tactic.role_for_slot("st").role_id == alternative.role_id
    assert after.role == alternative.name
    assert after.current != before.current


def test_manual_team_instruction_updates_real_tactic_and_familiarity() -> None:
    session = DevelopmentSession()
    familiarity_before = session.tactical_team_state().xi_familiarity
    pressing_before = session.tactical_view().pressing

    session.set_team_instruction("out_of_possession", "pressing_intensity", "very_high")

    assert session.home_tactic.team_instructions.out_of_possession.pressing_intensity.value == 100
    assert session.tactical_view().preset is TacticalPreset.CUSTOM
    assert session.tactical_view().pressing > pressing_before
    assert session.tactical_team_state().xi_familiarity < familiarity_before


def test_tactical_team_state_exposes_real_collective_inputs() -> None:
    session = DevelopmentSession()

    state = session.tactical_team_state()

    assert 0.0 <= state.xi_familiarity <= 100.0
    assert 0.0 <= state.squad_familiarity <= 100.0
    assert 0.0 <= state.xi_chemistry <= 100.0
    assert 0.0 <= state.xi_condition <= 100.0
    assert 0.0 <= state.xi_morale <= 100.0
    assert 0.0 <= state.squad_morale <= 100.0
    assert state.condition_below_75 == 0


def test_lineup_change_can_change_xi_chemistry_without_magic_ui_formula() -> None:
    session = DevelopmentSession()
    before = session.tactical_team_state().xi_chemistry
    rows = session.squad_rows()
    starter = next(row for row in rows if row.squad_status == "XI" and row.slot == "ST")
    bench = next(row for row in rows if row.squad_status == "BENCH" and row.position == "ST")

    session.swap_lineup(starter.player_id, bench.player_id)
    after = session.tactical_team_state().xi_chemistry

    assert after < before


def test_chemistry_input_is_applied_to_snapshot_current_rating() -> None:
    session = DevelopmentSession()
    starter_id = session.home_lineup.starters[0].player.id
    with_chemistry = session._build_snapshot().home_team.player(starter_id).current_rating

    session._home_chemistry[starter_id] = 20.0
    lower_chemistry = session._build_snapshot().home_team.player(starter_id).current_rating

    assert lower_chemistry < with_chemistry


def test_drag_board_slot_swap_allows_extreme_out_of_position_assignment() -> None:
    session = DevelopmentSession()
    before = {row.slot: row for row in session.squad_rows() if row.squad_status == "XI"}
    striker_id = before["ST"].player_id
    centre_back_id = before["RCB"].player_id
    striker_act_before = before["ST"].current
    familiarity_before = session.tactical_team_state().xi_familiarity

    session.swap_starting_slots("st", "rcb")

    after = {row.slot: row for row in session.squad_rows() if row.squad_status == "XI"}
    assert after["RCB"].player_id == striker_id
    assert after["ST"].player_id == centre_back_id
    assert after["RCB"].position == "ST"
    assert after["RCB"].role == "Central Defender"
    assert after["RCB"].current < striker_act_before
    assert session.tactical_team_state().xi_familiarity < familiarity_before

    # The Fast Simulator must accept the intentionally absurd assignment too.
    result = session.quick_simulate()
    assert isinstance(result, FastMatchResult)


def test_mirrored_position_swaps_do_not_collapse_act() -> None:
    session = DevelopmentSession()
    before = {row.player_id: row for row in session.squad_rows() if row.squad_status == "XI"}

    session.swap_starting_slots("rw", "lw")
    session.swap_starting_slots("rcm", "lcm")
    session.swap_starting_slots("rcb", "lcb")
    after = {row.player_id: row for row in session.squad_rows() if row.squad_status == "XI"}

    moved_ids = {
        session.home_lineup.player_for_slot(slot).id
        for slot in ("rw", "lw", "rcm", "lcm", "rcb", "lcb")
    }
    assert all(after[player_id].current >= before[player_id].current - 2.0 for player_id in moved_ids)


def test_outfielder_in_goal_is_an_emergency_keeper_not_a_normal_goalkeeper() -> None:
    session = DevelopmentSession()
    session.swap_starting_slots("gk", "st")

    home_profile, _ = session._simulator.profiles(session._build_snapshot())

    assert home_profile.goalkeeping < 45.0
