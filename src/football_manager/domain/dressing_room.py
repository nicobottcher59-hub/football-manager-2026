"""Bounded, persistent social state; no football rating or UI logic lives here."""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date
from itertools import combinations
from math import isfinite

MAX_MORALE_EFFECT = 2.0
MAX_EVENTS = 40
MAX_APPEARANCES = 12
MAX_FIXTURE_MEMORY = 256
TIERS = ('leaders', 'influential', 'core', 'emerging')
TIER_LABELS = {
    'leaders': 'Team leaders', 'influential': 'Influential players',
    'core': 'Established group', 'emerging': 'Developing influence',
}


def finite_range(name: str, value: float, low: float, high: float) -> None:
    if type(value) not in (int, float) or not isfinite(value) or not low <= value <= high:
        raise ValueError(f'{name} must be finite and within [{low}, {high}]')


def require_day(value: date) -> None:
    if type(value) is not date:
        raise ValueError('calendar date required')


@dataclass(frozen=True, slots=True)
class SocialAppearance:
    fixture_id: str
    day: date
    minutes: int
    eligible: bool

    def validate(self) -> None:
        require_day(self.day)
        if not isinstance(self.fixture_id, str) or not self.fixture_id:
            raise ValueError('appearance requires fixture identity')
        if type(self.minutes) is not int or not 0 <= self.minutes <= 120:
            raise ValueError('invalid played minutes')
        if type(self.eligible) is not bool:
            raise ValueError('invalid availability flag')


@dataclass(slots=True)
class SocialMember:
    player_id: str
    joined_on: date
    integration: float = 65.0
    influence: float = 50.0
    tier: str = 'core'
    tier_since: date | None = None
    previous_influence: float = 50.0
    appearances: list[SocialAppearance] = field(default_factory=list)
    departure_disruption: float = 0.0
    result_response: float = 0.0
    support_player_id: str | None = None
    morale_components: dict[str, float] = field(default_factory=dict)
    last_concern_on: date | None = None

    def validate(self, on_date: date) -> None:
        require_day(self.joined_on)
        require_day(self.tier_since)
        if not self.player_id or self.joined_on > on_date or not self.joined_on <= self.tier_since <= on_date:
            raise ValueError('invalid member identity or dates')
        if self.tier not in TIERS:
            raise ValueError('invalid hierarchy tier')
        for name in ('integration', 'influence', 'previous_influence'):
            finite_range(name, getattr(self, name), 0, 100)
        finite_range('departure disruption', self.departure_disruption, 0, 1)
        finite_range('result response', self.result_response, -.35, .35)
        if not isinstance(self.appearances, list) or len(self.appearances) > MAX_APPEARANCES:
            raise ValueError('invalid participation window')
        seen = set()
        previous = self.joined_on
        for appearance in self.appearances:
            if not isinstance(appearance, SocialAppearance):
                raise ValueError('invalid appearance record')
            appearance.validate()
            if not previous <= appearance.day <= on_date or appearance.fixture_id in seen:
                raise ValueError('invalid appearance chronology')
            previous = appearance.day
            seen.add(appearance.fixture_id)
        if self.last_concern_on is not None:
            require_day(self.last_concern_on)
            if not self.joined_on <= self.last_concern_on <= on_date:
                raise ValueError('invalid concern date')
        allowed = {'integration', 'participation', 'atmosphere', 'departure', 'response'}
        if not isinstance(self.morale_components, dict) or set(self.morale_components) - allowed:
            raise ValueError('unknown morale source')
        for value in self.morale_components.values():
            finite_range('morale component', value, -MAX_MORALE_EFFECT, MAX_MORALE_EFFECT)


@dataclass(slots=True)
class SocialLink:
    player_a: str
    player_b: str
    affinity: float = 50.0
    shared_minutes: int = 0

    def validate(self) -> None:
        if not isinstance(self.player_a, str) or not isinstance(self.player_b, str) or not self.player_a < self.player_b:
            raise ValueError('social endpoints must be distinct, sorted player IDs')
        finite_range('affinity', self.affinity, 0, 100)
        if type(self.shared_minutes) is not int or not 0 <= self.shared_minutes <= 100_000_000:
            raise ValueError('invalid shared playing time')


@dataclass(frozen=True, slots=True)
class SocialEvent:
    sequence: int
    day: date
    kind: str
    player_ids: tuple[str, ...]
    message: str

    def validate(self, on_date: date) -> None:
        require_day(self.day)
        if self.day > on_date or type(self.sequence) is not int or self.sequence < 1:
            raise ValueError('invalid social event chronology')
        if self.kind not in ('arrival', 'departure', 'hierarchy', 'participation', 'integration'):
            raise ValueError('unknown social event')
        if not isinstance(self.player_ids, tuple) or any(not isinstance(p, str) or not p for p in self.player_ids):
            raise ValueError('invalid event identities')
        if not isinstance(self.message, str) or not 1 <= len(self.message) <= 500:
            raise ValueError('invalid event text')


@dataclass(slots=True)
class DressingRoomState:
    club_id: str
    started_on: date
    last_updated: date
    last_review: date
    members: dict[str, SocialMember] = field(default_factory=dict)
    links: dict[tuple[str, str], SocialLink] = field(default_factory=dict)
    events: list[SocialEvent] = field(default_factory=list)
    processed_fixtures: dict[str, date] = field(default_factory=dict)
    atmosphere: float = 65.0
    revision: int = 0
    event_sequence: int = 0

    def validate(self, player_ids: set[str], on_date: date) -> None:
        for value in (on_date, self.started_on, self.last_updated, self.last_review):
            require_day(value)
        if not isinstance(self.club_id, str) or not self.club_id:
            raise ValueError('invalid dressing room club')
        if not self.started_on <= self.last_review <= self.last_updated <= on_date:
            raise ValueError('invalid dressing room clock')
        if (type(self.revision) is not int or self.revision < 0
                or type(self.event_sequence) is not int or self.event_sequence < 0):
            raise ValueError('invalid social revision')
        finite_range('atmosphere', self.atmosphere, 0, 100)
        if not isinstance(self.members, dict) or set(self.members) != player_ids:
            raise ValueError('dressing room membership differs from the registered squad')
        for pid, member in self.members.items():
            if not isinstance(member, SocialMember) or member.player_id != pid:
                raise ValueError('invalid social member')
            member.validate(self.last_updated)
            if member.support_player_id is not None and (member.support_player_id not in player_ids or member.support_player_id == pid):
                raise ValueError('invalid integration support reference')
        pairs = set(combinations(sorted(player_ids), 2))
        if not isinstance(self.links, dict) or set(self.links) != pairs:
            raise ValueError('social graph does not match squad membership')
        for pair, link in self.links.items():
            if not isinstance(link, SocialLink) or pair != (link.player_a, link.player_b):
                raise ValueError('invalid social graph edge')
            link.validate()
        if not isinstance(self.events, list) or len(self.events) > MAX_EVENTS:
            raise ValueError('invalid event history')
        sequence, previous = 0, self.started_on
        for event in self.events:
            if not isinstance(event, SocialEvent):
                raise ValueError('invalid social event')
            event.validate(self.last_updated)
            if not sequence < event.sequence <= self.event_sequence or event.day < previous:
                raise ValueError('unordered social events')
            sequence, previous = event.sequence, event.day
        if not isinstance(self.processed_fixtures, dict) or len(self.processed_fixtures) > MAX_FIXTURE_MEMORY:
            raise ValueError('invalid social fixture ledger')
        for key, value in self.processed_fixtures.items():
            require_day(value)
            if not isinstance(key, str) or not key or not self.started_on <= value <= self.last_updated:
                raise ValueError('invalid social fixture identity/date')
