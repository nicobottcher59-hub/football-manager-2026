"""TS-FIX-03: shared, deterministic player-agent bargaining for purchases and renewals.

Only statements actually communicated by the agent are returned to the UI.
The internal acceptance score, salary floor and personality weights stay server-side.
"""
from __future__ import annotations

from dataclasses import replace
from football_manager.domain.transfer_personal import ContractBonus, PersonalTerms
from football_manager.services.club_economy import _round_wage

ROLES = ('star','important','regular','rotation','backup')
DEFENSIVE_POSITIONS = {'GK', 'CB', 'LCB', 'RCB', 'LB', 'RB', 'LWB', 'RWB'}


def validate_player_bonuses(player, terms: PersonalTerms) -> None:
    if (any(item.kind == 'clean_sheets' for item in terms.bonuses)
            and player.primary_position.value not in DEFENSIVE_POSITIONS):
        raise ValueError('Clean-sheet bonuses are available only to goalkeepers and defenders')



def public_wage_range(demand: int) -> dict:
    """An approximate request, deliberately not the actual acceptance threshold."""
    step = 500 if demand < 20_000 else 2_500 if demand < 100_000 else 5_000
    lower = max(75, int(demand * .87 / step) * step)
    upper = max(lower+step, int(demand * 1.14 / step + 1) * step)
    return {'low_gbp':lower, 'high_gbp':upper}


def terms_json(terms: PersonalTerms | None) -> dict | None:
    if terms is None:
        return None
    return {'weekly_wage_gbp':terms.weekly_wage_gbp,'years':terms.years,
            'role':terms.role,'signing_bonus_gbp':terms.signing_bonus_gbp,
            'bonuses':[{'kind':b.kind,'threshold':b.threshold,'amount_gbp':b.amount_gbp}
                       for b in terms.bonuses]}


def terms_from_json(raw: object) -> PersonalTerms:
    if not isinstance(raw,dict) or set(raw)-{'weekly_wage_gbp','years','role','signing_bonus_gbp','bonuses'}:
        raise ValueError('Invalid player-agent contract fields')
    if not {'weekly_wage_gbp','years','role','signing_bonus_gbp'} <= set(raw):
        raise ValueError('Enter weekly salary, years, role and signing-on fee')
    bonuses=raw.get('bonuses',[])
    if not isinstance(bonuses,(list,tuple)) or len(bonuses)>3:
        raise ValueError('At most three conditional player bonuses')
    parsed=[]
    for bonus in bonuses:
        if not isinstance(bonus,dict) or set(bonus)!={'kind','threshold','amount_gbp'}:
            raise ValueError('Invalid personal contract bonus fields')
        parsed.append(ContractBonus(**bonus))
    terms=PersonalTerms(raw['weekly_wage_gbp'],raw['years'],raw['role'],raw['signing_bonus_gbp'],tuple(parsed))
    terms.validate()
    return terms


def agent_response(player, terms: PersonalTerms, quote: dict, patience: int, rounds: int):
    """Return ('accept'|'counter'|'end', counter, patience, explanation).

    Different agents trade salary, role, duration and bonuses differently.
    Refusal severity depends on real economic distance, not a rigid attempt cap.
    """
    demand=quote['weekly_wage_gbp']
    if not demand:
        raise ValueError('Unpriced personal request')
    years=max(1,min(terms.years, quote['max_years']))
    age=player.age_on(quote['date'])
    ambition=player.personality.ambition
    loyalty=player.personality.loyalty
    prefer=quote['role']
    role_deficit=max(0, ROLES.index(terms.role)-ROLES.index(prefer))
    length_deficit=max(0,min(quote.get('years',3),quote['max_years'])-years)
    role_extra=max(0, ROLES.index(prefer)-ROLES.index(terms.role))
    min_cash_factor=.53 if ambition<55 else .61
    conditional=sum(b.amount_gbp * (.15 if b.kind=='promotion' else .23 if b.kind=='appearances' else .12)
                    for b in terms.bonuses)
    bonus_weekly=(terms.signing_bonus_gbp*(.70 if loyalty<65 else .55)+conditional)/(52*years)
    effective=terms.weekly_wage_gbp+bonus_weekly
    # Promising extra role/years has value but not a magic substitute for wages.
    effective += demand * (min(2,role_extra)*(.028 if ambition>65 else .043))
    if age>=30:effective+=demand*min(2,max(0,years-2))*.034
    effective-=demand*(role_deficit*(.10 if ambition>50 else .07)+length_deficit*(.027 if age<30 else .05))
    needed=demand*(1-.012*min(rounds,3))
    enough=(effective>=needed and terms.weekly_wage_gbp >= max(75, int(demand*min_cash_factor))
            and role_deficit<= (0 if ambition>=60 else 1) and terms.years<=quote['max_years'])
    if enough:
        return 'accept',None,patience,'The agent and player have accepted the complete contract package.'
    distance=max(0.,(needed-effective)/max(needed,1))
    cost= max(7,round(9+min(.95,distance)*36 + role_deficit*7 + (5 if terms.years>quote['max_years'] else 0)))
    if terms.weekly_wage_gbp < demand*.20:
        cost=max(cost,45)
    remaining=max(0,patience-cost)
    if remaining<=0 or rounds>=7:
        return 'end',None,0,'The player and agent have ended discussions after repeated unacceptable offers.'
    # Dynamic response: offer salary/bonus/role and term tradeoffs rather than only wage increases.
    favor_bonus=(loyalty<58 and rounds%2==0) or (terms.signing_bonus_gbp>0 and rounds%2==1)
    counter_role=prefer if role_deficit and ambition>=45 else terms.role
    counter_years=years
    if age>=31 and counter_years<min(quote['max_years'],3):
        counter_years+=1
    elif age<=22 and years>3 and ambition>=70:
        counter_years=3
    target=_round_wage(max(75,needed*(.97 if remaining>35 else 1.0)))
    counter_bonus=terms.signing_bonus_gbp
    if favor_bonus:
        counter_bonus=min(50_000_000,max(counter_bonus,round(demand*8/5000)*5000))
        target=_round_wage(target*.93)
    elif role_deficit:
        target=_round_wage(target*.985)
    # Retain up to three conditions the club suggested; at most one new request.
    proposed=terms.bonuses
    if not proposed and rounds>=1 and ambition<75 and not favor_bonus:
        kind='appearances' if age>27 or player.primary_position.value=='GK' else 'promotion'
        threshold=20 if kind=='appearances' else 1
        proposed=(ContractBonus(kind,threshold,max(1_000,round(demand*5/1000)*1000)),)
        target=_round_wage(target*.975)
    counter=PersonalTerms(max(75,target),counter_years,counter_role,counter_bonus,proposed)
    counter.validate()
    objection=('playing-time role' if role_deficit else 'contract duration' if terms.years>quote['max_years']
               else 'guaranteed salary and overall compensation')
    return 'counter',counter,remaining,f'The agent wants changes to {objection}, and has submitted revised terms.'
