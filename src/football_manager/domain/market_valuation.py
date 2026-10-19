"""TS-24.1: symmetric GBP footballer valuation; no buying/selling side bias.

Market estimates are *not* exact PA, contract claims or accepted offers.
Inputs are authoritative OVR, age, stable noisy upside beliefs, smoothed form
and recorded injuries. Quotes are refreshed on the world monthly clock.
This policy does not change OVR, ACT, CA, PA, morale or game simulation.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from hashlib import sha256
from math import exp, isfinite, log

ANCHORS_GBP: tuple[tuple[float, int], ...] = (
    (35, 10_000), (40, 20_000), (45, 60_000), (50, 130_000),
    (55, 300_000), (60, 700_000), (65, 1_600_000),
    (70, 4_000_000), (75, 9_000_000), (78, 16_000_000),
    (80, 24_000_000), (82, 34_000_000), (85, 55_000_000),
    (88, 89_000_000), (90, 120_000_000), (93, 175_000_000),
    (95, 230_000_000), (98, 350_000_000),
)
# A 26-28 year old with ordinary remaining potential is the baseline.
# Outfield decline is faster; GK longevity is handled separately.
AGE_BASE: tuple[tuple[int, float], ...] = (
    (15, .94), (16, .98), (17, 1.01), (18, 1.02),
    (19, 1.03), (20, 1.11), (21, 1.15), (22, 1.15),
    (23, 1.10), (24, 1.08), (25, 1.04), (26, 1.02),
    (27, 1.0), (28, 1.0), (29, .87), (30, .82),
    (31, .72), (32, .60), (33, .42), (34, .25),
    (35, .22), (36, .11), (37, .075), (38, .047),
    (40, .025), (46, .01),
)
UPSIDES: tuple[tuple[int, float], ...] = (
    (15, 1.65), (16, 1.52), (17, 1.32), (18, 1.13), (19, 1.0),
    (20, .90), (21, .85), (22, .65), (23, .50), (24, .38),
    (25, .27), (26, .15), (27, 0.0), (28, 0.0),
)
POLICY_VERSION = 1
MAX_MARKET_VALUE_GBP = 500_000_000
# Modest positional-demand stand-ins until a buyer-specific demand model exists.
POSITION_FACTORS = {
    'GK': 1.0, 'LB': .97, 'RB': .97, 'LWB': .98, 'RWB': .98,
    'CB': 1.0, 'LCB': 1.0, 'RCB': 1.0,
    'DM': .98, 'CM': 1.0, 'LCM': 1.0, 'RCM': 1.0,
    'AM': 1.02, 'LW': 1.03, 'RW': 1.03, 'SS': 1.04, 'ST': 1.06,
}


def _interp(x: float, knots: tuple[tuple[float, float], ...]) -> float:
    if x <= knots[0][0]:
        return knots[0][1]
    for (left, a), (right, b) in zip(knots, knots[1:]):
        if x <= right:
            return a + (b-a) * (x-left)/(right-left)
    return knots[-1][1]


def base_market_value(ovr: float) -> float:
    """Exponentially interpolated; anchored examples have no step cliffs."""
    if not isfinite(ovr) or not 0 <= ovr <= 100:
        raise ValueError('OVR must be finite between 0 and 100')
    data = tuple((score, log(gbp)) for score, gbp in ANCHORS_GBP)
    return exp(_interp(ovr, data))


def perceived_upside(seed: int, player_id: str, actual_headroom: float) -> float:
    """Inexact, persistent market belief; cannot reveal the true PA value.

    This belongs to the valuation engine, not the player's scouting UI. Noise
    is seeded from stable ID and world, never by random state or a GET request.
    """
    if not isfinite(actual_headroom):
        raise ValueError('invalid future ability headroom')
    if not player_id:
        raise ValueError('player identity required')
    digest = sha256(f'ts24-market-belief-v1:{seed}:{player_id}'.encode()).digest()
    # Two components provide sub-Gaussian, bounded noise rather than a direct
    # 'PA minus CA' mapping. Neither value nor headroom is sent in JSON.
    noise = ((digest[0]/255 + digest[1]/255) - 1.0) * 4.6
    return max(0., min(34., .94*max(0., actual_headroom) + noise))


def medical_adjustment(*, burden: float = 0.0, serious_injuries: int = 0) -> float:
    """A few minor knocks cost nothing; repeated long absences matter."""
    if not isfinite(burden) or burden < 0 or serious_injuries < 0:
        raise ValueError('invalid injury record')
    return 1 - min(.32, max(0., burden*.13) + serious_injuries*.038)


def form_adjustment(form: float) -> float:
    """Steady *footballing form* only; fitness/fatigue are ignored."""
    if not isfinite(form) or not 0 <= form <= 100:
        raise ValueError('form must be 0-100')
    return max(.88, min(1.12, 1 + (form - 65.)*.12/35))


def _round_market(value: float) -> int:
    # Present money in credible retail increments; keeps quotes readable.
    if value < 100_000:
        step = 5_000
    elif value < 1_000_000:
        step = 10_000
    elif value < 10_000_000:
        step = 100_000
    elif value < 50_000_000:
        step = 500_000
    else:
        step = 1_000_000
    return max(5_000, int((value + step/2)//step * step))


def valuation_amount(*, ovr: float, age: int, perceived_growth: float = 0.0,
                     form: float = 65., medical_factor: float = 1.,
                     goalkeeper: bool = False, position_market_factor: float = 1.0) -> int:
    """Pure valuation function, separate from contract bargaining.

    Age/potential premium is individual and continuous, not a binary 'youth' flag.
    90+ and especially 95+ remain scarce and nonlinearly expensive. Dynamic
    form is bounded to +/-12%, even if state.form is extreme.
    """
    if type(age) is not int or not 14 <= age <= 65:
        raise ValueError('invalid footballer age')
    if (not isfinite(perceived_growth) or perceived_growth < 0 or not isfinite(medical_factor)
            or not .65 <= medical_factor <= 1 or not isfinite(position_market_factor)
            or not .90 <= position_market_factor <= 1.10):
        raise ValueError('invalid market factors')
    age_factor = _interp(age, AGE_BASE)
    if goalkeeper and age >= 31:
        # GK can keep their level/market longer than outfielders.
        longevity = _interp(age, ((31, 1.), (32, 1.12), (34, 1.55), (35, 1.85), (38, 2.0), (46, 1.3)))
        age_factor *= longevity
    # Very good young players with little remaining headroom are *not*
    # automatically priced like players forecast to dominate world football.
    upside_factor = _interp(age, UPSIDES)
    growth = min(34.0, perceived_growth)
    premium = 1 + upside_factor*(.105*growth + .004*growth*growth)
    return min(MAX_MARKET_VALUE_GBP, _round_market(base_market_value(ovr) * age_factor * premium
                         * form_adjustment(form) * medical_factor * position_market_factor))


@dataclass(frozen=True, slots=True)
class MarketQuote:
    player_id: str
    value_gbp: int
    as_of: date
    policy_version: int = POLICY_VERSION

    def validate(self) -> None:
        if not self.player_id or type(self.value_gbp) is not int or not 5_000 <= self.value_gbp <= MAX_MARKET_VALUE_GBP:
            raise ValueError('invalid market quote')
        if type(self.as_of) is not date or self.as_of.day != 1 or self.policy_version != POLICY_VERSION:
            raise ValueError('invalid market date or policy')


@dataclass(frozen=True, slots=True)
class SaleContext:
    """Actual commercial facts supplied by transfer/contract engine once built.

    None contract months means UNKNOWN: this engine never pretends a contract
    exists. Both manager and AI use the same function and the same inputs.
    """
    contract_months: int | None = None
    importance: str = 'regular'
    urgency: str = 'normal'
    transfer_listed: bool = False
    player_wants_exit: bool = False
    direct_rival: bool = False
    other_bidders: int = 0
    replacement_ready: bool = False

    def validate(self) -> None:
        if self.contract_months is not None and (type(self.contract_months) is not int or not 0 <= self.contract_months <= 120):
            raise ValueError('invalid contract months')
        if self.importance not in ('rotation','regular','key','indispensable'):
            raise ValueError('invalid player importance')
        if self.urgency not in ('normal','urgent') or type(self.other_bidders) is not int or not 0 <= self.other_bidders <= 20:
            raise ValueError('invalid seller market context')
        if any(type(getattr(self, name)) is not bool for name in
               ('transfer_listed','player_wants_exit','direct_rival','replacement_ready')):
            raise ValueError('invalid sale flags')


@dataclass(frozen=True, slots=True)
class AskingBand:
    market_value_gbp: int
    low_gbp: int
    high_gbp: int
    contract_data_available: bool
    # It is a computed scenario, not a hidden minimum or an executed offer.
    scenario_only: bool = True


def asking_band(quote: MarketQuote, context: SaleContext) -> AskingBand:
    """Symmetric bargaining reference; not an automatic AI acceptance rule."""
    quote.validate(); context.validate()
    market = quote.value_gbp
    months = context.contract_months
    # Expiring deals are cheap, long contracts make replacement leverage strong.
    contract_market = (1.0 if months is None else _interp(months, (
        (0, 0.0), (6, .70), (12, .86), (24, .97), (36, 1.0), (60, 1.07), (120, 1.10))))
    market = _round_market(max(5_000, market*contract_market)) if months != 0 else 0
    if months == 0:
        return AskingBand(0, 0, 0, True)
    level = {'rotation': .91, 'regular': 1.0, 'key': 1.22, 'indispensable': 1.43}[context.importance]
    leverage = (1.0 + min(.27, .065*context.other_bidders))
    if context.direct_rival:
        leverage *= 1.32
    if context.player_wants_exit:
        leverage *= .86
    if context.transfer_listed:
        leverage *= .82
    if context.urgency == 'urgent':
        leverage *= .80
    if context.replacement_ready:
        leverage *= .94
    low = max(.50, min(3.0, 1.10*level*leverage))
    high = max(low + .07, min(3.4, 1.38*level*leverage))
    return AskingBand(market, _round_market(market*low), _round_market(market*high), months is not None)


def market_value_for_player(player, on_date: date, seed: int) -> MarketQuote:
    """Read only: player skill, potential, fitness and medical state never mutate."""
    from .player_development import current_ability
    age = player.age_on(on_date)
    ability_gap = (player.development.potential - current_ability(player)) if player.development else 0.0
    perceived = perceived_upside(seed, player.id, ability_gap)
    aging = player.aging
    burden = aging.injury_burden if aging else 0.0
    episodes = aging.medical_history if aging else ()
    recent_long = sum(1 for episode in episodes
                      if episode.return_on and episode.return_on <= on_date
                      and (on_date - episode.return_on).days <= 3*365
                      and (episode.return_on - episode.started_on).days >= 60)
    value = valuation_amount(ovr=player.overall_rating, age=age,
                             perceived_growth=perceived, form=player.state.form,
                             medical_factor=medical_adjustment(burden=burden, serious_injuries=recent_long),
                             goalkeeper=player.primary_position.value=='GK',
                             position_market_factor=POSITION_FACTORS[player.primary_position.value])
    return MarketQuote(player.id, value, on_date.replace(day=1))
