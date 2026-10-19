from __future__ import annotations

from dataclasses import dataclass, field, replace
import math

from football_manager.domain import (
    MatchDecider,
    MatchSnapshot,
    PlayerMatchSnapshot,
    Position,
    TeamMatchSnapshot,
)
from football_manager.domain.snapshot_assignment import assign_match_player

from .conditioning import physical_state_after
from .models import (
    FastCardEvent,
    FastCardType,
    FastGoalEvent,
    FastMatchDecision,
    FastMatchResult,
    FastPenaltyKickEvent,
    FastPlayerStatistics,
    FastSubstitutionEvent,
    FastTeamStatistics,
)
from .profiles import FastTeamProfile, build_fast_team_profile
from .randomness import FastMatchRandom
from . import tactical_effects as tactical
from football_manager.domain.tactical_geometry import phase_points


@dataclass(frozen=True, slots=True)
class FastSimulationConfig:
    base_shots_per_team: float = 12.2
    base_passes_per_team: float = 425.0
    base_fouls_per_team: float = 11.4
    base_corners_per_team: float = 4.8
    home_advantage_rating: float = 3.1
    home_shot_advantage: float = 1.10
    chance_quality_scale: float = 0.96
    base_card_probability: float = 0.158
    assist_probability: float = 0.72
    extra_time_first_half_rate: float = 0.76
    extra_time_second_half_rate: float = 0.68
    penalty_base_probability: float = 0.755
    penalty_min_probability: float = 0.50
    penalty_max_probability: float = 0.94


@dataclass(frozen=True, slots=True)
class _ShotRecord:
    player_id: str
    assist_player_id: str | None
    xg: float
    on_target: bool
    goal: bool
    minute: int
    extra_time: bool


@dataclass(slots=True)
class _PlayerAccumulator:
    goals: int = 0
    assists: int = 0
    shots: int = 0
    shots_on_target: int = 0
    xg: float = 0.0
    passes_attempted: int = 0
    passes_completed: int = 0
    fouls: int = 0
    yellow_cards: int = 0
    red_cards: int = 0


@dataclass(slots=True)
class _TeamRuntime:
    team: TeamMatchSnapshot
    profile: FastTeamProfile
    possession: float = 50.0
    passes_attempted: int = 0
    passes_completed: int = 0
    fouls: int = 0
    yellow_cards: int = 0
    red_cards: int = 0
    corners: int = 0
    shots: list[_ShotRecord] = field(default_factory=list)
    cards: list[FastCardEvent] = field(default_factory=list)
    substitutions: list[FastSubstitutionEvent] = field(default_factory=list)
    participants: dict[str, PlayerMatchSnapshot] = field(default_factory=dict)
    entered_minute: dict[str, int] = field(default_factory=dict)
    exited_minute: dict[str, int] = field(default_factory=dict)
    dismissed_at: dict[str, int] = field(default_factory=dict)
    booked_fouls: dict[str, int] = field(default_factory=dict)
    tactical_events: list = field(default_factory=list)
    exposures: list = field(default_factory=list)

    def __post_init__(self) -> None:
        if not self.participants:
            self.participants = {player.player_id: player for player in self.team.starters}
        if not self.entered_minute:
            self.entered_minute = {player.player_id: 0 for player in self.team.starters}

    def player(self, player_id: str) -> PlayerMatchSnapshot:
        try:
            return self.participants[player_id]
        except KeyError as exc:
            raise KeyError(f"player {player_id!r} did not participate for {self.team.club_id!r}") from exc

    def minutes_for(self, player_id: str, match_minutes: int) -> int:
        entered = self.entered_minute.get(player_id, 0)
        exited = min(self.exited_minute.get(player_id, match_minutes), self.dismissed_at.get(player_id, match_minutes))
        return max(0, min(match_minutes, exited) - min(match_minutes, entered))

    def active_starters_at(self, minute: int) -> tuple[PlayerMatchSnapshot, ...]:
        """Only players actually on the pitch at this minute may act."""
        return tuple(
            player for player in self.team.starters
            if self.entered_minute.get(player.player_id, 0) < minute
            and self.exited_minute.get(player.player_id, 121) >= minute
            and self.dismissed_at.get(player.player_id, 121) >= minute
        )

    def participating_players(self, match_minutes: int) -> tuple[PlayerMatchSnapshot, ...]:
        return tuple(
            player
            for player in self.participants.values()
            if self.minutes_for(player.player_id, match_minutes) > 0
        )


class FastMatchSimulator:
    """Instant seeded match simulation that never instantiates 2D agents.

    Team quality defines probability distributions rather than a preselected
    winner.  Results emerge from possession, chance volume, individual shots,
    finishing/goalkeeping, discipline and other compact football processes.
    """

    def __init__(self, config: FastSimulationConfig | None = None) -> None:
        self.config = config or FastSimulationConfig()

    def simulate(self, snapshot: MatchSnapshot, *, tactical_plans: tuple = (),
                 ai_coaches: dict | None = None) -> FastMatchResult:
        from .plans import validate_changes
        validate_changes(snapshot, tactical_plans)
        root = FastMatchRandom(snapshot.seed)
        home = _TeamRuntime(snapshot.home_team, build_fast_team_profile(snapshot.home_team))
        away = _TeamRuntime(snapshot.away_team, build_fast_team_profile(snapshot.away_team))
        if ai_coaches:
            from .ai_coaching import adjusted_profile
            for side, opponent in ((home, away), (away, home)):
                coach = ai_coaches.get(side.team.club_id)
                if coach is not None:
                    if coach.club_id != side.team.club_id:
                        raise ValueError("AI coach club does not match match side")
                    decisive = snapshot.context.competition.match_decider is not MatchDecider.DRAW_ALLOWED
                    side.profile = adjusted_profile(
                        side.profile, coach, importance=0.85 if decisive else 0.45,
                        opponent_current=opponent.profile.current,
                    )

        home.possession = self._home_possession(home.profile, away.profile, root.fork("possession"))
        away.possession = round(100.0 - home.possession, 1)
        home.possession = round(100.0 - away.possession, 1)

        if tactical_plans:
            self._run_planned_period(snapshot, home, away, tactical_plans, root, start=1, end=90)
        else:
            # Discipline is established before the opportunities it can affect.
            # Named RNG streams keep the no-dismissal shot distribution unchanged.
            self._simulate_discipline_period(snapshot, home, away, root=root, minute_start=1, minute_end=90)

            self._simulate_shot_windows(
                home,
                away,
                minutes=90,
                minute_start=1,
                minute_end=90,
                home_advantage=True,
                random=root.fork("home/shots/regulation"),
            )
            self._simulate_shot_windows(
                away,
                home,
                minutes=90,
                minute_start=1,
                minute_end=90,
                home_advantage=False,
                random=root.fork("away/shots/regulation"),
            )

            # Risk when leading uses the established risk equations, but may only
            # change future chances *after* the score actually favors that side.
            self._apply_score_dependent_risk(
                home, away, random=root.fork("leading-risk/regulation"),
            )

            # Resolve late score-dependent instructions against chronological chances.
            self._apply_regulation_game_management(home, away, root.fork("game-management"))

        regulation_home_goals = sum(shot.goal for shot in home.shots)
        regulation_away_goals = sum(shot.goal for shot in away.shots)
        extra_time_played = False
        decision = FastMatchDecision.REGULATION
        aggregate_home, aggregate_away = self._aggregate_score(snapshot, home, away)
        tied = aggregate_home == aggregate_away
        decider = snapshot.context.competition.match_decider

        if tied and decider is MatchDecider.EXTRA_TIME_AND_PENALTIES:
            extra_time_played = True
            extra_subs = snapshot.context.competition.extra_time_additional_substitutions
            self._apply_extra_time_substitutions(home, extra_subs, root.fork("home/extra_time/substitutions"))
            self._apply_extra_time_substitutions(away, extra_subs, root.fork("away/extra_time/substitutions"))
            if tactical_plans:
                self._run_planned_period(snapshot, home, away, tactical_plans, root,
                                         start=91, end=105, pace=self.config.extra_time_first_half_rate)
                self._run_planned_period(snapshot, home, away, tactical_plans, root,
                                         start=106, end=120, pace=self.config.extra_time_second_half_rate)
            else:
                self._simulate_discipline_period(snapshot, home, away, root=root, minute_start=91, minute_end=120)

                for half_index, (minute_start, minute_end, pace) in enumerate(
                    (
                        (91, 105, self.config.extra_time_first_half_rate),
                        (106, 120, self.config.extra_time_second_half_rate),
                    ),
                    start=1,
                ):
                    elapsed_before = 90 + (half_index - 1) * 15
                    home_energy = self._extra_time_energy(home, elapsed_before)
                    away_energy = self._extra_time_energy(away, elapsed_before)
                    self._simulate_shot_windows(
                        home,
                        away,
                        minutes=15,
                        minute_start=minute_start,
                        minute_end=minute_end,
                        home_advantage=True,
                        random=root.fork(f"home/shots/extra_time/{half_index}"),
                        pace_factor=pace,
                        attacker_energy=home_energy,
                        defender_energy=away_energy,
                    )
                    self._simulate_shot_windows(
                        away,
                        home,
                        minutes=15,
                        minute_start=minute_start,
                        minute_end=minute_end,
                        home_advantage=False,
                        random=root.fork(f"away/shots/extra_time/{half_index}"),
                        pace_factor=pace,
                        attacker_energy=away_energy,
                        defender_energy=home_energy,
                    )
                    self._apply_score_dependent_risk(
                        home, away,
                        minute_start=minute_start,
                        minute_end=minute_end,
                        pace_factor=pace,
                        home_energy=home_energy,
                        away_energy=away_energy,
                        random=root.fork(f"leading-risk/extra-time/{half_index}"),
                    )

            decision = FastMatchDecision.EXTRA_TIME
            aggregate_home, aggregate_away = self._aggregate_score(snapshot, home, away)
            tied = aggregate_home == aggregate_away

        final_profiles = (home.profile, away.profile)
        if tactical_plans:
            home.profile, away.profile = self._average_plan_profile(home), self._average_plan_profile(away)
            home.possession = round(sum((end - start + 1) * possession
                for start, end, _, _, possession in home.exposures) / (120 if extra_time_played else 90), 1)
            away.possession = round(100 - home.possession, 1)
        self._simulate_non_shot_statistics(
            snapshot,
            home,
            away,
            extra_time_played=extra_time_played,
            root=root,
        )

        home.profile, away.profile = final_profiles
        penalties_home = penalties_away = 0
        penalty_kicks: tuple[FastPenaltyKickEvent, ...] = ()
        winner_club_id: str | None
        if tied and decider in {
            MatchDecider.EXTRA_TIME_AND_PENALTIES,
            MatchDecider.PENALTIES_AFTER_90,
        }:
            match_minutes = 120 if extra_time_played else 90
            penalties_home, penalties_away, penalty_kicks = self._penalty_shootout(
                home,
                away,
                root.fork("penalty_shootout"),
                match_minutes=match_minutes,
            )
            decision = FastMatchDecision.PENALTIES
            winner_club_id = home.team.club_id if penalties_home > penalties_away else away.team.club_id
        elif aggregate_home > aggregate_away:
            winner_club_id = home.team.club_id
        elif aggregate_away > aggregate_home:
            winner_club_id = away.team.club_id
        else:
            winner_club_id = None
            decision = FastMatchDecision.DRAW

        goals = self._goal_events(home, away)
        home_goals = sum(shot.goal for shot in home.shots)
        away_goals = sum(shot.goal for shot in away.shots)
        extra_time_home_goals = home_goals - regulation_home_goals
        extra_time_away_goals = away_goals - regulation_away_goals
        aggregate_home, aggregate_away = self._aggregate_score(snapshot, home, away)

        home_stats = self._freeze_team_statistics(home, opponent=away)
        away_stats = self._freeze_team_statistics(away, opponent=home)
        player_statistics = self._player_statistics(
            home,
            away,
            goals=goals,
            extra_time_played=extra_time_played,
            winner_club_id=winner_club_id,
            root=root,
        )
        cards = tuple(sorted(home.cards + away.cards, key=lambda item: (item.minute, item.club_id)))
        substitutions = tuple(
            sorted(home.substitutions + away.substitutions, key=lambda item: (item.minute, item.club_id, item.player_in_id))
        )

        return FastMatchResult(
            match_id=snapshot.match_id,
            home_club_id=home.team.club_id,
            away_club_id=away.team.club_id,
            home_goals=home_goals,
            away_goals=away_goals,
            aggregate_home_goals=aggregate_home,
            aggregate_away_goals=aggregate_away,
            winner_club_id=winner_club_id,
            decision=decision,
            penalties_home=penalties_home,
            penalties_away=penalties_away,
            regulation_home_goals=regulation_home_goals,
            regulation_away_goals=regulation_away_goals,
            extra_time_home_goals=extra_time_home_goals,
            extra_time_away_goals=extra_time_away_goals,
            statistics_home=home_stats,
            statistics_away=away_stats,
            goals=goals,
            cards=cards,
            substitutions=substitutions,
            penalty_kicks=penalty_kicks,
            player_statistics=player_statistics,
            tactical_events=tuple(sorted(home.tactical_events + away.tactical_events, key=lambda e: (e.minute, e.club_id))),
            role_segments=self._role_segments(home, 120 if extra_time_played else 90) + self._role_segments(away, 120 if extra_time_played else 90),
        )

    def _run_planned_period(self, snapshot, home, away, changes, root, *, start, end, pace=1.0):
        """Chronological path for explicit plans: never change already played events.

        A minute is resolved using the real score at its start. Events, role
        exposures and physical workload follow the active plan. The ordinary
        no-plan path remains the legacy calibrated window simulation.
        """
        from .models import FastTacticalEvent
        by_minute = {}
        for change in changes:
            by_minute.setdefault(change.rule.minute, []).append(change)
        for minute in range(start, end + 1):
            rng = root.fork(f"planned/minute/{minute}")
            for change in sorted(by_minute.get(minute, ()), key=lambda c: c.team.club_id):
                side, opponent = (home, away) if change.team.club_id == home.team.club_id else (away, home)
                own = sum(s.goal for s in side.shots)
                conceded = sum(s.goal for s in opponent.shots)
                applies = change.rule.matches(own, conceded)
                if applies:
                    self._apply_match_plan(side, change)
                side.tactical_events.append(FastTacticalEvent(
                    minute, side.team.club_id, change.rule.plan, change.name,
                    applies, change.rule.condition, own, conceded,
                ))
            # Avoid changing a team's possession roll for unrelated tactical rules.
            raw_home, raw_away = home.profile, away.profile
            home.possession = self._home_possession(raw_home, raw_away, root.fork('planned/possession'))
            away.possession = round(100 - home.possession, 1)
            scores = (sum(s.goal for s in home.shots), sum(s.goal for s in away.shots))
            for side, own, other in ((home, scores[0], scores[1]), (away, scores[1], scores[0])):
                if own > other:
                    side.profile = replace(side.profile, risk=self._clamp(
                        side.profile.risk + (side.profile.risk_when_leading - 50) / 3, 0, 100))
            self._simulate_discipline_period(snapshot, home, away, root=rng,
                                               minute_start=minute, minute_end=minute)
            waste = 1.0
            if minute >= 76:
                leader = home if scores[0] > scores[1] else away if scores[1] > scores[0] else None
                if leader is not None:
                    waste -= leader.profile.time_wasting / 100 * .25
            for label, side, opponent, own, other, advantage in (
                ('home', home, away, scores[0], scores[1], True),
                ('away', away, home, scores[1], scores[0], False),
            ):
                urgency = 1.0
                if minute >= 65 and own < other:
                    urgency += max(0, side.profile.urgency_when_trailing - 50) / 50 * .20
                energy = self._extra_time_energy(side, minute - 1) if minute > 90 else 1.0
                opposition_energy = self._extra_time_energy(opponent, minute - 1) if minute > 90 else 1.0
                self._simulate_shot_windows(side, opponent, minutes=1, minute_start=minute, minute_end=minute,
                    home_advantage=advantage, random=rng.fork(f'{label}/shots'),
                    pace_factor=pace * waste * urgency, attacker_energy=energy, defender_energy=opposition_energy)
                signature = (side.profile, side.team.starters, side.possession)
                if side.exposures and side.exposures[-1][1] == minute - 1 and side.exposures[-1][2:] == signature:
                    previous = side.exposures[-1]
                    side.exposures[-1] = (previous[0], minute, *signature)
                else:
                    side.exposures.append((minute, minute, *signature))
            home.profile, away.profile = raw_home, raw_away

    def _apply_match_plan(self, runtime, change):
        """Reassign the present XI, following real substitutions; never revive a red card."""
        current = {p.player_id: p for p in runtime.team.starters}
        replacements = {s.player_out_id: s.player_in_id for s in runtime.substitutions}
        starters = []
        for planned in change.team.starters:
            player_id = planned.player_id
            visited = set()
            while player_id not in current and player_id in replacements and player_id not in visited:
                visited.add(player_id)
                player_id = replacements[player_id]
            if player_id not in current:
                raise ValueError('plan cannot identify an active lineup member')
            source = current[player_id]
            # The prebuilt plan has correctly adjusted tactical familiarity for
            # original starters. A real substitute keeps their own familiarity.
            if player_id == planned.player_id:
                source = replace(source, familiarity=planned.familiarity)
            slot = change.team.tactic.slot(planned.assigned_slot_id)
            assigned = assign_match_player(source, slot_id=slot.slot_id, position=slot.position,
                role_id=slot.role_id, role_name=slot.role_name,
                tactic_id=change.team.tactic.tactic_id, instructions=slot.effective_instructions)
            starters.append(assigned)
        runtime.team = replace(runtime.team, formation=change.team.formation,
                               tactic=change.team.tactic, starters=tuple(starters))
        for player in starters:
            runtime.participants[player.player_id] = player
        runtime.profile = build_fast_team_profile(runtime.team)

    @staticmethod
    def _exposure_minutes(runtime, player_id, start, end, match_minutes):
        lo = max(start, runtime.entered_minute.get(player_id, 0) + 1)
        hi = min(end, match_minutes, runtime.exited_minute.get(player_id, match_minutes),
                 runtime.dismissed_at.get(player_id, match_minutes))
        return lo, hi, max(0, hi - lo + 1)

    def _planned_physical_state(self, runtime, player, minutes, match_minutes):
        from football_manager.domain.conditioning import match_condition_state
        from .conditioning import player_workload_factor
        exposure, elapsed = 0.0, 0
        def time_weight(value):
            return min(value, 90) / 90 + max(0, value - 90) / 30 * .60
        for start, end, profile, players, _ in runtime.exposures:
            actual = next((p for p in players if p.player_id == player.player_id), None)
            if actual is None:
                continue
            _, _, duration = self._exposure_minutes(runtime, player.player_id, start, end, match_minutes)
            exposure += (time_weight(elapsed + duration) - time_weight(elapsed)) * player_workload_factor(actual, profile)
            elapsed += duration
        if elapsed != minutes:
            raise ValueError('physical exposure differs from played minutes')
        workload = exposure / max(.0001, time_weight(minutes))
        return match_condition_state(starting_condition=player.state.condition, starting_fatigue=player.state.fatigue,
            stamina=self._attr(player, 'physical.stamina'), minutes=minutes, workload_factor=workload)

    @staticmethod
    def _average_plan_profile(runtime):
        from dataclasses import fields
        total = sum(end - start + 1 for start, end, *_ in runtime.exposures)
        if not total:
            return runtime.profile
        def avg(obj, name):
            return sum((end - start + 1) * getattr(obj(profile), name)
                       for start, end, profile, *_ in runtime.exposures) / total
        profile_changes = {f.name: avg(lambda p: p, f.name) for f in fields(runtime.profile)
                           if type(getattr(runtime.profile, f.name)) in (int, float)}
        feature = runtime.profile.tactical_features
        changes = {f.name: avg(lambda p: p.tactical_features, f.name) for f in fields(feature)
                   if type(getattr(feature, f.name)) in (int, float)}
        shape = feature.shape
        shape = replace(shape, **{f.name: avg(lambda p: p.tactical_features.shape, f.name) for f in fields(shape)})
        feature = replace(feature, **changes, shape=shape)
        return replace(runtime.profile, **profile_changes, tactical_features=feature)

    def _role_segments(self, runtime, match_minutes):
        from .models import FastRoleSegment
        grouped = {}
        for start, end, _, players, _ in runtime.exposures:
            for player in players:
                lo, hi, duration = self._exposure_minutes(runtime, player.player_id, start, end, match_minutes)
                if not duration:
                    continue
                values = grouped.setdefault(player.player_id, [])
                key = (player.assigned_slot_id, player.assigned_position.value, player.role_id)
                if values and values[-1].end_minute == lo - 1 and (
                    values[-1].slot_id, values[-1].position, values[-1].role_id) == key:
                    values[-1] = replace(values[-1], end_minute=hi)
                else:
                    values.append(FastRoleSegment(runtime.team.club_id, player.player_id, *key, lo - 1, hi))
        return tuple(s for key in sorted(grouped) for s in grouped[key])

    def profiles(self, snapshot: MatchSnapshot) -> tuple[FastTeamProfile, FastTeamProfile]:
        return build_fast_team_profile(snapshot.home_team), build_fast_team_profile(snapshot.away_team)

    # ------------------------------------------------------------------
    # Team-level match processes
    # ------------------------------------------------------------------
    def _home_possession(
        self,
        home: FastTeamProfile,
        away: FastTeamProfile,
        random: FastMatchRandom,
    ) -> float:
        home_execution = self._execution_expression(home)
        away_execution = self._execution_expression(away)
        home_possession = self._effective_centered(home, home.possession_style)
        away_possession = self._effective_centered(away, away.possession_style)
        home_press = self._effective_centered(home, home.pressing)
        away_press = self._effective_centered(away, away.pressing)
        home_direct = self._effective_centered(home, home.directness)
        away_direct = self._effective_centered(away, away.directness)

        home_control = (
            home.control
            + self.config.home_advantage_rating
            + self._coordination_rating(home) * 0.85
            + (home.possession_style - 50.0) * 0.100 * home_execution
            + (home.pressing - 50.0) * 0.020 * home_execution
        )
        away_control = (
            away.control
            + self._coordination_rating(away) * 0.85
            + (away.possession_style - 50.0) * 0.100 * away_execution
            + (away.pressing - 50.0) * 0.020 * away_execution
        )

        # Tactical interaction: an organised press disrupts possession-oriented
        # build-up, while direct play can bypass part of that pressure. These are
        # matchup effects, not generic bonuses for selecting an instruction.
        home_control -= max(0.0, away_press) * max(0.0, home_possession) * 2.20
        away_control -= max(0.0, home_press) * max(0.0, away_possession) * 2.20
        home_control += max(0.0, home_direct) * max(0.0, away_press) * 1.10
        away_control += max(0.0, away_direct) * max(0.0, home_press) * 1.10

        home_control += tactical.possession_edge(home.tactical_features, away.tactical_features)
        away_control += tactical.possession_edge(away.tactical_features, home.tactical_features)
        share = 50.0 + (home_control - away_control) * 0.48 + random.gauss(0.0, 1.8)
        return round(self._clamp(share, 28.0, 72.0), 1)

    def _simulate_shot_windows(
        self,
        attacker: _TeamRuntime,
        defender: _TeamRuntime,
        *,
        minutes: int,
        minute_start: int,
        minute_end: int,
        home_advantage: bool,
        random: FastMatchRandom,
        pace_factor: float = 1.0,
        attacker_energy: float = 1.0,
        defender_energy: float = 1.0,
    ) -> None:
        # No dismissals: use the original RNG streams and match calculation.
        cutoffs = sorted({
            dismissed_minute + 1
            for runtime in (attacker, defender)
            for dismissed_minute in runtime.dismissed_at.values()
            if minute_start < dismissed_minute + 1 <= minute_end
        })
        if not cutoffs:
            self._simulate_period_shots(
                attacker, defender, minutes=minutes, minute_start=minute_start,
                minute_end=minute_end, home_advantage=home_advantage, random=random,
                pace_factor=pace_factor, attacker_energy=attacker_energy,
                defender_energy=defender_energy,
                manpower_factor=self._manpower_factor(attacker, defender, minute_start),
            )
            return

        starts = (minute_start, *cutoffs)
        ends = (*(cutoff - 1 for cutoff in cutoffs), minute_end)
        for start, end in zip(starts, ends):
            self._simulate_period_shots(
                attacker, defender, minutes=end - start + 1,
                minute_start=start, minute_end=end, home_advantage=home_advantage,
                random=random.fork(f"dismissal-window/{start}-{end}"),
                pace_factor=pace_factor, attacker_energy=attacker_energy,
                defender_energy=defender_energy,
                manpower_factor=self._manpower_factor(attacker, defender, start),
            )

    def _apply_score_dependent_risk(
        self,
        home: _TeamRuntime,
        away: _TeamRuntime,
        *,
        random: FastMatchRandom,
        minute_start: int = 1,
        minute_end: int = 90,
        pace_factor: float = 1.0,
        home_energy: float = 1.0,
        away_energy: float = 1.0,
    ) -> None:
        """Replay only the future when the existing risk setting activates.

        The normal seeded simulation is untouched until a real lead occurs.
        The risk component formerly included in the *whole-match* style is
        applied with its original 1/3 weight only to a team currently leading.
        After a goal changes that state, future chances use the same shot/xG
        formulas and isolated RNG streams; preceding events never change.

        Decisions at the same minute take effect from the following minute.
        This mirrors the fast engine's minute-resolution event contract, not
        a new tactical bonus or an additional player instruction.
        """
        baseline = (home.profile, away.profile)
        if all(profile.risk_when_leading == 50.0 for profile in baseline):
            return

        def active_risk(score: tuple[int, int]) -> tuple[float, float]:
            return (
                baseline[0].risk
                + ((baseline[0].risk_when_leading - 50.0) / 3.0 if score[0] > score[1] else 0.0),
                baseline[1].risk
                + ((baseline[1].risk_when_leading - 50.0) / 3.0 if score[1] > score[0] else 0.0),
            )

        # The shots already generated for this period always used baseline
        # profiles. Rebuild only if the score on entry requires an active risk.
        current_risk = (baseline[0].risk, baseline[1].risk)
        start = minute_start
        while start <= minute_end:
            score = [
                sum(int(shot.goal) for shot in runtime.shots if shot.minute < start)
                for runtime in (home, away)
            ]
            desired_risk = active_risk((score[0], score[1]))
            if desired_risk != current_risk:
                # Discard no earlier shots, including those at the same minute
                # as a goal. Replay both teams with the risk now in force.
                home.shots = [shot for shot in home.shots if not start <= shot.minute <= minute_end]
                away.shots = [shot for shot in away.shots if not start <= shot.minute <= minute_end]
                home.profile = replace(baseline[0], risk=desired_risk[0])
                away.profile = replace(baseline[1], risk=desired_risk[1])
                try:
                    self._simulate_shot_windows(
                        home, away, minutes=minute_end - start + 1,
                        minute_start=start, minute_end=minute_end,
                        home_advantage=True, random=random.fork(f"home/after/{start}"),
                        pace_factor=pace_factor,
                        attacker_energy=home_energy, defender_energy=away_energy,
                    )
                    self._simulate_shot_windows(
                        away, home, minutes=minute_end - start + 1,
                        minute_start=start, minute_end=minute_end,
                        home_advantage=False, random=random.fork(f"away/after/{start}"),
                        pace_factor=pace_factor,
                        attacker_energy=away_energy, defender_energy=home_energy,
                    )
                finally:
                    home.profile, away.profile = baseline
                current_risk = desired_risk

            # Inspect goals in chronological minute groups: two goals at the
            # same minute that cancel each other do not cause a fictitious lead.
            score_by_minute: dict[int, list[int]] = {}
            for side, runtime in enumerate((home, away)):
                for shot in runtime.shots:
                    if start <= shot.minute <= minute_end and shot.goal:
                        tally = score_by_minute.setdefault(shot.minute, [0, 0])
                        tally[side] += 1
            change_at = None
            for minute in sorted(score_by_minute):
                goals = score_by_minute[minute]
                score[0] += goals[0]
                score[1] += goals[1]
                if active_risk((score[0], score[1])) != current_risk:
                    change_at = minute
                    break
            if change_at is None:
                break
            # The next iteration can only move forward; at most one replay
            # can start per minute, even in an unusually high-scoring match.
            start = change_at + 1

    def _apply_regulation_game_management(
        self, home: _TeamRuntime, away: _TeamRuntime, random: FastMatchRandom
    ) -> None:
        """Apply late score-dependent controls without changing normal RNG streams.

        Time wasting by a side *currently leading* reduces the number of late
        opportunities for both teams (without deleting any earlier chances).
        A side trailing at minute 70 with maximal urgency can generate some
        additional late opportunities.  All changes stay within the existing
        xG/finishing and dismissal models; goals remain probabilistic.

        This is a low-resolution fast-sim approximation, not a 2D replay.
        """
        if (
            home.profile.time_wasting <= 50.0
            and away.profile.time_wasting <= 50.0
            and home.profile.urgency_when_trailing <= 75.0
            and away.profile.urgency_when_trailing <= 75.0
        ):
            return
        # Apply the historical 65+ time-wasting rule chronologically. Separate
        # minute 70 so urgency is decided from the *accepted* score, then merge
        # its extra opportunities into the same post-70 chronological filter.
        # Otherwise urgency-generated shots would bypass an opponent's active
        # time wasting, even though normal shots faced that restriction.
        original_counts = (len(home.shots), len(away.shots))
        events = sorted(
            [(shot.minute, 0, index, shot) for index, shot in enumerate(home.shots)]
            + [(shot.minute, 1, index, shot) for index, shot in enumerate(away.shots)],
            key=lambda item: (item[0], item[1], item[2]),
        )
        kept: tuple[list[_ShotRecord], list[_ShotRecord]] = ([], [])
        score = [0, 0]

        def accept(events_to_consider) -> None:
            for minute, side, index, shot in events_to_consider:
                leader = 0 if score[0] > score[1] else (1 if score[1] > score[0] else None)
                if minute >= 65 and leader is not None:
                    leader_profile = (home.profile, away.profile)[leader]
                    waste = max(0.0, (leader_profile.time_wasting - 50.0) / 50.0)
                    rejection = min(0.22, 0.22 * waste)
                    if rejection and random.fork(f"waste/{side}/{index}").random() < rejection:
                        continue
                kept[side].append(shot)
                score[side] += int(shot.goal)

        accept(item for item in events if item[0] <= 70)
        lead_at_70 = tuple(score)
        for side, attacker, defender in ((0, home, away), (1, away, home)):
            if lead_at_70[side] >= lead_at_70[1 - side]:
                continue
            intensity = max(0.0, (attacker.profile.urgency_when_trailing - 75.0) / 25.0)
            if not intensity:
                continue
            self._simulate_shot_windows(
                attacker, defender,
                minutes=20, minute_start=71, minute_end=90,
                home_advantage=side == 0,
                random=random.fork(f"urgency/{side}"),
                pace_factor=0.42 * intensity,
            )

        added = (
            [(shot.minute, 0, index, shot) for index, shot in enumerate(home.shots[original_counts[0]:], start=original_counts[0])],
            [(shot.minute, 1, index, shot) for index, shot in enumerate(away.shots[original_counts[1]:], start=original_counts[1])],
        )
        late_events = sorted(
            [item for item in events if item[0] > 70] + added[0] + added[1],
            key=lambda item: (item[0], item[1], item[2]),
        )
        accept(late_events)
        home.shots, away.shots = kept

    @staticmethod
    def _manpower_factor(attacker: _TeamRuntime, defender: _TeamRuntime, minute: int) -> float:
        fewer_attackers = max(0, 11 - len(attacker.active_starters_at(minute)))
        fewer_defenders = max(0, 11 - len(defender.active_starters_at(minute)))
        # Explicitly model the volume of chances created with fewer players;
        # strength and shooting accuracy continue to come from the profiles.
        return max(0.25, 1.0 - 0.26 * fewer_attackers + 0.13 * fewer_defenders)

    def _simulate_period_shots(
        self,
        attacker: _TeamRuntime,
        defender: _TeamRuntime,
        *,
        minutes: int,
        minute_start: int,
        minute_end: int,
        home_advantage: bool,
        random: FastMatchRandom,
        pace_factor: float = 1.0,
        attacker_energy: float = 1.0,
        defender_energy: float = 1.0,
        manpower_factor: float = 1.0,
    ) -> None:
        period_factor = minutes / 90.0
        fatigue_volume = self._clamp(
            0.92 + attacker_energy * 0.08 + (1.0 - defender_energy) * 0.10,
            0.82,
            1.10,
        )
        expected = (
            self._expected_shots(attacker, defender, home_advantage=home_advantage)
            * period_factor
            * pace_factor
            * fatigue_volume
            * manpower_factor
        )
        count = self._overdispersed_count(expected, random.fork("count"), dispersion=8.0)
        count = max(0, min(28 if minutes == 90 else (8 if minutes == 15 else max(1, math.ceil(28 * minutes / 90))), count))
        active_starters = attacker.active_starters_at(minute_start)
        if not active_starters:
            return
        for index in range(count):
            shot_random = random.fork(f"shot/{index}")
            active_defenders = defender.active_starters_at(minute_start)
            shooter = self._select_shooter(attacker.team, shot_random.fork("shooter"), players=active_starters, defenders=active_defenders)
            creator = self._select_assister(attacker.team, shooter.player_id, shot_random.fork("build-up"), players=active_starters)
            xg = self._chance_xg(attacker.profile, defender.profile, shot_random.fork("xg"))
            # Optional named takers affect a fraction of the SAME real chances.
            # No fabricated goals, extra shots or external match events.
            if attacker.team.set_piece_preferences:
                from football_manager.services.match_preparation import effective_order, role_score
                orders = attacker.team.set_piece_preferences
                kind_roll = shot_random.fork("set-pieces/kind").random()
                kind = ("free_kicks" if kind_roll < .045 else
                        "corners_left" if kind_roll < .095 else
                        "corners_right" if kind_roll < .145 else None)
                if kind:
                    candidates = effective_order(orders, kind, active_starters)
                    if candidates:
                        taker = candidates[0]
                        if kind == "free_kicks":
                            shooter = taker
                            creator = None
                        else:
                            # A corner taker is a possible creator, not scorer.
                            creator = taker if taker.player_id != shooter.player_id else None
                        quality_shift = max(-.045, min(.045, (role_score(taker, kind) - 65) / 600.0))
                        xg *= (1.0 + quality_shift)
                captain = effective_order(orders, "captain", active_starters)
                if captain:
                    # Leadership remains much less important than player quality.
                    captain_score = role_score(captain[0], "captain")
                    xg *= 1.0 + max(-.012, min(.012, (captain_score - 65) / 1800.0))
            fatigue_quality = self._clamp(
                1.0 - (1.0 - attacker_energy) * 0.22 + (1.0 - defender_energy) * 0.30,
                0.84,
                1.16,
            )
            xg = self._clamp(xg * fatigue_quality, 0.01, 0.65)
            xg, long_shot = tactical.action_quality(xg, shooter, creator, attacker.team, active_defenders, shot_random.fork("construction"))
            finishing = self._finishing_quality(shooter)
            finish_factor = self._clamp(
                (1.0 + (finishing - 65.0) * 0.0035) * (0.92 + 0.08 * attacker_energy),
                0.78,
                1.18,
            )
            active_keeper = any(
                player.assigned_position is Position.GK
                for player in defender.active_starters_at(minute_start)
            )
            # An outfield player forced into goal is not an elite keeper.
            effective_goalkeeping = (
                defender.profile.goalkeeping if active_keeper
                else min(defender.profile.goalkeeping, 28.0)
            )
            goalkeeper_delta = effective_goalkeeping - 65.0
            if goalkeeper_delta >= 0.0:
                goalkeeper_base = 1.0 - goalkeeper_delta * 0.0040
            else:
                # Weak keepers are more damaging than elite keepers are helpful.
                # In particular, an outfielder in goal must materially increase
                # conversion without hard-coding a result.
                goalkeeper_base = 1.0 + (-goalkeeper_delta) * 0.0065
            goalkeeper_factor = self._clamp(
                goalkeeper_base * (1.0 + (1.0 - defender_energy) * 0.08),
                0.78,
                1.42,
            )
            goal_probability = self._clamp(xg * finish_factor * goalkeeper_factor, 0.005, 0.78)
            goal = shot_random.fork("finish").random() < goal_probability
            if goal:
                on_target = True
            else:
                sot_probability = self._clamp(
                    0.20 + xg * 0.75 + (finishing - 65.0) * 0.0020 - (1.0 - attacker_energy) * 0.05,
                    0.12,
                    0.68,
                )
                on_target = shot_random.fork("target").random() < sot_probability
            assist_player_id = None
            if goal and shot_random.fork("assist/roll").random() < self.config.assist_probability * (.75 if long_shot else 1):
                assister = creator
                assist_player_id = assister.player_id if assister is not None else None
            minute = shot_random.fork("minute").randint(minute_start, minute_end)
            attacker.shots.append(
                _ShotRecord(
                    player_id=shooter.player_id,
                    assist_player_id=assist_player_id,
                    xg=round(xg, 3),
                    on_target=on_target,
                    goal=goal,
                    minute=minute,
                    extra_time=minute > 90,
                )
            )

    def _expected_shots(
        self,
        attacker: _TeamRuntime,
        defender: _TeamRuntime,
        *,
        home_advantage: bool,
    ) -> float:
        a = attacker.profile
        d = defender.profile
        attack = a.attack + self._coordination_rating(a) * 0.82
        defense = d.defense + self._coordination_rating(d) * 0.95
        control = a.control + self._coordination_rating(a) * 0.95
        opponent_control = d.control + self._coordination_rating(d) * 0.95

        mean = self.config.base_shots_per_team
        mean += (attack - defense) * 0.105
        mean += (control - opponent_control) * 0.035
        mean += (attacker.possession - 50.0) * 0.050
        mean += self._effective_centered(a, a.tempo) * 0.70
        mean += self._effective_centered(a, a.risk) * 0.50
        mean += self._tactical_shot_edge(a, d)
        mean += tactical.shot_edge(a.tactical_features, d.tactical_features, a.directness)
        if home_advantage:
            mean += self.config.home_shot_advantage
        return self._clamp(mean, 5.0, 21.0)

    def _chance_xg(
        self,
        attacker: FastTeamProfile,
        defender: FastTeamProfile,
        random: FastMatchRandom,
    ) -> float:
        attack = attacker.attack + self._coordination_rating(attacker) * 0.68
        defense = defender.defense + self._coordination_rating(defender) * 0.80
        edge = attack - defense
        risk = self._effective_centered(attacker, attacker.risk)
        tactical_quality = self._tactical_quality_edge(attacker, defender)
        tactical_quality += tactical.quality_edge(attacker.tactical_features, defender.tactical_features)
        big_chance_probability = self._clamp(
            0.10 + edge * 0.0018 + risk * 0.020 + tactical_quality * 0.55,
            0.035,
            0.22,
        )
        roll = random.random()
        if roll < big_chance_probability:
            base = random.triangular(0.24, 0.56, 0.34)
        elif roll < big_chance_probability + 0.35:
            base = random.triangular(0.075, 0.22, 0.125)
        else:
            base = random.triangular(0.018, 0.085, 0.045)

        quality_shift = edge * 0.0007
        quality_shift += (attacker.set_pieces - defender.defense) * 0.00008
        quality_shift += tactical_quality
        return self._clamp((base + quality_shift) * self.config.chance_quality_scale, 0.01, 0.65)

    def _apply_extra_time_substitutions(
        self,
        runtime: _TeamRuntime,
        limit: int,
        random: FastMatchRandom,
    ) -> None:
        """Use only the competition's extra-time substitution allowance.

        Regulation substitutions are intentionally outside Phase 5.11D. This
        hook models the extra fresh-leg option granted specifically when a tie
        reaches 90 minutes, and it refuses a bench option that is too unfamiliar
        with the requested position.
        """

        if limit <= 0 or not runtime.team.bench:
            return

        for substitution_index in range(limit):
            candidates: list[tuple[float, int, PlayerMatchSnapshot, PlayerMatchSnapshot]] = []
            for player_index, outgoing in enumerate(runtime.team.starters):
                if outgoing.player_id in runtime.dismissed_at or outgoing.assigned_position is Position.GK:
                    continue
                # An opponent can only replace an occupied, fully assigned tactical job.
                # Otherwise _assign_bench_player would fail after choosing a candidate.
                if (outgoing.assigned_position is None or outgoing.assigned_slot_id is None
                        or outgoing.role_id is None):
                    continue
                out_condition = self._condition_after(outgoing, runtime.profile, 90)
                for incoming in runtime.team.bench:
                    position = outgoing.assigned_position
                    if position is None:
                        continue
                    position_familiarity = incoming.familiarity.position_score(position)
                    if position_familiarity < 45.0:
                        continue
                    role_score = incoming.familiarity.role_score(outgoing.role_id or "") if outgoing.role_id else 65.0
                    tactic_score = incoming.familiarity.tactic_score(runtime.team.tactic.tactic_id)
                    execution = 0.30 * position_familiarity + 0.25 * role_score + 0.45 * tactic_score
                    fresh_leg_value = max(0.0, 95.0 - out_condition) * 0.45
                    assignment_overall, projected_current, _fit = self._bench_assignment_ratings(
                        runtime, incoming, outgoing
                    )
                    quality = 0.40 * projected_current + 0.20 * assignment_overall
                    score = fresh_leg_value + quality + execution * 0.40
                    score += random.fork(f"{substitution_index}/{outgoing.player_id}/{incoming.player_id}").uniform(0.0, 0.05)
                    candidates.append((score, player_index, outgoing, incoming))

            if not candidates:
                break

            _, player_index, outgoing, incoming = max(candidates, key=lambda item: item[0])
            assigned = self._assign_bench_player(runtime, incoming, outgoing)
            active = list(runtime.team.starters)
            active[player_index] = assigned
            remaining_bench = tuple(player for player in runtime.team.bench if player.player_id != incoming.player_id)
            runtime.team = replace(runtime.team, starters=tuple(active), bench=remaining_bench)
            runtime.profile = build_fast_team_profile(runtime.team)
            runtime.participants[assigned.player_id] = assigned
            runtime.entered_minute[assigned.player_id] = 90
            runtime.exited_minute[outgoing.player_id] = 90
            runtime.substitutions.append(
                FastSubstitutionEvent(
                    minute=91,
                    club_id=runtime.team.club_id,
                    player_out_id=outgoing.player_id,
                    player_in_id=assigned.player_id,
                    position=assigned.assigned_position.value if assigned.assigned_position is not None else "unknown",
                    extra_time=True,
                )
            )

    def _bench_assignment_ratings(
        self,
        runtime: _TeamRuntime,
        incoming: PlayerMatchSnapshot,
        outgoing: PlayerMatchSnapshot,
    ) -> tuple[float, float, float]:
        assigned = self._assign_bench_player(runtime, incoming, outgoing)
        assert assigned.role_context is not None
        return (
            assigned.overall_rating,
            assigned.current_rating,
            assigned.role_context.role_suitability,
        )

    def _assign_bench_player(
        self,
        runtime: _TeamRuntime,
        incoming: PlayerMatchSnapshot,
        outgoing: PlayerMatchSnapshot,
    ) -> PlayerMatchSnapshot:
        position = outgoing.assigned_position
        if position is None or outgoing.assigned_slot_id is None or outgoing.role_id is None:
            raise ValueError("cannot substitute into an unassigned tactical slot")
        return assign_match_player(
            incoming,
            slot_id=outgoing.assigned_slot_id,
            position=position,
            role_id=outgoing.role_id,
            role_name=outgoing.role_name or outgoing.role_id,
            tactic_id=runtime.team.tactic.tactic_id,
            instructions=outgoing.effective_instructions,
        )

    def _extra_time_energy(self, runtime: _TeamRuntime, elapsed_minutes: int) -> float:
        conditions: list[float] = []
        for player in runtime.team.starters:
            minutes_played = runtime.minutes_for(player.player_id, elapsed_minutes)
            conditions.append(self._condition_after(player, runtime.profile, minutes_played))
        average_condition = _safe_mean(*conditions)
        if average_condition >= 75.0:
            return 1.0
        return self._clamp(1.0 - (75.0 - average_condition) / 250.0, 0.78, 1.0)

    def _simulate_discipline_period(
        self,
        snapshot: MatchSnapshot,
        home: _TeamRuntime,
        away: _TeamRuntime,
        *,
        root: FastMatchRandom,
        minute_start: int,
        minute_end: int,
    ) -> None:
        minutes_factor = (minute_end - minute_start + 1) / 90.0
        extra_time = minute_start > 90
        for side_name, side in (("home", home), ("away", away)):
            profile = side.profile
            rng = root.fork(f"{side_name}/non_shot")
            referee = snapshot.context.referee
            expression = self._execution_expression(profile)
            poor_execution = max(0.0, 65.0 - profile.tactical_execution) / 65.0
            press_intensity = abs(profile.pressing - 50.0) / 50.0
            foul_mean = self.config.base_fouls_per_team
            foul_mean += (profile.pressing - 50.0) * 0.020 * expression
            foul_mean += (profile.defensive_aggression - 50.0) * 0.022
            foul_mean += poor_execution * press_intensity * 1.80
            foul_mean += (referee.strictness - 50.0) * 0.010
            foul_mean -= (referee.contact_tolerance - 50.0) * 0.008
            foul_mean -= (profile.discipline - 65.0) * 0.018
            foul_mean *= minutes_factor
            prefix = "extra_time/" if extra_time else ""
            foul_count = self._overdispersed_count(
                self._clamp(foul_mean, 5.0 * minutes_factor, 20.0 * minutes_factor),
                rng.fork(f"{prefix}fouls/count"), dispersion=18.0,
            )
            side.fouls += foul_count
            card_probability = self.config.base_card_probability
            card_probability += (referee.card_tendency - 50.0) * 0.0010
            card_probability += (referee.strictness - 50.0) * 0.0007
            card_probability += (profile.defensive_aggression - 50.0) * 0.0007
            card_probability -= (profile.discipline - 65.0) * 0.0005
            card_probability += poor_execution * press_intensity * 0.012
            card_probability = self._clamp(card_probability, 0.06, 0.28)
            self._simulate_cards(
                side, card_probability, rng.fork(f"{prefix}cards"),
                minute_start=minute_start, minute_end=minute_end, foul_count=foul_count,
            )

    def _simulate_non_shot_statistics(
        self,
        snapshot: MatchSnapshot,
        home: _TeamRuntime,
        away: _TeamRuntime,
        *,
        extra_time_played: bool,
        root: FastMatchRandom,
    ) -> None:
        minutes_factor = 120.0 / 90.0 if extra_time_played else 1.0
        for side_name, side, opponent in (
            ("home", home, away),
            ("away", away, home),
        ):
            profile = side.profile
            opponent_profile = opponent.profile
            rng = root.fork(f"{side_name}/non_shot")

            pass_mean = self.config.base_passes_per_team
            pass_mean += (side.possession - 50.0) * 5.2
            expression = self._execution_expression(profile)
            pass_mean += (profile.possession_style - 50.0) * 1.0 * expression
            pass_mean -= (profile.directness - 50.0) * 0.85 * expression
            pass_mean -= (profile.tempo - 50.0) * 0.35 * expression
            extra = profile.tactical_features
            if extra.enabled:
                pass_mean += 12 * extra.hold_up - 10 * extra.dribble - 8 * extra.keeper_release
            pass_mean *= minutes_factor
            duration = 120 if extra_time_played else 90
            own_shortage = sum(max(0, duration - minute) / duration for minute in side.dismissed_at.values())
            opponent_shortage = sum(max(0, duration - minute) / duration for minute in opponent.dismissed_at.values())
            pass_mean *= max(0.50, 1.0 - 0.18 * own_shortage + 0.08 * opponent_shortage)
            side.passes_attempted = max(120, int(round(rng.fork("passes/count").gauss(pass_mean, 24.0))))

            completion_probability = 0.815
            completion_probability += (profile.control - 65.0) * 0.00125
            completion_probability += self._coordination_rating(profile) * 0.00120
            completion_probability += (profile.possession_style - 50.0) * 0.00055 * expression
            completion_probability -= (opponent_profile.pressing - 50.0) * 0.00060 * self._execution_expression(opponent_profile)
            completion_probability -= (profile.directness - 50.0) * 0.00055 * expression
            completion_probability += tactical.pass_completion_edge(profile.tactical_features, opponent_profile.tactical_features)
            completion_probability = self._clamp(completion_probability, 0.68, 0.93)
            side.passes_completed = self._binomial_approx(
                side.passes_attempted,
                completion_probability,
                rng.fork("passes/completed"),
            )

            corner_mean = self.config.base_corners_per_team
            corner_mean += (len(side.shots or []) - self.config.base_shots_per_team * minutes_factor) * 0.13
            corner_mean += (profile.width - 50.0) * 0.010 * expression
            corner_mean += (profile.crossing_frequency - 50.0) * 0.012 * expression
            if profile.tactical_features.enabled:
                corner_mean += .25 * profile.tactical_features.player_crosses
                corner_mean += .15 * profile.tactical_features.overlap
            corner_mean *= minutes_factor
            side.corners = self._overdispersed_count(
                self._clamp(corner_mean, 1.0, 10.0 * minutes_factor),
                rng.fork("corners"),
                dispersion=10.0,
            )

    # ------------------------------------------------------------------
    # Individual attribution
    # ------------------------------------------------------------------
    def _goal_events(
        self,
        home: _TeamRuntime,
        away: _TeamRuntime,
    ) -> tuple[FastGoalEvent, ...]:
        events: list[FastGoalEvent] = []
        for runtime in (home, away):
            for shot in runtime.shots:
                if not shot.goal:
                    continue
                scorer = runtime.player(shot.player_id)
                events.append(
                    FastGoalEvent(
                        minute=shot.minute,
                        club_id=runtime.team.club_id,
                        scorer_player_id=scorer.player_id,
                        assist_player_id=shot.assist_player_id,
                        xg=shot.xg,
                        extra_time=shot.extra_time,
                    )
                )
        return tuple(sorted(events, key=lambda item: (item.minute, item.club_id, item.scorer_player_id)))

    def _simulate_cards(
        self,
        side: _TeamRuntime,
        card_probability: float,
        random: FastMatchRandom,
        *,
        minute_start: int,
        minute_end: int,
        foul_count: int,
    ) -> None:
        # Generate candidate bookings, then process them in match-time order.
        # A player may commit another offence only while still on the pitch.
        candidates: list[tuple[int, int, FastMatchRandom]] = []
        for index in range(foul_count):
            foul_rng = random.fork(f"foul/{index}")
            if foul_rng.random() >= card_probability:
                continue
            minute = foul_rng.fork("minute").randint(minute_start, minute_end)
            candidates.append((minute, index, foul_rng))

        yellows: dict[str, int] = {}
        for existing in side.cards:
            if existing.card is FastCardType.YELLOW:
                yellows[existing.player_id] = yellows.get(existing.player_id, 0) + 1

        for minute, _, foul_rng in sorted(candidates):
            eligible = tuple(
                player for player in side.active_starters_at(minute)
                if player.player_id not in side.dismissed_at
            )
            if not eligible:
                continue
            weights = {
                player.player_id: min(minute_end, side.exited_minute.get(player.player_id, minute_end))
                - max(minute_start - 1, side.entered_minute.get(player.player_id, 0))
                for player in eligible
            }
            player = self._select_fouler(eligible, foul_rng.fork("player"), minute_weights=weights)
            direct_red_probability = self._clamp(
                0.020 + max(0.0, self._attr(player, "mental.aggression") - 75.0) * 0.0010,
                0.01, 0.06,
            )
            direct_red = foul_rng.fork("type").random() < direct_red_probability
            side.booked_fouls[player.player_id] = side.booked_fouls.get(player.player_id, 0) + 1
            if not direct_red:
                side.yellow_cards += 1
                yellows[player.player_id] = yellows.get(player.player_id, 0) + 1
                side.cards.append(FastCardEvent(
                    minute=minute, club_id=side.team.club_id, player_id=player.player_id,
                    card=FastCardType.YELLOW,
                ))
            if direct_red or yellows.get(player.player_id, 0) == 2:
                side.red_cards += 1
                side.dismissed_at[player.player_id] = minute
                side.cards.append(FastCardEvent(
                    minute=minute, club_id=side.team.club_id, player_id=player.player_id,
                    card=FastCardType.RED,
                ))

    def _player_statistics(
        self,
        home: _TeamRuntime,
        away: _TeamRuntime,
        *,
        goals: tuple[FastGoalEvent, ...],
        extra_time_played: bool,
        winner_club_id: str | None,
        root: FastMatchRandom,
    ) -> tuple[FastPlayerStatistics, ...]:
        match_minutes = 120 if extra_time_played else 90
        results: list[FastPlayerStatistics] = []
        for label, runtime, opponent in (
            ("home", home, away),
            ("away", away, home),
        ):
            participants = runtime.participating_players(match_minutes)
            minutes_by_id = {
                player.player_id: runtime.minutes_for(player.player_id, match_minutes)
                for player in participants
            }
            accum = {player.player_id: _PlayerAccumulator() for player in participants}
            for shot in runtime.shots:
                item = accum[shot.player_id]
                item.shots += 1
                item.shots_on_target += int(shot.on_target)
                item.goals += int(shot.goal)
                item.xg += shot.xg
            for goal in goals:
                if goal.club_id == runtime.team.club_id and goal.assist_player_id is not None:
                    accum[goal.assist_player_id].assists += 1
            for card in runtime.cards:
                item = accum[card.player_id]
                if card.card is FastCardType.YELLOW:
                    item.yellow_cards += 1
                else:
                    item.red_cards += 1

            pass_attempts = self._allocate_pass_attempts(participants, runtime.passes_attempted, minutes_by_id)
            pass_completions = self._allocate_pass_completions(
                participants,
                pass_attempts,
                runtime.passes_completed,
            )
            foul_allocations = self._allocate_fouls(
                participants, runtime.fouls, minutes_by_id, minimums=runtime.booked_fouls,
            )
            for player_id, value in pass_attempts.items():
                accum[player_id].passes_attempted = value
            for player_id, value in pass_completions.items():
                accum[player_id].passes_completed = value
            for player_id, value in foul_allocations.items():
                accum[player_id].fouls = value

            team_result_bonus = 0.0
            if winner_club_id == runtime.team.club_id:
                team_result_bonus = 0.18
            elif winner_club_id == opponent.team.club_id:
                team_result_bonus = -0.10

            for player in participants:
                item = accum[player.player_id]
                player_minutes = minutes_by_id[player.player_id]
                minute_share = min(1.0, player_minutes / 90.0)
                rating = 6.45 + team_result_bonus * minute_share
                rating += item.goals * 0.78 + item.assists * 0.42
                rating += max(0.0, item.xg - 0.20) * 0.10
                rating += item.shots_on_target * 0.025
                rating -= item.yellow_cards * 0.14 + item.red_cards * 0.85
                is_defensive_outfield = player.assigned_position in {
                    Position.RB,
                    Position.RCB,
                    Position.CB,
                    Position.LCB,
                    Position.LB,
                    Position.RWB,
                    Position.LWB,
                    Position.DM,
                }
                if player.assigned_position is Position.GK or is_defensive_outfield:
                    # A player's defensive rating must reflect only the goals
                    # conceded and saves made during their own appearance.
                    # Team totals still include all 90/120 minutes. Keep the
                    # existing rating coefficients and 90-minute scaling.
                    entered = runtime.entered_minute.get(player.player_id, 0)
                    exited = min(
                        match_minutes,
                        runtime.exited_minute.get(player.player_id, match_minutes),
                        runtime.dismissed_at.get(player.player_id, match_minutes),
                    )
                    faced = tuple(
                        shot for shot in opponent.shots
                        if entered < shot.minute <= exited
                    )
                    conceded_while_playing = sum(shot.goal for shot in faced)
                    if player.assigned_position is Position.GK:
                        keeper_saves = sum(shot.on_target and not shot.goal for shot in faced)
                        rating += keeper_saves * 0.055 * minute_share
                        rating += (0.25 if conceded_while_playing == 0 else -max(0, conceded_while_playing - 2) * 0.12) * minute_share
                    else:
                        rating += (0.16 if conceded_while_playing == 0 else -max(0, conceded_while_playing - 2) * 0.07) * minute_share
                rating += root.fork(f"{label}/rating/{player.player_id}").gauss(0.0, 0.12)
                rating = round(self._clamp(rating, 3.0, 10.0), 2)

                physical_after = (self._planned_physical_state(runtime, player, player_minutes, match_minutes)
                                  if runtime.exposures else self._physical_state_after(player, runtime.profile, player_minutes))
                condition_after = physical_after.condition
                results.append(
                    FastPlayerStatistics(
                        player_id=player.player_id,
                        club_id=runtime.team.club_id,
                        minutes=player_minutes,
                        goals=item.goals,
                        assists=item.assists,
                        shots=item.shots,
                        shots_on_target=item.shots_on_target,
                        xg=round(item.xg, 3),
                        passes_attempted=item.passes_attempted,
                        passes_completed=item.passes_completed,
                        fouls=item.fouls,
                        yellow_cards=item.yellow_cards,
                        red_cards=item.red_cards,
                        match_rating=rating,
                        condition_after=condition_after,
                        fatigue_after=physical_after.fatigue,
                    )
                )
        return tuple(sorted(results, key=lambda item: (item.club_id, item.player_id)))

    # ------------------------------------------------------------------
    # Selectors and helpers
    # ------------------------------------------------------------------
    def _select_shooter(
        self, team: TeamMatchSnapshot, random: FastMatchRandom,
        *, players: tuple[PlayerMatchSnapshot, ...] | None = None,
        defenders: tuple[PlayerMatchSnapshot, ...] = (),
    ) -> PlayerMatchSnapshot:
        available = team.starters if players is None else players
        points = phase_points(team.tactic, "in_possession")
        weights: list[float] = []
        for player in available:
            position_weight = {
                Position.GK: 0.02,
                Position.RB: 0.35,
                Position.RCB: 0.20,
                Position.CB: 0.18,
                Position.LCB: 0.20,
                Position.LB: 0.35,
                Position.RWB: 0.55,
                Position.LWB: 0.55,
                Position.DM: 0.55,
                Position.RCM: 0.90,
                Position.CM: 0.90,
                Position.LCM: 0.90,
                Position.AM: 1.35,
                Position.RW: 1.45,
                Position.LW: 1.45,
                Position.SS: 1.55,
                Position.ST: 1.75,
            }.get(player.assigned_position, 0.7)
            quality = 0.50 * player.current_rating + 0.30 * self._attr(player, "technical.finishing") + 0.20 * self._attr(player, "mental.off_the_ball")
            weights.append(max(0.01, position_weight * quality * tactical.shooter_factor(player, team, defenders, points)))
        return self._weighted_choice(available, weights, random)

    def _select_assister(
        self,
        team: TeamMatchSnapshot,
        scorer_id: str,
        random: FastMatchRandom,
        *, players: tuple[PlayerMatchSnapshot, ...] | None = None,
    ) -> PlayerMatchSnapshot | None:
        available = team.starters if players is None else players
        candidates = [player for player in available if player.player_id != scorer_id]
        if not candidates:
            return None
        weights: list[float] = []
        for player in candidates:
            position_weight = {
                Position.GK: 0.12,
                Position.RB: 0.75,
                Position.RCB: 0.45,
                Position.CB: 0.40,
                Position.LCB: 0.45,
                Position.LB: 0.75,
                Position.RWB: 1.00,
                Position.LWB: 1.00,
                Position.DM: 0.85,
                Position.RCM: 1.15,
                Position.CM: 1.20,
                Position.LCM: 1.15,
                Position.AM: 1.45,
                Position.RW: 1.35,
                Position.LW: 1.35,
                Position.SS: 1.20,
                Position.ST: 0.75,
            }.get(player.assigned_position, 0.8)
            creator = _safe_mean(
                self._attr(player, "technical.passing"),
                self._attr(player, "technical.crossing"),
                self._attr(player, "mental.vision"),
                self._attr(player, "mental.creativity"),
                player.current_rating,
            )
            weights.append(max(0.01, creator * position_weight * tactical.creator_factor(player)))
        return self._weighted_choice(tuple(candidates), weights, random)

    def _select_fouler(
        self,
        players: tuple[PlayerMatchSnapshot, ...],
        random: FastMatchRandom,
        *,
        minute_weights: dict[str, int] | None = None,
    ) -> PlayerMatchSnapshot:
        weights: list[float] = []
        for player in players:
            position_weight = {
                Position.GK: 0.10,
                Position.RB: 1.20,
                Position.RCB: 1.30,
                Position.CB: 1.30,
                Position.LCB: 1.30,
                Position.LB: 1.20,
                Position.RWB: 1.10,
                Position.LWB: 1.10,
                Position.DM: 1.35,
                Position.RCM: 1.05,
                Position.CM: 1.05,
                Position.LCM: 1.05,
                Position.AM: 0.75,
                Position.RW: 0.65,
                Position.LW: 0.65,
                Position.SS: 0.60,
                Position.ST: 0.60,
            }.get(player.assigned_position, 0.8)
            aggression = self._attr(player, "mental.aggression")
            work_rate = self._attr(player, "mental.work_rate")
            minutes = 90 if minute_weights is None else max(1, minute_weights.get(player.player_id, 0))
            weights.append(
                max(0.01, position_weight * (0.65 * aggression + 0.35 * work_rate) * (minutes / 90.0))
            )
        return self._weighted_choice(players, weights, random)

    def _finishing_quality(self, player: PlayerMatchSnapshot) -> float:
        return _safe_mean(
            self._attr(player, "technical.finishing"),
            self._attr(player, "mental.composure"),
            self._attr(player, "technical.technique"),
            self._attr(player, "mental.anticipation"),
        )

    @staticmethod
    def _attr(player: PlayerMatchSnapshot, path: str) -> float:
        current: object = player.attributes
        for part in path.split("."):
            current = getattr(current, part)
            if current is None:
                return 50.0
        return float(current)

    def _allocate_pass_attempts(
        self,
        players: tuple[PlayerMatchSnapshot, ...],
        total: int,
        minutes_by_id: dict[str, int],
    ) -> dict[str, int]:
        weights: dict[str, float] = {}
        for player in players:
            position_weight = {
                Position.GK: 0.65,
                Position.RB: 1.00,
                Position.RCB: 1.20,
                Position.CB: 1.20,
                Position.LCB: 1.20,
                Position.LB: 1.00,
                Position.RWB: 0.95,
                Position.LWB: 0.95,
                Position.DM: 1.30,
                Position.RCM: 1.40,
                Position.CM: 1.45,
                Position.LCM: 1.40,
                Position.AM: 1.10,
                Position.RW: 0.78,
                Position.LW: 0.78,
                Position.SS: 0.72,
                Position.ST: 0.58,
            }.get(player.assigned_position, 0.9)
            minute_share = max(0.01, minutes_by_id[player.player_id] / 90.0)
            weights[player.player_id] = (
                position_weight
                * (0.65 * player.current_rating + 0.35 * self._attr(player, "technical.passing"))
                * minute_share
                * tactical.pass_share_factor(player)
            )
        return self._allocate_integer(total, weights)

    def _allocate_pass_completions(
        self,
        players: tuple[PlayerMatchSnapshot, ...],
        attempts: dict[str, int],
        total_completed: int,
    ) -> dict[str, int]:
        weights: dict[str, float] = {}
        capacity: dict[str, int] = {}
        for player in players:
            player_attempts = attempts[player.player_id]
            pass_skill = _safe_mean(
                self._attr(player, "technical.passing"),
                self._attr(player, "technical.first_touch"),
                self._attr(player, "mental.decisions"),
            )
            weights[player.player_id] = player_attempts * max(1.0, pass_skill)
            capacity[player.player_id] = player_attempts
        return self._allocate_integer(total_completed, weights, capacity=capacity)

    def _allocate_fouls(
        self,
        players: tuple[PlayerMatchSnapshot, ...],
        total: int,
        minutes_by_id: dict[str, int],
        *,
        minimums: dict[str, int] | None = None,
    ) -> dict[str, int]:
        weights: dict[str, float] = {}
        for player in players:
            position_weight = 1.0
            if player.assigned_position in {Position.GK}:
                position_weight = 0.12
            elif player.assigned_position in {Position.RB, Position.RCB, Position.CB, Position.LCB, Position.LB, Position.DM}:
                position_weight = 1.25
            elif player.assigned_position in {Position.ST, Position.SS}:
                position_weight = 0.65
            minute_share = max(0.01, minutes_by_id[player.player_id] / 90.0)
            weights[player.player_id] = position_weight * (
                0.65 * self._attr(player, "mental.aggression")
                + 0.35 * self._attr(player, "mental.work_rate")
            ) * minute_share
        guaranteed = {key: minimums.get(key, 0) if minimums else 0 for key in weights}
        remaining = total - sum(guaranteed.values())
        if remaining < 0:
            raise ValueError("booked fouls exceed recorded team fouls")
        allocated = self._allocate_integer(remaining, weights)
        return {key: allocated[key] + guaranteed[key] for key in weights}

    @staticmethod
    def _allocate_integer(
        total: int,
        weights: dict[str, float],
        *,
        capacity: dict[str, int] | None = None,
    ) -> dict[str, int]:
        result = {key: 0 for key in weights}
        if total <= 0 or not weights:
            return result
        positive = {key: max(0.0, value) for key, value in weights.items()}
        weight_sum = sum(positive.values())
        if weight_sum <= 0.0:
            positive = {key: 1.0 for key in weights}
            weight_sum = float(len(weights))

        fractions: list[tuple[float, str]] = []
        assigned = 0
        for key in sorted(positive):
            exact = total * positive[key] / weight_sum
            base = int(math.floor(exact))
            if capacity is not None:
                base = min(base, capacity.get(key, base))
            result[key] = base
            assigned += base
            fractions.append((exact - math.floor(exact), key))

        remaining = total - assigned
        fractions.sort(key=lambda item: (-item[0], item[1]))
        while remaining > 0:
            progressed = False
            for _, key in fractions:
                if remaining <= 0:
                    break
                if capacity is not None and result[key] >= capacity.get(key, result[key]):
                    continue
                result[key] += 1
                remaining -= 1
                progressed = True
            if not progressed:
                break
        return result

    def _physical_state_after(self, player: PlayerMatchSnapshot, profile: FastTeamProfile, minutes: int):
        return physical_state_after(player, profile, minutes)

    def _condition_after(self, player: PlayerMatchSnapshot, profile: FastTeamProfile, minutes: int) -> float:
        return self._physical_state_after(player, profile, minutes).condition

    def _penalty_shootout(
        self,
        home: _TeamRuntime,
        away: _TeamRuntime,
        random: FastMatchRandom,
        *,
        match_minutes: int,
    ) -> tuple[int, int, tuple[FastPenaltyKickEvent, ...]]:
        # An expulsion in the last minute still rules out shootout participation.
        shootout_minute = match_minutes + 1
        home_takers = self._penalty_takers(home, shootout_minute)
        away_takers = self._penalty_takers(away, shootout_minute)
        home_goalkeeper = self._active_goalkeeper(home, shootout_minute)
        away_goalkeeper = self._active_goalkeeper(away, shootout_minute)
        home_score = away_score = 0
        home_taken = away_taken = 0
        sequence = 0
        events: list[FastPenaltyKickEvent] = []

        def take(
            *,
            side: str,
            round_number: int,
            sudden_death: bool,
            taker: PlayerMatchSnapshot,
            goalkeeper: PlayerMatchSnapshot,
            team: _TeamRuntime,
            opponent: _TeamRuntime,
            kick_random: FastMatchRandom,
        ) -> bool:
            nonlocal home_score, away_score, home_taken, away_taken, sequence
            pressure = self._penalty_pressure(
                round_number=round_number,
                sudden_death=sudden_death,
                side=side,
                home_score=home_score,
                away_score=away_score,
                home_taken=home_taken,
                away_taken=away_taken,
            )
            scored = self._penalty_scored(
                taker,
                goalkeeper,
                team,
                opponent,
                pressure=pressure,
                match_minutes=match_minutes,
                random=kick_random,
            )
            if side == "home":
                home_taken += 1
                home_score += int(scored)
                club_id = home.team.club_id
            else:
                away_taken += 1
                away_score += int(scored)
                club_id = away.team.club_id
            sequence += 1
            events.append(
                FastPenaltyKickEvent(
                    sequence=sequence,
                    round_number=round_number,
                    club_id=club_id,
                    taker_player_id=taker.player_id,
                    goalkeeper_player_id=goalkeeper.player_id,
                    scored=scored,
                    sudden_death=sudden_death,
                    pressure=round(pressure, 3),
                    score_after_home=home_score,
                    score_after_away=away_score,
                )
            )
            return scored

        for round_index in range(5):
            round_number = round_index + 1
            take(
                side="home",
                round_number=round_number,
                sudden_death=False,
                taker=home_takers[round_index % len(home_takers)],
                goalkeeper=away_goalkeeper,
                team=home,
                opponent=away,
                kick_random=random.fork(f"home/{round_index}"),
            )
            if self._shootout_decided(home_score, away_score, home_taken, away_taken, scheduled=5):
                return home_score, away_score, tuple(events)

            take(
                side="away",
                round_number=round_number,
                sudden_death=False,
                taker=away_takers[round_index % len(away_takers)],
                goalkeeper=home_goalkeeper,
                team=away,
                opponent=home,
                kick_random=random.fork(f"away/{round_index}"),
            )
            if self._shootout_decided(home_score, away_score, home_taken, away_taken, scheduled=5):
                return home_score, away_score, tuple(events)

        sudden = 0
        while home_score == away_score and sudden < 30:
            round_number = 6 + sudden
            take(
                side="home",
                round_number=round_number,
                sudden_death=True,
                taker=home_takers[(5 + sudden) % len(home_takers)],
                goalkeeper=away_goalkeeper,
                team=home,
                opponent=away,
                kick_random=random.fork(f"home/sudden/{sudden}"),
            )
            take(
                side="away",
                round_number=round_number,
                sudden_death=True,
                taker=away_takers[(5 + sudden) % len(away_takers)],
                goalkeeper=home_goalkeeper,
                team=away,
                opponent=home,
                kick_random=random.fork(f"away/sudden/{sudden}"),
            )
            sudden += 1

        if home_score == away_score:
            # Safety valve for the vanishingly unlikely case of 30 consecutive
            # tied sudden-death rounds. Resolve through one final football kick,
            # never by selecting a winner directly.
            round_number = 6 + sudden
            while home_score == away_score:
                take(
                    side="home",
                    round_number=round_number,
                    sudden_death=True,
                    taker=home_takers[(5 + sudden) % len(home_takers)],
                    goalkeeper=away_goalkeeper,
                    team=home,
                    opponent=away,
                    kick_random=random.fork(f"home/safety/{sudden}"),
                )
                take(
                    side="away",
                    round_number=round_number,
                    sudden_death=True,
                    taker=away_takers[(5 + sudden) % len(away_takers)],
                    goalkeeper=home_goalkeeper,
                    team=away,
                    opponent=home,
                    kick_random=random.fork(f"away/safety/{sudden}"),
                )
                sudden += 1
                round_number += 1
        return home_score, away_score, tuple(events)

    @staticmethod
    def _shootout_decided(
        home_score: int,
        away_score: int,
        home_taken: int,
        away_taken: int,
        *,
        scheduled: int,
    ) -> bool:
        home_remaining = max(0, scheduled - home_taken)
        away_remaining = max(0, scheduled - away_taken)
        return (
            home_score > away_score + away_remaining
            or away_score > home_score + home_remaining
        )

    def _penalty_takers(self, runtime: _TeamRuntime, match_minutes: int) -> tuple[PlayerMatchSnapshot, ...]:
        active = runtime.active_starters_at(match_minutes)
        outfield = [player for player in active if player.assigned_position is not Position.GK]
        goalkeepers = [player for player in active if player.assigned_position is Position.GK]

        def taker_score(player: PlayerMatchSnapshot) -> tuple[float, str]:
            value = (
                0.55 * self._attr(player, "technical.penalties")
                + 0.20 * self._attr(player, "mental.composure")
                + 0.10 * self._attr(player, "technical.finishing")
                + 0.10 * player.state.confidence
                + 0.05 * player.current_rating
            )
            return value, player.player_id

        ranked = sorted(outfield, key=taker_score, reverse=True)
        # Manager-specified penalty priority applies only to available
        # players on the pitch. Others keep the established automatic order.
        preferred_ids = runtime.team.set_piece_preferences.get("penalties", ())
        available = {p.player_id: p for p in active}
        preferred = [available[pid] for pid in preferred_ids if pid in available]
        seen = {p.player_id for p in preferred}
        return tuple(preferred + [p for p in ranked if p.player_id not in seen]
                     + [p for p in sorted(goalkeepers, key=taker_score, reverse=True) if p.player_id not in seen])


    @staticmethod
    def _active_goalkeeper(runtime: _TeamRuntime, match_minutes: int) -> PlayerMatchSnapshot:
        active = runtime.active_starters_at(match_minutes)
        for player in active:
            if player.assigned_position is Position.GK:
                return player
        if active:
            # With an expelled keeper and no remaining replacement, an
            # outfield player must assume the position for the shootout.
            return max(active, key=lambda player: player.current_rating)
        raise ValueError(f"team {runtime.team.club_id!r} has no active players for the shootout")

    def _penalty_pressure(
        self,
        *,
        round_number: int,
        sudden_death: bool,
        side: str,
        home_score: int,
        away_score: int,
        home_taken: int,
        away_taken: int,
    ) -> float:
        if sudden_death:
            base = min(1.0, 0.72 + max(0, round_number - 6) * 0.035)
        else:
            base = (0.10, 0.16, 0.24, 0.38, 0.55)[min(4, round_number - 1)]

        own_score, opp_score = (home_score, away_score) if side == "home" else (away_score, home_score)
        own_taken, opp_taken = (home_taken, away_taken) if side == "home" else (away_taken, home_taken)
        if own_score < opp_score:
            base += 0.08
        if round_number >= 4 and own_score != opp_score:
            base += 0.06
        if not sudden_death:
            own_remaining_after = max(0, 5 - (own_taken + 1))
            if own_score + 1 + own_remaining_after <= opp_score:
                base += 0.10
        return self._clamp(base, 0.0, 1.0)

    def _penalty_scored(
        self,
        taker: PlayerMatchSnapshot,
        goalkeeper: PlayerMatchSnapshot,
        team: _TeamRuntime,
        opponent: _TeamRuntime,
        *,
        pressure: float,
        match_minutes: int,
        random: FastMatchRandom,
    ) -> bool:
        probability = self._penalty_probability(
            taker,
            goalkeeper,
            team,
            opponent,
            pressure=pressure,
            match_minutes=match_minutes,
        )
        return random.random() < probability

    def _penalty_probability(
        self,
        taker: PlayerMatchSnapshot,
        goalkeeper: PlayerMatchSnapshot,
        team: _TeamRuntime,
        opponent: _TeamRuntime,
        *,
        pressure: float,
        match_minutes: int,
    ) -> float:
        taker_quality = (
            0.50 * self._attr(taker, "technical.penalties")
            + 0.18 * self._attr(taker, "technical.finishing")
            + 0.22 * self._attr(taker, "mental.composure")
            + 0.10 * taker.current_rating
        )
        goalkeeper_quality = self._penalty_goalkeeper_quality(goalkeeper)
        taker_minutes = team.minutes_for(taker.player_id, match_minutes)
        keeper_minutes = opponent.minutes_for(goalkeeper.player_id, match_minutes)
        taker_condition = self._condition_after(taker, team.profile, taker_minutes)
        keeper_condition = self._condition_after(goalkeeper, opponent.profile, keeper_minutes)
        confidence = taker.state.confidence
        resilience = 0.65 * self._attr(taker, "mental.composure") + 0.35 * confidence

        probability = self.config.penalty_base_probability
        probability += (taker_quality - 70.0) * 0.0030
        probability -= (goalkeeper_quality - 70.0) * 0.0024
        probability += (confidence - 65.0) * 0.0008
        probability += (taker_condition - 70.0) * 0.00045
        probability -= (keeper_condition - 70.0) * 0.00025
        probability -= pressure * (75.0 - resilience) * 0.0015
        return self._clamp(
            probability,
            self.config.penalty_min_probability,
            self.config.penalty_max_probability,
        )

    def _penalty_goalkeeper_quality(self, goalkeeper: PlayerMatchSnapshot) -> float:
        group = goalkeeper.attributes.goalkeeping
        if group is not None:
            specialist = (
                0.45 * float(group.one_on_ones)
                + 0.35 * float(group.reflexes)
                + 0.20 * float(group.goalkeeper_positioning)
            )
        else:
            support = (
                0.40 * self._attr(goalkeeper, "mental.anticipation")
                + 0.35 * self._attr(goalkeeper, "physical.agility")
                + 0.25 * self._attr(goalkeeper, "mental.positioning")
            )
            if goalkeeper.original_position is Position.GK:
                specialist = support
            else:
                specialist = max(8.0, min(38.0, 6.0 + support * 0.32))
        return (
            0.82 * specialist
            + 0.10 * goalkeeper.state.confidence
            + 0.08 * self._attr(goalkeeper, "mental.composure")
        )

    @staticmethod
    def _aggregate_score(
        snapshot: MatchSnapshot,
        home: _TeamRuntime,
        away: _TeamRuntime,
    ) -> tuple[int, int]:
        tie = snapshot.context.competition.cup_tie
        prior_home = tie.home_aggregate_goals_before_match if tie is not None else 0
        prior_away = tie.away_aggregate_goals_before_match if tie is not None else 0
        return (
            prior_home + sum(shot.goal for shot in home.shots or []),
            prior_away + sum(shot.goal for shot in away.shots or []),
        )

    @staticmethod
    def _freeze_team_statistics(runtime: _TeamRuntime, *, opponent: _TeamRuntime) -> FastTeamStatistics:
        shots = runtime.shots or []
        goals = sum(shot.goal for shot in shots)
        on_target = sum(shot.on_target for shot in shots)
        saves = max(0, sum(shot.on_target for shot in opponent.shots or []) - sum(shot.goal for shot in opponent.shots or []))
        return FastTeamStatistics(
            possession_pct=runtime.possession,
            passes_attempted=runtime.passes_attempted,
            passes_completed=runtime.passes_completed,
            shots=len(shots),
            shots_on_target=on_target,
            xg=round(sum(shot.xg for shot in shots), 2),
            goals=goals,
            saves=saves,
            fouls=runtime.fouls,
            yellow_cards=runtime.yellow_cards,
            red_cards=runtime.red_cards,
            corners=runtime.corners,
        )

    @staticmethod
    def _execution_expression(profile: FastTeamProfile) -> float:
        """How faithfully the requested tactical intensity is expressed.

        65 is the neutral reference. Poor familiarity substantially blunts the
        plan, while elite familiarity adds only a controlled amount of extra
        precision. This is deliberately asymmetric: not knowing the system can
        hurt more than perfect familiarity can help.
        """

        score = FastMatchSimulator._clamp(profile.tactical_execution, 0.0, 100.0)
        if score >= 65.0:
            return 1.0 + ((score - 65.0) / 35.0) * 0.28
        return 1.0 - ((65.0 - score) / 65.0) * 0.68

    @staticmethod
    def _coordination_rating(profile: FastTeamProfile) -> float:
        """Rating-like effect of collective tactical understanding.

        This does not award a generic win bonus. It changes the quality of
        coordinated attacking, controlling and defending actions that feed the
        normal match processes. More demanding plans are slightly less forgiving
        when tactical familiarity is poor.
        """

        score = FastMatchSimulator._clamp(profile.tactical_execution, 0.0, 100.0)
        deviations = (
            profile.possession_style,
            profile.pressing,
            profile.directness,
            profile.defensive_depth,
            profile.tempo,
            profile.width,
            profile.risk,
            profile.defensive_compactness,
        )
        complexity = sum(abs(value - 50.0) for value in deviations) / (len(deviations) * 50.0)
        if score >= 65.0:
            return (score - 65.0) * 0.12 * (0.90 + complexity * 0.10)
        return -(65.0 - score) * 0.20 * (0.90 + complexity * 0.35)

    @staticmethod
    def _effective_centered(profile: FastTeamProfile, value: float) -> float:
        """Return an instruction on a -1..+1-ish scale after execution quality."""

        centered = (float(value) - 50.0) / 50.0
        return centered * FastMatchSimulator._execution_expression(profile)

    @staticmethod
    def _offside_trap_matchup(attacker: FastTeamProfile, defender: FastTeamProfile) -> float:
        """Small, contextual trap effect rather than an unconditional bonus.

        A high, coordinated line can catch patient build-up; a deep trap against
        direct running exposes the defence.  The opponent's plan matters.
        """
        if not defender.offside_trap:
            return 0.0
        depth = FastMatchSimulator._effective_centered(defender, defender.defensive_depth)
        press = FastMatchSimulator._effective_centered(defender, defender.pressing)
        direct = FastMatchSimulator._effective_centered(attacker, attacker.directness)
        return FastMatchSimulator._clamp(
            0.50 * depth + 0.35 * press - 0.70 * max(0.0, direct), -0.8, 0.8
        )

    @staticmethod
    def _tactical_shot_edge(attacker: FastTeamProfile, defender: FastTeamProfile) -> float:
        """Shot-volume effect from how the two plans interact.

        Every term has an opponent-dependent counterpoint, so selecting a high
        value is never a universal bonus. Examples: directness attacks a high
        line but loses much of that edge against a low block; pressing disrupts
        possession build-up but direct play can bypass it; width stretches a
        compact defence.
        """

        a_direct = FastMatchSimulator._effective_centered(attacker, attacker.directness)
        a_width = FastMatchSimulator._effective_centered(attacker, attacker.width)
        a_press = FastMatchSimulator._effective_centered(attacker, attacker.pressing)
        a_possession = FastMatchSimulator._effective_centered(attacker, attacker.possession_style)
        d_depth = FastMatchSimulator._effective_centered(defender, defender.defensive_depth)
        d_compact = FastMatchSimulator._effective_centered(defender, defender.defensive_compactness)
        d_press = FastMatchSimulator._effective_centered(defender, defender.pressing)
        d_possession = FastMatchSimulator._effective_centered(defender, defender.possession_style)
        d_risk = FastMatchSimulator._effective_centered(defender, defender.risk)

        edge = 0.0
        edge += 1.60 * a_direct * d_depth
        edge += 0.95 * a_width * d_compact
        edge += 0.75 * a_press * d_possession
        edge -= 0.85 * a_possession * d_press
        edge -= 0.90 * FastMatchSimulator._offside_trap_matchup(attacker, defender)
        edge += 0.70 * a_direct * d_press
        edge += 0.45 * d_risk
        return FastMatchSimulator._clamp(edge, -2.60, 2.60)

    @staticmethod
    def _tactical_quality_edge(attacker: FastTeamProfile, defender: FastTeamProfile) -> float:
        """Per-shot chance-quality effect from tactical matchup."""

        a_direct = FastMatchSimulator._effective_centered(attacker, attacker.directness)
        a_width = FastMatchSimulator._effective_centered(attacker, attacker.width)
        a_press = FastMatchSimulator._effective_centered(attacker, attacker.pressing)
        a_possession = FastMatchSimulator._effective_centered(attacker, attacker.possession_style)
        d_depth = FastMatchSimulator._effective_centered(defender, defender.defensive_depth)
        d_compact = FastMatchSimulator._effective_centered(defender, defender.defensive_compactness)
        d_press = FastMatchSimulator._effective_centered(defender, defender.pressing)
        d_possession = FastMatchSimulator._effective_centered(defender, defender.possession_style)
        d_risk = FastMatchSimulator._effective_centered(defender, defender.risk)
        d_central = FastMatchSimulator._effective_centered(defender, defender.central_protection)

        width_escape = 1.0 - 0.55 * max(0.0, min(1.0, a_width))
        edge = 0.0
        edge += 0.014 * a_direct * d_depth
        edge += 0.007 * a_width * d_compact
        edge += 0.008 * a_press * d_possession
        edge -= 0.009 * a_possession * d_press
        edge -= 0.007 * FastMatchSimulator._offside_trap_matchup(attacker, defender)
        edge += 0.007 * a_direct * d_press
        edge += 0.005 * d_risk
        edge -= 0.010 * d_central * width_escape
        return FastMatchSimulator._clamp(edge, -0.030, 0.030)

    @staticmethod
    def _weighted_choice(items, weights: list[float], random: FastMatchRandom):
        total = sum(max(0.0, weight) for weight in weights)
        if total <= 0.0:
            return items[0]
        threshold = random.random() * total
        running = 0.0
        for item, weight in zip(items, weights, strict=True):
            running += max(0.0, weight)
            if running >= threshold:
                return item
        return items[-1]

    @staticmethod
    def _overdispersed_count(mean: float, random: FastMatchRandom, *, dispersion: float) -> int:
        if mean <= 0.0:
            return 0
        sampled_mean = random.gammavariate(dispersion, mean / dispersion)
        return FastMatchSimulator._poisson(sampled_mean, random.fork("poisson"))

    @staticmethod
    def _poisson(mean: float, random: FastMatchRandom) -> int:
        if mean <= 0.0:
            return 0
        if mean > 30.0:
            return max(0, int(round(random.gauss(mean, math.sqrt(mean)))))
        limit = math.exp(-mean)
        count = 0
        product = 1.0
        while product > limit:
            count += 1
            product *= random.random()
        return count - 1

    @staticmethod
    def _binomial_approx(trials: int, probability: float, random: FastMatchRandom) -> int:
        if trials <= 0:
            return 0
        probability = FastMatchSimulator._clamp(probability, 0.0, 1.0)
        mean = trials * probability
        variance = trials * probability * (1.0 - probability)
        if variance < 1.0:
            successes = sum(random.random() < probability for _ in range(trials))
            return successes
        return max(0, min(trials, int(round(random.gauss(mean, math.sqrt(variance))))))

    @staticmethod
    def _clamp(value: float, low: float, high: float) -> float:
        return max(low, min(high, value))


def _safe_mean(*values: float) -> float:
    return sum(values) / len(values) if values else 0.0
