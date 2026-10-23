"""TS-21.1: persistent footballers and club identities, independent of a data pack.

The registry is saved by the complete manager-career codec, not the historical
results-only JSON exporter. Club membership is explicit: never infer a player's
current club from their ID. Ageing and development formulas live in shared modules.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date
from math import isfinite

from .club import Club
from .tactics import Tactic
from .personality import Personality
from .enums import Position
from .season_statistics import SeasonStatisticsLedger
from .player_development import DevelopmentEnvironment
from .player_aging import RetiredPlayer
from .youth_academy import YouthSystem
from .market_valuation import MarketQuote
from .club_economy import ClubFinances, PlayerContract
from .contract_negotiation import ContractTalk, PlayerBonusLedger
from .transfer_negotiation import TransferNegotiation
from .loan_market import LoanAgreement, FreeAgent
from .club_support import ClubSupport
from .career_recognition import RatingSnapshot, IndividualAward


@dataclass(slots=True)
class ClubFootballIdentity:
    club_id: str
    initial_tier: int
    tier: int
    style_key: str
    primary: Tactic
    alternative: Tactic
    source: str = "fictional-england-v1"

    def validate(self) -> None:
        if self.tier not in (0, 1, 2, 3, 4) or self.initial_tier not in (1, 2, 3, 4):
            raise ValueError("invalid professional English tier")
        if not self.club_id or not self.style_key or not self.source:
            raise ValueError("incomplete club football identity")
        for tactic in (self.primary, self.alternative):
            tactic.__post_init__()


@dataclass(frozen=True, slots=True)
class PlayerSeasonUsage:
    appearances: int = 0
    starts: int = 0
    minutes: int = 0
    goals: int = 0
    assists: int = 0
    rating_total: float = 0.0

    def __post_init__(self) -> None:
        counts = (self.appearances, self.starts, self.minutes, self.goals, self.assists)
        if any(type(n) is not int or n < 0 for n in counts):
            raise ValueError("invalid player season counts")
        if self.starts > self.appearances or self.minutes > 120 * self.appearances:
            raise ValueError("inconsistent player season participation")
        if not isfinite(self.rating_total) or not 0 <= self.rating_total <= 10 * self.appearances:
            raise ValueError("invalid player season ratings")


@dataclass(slots=True)
class FootballWorld:
    seed: int
    created_on: date
    season_label: str
    clubs: dict[str, Club] = field(default_factory=dict)
    identities: dict[str, ClubFootballIdentity] = field(default_factory=dict)
    last_recovery: dict[str, date] = field(default_factory=dict)
    # One small summary per player/season, not a second copy of match events.
    usage: dict[str, PlayerSeasonUsage] = field(default_factory=dict)
    history: dict[str, dict[str, PlayerSeasonUsage]] = field(default_factory=dict)
    # TS-28.2: only match-verified player-to-club links; no retroactive guessing.
    player_season_clubs: dict[str, dict[str, tuple[str, ...]]] = field(default_factory=dict)
    # Trophies awarded to actual registered players at the confirmed season boundary.
    player_honours: dict[str, tuple[tuple[str, str, str], ...]] = field(default_factory=dict)
    # TS-28.3: actual-season OVR/indicator snapshots and immutable individual prizes.
    rating_history: dict[str, tuple[RatingSnapshot, ...]] = field(default_factory=dict)
    individual_awards: dict[str, tuple[IndividualAward, ...]] = field(default_factory=dict)
    processed_fixtures: dict[str, bool] = field(default_factory=dict)
    tracked_from: date | None = None
    generator_version: int = 1
    statistics: SeasonStatisticsLedger = field(default_factory=SeasonStatisticsLedger)
    balance_adjustments: dict[str, dict] = field(default_factory=dict)

    development_next_review: date | None = None
    development_environments: dict[str, DevelopmentEnvironment] = field(default_factory=dict)

    retired_players: dict[str, RetiredPlayer] = field(default_factory=dict)
    medical_followups: dict[str, tuple[str, date]] = field(default_factory=dict)
    youth: YouthSystem | None = None
    # Price snapshots update at monthly boundaries, not on matches/GET requests.
    market_review_on: date | None = None
    market_values: dict[str, MarketQuote] = field(default_factory=dict)
    # TS-24.2, money and agreements belong to stable IDs rather than Player.
    finance_review_on: date | None = None
    finance_started_on: date | None = None
    contracts: dict[str, PlayerContract] = field(default_factory=dict)
    club_finances: dict[str, ClubFinances] = field(default_factory=dict)
    contract_talks: dict[str, ContractTalk] = field(default_factory=dict)
    contract_bonuses: dict[str, PlayerBonusLedger] = field(default_factory=dict)
    # TS-24.3/24.4 club negotiations and consented settlements.
    transfer_last_review_on: date | None = None
    transfer_interest_review_on: date | None = None
    transfer_next_id: int = 1
    transfer_offers: dict[str, TransferNegotiation] = field(default_factory=dict)
    # TS-24.6; registrations on loan differ from contractual ownership.
    loan_next_id: int = 1
    loans: dict[str, LoanAgreement] = field(default_factory=dict)
    free_agents: dict[str, FreeAgent] = field(default_factory=dict)
    # TS-26: small club staff, group training, and dated medical choices.
    club_support: dict[str, ClubSupport] = field(default_factory=dict)

    def validate(self, participants: dict[str, int] | None = None) -> None:
        if self.transfer_interest_review_on is not None and type(self.transfer_interest_review_on) is not date:
            raise ValueError('Invalid transfer interest clock')
        if self.club_support:
            if set(self.club_support) != set(self.clubs):
                raise ValueError('club support registry must cover all clubs')
            for cid, support in self.club_support.items():
                if support.club_id != cid:
                    raise ValueError('staff belongs to a different club')
                support.validate()
        if type(self.seed) is not int or self.generator_version != 1:
            raise ValueError("unsupported football world")
        if not isinstance(self.created_on, date) or not self.season_label:
            raise ValueError("invalid football world date")
        if self.tracked_from is not None and not isinstance(self.tracked_from, date):
            raise ValueError("invalid tracking start date")
        if set(self.clubs) != set(self.identities) or set(self.clubs) != set(self.last_recovery):
            raise ValueError("football world club registry mismatch")
        if participants is not None and {cid for cid, i in self.identities.items() if i.tier != 0} != set(participants):
            raise ValueError("football world does not cover the four English divisions")
        if self.youth is not None:
            if not isinstance(self.youth, YouthSystem) or self.youth.season_label != self.season_label:
                raise ValueError("youth system belongs to wrong world season")
            if not set(self.clubs).issubset(self.youth.academies):
                raise ValueError("youth academy missing for registered club")
            self.youth.check_unique(self)
        if self.market_review_on is not None:
            if type(self.market_review_on) is not date or self.market_review_on.day != 1:
                raise ValueError('invalid market review clock')
            for pid, quote in self.market_values.items():
                if not isinstance(quote, MarketQuote) or pid != quote.player_id or quote.as_of > self.market_review_on:
                    raise ValueError('invalid saved market price')
                quote.validate()
        elif self.market_values:
            raise ValueError('market values without market review clock')
        if self.finance_review_on is not None:
            if (type(self.finance_review_on) is not date or self.finance_review_on.day != 1
                    or type(self.finance_started_on) is not date
                    or self.finance_started_on.replace(day=1)>self.finance_review_on):
                raise ValueError('invalid finance review timeline')
            if set(self.club_finances) != set(self.clubs):
                raise ValueError('incomplete club finance register')
            active_owners = {p.id:cid for cid,club in self.clubs.items() for p in club.squad.players}
            if self.youth is not None:
                for cid,academy in self.youth.academies.items():
                    for pid in (*academy.u17,*academy.u21):
                        active_owners[pid]=cid
            active_loans = {loan.player_id:loan for loan in self.loans.values() if loan.status=='active'}
            if set(self.contracts) != set(active_owners):
                raise ValueError('contracts do not match active professional and youth players')
            for pid, contract in self.contracts.items():
                if not isinstance(contract, PlayerContract) or contract.player_id != pid or contract.club_id != (active_loans[pid].parent_id if pid in active_loans else active_owners[pid]):
                    raise ValueError('invalid contract identity')
                contract.validate()
            for cid, account in self.club_finances.items():
                if not isinstance(account, ClubFinances) or account.club_id != cid:
                    raise ValueError('invalid club finance identity')
                account.validate()
        elif self.contracts or self.club_finances or self.finance_started_on is not None:
            raise ValueError('partial economic ledger')
        for pid, talk in self.contract_talks.items():
            if not isinstance(talk, ContractTalk) or talk.player_id != pid or talk.club_id not in self.clubs:
                raise ValueError('Invalid manager contract negotiation identity')
            talk.validate()
        for pid, incentives in self.contract_bonuses.items():
            if (not isinstance(incentives, PlayerBonusLedger) or incentives.player_id != pid
                    or incentives.club_id not in self.clubs):
                raise ValueError('Invalid player incentive identity')
            incentives.validate()
        if self.transfer_last_review_on is not None:
            if type(self.transfer_last_review_on) is not date or self.transfer_last_review_on.day != 1:
                raise ValueError('invalid transfer review clock')
            if type(self.transfer_next_id) is not int or self.transfer_next_id < 1:
                raise ValueError('invalid transfer sequence')
            for key, offer in self.transfer_offers.items():
                if (not isinstance(offer, TransferNegotiation) or key != offer.deal_id
                        or offer.seller_id not in self.clubs or offer.buyer_id not in self.clubs):
                    raise ValueError('invalid transfer negotiation identity')
                offer.validate()
        elif self.transfer_offers or self.transfer_next_id != 1:
            raise ValueError('uninitialized transfer market')
        if type(self.loan_next_id) is not int or self.loan_next_id < 1:
            raise ValueError('Invalid loan sequence')
        loaned=set()
        for key,loan in self.loans.items():
            if (key != loan.loan_id or not isinstance(loan, LoanAgreement)
                    or loan.parent_id not in self.clubs or loan.borrower_id not in self.clubs):
                raise ValueError('Invalid registered loan')
            loan.validate()
            if loan.status=='active':
                if loan.player_id in loaned or not self.clubs[loan.borrower_id].squad.contains(loan.player_id):
                    raise ValueError('Active loan has no unique borrower registration')
                loaned.add(loan.player_id)
                if self.clubs[loan.parent_id].squad.contains(loan.player_id):
                    raise ValueError('Loan player also registered by parent')
        for pid,free in self.free_agents.items():
            if not isinstance(free,FreeAgent) or free.player.id != pid or free.previous_club_id not in self.clubs:
                raise ValueError('Invalid free-agent registry')
            free.validate()
            if pid in self.contracts or any(club.squad.contains(pid) for club in self.clubs.values()):
                raise ValueError('Free agent still registered or contracted')
        if not isinstance(self.player_season_clubs, dict) or not isinstance(self.player_honours, dict):
            raise ValueError('invalid career history ledgers')
        for season, players in self.player_season_clubs.items():
            if not isinstance(season, str) or not isinstance(players, dict):
                raise ValueError('invalid historical season')
            for pid, clubs in players.items():
                if not isinstance(pid, str) or not isinstance(clubs, tuple) or any(cid not in self.clubs for cid in clubs):
                    raise ValueError('invalid historical player-club link')
        for pid, awards in self.player_honours.items():
            if not isinstance(pid, str) or not isinstance(awards, tuple) or any(
                not isinstance(item, tuple) or len(item) != 3 or item[2] not in self.clubs
                for item in awards):
                raise ValueError('invalid historical player honour')
        if not isinstance(self.rating_history, dict) or not isinstance(self.individual_awards, dict):
            raise ValueError('invalid career recognition ledgers')
        for pid, snapshots in self.rating_history.items():
            if not isinstance(pid, str) or not isinstance(snapshots, tuple) or len(snapshots) > 80:
                raise ValueError('invalid player rating history')
            for i, item in enumerate(snapshots):
                if not isinstance(item, RatingSnapshot):
                    raise ValueError('invalid player rating snapshot')
                item.validate()
                if i and item.on_date <= snapshots[i-1].on_date:
                    raise ValueError('rating history must be chronological')
        for season, awards in self.individual_awards.items():
            if not isinstance(season, str) or not isinstance(awards, tuple) or len(awards) > 220:
                raise ValueError('invalid season awards')
            seen = set()
            for award in awards:
                if not isinstance(award, IndividualAward) or award.season != season:
                    raise ValueError('invalid award certificate')
                award.validate()
                key = (award.competition_id, award.category)
                if key in seen or award.club_id is not None and award.club_id not in self.clubs:
                    raise ValueError('duplicate/invalid award certificate')
                seen.add(key)
        if not isinstance(self.statistics, SeasonStatisticsLedger):
            raise ValueError("invalid statistics ledger")
        self.statistics.validate()
        if not isinstance(self.balance_adjustments, dict):
            raise ValueError("invalid balance adjustment ledger")
        if self.development_next_review is not None:
            if type(self.development_next_review) is not date or self.development_next_review.day != 1:
                raise ValueError("invalid global development clock")
            if set(self.development_environments) != set(self.clubs):
                raise ValueError("development environment registry mismatch")
            for environment in self.development_environments.values():
                if not isinstance(environment, DevelopmentEnvironment):
                    raise ValueError("invalid development environment")
                environment.validate()
        all_ids: set[str] = set()
        if not isinstance(self.retired_players, dict) or not isinstance(self.medical_followups, dict):
            raise ValueError("invalid ageing registries")
        for pid, entry in self.retired_players.items():
            if not isinstance(entry, RetiredPlayer) or entry.player.id != pid or entry.club_id not in self.clubs:
                raise ValueError("invalid retired player archive")
            entry.validate()
            all_ids.add(pid)
        for club_id, club in self.clubs.items():
            identity = self.identities[club_id]
            identity.validate()
            if club.id != club_id or identity.club_id != club_id:
                raise ValueError("club identity mismatch")
            if participants is not None and identity.tier != participants.get(club_id, 0):
                raise ValueError("club division differs from competition registration")
            if not isinstance(self.last_recovery[club_id], date):
                raise ValueError("invalid club recovery clock")
            if len(club.squad) < 11:
                raise ValueError("incomplete club squad")
            for key, player in club.squad._players.items():
                if key != player.id or key in all_ids:
                    raise ValueError("duplicate or noncanonical world player ID")
                all_ids.add(key)
                player.identity.__post_init__()
                if not isinstance(player.personality, Personality):
                    raise ValueError("missing world player personality")
                player.personality.validate()
                if self.development_next_review is not None:
                    if player.development is None:
                        raise ValueError("missing persistent player development")
                    player.development.validate(player)
                    if player.aging is None or player.aging.retired_on is not None:
                        raise ValueError("missing or retired active player ageing profile")
                    player.aging.validate(player)
                    if player.aging.last_review >= self.development_next_review:
                        raise ValueError("ageing is ahead of the global clock")
                    if player.development.last_review >= self.development_next_review:
                        raise ValueError("player development is ahead of the global clock")
                if not isinstance(player.primary_position, Position) or not isinstance(player.original_position, Position):
                    raise ValueError("invalid world player position")
                player.state._validate()
                if player.identity.birth_date > self.last_recovery[club_id]:
                    raise ValueError("player was born after club registration")
                for group in (player.attributes.technical, player.attributes.mental,
                              player.attributes.physical, player.attributes.goalkeeping):
                    if group is not None:
                        group.__post_init__()
                # Check saved familiarity values without rewriting them.
                for values in (player.positional_familiarity.values,
                               player.positional_familiarity.peak_values,
                               player.tactical_familiarity.role_values,
                               player.tactical_familiarity.tactic_values):
                    if any(not isfinite(float(v)) or not 0 <= v <= 100 for v in values.values()):
                        raise ValueError("invalid world player familiarity")
                for values in (player.positional_familiarity.played_minutes,
                               player.positional_familiarity.unused_minutes):
                    if any(not isfinite(float(v)) or v < 0 for v in values.values()):
                        raise ValueError("invalid world player position minutes")
        if any(pid in all_ids for pid in self.free_agents):
            raise ValueError('Unsigned player duplicates a registered or retired player')
        all_ids.update(self.free_agents)
        expected_medical = {p.id: (cid, p.aging.active_injury.return_on)
                            for cid, c in self.clubs.items() for p in c.squad.players
                            if p.aging is not None and p.aging.active_injury is not None
                            and p.aging.active_injury.return_on is not None}
        if self.medical_followups != expected_medical:
            raise ValueError("medical follow-up index differs from active injuries")
        if not set(self.usage).issubset(all_ids):
            raise ValueError("unknown player in season usage")
        for summary in self.usage.values():
            summary.__post_init__()
        for summaries in self.history.values():
            for summary in summaries.values():
                summary.__post_init__()
        if any(not isinstance(k, str) or not k or v is not True
               for k, v in self.processed_fixtures.items()):
            raise ValueError("invalid football participation ledger")

    def adopt_season(self, season_label: str, participants: dict[str, int]) -> None:
        if not set(participants).issubset(self.clubs):
            raise ValueError("professional club universe changed; explicit import required")
        if season_label != self.season_label:
            # No regeneration, no promotion bonus and no loss of career history.
            self.history[self.season_label] = dict(self.usage)
            self.usage = {}
            self.processed_fixtures = {}
            self.season_label = season_label
        for club_id in self.clubs:
            # Keep relegated-out clubs and their footballers, without inventing
            # a National League calendar. Tier 0 means outside the active scope.
            self.identities[club_id].tier = participants.get(club_id, 0)
