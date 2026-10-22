"""TS-26: lightweight staff, training policy and episode-specific medical decisions.

Facilities aren't modeled yet. Persist an explicit provisional capacity so the
future facility subsystem can replace its *source*, not the staff contracts.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date
from math import isfinite

ROLES = ('coach', 'medic', 'fitness', 'scout')
INTENSITIES = ('auto', 'light', 'balanced', 'intense')


@dataclass(frozen=True, slots=True)
class StaffMember:
    member_id: str
    club_id: str
    name: str
    role: str
    quality: int
    wage_weekly_gbp: int
    hired_on: date
    contract_until: date

    def validate(self) -> None:
        if (not self.member_id or not self.club_id or not self.name or self.role not in ROLES
                or type(self.quality) is not int or not 1 <= self.quality <= 100
                or type(self.wage_weekly_gbp) is not int or not 100 <= self.wage_weekly_gbp <= 50_000
                or type(self.hired_on) is not date or type(self.contract_until) is not date
                or self.contract_until <= self.hired_on):
            raise ValueError('invalid staff contract')


@dataclass(slots=True)
class TrainingPolicy:
    """One automatic workload policy for the first team, with ID-keyed exceptions.

    No starter/bench/reserve workload settings and no separate physical
    protection switch. Existing saved policies are migrated explicitly.
    """
    performance_max: int = 50
    performance_focus: int = 60
    energy_max: int = 50
    energy_focus: int = 60
    individual_intensities: dict[str, str] = field(default_factory=dict)

    def validate(self) -> None:
        for maximum, focused in ((self.performance_max, self.performance_focus),
                                 (self.energy_max, self.energy_focus)):
            if (type(maximum) is not int or type(focused) is not int
                    or not 0 <= maximum < focused <= 100):
                raise ValueError('automatic training thresholds must be ordered, 0–100')
        if (not isinstance(self.individual_intensities, dict)
                or len(self.individual_intensities) > 100
                or any(not isinstance(player_id, str) or not player_id or len(player_id) > 120
                       or mode not in INTENSITIES
                       for player_id, mode in self.individual_intensities.items())):
            raise ValueError('invalid individual training overrides')


@dataclass(slots=True)
class MedicalDecision:
    player_id: str
    episode_id: str
    method: str
    decided_on: date
    original_return: date
    planned_return: date
    relapse_risk: float
    will_relapse: bool
    relapse_days: int
    player_preference: str
    status: str = 'active'

    def validate(self) -> None:
        if (not self.player_id or not self.episode_id or self.method not in ('conservative', 'aggressive')
                or self.player_preference not in ('conservative', 'aggressive', 'neutral')
                or self.status not in ('active', 'relapsed', 'completed')
                or type(self.decided_on) is not date or type(self.original_return) is not date
                or type(self.planned_return) is not date or self.planned_return < self.decided_on
                or not isfinite(self.relapse_risk) or not 0 <= self.relapse_risk <= 0.40
                or type(self.will_relapse) is not bool or type(self.relapse_days) is not int
                or not 0 <= self.relapse_days <= 30):
            raise ValueError('invalid medical treatment')


@dataclass(slots=True)
class ProfessionalScoutAssignment:
    player_id: str
    scout_id: str
    started_on: date
    progress_points: int = 0

    def validate(self) -> None:
        if (not self.player_id or not self.scout_id or type(self.started_on) is not date
                or type(self.progress_points) is not int or not 0 <= self.progress_points < 100):
            raise ValueError('invalid professional scouting assignment')


@dataclass(frozen=True, slots=True)
class ProfessionalScoutReport:
    player_id: str
    scout_id: str
    completed_on: date
    player_name: str
    club_name: str
    position: str
    overall: float
    age: int
    value_gbp: int
    strengths: tuple[str, ...]
    verdict: str

    def validate(self) -> None:
        if (not self.player_id or not self.scout_id or not self.player_name
                or not self.club_name or not self.position or type(self.completed_on) is not date
                or not isfinite(self.overall) or not 1 <= self.overall <= 100
                or type(self.age) is not int or not 14 <= self.age <= 60
                or type(self.value_gbp) is not int or not 0 <= self.value_gbp <= 1_000_000_000
                or not 1 <= len(self.strengths) <= 3 or any(not s or len(s) > 45 for s in self.strengths)
                or not self.verdict or len(self.verdict) > 280):
            raise ValueError('invalid professional scouting report')


@dataclass(slots=True)
class ClubSupport:
    club_id: str
    capacity: dict[str, int]
    members: dict[str, StaffMember] = field(default_factory=dict)
    training: TrainingPolicy = field(default_factory=TrainingPolicy)
    treatments: dict[str, MedicalDecision] = field(default_factory=dict)
    # Sum of mild training-quality adjustments + number of actual trained days.
    training_days: dict[str, tuple[float, int]] = field(default_factory=dict)
    scouting_assignments: dict[str, ProfessionalScoutAssignment] = field(default_factory=dict)
    scouting_reports: dict[str, ProfessionalScoutReport] = field(default_factory=dict)
    # TS-UI-08: career-persistent independent shortlist and scout territories.
    scouting_shortlist: dict[str, str] = field(default_factory=dict)
    scouting_destinations: dict[str, str] = field(default_factory=dict)
    capacity_source: str = 'provisional-original-division-v1'
    baseline_weekly_gbp: int = 0  # Staff cost included in the original overhead proxy.

    def validate(self) -> None:
        if (not self.club_id or set(self.capacity) != set(ROLES)
                or any(type(n) is not int or not 1 <= n <= 8 for n in self.capacity.values())
                or not self.capacity_source or type(self.baseline_weekly_gbp) is not int
                or self.baseline_weekly_gbp < 0):
            raise ValueError('invalid club staff capacity')
        self.training.validate()
        for ident, member in self.members.items():
            member.validate()
            if member.club_id != self.club_id or ident != member.member_id:
                raise ValueError('staff identity mismatch')
        for ident, decision in self.treatments.items():
            decision.validate()
            if ident != decision.player_id:
                raise ValueError('treatment identity mismatch')
        if len(self.scouting_assignments) > 16 or len(self.scouting_reports) > 400:
            raise ValueError('professional scouting history is too large')
        for player_id, assignment in self.scouting_assignments.items():
            assignment.validate()
            if player_id != assignment.player_id:
                raise ValueError('professional scouting assignment mismatch')
        for player_id, report in self.scouting_reports.items():
            report.validate()
            if player_id != report.player_id:
                raise ValueError('professional scouting report mismatch')
        if (not isinstance(self.scouting_shortlist, dict) or len(self.scouting_shortlist) > 300
                or any(not isinstance(pid, str) or not pid or len(pid) > 160
                       or priority not in ('top', 'future', 'monitor')
                       for pid, priority in self.scouting_shortlist.items())):
            raise ValueError('invalid professional scouting shortlist')
        if (not isinstance(self.scouting_destinations, dict) or len(self.scouting_destinations) > 8
                or any(not isinstance(mid, str) or not mid or len(mid) > 160
                       or not isinstance(region, str) or len(region) > 100
                       or not (region == 'all' or region.startswith(('country:', 'league:')))
                       for mid, region in self.scouting_destinations.items())):
            raise ValueError('invalid scout destinations')
        for player_id, (score, days) in self.training_days.items():
            if not player_id or not isfinite(score) or type(days) is not int or days < 0 or days > 370:
                raise ValueError('invalid accumulated training days')
