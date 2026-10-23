from __future__ import annotations

from dataclasses import dataclass, fields, replace
from datetime import date, datetime, timedelta, timezone
from enum import Enum
from functools import lru_cache
from random import Random
from typing import Callable, Iterable
from pathlib import Path

from football_manager.domain import (
    Club,
    CompetitionDefinition,
    CompetitionEdition,
    CompetitionFixture,
    CompetitionFormat,
    CompetitionScope,
    CompetitionStage,
    CompetitionStageKind,
    CompetitionStatus,
    CompetitionContextSnapshot,
    CurrentRatingContext,
    LeagueResult,
    KnockoutBracketRound,
    KnockoutLegFormat,
    KnockoutMatchResult,
    KnockoutRoundDefinition,
    StageRouteKind,
    StandingRouteRule,
    RoundRobinFixturePlan,
    QualificationKind,
    QualificationRule,
    QualificationSource,
    ScheduleSource,
    ScheduledFixture,
    ScheduledFixtureStatus,
    SeasonCalendar,
    WorldSeasonRunner,
    Foot,
    Formation,
    GoalkeepingAttributes,
    KitSnapshot,
    KitType,
    LineupEntry,
    MatchConditionsSnapshot,
    MatchContextSnapshot,
    MatchDecider,
    MatchKitSelectionSnapshot,
    MatchLineup,
    MentalAttributes,
    PhysicalAttributes,
    PitchCondition,
    Player,
    PlayerAttributes,
    PlayerIdentity,
    PlayerState,
    Position,
    PositionalFamiliarity,
    RefereeSnapshot,
    Squad,
    StadiumSnapshot,
    SurfaceType,
    TacticalFamiliarity,
    TacticalStyleAnalysis,
    TacticalPreset,
    TechnicalAttributes,
    Tactic,
    WeatherSnapshot,
    WeatherType,
    default_role_for_position,
    role_similarity,
    roles_for_position,
    advance_knockout_round,
    build_league_table,
    generate_knockout_round,
    knockout_context_for_fixture,
    merge_calendars,
    merge_stage_participants,
    resolve_knockout_round,
    seed_knockout_round,
    resolve_standing_stage_transition,
    standings_snapshots,
)
from football_manager.data import (
    SPECS_BY_KEY,
    build_fa_cup_2026_27,
    build_carabao_cup_2026_27,
    tier_strength,
    build_all_development_efl_2026_27,
    load_premier_league_2026_27,
    build_uefa_2026_27,
    build_efl_trophy_2026_27,
)
from football_manager.domain.calendar import reprogram_pending_fixtures_for_blackouts
from football_manager.data.premier_calendar import build_premier_calendar
from football_manager.domain.international_calendar import build_international_calendar
from football_manager.domain.career import WorldCareer
from football_manager.domain.season_cycle import SeasonReport, TIER_IDS, PLAYOFF_IDS
from football_manager.fast_simulation import FastMatchResult, FastMatchSimulator
from football_manager.services.match_result_contract import record_managed_match
from football_manager.services import build_match_snapshot, recover_player_between_matches, set_post_match_condition
from football_manager.services.managed_match_transaction import preserve_player_state
from football_manager.services.player_match_progression import apply_player_match_progression


@dataclass(frozen=True, slots=True)
class DevelopmentFixture:
    date_label: str
    competition: str
    opponent: str
    venue: str
    status: str
    outcome: str = ""


@dataclass(frozen=True, slots=True)
class OfficialCalendarViewRow:
    date_label: str
    matchweek: int
    home: str
    away: str
    kickoff: str
    source: str


@dataclass(frozen=True, slots=True)
class DevelopmentScheduledMatch:
    match_date: date
    competition_key: str
    competition_name: str
    stage_id: str
    round_label: str
    fixture: CompetitionFixture


@dataclass(frozen=True, slots=True)
class LeagueTableViewRow:
    position: int
    club: str
    played: int
    won: int
    drawn: int
    lost: int
    goals_for: int
    goals_against: int
    goal_difference: int
    points: int
    qualification: str


@dataclass(frozen=True, slots=True)
class LeagueFixtureViewRow:
    round_number: int
    home: str
    away: str
    status: str


@dataclass(frozen=True, slots=True)
class KnockoutTieViewRow:
    round_name: str
    tie_number: int
    leg_number: int
    home: str
    away: str
    score: str
    status: str


@dataclass(frozen=True, slots=True)
class SquadViewRow:
    player_id: str
    squad_status: str
    name: str
    position: str
    secondary_positions: str
    slot: str
    role: str
    role_fit: float
    assigned_familiarity: float
    overall: float
    current: float
    condition: float
    fatigue: float
    confidence: float
    form: float
    sharpness: float


@dataclass(frozen=True, slots=True)
class TacticalView:
    preset: TacticalPreset
    formation_name: str
    style_label: str
    possession: float
    pressing: float
    directness: float
    defensive_depth: float
    tempo: float
    width: float
    risk: float


@dataclass(frozen=True, slots=True)
class TacticalTeamStateView:
    xi_familiarity: float
    squad_familiarity: float
    xi_chemistry: float
    xi_condition: float
    condition_below_75: int
    condition_below_60: int
    xi_morale: float
    squad_morale: float


@dataclass(frozen=True, slots=True)
class TacticalInstructionFieldView:
    group: str
    field: str
    label: str
    value: str
    options: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class RoleOption:
    role_id: str
    name: str


@dataclass(frozen=True, slots=True)
class MatchSummary:
    scoreline: str
    competition: str
    stats_line: str
    possession_line: str
    discipline_line: str


class DevelopmentSession:
    """Small application service used only by the disposable Phase 6.0 UI.

    It intentionally sits between Tkinter and the real football domain. The UI
    reads view models and invokes methods here; it never contains simulation,
    rating, lineup or condition formulas.
    """

    def __init__(self, *, world_seed: int = 6606) -> None:
        # TS-24.9: independent reproducible fictional worlds for calibration.
        # Default stays identical for the game, migrations and older tests.
        if type(world_seed) is not int or not 1 <= world_seed <= 2_147_483_647:
            raise ValueError('world_seed must be a positive 32-bit integer')
        self._simulator = FastMatchSimulator()
        self._next_seed = 6003
        self.reset(world_seed=world_seed)

    def reset(self, *, world_seed: int | None = None) -> None:
        # An optional testing seed is passed along this call stack rather
        # than persisted as a new DevelopmentSession attribute. The save
        # contract validates the precise list of fields in this class.
        if world_seed is None:
            world_seed = self._world.seed if hasattr(self, '_world') else 6606
        if type(world_seed) is not int or not 1 <= world_seed <= 2_147_483_647:
            raise ValueError('world_seed must be a positive 32-bit integer')
        # Keep the simulator deterministic for a given snapshot, but do not make
        # every UI reset replay the exact same match.  The old fixed seed made
        # very different lineups repeatedly land on the same visible scoreline.
        from football_manager.domain.tactical_studio import TacticalStudioState
        self.tactical_studio = TacticalStudioState()
        from football_manager.services.match_preparation import empty_orders
        self.set_piece_orders = empty_orders()
        self._seed = self._next_seed
        self._next_seed += 1
        self.current_date = date(2026, 8, 15)
        self.home_club, self.home_lineup, self.home_tactic = _build_side(
            club_id="northbridge",
            name="Northbridge FC",
            short_name="NBR",
            base_offset=-2,  # TS-22: average opening XI, not a hidden difficulty modifier.
            tactic_preset=TacticalPreset.BALANCED,
            names=_HOME_NAMES,
        )
        self.away_club, self.away_lineup, self.away_tactic = _build_side(
            club_id="riverside",
            name="Riverside Athletic",
            short_name="RIV",
            base_offset=0,
            tactic_preset=TacticalPreset.COUNTER_ATTACK,
            names=_AWAY_NAMES,
        )
        self._initialize_familiarity(self.home_lineup, self.home_tactic, 82.0)
        self._initialize_familiarity(self.away_lineup, self.away_tactic, 78.0)
        self._initialize_development_league()
        self._initialize_development_cup()
        self._initialize_development_multistage()
        self._initialize_development_schedule()
        self._official_premier_schedule = load_premier_league_2026_27()
        self._efl_divisions = build_all_development_efl_2026_27()
        self._efl_results: dict[str, list[LeagueResult]] = {key: [] for key in self._efl_divisions}
        self._efl_current_round: dict[str, int] = {key: 1 for key in self._efl_divisions}
        self._initialize_world_runner(world_seed=world_seed)
        self._career = WorldCareer(self._world, self._world_club_names)
        self.dev_favorable_mode = False

        # TS-21.1: the next rival references its persistent canonical squad.
        self._prepare_development_opponent()

        # The disposable sandbox starts with one trained reference plan. Manual
        # edits are measured against it so tactical familiarity visibly falls
        # when the manager asks the same players to execute something different.
        self._home_reference_formation = self.home_lineup.formation
        self._home_reference_style = self.home_tactic.analyze_style()
        self._home_base_tactic_familiarity = {
            player.id: player.tactical_familiarity.tactic_score(self.home_tactic.tactic_id)
            for player in self.home_club.squad.players
        }
        self._away_reference_formation = self.away_lineup.formation
        self._away_reference_style = self.away_tactic.analyze_style()
        self._away_base_tactic_familiarity = {
            player.id: player.tactical_familiarity.tactic_score(self.away_tactic.tactic_id)
            for player in self.away_club.squad.players
        }

        # Phase 6.0 has no relationship graph yet. These are explicit sandbox
        # cohesion inputs, not a hidden UI bonus. They are passed into the real
        # ACT chemistry adjustment when MatchSnapshot is built.
        self._home_chemistry = _build_development_chemistry(self.home_club, starter_ids={entry.player.id for entry in self.home_lineup.starters})
        self._away_chemistry = {player.id: 65.0 for player in self.away_club.squad.players}
        self._sync_effective_tactic_familiarity(home=True)
        self._sync_effective_tactic_familiarity(home=False)

        self.last_result: FastMatchResult | None = None
        self._last_played_match_metadata = ""
        self.match_played = False
        from football_manager.services.dressing_room import create_dressing_room
        self.dressing_room = create_dressing_room(self.home_club.id, self.home_club.squad.players, self.current_date)
        from football_manager.services.manager_inbox import create_manager_inbox
        self.manager_inbox = create_manager_inbox(self)

    def update_dressing_room(self) -> None:
        """Advance with the career clock; not called by UI getters/lineup edits."""
        from football_manager.services.dressing_room import advance_dressing_room, create_dressing_room
        # The legacy results-only import can move its clock backwards without
        # restoring player history. Start a neutral social baseline in that case.
        if self.current_date < self.dressing_room.last_updated:
            self.dressing_room = create_dressing_room(self.home_club.id, self.home_club.squad.players, self.current_date)
        else:
            advance_dressing_room(self.dressing_room, self.home_club.squad.players, self.current_date)

    @property
    def tactical_presets(self) -> tuple[TacticalPreset, ...]:
        return tuple(preset for preset in TacticalPreset if preset is not TacticalPreset.CUSTOM)

    @property
    def available_formations(self) -> tuple[tuple[str, str], ...]:
        return tuple((formation.formation_id, formation.name) for formation in _development_formations())

    @property
    def calendar_rows(self) -> tuple[DevelopmentFixture, ...]:
        rows: list[tuple[date, DevelopmentFixture]] = []
        active_id = self._active_match.fixture.fixture_id if self._active_match is not None else None
        for scheduled in self._season_calendar.fixtures_for_club(self.home_club.id):
            item = self._managed_schedule[scheduled.fixture_id]
            managed_home = item.fixture.home_club_id == self.home_club.id
            opponent_id = (
                item.fixture.away_club_id if managed_home else item.fixture.home_club_id
            )
            status = self._fixture_result_label(item)
            result_outcome = self._fixture_outcome(item)
            if status is None:
                status = (
                    "Next match"
                    if item.fixture.fixture_id == active_id and not self.match_played
                    else "Scheduled"
                )
            rows.append(
                (
                    item.match_date,
                    DevelopmentFixture(
                        item.match_date.strftime("%d %b %Y"),
                        item.competition_name,
                        self._world_club_names.get(opponent_id, opponent_id),
                        "H" if managed_home else "A",
                        f"{item.round_label} | {status}",
                        result_outcome,
                    ),
                )
            )

        # Only fixtures produced by sporting progression enter this calendar.
        # A dated, fixed "TBD if qualified" row is NOT a real fixture; it used
        # to survive a reprogrammed tie and duplicate semifinal legs.
        rows.sort(key=lambda item: (item[0], item[1].competition, item[1].opponent))
        return tuple(item for _date, item in rows)

    @property
    def official_calendar_summary(self) -> str:
        bundle = self._official_premier_schedule
        return (
            f"Official {bundle.metadata.competition_name} {bundle.metadata.season_label} release | "
            f"{len(bundle.calendar.fixtures)} fixtures | 20 clubs | "
            f"published {bundle.metadata.published_date:%d %b %Y} | "
            f"snapshot {bundle.metadata.snapshot_date:%d %b %Y}. "
            "Data inspector only: real clubs are not yet the managed sandbox world."
        )

    @property
    def official_calendar_rows(self) -> tuple[OfficialCalendarViewRow, ...]:
        bundle = self._official_premier_schedule
        rows: list[OfficialCalendarViewRow] = []
        for fixture in sorted(
            bundle.calendar.fixtures,
            key=lambda item: (item.kickoff, item.fixture_id),
        ):
            assert fixture.kickoff is not None
            rows.append(
                OfficialCalendarViewRow(
                    date_label=fixture.kickoff.strftime("%d %b %Y"),
                    matchweek=int(fixture.round_number or 0),
                    home=bundle.club_names[fixture.home_club_id],
                    away=bundle.club_names[fixture.away_club_id],
                    kickoff=(
                        fixture.kickoff.strftime("%H:%M ")
                        + ("BST" if fixture.kickoff.utcoffset() == timedelta(hours=1) else "GMT")
                    ),
                    source=fixture.source.value.upper(),
                )
            )
        return tuple(rows)

    @property
    def efl_division_options(self) -> tuple[tuple[str, str], ...]:
        return tuple((key, SPECS_BY_KEY[key].name) for key in self._efl_divisions)

    def _efl_division(self, key: str):
        if key not in self._efl_divisions:
            raise ValueError(f"unknown DEV division: {key}")
        return self._efl_divisions[key]

    def efl_calendar_summary(self, key: str) -> str:
        division = self._efl_division(key)
        return (
            f"{division.spec.name} {self._world.season_label} | 24 fictional clubs | 46 rounds | "
            f"552 GENERATED pairings. "
            + ("Published 2026/27 date slots (not official matchups). "
               if self._world.season_label == "2026/27" else "Future fixture windows GENERATED by policy. ")
            + f"Source: {division.slot_source_url}"
        )

    def efl_calendar_rows(self, key: str) -> tuple[OfficialCalendarViewRow, ...]:
        division = self._efl_division(key)
        return tuple(
            OfficialCalendarViewRow(
                date_label=item.kickoff.strftime("%d %b %Y"),
                matchweek=int(item.round_number or 0),
                home=division.club_names[item.home_club_id],
                away=division.club_names[item.away_club_id],
                kickoff=item.kickoff.strftime("%H:%M UTC"),
                source="DEV (EFL slot)",
            )
            for item in division.calendar.fixtures
        )

    def efl_league_summary(self, key: str) -> str:
        division = self._efl_division(key)
        completed = len(self._efl_results[key])
        strengths = division.strengths.values()
        return (
            f"{division.spec.name} DEV | 24 fictional clubs | 46 rounds / 552 fixtures | "
            f"{completed} results | team strength {min(strengths)}-{max(strengths)}. "
            + ("Published 2026/27 EFL dates" if self._world.season_label == "2026/27"
             else "Future GENERATED date windows") + ", GENERATED opponent pairings; results DEV only."
        )

    def efl_current_round(self, key: str) -> int:
        self._efl_division(key)
        return self._efl_current_round[key]

    def efl_table_rows(self, key: str) -> tuple[LeagueTableViewRow, ...]:
        division = self._efl_division(key)
        rows = build_league_table(
            participant_club_ids=division.edition.participant_club_ids,
            fixtures=division.edition.fixtures,
            results=self._efl_results[key],
        )
        return tuple(LeagueTableViewRow(
            position=row.position,
            club=division.club_names[row.club_id],
            played=row.played, won=row.won, drawn=row.drawn, lost=row.lost,
            goals_for=row.goals_for, goals_against=row.goals_against,
            goal_difference=row.goal_difference, points=row.points,
            qualification=f"DEV STR {division.strengths[row.club_id]}",
        ) for row in rows)

    def efl_fixture_rows(self, key: str, round_number: int) -> tuple[LeagueFixtureViewRow, ...]:
        division = self._efl_division(key)
        if not 1 <= round_number <= 46:
            raise ValueError("EFL round_number must be 1..46")
        return tuple(LeagueFixtureViewRow(
            round_number=round_number,
            home=division.club_names[item.home_club_id],
            away=division.club_names[item.away_club_id],
            status=f"{item.kickoff:%d %b %H:%M} UTC | {item.status.value.title()}",
        ) for item in division.calendar.fixtures
            if item.round_number == round_number)

    def simulate_next_efl_round(self, key: str) -> int:
        """Manual DEV inspector shortcut backed by the same persistent runner."""
        division = self._efl_division(key)
        number = self._efl_current_round[key]
        if number > 46:
            raise RuntimeError(f"{division.spec.name} DEV season already complete")
        for fixture in division.edition.fixtures:
            if fixture.round_number == number and self._world.result_for(fixture.fixture_id) is None:
                self._world.simulate_fixture(fixture.fixture_id)
        self._sync_world_view()
        return number

    @property
    def competition_rows(self) -> tuple[tuple[str, str, str], ...]:
        return (
            (
                "Premier League",
                "Round-robin league",
                f"DEV world {self._world.season_label} | {len(self._league_club_names)} clubs | "
                f"{2*(len(self._league_club_names)-1)} rounds | {len(self._league_edition.fixtures)} fixtures",
            ),
            (
                "Premier League 2026/27 official data",
                "Round-robin + calendar",
                "Phase 6.5 | official published fixture dataset | 380 fixtures | 20 real club IDs",
            ),
            *tuple((
                spec.name + " (DEV)",
                "24-team double round-robin",
                "Phase 6.5a | 46 rounds / 552 fictional fixtures on EFL 2026/27 date slots",
            ) for spec in SPECS_BY_KEY.values()),
            (
                "Development Cup",
                "Knockout",
                "Legacy knockout inspector only; no longer occupies English season calendar",
            ),
            ("Development Continental", "Multi-stage", "Legacy 8-club inspector (not the managed world)"),
            ("FA Cup", "Knockout", f"{self._world.season_label} | GENERATED fictional draws | {len(self._world.cups['fa-cup'].plans)} rounds"),
            ("Carabao Cup", "Knockout", f"{self._world.season_label} | GENERATED fictional draws | {len(self._world.cups['carabao-cup'].plans)} rounds"),
            *tuple((comp.name, "Multi-stage" if comp.kind == "uefa" else "Groups + knockout",
                    f"{self._world.season_label} round windows | GENERATED fictitious pairings | {len(comp.participants)} clubs")
                   for comp in self._world.staged.values()),
        )

    @property
    def league_summary(self) -> str:
        return (
            f"Development league: {len(self._league_club_names)} clubs | "
            f"{2*(len(self._league_club_names)-1)} rounds | {len(self._league_edition.fixtures)} fixtures | "
            f"{len(self._league_results)} result(s) recorded. "
            "Qualification labels are sandbox data, not real-season allocations."
        )

    def league_table_rows(self) -> tuple[LeagueTableViewRow, ...]:
        standings = self._league_standings()
        rows: list[LeagueTableViewRow] = []
        for row in standings:
            rules = self._league_edition.qualification_rules_for_position(row.position)
            labels = ", ".join(rule.label for rule in rules) or "-"
            rows.append(
                LeagueTableViewRow(
                    position=row.position,
                    club=self._league_club_names[row.club_id],
                    played=row.played,
                    won=row.won,
                    drawn=row.drawn,
                    lost=row.lost,
                    goals_for=row.goals_for,
                    goals_against=row.goals_against,
                    goal_difference=row.goal_difference,
                    points=row.points,
                    qualification=labels,
                )
            )
        return tuple(rows)

    def league_fixture_rows(self, round_number: int = 1) -> tuple[LeagueFixtureViewRow, ...]:
        result_ids = {result.fixture_id for result in self._league_results}
        fixtures = (
            fixture
            for fixture in self._league_edition.fixtures
            if fixture.round_number == round_number
        )
        return tuple(
            LeagueFixtureViewRow(
                round_number=round_number,
                home=self._league_club_names[fixture.home_club_id],
                away=self._league_club_names[fixture.away_club_id],
                status="Played" if fixture.fixture_id in result_ids else "Scheduled (sporting)",
            )
            for fixture in fixtures
        )

    @property
    def cup_summary(self) -> str:
        latest = self._cup_rounds[-1]
        complete = latest.outcome is not None and latest.outcome.complete and len(latest.outcome.winner_club_ids) == 1
        status = "Completed" if complete else f"Current: {latest.definition.name}"
        return (
            "Legacy Development Cup inspector (not scheduled): 8 clubs | "
            f"QF single-leg | SF two-legged | Final single-leg | {status}."
        )

    @property
    def can_simulate_cup_round(self) -> bool:
        latest = self._cup_rounds[-1]
        if latest.outcome is not None:
            return False
        result_ids = {result.fixture_id for result in self._cup_results}
        return True  # Legacy 8-club inspector is no longer in the managed calendar.

    def cup_bracket_rows(self) -> tuple[KnockoutTieViewRow, ...]:
        result_by_fixture = {result.fixture_id: result for result in self._cup_results}
        rows: list[KnockoutTieViewRow] = []
        for bracket_round in self._cup_rounds:
            outcome_by_tie = (
                {tie.tie_id: tie for tie in bracket_round.outcome.ties}
                if bracket_round.outcome is not None
                else {}
            )
            for tie_number, tie in enumerate(bracket_round.plan.ties, start=1):
                tie_outcome = outcome_by_tie.get(tie.tie_id)
                for fixture in tie.fixtures:
                    result = result_by_fixture.get(fixture.fixture_id)
                    score = "-"
                    if result is not None:
                        score = f"{result.home_goals}-{result.away_goals}"
                        if result.decided_by_penalties:
                            score += f" ({result.penalties_home}-{result.penalties_away} pens)"
                    if result is None:
                        status = "Scheduled (sporting)"
                    elif tie_outcome is not None and tie_outcome.complete:
                        winner = self._cup_club_names[tie_outcome.winner_club_id or ""]
                        status = f"Winner: {winner}"
                    else:
                        status = "Leg played"
                    rows.append(
                        KnockoutTieViewRow(
                            round_name=bracket_round.definition.name,
                            tie_number=tie_number,
                            leg_number=fixture.leg_number,
                            home=self._cup_club_names[fixture.home_club_id],
                            away=self._cup_club_names[fixture.away_club_id],
                            score=score,
                            status=status,
                        )
                    )
        return tuple(rows)

    @property
    def continental_summary(self) -> str:
        standings = self._continental_standings()
        completed_league = len(self._continental_league_results) == len(self._continental_edition.fixtures)
        if not completed_league:
            played_rounds = max((row.played for row in standings), default=0)
            return (
                "Development Continental: 8 clubs | 7-match league phase | "
                f"MD {played_rounds}/7 | top 2 direct SF | 3-6 playoff | 7-8 out"
            )
        if self._continental_rounds:
            latest = self._continental_rounds[-1]
            complete = latest.outcome is not None and latest.outcome.complete
            if complete and len(latest.outcome.winner_club_ids) == 1:
                champion = self._continental_club_names[latest.outcome.winner_club_ids[0]]
                return f"Development Continental: completed | Champion: {champion}"
            return f"Development Continental: knockout stage | Current: {latest.definition.name}"
        return "Development Continental: league phase completed; transition pending"

    def continental_table_rows(self) -> tuple[LeagueTableViewRow, ...]:
        standings = self._continental_standings()
        rows: list[LeagueTableViewRow] = []
        for row in standings:
            route_label = "-"
            for rule in self._continental_routes:
                if row.position in rule.positions:
                    route_label = rule.label
                    break
            rows.append(
                LeagueTableViewRow(
                    position=row.position,
                    club=self._continental_club_names[row.club_id],
                    played=row.played,
                    won=row.won,
                    drawn=row.drawn,
                    lost=row.lost,
                    goals_for=row.goals_for,
                    goals_against=row.goals_against,
                    goal_difference=row.goal_difference,
                    points=row.points,
                    qualification=route_label,
                )
            )
        return tuple(rows)

    def continental_bracket_rows(self) -> tuple[KnockoutTieViewRow, ...]:
        result_by_fixture = {
            result.fixture_id: result for result in self._continental_knockout_results
        }
        rows: list[KnockoutTieViewRow] = []
        for bracket_round in self._continental_rounds:
            outcome_by_tie = (
                {tie.tie_id: tie for tie in bracket_round.outcome.ties}
                if bracket_round.outcome is not None
                else {}
            )
            for tie_number, tie in enumerate(bracket_round.plan.ties, start=1):
                tie_outcome = outcome_by_tie.get(tie.tie_id)
                for fixture in tie.fixtures:
                    result = result_by_fixture.get(fixture.fixture_id)
                    score = "-"
                    if result is not None:
                        score = f"{result.home_goals}-{result.away_goals}"
                        if result.decided_by_penalties:
                            score += f" ({result.penalties_home}-{result.penalties_away} pens)"
                    if result is None:
                        status = "Scheduled"
                    elif tie_outcome is not None and tie_outcome.complete:
                        winner = self._continental_club_names[tie_outcome.winner_club_id or ""]
                        status = f"Winner: {winner}"
                    else:
                        status = "Leg played"
                    rows.append(
                        KnockoutTieViewRow(
                            round_name=bracket_round.definition.name,
                            tie_number=tie_number,
                            leg_number=fixture.leg_number,
                            home=self._continental_club_names[fixture.home_club_id],
                            away=self._continental_club_names[fixture.away_club_id],
                            score=score,
                            status=status,
                        )
                    )
        return tuple(rows)

    def simulate_dev_cup_round(self) -> None:
        if not self.can_simulate_cup_round:
            raise RuntimeError("The development cup is already complete.")
        bracket_round = self._cup_rounds[-1]
        new_results: list[KnockoutMatchResult] = []
        for tie in bracket_round.plan.ties:
            tie_results: list[KnockoutMatchResult] = []
            for fixture in tie.fixtures:
                rng = Random(f"dev-cup:{self._seed}:{fixture.fixture_id}")
                home_goals = self._sample_dev_goals(rng, 1.35)
                away_goals = self._sample_dev_goals(rng, 1.15)
                is_deciding_leg = fixture.leg_number == bracket_round.definition.leg_count
                penalties_home = penalties_away = 0
                candidate = KnockoutMatchResult(
                    fixture.fixture_id, home_goals, away_goals
                )
                projected = [*tie_results, candidate]
                if is_deciding_leg:
                    interim = resolve_knockout_round(
                        bracket_round.plan,
                        [*self._results_for_other_ties(bracket_round.plan, tie.tie_id), *projected],
                    )
                    tie_outcome = next(item for item in interim.ties if item.tie_id == tie.tie_id)
                    if not tie_outcome.complete:
                        if rng.random() < 0.5:
                            penalties_home, penalties_away = 5, 4
                        else:
                            penalties_home, penalties_away = 4, 5
                        candidate = KnockoutMatchResult(
                            fixture.fixture_id,
                            home_goals,
                            away_goals,
                            penalties_home,
                            penalties_away,
                        )
                        projected[-1] = candidate
                tie_results.append(candidate)
            new_results.extend(tie_results)

        self._cup_results.extend(new_results)
        outcome = resolve_knockout_round(
            bracket_round.plan, tuple(self._results_for_plan(bracket_round.plan))
        )
        self._cup_rounds[-1] = KnockoutBracketRound(
            definition=bracket_round.definition,
            plan=bracket_round.plan,
            outcome=outcome,
        )
        if len(outcome.winner_club_ids) == 1:
            return
        next_index = len(self._cup_rounds)
        next_definition = self._cup_round_definitions[next_index]
        next_plan = advance_knockout_round(
            outcome,
            edition_id=self._cup_edition.edition_id,
            stage_id="knockout",
            next_definition=next_definition,
            seed=self._seed + next_index,
        )
        self._cup_rounds.append(
            KnockoutBracketRound(
                definition=next_definition,
                plan=next_plan,
            )
        )
        # This legacy inspector is intentionally not attached to the 2026/27
        # managed fixture list. Real FA Cup / Carabao Cup are scheduled by world.

    def _results_for_plan(self, plan) -> list[KnockoutMatchResult]:
        fixture_ids = {fixture.fixture_id for fixture in plan.fixtures}
        return [result for result in self._cup_results if result.fixture_id in fixture_ids]

    def _results_for_other_ties(self, plan, tie_id: str) -> list[KnockoutMatchResult]:
        fixture_ids = {
            fixture.fixture_id
            for tie in plan.ties
            if tie.tie_id != tie_id
            for fixture in tie.fixtures
        }
        return [result for result in self._cup_results if result.fixture_id in fixture_ids]

    @property
    def current_league_round(self) -> int:
        if self._active_match is not None and self._active_match.competition_key == "league":
            return self._active_match.fixture.round_number or 1
        unplayed = [
            item
            for item in self._managed_schedule.values()
            if item.competition_key == "league" and not self._fixture_has_result(item)
        ]
        if unplayed:
            return min(item.fixture.round_number or 1 for item in unplayed)
        return 2*(len(self._league_edition.participant_club_ids)-1)

    @property
    def managed_is_home(self) -> bool:
        return self._active_match.fixture.home_club_id == self.home_club.id

    @property
    def next_match_label(self) -> str:
        if self._active_match is None:
            return f"Season {self._world.season_label} complete"
        actual_home, actual_away = self._actual_match_sides()
        return f"{actual_home.name} vs {actual_away.name}"

    @property
    def next_match_meta(self) -> str:
        if self._active_match is None:
            return "No remaining managed fixture; start next season when all results are recorded"
        venue = "Home" if self.managed_is_home else "Away"
        item = self._active_match
        scheduled = self._world.fixtures.get(item.fixture.fixture_id)
        kickoff = scheduled.kickoff if scheduled else None
        kickoff_label = (
            kickoff.astimezone(timezone.utc).strftime("%H:%M UTC")
            if kickoff is not None else "Time TBC"
        )
        return (
            f"{item.competition_name} DEV | {item.round_label} | "
            f"{item.match_date:%d %b %Y} | {kickoff_label} | {venue}"
        )

    @property
    def can_quick_sim(self) -> bool:
        return (
            self._active_match is not None
            and not self.match_played
            and not self._fixture_has_result(self._active_match)
        )

    @property
    def can_continue(self) -> bool:
        if not self.match_played:
            return False
        return self._next_unplayed_managed_match() is not None

    def squad_rows(self) -> tuple[SquadViewRow, ...]:
        starters_by_id = {entry.player.id: entry for entry in self.home_lineup.starters}
        rows: list[SquadViewRow] = []
        for player in self.home_club.squad.players:
            entry = starters_by_id.get(player.id)
            secondary = "/".join(position.value for position in player.secondary_positions) or "-"
            if entry is None:
                rating = player.current_rating()
                rows.append(
                    SquadViewRow(
                        player_id=player.id,
                        squad_status="BENCH",
                        name=player.full_name,
                        position=player.primary_position.value,
                        secondary_positions=secondary,
                        slot="-",
                        role="-",
                        role_fit=rating.overall_component("attribute_fit"),
                        assigned_familiarity=player.familiarity_for(player.primary_position),
                        overall=rating.overall,
                        current=rating.current,
                        condition=player.state.condition,
                        fatigue=player.state.fatigue,
                        confidence=player.state.confidence,
                        form=player.state.form,
                        sharpness=player.state.match_sharpness,
                    )
                )
                continue

            slot_position = self.home_lineup.formation.slot(entry.slot_id).position
            role = self.home_tactic.role_for_slot(entry.slot_id)
            rating = player.current_rating(
                CurrentRatingContext(
                    assigned_position=slot_position,
                    role_id=role.role_id,
                    tactic_id=self.home_tactic.tactic_id,
                    chemistry=self._home_chemistry.get(player.id, 65.0),
                )
            )
            rows.append(
                SquadViewRow(
                    player_id=player.id,
                    squad_status="XI",
                    name=player.full_name,
                    position=player.primary_position.value,
                    secondary_positions=secondary,
                    slot=entry.slot_id.upper(),
                    role=role.name,
                    role_fit=rating.overall_component("attribute_fit"),
                    assigned_familiarity=player.familiarity_for(slot_position),
                    overall=rating.overall,
                    current=rating.current,
                    condition=player.state.condition,
                    fatigue=player.state.fatigue,
                    confidence=player.state.confidence,
                    form=player.state.form,
                    sharpness=player.state.match_sharpness,
                )
            )
        return tuple(rows)

    def tactical_view(self) -> TacticalView:
        style = self.home_tactic.analyze_style()
        return TacticalView(
            preset=self.home_tactic.preset_origin,
            formation_name=self.home_tactic.formation.name,
            style_label=style.label,
            possession=style.possession,
            pressing=style.pressing,
            directness=style.directness,
            defensive_depth=style.defensive_depth,
            tempo=style.tempo,
            width=style.width,
            risk=style.risk,
        )

    def tactical_team_state(self) -> TacticalTeamStateView:
        starters_by_id = {entry.player.id: entry for entry in self.home_lineup.starters}

        xi_execution: list[float] = []
        squad_execution: list[float] = []
        xi_condition: list[float] = []
        xi_morale: list[float] = []
        squad_morale: list[float] = []

        for player in self.home_club.squad.players:
            entry = starters_by_id.get(player.id)
            if entry is None:
                position = player.primary_position
                role = default_role_for_position(position)
            else:
                position = self.home_lineup.formation.slot(entry.slot_id).position
                role = self.home_tactic.role_for_slot(entry.slot_id)

            execution = (
                0.25 * player.familiarity_for(position)
                + 0.30 * player.tactical_familiarity.role_score(role.role_id)
                + 0.45 * player.tactical_familiarity.tactic_score(self.home_tactic.tactic_id)
            )
            squad_execution.append(execution)
            squad_morale.append(player.state.effective_morale)
            if entry is not None:
                xi_execution.append(execution)
                xi_condition.append(player.state.condition)
                xi_morale.append(player.state.effective_morale)

        xi_chemistry = [
            self._home_chemistry.get(entry.player.id, 65.0)
            for entry in self.home_lineup.starters
        ]
        return TacticalTeamStateView(
            xi_familiarity=_mean_values(xi_execution),
            squad_familiarity=_mean_values(squad_execution),
            xi_chemistry=_mean_values(xi_chemistry),
            xi_condition=_mean_values(xi_condition),
            condition_below_75=sum(value < 75.0 for value in xi_condition),
            condition_below_60=sum(value < 60.0 for value in xi_condition),
            xi_morale=_mean_values(xi_morale),
            squad_morale=_mean_values(squad_morale),
        )

    def tactical_instruction_fields(self) -> tuple[TacticalInstructionFieldView, ...]:
        rows: list[TacticalInstructionFieldView] = []
        for group in ("in_possession", "transition", "out_of_possession", "game_management"):
            instruction_group = getattr(self.home_tactic.team_instructions, group)
            for item in fields(instruction_group):
                value = getattr(instruction_group, item.name)
                options = _instruction_options(value)
                if not options:
                    continue
                rows.append(
                    TacticalInstructionFieldView(
                        group=group,
                        field=item.name,
                        label=item.name.replace("_", " ").title(),
                        value=_instruction_display_value(value),
                        options=options,
                    )
                )
        return tuple(rows)

    def role_options_for_slot(self, slot_id: str) -> tuple[RoleOption, ...]:
        position = self.home_lineup.formation.slot(slot_id).position
        return tuple(RoleOption(role.role_id, role.name) for role in roles_for_position(position))

    def set_formation(self, formation_id: str) -> TacticalView:
        formation = next(
            (item for item in _development_formations() if item.formation_id == formation_id),
            None,
        )
        if formation is None:
            raise ValueError(f"unknown development formation: {formation_id}")
        if formation == self.home_lineup.formation:
            return self.tactical_view()

        previous_instructions = self.home_tactic.team_instructions
        previous_id = self.home_tactic.tactic_id
        self.home_lineup = _reassign_lineup_to_formation(self.home_lineup, formation)
        self.home_tactic = Tactic.from_preset(
            tactic_id=previous_id,
            name=f"Northbridge Custom {formation.name}",
            formation=formation,
            preset=TacticalPreset.CUSTOM,
        )
        # Changing shape should not silently throw away the manager's team plan.
        self.home_tactic.team_instructions = previous_instructions
        self._sync_effective_tactic_familiarity(home=True)
        return self.tactical_view()

    def set_tactical_preset(self, preset: TacticalPreset | str) -> TacticalView:
        preset = preset if isinstance(preset, TacticalPreset) else TacticalPreset(preset)
        if preset is TacticalPreset.CUSTOM:
            raise ValueError("CUSTOM is created by manual edits; choose a concrete preset to apply")

        previous_id = self.home_tactic.tactic_id
        previous_shapes = self.home_tactic.phase_shapes
        self.home_tactic = Tactic.from_preset(
            tactic_id=previous_id,
            name=f"Northbridge {preset.value.replace('_', ' ').title()}",
            formation=self.home_lineup.formation,
            preset=preset,
        )
        # Style presets replace instructions/roles, not manual phase targets.
        self.home_tactic.phase_shapes = previous_shapes
        self._sync_effective_tactic_familiarity(home=True)
        return self.tactical_view()

    def set_role(self, slot_id: str, role_id: str) -> TacticalView:
        self.home_tactic.set_role(slot_id, role_id)
        self.home_tactic.preset_origin = TacticalPreset.CUSTOM
        return self.tactical_view()

    def set_team_instruction(self, group: str, field_name: str, raw_value: str) -> TacticalView:
        if group not in {"in_possession", "transition", "out_of_possession", "game_management"}:
            raise ValueError(f"unknown tactical instruction group: {group}")
        instruction_group = getattr(self.home_tactic.team_instructions, group)
        if field_name not in {item.name for item in fields(instruction_group)}:
            raise ValueError(f"unknown tactical instruction: {group}.{field_name}")
        current = getattr(instruction_group, field_name)
        parsed = _parse_instruction_value(current, raw_value)
        updater = {
            "in_possession": self.home_tactic.update_in_possession,
            "transition": self.home_tactic.update_transition,
            "out_of_possession": self.home_tactic.update_out_of_possession,
            "game_management": self.home_tactic.update_game_management,
        }[group]
        updater(**{field_name: parsed})
        self.home_tactic.preset_origin = TacticalPreset.CUSTOM
        self._sync_effective_tactic_familiarity(home=True)
        return self.tactical_view()

    def swap_starting_slots(self, first_slot_id: str, second_slot_id: str) -> None:
        """Swap the players assigned to two starting-XI tactical slots.

        Slots, positions and roles belong to the tactical shape; only the players
        move.  The development sandbox intentionally allows any starter to be
        assigned anywhere so extreme out-of-position cases can be inspected.
        """

        first_slot_id = first_slot_id.strip().lower()
        second_slot_id = second_slot_id.strip().lower()
        if first_slot_id == second_slot_id:
            return

        self.home_lineup.formation.slot(first_slot_id)
        self.home_lineup.formation.slot(second_slot_id)
        starters = list(self.home_lineup.starters)
        first_index = next(
            (i for i, entry in enumerate(starters) if entry.slot_id == first_slot_id),
            None,
        )
        second_index = next(
            (i for i, entry in enumerate(starters) if entry.slot_id == second_slot_id),
            None,
        )
        if first_index is None or second_index is None:
            raise ValueError("both slots must belong to the current starting XI")

        first = starters[first_index]
        second = starters[second_index]
        starters[first_index] = LineupEntry(first.slot_id, second.player)
        starters[second_index] = LineupEntry(second.slot_id, first.player)
        self.home_lineup = MatchLineup(
            club_id=self.home_lineup.club_id,
            formation=self.home_lineup.formation,
            starters=tuple(starters),
            bench=self.home_lineup.bench,
        )
        self._sync_effective_tactic_familiarity(home=True)

    def swap_lineup(self, starter_player_id: str, bench_player_id: str) -> None:
        starter_index = next(
            (i for i, entry in enumerate(self.home_lineup.starters) if entry.player.id == starter_player_id),
            None,
        )
        bench_index = next(
            (i for i, player in enumerate(self.home_lineup.bench) if player.id == bench_player_id),
            None,
        )
        if starter_index is None:
            raise ValueError("select a player currently in the starting XI")
        if bench_index is None:
            raise ValueError("select a player currently on the bench")

        starters = list(self.home_lineup.starters)
        bench = list(self.home_lineup.bench)
        outgoing = starters[starter_index]
        incoming = bench[bench_index]
        starters[starter_index] = LineupEntry(outgoing.slot_id, incoming)
        bench[bench_index] = outgoing.player
        self.home_lineup = MatchLineup(
            club_id=self.home_lineup.club_id,
            formation=self.home_lineup.formation,
            starters=tuple(starters),
            bench=tuple(bench),
        )
        self._sync_effective_tactic_familiarity(home=True)

    def quick_simulate(self, *, delegate_team: bool = True) -> FastMatchResult:
        if self.match_played or (self._active_match is not None and self._fixture_has_result(self._active_match)):
            raise RuntimeError(
                "The current development fixture is already played. Continue to the next match."
            )
        if self._active_match is None:
            raise RuntimeError("The development season has no remaining managed fixtures.")
        social_eligibility = {p.id: p.state.is_available and p.state.condition >= 40
                              for p in self.home_club.squad.players}
        snapshot = self._build_snapshot()
        from football_manager.services.tactical_studio import prepared_match_plans
        plans = prepared_match_plans(self)
        from football_manager.fast_simulation.ai_coaching import coach_for_match
        opponent = snapshot.away_team if snapshot.home_team.club_id == self.home_club.id else snapshot.home_team
        coaches = {opponent.club_id: coach_for_match(
            self._world.seed, opponent.club_id, opponent.tactic.preset_origin.value,
            self._active_match.fixture.fixture_id)}
        if delegate_team:
            managed = snapshot.home_team if snapshot.home_team.club_id == self.home_club.id else snapshot.away_team
            coaches[managed.club_id] = coach_for_match(self._world.seed, managed.club_id,
                managed.tactic.preset_origin.value, self._active_match.fixture.fixture_id)
        result = self._simulator.simulate(snapshot, tactical_plans=plans, ai_coaches=coaches)
        # These projections are updated by _sync_world_view() after the world
        # ledger is committed. A failure during that projection must not leave
        # players or views ahead of the durable world result.
        view_state = {
            name: getattr(self, name) for name in (
                "_league_results", "_season_calendar", "_managed_schedule",
                "last_result", "_last_played_match_metadata", "match_played", "_seed",
            )
        }
        from copy import deepcopy
        view_state['dressing_room'] = deepcopy(self.dressing_room)
        view_state.update(
            _home_base_tactic_familiarity=dict(self._home_base_tactic_familiarity),
            _away_base_tactic_familiarity=dict(self._away_base_tactic_familiarity),
            _efl_divisions=dict(self._efl_divisions),
            _efl_results=dict(self._efl_results),
            _efl_current_round=dict(self._efl_current_round),
        )
        try:
            with self._world.transaction(), preserve_player_state((self.home_club, self.away_club)):
                self._persist_post_match_state(result, self.home_club)
                self._persist_post_match_state(result, self.away_club)
                self._persist_position_experience(result, self.home_lineup, self.home_club)
                self._persist_position_experience(result, self.away_lineup, self.away_club)
                self._persist_match_progression(result, self.home_lineup, self.home_tactic,
                                                self.home_club, home=True)
                self._persist_match_progression(result, self.away_lineup, self.away_tactic,
                                                self.away_club, home=False)
                self._apply_managed_result_morale(result)
                from football_manager.services.world_matches import result_morale, record_world_usage
                result_morale(result, self.away_club, self.away_lineup)
                self._record_active_match_result(result)
                record_world_usage(self._world, self._active_match.fixture.fixture_id,
                                   result, (self.home_lineup, self.away_lineup))
                from football_manager.services.dressing_room import record_session_match
                record_session_match(self, result, social_eligibility)
                self.last_result = result
                self._last_played_match_metadata = (
                    f"Development Sandbox - {self._active_match.competition_name} | "
                    f"{self._active_match.round_label}"
                )
                self.match_played = True
                self._seed += 1
        except BaseException:
            for name, old_value in view_state.items():
                setattr(self, name, old_value)
            raise
        return result

    def continue_to_next_match(self) -> None:
        """Run background world results up to (but not through) the next user fixture."""
        if not self.match_played:
            raise RuntimeError("Simulate the current match before continuing.")
        next_known = self._next_unplayed_managed_match()
        cutoff = next_known.match_date if next_known is not None else date(int(self._world.season_label[:4])+1, 6, 30)
        self._world.advance_until(cutoff, protected_club_id=self.home_club.id)
        self._sync_world_view()
        next_match = self._next_unplayed_managed_match()
        if next_match is None:
            self._active_match = None
            self.current_date = cutoff
            self.update_dressing_room()
            self.match_played = False
            raise RuntimeError("The development season has no remaining managed fixtures.")
        recovery_days = max(0, (next_match.match_date - self.current_date).days)
        from football_manager.services.club_support import recover_managed_players
        recover_managed_players(self, days=recovery_days)
        self._active_match = next_match
        self.current_date = next_match.match_date
        self.update_dressing_room()
        if next_match.competition_key == "league":
            self._current_league_fixture = next_match.fixture
        self._prepare_development_opponent()
        self.last_result = None
        self.match_played = False

    def _record_active_match_result(self, result: FastMatchResult) -> None:
        item = self._active_match
        fixture = item.fixture
        if item.competition_key == "league" or item.competition_key in self._world.cups or item.competition_key in self._world.staged:
            record_managed_match(self._world, fixture, result)
            self._sync_world_view()
            return
        self._season_calendar = self._season_calendar.mark_played(fixture.fixture_id)
        if item.competition_key == "league":
            self._league_results.append(
                LeagueResult(fixture.fixture_id, result.home_goals, result.away_goals)
            )
            self._complete_background_round(fixture.round_number or 1)
            return

        knockout_result = KnockoutMatchResult(
            fixture.fixture_id,
            result.home_goals,
            result.away_goals,
            result.penalties_home,
            result.penalties_away,
        )
        if item.competition_key == "cup":
            self._cup_results.append(knockout_result)
            self._complete_cup_leg_and_progress(fixture)
            return

        if item.stage_id == "league-phase":
            self._continental_league_results.append(
                LeagueResult(fixture.fixture_id, result.home_goals, result.away_goals)
            )
            self._complete_continental_league_round(fixture.round_number or 1)
            if len(self._continental_league_results) == len(self._continental_edition.fixtures):
                self._finish_continental_league_phase()
            return

        self._continental_knockout_results.append(knockout_result)
        self._complete_continental_knockout_leg_and_progress(fixture)

    def _apply_managed_result_morale(self, result: FastMatchResult) -> None:
        if result.home_club_id == self.home_club.id:
            goals_for, goals_against = result.home_goals, result.away_goals
        else:
            goals_for, goals_against = result.away_goals, result.home_goals
        margin = goals_for - goals_against
        if margin > 0:
            base_delta = 2.6 + min(1.4, 0.35 * margin)
        elif margin < 0:
            base_delta = -2.2 - min(1.3, 0.30 * abs(margin))
        else:
            base_delta = 0.35
        starter_ids = {entry.player.id for entry in self.home_lineup.starters}
        for player in self.home_club.squad.players:
            multiplier = 1.10 if player.id in starter_ids else 0.75
            # Result-driven morale with gentle reversion avoids weeks at 100.
            current = player.state.morale
            reversion = -0.18 * (current - 72.0)
            player.state.adjust_morale(base_delta * multiplier + reversion)

    def _complete_background_round(self, round_number: int) -> None:
        existing = {result.fixture_id for result in self._league_results}
        for fixture in self._league_edition.fixtures:
            if fixture.round_number != round_number or fixture.fixture_id in existing:
                continue
            rng = Random(f"dev-league:{self._seed}:{fixture.fixture_id}")
            home_index = self._league_strength_index(fixture.home_club_id)
            away_index = self._league_strength_index(fixture.away_club_id)
            home_edge = (home_index - away_index) * 0.08 + 0.30
            away_edge = (away_index - home_index) * 0.08
            home_goals = self._sample_dev_goals(rng, 1.15 + home_edge)
            away_goals = self._sample_dev_goals(rng, 1.05 + away_edge)
            self._league_results.append(
                LeagueResult(fixture.fixture_id, home_goals, away_goals)
            )

    def _complete_cup_leg_and_progress(self, fixture: CompetitionFixture) -> None:
        index, bracket_round = next(
            (index, item)
            for index, item in enumerate(self._cup_rounds)
            if fixture.fixture_id in {candidate.fixture_id for candidate in item.plan.fixtures}
        )
        self._complete_knockout_leg_background(
            bracket_round,
            self._cup_results,
            fixture.leg_number,
            namespace="dev-cup",
        )
        if fixture.leg_number < bracket_round.definition.leg_count:
            return
        outcome = resolve_knockout_round(
            bracket_round.plan, tuple(self._results_for_plan(bracket_round.plan))
        )
        self._cup_rounds[index] = KnockoutBracketRound(
            definition=bracket_round.definition,
            plan=bracket_round.plan,
            outcome=outcome,
        )
        if len(outcome.winner_club_ids) == 1:
            return
        next_index = index + 1
        if next_index < len(self._cup_rounds):
            return
        next_definition = self._cup_round_definitions[next_index]
        next_plan = advance_knockout_round(
            outcome,
            edition_id=self._cup_edition.edition_id,
            stage_id="knockout",
            next_definition=next_definition,
            seed=self._seed + next_index,
        )
        next_round = KnockoutBracketRound(next_definition, next_plan)
        self._cup_rounds.append(next_round)
        self._register_current_cup_round_schedule()

    def _complete_knockout_leg_background(
        self,
        bracket_round: KnockoutBracketRound,
        results: list[KnockoutMatchResult],
        leg_number: int,
        *,
        namespace: str,
    ) -> None:
        existing = {result.fixture_id for result in results}
        result_map = {result.fixture_id: result for result in results}
        for tie in bracket_round.plan.ties:
            for fixture in tie.fixtures:
                if fixture.leg_number != leg_number or fixture.fixture_id in existing:
                    continue
                rng = Random(f"{namespace}:{self._seed}:{fixture.fixture_id}")
                home_goals = self._sample_dev_goals(rng, 1.35)
                away_goals = self._sample_dev_goals(rng, 1.15)
                penalties_home = penalties_away = 0
                if leg_number == bracket_round.definition.leg_count:
                    aggregate = {tie.club_a_id: 0, tie.club_b_id: 0}
                    for previous in tie.fixtures:
                        previous_result = (
                            result_map.get(previous.fixture_id)
                            if previous.fixture_id != fixture.fixture_id
                            else None
                        )
                        if previous_result is None:
                            continue
                        aggregate[previous.home_club_id] += previous_result.home_goals
                        aggregate[previous.away_club_id] += previous_result.away_goals
                    aggregate[fixture.home_club_id] += home_goals
                    aggregate[fixture.away_club_id] += away_goals
                    if aggregate[tie.club_a_id] == aggregate[tie.club_b_id]:
                        if rng.random() < 0.5:
                            penalties_home, penalties_away = 5, 4
                        else:
                            penalties_home, penalties_away = 4, 5
                generated = KnockoutMatchResult(
                    fixture.fixture_id,
                    home_goals,
                    away_goals,
                    penalties_home,
                    penalties_away,
                )
                results.append(generated)
                result_map[fixture.fixture_id] = generated
                existing.add(fixture.fixture_id)

    def _complete_continental_league_round(self, round_number: int) -> None:
        existing = {result.fixture_id for result in self._continental_league_results}
        for fixture in self._continental_edition.fixtures:
            if fixture.round_number != round_number or fixture.fixture_id in existing:
                continue
            rng = Random(f"dev-continental-league:{self._seed}:{fixture.fixture_id}")
            home_index = self._league_strength_index(fixture.home_club_id)
            away_index = self._league_strength_index(fixture.away_club_id)
            home_edge = (home_index - away_index) * 0.07 + 0.25
            away_edge = (away_index - home_index) * 0.07
            self._continental_league_results.append(
                LeagueResult(
                    fixture.fixture_id,
                    self._sample_dev_goals(rng, 1.20 + home_edge),
                    self._sample_dev_goals(rng, 1.05 + away_edge),
                )
            )

    def _continental_standings(self):
        return build_league_table(
            participant_club_ids=self._continental_edition.participant_club_ids,
            fixtures=self._continental_edition.fixtures,
            results=tuple(self._continental_league_results),
        )

    def _finish_continental_league_phase(self) -> None:
        if self._continental_transition is not None:
            return
        standings = self._continental_standings()
        transition = resolve_standing_stage_transition(
            standings,
            self._continental_routes,
            source_stage_id="league-phase",
        )
        self._continental_transition = transition
        self._continental_direct_semifinalists = transition.for_target("semifinal")
        playoff_ids = transition.for_target("playoff")
        if len(playoff_ids) != 4:
            raise RuntimeError("development multi-stage playoff requires four clubs")
        pairings = (
            (playoff_ids[0], playoff_ids[-1]),
            (playoff_ids[1], playoff_ids[-2]),
        )
        definition = self._continental_round_definitions["playoff"]
        plan = seed_knockout_round(
            edition_id=self._continental_edition.edition_id,
            stage_id="playoff",
            definition=definition,
            pairings=pairings,
        )
        bracket_round = KnockoutBracketRound(definition, plan)
        self._continental_rounds.append(bracket_round)
        self._register_continental_round_schedule(bracket_round)
        if self.home_club.id not in playoff_ids:
            self._complete_knockout_leg_background(
                bracket_round,
                self._continental_knockout_results,
                1,
                namespace="dev-continental-playoff",
            )
            outcome = resolve_knockout_round(
                plan, tuple(self._continental_results_for_plan(plan))
            )
            self._continental_rounds[-1] = KnockoutBracketRound(
                definition, plan, outcome
            )
            self._advance_continental_after_round(outcome, stage_id="playoff")

    def _complete_continental_knockout_leg_and_progress(
        self, fixture: CompetitionFixture
    ) -> None:
        index, bracket_round = next(
            (index, item)
            for index, item in enumerate(self._continental_rounds)
            if fixture.fixture_id in {candidate.fixture_id for candidate in item.plan.fixtures}
        )
        self._complete_knockout_leg_background(
            bracket_round,
            self._continental_knockout_results,
            fixture.leg_number,
            namespace=f"dev-continental-{fixture.stage_id}",
        )
        if fixture.leg_number < bracket_round.definition.leg_count:
            return
        outcome = resolve_knockout_round(
            bracket_round.plan,
            tuple(self._continental_results_for_plan(bracket_round.plan)),
        )
        self._continental_rounds[index] = KnockoutBracketRound(
            bracket_round.definition,
            bracket_round.plan,
            outcome,
        )
        self._advance_continental_after_round(outcome, stage_id=fixture.stage_id)

    def _advance_continental_after_round(self, outcome, *, stage_id: str) -> None:
        if not outcome.complete:
            raise RuntimeError("cannot advance incomplete development continental round")
        if stage_id == "final":
            return
        if stage_id == "playoff":
            participants = merge_stage_participants(
                self._continental_direct_semifinalists,
                outcome.winner_club_ids,
            )
            next_stage = "semifinal"
        elif stage_id == "semifinal":
            participants = outcome.winner_club_ids
            next_stage = "final"
        else:
            raise ValueError(f"unknown continental knockout stage: {stage_id}")
        definition = self._continental_round_definitions[next_stage]
        plan = generate_knockout_round(
            edition_id=self._continental_edition.edition_id,
            stage_id=next_stage,
            definition=definition,
            participant_club_ids=participants,
            seed=self._seed + 6400 + len(self._continental_rounds),
        )
        bracket_round = KnockoutBracketRound(definition, plan)
        self._continental_rounds.append(bracket_round)
        self._register_continental_round_schedule(bracket_round)

    def _continental_results_for_plan(self, plan) -> list[KnockoutMatchResult]:
        fixture_ids = {fixture.fixture_id for fixture in plan.fixtures}
        return [
            result
            for result in self._continental_knockout_results
            if result.fixture_id in fixture_ids
        ]

    def _league_strength_index(self, club_id: str) -> int:
        return self._league_edition.participant_club_ids.index(club_id) % 7

    @staticmethod
    def _sample_dev_goals(rng: Random, expectation: float) -> int:
        # Tiny Poisson sampler used only for unobserved sandbox fixtures.
        expectation = max(0.25, min(2.75, expectation))
        threshold = 2.718281828459045 ** (-expectation)
        product = 1.0
        count = 0
        while product > threshold:
            count += 1
            product *= rng.random()
        return min(7, count - 1)

    def match_summary(self) -> MatchSummary | None:
        result = self.last_result
        if result is None:
            return None
        # A completed season has no active fixture. Keep the last match visible
        # without dereferencing an absent next match or swapping the teams.
        actual_home, actual_away = (
            (self.home_club, self.away_club)
            if result.home_club_id == self.home_club.id
            else (self.away_club, self.home_club)
        )
        return MatchSummary(
            scoreline=(
                f"{actual_home.short_name} {result.home_goals}-{result.away_goals} "
                f"{actual_away.short_name}"
            ),
            competition=self._last_played_match_metadata,
            stats_line=(
                f"xG {result.statistics_home.xg:.2f}-{result.statistics_away.xg:.2f} | "
                f"Shots {result.statistics_home.shots}-{result.statistics_away.shots} | "
                f"SOT {result.statistics_home.shots_on_target}-{result.statistics_away.shots_on_target}"
            ),
            possession_line=(
                f"Possession {result.statistics_home.possession_pct:.1f}% - "
                f"{result.statistics_away.possession_pct:.1f}% | "
                f"Passes {result.statistics_home.passes_completed}/{result.statistics_home.passes_attempted} - "
                f"{result.statistics_away.passes_completed}/{result.statistics_away.passes_attempted}"
            ),
            discipline_line=(
                f"Fouls {result.statistics_home.fouls}-{result.statistics_away.fouls} | "
                f"YC {result.statistics_home.yellow_cards}-{result.statistics_away.yellow_cards} | "
                f"Corners {result.statistics_home.corners}-{result.statistics_away.corners}"
            ),
        )

    def _initialize_development_league(self) -> None:
        # The sandbox intentionally uses fictional clubs. Real 2026/27 fixture
        # data is a later data-import concern, not part of the league engine.
        club_pairs = (
            (self.home_club.id, self.home_club.name),
            ("harbour-town", "Harbour Town"),
            ("kingsport", "Kingsport FC"),
            ("westborough", "Westborough United"),
            ("ashford-city", "Ashford City"),
            ("oakmere", "Oakmere Athletic"),
            ("redhaven", "Redhaven FC"),
            ("stonebridge", "Stonebridge Town"),
            ("greenwich-rovers", "Greenwich Rovers"),
            ("eastgate", "Eastgate FC"),
            ("southbank", "Southbank Athletic"),
            ("fairview", "Fairview United"),
            ("highfield", "Highfield City"),
            ("brookdale", "Brookdale FC"),
            ("woodford", "Woodford Town"),
            ("lakeside", "Lakeside Rovers"),
            ("hillcrest", "Hillcrest Athletic"),
            ("meadowpark", "Meadowpark United"),
            ("northshore", "Northshore City"),
            (self.away_club.id, self.away_club.name),
        )
        self._league_club_names = dict(club_pairs)
        participant_ids = tuple(club_id for club_id, _ in club_pairs)
        self._league_fixture_plan = RoundRobinFixturePlan.generated(
            edition_id="dev-premier-2026-27",
            stage_id="league",
            participant_club_ids=participant_ids,
        )
        fixtures = self._league_fixture_plan.fixtures
        self._league_edition = CompetitionEdition(
            edition_id="dev-premier-2026-27",
            competition=CompetitionDefinition(
                competition_id="dev-premier",
                name="Premier League (development)",
                short_name="DPL",
                scope=CompetitionScope.DOMESTIC,
                format=CompetitionFormat.LEAGUE,
                country="England",
            ),
            season_label="2026/27",
            participant_club_ids=participant_ids,
            stages=(
                CompetitionStage(
                    stage_id="league",
                    name="League",
                    kind=CompetitionStageKind.ROUND_ROBIN,
                    order=1,
                    participant_club_ids=participant_ids,
                ),
            ),
            qualification_rules=(
                QualificationRule(
                    rule_id="dev-ucl",
                    label="DEV UCL",
                    kind=QualificationKind.CONTINENTAL,
                    source=QualificationSource.STANDING_POSITION,
                    target_competition_id="dev-champions",
                    standing_positions=(1, 2, 3, 4),
                ),
                QualificationRule(
                    rule_id="dev-uel",
                    label="DEV UEL",
                    kind=QualificationKind.CONTINENTAL,
                    source=QualificationSource.STANDING_POSITION,
                    target_competition_id="dev-europa",
                    standing_positions=(5,),
                ),
                QualificationRule(
                    rule_id="dev-uecl",
                    label="DEV UECL",
                    kind=QualificationKind.CONTINENTAL,
                    source=QualificationSource.STANDING_POSITION,
                    target_competition_id="dev-conference",
                    standing_positions=(6,),
                ),
                QualificationRule(
                    rule_id="dev-relegation",
                    label="DEV Relegation",
                    kind=QualificationKind.RELEGATION,
                    source=QualificationSource.STANDING_POSITION,
                    target_competition_id="dev-second-tier",
                    standing_positions=(18, 19, 20),
                ),
            ),
            status=CompetitionStatus.ACTIVE,
            fixtures=fixtures,
        )
        self._league_results: list[LeagueResult] = []
        self._current_league_fixture = next(
            fixture
            for fixture in fixtures
            if fixture.round_number == 1
            and fixture.home_club_id == self.home_club.id
            and fixture.away_club_id == self.away_club.id
        )

    def _initialize_development_cup(self) -> None:
        participant_ids = tuple(self._league_edition.participant_club_ids[:8])
        self._cup_club_names = {
            club_id: self._league_club_names[club_id] for club_id in participant_ids
        }
        self._cup_edition = CompetitionEdition(
            edition_id="dev-cup-2026-27",
            competition=CompetitionDefinition(
                competition_id="dev-cup",
                name="Development Cup",
                short_name="DC",
                scope=CompetitionScope.DOMESTIC,
                format=CompetitionFormat.KNOCKOUT,
                country="England",
            ),
            season_label="2026/27",
            participant_club_ids=participant_ids,
            stages=(
                CompetitionStage(
                    stage_id="knockout",
                    name="Knockout",
                    kind=CompetitionStageKind.KNOCKOUT,
                    order=1,
                    participant_club_ids=participant_ids,
                ),
            ),
            status=CompetitionStatus.ACTIVE,
        )
        self._cup_round_definitions = (
            KnockoutRoundDefinition(
                round_id="quarterfinal",
                name="Quarter-final",
                order=1,
                leg_format=KnockoutLegFormat.SINGLE_LEG,
            ),
            KnockoutRoundDefinition(
                round_id="semifinal",
                name="Semi-final",
                order=2,
                leg_format=KnockoutLegFormat.TWO_LEGGED,
            ),
            KnockoutRoundDefinition(
                round_id="final",
                name="Final",
                order=3,
                leg_format=KnockoutLegFormat.SINGLE_LEG,
            ),
        )
        first_plan = generate_knockout_round(
            edition_id=self._cup_edition.edition_id,
            stage_id="knockout",
            definition=self._cup_round_definitions[0],
            participant_club_ids=participant_ids,
            seed=self._seed,
        )
        self._cup_results: list[KnockoutMatchResult] = []
        self._cup_rounds: list[KnockoutBracketRound] = [
            KnockoutBracketRound(
                definition=self._cup_round_definitions[0],
                plan=first_plan,
            )
        ]

    def _initialize_development_multistage(self) -> None:
        participant_ids = tuple(self._league_edition.participant_club_ids[:8])
        self._continental_club_names = {
            club_id: self._league_club_names[club_id] for club_id in participant_ids
        }
        generated = RoundRobinFixturePlan.generated(
            edition_id="dev-continental-2026-27",
            stage_id="league-phase",
            participant_club_ids=participant_ids,
            seed=self._seed + 640,
        )
        league_phase_fixtures = tuple(
            fixture for fixture in generated.fixtures if (fixture.round_number or 0) <= 7
        )
        self._continental_edition = CompetitionEdition(
            edition_id="dev-continental-2026-27",
            competition=CompetitionDefinition(
                competition_id="dev-continental",
                name="Development Continental",
                short_name="DCC",
                scope=CompetitionScope.CONTINENTAL,
                format=CompetitionFormat.MULTI_STAGE,
            ),
            season_label="2026/27",
            participant_club_ids=participant_ids,
            stages=(
                CompetitionStage(
                    stage_id="league-phase",
                    name="League phase",
                    kind=CompetitionStageKind.LEAGUE_PHASE,
                    order=1,
                    participant_club_ids=participant_ids,
                ),
                CompetitionStage(
                    stage_id="playoff",
                    name="Playoff",
                    kind=CompetitionStageKind.KNOCKOUT,
                    order=2,
                ),
                CompetitionStage(
                    stage_id="semifinal",
                    name="Semi-final",
                    kind=CompetitionStageKind.KNOCKOUT,
                    order=3,
                ),
                CompetitionStage(
                    stage_id="final",
                    name="Final",
                    kind=CompetitionStageKind.KNOCKOUT,
                    order=4,
                ),
            ),
            status=CompetitionStatus.ACTIVE,
            fixtures=league_phase_fixtures,
        )
        self._continental_routes = (
            StandingRouteRule(
                "dev-direct-semi",
                "Direct SF",
                "league-phase",
                (1, 2),
                StageRouteKind.ADVANCE,
                "semifinal",
            ),
            StandingRouteRule(
                "dev-playoff",
                "Playoff",
                "league-phase",
                (3, 4, 5, 6),
                StageRouteKind.PLAYOFF,
                "playoff",
            ),
            StandingRouteRule(
                "dev-eliminated",
                "Out",
                "league-phase",
                (7, 8),
                StageRouteKind.ELIMINATED,
            ),
        )
        self._continental_round_definitions = {
            "playoff": KnockoutRoundDefinition(
                round_id="playoff",
                name="Playoff",
                order=1,
                leg_format=KnockoutLegFormat.SINGLE_LEG,
            ),
            "semifinal": KnockoutRoundDefinition(
                round_id="continental-semifinal",
                name="Semi-final",
                order=2,
                leg_format=KnockoutLegFormat.TWO_LEGGED,
            ),
            "final": KnockoutRoundDefinition(
                round_id="continental-final",
                name="Final",
                order=3,
                leg_format=KnockoutLegFormat.SINGLE_LEG,
            ),
        }
        self._continental_league_results: list[LeagueResult] = []
        self._continental_knockout_results: list[KnockoutMatchResult] = []
        self._continental_rounds: list[KnockoutBracketRound] = []
        self._continental_transition = None
        self._continental_direct_semifinalists: tuple[str, ...] = ()

    def _initialize_development_schedule(self) -> None:
        self._managed_schedule: dict[str, DevelopmentScheduledMatch] = {}
        self._season_calendar = SeasonCalendar("2026/27", "UTC", ())
        league_start = date(2026, 8, 15)
        for fixture in self._league_edition.fixtures:
            if self.home_club.id not in (fixture.home_club_id, fixture.away_club_id):
                continue
            round_number = fixture.round_number or 1
            self._register_managed_match(
                DevelopmentScheduledMatch(
                    match_date=league_start + timedelta(days=7 * (round_number - 1)),
                    competition_key="league",
                    competition_name="Premier League",
                    stage_id="league",
                    round_label=f"Round {round_number}",
                    fixture=fixture,
                )
            )
        # Legacy 8-club DEV Cup remains in the inspector, not the playable season.
        # FA Cup and Carabao Cup are now the two scheduled English domestic cups.

        continental_dates = {
            1: date(2026, 8, 26),
            2: date(2026, 9, 23),
            3: date(2026, 10, 21),
            4: date(2026, 11, 18),
            5: date(2026, 12, 16),
            6: date(2027, 1, 13),
            7: date(2027, 2, 10),
        }
        for fixture in self._continental_edition.fixtures:
            if self.home_club.id not in (fixture.home_club_id, fixture.away_club_id):
                continue
            round_number = fixture.round_number or 1
            self._register_managed_match(
                DevelopmentScheduledMatch(
                    match_date=continental_dates[round_number],
                    competition_key="continental",
                    competition_name="Development Continental",
                    stage_id="league-phase",
                    round_label=f"League phase MD{round_number}",
                    fixture=fixture,
                )
            )

        first = self._next_unplayed_managed_match()
        if first is None:
            raise RuntimeError("development schedule has no managed fixtures")
        self._active_match = first
        self.current_date = first.match_date
        if first.competition_key == "league":
            self._current_league_fixture = first.fixture

    def _initialize_world_runner(self, *, world_seed: int = 6606) -> None:
        """Register all four fictional English leagues and both official cup formats."""
        # Build the normal initial-season fixture first, then apply the FIFA
        # calendar without changing sporting pairings or already played dates.
        master = build_international_calendar(2026, 2027)
        season_end = date(2027, 5, 31)
        blackout_periods = master.league_blackouts(self.current_date, season_end)
        self._world = WorldSeasonRunner(
            season_label="2026/27", seed=world_seed, international_calendar=master,
        )
        # Use the official 2026/27 Premier kickoff distribution as a template
        # for *fictional* opponents. A later cup/UEFA draw can still reprogram
        # individual unplayed matches in WorldSeasonRunner.
        premier_calendar = build_premier_calendar(
            self._league_edition, 2026, international_calendar=master,
        )
        premier_ids = self._league_edition.participant_club_ids
        self._world.register_league(
            self._league_edition, premier_calendar,
            {club: tier_strength(1, i) for i, club in enumerate(premier_ids)},
        )
        tiers: dict[int, tuple[str, ...]] = {1: premier_ids}
        self._world_club_names: dict[str, str] = dict(self._league_club_names)
        for tier, key in ((2, "championship"), (3, "league-one"), (4, "league-two")):
            division = self._efl_divisions[key]
            tiers[tier] = division.edition.participant_club_ids
            self._world_club_names.update(division.club_names)
            efl_calendar = reprogram_pending_fixtures_for_blackouts(
                division.calendar, blackout_periods=blackout_periods,
                earliest_date=self.current_date, latest_date=season_end,
            )
            self._world.register_league(division.edition, efl_calendar, division.strengths)
        nonleague = {
            f"dev-nonleague-{index:03d}": tier_strength(4, (index - 1) % 24) - 10
            for index in range(1, 65)
        }
        self._world_club_names.update({club: f"Non-League {index:02d}"
                                       for index, club in enumerate(nonleague, 1)})
        fa_cup = build_fa_cup_2026_27(tiers)
        # Nine fictional Premier clubs have the European-entry exemption in the
        # 2026/27 Carabao structure. This is NOT actual European qualification.
        carabao = build_carabao_cup_2026_27(tiers, european_entrant_ids=premier_ids[1:10])
        self._world.register_cup(fa_cup, strengths=nonleague)
        self._world.register_cup(carabao, strengths={})
        # Fictional international participants; no real clubs or UEFA draws yet.
        # The managed club occupies one UEFA Champions League place in this
        # deliberately small DEV qualification fixture, not a real berth rule.
        for key, english_clubs, strength in (
            ("champions-league", premier_ids[:5], 79),
            ("europa-league", premier_ids[5:7], 74),
            ("conference-league", premier_ids[7:8], 69),
        ):
            foreign_count = 36 - len(english_clubs)
            foreign = tuple(f"dev-{key}-foreign-{i:02d}" for i in range(1, foreign_count + 1))
            self._world_club_names.update({club: f"{key.replace('-', ' ').title()} Visitor {i:02d}"
                                           for i, club in enumerate(foreign, 1)})
            self._world.register_staged(
                build_uefa_2026_27(key, (*english_clubs, *foreign)),
                strengths={cid: strength + ((i * 7) % 17) - 8 for i, cid in enumerate(foreign)},
            )
        trophy = build_efl_trophy_2026_27(tiers[3], tiers[4])
        academy_ids = (cid for cid in trophy.participants if cid.startswith("dev-trophy-u21-"))
        academy_strengths = {cid: 46 + (i * 5) % 17 for i, cid in enumerate(academy_ids)}
        self._world_club_names.update({cid: f"Academy {cid.split('-')[-2].title()} {cid.split('-')[-1]} U21"
                                       for cid in academy_strengths})
        self._world.register_staged(trophy, strengths=academy_strengths)
        self._world.configure_promotion_playoffs(("dev-championship", "dev-league-one", "dev-league-two"))
        from football_manager.domain.calendar_planner import repair_generated_calendar
        repair_generated_calendar(self._world)
        from football_manager.services.world_squads import install_football_world
        install_football_world(self)
        self._world.advance_until(self.current_date, protected_club_id=self.home_club.id)
        self._sync_world_view()
        # Matchday begins on the actual earliest scheduled controlled fixture,
        # not the old synthetic 15 August kickoff used by the inspector.
        first = self._next_unplayed_managed_match()
        if first is None:
            raise RuntimeError("development world has no opening match")
        self._active_match = first
        self.current_date = first.match_date
        self._world.advance_until(self.current_date, protected_club_id=self.home_club.id)
        self._sync_world_view()

    def _sync_world_view(self) -> None:
        """Project the canonical world ledger into existing lightweight DEV views."""
        self._league_results = list(self._world.league_results(self._league_edition.competition_id))
        for key, division in self._efl_divisions.items():
            self._efl_results[key] = list(self._world.league_results(division.edition.competition_id))
            dates = [self._world.fixtures[old.fixture_id] for old in division.calendar.fixtures]
            self._efl_divisions[key] = replace(
                division, calendar=SeasonCalendar(self._world.season_label, "UTC", tuple(dates)),
            )
            played = {r.fixture_id for r in self._efl_results[key]}
            self._efl_current_round[key] = next((
                number for number in range(1, 47)
                if any(f.fixture_id not in played for f in division.edition.fixtures
                       if f.round_number == number)
            ), 47)
            if len(played) == 552:
                self._efl_current_round[key] = 47

        fresh_managed: dict[str, DevelopmentScheduledMatch] = {}
        fixtures = []
        for scheduled in self._world.calendar.fixtures_for_club(self.home_club.id):
            if scheduled.match_date is None:
                continue
            if scheduled.competition_id in self._world.leagues:
                if scheduled.competition_id != self._league_edition.competition_id:
                    continue
                fixture = next(f for f in self._league_edition.fixtures if f.fixture_id == scheduled.fixture_id)
                stage_label = f"Round {fixture.round_number}"
                key = "league"
                name = self._league_edition.competition.name.replace(" (development)", "")
            elif scheduled.competition_id in self._world.cups:
                cup = self._world.cups[scheduled.competition_id]
                plan = cup.plan_for_fixture(scheduled.fixture_id)
                fixture = next(f for f in plan.fixtures if f.fixture_id == scheduled.fixture_id)
                key = cup.cup_id
                name = cup.name.replace(" (fictional clubs)", "")
                rule = cup.rule_for_fixture(scheduled.fixture_id)
                stage_label = rule.label
                if rule.leg_format.leg_count > 1:
                    stage_label += f" leg {fixture.leg_number}"
            else:
                staged = self._world.staged[scheduled.competition_id]
                if scheduled.stage_id == staged.primary_stage_id:
                    fixture = next(f for f in staged.primary_fixtures if f.fixture_id == scheduled.fixture_id)
                    stage_label = (f"League phase MD{fixture.round_number}" if staged.kind == "uefa"
                                   else f"Group phase MD{fixture.round_number}")
                else:
                    plan = staged.plan_for_fixture(scheduled.fixture_id)
                    fixture = next(f for f in plan.fixtures if f.fixture_id == scheduled.fixture_id)
                    stage_label = f"{plan.definition.name}"
                    if plan.definition.leg_count > 1:
                        stage_label += f" leg {fixture.leg_number}"
                key = staged.competition_id
                name = staged.name
            fresh_managed[scheduled.fixture_id] = DevelopmentScheduledMatch(
                scheduled.match_date, key, name, scheduled.stage_id, stage_label, fixture,
            )
            fixtures.append(scheduled)
        # One canonical calendar, no disconnected legacy Development Continental
        # fixtures or immutable conditional placeholders.
        self._managed_schedule = fresh_managed
        self._season_calendar = SeasonCalendar(self._world.season_label, "UTC", tuple(fixtures))

    def _reflow_dev_continental(self, fixtures, managed):
        club_id = self.home_club.id
        others = [f for f in fixtures if f.competition_id != self._continental_edition.competition_id]
        continental = sorted(
            (f for f in fixtures if f.competition_id == self._continental_edition.competition_id),
            key=lambda f: (f.kickoff or datetime.max.replace(tzinfo=timezone.utc), f.fixture_id),
        )
        assigned = []
        for fixture in continental:
            if fixture.status is not ScheduledFixtureStatus.SCHEDULED or fixture.kickoff is None:
                assigned.append(fixture)
                continue
            chosen = None
            original = fixture.kickoff
            # Reconsider earlier shifted dates if later cup draws force another
            # move. Never rewrite dates/results of an already played fixture.
            for offset in range(0, 29):
                candidate_day = max(original.date(), self.current_date) + timedelta(days=offset)
                candidate = datetime(
                    candidate_day.year, candidate_day.month, candidate_day.day,
                    19, 45, tzinfo=timezone.utc,
                )
                participants = {fixture.home_club_id, fixture.away_club_id}
                if any(
                    rival.kickoff is not None
                    and rival.status not in (ScheduledFixtureStatus.CANCELLED, ScheduledFixtureStatus.POSTPONED)
                    and participants.intersection((rival.home_club_id, rival.away_club_id))
                    and (rival.kickoff.date() == candidate.date()
                         or abs((rival.kickoff - candidate).total_seconds()) < 48 * 3600)
                    for rival in (*others, *assigned)
                ):
                    continue
                chosen = candidate
                break
            if chosen is None:
                raise ValueError(f"no valid DEV continental date for {fixture.fixture_id}")
            moved = replace(fixture, kickoff=chosen,
                            original_kickoff=fixture.original_kickoff or fixture.kickoff)
            assigned.append(moved)
            previous = managed[fixture.fixture_id]
            managed[fixture.fixture_id] = replace(previous, match_date=chosen.date())
        return [*others, *assigned], managed

    def set_dev_favorable_mode(self, enabled: bool) -> None:
        """Lower opponents only in match snapshots for this opt-in DEV mode.

        Results remain genuine FastSimulator outputs. No scripted victories.
        """
        self.dev_favorable_mode = bool(enabled)
        if self._active_match is not None and not self.match_played:
            self._prepare_development_opponent()

    @property
    def season_finished(self) -> bool:
        return bool(self._world.fixtures) and set(self._world.fixtures) == set(self._world.results)

    @property
    def archived_season_reports(self) -> tuple[SeasonReport, ...]:
        return tuple(self._career.reports)

    def simulate_remaining_season(self, on_progress: Callable[[int], None] | None = None) -> int:
        """One-click DEV season, still using the real FastMatchSimulator for Northbridge.

        Never background-simulates a protected club's match. A fresh knockout
        tie can appear while the earlier known managed schedule is exhausted.
        """
        played_managed = 0
        finish_by = date(int(self._world.season_label[:4]) + 1, 6, 30)
        for _ in range(150):  # fail closed instead of silently infinite-looping
            if self.can_quick_sim:
                from football_manager.services.player_aging import repair_managed_unavailable
                repair_managed_unavailable(self)
                self.quick_simulate()
                played_managed += 1
                if on_progress:
                    on_progress(played_managed)
            if self.match_played:
                try:
                    self.continue_to_next_match()
                    continue
                except RuntimeError as exc:
                    if "no remaining managed fixtures" not in str(exc):
                        raise
            progress = self._world.advance_until(finish_by, protected_club_id=self.home_club.id)
            self._sync_world_view()
            next_match = self._next_unplayed_managed_match()
            if next_match is None:
                if progress.stopped_for_managed_fixture_id:
                    raise RuntimeError("protected fixture was not projected into the managed schedule")
                if not self.season_finished:
                    raise RuntimeError("season has unplayed matches past its generated finish window")
                self._active_match = None
                self.current_date = finish_by
                self.update_dressing_room()
                self.match_played = False
                return played_managed
            recovery_days = max(0, (next_match.match_date-self.current_date).days)
            from football_manager.services.club_support import recover_managed_players
            recover_managed_players(self, days=recovery_days)
            self._active_match = next_match
            self.current_date = next_match.match_date
            self.update_dressing_room()
            self._prepare_development_opponent()
            self.match_played = False
        raise RuntimeError("season simulation exceeded 150 managed fixtures")

    def begin_next_season(self) -> SeasonReport:
        if not self.season_finished:
            raise ValueError("finish all matches before beginning the next season")
        from football_manager.services.career_recognition import record_rating_snapshots, award_season
        completed_world = self._world
        report = self._career.begin_next_season()
        record_rating_snapshots(self._world_squads, self.current_date, final=True)
        # A title belongs to players still registered with the champion when
        # the completed season is certified, never to guessed past rosters.
        registry = self._world_squads
        for competition_id, club_id in report.champions.items():
            club = registry.clubs.get(club_id)
            if club is None:
                continue
            for player in club.squad.players:
                existing = registry.player_honours.get(player.id, ())
                award = (report.season_label, competition_id, club_id)
                if award not in existing:
                    registry.player_honours[player.id] = (*existing, award)
        award_season(registry, completed_world, report, as_of=self.current_date)
        self._adopt_career_world()
        # Recover over the offseason, without resetting identities or lineups.
        for player in self.home_club.squad.players:
            recover_player_between_matches(player, days=42)
        if self._active_match:
            self._prepare_development_opponent()
        return report

    def _adopt_career_world(self, *, results_only: bool = False) -> None:
        """Rebind the sandbox inspectors to the actual season and managed tier."""
        self._world = self._career.current
        from football_manager.services.world_squads import bind_football_world
        bind_football_world(self)
        if results_only:
            from football_manager.services.world_squads import reset_results_only_tracking
            reset_results_only_tracking(self)
        self._world_club_names = self._career.club_names
        managed_league_id = next(cid for cid, edition in self._world.leagues.items()
                                 if self.home_club.id in edition.participant_club_ids)
        self._league_edition = self._world.leagues[managed_league_id]
        self._league_club_names = {cid: self._world_club_names[cid]
                                   for cid in self._league_edition.participant_club_ids}
        self._efl_divisions = {
            key: replace(
                division, edition=self._world.leagues["dev-"+key],
                calendar=SeasonCalendar(self._world.season_label, "UTC", tuple(
                    fixture for fixture in self._world.fixtures.values()
                    if fixture.competition_id == "dev-"+key)),
                club_names={cid: self._world_club_names[cid]
                            for cid in self._world.leagues["dev-"+key].participant_club_ids},
                strengths={cid: self._world.strengths[cid]
                           for cid in self._world.leagues["dev-"+key].participant_club_ids},
                slot_source_url="GENERATED DEV future season policy (not EFL official fixtures)",
            ) for key, division in self._efl_divisions.items()
        }
        self._efl_results = {key: [] for key in self._efl_divisions}
        self._efl_current_round = {key: 1 for key in self._efl_divisions}
        self._sync_world_view()
        first = self._next_unplayed_managed_match()
        self._active_match = first
        self.match_played = False
        self.last_result = None
        if first:
            self.current_date = first.match_date
            self._world.advance_until(self.current_date, protected_club_id=self.home_club.id)
            self._sync_world_view()
            self._prepare_development_opponent()
        else:
            self.current_date = date(int(self._world.season_label[:4])+1, 6, 30)
            from football_manager.services.player_development import advance_world_development
            advance_world_development(self._world, self.current_date)
        self.update_dressing_room()

    def save_career_results(self, path: str | Path) -> None:
        self._career.save_json(path)

    def load_career_results(self, path: str | Path) -> None:
        """Results-only restore: no player/squad/tactic state is reconstructed."""
        career = WorldCareer.load_json(path)
        if self.home_club.id not in career.current.strengths:
            raise ValueError("managed DEV club is not present in the career archive")
        self._career = career
        self._adopt_career_world(results_only=True)

    def save_world(self, path: str | Path) -> None:
        """Export results only; use the complete SQLite manager save for squads."""
        self._world.save_json(path)

    def load_world(self, path: str | Path) -> None:
        """Restore the world result ledger, not a full manager save game."""
        loaded = WorldSeasonRunner.load_json(path)
        if (loaded.season_label != self._world.season_label
                or set(loaded.leagues) != set(self._world.leagues)
                or (set(loaded.cups) - set(PLAYOFF_IDS.values())) !=
                   (set(self._world.cups) - set(PLAYOFF_IDS.values()))
                or set(loaded.staged) != set(self._world.staged)):
            raise ValueError("world save is incompatible with current development leagues")
        self._world = loaded
        from football_manager.services.world_squads import bind_football_world
        bind_football_world(self)
        from football_manager.services.world_squads import reset_results_only_tracking
        reset_results_only_tracking(self)
        self._career.worlds[-1] = loaded
        self._sync_world_view()
        first = self._next_unplayed_managed_match()
        self._active_match = first
        self.match_played = False
        self.last_result = None
        if first is not None:
            self.current_date = first.match_date
            self._prepare_development_opponent()
        self.update_dressing_room()

    @property
    def world_summary(self) -> str:
        return (
            f"World {self._world.season_label} | 4 leagues + FA Cup + Carabao + 3 UEFA + EFL Trophy + EFL playoffs | "
            f"{len(self._world.results)}/{len(self._world.fixtures)} "
            "currently drawn fixtures played | Canonical DEV results"
        )

    def world_cup_summary(self, cup_id: str) -> str:
        cup = self._world.cups[cup_id]
        current = cup.current_round
        completed = sum(fid in self._world.results for plan in cup.plans for fid in
                        (f.fixture_id for f in plan.fixtures))
        champion = self._world_club_names.get(cup.champion_club_id or "", "")
        return (f"{cup.name} | {current.label} | {completed} played | "
                + (f"Champion: {champion}" if champion else "Generated draws; official 2026/27 round dates"))

    def world_cup_bracket_rows(self, cup_id: str) -> tuple[KnockoutTieViewRow, ...]:
        cup = self._world.cups[cup_id]
        rows = []
        for plan in cup.plans:
            for index, tie in enumerate(plan.ties, 1):
                for fixture in tie.fixtures:
                    result = self._world.result_for(fixture.fixture_id)
                    rows.append(KnockoutTieViewRow(
                        round_name=plan.definition.name, tie_number=index,
                        leg_number=fixture.leg_number,
                        home=self._world_club_names.get(fixture.home_club_id, fixture.home_club_id),
                        away=self._world_club_names.get(fixture.away_club_id, fixture.away_club_id),
                        score="-" if result is None else f"{result.home_goals}-{result.away_goals}"
                        + (f" ({result.penalties_home}-{result.penalties_away} pens)"
                           if result.penalties_home or result.penalties_away else ""),
                        status=(
                            f"{self._world.fixtures[fixture.fixture_id].kickoff:%d %b %Y} | "
                            + ("Scheduled" if result is None else "Played")
                        ),
                    ))
        return tuple(rows)

    @property
    def staged_competition_options(self) -> tuple[tuple[str, str], ...]:
        return tuple((cid, staged.name) for cid, staged in self._world.staged.items())

    def staged_competition_groups(self, competition_id: str) -> tuple[str, ...]:
        return tuple(self._world.staged[competition_id].groups)

    def staged_competition_summary(self, competition_id: str) -> str:
        staged = self._world.staged[competition_id]
        played = sum(f.fixture_id in self._world.results for f in staged.primary_fixtures)
        champion = self._world_club_names.get(staged.champion_club_id or "", "")
        group_note = "16 groups of 4, 2 advance" if staged.kind == "efl-trophy" else "1-8 direct R16, 9-24 playoff, 25-36 out"
        return (f"{staged.name} | {len(staged.participants)} fictional clubs | "
                f"{played}/{len(staged.primary_fixtures)} league/group results | "
                f"{group_note} | " + (f"Champion: {champion}" if champion else "Generated fictional pairings"))

    def staged_competition_table_rows(
        self, competition_id: str, group_id: str | None = None,
    ) -> tuple[LeagueTableViewRow, ...]:
        staged = self._world.staged[competition_id]
        if staged.groups and group_id is None:
            group_id = next(iter(staged.groups))
        standing = staged.standings(self._world.results, group_id)
        rows = []
        for r in standing:
            if staged.kind == "efl-trophy":
                route = "R32" if r.position <= 2 else "Out"
            elif r.position <= 8:
                route = "Direct R16"
            elif r.position <= 24:
                route = "Playoff"
            else:
                route = "Out"
            rows.append(LeagueTableViewRow(
                position=r.position,
                club=self._world_club_names.get(r.club_id, r.club_id),
                played=r.played, won=r.won, drawn=r.drawn, lost=r.lost,
                goals_for=r.goals_for, goals_against=r.goals_against,
                goal_difference=r.goal_difference, points=r.points,
                qualification=route,
            ))
        return tuple(rows)

    def staged_competition_bracket_rows(self, competition_id: str) -> tuple[KnockoutTieViewRow, ...]:
        staged = self._world.staged[competition_id]
        rows = []
        for plan in staged.knockout_plans:
            for index, tie in enumerate(plan.ties, 1):
                for fixture in tie.fixtures:
                    result = self._world.result_for(fixture.fixture_id)
                    item = self._world.fixtures[fixture.fixture_id]
                    rows.append(KnockoutTieViewRow(
                        round_name=plan.definition.name, tie_number=index,
                        leg_number=fixture.leg_number,
                        home=self._world_club_names.get(fixture.home_club_id, fixture.home_club_id),
                        away=self._world_club_names.get(fixture.away_club_id, fixture.away_club_id),
                        score="-" if result is None else f"{result.home_goals}-{result.away_goals}"
                        + (f" ({result.penalties_home}-{result.penalties_away} pens)"
                           if result.penalties_home or result.penalties_away else ""),
                        status=f"{item.kickoff:%d %b %Y} | " + ("Played" if result else "Scheduled"),
                    ))
        return tuple(rows)

    def staged_calendar_rows(self, competition_id: str) -> tuple[OfficialCalendarViewRow, ...]:
        if competition_id not in self._world.staged:
            raise ValueError("unknown world staged competition")
        return tuple(OfficialCalendarViewRow(
            date_label=scheduled.kickoff.strftime("%d %b %Y"),
            matchweek=int(scheduled.round_number or 0),
            home=self._world_club_names.get(scheduled.home_club_id, scheduled.home_club_id),
            away=self._world_club_names.get(scheduled.away_club_id, scheduled.away_club_id),
            kickoff=scheduled.kickoff.strftime("%H:%M UTC"),
            source=f"{scheduled.stage_id} / {scheduled.status.value} / GENERATED",
        ) for scheduled in sorted(
            (f for f in self._world.fixtures.values() if f.competition_id == competition_id),
            key=lambda x: (x.kickoff, x.fixture_id),
        ))

    @property
    def world_result_count(self) -> int:
        return len(self._world.results)

    def _register_managed_match(self, item: DevelopmentScheduledMatch) -> None:
        existing = self._managed_schedule.get(item.fixture.fixture_id)
        if existing is not None and existing != item:
            raise ValueError(f"development fixture {item.fixture.fixture_id} has two schedule slots")
        self._managed_schedule[item.fixture.fixture_id] = item

        competition_id = {
            "league": self._league_edition.competition_id,
            "cup": self._cup_edition.competition_id,
            "continental": self._continental_edition.competition_id,
        }[item.competition_key]
        scheduled_ids = {fixture.fixture_id for fixture in self._season_calendar.fixtures}
        if item.fixture.fixture_id not in scheduled_ids:
            scheduled = ScheduledFixture(
                fixture_id=item.fixture.fixture_id,
                competition_id=competition_id,
                edition_id=item.fixture.edition_id,
                stage_id=item.stage_id,
                home_club_id=item.fixture.home_club_id,
                away_club_id=item.fixture.away_club_id,
                kickoff=datetime(
                    item.match_date.year,
                    item.match_date.month,
                    item.match_date.day,
                    12,
                    0,
                    tzinfo=timezone.utc,
                ),
                source=ScheduleSource.GENERATED,
                round_number=item.fixture.round_number,
                leg_number=item.fixture.leg_number,
            )
            self._season_calendar = merge_calendars(
                self._season_calendar,
                SeasonCalendar("2026/27", "UTC", (scheduled,)),
            )

    @staticmethod
    def _cup_round_dates(round_id: str) -> tuple[date, ...]:
        dates = {
            "quarterfinal": (date(2026, 9, 9),),
            "semifinal": (date(2026, 11, 4), date(2026, 11, 11)),
            "final": (date(2027, 3, 10),),
        }
        return dates[round_id]

    @staticmethod
    def _continental_round_dates(stage_id: str) -> tuple[date, ...]:
        dates = {
            "playoff": (date(2027, 2, 24),),
            "semifinal": (date(2027, 3, 17), date(2027, 3, 24)),
            "final": (date(2027, 4, 21),),
        }
        return dates[stage_id]

    def _register_current_cup_round_schedule(self) -> None:
        bracket_round = self._cup_rounds[-1]
        dates = self._cup_round_dates(bracket_round.definition.round_id)
        for fixture in bracket_round.plan.fixtures:
            if self.home_club.id not in (fixture.home_club_id, fixture.away_club_id):
                continue
            self._register_managed_match(
                DevelopmentScheduledMatch(
                    match_date=dates[fixture.leg_number - 1],
                    competition_key="cup",
                    competition_name="Development Cup",
                    stage_id="knockout",
                    round_label=(
                        bracket_round.definition.name
                        if bracket_round.definition.leg_count == 1
                        else f"{bracket_round.definition.name} leg {fixture.leg_number}"
                    ),
                    fixture=fixture,
                )
            )

    def _register_continental_round_schedule(self, bracket_round: KnockoutBracketRound) -> None:
        stage_id = bracket_round.plan.fixtures[0].stage_id
        dates = self._continental_round_dates(stage_id)
        for fixture in bracket_round.plan.fixtures:
            if self.home_club.id not in (fixture.home_club_id, fixture.away_club_id):
                continue
            self._register_managed_match(
                DevelopmentScheduledMatch(
                    match_date=dates[fixture.leg_number - 1],
                    competition_key="continental",
                    competition_name="Development Continental",
                    stage_id=stage_id,
                    round_label=(
                        bracket_round.definition.name
                        if bracket_round.definition.leg_count == 1
                        else f"{bracket_round.definition.name} leg {fixture.leg_number}"
                    ),
                    fixture=fixture,
                )
            )

    def _next_unplayed_managed_match(self) -> DevelopmentScheduledMatch | None:
        for scheduled in self._season_calendar.fixtures_for_club(self.home_club.id):
            if scheduled.status is not ScheduledFixtureStatus.SCHEDULED:
                continue
            item = self._managed_schedule.get(scheduled.fixture_id)
            if item is not None and not self._fixture_has_result(item):
                return item
        return None

    def _fixture_has_result(self, item: DevelopmentScheduledMatch) -> bool:
        fixture_id = item.fixture.fixture_id
        if item.competition_key == "league" or item.competition_key in self._world.cups or item.competition_key in self._world.staged:
            if not hasattr(self, "_world"):
                return any(x.fixture_id == fixture_id for x in self._league_results)
            return self._world.result_for(fixture_id) is not None
        if item.competition_key == "cup":
            return any(result.fixture_id == fixture_id for result in self._cup_results)
        if item.stage_id == "league-phase":
            return any(
                result.fixture_id == fixture_id for result in self._continental_league_results
            )
        return any(
            result.fixture_id == fixture_id for result in self._continental_knockout_results
        )

    def _fixture_result_label(self, item: DevelopmentScheduledMatch) -> str | None:
        fixture_id = item.fixture.fixture_id
        if item.competition_key == "league" or item.competition_key in self._world.cups or item.competition_key in self._world.staged:
            result = self._world.result_for(fixture_id)
            if result is None:
                return None
            label = f"Played {result.home_goals}-{result.away_goals}"
            if result.penalties_home or result.penalties_away:
                label += f" ({result.penalties_home}-{result.penalties_away} pens)"
            return label
        results = self._cup_results if item.competition_key == "cup" else self._continental_knockout_results
        if item.competition_key == "continental" and item.stage_id == "league-phase":
            result = next(
                (r for r in self._continental_league_results if r.fixture_id == fixture_id),
                None,
            )
            return None if result is None else f"Played {result.home_goals}-{result.away_goals}"
        result = next((r for r in results if r.fixture_id == fixture_id), None)
        if result is None:
            return None
        label = f"Played {result.home_goals}-{result.away_goals}"
        if result.decided_by_penalties:
            label += f" ({result.penalties_home}-{result.penalties_away} pens)"
        return label

    @staticmethod
    def outcome_for_result(home_goals: int, away_goals: int, *,
                           managed_home: bool, penalties_home: int = 0,
                           penalties_away: int = 0) -> str:
        """V/E/D from the managed team's perspective; shootouts override draws."""
        home, away = home_goals, away_goals
        if penalties_home or penalties_away:
            home, away = penalties_home, penalties_away
        difference = (home - away) * (1 if managed_home else -1)
        return "V" if difference > 0 else "D" if difference < 0 else "E"

    def _fixture_outcome(self, item: DevelopmentScheduledMatch) -> str:
        fixture_id = item.fixture.fixture_id
        if item.competition_key == "league" or item.competition_key in self._world.cups or item.competition_key in self._world.staged:
            result = self._world.result_for(fixture_id)
        elif item.stage_id == "league-phase":
            result = next((r for r in self._continental_league_results if r.fixture_id == fixture_id), None)
        else:
            result = next((r for r in self._continental_knockout_results if r.fixture_id == fixture_id), None)
        if result is None:
            return ""
        return self.outcome_for_result(
            result.home_goals, result.away_goals,
            managed_home=item.fixture.home_club_id == self.home_club.id,
            penalties_home=getattr(result, "penalties_home", 0),
            penalties_away=getattr(result, "penalties_away", 0),
        )

    def _prepare_development_opponent(self) -> None:
        """Prepare the next opponent, settling genuine AI non-appearances first.

        AI players who have retired never come back just to fill a matchday XI.
        If the registered opponent cannot field eleven *available* players and
        a natural goalkeeper, the canonical fixture is settled administratively
        and the managed calendar moves on. This is not a simulated match and
        does not create players or award appearances/minutes. The manager's own
        shortages remain the user's responsibility.
        """
        from football_manager.services.player_aging import repair_managed_unavailable
        from football_manager.services.world_matches import opponent_side
        from football_manager.services.world_squads import recover_world_club

        repair_managed_unavailable(self)
        # Guard against malformed schedules making an administrative loop.
        for _ in range(200):
            if self._active_match is None:
                return
            fixture = self._active_match.fixture
            opponent_id = (fixture.away_club_id if fixture.home_club_id == self.home_club.id
                           else fixture.home_club_id)
            opponent_name = self._world_club_names.get(opponent_id, opponent_id)
            if getattr(self._world, 'football_world', None) is not None:
                registry = self._world.football_world
                if opponent_id in registry.clubs:
                    # A day progression may have resolved this rival before the
                    # managed clock is published. Never rewind or recover twice.
                    ready_on = max(self.current_date, registry.last_recovery[opponent_id])
                    recover_world_club(self._world, opponent_id, ready_on)
                try:
                    away = opponent_side(self._world, opponent_id, opponent_name)
                except ValueError as exc:
                    # Only a *registered* AI club lacking a valid matchday team
                    # is eligible for a forfeit. No other selection errors are
                    # silenced or converted into automatic results.
                    club = registry.clubs.get(opponent_id)
                    if club is None or str(exc) != f'{club.name} has no valid lineup':
                        raise
                    from football_manager.services.world_matches import _administrative_result
                    with self._world.transaction():
                        result = _administrative_result(self._world, fixture.fixture_id)
                        if result is None:
                            raise  # A different lineup bug is not a valid forfeit.
                    if result.resolver != 'administrative':
                        raise RuntimeError('Missing administrative fixture provenance')
                    self._sync_world_view()
                    next_known = self._next_unplayed_managed_match()
                    cutoff = (next_known.match_date if next_known is not None else
                              date(int(self._world.season_label[:4]) + 1, 6, 30))
                    self._world.advance_until(cutoff, protected_club_id=self.home_club.id)
                    self._sync_world_view()
                    next_match = self._next_unplayed_managed_match()
                    if next_match is None:
                        self._active_match = None
                        self.current_date = cutoff
                        self.match_played = False
                        self.last_result = None
                        self.update_dressing_room()
                        return
                    days = max(0, (next_match.match_date - self.current_date).days)
                    from football_manager.services.club_support import recover_managed_players
                    recover_managed_players(self, days=days)
                    self._active_match = next_match
                    self.current_date = next_match.match_date
                    self.match_played = False
                    self.last_result = None
                    self.update_dressing_room()
                    continue
                self.away_club, self.away_lineup, self.away_tactic = away
            else:
                if opponent_id in self._league_edition.participant_club_ids:
                    participant_index = self._league_edition.participant_club_ids.index(opponent_id)
                else:
                    participant_index = sum(ord(ch) for ch in opponent_id) % 24
                strength_gap = self._world.strengths.get(opponent_id, 65) - self._world.strengths[self.home_club.id]
                # Test-only handicap. Never alter player calibration, world strengths,
                # saved results or permanent attributes of either team.
                if self.dev_favorable_mode:
                    strength_gap -= 28
                presets = (
                    TacticalPreset.BALANCED, TacticalPreset.COUNTER_ATTACK,
                    TacticalPreset.POSSESSION, TacticalPreset.CONSTANT_PRESS,
                )
                self.away_club, self.away_lineup, self.away_tactic = _build_side(
                    club_id=opponent_id, name=opponent_name,
                    short_name=_development_short_name(opponent_name),
                    base_offset=max(-45, min(12, strength_gap + ((participant_index * 3) % 9) - 4)),
                    tactic_preset=presets[participant_index % len(presets)], names=_AWAY_NAMES,
                )
                self._initialize_familiarity(self.away_lineup, self.away_tactic, 74.0 + float(participant_index % 7))
            self._away_reference_formation = self.away_lineup.formation
            self._away_reference_style = self.away_tactic.analyze_style()
            self._away_base_tactic_familiarity = {
                player.id: player.tactical_familiarity.tactic_score(self.away_tactic.tactic_id)
                for player in self.away_club.squad.players
            }
            self._away_chemistry = {player.id: 65.0 for player in self.away_club.squad.players}
            self._sync_effective_tactic_familiarity(home=False)
            return
        raise RuntimeError('More than 200 consecutive invalid managed AI opponents')

    def _actual_match_sides(self) -> tuple[Club, Club]:
        if self.managed_is_home:
            return self.home_club, self.away_club
        return self.away_club, self.home_club

    def _league_standings(self):
        return build_league_table(
            participant_club_ids=self._league_edition.participant_club_ids,
            fixtures=self._league_edition.fixtures,
            results=tuple(self._league_results),
        )

    def _current_competition_context(self) -> CompetitionContextSnapshot:
        item = self._active_match
        fixture_id = item.fixture.fixture_id
        if item.competition_key == "league":
            return self._league_edition.context_snapshot(
                "league",
                standings=standings_snapshots(
                    self._league_standings(),
                    club_names=self._league_club_names,
                ),
            )
        if item.competition_key in self._world.cups:
            cup = self._world.cups[item.competition_key]
            plan = cup.plan_for_fixture(fixture_id)
            rule = cup.rule_for_fixture(fixture_id)
            edition = CompetitionEdition(
                edition_id=cup.edition_id,
                competition=CompetitionDefinition(
                    competition_id=cup.cup_id, name=cup.name,
                    short_name="FAC" if cup.cup_id == "fa-cup" else "EFL",
                    scope=CompetitionScope.DOMESTIC, format=CompetitionFormat.KNOCKOUT,
                    country="England",
                ),
                season_label=cup.season_label,
                participant_club_ids=plan.participant_club_ids,
                stages=(CompetitionStage(
                    stage_id=rule.round_id, name=rule.label,
                    kind=CompetitionStageKind.KNOCKOUT, order=1,
                    participant_club_ids=plan.participant_club_ids,
                    match_decider=rule.decider,
                ),),
                status=CompetitionStatus.ACTIVE, fixtures=plan.fixtures,
            )
            return knockout_context_for_fixture(
                edition=edition, stage_id=rule.round_id,
                plan=plan, fixture_id=fixture_id,
                results=tuple(
                    self._world.results[f.fixture_id].knockout_result()
                    for f in plan.fixtures if f.fixture_id in self._world.results
                ),
            )
        if item.competition_key in self._world.staged:
            staged = self._world.staged[item.competition_key]
            is_primary = item.stage_id == staged.primary_stage_id
            plan = None if is_primary else staged.plan_for_fixture(fixture_id)
            participants = (staged.participants if is_primary else plan.participant_club_ids)
            stage_kind = (CompetitionStageKind.LEAGUE_PHASE if staged.kind == "uefa"
                          else CompetitionStageKind.GROUP_STAGE) if is_primary else CompetitionStageKind.KNOCKOUT
            edition = CompetitionEdition(
                edition_id=staged.edition_id,
                competition=CompetitionDefinition(
                    competition_id=staged.competition_id, name=staged.name,
                    short_name=staged.competition_id.upper()[:8],
                    scope=CompetitionScope.CONTINENTAL if staged.kind == "uefa" else CompetitionScope.DOMESTIC,
                    format=CompetitionFormat.MULTI_STAGE, country=None if staged.kind == "uefa" else "England",
                ),
                season_label=staged.season_label,
                participant_club_ids=participants,
                stages=(CompetitionStage(
                    stage_id=item.stage_id, name=item.round_label,
                    kind=stage_kind, order=1,
                    participant_club_ids=participants,
                    match_decider=(plan.definition.deciding_match_decider if plan
                                   else MatchDecider.PENALTIES_AFTER_90 if staged.kind == 'efl-trophy'
                                   else MatchDecider.DRAW_ALLOWED),
                ),),
                status=CompetitionStatus.ACTIVE,
                fixtures=staged.primary_fixtures if is_primary else plan.fixtures,
            )
            if is_primary:
                return edition.context_snapshot(item.stage_id, standings=standings_snapshots(
                    staged.standings(self._world.results), club_names=self._world_club_names,
                ))
            return knockout_context_for_fixture(
                edition=edition, stage_id=item.stage_id, plan=plan, fixture_id=fixture_id,
                results=tuple(self._world.results[f.fixture_id].knockout_result()
                              for f in plan.fixtures if f.fixture_id in self._world.results),
            )
        if item.competition_key == "cup":
            bracket_round = next(
                bracket
                for bracket in self._cup_rounds
                if fixture_id in {fixture.fixture_id for fixture in bracket.plan.fixtures}
            )
            return knockout_context_for_fixture(
                edition=self._cup_edition,
                stage_id="knockout",
                plan=bracket_round.plan,
                fixture_id=fixture_id,
                results=tuple(self._cup_results),
            )
        if item.stage_id == "league-phase":
            return self._continental_edition.context_snapshot(
                "league-phase",
                standings=standings_snapshots(
                    self._continental_standings(),
                    club_names=self._continental_club_names,
                ),
            )
        bracket_round = next(
            bracket
            for bracket in self._continental_rounds
            if fixture_id in {fixture.fixture_id for fixture in bracket.plan.fixtures}
        )
        return knockout_context_for_fixture(
            edition=self._continental_edition,
            stage_id=item.stage_id,
            plan=bracket_round.plan,
            fixture_id=fixture_id,
            results=tuple(self._continental_knockout_results),
        )

    def _build_snapshot(self):
        managed_home = self.managed_is_home
        actual_home, actual_away = self._actual_match_sides()
        if managed_home:
            home_lineup, home_tactic, home_chemistry = (
                self.home_lineup, self.home_tactic, self._home_chemistry
            )
            away_lineup, away_tactic, away_chemistry = (
                self.away_lineup, self.away_tactic, self._away_chemistry
            )
        else:
            home_lineup, home_tactic, home_chemistry = (
                self.away_lineup, self.away_tactic, self._away_chemistry
            )
            away_lineup, away_tactic, away_chemistry = (
                self.home_lineup, self.home_tactic, self._home_chemistry
            )

        # The legacy opt-in DEV handicap is snapshot-only. Never rewrite a
        # persistent opponent's attributes or replace its registered identity.
        if self.dev_favorable_mode and self._world.football_world is not None:
            from football_manager.services.world_squads import dev_handicap_copy
            if managed_home:
                actual_away, away_lineup = dev_handicap_copy(actual_away, away_lineup)
            else:
                actual_home, home_lineup = dev_handicap_copy(actual_home, home_lineup)
        context = MatchContextSnapshot(
            kickoff=datetime(
                self.current_date.year,
                self.current_date.month,
                self.current_date.day,
                15,
                0,
                tzinfo=timezone.utc,
            ),
            competition=self._current_competition_context(),
            stadium=StadiumSnapshot(
                stadium_id=f"{actual_home.id}-ground",
                name=f"{actual_home.name} Ground",
                pitch_length_m=105.0,
                pitch_width_m=68.0,
                surface=SurfaceType.HYBRID_GRASS,
                city="England",
            ),
            conditions=MatchConditionsSnapshot(
                weather=WeatherSnapshot(
                    weather_type=WeatherType.CLOUDY,
                    temperature_c=18.0,
                    wind_kph=11.0,
                    humidity=62.0,
                ),
                pitch_condition=PitchCondition.GOOD,
            ),
            referee=RefereeSnapshot(referee_id="dev-ref", name="Development Referee"),
            kits=MatchKitSelectionSnapshot(
                home=KitSnapshot(f"{actual_home.id}-home", actual_home.id, "Home", KitType.HOME),
                away=KitSnapshot(f"{actual_away.id}-away", actual_away.id, "Away", KitType.AWAY),
            ),
        )
        return build_match_snapshot(
            match_id=f"dev-ui-{self._seed}",
            seed=self._seed,
            context=context,
            home_club=actual_home,
            home_lineup=home_lineup,
            home_tactic=home_tactic,
            away_club=actual_away,
            away_lineup=away_lineup,
            away_tactic=away_tactic,
            home_chemistry_by_player=home_chemistry,
            away_chemistry_by_player=away_chemistry,
            home_set_piece_preferences=self.set_piece_orders if managed_home else None,
            away_set_piece_preferences=self.set_piece_orders if not managed_home else None,
        )

    @staticmethod
    def _persist_post_match_state(result: FastMatchResult, club: Club) -> None:
        stats = {item.player_id: item for item in result.player_statistics if item.club_id == club.id}
        for player in club.squad.players:
            item = stats.get(player.id)
            if item is not None:
                set_post_match_condition(
                    player,
                    condition=item.condition_after,
                    fatigue=item.fatigue_after,
                )


    @staticmethod
    def _persist_position_experience(
        result: FastMatchResult,
        lineup: MatchLineup,
        club: Club,
    ) -> None:
        """Persist positional learning for players whose assignment is known.

        Phase 6.0 only has a single sandbox fixture and no full substitution
        position history. Starter minutes are enough to exercise the real domain
        learning model now; the future calendar/match-history layer can feed exact
        stint-by-stint positions through the same Player API.
        """

        stats = {
            item.player_id: item
            for item in result.player_statistics
            if item.club_id == club.id
        }
        segments = [s for s in result.role_segments if s.club_id == club.id]
        if segments:
            players = {p.id: p for p in club.squad.players}
            for segment in segments:
                players[segment.player_id].record_position_minutes(Position(segment.position), float(segment.minutes))
            return
        for entry in lineup.starters:
            item = stats.get(entry.player.id)
            if item is None or item.minutes <= 0:
                continue
            position = lineup.formation.slot(entry.slot_id).position
            entry.player.record_position_minutes(position, float(item.minutes))

    def _persist_match_progression(
        self, result: FastMatchResult, lineup: MatchLineup, tactic: Tactic,
        club: Club, *, home: bool,
    ) -> None:
        """Use real minutes/rating and actual starter roles for ACT state.

        Keep earned tactical mastery in the plan's existing baseline so normal
        changes to formations or instructions cannot silently erase it.
        """
        participants = {item.player_id: item for item in result.player_statistics
                        if item.club_id == club.id and item.minutes > 0}
        starter_roles = {entry.player.id: tactic.role_for_slot(entry.slot_id).role_id
                         for entry in lineup.starters}
        base_scores = (self._home_base_tactic_familiarity if home
                       else self._away_base_tactic_familiarity)
        for player in club.squad.players:
            item = participants.get(player.id)
            if item is None:
                continue
            role_minutes = None
            segments = [s for s in result.role_segments
                        if s.club_id == club.id and s.player_id == player.id]
            if segments:
                role_minutes = {}
                for segment in segments:
                    role_minutes[segment.role_id] = role_minutes.get(segment.role_id, 0) + segment.minutes
            gained = apply_player_match_progression(
                player, minutes=item.minutes, match_rating=item.match_rating,
                role_id=starter_roles.get(player.id), tactic_id=tactic.tactic_id,
                role_minutes=role_minutes,
            )
            if gained:
                base_scores[player.id] = min(
                    100.0, base_scores.get(player.id, 0.0) + gained
                )
        self._sync_effective_tactic_familiarity(home=home)

    @staticmethod
    def _initialize_familiarity(lineup: MatchLineup, tactic: Tactic, score: float) -> None:
        starter_ids = {entry.player.id for entry in lineup.starters}
        for player in lineup.selected_players:
            player_score = score if player.id in starter_ids else score - 5.0
            player.tactical_familiarity.set_tactic_score(tactic.tactic_id, player_score)

            base_role = default_role_for_position(player.primary_position)
            for role in roles_for_position(player.primary_position):
                similarity = role_similarity(base_role, role)
                role_score = max(35.0, min(player_score, player_score - (100.0 - similarity) * 0.35))
                player.tactical_familiarity.set_role_score(role.role_id, role_score)

    def _sync_effective_tactic_familiarity(self, *, home: bool) -> None:
        if home:
            club = self.home_club
            lineup = self.home_lineup
            tactic = self.home_tactic
            reference_formation = self._home_reference_formation
            reference_style = self._home_reference_style
            base_scores = self._home_base_tactic_familiarity
        else:
            club = self.away_club
            lineup = self.away_lineup
            tactic = self.away_tactic
            reference_formation = self._away_reference_formation
            reference_style = self._away_reference_style
            base_scores = self._away_base_tactic_familiarity

        similarity = _plan_similarity(
            reference_formation=reference_formation,
            current_formation=lineup.formation,
            reference_style=reference_style,
            current_style=tactic.analyze_style(),
        )
        retention = 0.55 + 0.45 * similarity
        for player in club.squad.players:
            base = base_scores.get(player.id, 65.0)
            player.tactical_familiarity.set_tactic_score(tactic.tactic_id, base * retention)


def _mean_values(values: Iterable[float]) -> float:
    values = tuple(values)
    return sum(values) / len(values) if values else 0.0


def _instruction_display_value(value: object) -> str:
    if isinstance(value, bool):
        return "on" if value else "off"
    if isinstance(value, Enum):
        enum_value = getattr(value, "value", None)
        if isinstance(enum_value, str):
            return enum_value
        return value.name.lower()
    return str(value)


def _instruction_options(value: object) -> tuple[str, ...]:
    if isinstance(value, bool):
        return ("off", "on")
    if isinstance(value, Enum):
        options: list[str] = []
        for item in type(value):
            enum_value = getattr(item, "value", None)
            options.append(enum_value if isinstance(enum_value, str) else item.name.lower())
        return tuple(options)
    return ()


def _parse_instruction_value(current: object, raw_value: str) -> object:
    if isinstance(current, bool):
        normalized = raw_value.strip().lower()
        if normalized not in {"on", "off"}:
            raise ValueError("boolean tactical values must be 'on' or 'off'")
        return normalized == "on"
    if isinstance(current, Enum):
        enum_type = type(current)
        for item in enum_type:
            if _instruction_display_value(item) == raw_value:
                return item
        raise ValueError(f"invalid value {raw_value!r} for {enum_type.__name__}")
    raise ValueError(f"unsupported tactical instruction type: {type(current).__name__}")


def _formation_similarity(reference: Formation, current: Formation) -> float:
    reference_positions = [slot.position for slot in reference.slots]
    current_positions = [slot.position for slot in current.slots]
    remaining = list(current_positions)
    matches = 0
    for position in reference_positions:
        if position in remaining:
            matches += 1
            remaining.remove(position)
    return matches / 11.0


def _style_similarity(reference: TacticalStyleAnalysis, current: TacticalStyleAnalysis) -> float:
    fields_to_compare = (
        "possession",
        "pressing",
        "directness",
        "defensive_depth",
        "tempo",
        "width",
        "risk",
    )
    mean_difference = _mean_values(
        abs(float(getattr(reference, name)) - float(getattr(current, name)))
        for name in fields_to_compare
    )
    return max(0.0, min(1.0, 1.0 - mean_difference / 100.0))


def _plan_similarity(
    *,
    reference_formation: Formation,
    current_formation: Formation,
    reference_style: TacticalStyleAnalysis,
    current_style: TacticalStyleAnalysis,
) -> float:
    return 0.35 * _formation_similarity(reference_formation, current_formation) + 0.65 * _style_similarity(
        reference_style, current_style
    )


def _build_development_chemistry(club: Club, *, starter_ids: set[str]) -> dict[str, float]:
    chemistry: dict[str, float] = {}
    for index, player in enumerate(club.squad.players):
        base = 77.0 if player.id in starter_ids else 69.0
        chemistry[player.id] = max(0.0, min(100.0, base + ((index * 3) % 7) - 3.0))
    return chemistry


def _reassign_lineup_to_formation(lineup: MatchLineup, formation: Formation) -> MatchLineup:
    players = lineup.starting_players

    @lru_cache(maxsize=None)
    def best(slot_index: int, used_mask: int) -> tuple[float, tuple[int, ...]]:
        if slot_index == len(formation.slots):
            return 0.0, ()
        slot = formation.slots[slot_index]
        best_score = float("-inf")
        best_assignment: tuple[int, ...] = ()
        for index, player in enumerate(players):
            if used_mask & (1 << index):
                continue
            familiarity = player.familiarity_for(slot.position)
            primary_bonus = 4.0 if player.primary_position is slot.position else 0.0
            score, assignment = best(slot_index + 1, used_mask | (1 << index))
            total = familiarity + primary_bonus + score
            if total > best_score:
                best_score = total
                best_assignment = (index,) + assignment
        return best_score, best_assignment

    _, assignment = best(0, 0)
    starters = tuple(
        LineupEntry(slot.slot_id, players[player_index])
        for slot, player_index in zip(formation.slots, assignment, strict=True)
    )
    return MatchLineup(
        club_id=lineup.club_id,
        formation=formation,
        starters=starters,
        bench=lineup.bench,
    )


def _development_formations() -> tuple[Formation, ...]:
    # Catalogue and coordinates are shared with both live frontends.
    from .formations import development_formations

    return development_formations()


def _formation_433() -> Formation:
    # Preserve the historical default and its serialized formation ID.
    return _development_formations()[0]


def _formation_4231() -> Formation:
    return _development_formations()[1]


def _formation_442() -> Formation:
    return _development_formations()[2]


def _formation_3421() -> Formation:
    return _development_formations()[3]


def _development_short_name(name: str) -> str:
    words = [word for word in name.replace("-", " ").split() if word]
    if len(words) >= 2:
        return "".join(word[0] for word in words[:3]).upper()
    return name[:3].upper()


def _build_side(
    *,
    club_id: str,
    name: str,
    short_name: str,
    base_offset: int,
    tactic_preset: TacticalPreset,
    names: tuple[str, ...],
) -> tuple[Club, MatchLineup, Tactic]:
    formation = _formation_433()
    starter_specs = (
        (Position.GK, 77, 63, 72),
        (Position.RB, 73, 82, 78),
        (Position.RCB, 78, 69, 74),
        (Position.LCB, 76, 71, 75),
        (Position.LB, 74, 86, 79),
        (Position.DM, 79, 83, 82),
        (Position.RCM, 81, 79, 76),
        (Position.LCM, 77, 75, 84),
        (Position.RW, 84, 72, 81),
        (Position.ST, 82, 68, 77),
        (Position.LW, 80, 88, 85),
    )
    bench_specs = (
        (Position.GK, 69, 58, 71),
        (Position.CB, 72, 74, 78),
        (Position.RB, 70, 89, 86),
        (Position.CM, 75, 77, 81),
        (Position.AM, 78, 66, 73),
        (Position.RW, 76, 92, 88),
        (Position.ST, 74, 61, 69),
    )
    specs = starter_specs + bench_specs
    if len(names) != len(specs):
        raise ValueError("development side name/spec counts must match")

    players = tuple(
        _make_player(
            player_id=f"{club_id}-{index + 1}",
            full_name=full_name,
            position=position,
            base=max(1, min(100, base + base_offset)),
            stamina=stamina,
            natural_fitness=natural_fitness,
            index=index,
        )
        for index, ((position, base, stamina, natural_fitness), full_name) in enumerate(zip(specs, names, strict=True))
    )
    starters = players[:11]
    bench = players[11:]
    club = Club(
        club_id=club_id,
        name=name,
        short_name=short_name,
        country="England",
        squad=Squad.from_players(players),
    )
    lineup = MatchLineup(
        club_id=club.id,
        formation=formation,
        starters=tuple(
            LineupEntry(slot.slot_id, player)
            for slot, player in zip(formation.slots, starters, strict=True)
        ),
        bench=bench,
    )
    tactic = Tactic.from_preset(
        tactic_id=f"{club_id}-primary",
        name=f"{name} Primary",
        formation=formation,
        preset=tactic_preset,
    )
    return club, lineup, tactic


def _make_player(
    *,
    player_id: str,
    full_name: str,
    position: Position,
    base: int,
    stamina: int,
    natural_fitness: int,
    index: int,
) -> Player:
    first_name, last_name = full_name.split(" ", 1)
    tech = _technical_for(position, base)
    mental = MentalAttributes(
        vision=_cap(base + (3 if position in _CREATIVE_POSITIONS else 0)),
        decisions=_cap(base + 1),
        anticipation=_cap(base + 2),
        concentration=_cap(base + (3 if position in _DEFENSIVE_POSITIONS else 0)),
        composure=_cap(base + 1),
        positioning=_cap(base + (4 if position in _DEFENSIVE_POSITIONS else -1)),
        off_the_ball=_cap(base + (4 if position in _ATTACKING_POSITIONS else 0)),
        teamwork=_cap(base + 1),
        work_rate=_cap(base + 2),
        aggression=_cap(base - 2 + index % 5),
        bravery=_cap(base + (2 if position in _DEFENSIVE_POSITIONS else 0)),
        creativity=_cap(base + (4 if position in _CREATIVE_POSITIONS else -2)),
        tactical_intelligence=_cap(base + 2),
        adaptability=_cap(62 + (index * 3) % 28),
    )
    physical = PhysicalAttributes(
        pace=_cap(base + (5 if position in _WIDE_POSITIONS else 0)),
        acceleration=_cap(base + (5 if position in _WIDE_POSITIONS else 0)),
        strength=_cap(base + (5 if position in _DEFENSIVE_POSITIONS | {Position.ST} else -2)),
        stamina=stamina,
        agility=_cap(base + (4 if position in _WIDE_POSITIONS | _ATTACKING_POSITIONS else 0)),
        balance=_cap(base),
        jumping_reach=_cap(base + (6 if position in _DEFENSIVE_POSITIONS | {Position.ST} else -4)),
        natural_fitness=natural_fitness,
    )
    goalkeeping = None
    if position is Position.GK:
        goalkeeping = GoalkeepingAttributes(
            reflexes=_cap(base + 5),
            handling=_cap(base + 2),
            one_on_ones=_cap(base + 3),
            aerial_reach=_cap(base + 2),
            command_of_area=_cap(base),
            kicking=_cap(base - 2),
            throwing=_cap(base - 1),
            goalkeeper_positioning=_cap(base + 4),
        )

    primary_familiarity = 95.0
    secondary: dict[Position, float] = {position: primary_familiarity}
    if position in {Position.RCB, Position.LCB}:
        secondary[Position.CB] = 90.0
    if position is Position.CB:
        secondary[Position.RCB] = 80.0
        secondary[Position.LCB] = 80.0
    if position in {Position.RCM, Position.LCM}:
        secondary[Position.CM] = 90.0
    if position is Position.CM:
        secondary[Position.RCM] = 80.0
        secondary[Position.LCM] = 80.0

    return Player(
        identity=PlayerIdentity(
            player_id=player_id,
            first_name=first_name,
            last_name=last_name,
            birth_date=date(1998 + (index % 7), 1 + (index % 11), 1 + (index * 2) % 27),
            nationality="England",
            dominant_foot=Foot.LEFT if index % 4 == 0 else Foot.RIGHT,
        ),
        attributes=PlayerAttributes(
            technical=tech,
            mental=mental,
            physical=physical,
            goalkeeping=goalkeeping,
        ),
        positional_familiarity=PositionalFamiliarity(secondary),
        original_position=position,
        primary_position=position,
        state=PlayerState(
            fitness=float(100 - (index % 4) * 3),
            fatigue=float((index % 4) * 2),
            form=float(58 + (index * 5) % 29),
            morale=float(61 + (index * 4) % 25),
            confidence=float(57 + (index * 6) % 31),
            match_sharpness=float(62 + (index * 3) % 26),
        ),
        tactical_familiarity=TacticalFamiliarity(),
    )


def _technical_for(position: Position, base: int) -> TechnicalAttributes:
    defensive = position in _DEFENSIVE_POSITIONS
    attacking = position in _ATTACKING_POSITIONS
    creative = position in _CREATIVE_POSITIONS
    wide = position in _WIDE_POSITIONS
    if position is Position.GK:
        base = max(45, base - 20)
    return TechnicalAttributes(
        passing=_cap(base + (4 if creative else 0)),
        technique=_cap(base + (3 if creative or attacking else 0)),
        finishing=_cap(base + (7 if attacking else -7)),
        first_touch=_cap(base + (4 if creative or attacking else 0)),
        dribbling=_cap(base + (6 if wide or attacking else -3)),
        crossing=_cap(base + (7 if wide else -4)),
        tackling=_cap(base + (7 if defensive else -8)),
        heading=_cap(base + (6 if defensive or position is Position.ST else -4)),
        long_shots=_cap(base + (3 if creative else -2)),
        shot_power=_cap(base + (3 if attacking else 0)),
        marking=_cap(base + (7 if defensive else -9)),
        set_pieces=_cap(base + (4 if creative else -3)),
        penalties=_cap(base + (5 if attacking else -2)),
    )


def _cap(value: int) -> int:
    return max(1, min(100, int(value)))


_DEFENSIVE_POSITIONS = {Position.RB, Position.RCB, Position.CB, Position.LCB, Position.LB, Position.DM}
_ATTACKING_POSITIONS = {Position.AM, Position.RW, Position.LW, Position.SS, Position.ST}
_CREATIVE_POSITIONS = {Position.DM, Position.RCM, Position.CM, Position.LCM, Position.AM}
_WIDE_POSITIONS = {Position.RB, Position.LB, Position.RWB, Position.LWB, Position.RW, Position.LW}

_HOME_NAMES = (
    "Daniel Mercer",
    "Lewis Hart",
    "Nathan Cole",
    "Elliot Price",
    "Jack Holloway",
    "Marcus Reed",
    "Oliver Grant",
    "Theo Bennett",
    "Noah Clarke",
    "Mason Ward",
    "Jamie Foster",
    "Adam Wells",
    "Ryan Brooks",
    "Ben Parker",
    "Callum Stone",
    "Ethan Walsh",
    "Luke Spencer",
    "Sam Turner",
)

_AWAY_NAMES = (
    "George Hale",
    "Dylan Moore",
    "Connor Mills",
    "Harry Nolan",
    "Alfie Shaw",
    "Isaac Ford",
    "Leo Barker",
    "Max Sutton",
    "Charlie Dean",
    "Jacob Ellis",
    "Finley Wood",
    "Tom Rhodes",
    "Alex Fisher",
    "Josh Webb",
    "Owen Palmer",
    "Freddie Cross",
    "Archie Bell",
    "Henry Lane",
)
