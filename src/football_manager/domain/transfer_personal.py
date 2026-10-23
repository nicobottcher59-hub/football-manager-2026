"""Persistent player-agent offers for TS-24.4.

Terms are separate from an existing player's current professional contract.
An unsigned agreement is not a player registration or a financial payment.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import date

from football_manager.domain.club_economy import CONTRACT_ROLES


@dataclass(frozen=True, slots=True)
class ContractBonus:
    kind: str  # recorded milestones, not promises about untracked stats
    threshold: int
    amount_gbp: int

    def validate(self) -> None:
        limits = {'appearances': (5, 100), 'goals': (3, 50),
                  'assists': (3, 50), 'clean_sheets': (3, 35), 'promotion': (1, 1)}
        if (self.kind not in limits or type(self.threshold) is not int
                or not limits[self.kind][0] <= self.threshold <= limits[self.kind][1]
                or type(self.amount_gbp) is not int or not 1_000 <= self.amount_gbp <= 10_000_000):
            raise ValueError('Invalid personal contract bonus')


@dataclass(frozen=True, slots=True)
class PersonalTerms:
    weekly_wage_gbp: int
    years: int
    role: str
    signing_bonus_gbp: int = 0
    bonuses: tuple[ContractBonus, ...] = ()

    def validate(self) -> None:
        if (type(self.weekly_wage_gbp) is not int or not 0 <= self.weekly_wage_gbp <= 1_500_000
                or type(self.years) is not int or not 1 <= self.years <= 5
                or self.role not in CONTRACT_ROLES
                or type(self.signing_bonus_gbp) is not int
                or not 0 <= self.signing_bonus_gbp <= 50_000_000
                or type(self.bonuses) is not tuple or len(self.bonuses) > 3):
            raise ValueError('Invalid personal contract terms')
        seen=set()
        for bonus in self.bonuses:
            if not isinstance(bonus, ContractBonus):
                raise ValueError('Invalid personal contract bonus')
            bonus.validate()
            if bonus.kind in seen:
                raise ValueError('Duplicate personal contract milestone')
            seen.add(bonus.kind)


@dataclass(frozen=True, slots=True)
class PersonalEvent:
    on_date: date
    actor: str  # 'club' or 'agent'
    terms: PersonalTerms
    note: str

    def validate(self) -> None:
        if (type(self.on_date) is not date or self.actor not in ('club', 'agent')
                or not isinstance(self.terms, PersonalTerms)
                or type(self.note) is not str or len(self.note) > 240):
            raise ValueError('Invalid agent conversation event')
        self.terms.validate()
