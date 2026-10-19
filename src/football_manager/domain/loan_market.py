"""TS-24.6: persistent loans and unsigned professionals.

The parent owns the employment contract while the borrowing club registers the
player for matches. No installment payments and no mandatory purchase options.
"""
from __future__ import annotations
from dataclasses import dataclass
from datetime import date
from .player import Player


@dataclass(frozen=True, slots=True)
class LoanAgreement:
    loan_id: str
    player_id: str
    parent_id: str
    borrower_id: str
    started_on: date
    ends_on: date
    borrower_wage_percent: int
    playing_time: str
    option_gbp: int | None = None
    status: str = 'active'  # active, returned, purchased, retired
    completed_on: date | None = None
    appearances_at_start: int = 0
    minutes_at_start: int = 0

    def validate(self) -> None:
        from football_manager.services.club_economy import _date_plus_months
        if (not self.loan_id or not self.player_id or not self.parent_id or not self.borrower_id
                or self.parent_id == self.borrower_id or type(self.started_on) is not date
                or type(self.ends_on) is not date or self.ends_on <= self.started_on
                or self.ends_on not in tuple(_date_plus_months(self.started_on,m) for m in (6,12,24))
                or type(self.borrower_wage_percent) is not int
                or not 0 <= self.borrower_wage_percent <= 100
                or self.playing_time not in ('starter','rotation','backup')
                or (self.option_gbp is not None and (type(self.option_gbp) is not int
                    or not 5_000 <= self.option_gbp <= 500_000_000))
                or self.status not in ('active','returned','purchased','retired')
                or (self.status == 'active') != (self.completed_on is None)
                or self.completed_on is not None and (type(self.completed_on) is not date
                    or self.completed_on < self.started_on)
                or any(type(n) is not int or n < 0 for n in
                       (self.appearances_at_start,self.minutes_at_start))):
            raise ValueError('Invalid loan agreement')


@dataclass(frozen=True, slots=True)
class FreeAgent:
    player: Player
    previous_club_id: str
    released_on: date
    previous_wage_gbp: int

    def validate(self) -> None:
        if (not isinstance(self.player,Player) or not self.previous_club_id
                or type(self.released_on) is not date
                or type(self.previous_wage_gbp) is not int
                or not 0 <= self.previous_wage_gbp <= 2_000_000):
            raise ValueError('Invalid unsigned player')
