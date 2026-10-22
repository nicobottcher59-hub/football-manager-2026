"""TS-23: persistent academy pipeline, youth fixtures and FIFA-style quarterly scouts.

Only senior players enter the professional match engine. Youth matches are
cheap, deterministic per-fixture updates feeding the same TS-21 CA/PA and
attribute-review functions. No youth simulation runs during read-only API calls.
"""
from __future__ import annotations
from dataclasses import replace
from datetime import date, timedelta
from random import Random

from football_manager.data.english_players import FIRST_NAMES, LAST_NAMES, make_player, stable_seed
from football_manager.domain.enums import Position
from football_manager.domain.player import PlayerIdentity
from football_manager.domain.youth_academy import (
    YouthAcademy, YouthFixture, YouthPreview, YouthScout, YouthScoutingCandidate, YouthSystem,
)
from football_manager.domain.player_development import (
    current_ability, initialize_development, add_match_exposure, next_month, reference_overall,
)
from football_manager.domain.player_aging import initialize_aging, review_career
from football_manager.domain.roles import default_role_for_position
from football_manager.domain.season_cycle import TIER_IDS

POSITION_POOL = (Position.GK, Position.GK, Position.LB, Position.RB,
                 Position.LCB, Position.RCB, Position.CB, Position.DM,
                 Position.CM, Position.LCM, Position.RCM, Position.AM,
                 Position.LW, Position.RW, Position.ST, Position.ST,
                 Position.LB, Position.CM, Position.CB, Position.RB)
COUNTRIES = ('England', 'Scotland', 'Wales', 'Ireland', 'Northern Ireland',
             'Brazil', 'Argentina', 'France', 'Spain', 'Germany', 'Portugal',
             'Netherlands', 'Italy', 'Nigeria', 'Ghana', 'Japan', 'Colombia', 'Uruguay')
PROFILES = ('any', 'GK', 'CB', 'FB', 'MID', 'WIDE', 'ST')
MAX_U15 = 20
MAX_U17 = 23
MAX_U21 = 24
MAX_REPORT_CANDIDATES = 90
MAX_HIRED_SCOUTS = 3
RECRUITMENT_STARTING_FUNDS = 500_000
SCOUT_NAMES = ('James Wilson', 'Carlos Mendes', 'Harry Morgan', 'Alexander Reed',
               'Oliver Bennett', 'Diego Alvarez', 'Matteo Rossi', 'Daniel Foster',
               'Liam Hughes', 'Samuel Turner', 'Marcus Bell', 'Thomas Carter')


def _rng(*parts) -> Random:
    return Random(stable_seed(23, *parts))


def _birthday_at_age(today: date, age: int, rng: Random) -> date:
    month, day = rng.randint(1, 12), rng.randint(1, 28)
    year = today.year - age - ((month, day) > (today.month, today.day))
    return date(year, month, day)


def _country(rng: Random, region: str = 'England') -> str:
    if region != 'England':
        return region
    return rng.choices(COUNTRIES[:5] + ('France', 'Nigeria'),
                       weights=(78, 6, 5, 4, 3, 2, 2))[0]


def _talent(seed: int, club_id: str, key: str, level: int, *, on_date: date, country: str,
            position: Position, age: int, source: str) -> YouthPreview:
    rng = _rng(seed, club_id, key, 'talent')
    # Ability and potential are related, not identical. No club guaranteed stars.
    base = (41, 36, 31, 27)[min(4, max(1, level)) - 1]
    roll = rng.random()
    bonus = (rng.uniform(23, 28) if roll < .0004 else
             rng.uniform(12, 21) if roll < .013 else
             rng.uniform(5, 12) if roll < .105 else 0)
    quality = max(17, min(89, base + rng.gauss(0, 7) + bonus))
    potential = max(quality, min(99, quality + rng.uniform(6, 24) +
                                  (rng.uniform(15, 32) if roll < .018 else 0)))
    # The rare already-exceptional 18-19-year-old is not forced by intake.
    first, last = rng.choice(FIRST_NAMES), rng.choice(LAST_NAMES)
    return YouthPreview(
        f'ya23-{stable_seed(seed, club_id, key):016x}', first, last,
        _birthday_at_age(on_date, age, rng), country, position,
        round(quality, 2), round(potential, 2), source,
    )


def _preview_to_player(preview: YouthPreview, academy: YouthAcademy, registry, on_date: date) -> object:
    identity = registry.identities[academy.club_id]
    role_id = default_role_for_position(preview.position).role_id
    player = make_player(
        player_id=preview.player_id, position=preview.position, role_id=role_id,
        quality=preview.initial_ovr, age=preview.age_on(on_date), on_date=on_date,
        seed=registry.seed, style=identity.style_key, versatile=True,
        tactics=(identity.primary, identity.alternative),
    )
    player.identity = replace(player.identity,
        first_name=preview.first_name, last_name=preview.last_name,
        birth_date=preview.birth_date, nationality=preview.nationality)
    ca = current_ability(player)
    # Imported PA is hidden and attached to the genuine TS-21 development model.
    # CA isn't OVR: use the generated relative *headroom*, not OVR as PA.
    headroom = max(0, preview.potential_budget - preview.initial_ovr)
    pa = min(99.9, max(ca, ca + headroom))
    initialize_development(player, on_date, registry.seed,
        potential=pa, source='academy-scouting-v1')
    initialize_aging(player, on_date, registry.seed)
    player.state.match_sharpness = 65.0
    return player


def _initial_academy(registry, club_id: str, on_date: date) -> YouthAcademy:
    identity = registry.identities[club_id]
    academy = YouthAcademy(club_id)
    for idx, position in enumerate(POSITION_POOL):
        rng = _rng(registry.seed, club_id, 'u15', idx)
        youth = _talent(registry.seed, club_id, f'u15-bootstrap-{idx}', identity.initial_tier,
                        on_date=on_date, country=_country(rng), position=position,
                        age=15 if idx < 12 else 14, source='local-academy')
        academy.u15[youth.player_id] = youth
    for level, total in (('u17', 18), ('u21', 18)):
        for idx in range(total):
            position = POSITION_POOL[idx]
            age = (16 + idx % 2) if level == 'u17' else (18 + idx % 3)
            rng = _rng(registry.seed, club_id, level, idx)
            preview = _talent(registry.seed, club_id, f'{level}-bootstrap-{idx}', identity.initial_tier,
                on_date=on_date, country=_country(rng), position=position,
                age=age, source='academy-bootstrap')
            getattr(academy, level)[preview.player_id] = _preview_to_player(preview, academy, registry, on_date)
    return academy


def _fixture_calendar(registry, label: str) -> dict[str, YouthFixture]:
    """Two lightweight double round robins per professional division."""
    year = int(label[:4]); fixtures = {}
    for division in TIER_IDS:
        club_ids = sorted(cid for cid, record in registry.identities.items()
                          if record.tier == TIER_IDS.index(division) + 1)
        if len(club_ids) % 2 or len(club_ids) < 2:
            continue
        order = list(club_ids)
        # Circle rotation: each pairing occurs exactly once per leg.
        round_count = len(order) - 1
        for rnd in range(round_count):
            pairings = [(order[j], order[-j-1]) for j in range(len(order)//2)]
            for leg in range(2):
                number = rnd + round_count * leg
                week = date(year, 8, 1) + timedelta(days=7*number)
                # Saturdays, never conflict with senior fixture schedule.
                match_day = week + timedelta(days=(5-week.weekday()) % 7)
                for match_idx, (home, away) in enumerate(pairings):
                    if (rnd + match_idx + leg) % 2:
                        home, away = away, home
                    for level in ('u17', 'u21'):
                        fid = f'ya23-{label}-{level}-{division}-{number:02d}-{match_idx:02d}'
                        fixtures[fid] = YouthFixture(fid, division, level, home, away, match_day)
            order = [order[0], order[-1], *order[1:-1]]
    return fixtures


def initialize_youth(registry, on_date: date, managed_club_id: str) -> YouthSystem:
    if registry.youth is not None:
        return registry.youth
    academies = {cid: _initial_academy(registry, cid, on_date) for cid in registry.clubs}
    youth = YouthSystem(registry.seed, registry.season_label, on_date, academies)
    youth.managed_club_id = managed_club_id
    youth.fixtures = _fixture_calendar(registry, registry.season_label)
    # New careers start without employees; their recruitment allocation is
    # available for the manager to use on paid hires, not free starter scouts.
    youth.recruitment_funds = RECRUITMENT_STARTING_FUNDS
    youth.last_scout_payroll = on_date.replace(day=1)
    registry.youth = youth
    youth.check_unique(registry)
    return youth


def scout_market(youth: YouthSystem) -> list[dict]:
    """Stable offers for the season, not new random people on every page load."""
    rng = _rng(youth.seed, youth.managed_club_id, youth.season_label, 'scout-offers')
    offers = []
    for index in range(8):
        quality = min(96, max(29, int(rng.gauss(59, 17))))
        wage = int(round((750 + 43 * quality + .24 * quality**2) / 100) * 100)
        fee = int(round((1800 + 69 * quality) / 100) * 100)
        offers.append({'id':f'{youth.season_label}-offer-{index+1}',
                       'name':SCOUT_NAMES[index], 'quality':quality,
                       'judging_potential': min(99,max(1,quality+rng.randint(-8,9))),
                       'judging_ability': min(99,max(1,quality+rng.randint(-8,9))),
                       'monthly_wage':wage, 'signing_fee':fee})
    return offers


def _pay_scouts(youth: YouthSystem, boundary: date) -> None:
    """Monthly, idempotent youth allocation charges; no negative funds."""
    stamp = boundary.replace(day=1)
    if youth.last_scout_payroll is not None and stamp <= youth.last_scout_payroll:
        return
    for sid, scout in sorted(tuple(youth.scouts.items())):
        if scout.contract_until is not None and boundary >= scout.contract_until:
            del youth.scouts[sid]
            continue
        if scout.monthly_wage > youth.recruitment_funds:
            # Expired recruitment budget stops this employment, rather than
            # secretly paying with money the game does not yet simulate.
            del youth.scouts[sid]
            continue
        youth.recruitment_funds -= scout.monthly_wage
        youth.recruitment_spent += scout.monthly_wage
    youth.last_scout_payroll = stamp


def _candidate_risk(candidate: YouthScoutingCandidate, today: date) -> tuple[str, float]:
    age = max(0, (today-candidate.discovered_on).days)
    quality = candidate.preview.potential_budget
    monthly = .06 + (.12 if quality>=85 else .07 if quality>=75 else .025)
    monthly += min(.09, max(0,age-30)/750)
    return ('High' if monthly>=.17 or age>=120 else 'Medium' if monthly>=.10 or age>=60 else 'Low', monthly)


def _poach_prospects(registry, youth: YouthSystem, boundary: date, journal) -> int:
    """A rival signs an unsigned candidate; identity is kept, never cloned."""
    total = 0
    for pid, candidate in tuple(youth.candidates.items()):
        if candidate.status not in ('available','watching'):
            continue
        elapsed = (boundary-candidate.discovered_on).days
        if elapsed < 30:
            continue
        _, risk = _candidate_risk(candidate,boundary)
        chance = min(.34, risk * min(1.5, elapsed/45))
        if _rng(registry.seed, pid,'poach',boundary.isoformat()).random() >= chance:
            continue
        available = [cid for cid,academy in youth.academies.items()
                     if cid != youth.managed_club_id and len(academy.u17)<MAX_U17]
        if not available:
            continue
        target = _rng(registry.seed,pid,'rival',boundary.isoformat()).choice(sorted(available))
        academy = youth.academies[target]
        player = _preview_to_player(candidate.preview,academy,registry,boundary)
        academy.u17[pid] = player
        youth.lost_prospects[pid] = (candidate.preview.full_name,boundary,target)
        del youth.candidates[pid]
        journal.undo_callbacks.setdefault(('youth-poach',pid),
            lambda key=pid, original=candidate, roster=academy.u17:
            (roster.pop(key,None), youth.lost_prospects.pop(key,None),
             youth.candidates.__setitem__(key,original)))
        total += 1
    # Keep the archive bounded; historic rival player stays in their club.
    if len(youth.lost_prospects)>60:
        for key in list(youth.lost_prospects)[:-60]:
            old = youth.lost_prospects.pop(key)
            journal.undo_callbacks.setdefault(('youth-poach-history',key),
                lambda k=key,entry=old:youth.lost_prospects.__setitem__(k,entry))
    return total


def _team(academy: YouthAcademy, level: str, on_date: date):
    """Choose a balanced youth XI rather than eleven high-rated outfielders.

    This lightweight 4-3-3 is independent of the fully simulated senior tactic.
    Keepers are never used as outfield substitutes.
    """
    roster = list(getattr(academy, level).values())
    season_start = date(on_date.year if on_date.month >= 8 else on_date.year-1, 8, 1)
    eligible = [p for p in roster if p.age_on(season_start) <= (17 if level == 'u17' else 21)
                and p.state.injury is None]
    eligible.sort(key=lambda p:(-reference_overall(p),p.id))
    keepers = [p for p in eligible if p.primary_position is Position.GK]
    fielders = [p for p in eligible if p.primary_position is not Position.GK]
    if not keepers or len(fielders) < 10:
        return ()
    groups = (
        (Position.RB,Position.RWB),
        (Position.RCB,Position.CB,Position.LCB),
        (Position.LCB,Position.CB,Position.RCB),
        (Position.LB,Position.LWB),
        (Position.DM,Position.CM),
        (Position.RCM,Position.CM,Position.AM),
        (Position.LCM,Position.CM,Position.AM),
        (Position.RW,),
        (Position.ST,),
        (Position.LW,),
    )
    lineup = [keepers[0]]
    for positions in groups:
        selected = next((p for p in fielders if p.primary_position in positions),fielders[0])
        lineup.append(selected)
        fielders.remove(selected)
    return tuple(lineup)


def _simulate_youth_fixtures(registry, youth: YouthSystem, boundary: date, world) -> tuple[int,int]:
    from football_manager.domain.player_development import add_match_exposure
    count, exposures = 0, 0
    active = world._active_journal
    for fid, fixture in youth.fixtures.items():
        if fixture.home_goals is not None or not youth.last_processed < fixture.match_date < boundary:
            continue
        home = youth.academies.get(fixture.home_club_id)
        away = youth.academies.get(fixture.away_club_id)
        if home is None or away is None:
            continue
        first, second = _team(home, fixture.level, fixture.match_date), _team(away, fixture.level, fixture.match_date)
        rng = _rng(registry.seed, fid, 'result')
        if not first or not second:
            # Unplayed: avoid fake results and phantom minutes when fewer than 11 eligible.
            continue
        def strength(team):
            return sum(reference_overall(p) for p in team) / 11
        diff = (strength(first) - strength(second)) / 20
        goals_h = max(0, min(7, round(rng.gauss(1.4 + diff*.6, 1.0))))
        goals_a = max(0, min(7, round(rng.gauss(1.15 - diff*.6, 1.0))))
        previous = (fixture.home_goals, fixture.away_goals)
        active.undo_callbacks[('youth-fixture',fid)] = lambda obj=fixture,prior=previous: (
            setattr(obj,'home_goals',prior[0]),setattr(obj,'away_goals',prior[1]))
        fixture.home_goals, fixture.away_goals = goals_h, goals_a
        count += 1
        for team,goals in ((first,goals_h),(second,goals_a)):
            for player in team:
                minutes = 90
                # Youth competition below senior intensity; no invented senior appearances.
                challenge = .70 if fixture.level == 'u17' else .83
                role = default_role_for_position(player.primary_position).role_id
                rating = max(3.0,min(9.5,6.3 + rng.uniform(-.7,.7) + .08*goals))
                previous_development = player.development
                previous_sharpness = player.state.match_sharpness
                active.undo_callbacks.setdefault(('youth-player',player.id),
                    lambda obj=player,dev=previous_development,sharp=previous_sharpness:
                    (setattr(obj,'development',dev),setattr(obj.state,'match_sharpness',sharp)))
                player.development = add_match_exposure(player,minutes=minutes,rating=rating,
                    role_minutes={role:minutes},challenge=challenge)
                player.state.match_sharpness = min(94.0,player.state.match_sharpness+1.7)
                exposures += 1
    return count,exposures


def _month_scout_reports(registry, youth: YouthSystem, boundary: date) -> int:
    reports = 0
    for scout in youth.scouts.values():
        if scout.next_report is None:
            continue
        while scout.next_report <= boundary:
            when = scout.next_report
            rng = _rng(registry.seed, scout.scout_id,when.isoformat(),'scout')
            # 45 -> 3-5, 67 -> 5-7, 87 -> 7-9. Never 15.
            centre = 4 if scout.quality < 55 else 6 if scout.quality < 80 else 8
            count = min(9, max(2, centre + rng.choice((-1, 0, 1))))
            region = scout.country
            from football_manager.services.world_squads import position_family
            possible = [p for p in POSITION_POOL if scout.position == 'any' or
                        position_family(p) == scout.position]
            if not possible:
                possible = list(POSITION_POOL)
            # Candidate quality is not automatically high because scouting skill is high.
            # Assessment uncertainty, quantity and occasional discoveries vary by scout.
            for i in range(count):
                if len(youth.candidates) >= MAX_REPORT_CANDIDATES:
                    break
                player = _talent(registry.seed, 'scout-world', f'{scout.scout_id}-{when}-{i}',
                    2, on_date=when, country=region,position=rng.choice(possible),
                    age=rng.choice((15,16,17)),source=f'scout-{region}')
                youth.candidates[player.player_id] = YouthScoutingCandidate(
                    player,when,scout.scout_id,scout.quality)
            # Every unsigned discovery is followed automatically: no manual
            # 'Keep scouting' decision or hidden watchlist priority.
            for candidate in youth.candidates.values():
                if candidate.scout_id==scout.scout_id and candidate.status in ('available','watching') \
                        and candidate.discovered_on < when:
                    candidate.confidence=min(97,candidate.confidence+10)
            scout.reports_sent += 1
            scout.next_report = _quarter_after(when)
            youth.generated_reports += 1
            reports += 1
    return reports


def _quarter_after(start: date) -> date:
    month = (start.month - 1 + 3) % 12 + 1
    year = start.year + (start.month - 1 + 3) // 12
    return date(year,month,min(start.day,28))


def _ai_quarterly_recruitment(registry, youth: YouthSystem, boundary: date, journal) -> int:
    """Automatically seek occasional new juveniles for rival academies.

    Scouts generate fresh identities; they do not search a pre-existing foreign
    roster. Academy caps prevent inflation and no premium club is guaranteed a
    prodigy. This is AI decision-making, not a user-visible scouting report.
    """
    if boundary.month not in (2, 5, 8, 11):
        return 0
    signed = 0
    for cid,academy in youth.academies.items():
        if cid == youth.managed_club_id or cid not in registry.clubs:
            continue
        if len(academy.u17) >= MAX_U17:
            continue
        rng = _rng(registry.seed,cid,'ai-scout',boundary.isoformat())
        # Most youth scouting is domestic; imports are a minority.
        country = _country(rng) if rng.random() < .82 else rng.choice(COUNTRIES)
        position = rng.choice(POSITION_POOL)
        key = f'ia-quarterly-{boundary.year}-{boundary.month}'
        preview = _talent(registry.seed,cid,key,registry.identities[cid].initial_tier,
                          on_date=boundary,country=country,position=position,
                          age=rng.choice((15,16,17)),source='ai-quarterly-scout')
        if preview.id in academy.u17:
            continue
        player = _preview_to_player(preview,academy,registry,boundary)
        academy.u17[player.id] = player
        journal.undo_callbacks.setdefault(('youth-ai-recruit',cid,boundary),
            lambda roster=academy.u17,pid=player.id: roster.pop(pid,None))
        signed += 1
    return signed


def process_youth_month(world, boundary: date) -> dict:
    """One call per TS-21 monthly boundary inside the world transaction."""
    registry = world.football_world
    youth = registry.youth
    if youth is None or boundary <= youth.last_processed:
        return {'matches':0,'reports':0,'reviews':0}
    journal = world._active_journal
    if journal is None:
        raise RuntimeError('youth clock requires a world transaction')
    previous_date = youth.last_processed
    journal.undo_callbacks.setdefault(('youth-clock', id(youth)),
        lambda: setattr(youth,'last_processed',previous_date))
    played,participation = _simulate_youth_fixtures(registry,youth,boundary,world)
    reviews = 0
    for cid,academy in youth.academies.items():
        env = registry.development_environments[cid]
        for level in ('u17','u21'):
            for player in getattr(academy,level).values():
                profile = player.development
                if profile is None or boundary <= profile.last_review:
                    continue
                previous = player.attributes,player.development,player.aging,player.state.injury
                journal.undo_callbacks.setdefault(('youth-review',player.id),
                    lambda p=player,old=previous:
                    (setattr(p,'attributes',old[0]),setattr(p,'development',old[1]),
                     setattr(p,'aging',old[2]),setattr(p.state,'injury',old[3])))
                # Shared TS-21 engine; softer competitive training intensity
                # than first-team football, with stronger U21 than U17.
                youth_environment = replace(env,training_quality=
                    round(env.training_quality*(.76 if level=='u17' else .87),2))
                attrs,profile_new,aging = review_career(player,boundary,youth_environment)
                player.attributes,player.development,player.aging = attrs,profile_new,aging
                reviews += 1
    # Only prune reports when an explicit, reproducible period has elapsed.
    for pid,candidate in tuple(youth.candidates.items()):
        if candidate.status == 'dismissed' or (boundary - candidate.discovered_on).days >= (365 if candidate.status == 'watching' else 190):
            previous = candidate
            journal.undo_callbacks.setdefault(('youth-candidate',pid),
                lambda old=previous,key=pid: youth.candidates.__setitem__(key,old))
            del youth.candidates[pid]
    # Scouts and reports update after review; rollback their small state if needed.
    scout_checkpoint = {sid:(s,s.next_report,s.reports_sent) for sid,s in youth.scouts.items()}
    confidence_before = {pid:c.confidence for pid,c in youth.candidates.items()}
    count_before = youth.generated_reports
    existing = set(youth.candidates)
    funds_before = (youth.recruitment_funds,youth.recruitment_spent,youth.last_scout_payroll)
    journal.undo_callbacks.setdefault(('youth-scouts', id(youth)),
        lambda: _rollback_scouts(youth,scout_checkpoint,count_before,existing,confidence_before,funds_before))
    _pay_scouts(youth,boundary)
    _ai_quarterly_recruitment(registry,youth,boundary,journal)
    reports = _month_scout_reports(registry,youth,boundary)
    _poach_prospects(registry,youth,boundary,journal)
    youth.last_processed = boundary
    return {'matches':played,'reports':reports,'reviews':reviews}


def _rollback_scouts(youth, snapshot, old_count, old_candidates, confidence_before, funds_before):
    youth.scouts.clear()
    for sid,(scout,when,count) in snapshot.items():
        scout.next_report = when
        scout.reports_sent = count
        youth.scouts[sid] = scout
    youth.recruitment_funds,youth.recruitment_spent,youth.last_scout_payroll = funds_before
    youth.generated_reports = old_count
    for pid in set(youth.candidates)-old_candidates:
        del youth.candidates[pid]
    for pid, quality in confidence_before.items():
        if pid in youth.candidates:
            youth.candidates[pid].confidence=quality


def _academy_promotions(registry, academy: YouthAcademy, on_date: date,
                        *, managed_club_id: str | None = None) -> dict[str,int]:
    """Promote existing U21 footballers by tactical need and senior readiness.

    TS-24.8: eligible graduates no longer enter the XI solely by dictionary
    order, and a club may call up a sufficiently ready 19/20-year-old to cover
    a *real* reserve vacancy. The manager retains all manual first-team rights.
    No player is generated by this routine and all IDs survive unchanged.
    """
    counts={'u15_to_u17':0,'u17_to_u21':0,'u21_to_first':0,'released':0}
    if academy.club_id != managed_club_id and academy.club_id in registry.clubs:
        from football_manager.services.ai_squad_planning import squad_plan
        club = registry.clubs[academy.club_id]
        tactic = registry.identities[academy.club_id].primary
        tier = registry.identities[academy.club_id].tier
        # Younger call-ups must be credible substitutes for their league.
        # 21-year-olds are evaluated through the regular graduation policy.
        youth_ready_ovr = {0:30,1:47,2:40,3:34,4:29}.get(tier,29)
        promoted = 0
        protected_retiring_ids=set()
        while promoted < 8 and len(club.squad) < 29:
            plan = squad_plan(club,tactic)
            vacancies = [need for need in plan['vacancies'] if need['layer'] <= 2]
            # Preserve a natural third goalkeeper where a genuine U21 prospect
            # has matured. Existing financial distress must not prevent a club
            # from developing its OWN players. This is optional squad depth,
            # not a synthetic transfer or a guarantee of XI coverage.
            natural_keepers = sum(p.primary_position is Position.GK for p in club.squad.players)
            if natural_keepers == 2:
                vacancies.append({'layer':3, 'slot_id':'third-keeper', 'position':'GK'})
            # Recruit into tomorrow's vacancy *before* a veteran retires.
            # Only actual requested/deferred retirements qualify, not an
            # age-based arbitrary purge. This also prevents holding 45-year-
            # olds indefinitely because releasing them would break the XI.
            retirements=[]
            for slot in plan['assignments']:
                if slot['layer'] > 2 or slot['player_id'] in protected_retiring_ids:
                    continue
                veteran=club.squad.get(slot['player_id'])
                aging=veteran.aging
                if aging is not None and aging.retirement_status in ('requested','deferred'):
                    retirements.append({**slot, 'is_retirement_cover':True})
            u23 = sum(p.age_on(on_date) < 23 for p in club.squad.players)
            candidates=[]
            for candidate in academy.u21.values():
                age = candidate.age_on(on_date)
                if age < 19:
                    continue
                fit = next((need for need in (*vacancies,*retirements)
                            if candidate.familiarity_for(Position(need['position'])) >= 70
                            and ((candidate.primary_position is Position.GK) ==
                                 (need['position'] == 'GK'))), None)
                ready = candidate.overall_rating >= youth_ready_ovr
                # Never stockpile a fourth goalkeeper. An optional third
                # needs a credible U21 profile, not a newly created reserve.
                if candidate.primary_position is Position.GK and natural_keepers >= 3:
                    continue
                if (candidate.primary_position is Position.GK and natural_keepers == 2
                        and (fit is None or age < 20 or
                             candidate.overall_rating < max(25, youth_ready_ovr - 4))):
                    continue
                # A developing U19/U20 is promoted early only for a tactical
                # shortage, or after reaching 20 if the club lacks U23 players.
                if age < 21 and not ready:
                    continue
                if age < 21 and fit is None and not (age >= 20 and u23 < 4):
                    continue
                # Prevent a club full of established youths from stockpiling
                # unneeded players merely because they are graduating.
                if fit is None and not (len(club.squad) < 24 or u23 < 4):
                    continue
                if fit is None and len(club.squad) >= 27:
                    continue
                # Prioritize starter/backup coverage before age or raw OVR;
                # flexible players compete for ONE slot, then recompute plan.
                priority = (300 if fit and fit['layer']==1 else
                            210 if fit and fit.get('is_retirement_cover') else
                            180 if fit and fit['layer']==2 else
                            60 if fit and fit['layer']==3 else 0)
                rank = (priority + (15 if age>=21 else 0)
                        + candidate.overall_rating*.40
                        + min(age,21)*.05)
                candidates.append((rank,candidate.id,candidate,
                                   fit.get('player_id') if fit and fit.get('is_retirement_cover') else None))
            if not candidates:
                break
            _,pid,player,retiring_id=max(candidates,key=lambda row:(row[0],row[1]))
            if retiring_id:
                protected_retiring_ids.add(retiring_id)
            academy.u21.pop(pid)
            club.squad.add(player)
            academy.graduates[pid]='first'
            counts['u21_to_first'] += 1
            promoted += 1
    # 21+ players cannot remain indefinitely registered in an U21 squad.
    # The managed club can still promote them manually before this boundary.
    for pid,p in tuple(academy.u21.items()):
        if p.age_on(on_date) < 21:
            continue
        academy.u21.pop(pid)
        academy.released += 1
        counts['released'] += 1
    for pid,p in tuple(academy.u17.items()):
        if p.age_on(on_date) < 18:
            continue
        academy.u17.pop(pid)
        if len(academy.u21) < MAX_U21:
            academy.u21[pid] = p
            counts['u17_to_u21'] += 1
        else:
            academy.released += 1
            counts['released'] += 1
    for pid,p in tuple(academy.u15.items()):
        if p.age_on(on_date) < 16:
            continue
        academy.u15.pop(pid)
        if len(academy.u17) < MAX_U17:
            academy.u17[pid] = _preview_to_player(p,academy,registry,on_date)
            counts['u15_to_u17'] += 1
        else:
            academy.released += 1
            counts['released'] += 1
    # U15 is not played; retained previews mature modestly across seasons.
    # These are pre-academy estimates, not match-earned CA or instant senior OVR.
    for pid,preview in tuple(academy.u15.items()):
        rng = _rng(registry.seed,academy.club_id,pid,'pre-academy-growth',on_date.year)
        room = max(0.0, preview.potential_budget-preview.initial_ovr)
        gain = min(room, max(0.0, rng.gauss(1.0,.45)))
        academy.u15[pid] = replace(preview,initial_ovr=round(preview.initial_ovr+gain,2))
    # Keep the normal annual intake size but recruit a *cohort*, not the
    # permanently truncated tail of POSITION_POOL. The previous tail-index
    # logic eventually stopped bringing in ANY U15 goalkeepers whenever
    # mature players vacated fewer than 18 places. Across a long career this
    # destroyed the only renewable source of home-grown keepers.
    #
    # At least two of twenty U15 places are earmarked for goalkeeper
    # development where available, like the opening academy cohort. These
    # are genuine age-14 academy entrants who still must progress through
    # U17/U21 and earn a senior contract; never emergency XI replacements.
    starting_count = len(academy.u15)
    incoming_count = MAX_U15 - starting_count
    needed_keep = max(0, 2 - sum(p.position is Position.GK for p in academy.u15.values()))
    keeper_places = min(needed_keep, incoming_count)
    # Distribute outfield recruiting across years and clubs without changing
    # the total number of real academy entrants or creating hidden identities.
    rotation = stable_seed(registry.seed, academy.club_id, on_date.year, 'academy-cohort') % len(POSITION_POOL)
    outfield_positions = [p for p in POSITION_POOL if p is not Position.GK]
    rotation %= len(outfield_positions)
    for idx in range(incoming_count):
        role = (Position.GK if idx < keeper_places else
                outfield_positions[(rotation + idx - keeper_places) % len(outfield_positions)])
        key = f'local-{on_date.year}-{idx}'
        rng = _rng(registry.seed,academy.club_id,key)
        preview = _talent(registry.seed,academy.club_id,key,
            registry.identities[academy.club_id].initial_tier,on_date=on_date,
            country=_country(rng),position=role,age=14,source='local-academy')
        academy.u15[preview.player_id] = preview
    # Maintain 11 available footballers for each youth category; no ghost fixtures.
    for level, minimum in (('u17',15),('u21',15)):
        roster = getattr(academy,level)
        gap = max(0,minimum-len(roster))
        for i in range(gap):
            pos = POSITION_POOL[i % len(POSITION_POOL)]
            key = f'{level}-support-{on_date.year}-{i}'
            prev = _talent(registry.seed,academy.club_id,key,
                registry.identities[academy.club_id].initial_tier,on_date=on_date,
                country=_country(_rng(registry.seed,academy.club_id,key)),position=pos,
                age=16 if level=='u17' else 18,source='academy-support')
            roster[prev.player_id] = _preview_to_player(prev,academy,registry,on_date)
    return counts


def roll_youth_season(registry, on_date: date, managed_club_id: str, *, new_label: str) -> dict:
    youth = registry.youth
    if youth is None:
        initialize_youth(registry,on_date,managed_club_id)
        return {'created':len(registry.clubs)}
    if youth.season_label == new_label:
        return {'unchanged':True}
    for cid in registry.clubs:
        if cid not in youth.academies:
            youth.academies[cid] = _initial_academy(registry,cid,on_date)
    totals = {'u15_to_u17':0,'u17_to_u21':0,'u21_to_first':0,'released':0}
    for academy in youth.academies.values():
        changes = _academy_promotions(registry,academy,on_date,managed_club_id=managed_club_id)
        for key,value in changes.items():
            totals[key] += value
    # Annual academy allocation (separate from the not-yet-implemented club
    # accounts); players' ability never depends on this UI-facing balance.
    tier = registry.identities[managed_club_id].tier
    youth.recruitment_funds += {1:200_000,2:145_000,3:105_000,4:75_000}.get(tier,75_000)
    youth.season_label = new_label
    youth.last_processed = on_date
    youth.fixtures = _fixture_calendar(registry,new_label)
    youth.season_promotion = new_label
    youth.check_unique(registry)
    return totals


def _projection(preview: YouthPreview, seed: int, quality: int = 60) -> str:
    """Imperfect, stable non-numeric report; NEVER shows exact PA."""
    rng = _rng(seed,preview.player_id,'report',quality)
    estimate = preview.potential_budget + rng.uniform(-18,18)*(1 - .65*quality/100)
    return ('Exceptional prospect' if estimate >= 90 else 'Very promising' if estimate >= 78
            else 'Promising' if estimate >= 64 else 'Developing' if estimate >= 49
            else 'Limited projection')


def _potential_band(preview: YouthPreview, seed: int, confidence: int) -> list[int]:
    """Noisy scouting interval; neither endpoint is the saved PA."""
    rng = _rng(seed,preview.id,'potential-band-v1',confidence)
    uncertainty = max(6, int(20*(1-.55*confidence/100)))
    middle = preview.potential_budget+rng.uniform(-uncertainty,uncertainty)
    return [max(1,min(99,int(middle-uncertainty))),
            max(1,min(99,int(middle+uncertainty)))]


def _academy_potential_range(player, seed: int) -> list[int] | None:
    """Imperfect academy appraisal. Saved actual potential remains private.

    The result is deterministic for a player across tabs/saves and deliberately
    wider than a point estimate. The model never sends hidden PA to the UI.
    """
    development = getattr(player, 'development', None)
    if development is None:
        return None
    rng = _rng(seed, player.id, 'academy-potential-appraisal-v1')
    centre = float(development.potential) + rng.uniform(-9, 9)
    uncertainty = 11 + rng.randint(0, 6)
    return [max(1, min(99, int(round(centre - uncertainty)))),
            max(1, min(99, int(round(centre + uncertainty))))]


def _player_data(player, on_date: date, seed: int) -> dict:
    history=player.development.history if player.development else ()
    recent=list(history)[-3:]
    delta=sum(float(row.ability_gain) for row in recent)
    return {'id':player.id,'name':player.full_name,'age':player.age_on(on_date),
            'birth_date':player.identity.birth_date.isoformat(),'country':player.identity.nationality,
            'position':player.primary_position.value,'ovr':round(reference_overall(player),1),
            'sharpness':round(player.state.match_sharpness,1),
            'projection':'On track' if delta>.05 else 'Adapting' if not recent else 'Stable',
            'development_delta':round(delta,2),
            'potential_range':_academy_potential_range(player,seed),
            'potential_confidence':'Approximate',
            'minutes':player.development.exposure.minutes if player.development else 0}


def youth_read_model(session, club_id: str | None = None) -> dict:
    registry = session._world_squads
    youth = registry.youth
    cid = club_id or session.home_club.id
    if youth is None or cid not in youth.academies:
        raise KeyError('academy not found')
    academy = youth.academies[cid]
    on_date = session.current_date
    previews = [
        {'id':p.player_id,'name':p.full_name,'age':p.age_on(on_date),
         'birth_date':p.birth_date.isoformat(),'country':p.nationality,
         'position':p.position.value,'ovr':round(p.initial_ovr,1),
         'projection':_projection(p,registry.seed),
         'potential_range':_potential_band(p,registry.seed,58),
         'upcoming':p.age_on(on_date)>=15}
        for p in academy.u15.values()
    ]
    def table(level: str):
        stats={cid:[0,0,0,0,0] for cid in youth.academies}
        for fixture in youth.fixtures.values():
            if fixture.level != level or fixture.home_goals is None:
                continue
            h,a=stats[fixture.home_club_id],stats[fixture.away_club_id]
            h[0]+=1;a[0]+=1;h[3]+=fixture.home_goals;h[4]+=fixture.away_goals
            a[3]+=fixture.away_goals;a[4]+=fixture.home_goals
            if fixture.home_goals>fixture.away_goals:h[1]+=1;a[2]+=1
            elif fixture.home_goals<fixture.away_goals:a[1]+=1;h[2]+=1
            else:h[1]+=0; a[1]+=0;h[2]+=0;a[2]+=0
        # [Played,Wins,Losses,GF,GA]; draws are played-wins-losses
        if cid not in stats:return {}
        played,wins,losses,gf,ga=stats[cid]
        return {'played':played,'wins':wins,'draws':played-wins-losses,'losses':losses,
                'goals_for':gf,'goals_against':ga,'points':wins*3+played-wins-losses}
    def league_standings(level):
        division = TIER_IDS[registry.identities[cid].tier - 1] if registry.identities[cid].tier in (1,2,3,4) else None
        if division is None:
            return []
        ids = {team for team,ident in registry.identities.items() if ident.tier==registry.identities[cid].tier}
        rows={team:{'club_id':team,'club':registry.clubs[team].name,'played':0,
                    'wins':0,'draws':0,'losses':0,'goals_for':0,'goals_against':0,'points':0}
              for team in ids}
        for fixture in youth.fixtures.values():
            if fixture.level!=level or fixture.division!=division or fixture.home_goals is None:
                continue
            home,away=rows[fixture.home_club_id],rows[fixture.away_club_id]
            for rec,gf,ga in ((home,fixture.home_goals,fixture.away_goals),
                              (away,fixture.away_goals,fixture.home_goals)):
                rec['played']+=1;rec['goals_for']+=gf;rec['goals_against']+=ga
                if gf>ga:rec['wins']+=1;rec['points']+=3
                elif gf==ga:rec['draws']+=1;rec['points']+=1
                else:rec['losses']+=1
        return sorted(rows.values(),key=lambda r:(-r['points'],
                    -(r['goals_for']-r['goals_against']),-r['goals_for'],r['club_id']))

    from football_manager.services.market_valuation import player_market_view
    data={
        'club_id':cid,'club_name':registry.clubs[cid].name,'date':on_date.isoformat(),
        'managed':cid==session.home_club.id,'season':youth.season_label,
        'u15':sorted(previews,key=lambda p:(-p['ovr'],p['name'])),
        'u17':sorted(({**_player_data(p,on_date,registry.seed), **player_market_view(registry,p,on_date)} for p in academy.u17.values()),key=lambda p:-p['ovr']),
        'u21':sorted(({**_player_data(p,on_date,registry.seed), **player_market_view(registry,p,on_date)} for p in academy.u21.values()),key=lambda p:-p['ovr']),
        'league_tables':{'u17':table('u17'),'u21':table('u21')},
        'standings':{'u17':league_standings('u17'),'u21':league_standings('u21')},
        'fixtures':{},'scouts':[],'candidates':[],
        'note':'Sub-15 is a non-playable preview. U17/U21 play automated lightweight fixtures; no manual youth matches.',
    }
    for level in ('u17','u21'):
        games=[f for f in youth.fixtures.values()
               if f.level==level and cid in (f.home_club_id,f.away_club_id)]
        games.sort(key=lambda f:f.match_date)
        next_games = [f for f in games if f.home_goals is None and f.match_date>=on_date][:3]
        latest = [f for f in games if f.home_goals is not None][-3:]
        data['fixtures'][level]=[{
            'date':f.match_date.isoformat(),
            'opponent_club_id':f.away_club_id if f.home_club_id==cid else f.home_club_id,
            'opponent':registry.clubs[f.away_club_id if f.home_club_id==cid else f.home_club_id].name,
            'home':f.home_club_id==cid,
            # Scores are displayed from the selected club's perspective.
            'score':None if f.home_goals is None else (
                f'{f.home_goals}-{f.away_goals}' if f.home_club_id==cid
                else f'{f.away_goals}-{f.home_goals}'),
        } for f in (*latest,*next_games)]
    if data['managed']:
        data['scouts']=[{'id':s.scout_id,'name':s.name or s.scout_id.replace('-',' ').title(),
            'quality':s.quality,'monthly_wage':s.monthly_wage,
            'signing_fee':s.signing_fee,'contract_until':s.contract_until.isoformat() if s.contract_until else None,
            'legacy':s.hired_on is None,
            'country':s.country,
            'position':s.position,'next_report':s.next_report.isoformat() if s.next_report else None,
            'reports_sent':s.reports_sent} for s in sorted(youth.scouts.values(),key=lambda s:s.scout_id)]
        data['scout_slots'] = MAX_HIRED_SCOUTS
        data['recruitment_funds'] = youth.recruitment_funds
        data['recruitment_spent'] = youth.recruitment_spent
        data['monthly_scout_cost'] = sum(s.monthly_wage for s in youth.scouts.values())
        data['market_offers'] = [offer for offer in scout_market(youth)
                                 if offer['name'] not in {s.name for s in youth.scouts.values()}]
        data['lost_prospects']=[{'id':key,'name':name,'date':when.isoformat(),
                                 'club':registry.clubs[cid].name if cid in registry.clubs else cid}
                                for key,(name,when,cid) in reversed(list(youth.lost_prospects.items()))][:12]
        data['candidates']=[{
            'id':p.preview.player_id,'name':p.preview.full_name,
            'age':p.preview.age_on(on_date),'country':p.preview.nationality,
            'position':p.preview.position.value,'ovr_estimate':round(p.preview.initial_ovr,1),
            'projection':_projection(p.preview,registry.seed,p.confidence),
            'confidence': 'High' if p.confidence>=80 else 'Moderate' if p.confidence>=60 else 'Low',
            'confidence_score':p.confidence,
            'potential_range': _potential_band(p.preview,registry.seed,p.confidence),
            'poaching_risk': _candidate_risk(p,on_date)[0],
            'discovered_on':p.discovered_on.isoformat(),'scout':p.scout_id,
            'watching':p.watched,'status':p.status,
        } for p in youth.candidates.values() if p.status in ('available','watching')]
    return data


YOUTH_SCOUT_CONTRACT_YEARS = (1, 2, 3, 4)


def _scout_contract_offer(session, command: dict) -> dict:
    """Staff-style negotiation using the EXISTING youth recruitment budget.

    Scouts are paid from the academy recruitment allocation, not senior club
    payroll. No alternative instant-hire path remains available.
    """
    if set(command) != {'action', 'offer_id', 'scout_id', 'monthly_wage', 'years', 'signing_fee'}:
        raise ValueError('Scout offer needs candidate, salary, term and signing fee')
    wage, years, bonus = (command['monthly_wage'], command['years'], command['signing_fee'])
    if (type(wage) is not int or type(years) is not int or type(bonus) is not int
            or not 100 <= wage <= 100_000 or years not in YOUTH_SCOUT_CONTRACT_YEARS
            or not 0 <= bonus <= 200_000):
        raise ValueError('Invalid youth scout contract terms')
    registry = session._world_squads
    youth = registry.youth
    today = session.current_date
    offer_id, scout_id = command['offer_id'], command['scout_id']
    existing = None
    if scout_id is not None:
        if offer_id is not None or not isinstance(scout_id, str):
            raise ValueError('Choose a single youth scout to renegotiate')
        existing = youth.scouts.get(scout_id)
        if existing is None or (existing.contract_until is not None and existing.contract_until < today):
            raise ValueError('Youth scout contract not available')
        demand = max(100, int(round(existing.monthly_wage * 1.09 / 100) * 100))
        identity = existing.scout_id
        name, quality = existing.name, existing.quality
    else:
        if not isinstance(offer_id, str):
            raise ValueError('Select a youth scout candidate')
        if len(youth.scouts) >= MAX_HIRED_SCOUTS:
            raise ValueError('No free youth scout slot')
        market = {m['id']:m for m in scout_market(youth)}
        offer = market.get(offer_id)
        if offer is None or any(m.name == offer['name'] for m in youth.scouts.values()):
            raise ValueError('Scout offer is no longer available')
        demand = offer['monthly_wage']
        identity = offer['id']
        name, quality = offer['name'], offer['quality']
    if youth.recruitment_funds < bonus + 2 * wage:
        raise ValueError('Insufficient academy recruitment budget for signing and two months of wages')
    variation = _rng(youth.seed, youth.managed_club_id, identity, 'scout-expectation-v1').randint(-5, 8)
    threshold = max(100, int(round(demand * (0.96 + variation/100 - (years - 1)*.014) / 100) * 100))
    # Up-front money is worth less to the scout than recurring wages.
    bonus_credit = min(bonus / (12 * years), wage * .18)
    if wage + bonus_credit < threshold:
        counter = max(100, int(round((threshold - bonus_credit + 50) / 100) * 100))
        return {'accepted':False, 'counter_monthly_wage':counter,
                'name':name, 'message':'Offer declined. The scout is seeking better terms.'}
    until = date(today.year + years, today.month, min(today.day,28))
    if existing is not None and existing.contract_until and existing.contract_until > today:
        expiry = existing.contract_until
        until = date(expiry.year + years, expiry.month, min(expiry.day,28))
    if existing is None:
        slot = next(f'scout-{i}' for i in range(1,MAX_HIRED_SCOUTS+1)
                    if f'scout-{i}' not in youth.scouts)
        new_scout = YouthScout(slot, quality, name=name, hired_on=today,
                               contract_until=until, signing_fee=bonus,monthly_wage=wage)
    else:
        slot = scout_id
        new_scout = replace(existing,monthly_wage=wage,contract_until=until,signing_fee=bonus)
    # Mutate only after all validations and the acceptance decision.
    youth.recruitment_funds -= bonus
    youth.recruitment_spent += bonus
    youth.scouts[slot] = new_scout
    return {'accepted':True,'scout_id':slot,'name':name,
            'kind':'renewal' if existing is not None else 'appointment',
            'monthly_wage':wage,'signing_fee_paid':bonus,
            'until':until.isoformat(),'message':'Scout contract accepted.'}


def youth_command(session, command: dict) -> dict:
    """Explicit UI actions; caller clones the session for atomic publication."""
    registry = session._world_squads
    youth = registry.youth
    if youth is None:
        raise ValueError('Youth academy has not been initialized')
    cid = session.home_club.id
    academy = youth.academies[cid]
    today = session.current_date
    action=command.get('action')
    if action=='hire_scout':
        raise ValueError('Youth scout appointments require a negotiated contract offer')
    if action=='offer_scout':
        return _scout_contract_offer(session, command)
    if action=='fire_scout':
        scout=youth.scouts.get(command.get('scout_id'))
        if scout is None: raise ValueError('Unknown scout')
        exit_fee=scout.monthly_wage
        if youth.recruitment_funds < exit_fee:
            raise ValueError('Insufficient recruitment funds for contract termination')
        youth.recruitment_funds-=exit_fee
        youth.recruitment_spent+=exit_fee
        del youth.scouts[scout.scout_id]
        return {'released_scout':True,'scout_id':scout.scout_id,'termination_fee':exit_fee}
    if action=='assign_scout':
        scout=youth.scouts.get(command.get('scout_id'))
        if scout is None:raise ValueError('Unknown scout')
        country, position=command.get('country'),command.get('position')
        if country not in COUNTRIES or position not in PROFILES:
            raise ValueError('Unsupported scout region or positional focus')
        scout.country,scout.position=country,position
        scout.started_on=today
        scout.next_report=_quarter_after(today)
        return {'assigned':True,'scout_id':scout.scout_id,'next_report':scout.next_report.isoformat()}
    if action in ('watch','dismiss'):
        raise ValueError('Youth prospects are followed automatically; only Sign to U17 is available')
    if action=='sign':
        prospect=youth.candidates.get(command.get('player_id'))
        if prospect is None or prospect.status not in ('available','watching'):
            raise ValueError('Candidate unavailable')
        # Scouting generates players; signing makes one persistent academy Player.
        if prospect.preview.age_on(today) > 17:
            raise ValueError('Prospect is over the U17 age limit')
        target='u17'
        roster=academy.u17
        cap=MAX_U17
        if len(roster)>=cap:
            raise ValueError('Youth squad is full; release or promote a player first')
        p=_preview_to_player(prospect.preview,academy,registry,today)
        roster[p.id]=p
        del youth.candidates[p.id]
        youth.check_unique(registry)
        from football_manager.services.club_economy import sync_financial_rosters
        sync_financial_rosters(registry,today)
        return {'signed':True,'player_id':p.id,'team':target}
    if action in ('move','release'):
        pid=command.get('player_id');target=command.get('target')
        if not isinstance(pid,str):raise ValueError('Player ID required')
        roster_name=next((lv for lv in ('u17','u21') if pid in getattr(academy,lv)),None)
        if roster_name is None and session.home_club.squad.contains(pid):
            roster_name='first'
        if roster_name is None:
            raise ValueError('Only the managed-club squad or its youth teams may be changed')
        if action=='release':
            if roster_name=='first':raise ValueError('Release from the first team is not a youth action')
            current=getattr(academy,roster_name)
            if len(current)<=12 or (current[pid].primary_position is Position.GK and
                sum(p.primary_position is Position.GK for p in current.values())<=1):
                raise ValueError('Keep 12 players and a goalkeeper in each youth squad')
            current.pop(pid)
            academy.released+=1
            from football_manager.services.club_economy import sync_financial_rosters
            sync_financial_rosters(registry,today)
            return {'released':True,'player_id':pid}
        if target not in ('u17','u21','first') or target==roster_name:
            raise ValueError('Invalid destination')
        player=(session.home_club.squad.get(pid) if roster_name=='first'
                else getattr(academy,roster_name)[pid])
        age=player.age_on(today)
        if target=='u17' and age>17:raise ValueError('Over age for U17')
        if target=='u21' and age>21:raise ValueError('Over age for U21')
        if target!='first' and len(getattr(academy,target)) >= (MAX_U17 if target=='u17' else MAX_U21):
            raise ValueError('Destination youth roster full')
        if target=='first' and age<15:raise ValueError('Player too young')
        if roster_name=='first':
            assigned={entry.player.id for entry in session.home_lineup.starters}
            assigned.update(p.id for p in session.home_lineup.bench)
            if pid in assigned:raise ValueError('Remove player from starting lineup and bench before moving him')
            if len(session.home_club.squad)<=18:raise ValueError('First team needs at least 18 players')
            session.home_club.squad.remove(pid)
        else:
            getattr(academy,roster_name).pop(pid)
        if target=='first':
            session.home_club.squad.add(player)
            youth.promoted_to_first[pid]=cid
            # No first-team match = reduced sharpness, not an instant CA decrease.
            player.state.match_sharpness=min(player.state.match_sharpness,72.0)
        else:
            getattr(academy,target)[pid]=player
        from football_manager.services.dressing_room import sync_roster
        sync_roster(session.dressing_room,session.home_club.squad.players)
        youth.check_unique(registry)
        from football_manager.services.club_economy import sync_financial_rosters
        sync_financial_rosters(registry,today)
        return {'moved':True,'player_id':pid,'team':target}
    raise ValueError('Unknown youth command')
