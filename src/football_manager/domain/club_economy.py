"""TS-24.2 persistent club money and employment, independent of UI ownership.

Amounts are exact integer GBP. No player rating, age curve or PA is modified.
These records are fictional initial estimates, not claims about real salaries.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date

CONTRACT_ROLES = ('star', 'important', 'regular', 'rotation', 'backup')
CONTRACT_KINDS = ('professional', 'academy', 'temporary')
MAX_AMOUNT = 20_000_000_000


@dataclass(frozen=True, slots=True)
class WagePeriod:
    """Historical wage coverage used for prorated payroll after a renewal."""
    starts_on: date
    ends_on: date
    weekly_gbp: int

    def validate(self) -> None:
        if (type(self.starts_on) is not date or type(self.ends_on) is not date
                or self.ends_on < self.starts_on or type(self.weekly_gbp) is not int
                or not 0 <= self.weekly_gbp <= 2_000_000):
            raise ValueError('invalid wage period')


@dataclass(frozen=True, slots=True)
class PlayerContract:
    player_id: str
    club_id: str
    signed_on: date
    expires_on: date
    weekly_wage_gbp: int
    role: str = 'regular'
    kind: str = 'professional'
    history: tuple[WagePeriod, ...] = ()
    renewed_on: date | None = None

    def validate(self) -> None:
        if (not self.player_id or not self.club_id or type(self.signed_on) is not date
                or type(self.expires_on) is not date or self.signed_on > self.expires_on
                or self.role not in CONTRACT_ROLES or self.kind not in CONTRACT_KINDS
                or type(self.weekly_wage_gbp) is not int
                or not 0 <= self.weekly_wage_gbp <= 2_000_000):
            raise ValueError('invalid professional player contract')
        if self.renewed_on is not None and (type(self.renewed_on) is not date or self.renewed_on < self.signed_on):
            raise ValueError('invalid renewal date')
        for period in self.history:
            if not isinstance(period, WagePeriod):
                raise ValueError('invalid contract history')
            period.validate()


@dataclass(frozen=True, slots=True)
class FinanceMonth:
    period_start: date
    income_gbp: int
    wages_gbp: int
    operations_gbp: int
    closing_cash_gbp: int

    def validate(self) -> None:
        if type(self.period_start) is not date or self.period_start.day != 1:
            raise ValueError('invalid statement period')
        for amount in (self.income_gbp, self.wages_gbp, self.operations_gbp):
            if type(amount) is not int or not 0 <= amount <= MAX_AMOUNT:
                raise ValueError('invalid statement amount')
        if type(self.closing_cash_gbp) is not int or not -MAX_AMOUNT <= self.closing_cash_gbp <= MAX_AMOUNT:
            raise ValueError('invalid closing cash')


@dataclass(frozen=True, slots=True)
class ClubFinances:
    club_id: str
    cash_gbp: int
    transfer_budget_gbp: int
    wage_budget_weekly_gbp: int
    recurring_income_gbp: int
    recurring_operations_gbp: int
    season_income_gbp: int = 0
    season_wages_gbp: int = 0
    season_operations_gbp: int = 0
    history: tuple[FinanceMonth, ...] = ()

    def validate(self) -> None:
        if not self.club_id or type(self.cash_gbp) is not int or not -MAX_AMOUNT <= self.cash_gbp <= MAX_AMOUNT:
            raise ValueError('invalid club cash')
        for amount in (self.transfer_budget_gbp, self.wage_budget_weekly_gbp,
                       self.recurring_income_gbp, self.recurring_operations_gbp,
                       self.season_income_gbp, self.season_wages_gbp, self.season_operations_gbp):
            if type(amount) is not int or not 0 <= amount <= MAX_AMOUNT:
                raise ValueError('invalid club budget amount')
        for month in self.history:
            if not isinstance(month, FinanceMonth):
                raise ValueError('invalid finance history')
            month.validate()
        if any(a.period_start >= b.period_start for a, b in zip(self.history, self.history[1:])):
            raise ValueError('finance history is not chronological')
