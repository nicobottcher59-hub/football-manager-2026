"""TS-24.2 fictional 92-club financial model, salaries and contracts.

The same wage schedule, renewal checks and budget formulas serve every
club. Loan payroll sharing and free-agent release are integrated in TS-24.6.
"""
from __future__ import annotations

from dataclasses import replace
from datetime import date, timedelta
from hashlib import sha256
from math import exp, log
from calendar import monthrange

from football_manager.domain.club_economy import (
    ClubFinances, FinanceMonth, PlayerContract, WagePeriod,
)
from football_manager.domain.market_valuation import perceived_upside
from football_manager.services.market_valuation import format_gbp

WAGE_ANCHORS = (
    (35, 150), (40, 230), (45, 330), (50, 550), (55, 900),
    (60, 1_600), (65, 4_000), (70, 8_500), (75, 26_000),
    (80, 65_000), (85, 132_000), (90, 270_000),
    (95, 410_000), (98, 550_000),
)
# Board-size floors and initial discretionary transfer allocations.
MINIMUM_WAGE_BUDGET = {0: 9_000, 1: 600_000, 2: 150_000, 3: 35_000, 4: 15_000}
DIVISION_BASE_MONTHLY_INCOME = {0: 130_000, 1: 5_500_000, 2: 1_050_000, 3: 310_000, 4: 160_000}
INITIAL_TRANSFER_ALLOCATION = {0: 30_000, 1: 27_000_000, 2: 3_500_000, 3: 375_000, 4: 85_000}
MIN_CASH_RESERVE = {0: 400_000, 1: 26_000_000, 2: 4_000_000, 3: 1_300_000, 4: 450_000}


def _unit(seed: int, *keys: str) -> float:
    raw = sha256((':'.join(map(str, ('ts24-2', seed, *keys)))).encode()).digest()
    return int.from_bytes(raw[:8], 'big') / (2**64 - 1)


def _wage_base(ovr: float) -> float:
    if ovr <= WAGE_ANCHORS[0][0]:
        return float(WAGE_ANCHORS[0][1])
    for (left, amount), (right, other) in zip(WAGE_ANCHORS, WAGE_ANCHORS[1:]):
        if ovr <= right:
            step = (ovr - left) / (right - left)
            return exp(log(amount) + (log(other) - log(amount)) * step)
    return float(WAGE_ANCHORS[-1][1])


def _round_wage(amount: float) -> int:
    # GBP/week; integer money and non-cliff price curve.
    step = 25 if amount < 2_000 else 100 if amount < 20_000 else 500 if amount < 100_000 else 1_000
    return max(75, min(1_500_000, int((amount + step / 2) // step * step)))


def wage_expectation(player, on_date: date, seed: int, *, role: str = 'regular') -> int:
    """General professional demand; a separate number from a signed wage.

    Uses an imperfect upside estimate. No asking wage is extracted from exact
    PA, and temporary fatigue is not an input.
    """
    from football_manager.domain.player_development import current_ability
    if role not in ('star','important','regular','rotation','backup'):
        raise ValueError('invalid contract role')
    age = player.age_on(on_date)
    age_factor = (.64 if age <= 18 else .78 if age <= 20 else .88 if age <= 22 else
                  1.0 if age <= 32 else .94 if age <= 35 else .86)
    headroom = max(0.0, player.development.potential-current_ability(player)) if player.development else 0.
    upside = perceived_upside(seed, player.id, headroom)
    potential_factor = 1 + min(.42, upside * .018) if age <= 22 else 1.0
    role_factor = {'star': 1.12,'important': 1.06,'regular': 1.,'rotation': .91,'backup': .85}[role]
    return _round_wage(_wage_base(player.overall_rating) * age_factor * potential_factor * role_factor)


def _date_plus_months(day: date, months: int) -> date:
    year = day.year + (day.month-1+months)//12
    month = (day.month-1+months)%12+1
    return date(year, month, min(day.day, monthrange(year, month)[1]))


def _role_for_rank(rank: int, total: int) -> str:
    percent = rank / max(1,total)
    return 'star' if percent < .09 else 'important' if percent < .32 else 'regular' if percent < .64 else 'rotation' if percent < .86 else 'backup'


def _initial_contract(registry, club_id: str, player, on_date: date, role: str, *, youth: bool) -> PlayerContract:
    seed = registry.seed
    if youth:
        # Academy members receive a small retained youth agreement, not a
        # professional-scale offer driven by speculative future PA.
        year = 2 if player.age_on(on_date) <= 17 else 1
        wage = _round_wage(100 + max(0, player.overall_rating-36)*18 + _unit(seed,player.id,'youth-wage')*140)
        wage = min(1_500, wage)
        return PlayerContract(player.id,club_id,on_date,_date_plus_months(on_date,12*year),wage,
                              'backup','academy')
    fair = wage_expectation(player,on_date,seed,role=role)
    age = player.age_on(on_date)
    # Older signings are cheaper than their current new-contract demand in
    # some cases; breakout youngsters may have signed at old rates.
    factor = .78 + .38*_unit(seed,player.id,'contract-wage')
    if age <= 23:
        factor *= .84
    wage = _round_wage(fair*factor)
    months = 12*(1+int(4*_unit(seed,player.id,'contract-term')))
    if age >= 35:
        months = min(24,months)
    return PlayerContract(player.id,club_id,on_date,_date_plus_months(on_date,months),wage,role)


def _rosters(registry):
    """One canonical membership entry per player, including U17/U21."""
    for cid,club in registry.clubs.items():
        ordered = sorted(club.squad.players, key=lambda p:(-p.overall_rating,p.id))
        for rank,player in enumerate(ordered):
            yield cid,player,False,_role_for_rank(rank,len(ordered))
    if registry.youth is not None:
        for cid,academy in registry.youth.academies.items():
            for roster in (academy.u17,academy.u21):
                for player in roster.values():
                    yield cid,player,True,'backup'


def weekly_payroll(registry, club_id: str) -> int:
    base=sum(c.weekly_wage_gbp for c in registry.contracts.values() if c.club_id==club_id)
    from football_manager.services.loan_market import loan_payroll
    return loan_payroll(registry,club_id,base)


def _operating_overhead(registry, club_id: str, monthly_revenue: int) -> int:
    """Non-player running costs (travel, facilities, staff and academies).

    A Championship or League Two club does not have a Premier League's cost
    footprint. Retain persistent club-to-club variation, not a cash-based tax.
    """
    tier=registry.identities[club_id].tier
    baseline={0:.17,1:.35,2:.28,3:.21,4:.14}[tier]
    return int(monthly_revenue*(baseline+.09*_unit(registry.seed,club_id,'club-costs')))


def _sustainable_wage_budget(registry, club_id: str, monthly_revenue: int,
                             operations: int, existing_payroll: int) -> int:
    """Seasonal board envelope based on genuine recurring income, not only
    last year's existing wage bill. Does not guarantee solvency after demotion.
    """
    tier = registry.identities[club_id].tier
    available_weekly = max(0, (monthly_revenue - operations)*12/52)
    affordable = available_weekly*(.75 + .08*_unit(registry.seed,club_id,'headroom'))
    # Existing contracts survive relegation; the board can still face losses.
    return max(MINIMUM_WAGE_BUDGET[tier], int(existing_payroll*1.08), int(affordable))


def _club_finances(registry, club_id: str) -> ClubFinances:
    tier = registry.identities[club_id].tier
    payroll = weekly_payroll(registry,club_id)
    # Club-specific standing survives a change of division, is symmetric and
    # does not change after a good or poor match.
    stature = .78 + .50*_unit(registry.seed,club_id,'club-stature')
    minimum = MINIMUM_WAGE_BUDGET[tier]
    wage_budget = max(minimum, int(payroll*(1.16+.10*_unit(registry.seed,club_id,'headroom'))))
    # Revenue is estimated ONCE on initialization; raising wages later never
    # magically raises gate receipts. New divisions rebase revenue each season.
    monthly_income = max(int(DIVISION_BASE_MONTHLY_INCOME[tier]*stature),int(payroll*52/12*1.32))
    operating = _operating_overhead(registry, club_id, monthly_income)
    cash = max(int(MIN_CASH_RESERVE[tier]*stature),int((payroll*52/12+operating)*3.2))
    allocation = min(int(cash*.42),int(INITIAL_TRANSFER_ALLOCATION[tier]*stature))
    return ClubFinances(club_id,cash,allocation,wage_budget,monthly_income,operating)


def initialize_finances(registry, on_date: date) -> None:
    """Bootstrap new careers or a v12 migration, without backdating payroll."""
    if registry.finance_review_on is not None:
        return
    if registry.contracts or registry.club_finances or registry.finance_started_on is not None:
        raise ValueError('partial economic ledger cannot be initialized')
    membership: set[str] = set()
    for club_id,player,youth,role in _rosters(registry):
        if player.id in membership:
            raise ValueError('duplicate contract holder')
        membership.add(player.id)
        registry.contracts[player.id] = _initial_contract(registry,club_id,player,on_date,role,youth=youth)
    for cid in registry.clubs:
        registry.club_finances[cid] = _club_finances(registry,cid)
    registry.finance_review_on = on_date.replace(day=1)
    registry.finance_started_on = on_date


def _replace_contract(registry, contract: PlayerContract, *, world=None) -> None:
    if world is None:
        registry.contracts[contract.player_id] = contract
    else:
        world._put(registry.contracts,contract.player_id,contract)


def sync_financial_rosters(registry, on_date: date, *, world=None) -> None:
    """Create terms for genuine new entrants, and prune departed/retired IDs.

    Academy -> first-team promotions are an actual new professional agreement;
    first-team -> reserves cannot silently lower the existing contract wage.
    """
    active: set[str] = set()
    for club_id,player,youth,role in _rosters(registry):
        active.add(player.id)
        current = registry.contracts.get(player.id)
        loan = next((l for l in registry.loans.values() if l.player_id==player.id and l.status=='active'),None)
        if loan is not None and loan.borrower_id==club_id and current is not None:
            continue  # Temporary registration; parent's contract remains intact.
        if current is None or current.club_id != club_id:
            _replace_contract(registry,_initial_contract(registry,club_id,player,on_date,role,youth=youth),world=world)
        elif not youth and current.kind == 'academy':
            # Promotion is a signed entry-level professional deal. Preserve
            # accrued past wages so the month boundary cannot undercharge.
            history = current.history
            if current.signed_on < on_date:
                history += (WagePeriod(current.signed_on,on_date-timedelta(days=1),current.weekly_wage_gbp),)
            target = max(current.weekly_wage_gbp,wage_expectation(player,on_date,registry.seed,role='rotation')//2)
            upgraded = PlayerContract(player.id,club_id,on_date,_date_plus_months(on_date,24),_round_wage(target),
                                      'rotation','professional',history)
            _replace_contract(registry,upgraded,world=world)
    # New clubs can enter from the National League in later seasons. They
    # need an independently funded account just like the opening 92 clubs.
    for cid in registry.clubs:
        if cid not in registry.club_finances:
            account=_club_finances(registry,cid)
            if world is None:
                registry.club_finances[cid]=account
            else:
                world._put(registry.club_finances,cid,account)
    for pid in set(registry.contracts)-active:
        if world is not None:
            old=registry.contracts[pid]
            journal=world._active_journal
            journal.undo_callbacks.setdefault(('econ-prune',id(registry),pid),
                lambda key=pid,val=old: registry.contracts.__setitem__(key,val))
        del registry.contracts[pid]


def _month_wage(contract: PlayerContract, start: date, end: date) -> int:
    total = 0
    for period in (*contract.history, WagePeriod(contract.signed_on,end,contract.weekly_wage_gbp)):
        lo = max(start,period.starts_on)
        hi = min(end,period.ends_on)
        if lo <= hi:
            # Out-of-contract players stay on paid interim retention while the
            # Expiry handling is performed by the TS-24.6 free-agent review.
            total += round(period.weekly_gbp*(hi-lo).days/7 + period.weekly_gbp/7)
    return total


def auto_renew_ai_contracts(world, on_date: date, managed_club_id: str | None = None) -> int:
    """AI clubs renew expiring employees when the SAME demand/budget rules fit.

    An unaffordable deal does not create free cash or an unpaid player. Until
    the monthly free-agent review happens, that employee stays on paid interim
    retention at the old weekly wage (visible in the contract status).
    """
    registry=world.football_world
    if registry is None or world._active_journal is None:
        raise RuntimeError('AI renewal review needs world transaction')
    renewed=0
    for cid,club in registry.clubs.items():
        if cid==managed_club_id:
            continue
        account=registry.club_finances[cid]
        if account.cash_gbp<0:
            continue
        for player in sorted(club.squad.players,key=lambda p:p.id):
            # The player's confirmed retirement cannot be reversed by the
            # club's need for another season of cheap cover.
            if (player.aging is not None and
                    player.aging.retirement_status in ('requested','deferred')):
                continue
            contract=registry.contracts.get(player.id)
            # Loan registration is NOT employment: only the contracting
            # parent may renew a player. The borrower must never overwrite
            # PlayerContract.club_id during a monthly review.
            if (contract is None or contract.kind!='professional'
                    or contract.club_id != cid):
                continue
            days_left=(contract.expires_on-on_date).days
            if days_left>120:
                continue
            years=1 if player.age_on(on_date)>=35 else 2
            try:
                terms=quote_renewal(registry,player,contract,on_date,years)
            except ValueError:
                continue
            wage=terms['minimum_weekly_gbp']
            next_payroll=weekly_payroll(registry,cid)-contract.weekly_wage_gbp+wage
            if next_payroll>account.wage_budget_weekly_gbp:
                continue
            # TS-24.9: do not recommit an insolvent club to a costly deal.
            # Honour binding contracts, but let unaffordable renewals expire
            # under the existing positional safeguards. No debt is written off.
            monthly_gap=max(0,round(next_payroll*52/12)+account.recurring_operations_gbp
                            -account.recurring_income_gbp)
            if monthly_gap and account.cash_gbp < monthly_gap*6:
                continue
            history=contract.history
            if contract.signed_on < on_date:
                history=(*history,WagePeriod(contract.signed_on,on_date-timedelta(days=1),contract.weekly_wage_gbp))
            updated=PlayerContract(contract.player_id,cid,on_date,_date_plus_months(on_date,years*12),
                                   wage,contract.role,'professional',history,on_date)
            updated.validate()
            world._put(registry.contracts,player.id,updated)
            renewed+=1
    return renewed


def review_finances(world, boundary: date) -> int:
    """Close each elapsed calendar month inside WorldSeasonRunner's journal."""
    registry=world.football_world
    if registry is None or registry.finance_review_on is None or boundary.replace(day=1) <= registry.finance_review_on:
        return 0
    if world._active_journal is None:
        raise RuntimeError('financial monthly review requires world transaction')
    previous=registry.finance_review_on
    world._active_journal.undo_callbacks.setdefault(
        ('finance-clock',id(registry)), lambda: setattr(registry,'finance_review_on',previous))
    count=0
    while registry.finance_review_on < boundary.replace(day=1):
        month=registry.finance_review_on
        period_end=_date_plus_months(month,1)-timedelta(days=1)
        covered_from=max(month,registry.finance_started_on)
        covered_days=max(0,(period_end-covered_from).days+1)
        month_days=(period_end-month).days+1
        from football_manager.services.loan_market import loan_monthly_adjustments
        wage_shares=loan_monthly_adjustments(registry,covered_from,period_end)
        from football_manager.services.contract_incentives import due_contract_bonuses
        bonus_expenses=due_contract_bonuses(world,period_end)
        for cid,account in list(registry.club_finances.items()):
            wages=sum(_month_wage(c,covered_from,period_end) for c in registry.contracts.values() if c.club_id==cid)
            wages+=wage_shares.get(cid,0)
            from football_manager.services.club_support import active_staff
            support=registry.club_support.get(cid)
            staff_monthly=0
            if support is not None:
                # Staff contracts expire without charging wages after expiry.
                staff_monthly=sum(round(m.wage_weekly_gbp * 52 / 365 *
                                        max(0, (min(period_end, m.contract_until) - max(covered_from, m.hired_on)).days + 1))
                                  for m in support.members.values() if m.contract_until >= covered_from)
            income=round(account.recurring_income_gbp*covered_days/month_days)
            # A fraction of legacy overhead already represented unnamed staff.
            # Replace that allowance with explicit staff pay, not a double charge.
            nominal_ops=round(account.recurring_operations_gbp*covered_days/month_days)
            preexisting_staff_allowance = (round(support.baseline_weekly_gbp * 52 / 365 * covered_days)
                                           if support is not None else 0)
            costs=nominal_ops-min(round(nominal_ops * .12), preexisting_staff_allowance) + bonus_expenses.get(cid,0)
            wages+=staff_monthly
            new_cash=account.cash_gbp+income-wages-costs
            # Liquid budget cannot be spent if it exceeds current cash.
            new_budget=min(account.transfer_budget_gbp,max(0,int(max(0,new_cash)*.85)))
            statement=FinanceMonth(month,income,wages,costs,new_cash)
            amended=replace(account,cash_gbp=new_cash,transfer_budget_gbp=new_budget,
                season_income_gbp=account.season_income_gbp+income,
                season_wages_gbp=account.season_wages_gbp+wages,
                season_operations_gbp=account.season_operations_gbp+costs,
                history=(*account.history[-23:],statement))
            world._put(registry.club_finances,cid,amended)
            count+=1
        # Contract extensions take effect on the NEW month, never before
        # paying the period just closed. Managed offers remain the user's call.
        from football_manager.services.club_support import auto_extend_ai_staff
        auto_extend_ai_staff(world, _date_plus_months(month, 1),
                             managed_club_id=(registry.youth.managed_club_id if registry.youth else None))
        auto_renew_ai_contracts(world,_date_plus_months(month,1),
                                managed_club_id=(registry.youth.managed_club_id if registry.youth else None))
        from football_manager.services.loan_market import review_loan_month
        review_loan_month(world,_date_plus_months(month,1))
        registry.finance_review_on=_date_plus_months(month,1)
    sync_financial_rosters(registry,boundary,world=world)
    return count


def rebase_finances_for_new_season(registry, on_date: date) -> None:
    """Realign allocations to promotions/relegations, preserving bank cash."""
    sync_financial_rosters(registry,on_date)
    for cid,account in list(registry.club_finances.items()):
        tier=registry.identities[cid].tier
        payroll=weekly_payroll(registry,cid)
        stature=.78+.50*_unit(registry.seed,cid,'club-stature')
        # Seasonal income changes with tier/stature, NEVER because the team
        # signs expensive contracts. This allows genuine post-relegation risk.
        revenue=int(DIVISION_BASE_MONTHLY_INCOME[tier]*stature)
        operations=_operating_overhead(registry,cid,revenue)
        wage_budget=_sustainable_wage_budget(registry,cid,revenue,operations,payroll)
        discretionary=min(max(0,int(max(0,account.cash_gbp)*.40)),
                          int(INITIAL_TRANSFER_ALLOCATION[tier]*stature))
        registry.club_finances[cid]=replace(account,wage_budget_weekly_gbp=wage_budget,
            transfer_budget_gbp=discretionary,recurring_income_gbp=revenue,
            recurring_operations_gbp=operations,season_income_gbp=0,season_wages_gbp=0,
            season_operations_gbp=0)


def quote_renewal(registry, player, contract: PlayerContract, on_date: date, years: int) -> dict:
    # A signed declaration of retirement is the player's own decision, not
    # something the club can overrule by offering another contract.
    if (player.aging is not None and
            player.aging.retirement_status in ('requested', 'deferred', 'retired')):
        raise ValueError('Player has already decided to retire')
    if type(years) is not int or not 1 <= years <= 5:
        raise ValueError('Contract duration must be 1 to 5 years')
    age=player.age_on(on_date)
    if age>=35 and years>2 or age>=32 and years>3:
        raise ValueError('Player does not accept a contract of this duration at their age')
    if contract.renewed_on is not None and (on_date-contract.renewed_on).days < 90:
        raise ValueError('Contract was renewed recently; wait before offering again')
    if contract.kind=='academy':
        raise ValueError('Youth agreements are not negotiated here; promote the player first')
    # Existing high-earners are unlikely to accept an unreasonable salary cut.
    role=contract.role
    fair=wage_expectation(player,on_date,registry.seed,role=role)
    demand=_round_wage(max(fair,contract.weekly_wage_gbp*.94))
    return {'minimum_weekly_gbp': demand, 'maximum_years': 2 if age>=35 else 3 if age>=32 else 5,
            'current_weekly_gbp':contract.weekly_wage_gbp,
            'estimated_additional_weekly_gbp':max(0,demand-contract.weekly_wage_gbp)}


def renew_contract(session, command: dict) -> dict:
    """Manager decision; caller clones the session before publishing."""
    registry=session._world_squads
    pid=command.get('player_id')
    years=command.get('years')
    offer=command.get('weekly_wage_gbp')
    if not isinstance(pid,str) or not session.home_club.squad.contains(pid):
        raise ValueError('Player is not in your first-team squad')
    if type(offer) is not int or not 75 <= offer <= 1_500_000:
        raise ValueError('Invalid weekly wage')
    current=registry.contracts.get(pid)
    if current is None or current.club_id!=session.home_club.id:
        raise ValueError('Player has no registered current agreement')
    demand=quote_renewal(registry,session.home_club.squad.get(pid),current,session.current_date,years)
    if offer<demand['minimum_weekly_gbp']:
        raise ValueError('Player rejects the salary: offer is below the current expectation')
    account=registry.club_finances[session.home_club.id]
    after=weekly_payroll(registry,session.home_club.id)-current.weekly_wage_gbp+offer
    if after>account.wage_budget_weekly_gbp:
        raise ValueError('Contract would exceed the board wage budget')
    if account.cash_gbp < 0:
        raise ValueError('Club has no positive operating cash for new commitments')
    history=current.history
    if current.signed_on < session.current_date:
        history=(*history,WagePeriod(current.signed_on,session.current_date-timedelta(days=1),current.weekly_wage_gbp))
    updated=PlayerContract(pid,session.home_club.id,session.current_date,
                           _date_plus_months(session.current_date,12*years),offer,
                           current.role,'professional',history,session.current_date)
    updated.validate()
    registry.contracts[pid]=updated
    return {'renewed':True,'player_id':pid,'wage_weekly_gbp':offer,
            'expires_on':updated.expires_on.isoformat(),'wage_budget_remaining_gbp':account.wage_budget_weekly_gbp-after}


def contract_view(registry, player_id: str, as_of: date) -> dict | None:
    contract=registry.contracts.get(player_id)
    if contract is None:
        return None
    from football_manager.services.loan_market import active_loan
    loan=active_loan(registry,player_id)
    return {'weekly_wage_gbp':contract.weekly_wage_gbp,
            'weekly_wage':'£'+f'{contract.weekly_wage_gbp:,}',
            'expires_on':contract.expires_on.isoformat(),
            'signed_on':contract.signed_on.isoformat(),
            'role':contract.role,'kind':contract.kind,
            'loan': {'parent_id':loan.parent_id,'borrower_id':loan.borrower_id,'until':loan.ends_on.isoformat(),'borrower_wage_percent':loan.borrower_wage_percent} if loan else None,
            'status': 'out_of_contract_retained' if as_of > contract.expires_on else 'active',
            'note': ('Contract has expired; pending month-end review for possible release.'
                     if as_of > contract.expires_on else 'Registered contract; weekly wage remains fixed until renewal.')}


def financial_outlook(registry, cid: str) -> dict:
    """Read-only cash sustainability signals, not a solvency pass/fail quota.

    A loss-making club is not automatically distressed: an adequate reserve
    can finance sporting investments. Only persistent negative cash *with*
    continued operating losses is classed as critical. No bank account or
    player contract is changed by this assessment.
    """
    account=registry.club_finances[cid]
    payroll=weekly_payroll(registry,cid)
    support=registry.club_support.get(cid)
    staff_weekly=sum(m.wage_weekly_gbp for m in support.members.values() if m.contract_until >= registry.finance_review_on) if support else 0
    initial_allowance=min(round(account.recurring_operations_gbp * .12),
                          round(support.baseline_weekly_gbp*52/12)) if support else 0
    net_month=(account.recurring_income_gbp - account.recurring_operations_gbp + initial_allowance
               - round((payroll+staff_weekly)*52/12))
    cash=account.cash_gbp
    six_month_projection=cash+6*net_month
    history=account.history[-6:]
    negative_months=sum(statement.closing_cash_gbp<0 for statement in history)
    if cash<0 and net_month<0 and negative_months>=4:
        level='critical'
    elif cash<0 or (six_month_projection<0 and net_month<0):
        level='pressure'
    elif net_month<0:
        level='investment_or_deficit'
    else:
        level='stable'
    return {'level':level,'projected_monthly_operating_net_gbp':net_month,
            'projected_six_month_cash_gbp':six_month_projection,
            'negative_cash_months_last_six':negative_months,
            'actual_operating_net_last_six_gbp':sum(
                m.income_gbp-m.wages_gbp-m.operations_gbp for m in history),
            'note':'Losses and imperfect decisions are allowed; this is a diagnostic, not a financial bailout.'}


def staff_budget_weekly(registry, club_id: str) -> int:
    """Deterministic independent board limit for staff salary commitments.

    Based only on the saved season's recurring revenue, original staffing
    baseline and division, never the wages of new hires. Thus a new hire cannot
    increase their own budget. Relegation/promotion rebases this limit through
    the existing annual club-economy process; no new save field is required.
    Existing contracts survive a reduction, but increases over the limit are
    rejected by staff_command.
    """
    account = registry.club_finances[club_id]
    support = registry.club_support.get(club_id)
    baseline = support.baseline_weekly_gbp if support else 0
    tier = registry.identities[club_id].tier
    floor = {0: 900, 1: 18000, 2: 5500, 3: 2500, 4: 1400}.get(tier, 1400)
    # Recurring revenue is not changed by signing an employee. Keep the
    # independent envelope proportional to the real economic size of the club.
    from_income = round(account.recurring_income_gbp * 12 / 52 *
                        (.018 + .004 * _unit(registry.seed, club_id, 'staff-policy')))
    return max(floor, round(baseline * 1.85), from_income)


def finances_read_model(session, club_id: str | None = None) -> dict:
    registry=session._world_squads
    cid=club_id or session.home_club.id
    if cid not in registry.club_finances:
        raise KeyError('Unknown club finances')
    account=registry.club_finances[cid]
    payroll=weekly_payroll(registry,cid)
    if registry.transfer_last_review_on is not None:
        from football_manager.services.transfer_negotiation import _availability
        available_transfer_funds = _availability(registry,cid,session.current_date)
    else:
        available_transfer_funds = account.transfer_budget_gbp
    players={p.id:p for p in registry.clubs[cid].squad.players}
    # Only registered professional first-team deals belong to this contracts
    # table; academy wages are included in payroll and visible as a summary.
    rows=[]
    for pid,player in players.items():
        contract=registry.contracts.get(pid)
        if contract is None:
            continue
        details=contract_view(registry,pid,session.current_date)
        # Temporary registrations belong to the lending club, not the
        # borrower: the borrower cannot offer a contract extension.
        if contract.club_id!=cid:
            renew=None
        else:
            try:
                info=quote_renewal(registry,player,contract,session.current_date,2)
                from football_manager.services.contract_bargaining import public_wage_range
                renew={'wage_range':public_wage_range(info['minimum_weekly_gbp']),
                       'maximum_years':info['maximum_years']}
            except ValueError:
                renew=None
        rows.append({'player_id':pid,'name':player.full_name,'position':player.primary_position.value,
                     'age':player.age_on(session.current_date),'ovr':round(player.overall_rating,1),
                     **details,'renewal': renew})
    rows.sort(key=lambda p:(p['expires_on'],p['name']))
    support=registry.club_support.get(cid)
    staff_weekly=sum(m.wage_weekly_gbp for m in support.members.values() if m.contract_until>=session.current_date) if support else 0
    staff_limit=staff_budget_weekly(registry,cid)
    staff_rows=sorted(({
        'member_id':m.member_id,'name':m.name,'role':m.role,'quality':m.quality,
        'weekly_wage_gbp':m.wage_weekly_gbp,
        'expires_on':m.contract_until.isoformat()}
        for m in support.members.values() if m.contract_until >= session.current_date),
        key=lambda m:(-m['weekly_wage_gbp'],m['name'])) if support else []
    loan_fees_paid=sum(loan.loan_fee_gbp for loan in registry.loans.values()
                       if loan.borrower_id == cid and loan.started_on <= session.current_date)
    loan_fees_received=sum(loan.loan_fee_gbp for loan in registry.loans.values()
                           if loan.parent_id == cid and loan.started_on <= session.current_date)
    initial_allowance=min(round(account.recurring_operations_gbp*.12),
                          round(support.baseline_weekly_gbp*52/12)) if support else 0
    from football_manager.services.transfer_installments import finance_summary
    return {'schema_version':1,'source':'ts24-2-persistent-club-economy',
            'installment_finance':finance_summary(registry,cid,session.current_date),
            'club_id':cid,'club':registry.clubs[cid].name,'managed':cid==session.home_club.id,
            'tier':registry.identities[cid].tier,'date':session.current_date.isoformat(),
            'season':f"{session.current_date.year if session.current_date.month>=7 else session.current_date.year-1}/{str((session.current_date.year if session.current_date.month>=7 else session.current_date.year-1)+1)[-2:]}",
            'as_of_month':registry.finance_review_on.isoformat(),
            'cash_gbp':account.cash_gbp,'cash':format_gbp(account.cash_gbp) if account.cash_gbp>=0 else '-'+format_gbp(-account.cash_gbp),
            'transfer_budget_gbp':account.transfer_budget_gbp,
            'transfer_available_gbp':available_transfer_funds,
            'transfer_reserved_gbp':max(0,account.transfer_budget_gbp-available_transfer_funds),
            'transfer_budget':format_gbp(account.transfer_budget_gbp),
            'wage_budget_weekly_gbp':account.wage_budget_weekly_gbp,
            'weekly_payroll_gbp':payroll,
            'wage_headroom_weekly_gbp':account.wage_budget_weekly_gbp-payroll,
            'monthly_income_gbp':account.recurring_income_gbp,
            'monthly_operating_costs_gbp':account.recurring_operations_gbp-initial_allowance,
            'forecast_monthly_wages_gbp':round((payroll+staff_weekly)*52/12),
            'staff_weekly_wages_gbp':staff_weekly,
            'staff_budget_weekly_gbp':staff_limit,
            'staff_headroom_weekly_gbp':staff_limit-staff_weekly,
            'staff_contracts':staff_rows,
            'loan_fees_paid_gbp':loan_fees_paid,
            'loan_fees_received_gbp':loan_fees_received,
            'staff_baseline_allowance_gbp':initial_allowance,
            'season_income_gbp':account.season_income_gbp,
            'season_wages_gbp':account.season_wages_gbp,
            'season_operations_gbp':account.season_operations_gbp,
            'financial_outlook':financial_outlook(registry,cid),
            'academy_weekly_wages_gbp':sum(c.weekly_wage_gbp for c in registry.contracts.values()
                if c.club_id==cid and c.kind=='academy'),
            'contracts':rows,
            'history':[{'period':m.period_start.isoformat(),'income_gbp':m.income_gbp,
                        'wages_gbp':m.wages_gbp,'operations_gbp':m.operations_gbp,
                        'net_gbp':m.income_gbp-m.wages_gbp-m.operations_gbp,
                        'closing_cash_gbp':m.closing_cash_gbp}
                       for m in reversed(account.history[-12:])],
            'note':'Provisional fictional revenue and budgets, calibrated to the squad and division. Completed transfers debit fees immediately; loan salary contributions are shared between clubs. Youth scout allocation remains separate.',
            'contracts_note':'Professional contracts may expire and eligible players join the free-agent market at the monthly review. Borrowed players keep contracts with their parent club; academy players can be promoted.'}
