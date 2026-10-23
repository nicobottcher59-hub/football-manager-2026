"""TS-FIX-06: persistent club-to-club loan negotiations and AI counter-offers.

The dialogue is not a price oracle. AI policy uses private squad, financial and
sporting context; only actual counterproposals and qualitative reasons are exposed.
"""
from __future__ import annotations
from dataclasses import replace
from datetime import date, timedelta
from football_manager.domain.loan_negotiation import LoanTerms, LoanRound, LoanTalk
from football_manager.domain.transfer_negotiation import TransferTerms
from football_manager.services.transfer_negotiation import _terms_from_data, _seller_target
from football_manager.services.club_economy import _date_plus_months, weekly_payroll
from football_manager.services.transfer_windows import next_opening, window_open
from football_manager.services.ai_squad_planning import squad_plan

ACTIVE = ('counter', 'agreed', 'pending_window')


def parse_loan_terms(payload: dict, now: date) -> LoanTerms:
    if not isinstance(payload, dict):
        raise ValueError('Choose terms for the proposed loan')
    purchase_raw=payload.get('purchase')
    purchase=None
    if purchase_raw is not None:
        # Reuse the same validation as a regular purchase (bonuses, deferred
        # guaranteed fee, sell-on, buyback). The market quote is not leaked.
        purchase=_terms_from_data(purchase_raw,now,0)
    terms=LoanTerms(payload.get('months'),payload.get('borrower_wage_percent'),
                    payload.get('playing_time'),payload.get('recall_allowed',False),purchase)
    terms.validate()
    return terms


def _player_and_clubs(session,pid,parent,borrower):
    reg=session._world_squads
    if (parent==borrower or parent not in reg.clubs or borrower not in reg.clubs
            or session.home_club.id not in (parent,borrower)):
        raise ValueError('Your club must be one party to the proposed loan')
    if not reg.clubs[parent].squad.contains(pid):
        raise ValueError('This player is no longer registered with the parent club')
    player=reg.clubs[parent].squad.get(pid)
    contract=reg.contracts.get(pid)
    if contract is None or contract.club_id!=parent or contract.kind!='professional':
        raise ValueError('The player needs a parent-club professional contract')
    from football_manager.services.loan_market import active_loan
    if active_loan(reg,pid):
        raise ValueError('This player is already out on loan')
    if len(reg.clubs[parent].squad)<=17 or len(reg.clubs[borrower].squad)>=35:
        raise ValueError('Squad registration does not permit this loan')
    return player,contract


def _policy(reg,player,parent,borrower,now):
    contract=reg.contracts[player.id]
    room=max(0,reg.club_finances[borrower].wage_budget_weekly_gbp-weekly_payroll(reg,borrower))
    max_affordable=min(100,(room*100)//max(1,contract.weekly_wage_gbp))
    plan=squad_plan(reg.clubs[borrower],reg.identities[borrower].primary)
    holes={r['position'] for r in plan['vacancies'] if r['layer']<=2}
    needs_role='starter' if player.primary_position.value in holes else 'rotation'
    important=player.overall_rating>=max((p.overall_rating for p in reg.clubs[parent].squad.players),default=0)-3
    # A lender of an important player expects higher coverage; a borrower
    # with little wage room may counter with shorter/cheaper terms.
    requested=75 if important else 50 if contract.weekly_wage_gbp>5000 else 25
    max_willing=max(0,min(max_affordable,80 if needs_role=='starter' else 55))
    minimum_option=max(5_000,round(_seller_target(reg,parent,borrower,player,contract,now)*.82/5000)*5000)
    return requested,max_willing,needs_role,minimum_option


def _AI_decide(reg,player,parent,borrower,terms,now,manager,rounds):
    requested,maximum,need,minimum_option=_policy(reg,player,parent,borrower,now)
    ai_lender=parent!=manager
    desired=terms
    score=0
    objection=[]
    # Salary negotiability is private and depends on which club is controlled.
    if ai_lender and terms.borrower_wage_percent<requested:
        desired=replace(desired,borrower_wage_percent=min(100,max(terms.borrower_wage_percent+15,requested-5*min(rounds,3))))
        score+=max(0,requested-terms.borrower_wage_percent)*1.0
        objection.append('The parent club wants more of the salary covered')
    elif not ai_lender and terms.borrower_wage_percent>maximum:
        desired=replace(desired,borrower_wage_percent=max(0,min(maximum+5,terms.borrower_wage_percent-15)))
        score+=max(0,terms.borrower_wage_percent-maximum)*1.1
        objection.append('The borrowing club cannot justify this salary commitment')
    # Playing-time promises must be feasible for the actual squad, even when
    # the AI is the parent club and the manager is the borrower.
    borrower_club=reg.clubs[borrower]
    rivals=sorted((p.overall_rating for p in borrower_club.squad.players
                   if p.familiarity_for(player.primary_position)>=60),reverse=True)
    rank=sum(v>player.overall_rating+2 for v in rivals)
    slots=sum(s.position==player.primary_position for s in reg.identities[borrower].primary.formation.slots)
    if desired.playing_time=='starter' and rank>=max(1,slots):
        desired=replace(desired,playing_time='rotation')
        score+=12
        objection.append('A guaranteed starting role is not credible at the borrowing club')
    if desired.playing_time=='rotation' and rank>=max(2,slots*3):
        desired=replace(desired,playing_time='backup')
        score+=12
        objection.append('Only backup minutes are currently credible at the borrowing club')
    if terms.playing_time=='backup' and need=='starter' and not ai_lender:
        desired=replace(desired,playing_time='rotation')
        score+=9
        objection.append('The club wants meaningful playing time')
    if terms.playing_time=='starter' and need=='rotation' and not ai_lender:
        desired=replace(desired,playing_time='rotation')
        score+=12
        objection.append('The club will not guarantee a starting position')
    if terms.months==24 and not ai_lender:
        desired=replace(desired,months=12)
        score+=13
        objection.append('A shorter initial loan is preferred')
    if ai_lender and terms.months==24 and player.age_on(now)<=20:
        desired=replace(desired,months=12)
        score+=10
        objection.append('The lender wants to review development after a season')
    if terms.recall_allowed and not ai_lender:
        desired=replace(desired,recall_allowed=False)
        score+=8
        objection.append('The borrower wants a stable loan')
    if not terms.recall_allowed and ai_lender and player.age_on(now)<=21:
        desired=replace(desired,recall_allowed=True)
        score+=8
        objection.append('The parent club asks for a recall right')
    if terms.purchase:
        if ai_lender:
            from football_manager.services.transfer_negotiation import assess_terms
            # A variable-heavy option is discounted using exactly the same
            # expected-value model as normal club transfer negotiations.
            valuation=assess_terms(reg,player,borrower,terms.purchase,now)['risk_adjusted_gbp']
            if valuation < minimum_option:
                raised=max(minimum_option,terms.purchase.guaranteed_gbp+max(5000,(minimum_option-valuation)//2))
                raised=min(500_000_000,round(raised/5000)*5000)
                if raised>terms.purchase.guaranteed_gbp:
                    desired=replace(desired,purchase=replace(terms.purchase,fixed_gbp=max(0,raised-terms.purchase.installments_gbp)))
                    score+=min(55,20+(minimum_option-valuation)/max(1,minimum_option)*35)
                    objection.append('The option to buy undervalues the permanent transfer')
        else:
            if terms.purchase.guaranteed_gbp>minimum_option*1.5 and player.age_on(now)<24:
                desired=replace(desired,purchase=replace(terms.purchase,fixed_gbp=max(0,round(minimum_option*1.3)-terms.purchase.installments_gbp)))
                score+=9
                objection.append('The borrowing club wants a more realistic option price')
    # Counteroffer is a real, explicit proposal from the AI, not a hidden
    # number placed in the manager's input. Small differences are negotiable.
    acceptable=score <= (8+rounds*2)
    reason='The other club accepts the sporting and financial structure.' if acceptable else '; '.join(dict.fromkeys(objection))[:220]
    return acceptable,desired,score,reason


def _register(session, pid, parent, borrower, terms, *, talk_id=None):
    from football_manager.services.loan_market import _begin
    cmd={'player_id':pid,'parent_id':parent,'borrower_id':borrower,
         'months':terms.months,'borrower_wage_percent':terms.borrower_wage_percent,
         'playing_time':terms.playing_time,'option_gbp':terms.purchase.guaranteed_gbp if terms.purchase else None,
         'recall_allowed':terms.recall_allowed,'purchase_terms':terms.purchase}
    result=_begin(session,cmd)
    if talk_id:
        reg=session._world_squads
        reg.loan_talks[talk_id]=replace(reg.loan_talks[talk_id],status='active',loan_id=result['loan_id'])
    return result


def loan_talk_command(session,cmd):
    reg=session._world_squads
    manager=session.home_club.id
    now=session.current_date
    action=cmd.get('action')
    if action in ('loan_accept_counter','loan_walk'):
        talk=reg.loan_talks.get(cmd.get('talk_id'))
        if talk is None or talk.status not in ACTIVE:
            raise ValueError('No ongoing discussion with that club')
        if talk.expires_on<now:
            raise ValueError('This discussion has expired')
        if action=='loan_walk':
            reg.loan_talks[talk.talk_id]=replace(talk,status='walked',reason='Manager ended the discussion')
            return {'talk_id':talk.talk_id,'status':'walked'}
        if talk.status!='counter' or talk.rounds[-1].by_club_id==manager:
            raise ValueError('Only a counteroffer from the other club can be accepted')
        _player_and_clubs(session,talk.player_id,talk.parent_id,talk.borrower_id)
        return _agree(session,talk,talk.terms)
    if action!='loan_propose':
        raise ValueError('Unsupported loan negotiation operation')
    old=reg.loan_talks.get(cmd.get('talk_id')) if cmd.get('talk_id') else None
    if old is not None and old.expires_on<now:
        raise ValueError('This conversation expired; start a new negotiation')
    if old is not None and old.status!='counter':
        raise ValueError('This loan discussion is not available for a new proposal')
    if old is not None and old.rounds[-1].by_club_id==manager:
        raise ValueError('Wait for the other club response')
    pid=old.player_id if old else cmd.get('player_id')
    parent=old.parent_id if old else cmd.get('parent_id')
    borrower=old.borrower_id if old else cmd.get('borrower_id')
    player,contract=_player_and_clubs(session,pid,parent,borrower)
    terms=parse_loan_terms(cmd.get('terms'),now)
    arrival=next_opening(now,reg.clubs[borrower].country)
    # Reject structurally impossible loans before creating a stateful dialogue.
    # Zero salary/backup is only a feasibility check, not the AI's counteroffer.
    from football_manager.services.loan_market import _can_loan
    _can_loan(reg,pid,parent,borrower,now,terms.months,0,'backup',None,registration_on=arrival)
    if contract.expires_on<_date_plus_months(arrival,terms.months):
        raise ValueError('The parent contract must cover the proposed loan after registration')
    if old is None:
        if any(t.player_id==pid and t.parent_id==parent and t.borrower_id==borrower
               and t.status in ACTIVE and t.expires_on>=now for t in reg.loan_talks.values()):
            raise ValueError('A discussion for this loan is already open')
        # Ending a difficult discussion has an actual cost. Creating a fresh
        # dialogue may not reset the counterparty to 100% patience tomorrow.
        for previous in reg.loan_talks.values():
            if (previous.player_id==pid and previous.parent_id==parent
                    and previous.borrower_id==borrower
                    and previous.status in ('broken','walked')
                    and previous.rounds[-1].on_date+timedelta(days=60 if previous.status=='broken' else 14)>now):
                raise ValueError('The other club needs time before restarting loan talks')
        idx=reg.loan_next_id
        reg.loan_next_id+=1
        key=f'tsfix06-talk-{idx:06d}'
        rounds=()
        patience=100
        started=now
    else:
        key=old.talk_id
        rounds=old.rounds
        patience=old.patience
        started=old.started_on
        if len(rounds)>=22:
            raise ValueError('This discussion has reached its maximum length')
    submitted=LoanRound(now,manager,terms,'Manager submits a complete loan package')
    accepted,counter,disagreement,reason=_AI_decide(reg,player,parent,borrower,terms,now,manager,len(rounds)//2)
    lost=(3 if accepted else min(39,7+int(disagreement*.45)+(len(rounds)//2)*3))
    patience=max(0,patience-lost)
    response=LoanRound(now,borrower if manager==parent else parent,
                       terms if accepted else counter,reason)
    next_status='agreed' if accepted else 'counter' if patience>0 else 'broken'
    talked=LoanTalk(key,pid,parent,borrower,started,now+timedelta(days=35),
                    next_status,response.terms,rounds+(submitted,response),patience,None,reason)
    talked.validate()
    reg.loan_talks[key]=talked
    if accepted:
        return _agree(session,talked,terms)
    return {'talk_id':key,'status':next_status,'patience':patience,'reason':reason,
            'terms':public_loan_terms(response.terms)}


def _agree(session,talk,terms):
    reg=session._world_squads
    from football_manager.services.loan_market import _can_loan
    now=session.current_date
    arrival=next_opening(now,reg.clubs[talk.borrower_id].country)
    if arrival>now:
        # Validate sporting fit at agreement time, then repeat at registration.
        # No cash, salary liability or player registration starts yet.
        _can_loan(reg,talk.player_id,talk.parent_id,talk.borrower_id,now,terms.months,
                  terms.borrower_wage_percent,terms.playing_time,
                  terms.purchase.guaranteed_gbp if terms.purchase else None,
                  registration_on=arrival,purchase_terms=terms.purchase)
        pending=replace(talk,status='pending_window',terms=terms,expires_on=arrival+timedelta(days=6),
                        reason=f'Loan agreed; registration scheduled for {arrival.isoformat()}')
        if pending.rounds[-1].terms!=terms:
            pending=replace(pending,rounds=pending.rounds+(LoanRound(now,session.home_club.id,terms,'Counteroffer accepted'),))
        reg.loan_talks[talk.talk_id]=pending
        return {'talk_id':talk.talk_id,'status':'pending_window','arrival_on':arrival.isoformat()}
    if talk.rounds[-1].terms!=terms:
        talk=replace(talk,terms=terms,rounds=talk.rounds+(LoanRound(now,session.home_club.id,terms,'Counteroffer accepted'),))
    reg.loan_talks[talk.talk_id]=talk
    result=_register(session,talk.player_id,talk.parent_id,talk.borrower_id,terms,talk_id=talk.talk_id)
    result['talk_id']=talk.talk_id
    return result


def public_loan_terms(terms):
    from football_manager.services.transfer_negotiation import terms_as_json
    return {'months':terms.months,'borrower_wage_percent':terms.borrower_wage_percent,
            'playing_time':terms.playing_time,'recall_allowed':terms.recall_allowed,
            'purchase':terms_as_json(terms.purchase) if terms.purchase else None}


def public_loan_talk(talk,registry):
    return {'id':talk.talk_id,'player_id':talk.player_id,'parent_id':talk.parent_id,
            'parent':registry.clubs[talk.parent_id].name,'borrower_id':talk.borrower_id,
            'borrower':registry.clubs[talk.borrower_id].name,'status':talk.status,
            'patience':talk.patience,'reason':talk.reason,'expires_on':talk.expires_on.isoformat(),
            'loan_id':talk.loan_id,'terms':public_loan_terms(talk.terms),
            'history':[{'date':r.on_date.isoformat(),'by_club_id':r.by_club_id,
                        'club':registry.clubs[r.by_club_id].name,'note':r.note,
                        'terms':public_loan_terms(r.terms)} for r in talk.rounds]}


def settle_pending_loan_talks(world,day):
    """Register agreed loans at the next valid window, with journal rollback."""
    reg=world.football_world
    if world._active_journal is None:
        raise RuntimeError('Loan registrations must run in a world transaction')
    from football_manager.services.loan_market import _can_loan, _move, _career_minutes
    from football_manager.services.transfer_personal import career_player_totals
    from football_manager.domain.loan_market import LoanAgreement
    completed=0
    for talk in sorted(tuple(reg.loan_talks.values()),key=lambda t:t.talk_id):
        if talk.status!='pending_window':
            continue
        if not window_open(day,reg.clubs[talk.borrower_id].country):
            continue
        terms=talk.terms
        try:
            player,_=_can_loan(reg,talk.player_id,talk.parent_id,talk.borrower_id,day,terms.months,
                               terms.borrower_wage_percent,terms.playing_time,
                               terms.purchase.guaranteed_gbp if terms.purchase else None,
                               purchase_terms=terms.purchase)
            serial=reg.loan_next_id
            world._active_journal.undo_callbacks.setdefault(('loan-talk-sequence',serial),
                lambda previous=serial:setattr(reg,'loan_next_id',previous))
            reg.loan_next_id+=1
            agreement=LoanAgreement(f'tsfix06-loan-{serial:06d}',player.id,talk.parent_id,talk.borrower_id,
                         day,_date_plus_months(day,terms.months),terms.borrower_wage_percent,
                         terms.playing_time,terms.purchase.guaranteed_gbp if terms.purchase else None,
                         appearances_at_start=career_player_totals(reg,player.id)[0],
                         minutes_at_start=_career_minutes(reg,player.id),
                         recall_allowed=terms.recall_allowed,purchase_terms=terms.purchase)
            agreement.validate()
            _move(reg,player,talk.parent_id,talk.borrower_id,world=world,key=agreement.loan_id)
            world._put(reg.loans,agreement.loan_id,agreement)
            world._put(reg.loan_talks,talk.talk_id,replace(talk,status='active',loan_id=agreement.loan_id))
            completed+=1
        except ValueError as error:
            world._put(reg.loan_talks,talk.talk_id,replace(talk,status='failed',reason=str(error)[:240]))
    return completed
