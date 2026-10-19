"""Seeded fictional data pack for the existing English professional clubs.

Generation is a one-time bootstrap, never a matchday or promotion operation.
The Player/Club/Tactic domain objects are equally suitable for future imports.
All quality calibration evaluates the existing contextual OVR function.
"""
from __future__ import annotations

from dataclasses import fields
from datetime import date
from hashlib import sha256
from random import Random
from statistics import NormalDist

from football_manager.domain.attributes import (
    PlayerAttributes, TechnicalAttributes, MentalAttributes, PhysicalAttributes,
    GoalkeepingAttributes,
)
from football_manager.domain.club import Club
from football_manager.domain.enums import Foot, Position
from football_manager.domain.football_world import ClubFootballIdentity
from football_manager.domain.player import Player, PlayerIdentity
from football_manager.domain.player_state import PlayerState
from football_manager.domain.positional_familiarity import PositionalFamiliarity
from football_manager.domain.roles import get_role, roles_for_position, role_similarity
from football_manager.domain.squad import Squad
from football_manager.domain.tactical_catalogue import development_formations
from football_manager.domain.tactical_familiarity import TacticalFamiliarity
from football_manager.domain.tactical_instructions import Level
from football_manager.domain.tactical_presets import TacticalPreset
from football_manager.domain.tactics import Tactic

CB = frozenset((Position.RCB, Position.CB, Position.LCB))
CM = frozenset((Position.RCM, Position.CM, Position.LCM))
FB = frozenset((Position.RB, Position.LB))
WB = frozenset((Position.RWB, Position.LWB))
WIDE = frozenset((Position.RW, Position.LW))

STYLE_FORMATIONS = {
    'balanced': ('4-3-3', '4-4-2', '4-2-3-1', '3-5-2', '4-4-2-diamond'),
    'possession': ('4-3-3', '4-2-3-1', '3-4-2-1', '4-3-2-1', '4-2-3-1-narrow'),
    'tiki_taka': ('4-3-3', '4-2-3-1', '4-4-2-diamond', '4-3-1-2', '3-4-1-2'),
    'constant_press': ('4-3-3', '4-4-2', '4-2-3-1', '3-4-3', '4-2-4'),
    'counterpress': ('4-3-3', '4-2-3-1', '3-4-2-1', '4-3-3-double-dm'),
    'counter_attack': ('4-4-2', '4-1-4-1', '4-2-3-1', '5-3-2', '3-5-2'),
    'direct_counter': ('4-4-2', '5-3-2', '4-4-1-1', '5-3-1-1', '3-1-4-2'),
    'catenaccio': ('5-3-2', '5-4-1', '5-2-1-2', '4-4-2-double-dm'),
    'low_block': ('5-4-1', '4-5-1', '4-1-4-1', '5-2-3', '5-2-2-1'),
    'direct_play': ('4-4-2', '3-5-2', '4-4-2', '4-1-3-2', '3-4-1-2-dm'),
    'wide_attack': ('4-3-3', '4-4-2', '3-4-3', '4-5-1-am-duo', '4-2-4'),
}
ALTERNATIVES = {
    '4-3-3': '4-1-4-1', '4-1-4-1': '4-3-3',
    '4-4-2': '4-4-1-1', '4-4-1-1': '4-4-2',
    '3-5-2': '5-3-2', '5-3-2': '3-5-2',
    '3-4-3': '5-2-3', '5-2-3': '3-4-3',
    '3-4-2-1': '5-2-2-1', '5-2-2-1': '3-4-2-1',
    '4-4-2-diamond': '4-3-1-2', '4-3-1-2': '4-4-2-diamond',
    '3-4-1-2': '5-2-1-2', '5-2-1-2': '3-4-1-2',
    '4-2-3-1': '4-3-3-double-dm', '4-3-3-double-dm': '4-2-3-1',
    '5-4-1': '5-2-3', '4-5-1': '4-1-4-1',
    '4-4-2-double-dm': '4-4-2', '4-2-4': '4-4-2',
    '3-1-4-2': '3-5-2', '3-4-1-2-dm': '3-4-1-2',
    '5-3-1-1': '3-5-2', '4-1-3-2': '4-4-2',
    '4-2-3-1-narrow': '4-3-2-1', '4-3-2-1': '4-2-3-1-narrow',
    '4-5-1-am-duo': '4-2-3-1', '4-2-2-2': '4-4-2-diamond',
}

FIRST_NAMES = (
    'Oliver', 'Harry', 'George', 'Noah', 'Arthur', 'Jack', 'Leo', 'Oscar',
    'Charlie', 'Theo', 'Freddie', 'Alfie', 'Archie', 'Henry', 'Thomas', 'Joshua',
    'James', 'William', 'Ethan', 'Isaac', 'Alexander', 'Joseph', 'Edward', 'Adam',
    'Samuel', 'Daniel', 'Lucas', 'Benjamin', 'Mason', 'Harrison', 'Jacob', 'Luke',
    'Nathan', 'Lewis', 'Connor', 'Liam', 'Callum', 'Ryan', 'Owen', 'Dylan',
    'Tyler', 'Reece', 'Ellis', 'Max', 'Jude', 'Toby', 'Sebastian', 'Aaron',
    'Finley', 'Reuben', 'Leon', 'Jayden', 'Cameron', 'Joel', 'Zachary', 'Harvey',
    'Elliot', 'Evan', 'Rory', 'Declan', 'Scott', 'Alex', 'Blake', 'Dominic',
)
LAST_NAMES = (
    'Ashworth', 'Barlow', 'Beckett', 'Bentley', 'Bradshaw', 'Brennan', 'Brock',
    'Calder', 'Cartwright', 'Chadwick', 'Clarke', 'Collins', 'Dalton', 'Davies',
    'Dawson', 'Dempsey', 'Doyle', 'Dunbar', 'Easton', 'Ellison', 'Farrell',
    'Fletcher', 'Forster', 'Galloway', 'Gibson', 'Goodwin', 'Grant', 'Greenwood',
    'Hadley', 'Hammond', 'Hardwick', 'Hawthorne', 'Henderson', 'Hewitt', 'Holland',
    'Holt', 'Hudson', 'Ingram', 'Jarvis', 'Keating', 'Kendall', 'Kirkwood',
    'Langley', 'Lawson', 'Lennox', 'Lockwood', 'Maddox', 'Marsden', 'Mercer',
    'Millward', 'Monroe', 'Nolan', 'Oakley', 'Osborne', 'Palmer', 'Pearson',
    'Penrose', 'Quinn', 'Radcliffe', 'Ramsey', 'Redmond', 'Rowland', 'Sawyer',
    'Sheppard', 'Sinclair', 'Spencer', 'Stafford', 'Sullivan', 'Tanner', 'Thorpe',
    'Townsend', 'Travers', 'Turner', 'Vaughan', 'Walsh', 'Warren', 'Webster',
    'Weston', 'Whitaker', 'Whitfield', 'Wilmot', 'Woodward', 'Wren', 'Yardley',
)


def stable_seed(*parts: object) -> int:
    return int.from_bytes(sha256(':'.join(map(str, parts)).encode('utf-8')).digest()[:8], 'big')


def target_quality(tier: int, rank: int, count: int) -> float:
    """Normal-like within-tier distribution with deliberately overlapping tails."""
    if tier not in (1, 2, 3, 4) or not 0 <= rank < count:
        raise ValueError('invalid quality stratum')
    middle = {1: 79.5, 2: 69.5, 3: 59.5, 4: 49.5}[tier]
    z = NormalDist().inv_cdf((rank + .5) / count)
    return round(max(middle - 6.5, min(middle + 6.5, middle + 3.6 * z)), 2)


def formation_by_id(formation_id: str):
    for form in development_formations():
        if form.formation_id == formation_id:
            return form
    raise ValueError(f'unknown formation: {formation_id}')


def _roles(tactic: Tactic, style: str, variant: int) -> None:
    """Complementary jobs; the same formation may execute different football."""
    possession = style in ('possession', 'tiki_taka')
    press = style in ('constant_press', 'counterpress')
    direct = style in ('direct_play', 'direct_counter')
    deep = style in ('low_block', 'catenaccio', 'counter_attack', 'direct_counter')
    count = {}
    for slot in tactic.formation.slots:
        p = slot.position
        group = 'cb' if p in CB else 'cm' if p in CM else p.value
        n = count.get(group, 0); count[group] = n + 1
        if p is Position.GK:
            role = ('distributor_keeper' if possession else 'sweeper_keeper' if press
                    else 'shot_stopper' if deep else 'goalkeeper')
        elif p in CB:
            role = ('ball_playing_defender' if possession and n != 1
                    else 'covering_defender' if (press or p is Position.CB) and n == 1
                    else 'stopper' if direct and n == 0
                    else 'central_defender')
        elif p in FB:
            role = ('inverted_fullback' if possession and p is Position.RB and variant % 2
                    else 'wingback' if possession or style == 'wide_attack'
                    else 'defensive_fullback' if deep else 'balanced_fullback')
        elif p in WB:
            role = ('wide_playmaker_wingback' if possession and p is Position.LWB
                    else 'defensive_wingback' if style == 'low_block'
                    else 'attacking_wingback' if style == 'wide_attack'
                    else 'wingback')
        elif p is Position.DM:
            role = ('deep_lying_playmaker' if possession and n == 0
                    else 'ball_winning_midfielder' if press and n == 0
                    else 'anchor' if deep else 'holding_midfielder')
        elif p in CM:
            role = (('central_playmaker' if n % 2 else 'central_midfielder') if possession
                    else ('box_to_box' if n % 2 else 'ball_winning_midfielder') if press
                    else ('central_playmaker' if n % 2 else 'ball_winning_midfielder') if direct
                    else ('central_midfielder' if n % 2 else 'box_to_box'))
        elif p is Position.AM:
            role = ('advanced_playmaker' if possession or n == 0 else 'shadow_striker')
        elif p in WIDE:
            # Deeper LM/RM remain LW/RW domain aliases, as in the TS-19 hotfix.
            label = next((label for sid, _x, _y, label in _layout(tactic.formation)
                          if sid == slot.slot_id), p.value)
            y = next(row[2] for row in _layout(tactic.formation) if row[0] == slot.slot_id)
            deeper = label in ('LM', 'RM') or y >= .40
            role = ('defensive_winger' if deeper and deep
                    else 'wide_playmaker' if deeper and possession
                    else 'inside_forward' if not deeper and possession and p is Position.LW
                    else 'inverted_winger' if press and p is Position.RW
                    else 'winger')
        elif p is Position.SS:
            role = 'pressing_second_striker' if press else 'second_striker'
        else:
            total = sum(s.position is Position.ST for s in tactic.formation.slots)
            role = ('target_forward' if direct and n == 0
                    else 'advanced_forward' if total > 1 and n == 1
                    else 'pressing_forward' if press
                    else 'deep_lying_forward' if possession and total > 1
                    else 'false_nine' if style == 'tiki_taka'
                    else 'advanced_forward')
        tactic.set_role(slot.slot_id, role)


def _layout(formation):
    from football_manager.domain.tactical_catalogue import formation_board_layouts, formation_slot_label
    # Return coordinates/labels from the same catalogue used by the portable UI.
    raw = formation_board_layouts()[formation.formation_id]
    return tuple((s.slot_id, *raw[s.slot_id],
                  formation_slot_label(formation.formation_id, s.slot_id, s.position.value))
                 for s in formation.slots)


def make_identity(club_id: str, name: str, tier: int, style: str, seed: int,
                  formation_id: str | None = None) -> ClubFootballIdentity:
    rng = Random(stable_seed(seed, club_id, 'tactics'))
    formation_id = formation_id or 'dev-' + rng.choice(STYLE_FORMATIONS[style])
    main_form = formation_by_id(formation_id)
    alternative_id = 'dev-' + ALTERNATIVES.get(formation_id.removeprefix('dev-'),
                                              formation_id.removeprefix('dev-'))
    main = Tactic.from_preset(f'{club_id}-primary', f'{name} Primary', main_form,
                             TacticalPreset(style))
    alt = Tactic.from_preset(f'{club_id}-alternative', f'{name} Alternative',
                            formation_by_id(alternative_id), TacticalPreset(style))
    _roles(main, style, rng.randrange(4))
    _roles(alt, style, rng.randrange(4))
    # Club-level variants inside a style, without randomizing every control.
    main.update_in_possession(switch_play=rng.choice((Level.NORMAL, Level.HIGH)))
    alt.update_game_management(risk_when_leading=Level.LOW)
    return ClubFootballIdentity(club_id, tier, tier, style, main, alt)


def _secondary_positions(position: Position, versatile: bool, rng: Random) -> dict[Position, float]:
    values = {position: 96.0}
    if position in CB:
        values.update({p: 91.0 for p in CB if p is not position})
    elif position in CM:
        values.update({p: 90.0 for p in CM if p is not position})
    neighbours = {
        Position.RB: (Position.RWB, Position.RCB), Position.LB: (Position.LWB, Position.LCB),
        Position.RWB: (Position.RB, Position.RW), Position.LWB: (Position.LB, Position.LW),
        Position.RCB: (Position.RB, Position.DM), Position.CB: (Position.DM,),
        Position.LCB: (Position.LB, Position.DM), Position.DM: (Position.CM,),
        Position.RCM: (Position.DM, Position.AM), Position.LCM: (Position.AM, Position.DM),
        Position.CM: (Position.DM, Position.AM), Position.AM: (Position.CM, Position.SS),
        Position.RW: (Position.AM, Position.ST), Position.LW: (Position.AM, Position.ST),
        Position.ST: (Position.SS,), Position.SS: (Position.ST, Position.AM),
    }
    # Natural defensive/wing-back neighbours, not a universal utility player.
    if position in FB | WB:
        values[neighbours[position][0]] = 88.0
    if versatile and position in neighbours:
        values[rng.choice(neighbours[position])] = float(rng.randint(82, 90))
    return values


def make_player(*, player_id: str, position: Position, role_id: str, quality: float,
                age: int, on_date: date, seed: int, style: str, versatile: bool,
                tactics: tuple[Tactic, ...]) -> Player:
    rng = Random(stable_seed(seed, player_id))
    first, last = rng.choice(FIRST_NAMES), rng.choice(LAST_NAMES)
    left = position in (Position.LB, Position.LWB, Position.LCB, Position.LCM, Position.LW)
    inverted = role_id in ('inverted_fullback', 'inverted_wingback', 'inverted_winger', 'inside_forward')
    foot = Foot.LEFT if left != inverted else Foot.RIGHT
    if rng.random() < .12:
        foot = Foot.BOTH
    # Exact age at bootstrap. Month/day varies without invalid leap birthdays.
    month, day = rng.randint(1, 12), rng.randint(1, 28)
    year = on_date.year - age - ((month, day) > (on_date.month, on_date.day))
    familiarity = PositionalFamiliarity(_secondary_positions(position, versatile, rng))
    groups = (('technical', TechnicalAttributes), ('mental', MentalAttributes),
              ('physical', PhysicalAttributes)) + ((('goalkeeping', GoalkeepingAttributes),)
                                                 if position is Position.GK else ())
    offsets = {f'{group}.{f.name}': rng.uniform(-10, 10)
               for group, cls in groups for f in fields(cls)}
    # Specialism changes the attribute distribution, not the target ability.
    important = dict(get_role(role_id).attribute_weights)
    for path, weight in important.items():
        if path in offsets:
            offsets[path] += 5 + 3 * weight
    if position in CB:
        for key in ('technical.finishing', 'technical.dribbling', 'technical.crossing'):
            offsets[key] -= 19
    if position in WIDE | {Position.ST, Position.SS, Position.AM}:
        for key in ('technical.tackling', 'technical.marking'):
            offsets[key] -= 20
    if role_id == 'target_forward':
        offsets['physical.pace'] -= 12; offsets['physical.acceleration'] -= 12
    if role_id in ('advanced_forward', 'inside_forward', 'winger'):
        offsets['physical.pace'] += 10; offsets['physical.acceleration'] += 9
    if style in ('possession', 'tiki_taka'):
        for key in ('technical.passing', 'technical.first_touch', 'mental.decisions'):
            offsets[key] += 7
    if style in ('constant_press', 'counterpress'):
        for key in ('physical.stamina', 'mental.work_rate', 'mental.teamwork'):
            offsets[key] += 9
    if style in ('direct_play', 'direct_counter'):
        for key in ('physical.strength', 'technical.heading', 'physical.jumping_reach'):
            offsets[key] += 6
    if position is Position.GK:
        for key in offsets:
            if key.startswith('technical.') and key != 'technical.passing':
                offsets[key] -= 30
    if age >= 32:
        offsets['physical.pace'] -= 7; offsets['physical.acceleration'] -= 7
        offsets['mental.positioning'] += 5; offsets['mental.decisions'] += 5

    def attributes(budget: float) -> PlayerAttributes:
        built = {group: cls(**{f.name: max(1, min(100, round(budget + offsets[f'{group}.{f.name}'])))
                              for f in fields(cls)}) for group, cls in groups}
        return PlayerAttributes(**built)

    player = Player(
        PlayerIdentity(player_id, first, last, date(year, month, day),
                       rng.choices(('England', 'Scotland', 'Wales', 'Ireland', 'Northern Ireland'),
                                   (66, 10, 9, 10, 5))[0], foot),
        attributes(quality), familiarity, position, position,
        state=PlayerState(form=float(rng.randint(62, 72)), morale=float(rng.randint(64, 76)),
                          confidence=float(rng.randint(62, 74)), match_sharpness=75.0),
    )
    # Calibrate only a newly generated player; never re-rate existing footballers.
    lo, hi = 1.0, 100.0
    best = player.attributes
    error = float('inf')
    for _ in range(12):
        mid = (lo + hi) / 2
        player.attributes = attributes(mid)
        actual = player.overall_rating_for(position, role_id)
        if abs(actual - quality) < error:
            error, best = abs(actual - quality), player.attributes
        if actual < quality:
            lo = mid
        else:
            hi = mid
    player.attributes = best
    role = get_role(role_id)
    for other in roles_for_position(position):
        player.tactical_familiarity.set_role_score(
            other.role_id, max(55.0, 85.0 - (100 - role_similarity(role, other)) * .25))
    for tactic in tactics:
        player.tactical_familiarity.set_tactic_score(tactic.tactic_id, 83.0 if tactic is tactics[0] else 74.0)
        for slot in tactic.formation.slots:
            if player.familiarity_for(slot.position) >= 75:
                rid = tactic.role_for_slot(slot.slot_id).role_id
                if rid not in player.tactical_familiarity.role_values:
                    player.tactical_familiarity.set_role_score(rid, 70.0)
    return player


def generate_club(*, club_id: str, name: str, tier: int, quality: float,
                  seed: int, on_date: date, style: str,
                  formation_id: str | None = None) -> tuple[Club, ClubFootballIdentity]:
    identity = make_identity(club_id, name, tier, style, seed, formation_id)
    rng = Random(stable_seed(seed, club_id, 'squad'))
    gaps = [rng.gauss(0, 2.0) for _ in range(11)]
    mean = sum(gaps) / 11
    gaps = [x - mean for x in gaps]
    star = rng.randrange(1, 11)
    gaps[star] += 3.0
    # A shallow bench or stronger depth is a club characteristic, not a tier bonus.
    bench_gap = rng.uniform(4.0, 8.0)
    versatile_indices = set(rng.sample(list(range(1, 11)) + list(range(12, 22)), 6))
    players = []
    for layer in range(2):
        for i, slot in enumerate(identity.primary.formation.slots):
            index = layer * 11 + i
            age = rng.randint(22, 31) if layer == 0 else rng.randint(20, 29)
            if layer == 1 and i in (2, 5, 8):
                age = rng.randint(17, 20)
            if i == 0:
                age = rng.randint(25, 35) if layer == 0 else rng.randint(21, 31)
            if layer == 1 and i == 4:
                age = rng.randint(32, 36)
            target = quality + gaps[i] - (0 if layer == 0 else bench_gap + rng.uniform(-1, 3))
            player = make_player(
                player_id=f'ew1-{stable_seed(seed, club_id, index):016x}',
                position=slot.position, role_id=identity.primary.role_for_slot(slot.slot_id).role_id,
                quality=max(25.0, min(94.0, target)), age=age, on_date=on_date,
                seed=seed, style=style, versatile=index in versatile_indices,
                tactics=(identity.primary, identity.alternative),
            )
            players.append(player)
    short = ''.join(part[0] for part in name.split() if part not in ('FC', 'AFC'))[:3].upper()
    return Club(club_id, name, short or club_id[:3].upper(), 'England',
                Squad.from_players(tuple(players))), identity
