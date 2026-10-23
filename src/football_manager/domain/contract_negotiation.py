"""TS-FIX-03: persistent manager/agent contract discussions and earned bonuses."""
from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from .transfer_personal import PersonalTerms, PersonalEvent


@dataclass(frozen=True, slots=True)
class ContractTalk:
    player_id: str
    club_id: str
    started_on: date
    status: str = 'open'  # open, counter, renewed, ended
    patience: int = 100
    rounds: int = 0
    counter: PersonalTerms | None = None
    events: tuple[PersonalEvent, ...] = ()
    reason: str = ''

    def validate(self):
        if (not self.player_id or not self.club_id or type(self.started_on) is not date
                or self.status not in ('open','counter','renewed','ended')
                or type(self.patience) is not int or not 0 <= self.patience <= 100
                or type(self.rounds) is not int or not 0 <= self.rounds <= 32
                or not isinstance(self.events,tuple) or len(self.events)>64
                or type(self.reason) is not str or len(self.reason)>240):
            raise ValueError('Invalid contract negotiation')
        if self.counter is not None:
            self.counter.validate()
        if self.status=='counter' and self.counter is None:
            raise ValueError('Missing agent counteroffer')
        for item in self.events:
            if not isinstance(item,PersonalEvent):
                raise ValueError('Invalid contract conversation')
            item.validate()
        if self.events and self.events[0].on_date < self.started_on:
            raise ValueError('Contract conversation precedes negotiations')


@dataclass(frozen=True, slots=True)
class PlayerBonusLedger:
    """One set of payable incentives tied to one actual employment contract.

    Historical baselines avoid paying for goals scored before the agreement.
    Once a trigger is settled its kind is persisted, avoiding double payment.
    """
    player_id: str
    club_id: str
    signed_on: date
    baseline: tuple[int,int,int]
    starting_tier: int
    bonuses: tuple['ContractBonus', ...]
    paid: tuple[str, ...] = ()

    def validate(self):
        from .transfer_personal import ContractBonus
        if (not self.player_id or not self.club_id or type(self.signed_on) is not date
                or type(self.baseline) is not tuple or len(self.baseline)!=4
                or any(type(x) is not int or x<0 for x in self.baseline)
                or type(self.starting_tier) is not int or self.starting_tier not in range(5)
                or not isinstance(self.bonuses,tuple) or len(self.bonuses)>3
                or not isinstance(self.paid,tuple) or len(set(self.paid))!=len(self.paid)):
            raise ValueError('Invalid player bonus ledger')
        kinds=[]
        for item in self.bonuses:
            if not isinstance(item,ContractBonus):
                raise ValueError('Invalid contract bonus')
            item.validate()
            kinds.append(item.kind)
        if len(set(kinds)) != len(kinds) or any(x not in kinds for x in self.paid):
            raise ValueError('Invalid paid performance triggers')
