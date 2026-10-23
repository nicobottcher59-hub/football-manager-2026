"""TS-24.3 persistent preliminary inter-club talks; no player transfer yet.

All pounds are integer GBP. Agreements are contingent on TS-24.4 player
consent, registration and actual clearing, so they transfer no money or players.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import date

from .transfer_personal import PersonalTerms, PersonalEvent

MAX_FEE = 500_000_000
BONUS_KINDS = ('appearances', 'goals', 'assists', 'promotion')


@dataclass(frozen=True, slots=True)
class TransferBonus:
    kind: str
    threshold: int
    amount_gbp: int

    def validate(self) -> None:
        limits = {'appearances': (10, 100), 'goals': (5, 40),
                  'assists': (5, 35), 'promotion': (1, 1)}
        if (self.kind not in limits or type(self.threshold) is not int
                or not limits[self.kind][0] <= self.threshold <= limits[self.kind][1]
                or type(self.amount_gbp) is not int or not 10_000 <= self.amount_gbp <= MAX_FEE):
            raise ValueError('Invalid conditional bonus')


@dataclass(frozen=True, slots=True)
class TransferTerms:
    fixed_gbp: int
    bonuses: tuple[TransferBonus, ...] = ()
    sell_on_type: str = 'none'  # gross or profit, never both simultaneously
    sell_on_percent: int = 0
    buyback_gbp: int | None = None
    buyback_until: date | None = None
    # TS-FIX-02: fixed_gbp is cash at registration; deferred cash is guaranteed too.
    installments_gbp: int = 0
    installment_count: int = 0
    installment_interval_months: int = 0

    @property
    def guaranteed_gbp(self) -> int:
        return self.fixed_gbp + self.installments_gbp

    def validate(self) -> None:
        if type(self.fixed_gbp) is not int or not 0 <= self.fixed_gbp <= MAX_FEE:
            raise ValueError('Enter a non-negative upfront payment (technical limit: GBP 500 million)')
        if (type(self.installments_gbp) is not int or not 0 <= self.installments_gbp <= MAX_FEE
                or type(self.installment_count) is not int
                or type(self.installment_interval_months) is not int):
            raise ValueError('Invalid installment amount or schedule')
        if self.installments_gbp:
            if (self.installment_count not in (2, 4, 6)
                    or self.installment_interval_months not in (6, 12, 18)
                    or self.installments_gbp < self.installment_count):
                raise ValueError('Choose 2, 4 or 6 positive installments, every 6, 12 or 18 months')
        elif self.installment_count or self.installment_interval_months:
            raise ValueError('A payment schedule requires a positive installment total')
        if self.guaranteed_gbp > MAX_FEE:
            raise ValueError('Technical guaranteed-total limit is GBP 500 million')
        if type(self.bonuses) is not tuple or len(self.bonuses) > 3:
            raise ValueError('At most three distinct conditional bonuses')
        seen = set()
        for bonus in self.bonuses:
            if not isinstance(bonus, TransferBonus):
                raise ValueError('Invalid bonus type')
            bonus.validate()
            if bonus.kind in seen:
                raise ValueError('Only one bonus per achievement')
            seen.add(bonus.kind)
        if sum(b.amount_gbp for b in self.bonuses) > MAX_FEE:
            raise ValueError('Excessive contingent fee')
        if self.sell_on_type not in ('none', 'gross', 'profit'):
            raise ValueError('Invalid future-sale mechanism')
        if (type(self.sell_on_percent) is not int or not 0 <= self.sell_on_percent <= 35
                or (self.sell_on_type == 'none') != (self.sell_on_percent == 0)):
            raise ValueError('Invalid future-sale percentage')
        if (self.buyback_gbp is None) != (self.buyback_until is None):
            raise ValueError('Buyback price requires an expiration date')
        if self.buyback_gbp is not None and (type(self.buyback_gbp) is not int
                or not 5_000 <= self.buyback_gbp <= MAX_FEE
                or type(self.buyback_until) is not date):
            raise ValueError('Invalid buyback terms')


@dataclass(frozen=True, slots=True)
class NegotiationEvent:
    on_date: date
    by_club_id: str
    terms: TransferTerms
    note: str

    def validate(self) -> None:
        if type(self.on_date) is not date or not self.by_club_id or not isinstance(self.terms, TransferTerms):
            raise ValueError('Invalid offer event')
        self.terms.validate()
        if not isinstance(self.note,str) or len(self.note)>240:
            raise ValueError('Invalid negotiation event note')


@dataclass(frozen=True, slots=True)
class TransferNegotiation:
    deal_id: str
    player_id: str
    seller_id: str
    buyer_id: str
    started_on: date
    expires_on: date
    status: str  # manager_turn, agreed, completed, failed, rejected, withdrawn, expired
    proposed_by: str
    terms: TransferTerms
    events: tuple[NegotiationEvent, ...]
    reason: str = ''
    refusal_count: int = 0
    personal_status: str = 'not_started'  # not_started, counter, completed, declined
    personal_terms: PersonalTerms | None = None
    personal_events: tuple[PersonalEvent, ...] = ()
    personal_refusals: int = 0
    personal_patience: int = 100
    sell_on_paid_gbp: int = 0
    bonus_baseline: tuple[int, int, int] = (0, 0, 0)
    bonus_paid: tuple[str, ...] = ()
    buyer_tier_at_signing: int = 0
    tolerance_remaining: int = 100
    settled_on: date | None = None
    installments_paid: int = 0

    def validate(self) -> None:
        if (not self.deal_id or not self.player_id or not self.seller_id or not self.buyer_id
                or self.seller_id == self.buyer_id or type(self.started_on) is not date
                or type(self.expires_on) is not date or self.expires_on < self.started_on
                or self.status not in ('manager_turn', 'agreed', 'completed', 'failed', 'rejected', 'withdrawn', 'expired')
                or self.proposed_by not in (self.seller_id, self.buyer_id)
                or not isinstance(self.terms, TransferTerms) or not isinstance(self.events, tuple)
                or not self.events or len(self.events) > 32 or not 0 <= self.refusal_count <= 32):
            raise ValueError('Invalid recorded transfer negotiation')
        self.terms.validate()
        if type(self.tolerance_remaining) is not int or not 0 <= self.tolerance_remaining <= 100:
            raise ValueError('Invalid negotiation tolerance')
        if self.settled_on is not None and (type(self.settled_on) is not date or self.settled_on < self.started_on):
            raise ValueError('Invalid transfer completion date')
        if (type(self.installments_paid) is not int
                or not 0 <= self.installments_paid <= self.terms.installment_count):
            raise ValueError('Invalid settled installment count')
        if self.installments_paid and self.status != 'completed':
            raise ValueError('Uncompleted transfers cannot have paid installments')
        if self.status == 'completed' and self.terms.installments_gbp and self.settled_on is None:
            raise ValueError('Deferred payments require the actual registration date')
        if (self.personal_status not in ('not_started', 'counter', 'completed', 'declined')
                or type(self.personal_refusals) is not int or not 0 <= self.personal_refusals <= 8
                or type(self.personal_patience) is not int or not 0 <= self.personal_patience <= 100
                or type(self.personal_events) is not tuple or len(self.personal_events) > 16
                or type(self.sell_on_paid_gbp) is not int or self.sell_on_paid_gbp < 0
                or type(self.bonus_baseline) is not tuple or len(self.bonus_baseline) != 3
                or any(type(x) is not int or x < 0 for x in self.bonus_baseline)
                or type(self.bonus_paid) is not tuple or len(set(self.bonus_paid)) != len(self.bonus_paid)
                or any(kind not in ('appearances','goals','assists','promotion') for kind in self.bonus_paid)
                or type(self.buyer_tier_at_signing) is not int or self.buyer_tier_at_signing not in range(5)):
            raise ValueError('Invalid personal negotiation state')
        if self.personal_terms is not None:
            if not isinstance(self.personal_terms, PersonalTerms):
                raise ValueError('Invalid personal offer type')
            self.personal_terms.validate()
        if self.personal_status in ('counter','completed') and self.personal_terms is None:
            raise ValueError('Agent counter/agreement is missing contract terms')
        if self.status == 'completed' and self.personal_status != 'completed':
            raise ValueError('Completed transfer requires player consent')
        if self.personal_events and self.personal_terms != self.personal_events[-1].terms:
            raise ValueError('Latest personal event differs from recorded terms')
        for event in self.personal_events:
            if not isinstance(event, PersonalEvent):
                raise ValueError('Invalid agent event')
            event.validate()
        if self.events[-1].terms != self.terms or self.events[-1].by_club_id != self.proposed_by:
            raise ValueError('Latest offer must match the recorded terms')
        for event in self.events:
            event.validate()
            if event.by_club_id not in (self.seller_id, self.buyer_id) or event.on_date < self.started_on:
                raise ValueError('Invalid negotiation event author/date')
        if not isinstance(self.reason,str) or len(self.reason)>240:
            raise ValueError('Invalid negotiation reason')
