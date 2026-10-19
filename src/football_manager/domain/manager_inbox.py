"""TS-25: small persistent manager inbox and player-conversation state.

Only verified world events become notices.  The player conversation history
is separate from the autonomous TS-20 dressing-room graph and does not grant
a match-engine ability, chemistry or automatic contract bonus.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date
from math import isfinite

MAX_MESSAGES = 350
MAX_KEYS = 3000
CATEGORIES = frozenset({'medical', 'contracts', 'scouting', 'calendar', 'results',
                        'market', 'dressing_room', 'conversations', 'academy', 'system'})
TOPICS = frozenset({'praise', 'support', 'future', 'minutes', 'role', 'criticism',
                    'development', 'leadership', 'loan', 'transfer', 'recovery'})
PROMISE_KINDS = frozenset({'playing_time', 'starter_role', 'renewal',
                           'youth_opportunity', 'loan_move'})


@dataclass(slots=True)
class InboxMessage:
    message_id: int
    day: date
    category: str
    title: str
    body: str
    source_key: str
    player_id: str | None = None
    read: bool = False
    requires_reply: bool = False
    resolved: bool = False

    def validate(self, today: date) -> None:
        if type(self.message_id) is not int or self.message_id < 1 or type(self.day) is not date or self.day > today:
            raise ValueError('invalid inbox message clock or identifier')
        if self.category not in CATEGORIES or not 1 <= len(self.title) <= 140 or not 1 <= len(self.body) <= 800:
            raise ValueError('invalid inbox content')
        if not isinstance(self.source_key, str) or not 1 <= len(self.source_key) <= 220:
            raise ValueError('invalid inbox source')
        if self.player_id is not None and (not isinstance(self.player_id, str) or not self.player_id):
            raise ValueError('invalid inbox player')
        if any(type(v) is not bool for v in (self.read, self.requires_reply, self.resolved)):
            raise ValueError('invalid inbox status')


@dataclass(slots=True)
class ManagerRelation:
    player_id: str
    trust: float = 50.0
    pressure: float = 0.0
    last_updated: date | None = None
    last_talk: date | None = None
    last_topics: dict[str, date] = field(default_factory=dict)
    conversations: int = 0

    def validate(self, day: date) -> None:
        if not self.player_id or not all(isfinite(v) and 0 <= v <= 100 for v in (self.trust, self.pressure)):
            raise ValueError('invalid manager relationship')
        if type(self.conversations) is not int or self.conversations < 0:
            raise ValueError('invalid conversation count')
        for t in (self.last_talk, self.last_updated, *self.last_topics.values()):
            if t is not None and (type(t) is not date or t > day):
                raise ValueError('conversation dated in the future')
        if set(self.last_topics) - TOPICS:
            raise ValueError('invalid conversation topic')


@dataclass(slots=True)
class ManagerPromise:
    promise_id: int
    player_id: str
    created_on: date
    due_on: date
    kind: str = 'playing_time'
    status: str = 'active'
    assessed_on: date | None = None
    extension_count: int = 0

    def validate(self, day: date) -> None:
        if (type(self.promise_id) is not int or self.promise_id < 1 or not self.player_id
                or type(self.created_on) is not date or type(self.due_on) is not date
                or self.created_on > day or self.created_on >= self.due_on
                or self.kind not in PROMISE_KINDS or self.status not in ('active', 'kept', 'broken', 'void')
                or type(self.extension_count) is not int or not 0 <= self.extension_count <= 1):
            raise ValueError('invalid manager promise')
        if self.assessed_on is not None and (type(self.assessed_on) is not date or self.assessed_on > day):
            raise ValueError('invalid promise outcome date')
        if (self.status == 'active') != (self.assessed_on is None):
            raise ValueError('inconsistent promise status')


@dataclass(slots=True)
class ManagerInbox:
    club_id: str
    started_on: date
    last_synced: date
    messages: list[InboxMessage] = field(default_factory=list)
    sequence: int = 0
    known_sources: set[str] = field(default_factory=set)
    relations: dict[str, ManagerRelation] = field(default_factory=dict)
    promises: list[ManagerPromise] = field(default_factory=list)
    next_promise_id: int = 1
    injuries: dict[str, str] = field(default_factory=dict)
    contracts: dict[str, str] = field(default_factory=dict)
    scouting_candidates: set[str] = field(default_factory=set)
    scout_report_counts: dict[str, int] = field(default_factory=dict)
    fixtures: dict[str, date] = field(default_factory=dict)
    results: set[str] = field(default_factory=set)
    offers: dict[str, str] = field(default_factory=dict)
    social_sequence: int = 0

    def validate(self, day: date, club_id: str) -> None:
        if self.club_id != club_id or type(self.started_on) is not date or type(self.last_synced) is not date:
            raise ValueError('invalid inbox club or date')
        if not self.started_on <= self.last_synced <= day:
            raise ValueError('inbox is ahead of career')
        if type(self.sequence) is not int or self.sequence < 0 or len(self.messages) > MAX_MESSAGES:
            raise ValueError('inbox history exceeds limit')
        ids = [m.message_id for m in self.messages]
        if len(set(ids)) != len(ids) or ids != sorted(ids) or (ids and ids[-1] > self.sequence):
            raise ValueError('non-sequential inbox history')
        for item in self.messages:
            item.validate(day)
        if not isinstance(self.known_sources, set) or len(self.known_sources) > MAX_KEYS:
            raise ValueError('invalid inbox deduplication ledger')
        if any(not isinstance(k, str) or not k or len(k) > 220 for k in self.known_sources):
            raise ValueError('invalid inbox event source')
        if len(self.relations) > 2000 or any(k != r.player_id for k, r in self.relations.items()):
            raise ValueError('invalid manager relations')
        for rel in self.relations.values():
            rel.validate(day)
        if len(self.promises) > 1000 or type(self.next_promise_id) is not int or self.next_promise_id < 1:
            raise ValueError('invalid manager promise history')
        promise_ids = [p.promise_id for p in self.promises]
        if promise_ids != sorted(set(promise_ids)) or (promise_ids and promise_ids[-1] >= self.next_promise_id):
            raise ValueError('invalid promise numbering')
        for p in self.promises:
            p.validate(day)
        if any(type(v) is not date or abs((v-day).days) > 740 for v in self.fixtures.values()):
            raise ValueError('invalid fixture notification clock')
        if type(self.social_sequence) is not int or self.social_sequence < 0:
            raise ValueError('invalid social alert clock')
