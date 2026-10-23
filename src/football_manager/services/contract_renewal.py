"""TS-FIX-03: agent-mediated professional renewals on the same terms model as signings."""
from __future__ import annotations

from dataclasses import replace
from datetime import timedelta

from football_manager.domain.club_economy import PlayerContract, WagePeriod
from football_manager.domain.contract_negotiation import ContractTalk
from football_manager.domain.transfer_personal import PersonalEvent
from football_manager.services.club_economy import (
    _date_plus_months, quote_renewal, weekly_payroll,
)
from football_manager.services.contract_bargaining import (
    agent_response, terms_from_json, terms_json, public_wage_range,
)
from football_manager.services.contract_incentives import record_contract_bonuses


def _context(session,player_id):
    registry=session._world_squads
    if not isinstance(player_id,str) or not session.home_club.squad.contains(player_id):
        raise ValueError('Player must belong to your first team')
    player=session.home_club.squad.get(player_id)
    contract=registry.contracts.get(player_id)
    if contract is None or contract.club_id!=session.home_club.id:
        raise ValueError('Only your club can renew its registered players')
    return registry,player,contract


def _quote(registry,player,contract,day):
    max_years=2 if player.age_on(day)>=35 else 3 if player.age_on(day)>=32 else 5
    info=quote_renewal(registry,player,contract,day,min(2,max_years))
    return {'weekly_wage_gbp':info['minimum_weekly_gbp'],'max_years':max_years,
            'role':contract.role,'years':min(3,max_years),'date':day}


def _current_talk(talk, contract, now):
    """Read-only cooldown: a closed round cannot ban a future renewal forever.

    Previous discussions remain in the save until a new offer is submitted;
    reading a reopened screen never mutates the save. New rounds start at full
    patience only after the cooling-off period has actually elapsed.
    """
    if talk is None:
        return None
    if talk.status == 'ended':
        last = talk.events[-1].on_date if talk.events else talk.started_on
        if (now - last).days >= 45:
            return None
    if talk.status == 'renewed':
        latest = contract.renewed_on or contract.signed_on
        if latest > talk.started_on and (now - latest).days >= 90:
            return None
        # A renewal signed on the same day as the talk should reopen after
        # the same 90-day period, never on the signing day itself.
        if latest == talk.started_on and (now - latest).days >= 90:
            return None
    return talk


def renew_read_model(session, player_id: str) -> dict:
    registry,player,contract=_context(session,player_id)
    talk=registry.contract_talks.get(player_id)
    if talk is not None and talk.club_id!=session.home_club.id:
        talk=None
    talk=_current_talk(talk,contract,session.current_date)
    try:
        quote=_quote(registry,player,contract,session.current_date)
        available=True
        note='The agent is open to discussing a contract extension.'
    except ValueError as error:
        quote=None
        available=False
        note=str(error)
    from football_manager.services.contract_bargaining import public_wage_range
    from football_manager.services.club_economy import contract_view
    bonus_row=registry.contract_bonuses.get(player_id)
    return {'mode':'renewal','player':{'id':player.id,'name':player.full_name,
                'age':player.age_on(session.current_date),'position':player.primary_position.value,
                'nationality':player.identity.nationality,'club_id':session.home_club.id,
                'club':session.home_club.name,'ovr':round(player.overall_rating,1)},
            'club_id':session.home_club.id,'club':session.home_club.name,
            'date':session.current_date.isoformat(),'available':available,'note':note,
            'current':contract_view(registry,player_id,session.current_date),
            'quote':({'range':public_wage_range(quote['weekly_wage_gbp']),
                     'role':quote['role'],'years':quote['years'],
                     'max_years':quote['max_years']} if quote else None),
            'wage_headroom_gbp':registry.club_finances[session.home_club.id].wage_budget_weekly_gbp
                    - weekly_payroll(registry,session.home_club.id),
            'talk':_talk_json(talk),
            'incentives':({'bonuses':terms_json_bonuses(bonus_row.bonuses),
                           'paid':list(bonus_row.paid)} if bonus_row and bonus_row.club_id==session.home_club.id
                           and bonus_row.signed_on==contract.signed_on else None)}


def terms_json_bonuses(bonuses):
    return [{'kind':x.kind,'threshold':x.threshold,'amount_gbp':x.amount_gbp} for x in bonuses]


def _talk_json(talk):
    if talk is None:
        return {'status':'open','patience':100,'rounds':0,'counter':None,'reason':'','history':[]}
    return {'status':talk.status,'patience':talk.patience,'rounds':talk.rounds,
            'counter':terms_json(talk.counter),'reason':talk.reason,
            'history':[{'on_date':e.on_date.isoformat(),'actor':e.actor,
                        'note':e.note,'terms':terms_json(e.terms)} for e in talk.events]}


def _commit(session,player,contract,terms):
    if terms.weekly_wage_gbp<75:
        raise ValueError('A registered professional contract needs positive weekly wages')
    registry=session._world_squads
    acc=registry.club_finances[session.home_club.id]
    revised=weekly_payroll(registry,session.home_club.id)-contract.weekly_wage_gbp+terms.weekly_wage_gbp
    if revised>acc.wage_budget_weekly_gbp:
        raise ValueError('The offered wages would exceed the approved wage budget')
    if terms.signing_bonus_gbp>max(0,acc.cash_gbp):
        raise ValueError('Club cash cannot cover the promised signing bonus')
    now=session.current_date
    history=contract.history
    if contract.signed_on<now:
        history=(*history,WagePeriod(contract.signed_on,now-timedelta(days=1),contract.weekly_wage_gbp))
    updated=PlayerContract(player.id,session.home_club.id,now,_date_plus_months(now,terms.years*12),
                           terms.weekly_wage_gbp,terms.role,'professional',history,now)
    updated.validate()
    registry.contracts[player.id]=updated
    registry.club_finances[session.home_club.id]=replace(acc,
        cash_gbp=acc.cash_gbp-terms.signing_bonus_gbp,
        season_operations_gbp=acc.season_operations_gbp+terms.signing_bonus_gbp)
    record_contract_bonuses(registry,player.id,session.home_club.id,now,terms.bonuses)
    from football_manager.services.contract_promises import record_contract_role_promise
    record_contract_role_promise(session,player.id,terms.role)
    return {'renewed':True,'player_id':player.id,'weekly_wage_gbp':terms.weekly_wage_gbp,
            'signing_bonus_paid_gbp':terms.signing_bonus_gbp,'expires_on':updated.expires_on.isoformat(),
            'role':terms.role}


def renewal_command(session, command: dict) -> dict:
    if not isinstance(command,dict) or command.get('action') not in ('contract_offer','contract_accept','contract_walk_away'):
        raise ValueError('Use the player-agent contract negotiation workflow')
    pid=command.get('player_id')
    registry,player,contract=_context(session,pid)
    now=session.current_date
    talk=registry.contract_talks.get(pid)
    if talk is not None and talk.club_id!=session.home_club.id:
        talk=None
    talk=_current_talk(talk,contract,now)
    if talk is None:
        talk=ContractTalk(pid,session.home_club.id,now)
    if talk.status in ('renewed','ended'):
        raise ValueError('This negotiation is closed; no further offers can be submitted')
    if command['action']=='contract_walk_away':
        registry.contract_talks[pid]=replace(talk,status='ended',reason='You withdrew from contract discussions.')
        return {'status':'ended','player_id':pid}
    quote=_quote(registry,player,contract,now)
    if command['action']=='contract_accept':
        if talk.status!='counter' or talk.counter is None:
            raise ValueError('No agent counteroffer available to accept')
        result=_commit(session,player,contract,talk.counter)
        registry.contract_talks[pid]=replace(talk,status='renewed',
            events=(*talk.events,PersonalEvent(now,'club',talk.counter,'Manager accepted the agent counteroffer')),
            reason='Contract renewed after negotiation')
        return {'status':'renewed',**result}
    if talk.rounds>=7 or talk.patience==0:
        raise ValueError('Agent is no longer willing to negotiate')
    terms=terms_from_json(command.get('terms'))
    from football_manager.services.contract_bargaining import validate_player_bonuses
    validate_player_bonuses(player,terms)
    entry=PersonalEvent(now,'club',terms,'Manager submitted a personal contract proposal')
    history=(*talk.events,entry)
    outcome,counter,patience,reason=agent_response(player,terms,quote,talk.patience,talk.rounds)
    if outcome=='accept':
        result=_commit(session,player,contract,terms)
        history+= (PersonalEvent(now,'agent',terms,reason),)
        updated=replace(talk,status='renewed',patience=patience,rounds=talk.rounds+1,
                        counter=None,events=history,reason=reason)
        registry.contract_talks[pid]=updated
        return {'status':'renewed',**result}
    if outcome=='end':
        updated=replace(talk,status='ended',patience=0,rounds=talk.rounds+1,counter=None,
                        events=history,reason=reason)
    else:
        history+= (PersonalEvent(now,'agent',counter,reason),)
        updated=replace(talk,status='counter',patience=patience,rounds=talk.rounds+1,
                        counter=counter,events=history,reason=reason)
    updated.validate()
    registry.contract_talks[pid]=updated
    return {'status':updated.status,'player_id':pid,'patience':patience,
            'counter':terms_json(counter),'reason':reason}
