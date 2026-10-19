"""TS-23: persistent youth academy records and fixture data.

U15 is deliberately a *preview* cohort, not a playable squad. U17/U21
contain genuine Player objects; promotion never creates a replacement identity.
Exact potential stays private to the simulation and save graph.
"""
from __future__ import annotations
from dataclasses import dataclass, field
from datetime import date
from football_manager.domain.player import Player
from football_manager.domain.enums import Position


@dataclass(frozen=True, slots=True)
class YouthPreview:
    player_id: str
    first_name: str
    last_name: str
    birth_date: date
    nationality: str
    position: Position
    initial_ovr: float
    potential_budget: float
    source: str = 'local-academy'

    def age_on(self, today: date) -> int:
        return today.year - self.birth_date.year - ((today.month, today.day) < (self.birth_date.month, self.birth_date.day))

    @property
    def id(self) -> str:
        return self.player_id

    @property
    def full_name(self) -> str:
        return f'{self.first_name} {self.last_name}'


@dataclass(slots=True)
class YouthAcademy:
    club_id: str
    u15: dict[str, YouthPreview] = field(default_factory=dict)
    u17: dict[str, Player] = field(default_factory=dict)
    u21: dict[str, Player] = field(default_factory=dict)
    graduates: dict[str, str] = field(default_factory=dict)
    released: int = 0


@dataclass(slots=True)
class YouthFixture:
    fixture_id: str
    division: str
    level: str
    home_club_id: str
    away_club_id: str
    match_date: date
    home_goals: int | None = None
    away_goals: int | None = None


@dataclass(slots=True)
class YouthScout:
    scout_id: str
    quality: int
    country: str = 'England'
    position: str = 'any'
    started_on: date | None = None
    next_report: date | None = None
    reports_sent: int = 0
    name: str = ''
    hired_on: date | None = None
    contract_until: date | None = None
    signing_fee: int = 0
    monthly_wage: int = 0


@dataclass(slots=True)
class YouthScoutingCandidate:
    preview: YouthPreview
    discovered_on: date
    scout_id: str
    confidence: int
    watched: int = 0
    status: str = 'available'


@dataclass(slots=True)
class YouthSystem:
    seed: int
    season_label: str
    last_processed: date
    academies: dict[str, YouthAcademy] = field(default_factory=dict)
    fixtures: dict[str, YouthFixture] = field(default_factory=dict)
    scouts: dict[str, YouthScout] = field(default_factory=dict)
    candidates: dict[str, YouthScoutingCandidate] = field(default_factory=dict)
    season_promotion: str = ''
    generated_reports: int = 0
    # User-selected players are *never* counted as newly created players when moved.
    promoted_to_first: dict[str, str] = field(default_factory=dict)
    managed_club_id: str = ''
    # Recruitment allocation is deliberately separate from the future full
    # club-finance model. No funds are silently deducted from placeholder UI.
    recruitment_funds: int = 500_000
    recruitment_spent: int = 0
    last_scout_payroll: date | None = None
    lost_prospects: dict[str, tuple[str, date, str]] = field(default_factory=dict)

    def check_unique(self, registry) -> None:
        used = set(registry.retired_players)
        for club in registry.clubs.values():
            for player in club.squad.players:
                if player.id in used:
                    raise ValueError('duplicate youth/first-team player ID')
                used.add(player.id)
        for academy in self.academies.values():
            for roster in (academy.u15, academy.u17, academy.u21):
                for pid in roster:
                    if pid in used:
                        raise ValueError('duplicate youth/first-team player ID')
                    used.add(pid)
        for pid, candidate in self.candidates.items():
            if pid in used or candidate.preview.player_id != pid:
                raise ValueError('duplicate scout candidate')
            used.add(pid)
