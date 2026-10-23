"""TS-24.6: persistent loans and unsigned professionals.

The parent owns the employment contract while the borrowing club registers the
player for matches. No installment payments and no mandatory purchase options.
"""
from __future__ import annotations
from dataclasses import dataclass
from datetime import date
from .player import Player
from .transfer_negotiation import TransferTerms


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
    recall_allowed: bool = True  # compatibility: TS-24 loans allowed recall
    purchase_terms: TransferTerms | None = None
    option_pending_deal_id: str | None = None
    loan_fee_gbp: int = 0  # settled exactly once on the registration date

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
                or (self.option_pending_deal_id is not None and
                    (not isinstance(self.option_pending_deal_id,str) or not self.option_gbp))
                or type(self.recall_allowed) is not bool
                or type(self.loan_fee_gbp) is not int or not 0 <= self.loan_fee_gbp <= 500_000_000
                or (self.purchase_terms is not None and not isinstance(self.purchase_terms, TransferTerms))
                or (self.purchase_terms is not None and self.option_gbp != self.purchase_terms.guaranteed_gbp)
                or any(type(n) is not int or n < 0 for n in
                       (self.appearances_at_start,self.minutes_at_start))):
            raise ValueError('Invalid loan agreement')
        if self.purchase_terms is not None:
            self.purchase_terms.validate()


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
