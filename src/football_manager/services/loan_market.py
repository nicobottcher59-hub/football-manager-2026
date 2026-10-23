"""TS-24.6 loans (6/12/24 months), unsigned professionals and buyback exercise.

Pages are read-only; commands run on a deep-copied career. Month-end operations
run in WorldSeasonRunner's journal and keep canonical Player objects.
"""
from __future__ import annotations

from dataclasses import replace
from datetime import date, timedelta

from football_manager.domain.club_economy import PlayerContract
from football_manager.domain.enums import Position
from football_manager.domain.loan_market import FreeAgent, LoanAgreement
from football_manager.domain.transfer_negotiation import TransferTerms, TransferNegotiation, NegotiationEvent
from football_manager.domain.transfer_personal import PersonalTerms, PersonalEvent
from football_manager.services.club_economy import (
    _date_plus_months, _month_wage, wage_expectation, weekly_payroll,
)
from football_manager.services.transfer_personal import (
    _player_interest, agent_demand, _expected_role, _repair_selected_team,
    _finish, career_player_totals,
)
from football_manager.services.transfer_negotiation import _availability
from football_manager.services.transfer_windows import window_open
from football_manager.services.ai_squad_planning import squad_plan, can_spare, imminent_succession_needs

LOAN_MONTHS = (6, 12, 24)
LOAN_MIN_ROSTER = 17
MAX_LOANS_PER_BORROWER = 5


def active_loan(registry, player_id: str) -> LoanAgreement | None:
    return next((x for x in registry.loans.values()
                 if x.player_id == player_id and x.status == 'active'), None)


def loan_payroll(registry, cid: str, base_weekly: int) -> int:
    """Parent pays remainder, borrower pays agreed share; no wage duplication."""
    for loan in registry.loans.values():
        if loan.status != 'active':
            continue
        contract = registry.contracts.get(loan.player_id)
        if contract is None:
            continue
        shared = round(contract.weekly_wage_gbp * loan.borrower_wage_percent / 100)
        if cid == loan.parent_id:
            base_weekly -= shared
        if cid == loan.borrower_id:
            base_weekly += shared
    return base_weekly


def loan_monthly_adjustments(registry, start: date, end: date) -> dict[str, int]:
    """Payments are based on the actual active days, including historical loans."""
    changes: dict[str, int] = {}
    for loan in registry.loans.values():
        contract = registry.contracts.get(loan.player_id)
        if contract is None or contract.club_id!=loan.parent_id:
            # A loan that later became a transfer has already had its wage
            # history settled at acquisition/expiry (no speculative back-pay).
            continue
        hi = (loan.completed_on - timedelta(days=1)) if loan.completed_on else end
        lo = max(start, loan.started_on, contract.signed_on)
        hi = min(end, hi)
        if lo > hi:
            continue
        portion = round(_month_wage(contract, lo, hi) * loan.borrower_wage_percent / 100)
        changes[loan.parent_id] = changes.get(loan.parent_id, 0) - portion
        changes[loan.borrower_id] = changes.get(loan.borrower_id, 0) + portion
    return changes


def _can_loan(registry, pid: str, parent: str, borrower: str, now: date, months: int,
              wage_percent: int, playing_time: str, option: int | None,
              *, registration_on: date | None = None, purchase_terms: TransferTerms | None = None):
    if not window_open(registration_on or now, registry.clubs[borrower].country if borrower in registry.clubs else 'England'):
        raise ValueError('Loan registration requires an open market window')
    actual_start = registration_on or now
    if actual_start < now:
        raise ValueError('Loan registration cannot precede the market offer')
    if parent == borrower or parent not in registry.clubs or borrower not in registry.clubs:
        raise ValueError('Select distinct registered English clubs')
    if months not in LOAN_MONTHS or type(months) is not int:
        raise ValueError('Loan length must be 6, 12 or 24 months')
    if type(wage_percent) is not int or not 0 <= wage_percent <= 100:
        raise ValueError('Borrower salary share must be from 0 to 100 percent')
    if playing_time not in ('starter','rotation','backup'):
        raise ValueError('Choose an expected playing-time role')
    if option is not None and (type(option) is not int or not 5_000 <= option <= 500_000_000):
        raise ValueError('Invalid optional purchase price')
    if active_loan(registry,pid):
        raise ValueError('Player already has an active loan')
    parent_club=registry.clubs[parent]
    borrower_club=registry.clubs[borrower]
    if not parent_club.squad.contains(pid):
        raise ValueError('Only registered first-team players can be loaned; promote academy players first')
    player=parent_club.squad.get(pid)
    contract=registry.contracts.get(pid)
    if contract is None or contract.club_id!=parent or contract.kind!='professional':
        raise ValueError('Professional contract must belong to the parent club')
    if option is not None and parent != (registry.youth.managed_club_id if registry.youth else None):
        from football_manager.services.transfer_negotiation import _seller_target
        minimum = max(5_000,round(_seller_target(registry,parent,borrower,player,contract,now)*.82/5000)*5000)
        if purchase_terms is not None:
            # A seller may trade guaranteed cash for conditional bonuses or
            # resale participation. Value the complete option exactly as the
            # bargaining AI did, rather than reintroducing an upfront-only
            # minimum after the counterpart has already agreed.
            from football_manager.services.transfer_negotiation import assess_terms
            option_value = assess_terms(registry,player,borrower,purchase_terms,now)['risk_adjusted_gbp']
        else:
            # Compatibility with existing TS-24 loans that specify only a price.
            option_value = option
        if option_value < minimum:
            raise ValueError('Lender rejects an undervalued future purchase option')
    if contract.expires_on < _date_plus_months(actual_start,months):
        raise ValueError('Parent contract must cover the entire loan; renew first')
    if len(parent_club.squad)<=LOAN_MIN_ROSTER or len(borrower_club.squad)>=35:
        raise ValueError('Club roster size does not support this loan')
    if not can_spare(parent_club,registry.identities[parent].primary,pid):
        raise ValueError('Parent club cannot spare that player without losing necessary coverage')
    if sum(p.primary_position.value=='GK' for p in parent_club.squad.players)<=2 and player.primary_position.value=='GK':
        raise ValueError('Parent must retain two goalkeepers')
    if sum(x.status=='active' and x.borrower_id==borrower for x in registry.loans.values())>=MAX_LOANS_PER_BORROWER:
        raise ValueError('Borrowing club already has five loan players')
    interested,why=_player_interest(registry,player,parent,borrower,now)
    if not interested:
        raise ValueError(why)
    buyer_finance=registry.club_finances[borrower]
    shared=round(contract.weekly_wage_gbp*wage_percent/100)
    if weekly_payroll(registry,borrower)+shared>buyer_finance.wage_budget_weekly_gbp:
        raise ValueError('Borrowing club has insufficient salary budget')
    if buyer_finance.cash_gbp < shared * 4:
        raise ValueError('Borrowing club cannot support its wage contribution')
    # The borrower must have a credible role for the arrival. An elite player
    # does not agree to a nominal 'starter' promise behind much better teammates.
    peers=sorted((p.overall_rating for p in borrower_club.squad.players
                  if p.familiarity_for(player.primary_position)>=60), reverse=True)
    rank=sum(value>player.overall_rating+2 for value in peers)
    slots=sum(s.position==player.primary_position for s in registry.identities[borrower].primary.formation.slots)
    if playing_time=='starter' and rank>=max(1,slots):
        raise ValueError('Borrower cannot offer credible starting minutes')
    if playing_time=='rotation' and rank>=max(2,slots*3):
        raise ValueError('Borrower does not have adequate rotation opportunities')
    return player,contract


def _move(registry, player, previous: str, next_club: str, *, world=None, key=''):
    if not registry.clubs[previous].squad.contains(player.id) or registry.clubs[next_club].squad.contains(player.id):
        raise ValueError('Loan registration changed before transfer')
    original_morale=player.state.dressing_room_morale
    if world is not None:
        if world._active_journal is None:
            raise RuntimeError('Loan changes require world transaction')
        def undo():
            registry.clubs[next_club].squad._players.pop(player.id,None)
            registry.clubs[previous].squad._players[player.id]=player
            player.state.dressing_room_morale=original_morale
        world._active_journal.undo_callbacks[('loan-move',key,player.id)]=undo
    registry.clubs[previous].squad.remove(player.id)
    registry.clubs[next_club].squad.add(player)
    if player.id in registry.medical_followups:
        _,due=registry.medical_followups[player.id]
        if world is not None:
            world._put(registry.medical_followups,player.id,(next_club,due))
        else:
            registry.medical_followups[player.id]=(next_club,due)


def _begin(session,cmd):
    registry=session._world_squads
    manager=session.home_club.id
    now=session.current_date
    pid=cmd.get('player_id')
    parent=cmd.get('parent_id')
    borrower=cmd.get('borrower_id')
    if type(pid) is not str or type(parent) is not str or type(borrower) is not str:
        raise ValueError('Choose a player, parent club and borrowing club')
    if manager not in (parent,borrower):
        raise ValueError('Only loans involving your club can be requested')
    months=cmd.get('months')
    share=cmd.get('borrower_wage_percent')
    playing=cmd.get('playing_time')
    option=cmd.get('option_gbp')
    purchase=cmd.get('purchase_terms')
    recall=cmd.get('recall_allowed',True)
    if type(recall) is not bool:
        raise ValueError('Recall rights must be true or false')
    if purchase is not None:
        purchase.validate()
        if option!=purchase.guaranteed_gbp:
            raise ValueError('Purchase guarantee does not match option terms')
    player,contract=_can_loan(registry,pid,parent,borrower,now,months,share,playing,option,purchase_terms=purchase)
    # A rival lender requires reasonable salary cover for an important player.
    if parent!=manager and share<25 and contract.weekly_wage_gbp>2000:
        raise ValueError('Parent club wants at least 25% of the wages covered')
    if borrower!=manager:
        plan=squad_plan(registry.clubs[borrower],registry.identities[borrower].primary)
        shortage=any(n['position']==player.primary_position.value for n in plan['vacancies'] if n['layer']<=2)
        if not shortage and playing=='backup':
            raise ValueError('Borrowing club has no need for another backup in this position')
    index=registry.loan_next_id
    registry.loan_next_id+=1
    loan=LoanAgreement(f't26-loan-{index:06d}',pid,parent,borrower,now,
        _date_plus_months(now,months),share,playing,option,
        appearances_at_start=career_player_totals(registry,pid)[0],
        minutes_at_start=sum(u.minutes for u in (*[h.get(pid) for h in registry.history.values()],
                                         registry.usage.get(pid)) if u is not None),
        recall_allowed=recall,purchase_terms=purchase)
    loan.validate()
    _move(registry,player,parent,borrower)
    registry.loans[loan.loan_id]=loan
    for cid in (parent,borrower):
        _repair_selected_team(session,cid)
    registry.validate()
    return {'loan_id':loan.loan_id,'status':'active','player':player.full_name,
            'parent':registry.clubs[parent].name,'borrower':registry.clubs[borrower].name,
            'ends_on':loan.ends_on.isoformat(),'salary_share_percent':share,
            'option_gbp':option,'note':'Contract remains with the parent club; no transfer fee was paid.'}


def _finish_loan(registry,loan,when:date,*,world=None):
    if loan.status!='active':
        raise ValueError('Loan already ended')
    borrower=registry.clubs[loan.borrower_id]
    player=borrower.squad.get(loan.player_id)
    # An evidenced, substantial breach is a sporting consequence for the
    # player. No fake minutes, automatic fines or compulsory purchases.
    if world is not None:
        evaluation=loan_promise_review(world,loan,when)
        if evaluation['assessable'] and evaluation['ratio'] < .40:
            original=player.state.morale
            world._active_journal.undo_callbacks.setdefault(
                ('ts2411-loan-morale',loan.loan_id),
                lambda p=player,old=original: setattr(p.state,'morale',old))
            player.state.adjust_morale(-9 if loan.playing_time=='starter' else -5)
    if not registry.clubs[loan.parent_id].squad.contains(player.id):
        _move(registry,player,loan.borrower_id,loan.parent_id,world=world,key=loan.loan_id)
    concluded=replace(loan,status='returned',completed_on=when)
    if world is None:
        registry.loans[loan.loan_id]=concluded
    else:
        world._put(registry.loans,loan.loan_id,concluded)
    return concluded


def _return(session,cmd):
    registry=session._world_squads
    loan=registry.loans.get(cmd.get('loan_id'))
    if loan is None or loan.status!='active' or loan.parent_id!=session.home_club.id:
        raise ValueError('Only the parent manager can recall an active loan')
    if not loan.recall_allowed:
        raise ValueError('This loan has no negotiated recall right')
    if (session.current_date-loan.started_on).days<30:
        raise ValueError('Loan recall requires a minimum of 30 days')
    _finish_loan(registry,loan,session.current_date)
    for cid in (loan.parent_id,loan.borrower_id):
        _repair_selected_team(session,cid)
    registry.validate()
    return {'loan_id':loan.loan_id,'status':'returned'}


def _register_transfer(session,player, seller_id, buyer_id, price,now, note):
    """Shared, consented immediate purchase; full transfer code settles money."""
    registry=session._world_squads
    if not window_open(now):
        raise ValueError('Permanent transfers require an open transfer window')
    willing, reason=_player_interest(registry,player,seller_id,buyer_id,now)
    if not willing:
        raise ValueError(reason)
    quote=agent_demand(registry,player,seller_id,buyer_id,now)
    # The agreed GUARANTEED total can exceed today's transfer budget when
    # financing is within the club's approved deferred-credit capacity.
    # _finish validates the actual upfront payment and future obligations.
    wage=quote['weekly_wage_gbp']
    terms=note if isinstance(note, TransferTerms) else TransferTerms(price)
    personal=PersonalTerms(wage,quote['years'],quote['role'],0)
    index=registry.transfer_next_id
    registry.transfer_next_id+=1
    deal_id=f't24-{index:06d}'
    event=NegotiationEvent(now,buyer_id,terms,'Borrower exercises the agreed purchase package' if isinstance(note,TransferTerms) else note)
    record=TransferNegotiation(deal_id,player.id,seller_id,buyer_id,now,now+timedelta(days=30),
        'agreed',buyer_id,terms,(event,),personal_status='not_started')
    result=_finish(session,record,personal)
    return result


def _loan_purchase(session,cmd):
    registry=session._world_squads
    loan=registry.loans.get(cmd.get('loan_id'))
    now=session.current_date
    if (loan is None or loan.status!='active' or loan.option_gbp is None
            or loan.borrower_id!=session.home_club.id or now>loan.ends_on):
        raise ValueError('No exercisable purchase option for your club')
    if now < loan.ends_on-timedelta(days=90):
        raise ValueError('Purchase option is exercisable only during the final 90 days of the loan')
    if not window_open(now,registry.clubs[loan.borrower_id].country):
        return _schedule_loan_purchase(session,loan)
    if loan.option_pending_deal_id:
        raise ValueError('The purchase option has already been exercised and scheduled')
    # A consented permanent purchase converts the temporary registration back
    # into a full transfer without modifying or duplicating the Player object.
    player=registry.clubs[loan.borrower_id].squad.get(loan.player_id)
    old_contract=registry.contracts[player.id]
    salary_start=max(registry.finance_review_on,registry.finance_started_on,loan.started_on)
    accrued_share=(round(_month_wage(old_contract,salary_start,now-timedelta(days=1))
                   *loan.borrower_wage_percent/100) if now>salary_start else 0)
    _move(registry,player,loan.borrower_id,loan.parent_id)
    registry.loans[loan.loan_id]=replace(loan,status='purchased',completed_on=now)
    try:
        result=_register_transfer(session,player,loan.parent_id,loan.borrower_id,
                                  loan.option_gbp,now,loan.purchase_terms or 'Borrower exercises agreed loan purchase option')
    except Exception:
        # The caller owns a deep-copied session, so this partial graph is
        # discarded by GameApplication on any exception.
        raise
    if accrued_share:
        parent_account=registry.club_finances[loan.parent_id]
        borrower_account=registry.club_finances[loan.borrower_id]
        registry.club_finances[loan.parent_id]=replace(parent_account,
            cash_gbp=parent_account.cash_gbp+accrued_share,
            season_wages_gbp=max(0,parent_account.season_wages_gbp-accrued_share))
        registry.club_finances[loan.borrower_id]=replace(borrower_account,
            cash_gbp=borrower_account.cash_gbp-accrued_share,
            season_wages_gbp=borrower_account.season_wages_gbp+accrued_share)
    for cid in (loan.parent_id,loan.borrower_id):
        _repair_selected_team(session,cid)
    registry.validate()
    return {'loan_id':loan.loan_id,'status':'purchased','transfer':result}


def _schedule_loan_purchase(session,loan):
    """Agree an option outside the window, settle only on registration day.

    No cash, parent contract or player registration changes at exercise time.
    If registration fails, the player remains at the parent club.
    """
    registry=session._world_squads
    now=session.current_date
    if loan.option_pending_deal_id:
        raise ValueError('This option has already been exercised')
    from football_manager.services.transfer_windows import next_opening
    from football_manager.services.transfer_installments import validate_financing
    from football_manager.services.transfer_personal import _player_interest, agent_demand
    arrival=next_opening(now,registry.clubs[loan.borrower_id].country)
    player=registry.clubs[loan.borrower_id].squad.get(loan.player_id)
    willing, reason=_player_interest(registry,player,loan.parent_id,loan.borrower_id,now)
    if not willing:raise ValueError(reason)
    quote=agent_demand(registry,player,loan.parent_id,loan.borrower_id,now)
    terms=loan.purchase_terms or TransferTerms(loan.option_gbp)
    validate_financing(registry,loan.borrower_id,terms,now)
    from football_manager.services.club_economy import weekly_payroll
    existing=registry.contracts[player.id].weekly_wage_gbp*loan.borrower_wage_percent//100
    acc=registry.club_finances[loan.borrower_id]
    if weekly_payroll(registry,loan.borrower_id)-existing+quote['weekly_wage_gbp']>acc.wage_budget_weekly_gbp:
        raise ValueError('Buyer cannot support the permanent contract wage')
    if registry.contracts[player.id].expires_on < arrival:
        raise ValueError('Parent player contract ends before registration')
    index=registry.transfer_next_id
    registry.transfer_next_id+=1
    deal_id=f't24-{index:06d}'
    personal=PersonalTerms(quote['weekly_wage_gbp'],quote['years'],quote['role'],0)
    event=NegotiationEvent(now,loan.borrower_id,terms,'Borrower exercises the purchase option at the agreed terms')
    negotiation=TransferNegotiation(deal_id,player.id,loan.parent_id,loan.borrower_id,
        now,arrival+timedelta(days=35),'pending_window',loan.borrower_id,terms,(event,),
        reason=f'Loan option signed; registration expected {arrival.isoformat()}',
        personal_status='completed',personal_terms=personal)
    negotiation.validate()
    registry.transfer_offers[deal_id]=negotiation
    registry.loans[loan.loan_id]=replace(loan,option_pending_deal_id=deal_id)
    registry.validate()
    return {'loan_id':loan.loan_id,'status':'pending_window','deal_id':deal_id,
            'arrival_on':arrival.isoformat(),'note':'Purchase option activated; registration and payment deferred'}


def _buyback(session,cmd):
    registry=session._world_squads
    deal=registry.transfer_offers.get(cmd.get('deal_id'))
    now=session.current_date
    manager=session.home_club.id
    if (deal is None or deal.status!='completed' or deal.seller_id!=manager
            or deal.terms.buyback_gbp is None or now>deal.terms.buyback_until):
        raise ValueError('No exercisable buyback agreement')
    if active_loan(registry,deal.player_id):
        raise ValueError('Buyback unavailable while player is on loan')
    if not registry.clubs[deal.buyer_id].squad.contains(deal.player_id):
        raise ValueError('Buyback cannot be exercised after the player changes clubs')
    player=registry.clubs[deal.buyer_id].squad.get(deal.player_id)
    result=_register_transfer(session,player,deal.buyer_id,manager,
                              deal.terms.buyback_gbp,now,'Former owner exercises agreed buyback')
    registry.validate()
    return {'buyback_of':deal.deal_id,'status':'completed','transfer':result}


def _settled_free_agent_review(registry, as_of: date) -> date:
    """Keep a returning free agent behind the next pending global review.

    A manual command may be dated ahead of the simulation clock (including
    restored/legacy sessions and isolated test fixtures). Updating the player's
    ageing beyond the global boundary makes FootballWorld.validate fail and
    can double-charge the following monthly review.
    """
    next_review = registry.development_next_review
    if next_review is None:
        return as_of
    completed = (next_review - timedelta(days=1)).replace(day=1)
    return min(as_of, completed)


def _free_demand(registry,free:FreeAgent,buyer_id:str,now:date):
    player=free.player
    possible,reason=_player_interest(registry,player,free.previous_club_id,buyer_id,now)
    role=_expected_role(registry,player,buyer_id)
    required=max(wage_expectation(player,now,registry.seed,role=role),round(free.previous_wage_gbp*.72))
    max_years=2 if player.age_on(now)>=35 else 3 if player.age_on(now)>=32 else 5
    return {'interested':possible,'reason':reason,'minimum_weekly_gbp':required,
            'role':role,'max_years':max_years}


def _sign_free(session,cmd):
    registry=session._world_squads
    pid=cmd.get('player_id')
    free=registry.free_agents.get(pid)
    if free is None:
        raise ValueError('Player is not available on a free transfer')
    now=session.current_date
    cid=session.home_club.id
    demand=_free_demand(registry,free,cid,now)
    wage=cmd.get('weekly_wage_gbp')
    years=cmd.get('years')
    role=cmd.get('role')
    if (type(wage) is not int or not 75<=wage<=1_500_000
            or type(years) is not int or not 1<=years<=demand['max_years']
            or role not in ('star','important','regular','rotation','backup')):
        raise ValueError('Invalid free agent contract proposal')
    if not demand['interested']:
        raise ValueError(demand['reason'])
    if wage<demand['minimum_weekly_gbp']:
        raise ValueError('Player agent requests at least £%s/week'%demand['minimum_weekly_gbp'])
    if len(registry.clubs[cid].squad)>=45:
        raise ValueError('First-team squad is full')
    acc=registry.club_finances[cid]
    if weekly_payroll(registry,cid)+wage>acc.wage_budget_weekly_gbp:
        raise ValueError('Wage budget does not support this contract')
    # Free agents do not receive club training/matches while unsigned. A
    # return after months out of football must catch up the ageing clock.
    from football_manager.services.player_development import catch_up_unsigned_player
    catch_up_unsigned_player(free.player, _settled_free_agent_review(registry, now))
    registry.clubs[cid].squad.add(free.player)
    registry.contracts[pid]=PlayerContract(pid,cid,now,_date_plus_months(now,years*12),wage,role)
    del registry.free_agents[pid]
    if free.player.aging and free.player.aging.active_injury and free.player.aging.active_injury.return_on:
        registry.medical_followups[pid]=(cid,free.player.aging.active_injury.return_on)
    _repair_selected_team(session,cid)
    registry.validate()
    return {'player_id':pid,'status':'signed','player':free.player.full_name,
            'club':registry.clubs[cid].name,'weekly_wage_gbp':wage,'years':years}


def loan_command(session,command:dict)->dict:
    action=command.get('action')
    if action in ('loan_propose','loan_accept_counter','loan_walk'):
        from football_manager.services.loan_bargaining import loan_talk_command
        return loan_talk_command(session,command)
    if action=='loan_offer':return _begin(session,command)
    if action=='loan_recall':return _return(session,command)
    if action=='loan_buy_option':return _loan_purchase(session,command)
    if action=='buyback':return _buyback(session,command)
    if action=='sign_free_agent':return _sign_free(session,command)
    raise ValueError('Unsupported loan or free-agent operation')


def _world_remove(world,player,club_id:str,key:str):
    reg=world.football_world
    club=reg.clubs[club_id]
    original=player.state.dressing_room_morale
    def undo():
        club.squad._players[player.id]=player
        player.state.dressing_room_morale=original
    world._active_journal.undo_callbacks[('loan-unsigned',key,player.id)]=undo
    club.squad.remove(player.id)
    if player.id in reg.medical_followups:
        old=reg.medical_followups[player.id]
        world._active_journal.undo_callbacks[('loan-medical-prune',key,player.id)]=lambda val=old: reg.medical_followups.__setitem__(player.id,val)
        del reg.medical_followups[player.id]


def _expire_professionals(world,as_of:date):
    reg=world.football_world
    dropped=0
    for cid,club in sorted(reg.clubs.items()):
        for player in tuple(club.squad.players):
            contract=reg.contracts.get(player.id)
            if (contract is None or contract.kind!='professional' or contract.expires_on>=as_of
                    or active_loan(reg,player.id)):
                continue
            # Never dismantle the functional XI or the two-keeper baseline.
            if len(club.squad)<=17:
                continue
            if player.primary_position.value=='GK' and sum(p.primary_position.value=='GK' for p in club.squad.players)<=2:
                continue
            if not can_spare(club,reg.identities[cid].primary,player.id):
                continue
            _world_remove(world,player,cid,'expired-'+str(as_of))
            # Remove the old contract with explicit undo, not _put(None).
            journal=world._active_journal
            journal.undo_callbacks.setdefault(('loan-contract-pop',player.id),
                  lambda val=contract: reg.contracts.__setitem__(player.id,val))
            reg.contracts.pop(player.id,None)
            world._put(reg.free_agents,player.id,FreeAgent(player,cid,as_of,contract.weekly_wage_gbp))
            for did,offer in tuple(reg.transfer_offers.items()):
                if offer.player_id==player.id and offer.status in ('manager_turn','agreed','pending_window'):
                    world._put(reg.transfer_offers,did,replace(offer,status='expired',reason='Contract expired'))
            dropped+=1
    return dropped


def _sign_ai_free(world,as_of:date):
    """Hire released players where they fill a *real* tactical vacancy.

    A tight board budget can prevent a signing. Rivals get a rotating, seeded
    priority order based on their uncovered XI/bench spots, not the spelling
    of the club name. Secondary positional familiarity counts, without using
    the same versatile player twice in squad_planning.
    """
    from football_manager.data.english_players import stable_seed
    reg=world.football_world
    manager=reg.youth.managed_club_id if reg.youth else None
    signings=0
    available=sorted(reg.free_agents.items(),key=lambda item:(
        -item[1].player.overall_rating,item[1].player.age_on(as_of),item[0]))
    buyers=[]
    for cid,club in reg.clubs.items():
        if cid==manager or len(club.squad)>=29:
            continue
        plan=squad_plan(club,reg.identities[cid].primary)
        needs=[v for v in plan['vacancies'] if v['layer']<=2]
        future=imminent_succession_needs(club,reg.identities[cid].primary,as_of,plan)
        existing={(v['layer'],v['position']) for v in needs}
        needs.extend(v for v in future if (v['layer'],v['position']) not in existing)
        if not needs:
            continue
        xi=sum(n['layer']==1 for n in needs)
        buyers.append((-xi,-len(needs),
                       stable_seed(reg.seed,'ts248-free-turn',cid,as_of.isoformat()),
                       cid,club,needs))
    for _,_,_,cid,club,needs in sorted(buyers):
        if signings>=24:
            break
        for pid,free in available:
            if pid not in reg.free_agents:
                continue
            pl=free.player
            fitting=[v for v in needs if pl.familiarity_for(Position(v['position'])) >= 70
                     and ((pl.primary_position is Position.GK) == (v['position'] == 'GK'))]
            if not fitting:
                continue
            if all(v.get('succession') for v in fitting) and pl.age_on(as_of)>32:
                continue  # don't replace a pensioner with another near-retiree
            demand=_free_demand(reg,free,cid,as_of)
            if not demand['interested']:
                continue
            wage=demand['minimum_weekly_gbp']
            acc=reg.club_finances[cid]
            if weekly_payroll(reg,cid)+wage>acc.wage_budget_weekly_gbp:
                continue
            if acc.cash_gbp<max(10_000,wage*4):
                continue
            from football_manager.services.player_development import catch_up_unsigned_player
            catch_up_unsigned_player(pl, _settled_free_agent_review(reg, as_of), world=world)
            old_morale=pl.state.dressing_room_morale
            world._active_journal.undo_callbacks[('loan-ai-sign',pid)]=lambda c=club,p=pl,m=old_morale:(c.squad._players.pop(p.id,None),setattr(p.state,'dressing_room_morale',m))
            club.squad.add(pl)
            world._put(reg.contracts,pid,PlayerContract(pid,cid,as_of,
                    _date_plus_months(as_of,2*12),wage,demand['role']))
            old=reg.free_agents[pid]
            world._active_journal.undo_callbacks[('loan-ai-free-pop',pid)]=lambda val=old: reg.free_agents.__setitem__(pid,val)
            del reg.free_agents[pid]
            if pl.aging and pl.aging.active_injury and pl.aging.active_injury.return_on:
                world._put(reg.medical_followups,pid,(cid,pl.aging.active_injury.return_on))
            signings+=1
            break
    return signings


def _retire_old_unsigned(world,boundary:date)->int:
    """Respect the individual retirement decision even without a contract.

    Free agents keep ageing without fictional minutes. An inactive player is
    NOT retired solely for being 39 or unemployed: the player must actually
    reach their own career-ending decision first. Older unsigned profiles
    are caught up monthly after 12 months without a club.
    """
    from football_manager.domain.player_aging import RetiredPlayer
    from football_manager.services.player_development import catch_up_unsigned_player
    reg=world.football_world
    count=0
    for pid,entry in tuple(reg.free_agents.items()):
        p=entry.player
        old=p.aging
        if old is None:
            continue
        decided=(old.retirement_status in ('requested','deferred')
                 and old.retirement_requested_on <= boundary)
        if not decided:
            if p.age_on(boundary)<39 or (boundary-entry.released_on).days<365:
                continue
            catch_up_unsigned_player(p,boundary,world=world)
            decided=(p.aging.retirement_status in ('requested','deferred')
                     and p.aging.retirement_requested_on <= boundary)
        if not decided:
            continue
        previous=p.aging
        world._active_journal.undo_callbacks.setdefault(
            ('free-retirement-profile',pid),
            lambda target=p,profile=previous: setattr(target,'aging',profile))
        p.aging=replace(previous,retirement_status='retired',
            retirement_checked_on=boundary,retired_on=boundary)
        archive=RetiredPlayer(p,entry.previous_club_id,boundary)
        archive.validate()
        old_free=reg.free_agents[pid]
        world._active_journal.undo_callbacks[('free-retirement-pop',pid)]=(
            lambda key=pid,val=old_free: reg.free_agents.__setitem__(key,val))
        reg.free_agents.pop(pid)
        world._put(reg.retired_players,pid,archive)
        count+=1
    return count


def _career_minutes(registry, pid: str) -> int:
    """Cumulative actual participation; stable across season rollover."""
    return sum(u.minutes for u in (*[season.get(pid) for season in registry.history.values()],
                                   registry.usage.get(pid)) if u is not None)


def loan_promise_review(world, loan: LoanAgreement, when: date) -> dict:
    """Evidence-based review, with no fictional appearances.

    Club-season stress runs with synthetic scorelines have no processed real
    matches: those loans are NOT punished for zero artificial match minutes.
    Injured players are not treated as a deliberate broken playing-time promise.
    """
    reg=world.football_world
    end=min(when,loan.ends_on)
    days=max(0,(end-loan.started_on).days)
    real_fixtures=sum(1 for fid in reg.processed_fixtures if
        fid in world.fixtures and
        world.fixtures[fid].match_date is not None and
        loan.started_on <= world.fixtures[fid].match_date < end and
        loan.borrower_id in (world.fixtures[fid].home_club_id,world.fixtures[fid].away_club_id))
    played=max(0,_career_minutes(reg,loan.player_id)-loan.minutes_at_start)
    monthly={'starter':155,'rotation':65,'backup':15}[loan.playing_time]
    target=min(round(days/30.44*monthly),real_fixtures*90)
    owner=reg.clubs[loan.borrower_id].squad._players.get(loan.player_id)
    injured=bool(owner is not None and
                 (owner.state.injury is not None or owner.state.suspended_matches>0 or
                  owner.aging is not None and owner.aging.active_injury is not None))
    assessable=(days>=90 and real_fixtures>=6 and target>=90 and not injured
                and loan.playing_time!='backup')
    return {'assessable':assessable,'minutes':played,'target':target,
            'matches':real_fixtures,'ratio':played/max(1,target)}


def process_ai_loans(world, boundary: date) -> list[dict]:
    """Small bounded AI-AI market, after the settled transfer window.

    Only squad needs and plausible playing time yield a loan. No club profile
    or new persisted graph field is introduced in TS-24.11. Manager clubs
    never gain or lose players from this autonomous routine.
    """
    from football_manager.data.english_players import stable_seed
    from football_manager.services.transfer_windows import window_open
    reg=world.football_world
    if reg is None or world._active_journal is None:
        raise RuntimeError('AI loan market requires a world transaction')
    offered=boundary-timedelta(days=1)
    if not window_open(offered):
        return []
    manager=reg.youth.managed_club_id if reg.youth else None
    # Clubs penalize counterparties with a previous, documented AI early recall.
    broken_pairs={(l.parent_id,l.borrower_id) for l in reg.loans.values()
                  if l.loan_id.startswith('t2411-ai-loan-') and
                  l.status=='returned' and l.completed_on is not None and
                  l.completed_on < l.ends_on}
    plans={cid:squad_plan(c,reg.identities[cid].primary)
           for cid,c in reg.clubs.items() if cid!=manager and reg.identities[cid].tier in (1,2,3,4)}
    lender_pool=[]
    for cid,plan in plans.items():
        club=reg.clubs[cid]
        if len(club.squad)<=20:
            continue
        # Loan only a young deputy whom the parent can really spare.
        options=[]
        for row in plan['assignments']:
            if row['layer']!=2 or row['position']=='GK':
                continue
            pl=club.squad.get(row['player_id'])
            contract=reg.contracts.get(pl.id)
            if (pl.age_on(boundary)>24 or pl.age_on(boundary)<17 or
                    contract is None or contract.club_id!=cid or
                    contract.expires_on < _date_plus_months(boundary,6) or
                    active_loan(reg,pl.id)):
                continue
            if not can_spare(club,reg.identities[cid].primary,pl.id,before=plan):
                continue
            options.append(pl)
        options.sort(key=lambda p:(p.age_on(boundary),p.overall_rating,p.id))
        for pl in options[:5]:
            lender_pool.append((cid,pl))
    if not lender_pool:
        return []
    entrants=[]
    received=set()
    sent=set()
    borrower_ids=sorted(plans,key=lambda cid:(stable_seed(reg.seed,'ts2411-borrow',boundary,cid),cid))
    for borrower in borrower_ids:
        if len(entrants)>=10:
            break
        club=reg.clubs[borrower]
        if len(club.squad)>=32 or sum(l.status=='active' and l.borrower_id==borrower for l in reg.loans.values())>=MAX_LOANS_PER_BORROWER:
            continue
        plan=squad_plan(club,reg.identities[borrower].primary)
        # Real uncovered places first; a prepared youth can also strengthen a
        # weak starter without displacing two existing squad members at once.
        needs=[v for v in plan['vacancies'] if v['layer']<=2]
        if not needs:
            starters=sorted((v for v in plan['assignments'] if v['layer']==1 and v['position']!='GK'),
                            key=lambda v:(club.squad.get(v['player_id']).overall_rating,v['slot_id']))
            needs=[dict(row,layer=4) for row in starters[:2]]
        shortlisted=[]
        for parent,pl in lender_pool:
            if parent==borrower or parent in sent or (parent,borrower) in broken_pairs or pl.id in received:
                continue
            if reg.identities[parent].tier>reg.identities[borrower].tier:
                continue # development loans normally move laterally or down a division
            for need in needs:
                pos=Position(need['position'])
                if pl.familiarity_for(pos)<75:
                    continue
                if need['layer']==4:
                    rival=club.squad.get(need['player_id'])
                    if pl.overall_rating_for(pos)<rival.overall_rating_for(pos)+3:
                        continue
                # Salary share chosen to be affordable rather than invented.
                wage=reg.contracts[pl.id].weekly_wage_gbp
                remaining=max(0,reg.club_finances[borrower].wage_budget_weekly_gbp-weekly_payroll(reg,borrower))
                share=next((pct for pct in (75,50,25,0) if round(wage*pct/100)<=remaining),None)
                if share is None:
                    continue
                # A lender has a reason to subsidize a developing prospect,
                # but no club takes financial liability without affordability.
                role='starter' if need['layer'] in (1,4) else 'rotation'
                for months in (12,6):
                    try:
                        _can_loan(reg,pl.id,parent,borrower,offered,months,share,role,None,
                                  registration_on=boundary)
                    except ValueError:
                        continue
                    grade=(100 if need['layer']==1 else 55 if need['layer']==2 else 30)
                    score=(grade+pl.overall_rating_for(pos)*.30-pl.age_on(boundary)*.18+
                           stable_seed(reg.seed,'ts2411-choice',pl.id,borrower,boundary)%100/100)
                    shortlisted.append((score,parent,pl,months,share,role))
                    break
                break
        if not shortlisted:
            continue
        _,parent,pl,months,share,role=max(shortlisted,key=lambda x:(x[0],x[2].id))
        current=reg.loan_next_id
        world._active_journal.undo_callbacks.setdefault(
            ('ts2411-ai-loan-seq',id(reg)),lambda n=current:setattr(reg,'loan_next_id',n))
        reg.loan_next_id+=1
        agreement=LoanAgreement(f't2411-ai-loan-{current:06d}',pl.id,parent,borrower,
                                boundary,_date_plus_months(boundary,months),share,role,
                                appearances_at_start=career_player_totals(reg,pl.id)[0],
                                minutes_at_start=_career_minutes(reg,pl.id))
        agreement.validate()
        _move(reg,pl,parent,borrower,world=world,key=agreement.loan_id)
        world._put(reg.loans,agreement.loan_id,agreement)
        entrants.append({'loan_id':agreement.loan_id,'parent_id':parent,'borrower_id':borrower,
                         'player_id':pl.id,'months':months,'wage_share':share,'role':role})
        sent.add(parent)
        received.add(pl.id)
    return entrants


def review_loan_month(world,boundary:date)->dict:
    """Called after paying the prior month, before new-window recruitment."""
    reg=world.football_world
    if world._active_journal is None:
        raise RuntimeError('Loan reviews need world transaction')
    returned=0
    recalled=0
    manager=reg.youth.managed_club_id if reg.youth else None
    for loan in tuple(reg.loans.values()):
        if loan.status!='active':
            continue
        if (loan.option_pending_deal_id and
                window_open(boundary,reg.clubs[loan.borrower_id].country)):
            _finish_loan(reg,loan,boundary,world=world)
            returned+=1
        elif loan.ends_on<=boundary:
            _finish_loan(reg,loan,boundary,world=world)
            returned+=1
        elif (loan.loan_id.startswith('t2411-ai-loan-')
              and manager not in (loan.parent_id,loan.borrower_id)
              and (boundary-loan.started_on).days>=180):
            assessment=loan_promise_review(world,loan,boundary)
            # Allow a natural sporting mistake, but not a player parked
            # indefinitely after six months of genuine match evidence.
            if assessment['assessable'] and assessment['ratio'] < .25:
                _finish_loan(reg,loan,boundary,world=world)
                recalled+=1
    from football_manager.services.loan_bargaining import settle_pending_loan_talks
    pending_registered=settle_pending_loan_talks(world,boundary)
    released=_expire_professionals(world,boundary)
    signed=_sign_ai_free(world,boundary)
    retired=_retire_old_unsigned(world,boundary)
    return {'returned':returned,'newly_registered':pending_registered,'breach_recalls':recalled,
            'released':released,'free_agent_signings':signed,'unsigned_retired':retired}


def loan_read_model(session)->dict:
    reg=session._world_squads
    manager=session.home_club.id
    day=session.current_date
    reports=reg.club_support[manager].scouting_reports if manager in reg.club_support else {}
    def person(p, own=True):
        known=own or p.overall_rating >= 85 or p.id in reports
        return {'id':p.id,'name':p.full_name,'position':p.primary_position.value,
                'nationality':p.identity.nationality,'age':p.age_on(day),
                'ovr':round(p.overall_rating,1) if known else None}
    deals=[]
    for item in sorted(reg.loans.values(),key=lambda x:x.started_on,reverse=True):
        if manager not in (item.parent_id,item.borrower_id): continue
        where=item.borrower_id if item.status in ('active','purchased') else item.parent_id
        p=reg.clubs[where].squad._players.get(item.player_id)
        if p is None:
            p=reg.free_agents.get(item.player_id)
            p=p.player if p else None
        if p is None and item.player_id in reg.retired_players:
            p=reg.retired_players[item.player_id].player
        appearances=career_player_totals(reg,item.player_id)[0]-item.appearances_at_start
        total_minutes=sum(u.minutes for u in (*[h.get(item.player_id) for h in reg.history.values()],
                               reg.usage.get(item.player_id)) if u is not None)
        loan_minutes=max(0,total_minutes-item.minutes_at_start)
        elapsed=max(0,(min(day,item.completed_on or day,item.ends_on)-item.started_on).days)
        # Two-to-four youth/senior appearances per month; targets are guidance
        # for the borrower rather than automatic guaranteed starts.
        target_per_month={'starter':155,'rotation':65,'backup':15}[item.playing_time]
        target_minutes=round(elapsed / 30.44 * target_per_month)
        review=(loan_promise_review(session._world,item,day) if item.status=='active' else None)
        deals.append({'id':item.loan_id,'player':person(p) if p else {'id':item.player_id,'name':item.player_id},
                      'parent_id':item.parent_id,'parent':reg.clubs[item.parent_id].name,
                      'borrower_id':item.borrower_id,'borrower':reg.clubs[item.borrower_id].name,
                      'status':item.status,'ends_on':item.ends_on.isoformat(),
                      'completed_on':item.completed_on.isoformat() if item.completed_on else None,
                      'wage_percent':item.borrower_wage_percent,'playing_time':item.playing_time,
                      'option_gbp':item.option_gbp,'recall_allowed':item.recall_allowed,
                      'option_pending_deal_id':item.option_pending_deal_id,
                      'purchase_terms':( __import__('football_manager.services.transfer_negotiation',fromlist=['terms_as_json']).terms_as_json(item.purchase_terms) if item.purchase_terms else None),
                      'option_exercisable':item.status=='active' and item.option_gbp is not None and item.option_pending_deal_id is None and day>=item.ends_on-timedelta(days=90),
                      'appearances':max(0,appearances),
                      'minutes':loan_minutes,'target_minutes':target_minutes,
                      'playing_time_on_track':(review is None or not review['assessable'] or
                                               review['ratio']>=.75),
                      'verified_target_minutes':review['target'] if review else None,
                      'real_borrower_matches':review['matches'] if review else None,
                      'promise_risk':bool(review and review['assessable'] and review['ratio']<.75)})
    outgoing=[person(p)|{'club_id':manager,'club':reg.clubs[manager].name,
               'weekly_gbp':reg.contracts[p.id].weekly_wage_gbp}
              for p in reg.clubs[manager].squad.players
              if p.id in reg.contracts and reg.contracts[p.id].kind=='professional'
              and reg.contracts[p.id].club_id==manager and active_loan(reg,p.id) is None]
    incoming=[]
    for cid,club in reg.clubs.items():
        if cid==manager:continue
        for p in club.squad.players:
            con=reg.contracts.get(p.id)
            if (con and con.club_id==cid and con.kind=='professional'
                    and active_loan(reg,p.id) is None and con.expires_on>_date_plus_months(day,6)):
                incoming.append(person(p,own=False)|{'club_id':cid,'club':club.name,
                          'weekly_gbp':None})
    # The loan search should surface attainable young reinforcements first,
    # instead of truncating a worldwide OVR-descending list to 250 stars.
    manager_account=reg.club_finances[manager]
    wage_room=max(0,manager_account.wage_budget_weekly_gbp-weekly_payroll(reg,manager))
    plan=squad_plan(reg.clubs[manager],reg.identities[manager].primary)
    needs={v['position'] for v in plan['vacancies'] if v['layer']<=2}
    mean_ovr=(sum(p.overall_rating for p in reg.clubs[manager].squad.players) /
              max(1,len(reg.clubs[manager].squad)))
    # Sorting must not expose a player's hidden OVR or salary indirectly.
    incoming.sort(key=lambda p:(p['position'] not in needs,p['age']>23,p['age'],p['name'],p['id']))
    free=[]
    for pid,entry in reg.free_agents.items():
        demand=_free_demand(reg,entry,manager,day)
        free.append(person(entry.player)|{'previous_club':reg.clubs[entry.previous_club_id].name,
            'released_on':entry.released_on.isoformat(),
            'minimum_weekly_gbp':demand['minimum_weekly_gbp'],
            'role':demand['role'],'max_years':demand['max_years'],
            'interested':demand['interested'],'reason':demand['reason']})
    free.sort(key=lambda p:(-p['ovr'],p['id']))
    buybacks=[]
    for offer in reg.transfer_offers.values():
        if (offer.seller_id==manager and offer.status=='completed'
                and offer.terms.buyback_gbp is not None
                and offer.terms.buyback_until>=day
                and reg.clubs[offer.buyer_id].squad.contains(offer.player_id)):
            pl=reg.clubs[offer.buyer_id].squad.get(offer.player_id)
            buybacks.append({'deal_id':offer.deal_id,'player':person(pl),
                'club':reg.clubs[offer.buyer_id].name,
                'price_gbp':offer.terms.buyback_gbp,'until':offer.terms.buyback_until.isoformat()})
    from football_manager.services.loan_bargaining import public_loan_talk
    return {'as_of':day.isoformat(),'window_open':window_open(day),
            'manager_club_name':reg.clubs[manager].name,
            'negotiations':[public_loan_talk(t,reg) for t in sorted(reg.loan_talks.values(),key=lambda t:t.started_on,reverse=True) if manager in (t.parent_id,t.borrower_id)],
            'manager_club_id':manager,'loans':deals,'outgoing':outgoing,
            'incoming':incoming[:250],'free_agents':free[:150],'buybacks':buybacks,
            'destinations':[{'id':cid,'name':club.name,'tier':reg.identities[cid].tier}
                            for cid,club in reg.clubs.items() if cid!=manager],
            'summary':{'active':sum(l.status=='active' for l in reg.loans.values()),
                       'unsigned':len(reg.free_agents)}}
