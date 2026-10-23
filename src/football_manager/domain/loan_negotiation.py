"""TS-FIX-06: auditable, multi-round loan negotiations.

A loan offer never registers a player or pays a fee until both clubs agree.
The option-to-buy captures the complete agreed permanent-transfer structure.
"""
from __future__ import annotations
from dataclasses import dataclass
from datetime import date
from .transfer_negotiation import TransferTerms


@dataclass(frozen=True, slots=True)
class LoanTerms:
    months: int
    borrower_wage_percent: int
    playing_time: str
    recall_allowed: bool = False
    purchase: TransferTerms | None = None

    def validate(self):
        if (type(self.months) is not int or self.months not in (6, 12, 24)
                or type(self.borrower_wage_percent) is not int
                or not 0 <= self.borrower_wage_percent <= 100
                or self.playing_time not in ('starter', 'rotation', 'backup')
                or type(self.recall_allowed) is not bool):
            raise ValueError('Invalid duration, salary percentage, minutes or recall option')
        if self.purchase is not None:
            if not isinstance(self.purchase, TransferTerms):
                raise ValueError('Invalid future purchase terms')
            self.purchase.validate()
            if self.purchase.guaranteed_gbp < 5_000:
                raise ValueError('Purchase option must guarantee at least GBP 5,000')


@dataclass(frozen=True, slots=True)
class LoanRound:
    on_date: date
    by_club_id: str
    terms: LoanTerms
    note: str

    def validate(self):
        if type(self.on_date) is not date or not self.by_club_id or not isinstance(self.terms, LoanTerms) or not isinstance(self.note, str) or len(self.note) > 240:
            raise ValueError('Invalid loan negotiating event')
        self.terms.validate()


@dataclass(frozen=True, slots=True)
class LoanTalk:
    talk_id: str
    player_id: str
    parent_id: str
    borrower_id: str
    started_on: date
    expires_on: date
    status: str  # counter, agreed, pending_window, active, broken, walked, expired, failed
    terms: LoanTerms
    rounds: tuple[LoanRound, ...]
    patience: int = 100
    loan_id: str | None = None
    reason: str = ''
    # An AI club may propose a permanent transfer in this same conversation.
    linked_transfer_deal_id: str | None = None
    source_transfer_deal_id: str | None = None

    def validate(self):
        if (not self.talk_id or not self.player_id or not self.parent_id or not self.borrower_id
                or self.parent_id == self.borrower_id or type(self.started_on) is not date
                or type(self.expires_on) is not date or self.expires_on < self.started_on
                or self.status not in ('counter','agreed','pending_window','active','broken','walked','expired','failed','converted')
                or not isinstance(self.terms, LoanTerms) or type(self.rounds) is not tuple
                or not 1 <= len(self.rounds) <= 24 or type(self.patience) is not int
                or not 0 <= self.patience <= 100 or not isinstance(self.reason,str) or len(self.reason)>240
                or (self.linked_transfer_deal_id is not None and not isinstance(self.linked_transfer_deal_id,str))
                or (self.source_transfer_deal_id is not None and not isinstance(self.source_transfer_deal_id,str))):
            raise ValueError('Invalid loan negotiation')
        self.terms.validate()
        for round_ in self.rounds:
            if not isinstance(round_, LoanRound) or round_.by_club_id not in (self.parent_id,self.borrower_id):
                raise ValueError('Invalid club response in loan negotiation')
            round_.validate()
        if self.terms != self.rounds[-1].terms:
            raise ValueError('Latest loan terms and timeline disagree')
        if self.status == 'active' and not self.loan_id:
            raise ValueError('An active loan talk must point at its agreement')
