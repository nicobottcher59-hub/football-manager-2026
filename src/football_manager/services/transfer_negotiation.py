"""TS-24.3/24.4 club negotiations and personal-agreement handoff.

Club agreement still reserves funds. TS-24.4 finalises only after player
consent and a registered contract; both manager and AI use shared rules.
"""
from __future__ import annotations

from dataclasses import replace
from datetime import date, timedelta
from hashlib import sha256
from math import ceil

from football_manager.domain.market_valuation import SaleContext, asking_band
from football_manager.domain.transfer_negotiation import (
    TransferBonus, TransferTerms, NegotiationEvent, TransferNegotiation,
)
from football_manager.services.market_valuation import format_gbp


def _unit(seed: int, *parts: object) -> float:
    raw = sha256((':'.join(str(x) for x in ('ts24-3',seed,*parts))).encode()).digest()
    return int.from_bytes(raw[:8], 'big') / 2**64


def _player(registry, player_id: str, seller_id: str):
    if seller_id not in registry.clubs:
        raise ValueError('Unknown selling club')
    if player_id not in registry.clubs[seller_id].squad._players:
        raise ValueError('Player is not professionally registered with the seller')
    contract = registry.contracts.get(player_id)
    if contract is None or contract.club_id != seller_id or contract.kind != 'professional':
        raise ValueError('Player has no valid professional contract')
    return registry.clubs[seller_id].squad.get(player_id), contract


def _quote(registry, player):
    result = registry.market_values.get(player.id)
    if result is None:
        from football_manager.domain.market_valuation import market_value_for_player
        result = market_value_for_player(player,registry.market_review_on or registry.created_on,registry.seed)
    return result


def _months_remaining(contract, on_date: date) -> int:
    return max(0, ceil((contract.expires_on - on_date).days / 30.4375))


def _seller_target(registry, seller_id: str, buyer_id: str, player, contract, on_date: date) -> int:
    seller=registry.clubs[seller_id]
    ordered=sorted(seller.squad.players,key=lambda p:-p.overall_rating)
    rank=next((i for i,p in enumerate(ordered) if p.id==player.id),len(ordered))
    important = ('indispensable' if rank<3 else 'key' if rank<10 else 'regular' if rank<18 else 'rotation')
    # A club with a similar division AND similarly strong team is a direct
    # sporting competitor; being in the same league alone is not a rivalry.
    sr=registry.identities[seller_id].tier
    br=registry.identities[buyer_id].tier
    def avg(cid):
        ps=registry.clubs[cid].squad.players
        return sum(p.overall_rating for p in ps[:min(len(ps),22)])/max(1,min(len(ps),22))
    close_rival=sr==br and abs(avg(seller_id)-avg(buyer_id))<5 and sr>0
    band=asking_band(_quote(registry,player),SaleContext(
        contract_months=_months_remaining(contract,on_date), importance=important,
        direct_rival=close_rival, replacement_ready=rank>=18))
    if band.low_gbp == 0:
        return 0
    adjustment=.95 + .09*_unit(registry.seed,'sale-policy',seller_id,player.id,registry.season_label)
    return max(5_000,round(band.low_gbp*adjustment/5_000)*5_000)


def _availability(registry, club_id: str, on_date: date, exclude_id: str = '') -> int:
    account=registry.club_finances[club_id]
    reserve=sum(deal.terms.fixed_gbp for deal in registry.transfer_offers.values()
                if deal.deal_id != exclude_id and deal.buyer_id==club_id
                and (deal.status=='agreed' or (deal.status=='manager_turn'
                     and registry.youth is not None
                     and deal.seller_id==registry.youth.managed_club_id))
                and deal.expires_on >= on_date)
    return max(0,min(account.transfer_budget_gbp,max(0,int(account.cash_gbp*.85)))-reserve)


def _probability(bonus: TransferBonus, player, buyer_tier: int, on_date: date) -> float:
    """Expected real achievability, not the size of a speculative jackpot."""
    ovr=player.overall_rating
    if bonus.kind=='appearances':
        # No automatic promise of first-team starts at a top-division club.
        threshold=bonus.threshold
        return max(.08,min(.86,(.88 if threshold<=20 else .72 if threshold<=35 else .47) *
                             (1 if player.age_on(on_date)>=19 else .7) *
                             (1 if buyer_tier>=2 or ovr>=78 else .8)))
    if bonus.kind in ('goals','assists'):
        pos=player.primary_position.value
        attacking = pos in ('ST','SS','LW','RW','AM')
        baseline=.68 if attacking else .20 if pos in ('CM','LCM','RCM','DM') else .07
        if bonus.kind=='assists':
            baseline *= 1.1 if pos in ('AM','LW','RW') else .8
        return max(.01,min(.82,baseline * (12/bonus.threshold)**1.12))
    # Promotion is a meaningful but uncertain collective outcome.
    return {1:.005,2:.16,3:.21,4:.22,0:.10}.get(buyer_tier,.10)


def assess_terms(registry, player, buyer_id: str, terms: TransferTerms, on_date: date) -> dict:
    """Same price weights for every club, no manager/buyer cheats.

    Risk discount applies on top of event probabilities. Even huge unlikely
    awards cannot replace a sensible fixed sum.
    """
    terms.validate()
    value=_quote(registry,player).value_gbp
    tier=registry.identities[buyer_id].tier
    forecasts=[]
    bonus_expected=0
    for b in terms.bonuses:
        p=_probability(b,player,tier,on_date)
        # Uncertain payments carry an additional downside discount of 18%-42%.
        discounted=round(b.amount_gbp*p*(.58 + .24*p))
        bonus_expected+=discounted
        forecasts.append({'kind':b.kind,'threshold':b.threshold,'amount_gbp':b.amount_gbp,
                          'probability_pct':round(p*100),'risk_adjusted_gbp':discounted})
    age=player.age_on(on_date)
    # Future resale is a possibility rather than a guaranteed payment.
    resale_chance=max(.03,min(.55,(34-age)*.021))
    profit_factor=.38 if terms.sell_on_type=='profit' else .75
    future_sale=round(value*resale_chance*profit_factor*terms.sell_on_percent/100*.67)
    # Buyback is favorable to SELLER but is not immediate income. Consent is
    # still required when exercised in a future transfer implementation.
    buyback_value=0
    if terms.buyback_gbp is not None:
        time_left=(terms.buyback_until-on_date).days
        if time_left<=0 or time_left>365*5:
            raise ValueError('Buyback must expire within 5 years in the future')
        if terms.buyback_gbp <= terms.fixed_gbp:
            raise ValueError('Buyback price must exceed the guaranteed fee')
        buyback_value=round(min(value*.12,max(0,value*1.65-terms.buyback_gbp)*.16))
    # A generous clause menu cannot replace essentially all guaranteed cash.
    unsecured=min(bonus_expected+future_sale+buyback_value, max(value*.38,terms.fixed_gbp*.70))
    adjusted=terms.fixed_gbp + round(unsecured)
    return {'fixed_gbp':terms.fixed_gbp,'headline_gbp':terms.fixed_gbp+sum(b.amount_gbp for b in terms.bonuses),
            'risk_adjusted_gbp':adjusted,'bonuses':forecasts,'resale_expected_gbp':future_sale,
            'buyback_expected_gbp':buyback_value,'uncertain_gbp':round(unsecured)}


def _quote_terms(registry, player, terms: TransferTerms, buyer_id: str, on_date: date):
    result=assess_terms(registry,player,buyer_id,terms,on_date)
    return result['risk_adjusted_gbp']


def _make_counter(terms: TransferTerms, target: int, offered: int, buyer_budget: int) -> TransferTerms | None:
    # Requiring more guaranteed money for a risky package is deliberate.
    bump=max(5_000,int((target-offered)*.92))
    fixed=max(terms.fixed_gbp+5_000,terms.fixed_gbp+bump)
    fixed=(fixed+4_999)//5_000*5_000
    if fixed > min(500_000_000,buyer_budget):
        return None
    return replace(terms,fixed_gbp=fixed)


def _terms_from_data(raw: dict, as_of: date, value: int) -> TransferTerms:
    if not isinstance(raw,dict):
        raise ValueError('Offer terms must be a JSON object')
    allowed={'fixed_gbp','bonuses','sell_on_type','sell_on_percent','buyback_gbp','buyback_until'}
    if set(raw)-allowed:
        raise ValueError('Unknown offer term')
    bs=raw.get('bonuses',[])
    if not isinstance(bs,list) or len(bs)>3:
        raise ValueError('At most three bonuses allowed')
    bonus=[]
    for b in bs:
        if not isinstance(b,dict) or set(b)!={'kind','threshold','amount_gbp'}:
            raise ValueError('Invalid bonus fields')
        bonus.append(TransferBonus(b['kind'],b['threshold'],b['amount_gbp']))
    try:
        until=date.fromisoformat(raw['buyback_until']) if raw.get('buyback_until') is not None else None
    except (ValueError,TypeError) as exc:
        raise ValueError('Invalid buyback expiration date') from exc
    terms=TransferTerms(raw.get('fixed_gbp'),tuple(bonus),raw.get('sell_on_type','none'),
                        raw.get('sell_on_percent',0),raw.get('buyback_gbp'),until)
    terms.validate()
    if terms.fixed_gbp + sum(b.amount_gbp for b in terms.bonuses) > 1_000_000_000:
        raise ValueError('Excessive headline valuation')
    if terms.buyback_until is not None and terms.buyback_until <= as_of:
        raise ValueError('Buyback must be valid in the future')
    return terms


def _status(reason: str, status: str, latest: TransferNegotiation) -> dict:
    return {'deal_id':latest.deal_id,'status':status,'reason':reason,
            'fixed_gbp':latest.terms.fixed_gbp, 'expires_on':latest.expires_on.isoformat(),
            'pending_player_consent':status=='agreed'}


def _manager_club(session) -> str:
    return session.home_club.id


def _apply_ai_reply(registry, offer: TransferNegotiation, on_date: date) -> TransferNegotiation:
    """Immediate deterministic evaluation by the other club; no random luck."""
    player,contract=_player(registry,offer.player_id,offer.seller_id)
    manager_id=registry.youth.managed_club_id if registry.youth else ''
    seller_is_ai=offer.seller_id!=manager_id
    buyer_budget=_availability(registry,offer.buyer_id,on_date,offer.deal_id)
    evaluation=_quote_terms(registry,player,offer.terms,offer.buyer_id,on_date)
    required=_seller_target(registry,offer.seller_id,offer.buyer_id,player,contract,on_date)
    if seller_is_ai and offer.buyer_id==manager_id:
        from football_manager.services.ai_squad_planning import squad_plan
        seller=registry.clubs[offer.seller_id]
        tactic=registry.identities[offer.seller_id].primary
        before=squad_plan(seller,tactic)
        after=squad_plan(seller,tactic,excluded_id=player.id)
        if after['starters_covered'] < before['starters_covered']:
            required=round(required*1.65/5_000)*5_000
        elif after['backups_covered'] < before['backups_covered']:
            required=round(required*1.25/5_000)*5_000
    fixed=offer.terms.fixed_gbp
    if fixed>buyer_budget:
        return replace(offer,status='rejected',reason='Buyer cannot finance the guaranteed upfront fee')
    # In principle a club will never accept a no-money deal hidden behind bonuses.
    if seller_is_ai:
        if required<=0:
            return replace(offer,status='rejected',reason='Seller has no valid contracted price')
        if evaluation>=required and fixed>=max(5_000,round(required*.32)):
            return replace(offer,status='agreed',expires_on=on_date+timedelta(days=45),
                           reason='Club terms agreed; awaiting player consent')
        if evaluation<required*.48:
            return replace(offer,status='rejected',reason='Offer too far below the seller valuation')
        if offer.refusal_count>=5:
            return replace(offer,status='rejected',reason='Seller closed negotiations after repeated low offers')
        counter=_make_counter(offer.terms,required,evaluation,buyer_budget)
        if counter is None:
            return replace(offer,status='rejected',reason='Required guaranteed fee exceeds buyer budget')
        event=NegotiationEvent(on_date,offer.seller_id,counter,'Seller counteroffer: more guaranteed money required')
        return replace(offer,terms=counter,proposed_by=offer.seller_id,
                       events=(*offer.events,event),refusal_count=offer.refusal_count+1,
                       expires_on=on_date+timedelta(days=21),status='manager_turn',
                       reason='Seller values uncertain clauses below their maximum headline')
    # AI buyer: max willingness tied to its valuation AND its liquidity.
    value=_quote(registry,player).value_gbp
    ceiling=min(buyer_budget,int(value*(1.15+.23*_unit(registry.seed,'demand',offer.buyer_id,player.id))))
    if fixed > ceiling or evaluation > ceiling*1.10:
        if offer.refusal_count>=5 or fixed>ceiling*1.75:
            return replace(offer,status='rejected',reason='Buyer refused the price')
        counter=replace(offer.terms,fixed_gbp=max(5_000,(int(min(ceiling, fixed*.82))//5_000)*5_000))
        if counter==offer.terms or counter.fixed_gbp>buyer_budget:
            return replace(offer,status='rejected',reason='Buyer refused the requested price')
        event=NegotiationEvent(on_date,offer.buyer_id,counter,'Buyer counteroffer based on financial ceiling')
        return replace(offer,terms=counter,proposed_by=offer.buyer_id,events=(*offer.events,event),
                       refusal_count=offer.refusal_count+1,expires_on=on_date+timedelta(days=21),
                       status='manager_turn',reason='Buyer is seeking a lower guaranteed fee')
    if evaluation>=required*.58:  # Manager-as-seller may accept a lower amount.
        return replace(offer,status='agreed',expires_on=on_date+timedelta(days=45),
                       reason='Club terms agreed; awaiting player consent')
    return replace(offer,status='rejected',reason='Buyer withdrew after unfavorable revised terms')


def initialize_transfer_market(registry, on_date: date) -> None:
    if registry.transfer_last_review_on is None:
        registry.transfer_last_review_on=on_date.replace(day=1)


def _can_start(registry, player_id: str, seller_id: str, buyer_id: str, on_date: date) -> None:
    if seller_id==buyer_id or seller_id not in registry.clubs or buyer_id not in registry.clubs:
        raise ValueError('Invalid buying or selling club')
    _player(registry,player_id,seller_id)
    if any(d.player_id==player_id and d.status in ('manager_turn','agreed') and d.expires_on>=on_date
           and d.buyer_id==buyer_id for d in registry.transfer_offers.values()):
        raise ValueError('A live negotiation already exists for this player and buyer')


def _create_offer(registry, player_id: str, seller: str, buyer: str, as_of: date,
                  terms: TransferTerms, proposal_by: str, status='manager_turn') -> TransferNegotiation:
    index=registry.transfer_next_id
    registry.transfer_next_id+=1
    event=NegotiationEvent(as_of,proposal_by,terms,'Initial club proposal')
    record=TransferNegotiation(f't24-{index:06d}',player_id,seller,buyer,as_of,
                               as_of+timedelta(days=21),status,proposal_by,terms,(event,))
    record.validate()
    registry.transfer_offers[record.deal_id]=record
    return record


def negotiate(session, command: dict) -> dict:
    """Transactional adapter: command is applied to a cloned session by caller."""
    registry=session._world_squads
    if registry.transfer_last_review_on is None:
        raise ValueError('Transfer market not initialized')
    now=session.current_date
    action=command.get('action')
    manager=_manager_club(session)
    if isinstance(action,str) and action.startswith('personal_'):
        from football_manager.services.transfer_personal import personal_command
        return personal_command(session,command)
    if action=='preview':
        seller=command.get('seller_id')
        pid=command.get('player_id')
        if type(seller) is not str or type(pid) is not str or seller==manager:
            raise ValueError('Choose a rival professional player')
        player,_=_player(registry,pid,seller)
        terms=_terms_from_data(command.get('terms'),now,_quote(registry,player).value_gbp)
        return {'valuation':assess_terms(registry,player,manager,terms,now),
                'available_transfer_budget_gbp':_availability(registry,manager,now),
                'market_value_gbp':_quote(registry,player).value_gbp,
                'note':'Risk-adjusted amount is NOT a seller acceptance quote.'}
    if action=='submit':
        from football_manager.services.ai_transfer_market import window_open
        if not window_open(now):
            raise ValueError('Transfer window is closed. New club offers open in January, July and August.')
        seller=command.get('seller_id')
        pid=command.get('player_id')
        if type(seller) is not str or type(pid) is not str or seller==manager:
            raise ValueError('Choose a rival professional player')
        _can_start(registry,pid,seller,manager,now)
        player,_=_player(registry,pid,seller)
        terms=_terms_from_data(command.get('terms'),now,_quote(registry,player).value_gbp)
        if terms.fixed_gbp>_availability(registry,manager,now):
            raise ValueError('Guaranteed fee exceeds available transfer budget')
        offer=_create_offer(registry,pid,seller,manager,now,terms,manager)
        answered=_apply_ai_reply(registry,offer,now)
        registry.transfer_offers[offer.deal_id]=answered
        return _status(answered.reason,answered.status,answered)
    deal_id=command.get('deal_id')
    if not isinstance(deal_id,str) or deal_id not in registry.transfer_offers:
        raise ValueError('Negotiation not found')
    old=registry.transfer_offers[deal_id]
    if manager not in (old.seller_id,old.buyer_id):
        raise ValueError('Cannot negotiate on behalf of a different club')
    if old.status=='agreed':
        if action=='withdraw':
            # Signed club agreements are not disposable negotiations.
            raise ValueError('Club agreement has already been accepted; awaits personal terms')
        raise ValueError('This club agreement is already concluded')
    if old.status!='manager_turn' or old.expires_on<now:
        raise ValueError('Negotiation is no longer active')
    if old.proposed_by==manager:
        raise ValueError('You must wait for the other club')
    if action=='withdraw':
        amended=replace(old,status='withdrawn',reason='Manager ended negotiations')
    elif action=='reject':
        amended=replace(old,status='rejected',reason='Manager rejected the offer')
    elif action=='accept':
        player,_=_player(registry,old.player_id,old.seller_id)
        required=_seller_target(registry,old.seller_id,old.buyer_id,player,
                                registry.contracts[old.player_id],now)
        if old.terms.fixed_gbp>_availability(registry,old.buyer_id,now,old.deal_id):
            raise ValueError('Buyer transfer budget no longer covers the guaranteed amount')
        amended=replace(old,status='agreed',expires_on=now+timedelta(days=45),
                        reason='Club terms agreed; player consent and transfer settlement pending')
    elif action=='counter':
        player,_=_player(registry,old.player_id,old.seller_id)
        new_terms=_terms_from_data(command.get('terms'),now,_quote(registry,player).value_gbp)
        if manager==old.buyer_id and new_terms.fixed_gbp>_availability(registry,manager,now,old.deal_id):
            raise ValueError('Guaranteed fee exceeds transfer budget')
        event=NegotiationEvent(now,manager,new_terms,'Manager counteroffer')
        candidate=replace(old,terms=new_terms,proposed_by=manager,events=(*old.events,event),
                          expires_on=now+timedelta(days=21),reason='Manager counteroffer submitted')
        amended=_apply_ai_reply(registry,candidate,now)
    else:
        raise ValueError('Unsupported transfer negotiation action')
    amended.validate()
    registry.transfer_offers[old.deal_id]=amended
    return _status(amended.reason,amended.status,amended)


def _settle_earned_bonuses(world, boundary: date) -> int:
    """Settle a single milestone at most once, using actual recorded outcomes.

    The historical fee never becomes guaranteed until its trigger is observed.
    Players who have moved on cannot create new appearance/goal/assist bonus
    milestones for an old buying club. Promotion refers to the buying club.
    """
    from football_manager.services.transfer_personal import career_player_totals
    registry=world.football_world
    count=0
    for key, deal in tuple(registry.transfer_offers.items()):
        if deal.status!='completed' or not deal.terms.bonuses:
            continue
        owner=registry.contracts.get(deal.player_id)
        currently_at_buyer=owner is not None and owner.club_id==deal.buyer_id
        totals=career_player_totals(registry,deal.player_id)
        earned=[]
        for bonus in deal.terms.bonuses:
            if bonus.kind in deal.bonus_paid:
                continue
            if bonus.kind=='promotion':
                qualifies=(currently_at_buyer and registry.identities[deal.buyer_id].tier>0 and
                    registry.identities[deal.buyer_id].tier < deal.buyer_tier_at_signing)
            else:
                stat_index={'appearances':0,'goals':1,'assists':2}[bonus.kind]
                qualifies=(currently_at_buyer and
                    totals[stat_index]-deal.bonus_baseline[stat_index] >= bonus.threshold)
            if qualifies:
                earned.append(bonus)
        if not earned:
            continue
        payout=sum(b.amount_gbp for b in earned)
        paid_kinds=(*deal.bonus_paid,*(b.kind for b in earned))
        from football_manager.services.transfer_personal import _sell_on_payout
        beneficiary,share=_sell_on_payout(registry,replace(deal,bonus_paid=paid_kinds))
        paying=registry.club_finances[deal.buyer_id]
        receiving=registry.club_finances[deal.seller_id]
        world._put(registry.club_finances,deal.buyer_id,replace(paying,
            cash_gbp=paying.cash_gbp-payout,
            transfer_budget_gbp=max(0,paying.transfer_budget_gbp-payout)))
        world._put(registry.club_finances,deal.seller_id,replace(receiving,
            cash_gbp=receiving.cash_gbp+payout-share,
            transfer_budget_gbp=receiving.transfer_budget_gbp+payout-share))
        if beneficiary is not None and share:
            current=registry.club_finances[beneficiary]
            world._put(registry.club_finances,beneficiary,replace(current,
                cash_gbp=current.cash_gbp+share,
                transfer_budget_gbp=current.transfer_budget_gbp+share))
        world._put(registry.transfer_offers,key,replace(deal,
            bonus_paid=paid_kinds,sell_on_paid_gbp=deal.sell_on_paid_gbp+share))
        count+=len(earned)
    return count


def review_transfers(world, boundary: date) -> int:
    """Monthly progression: expire stale talks, create occasional AI interest."""
    registry=world.football_world
    if registry is None or registry.transfer_last_review_on is None or world._active_journal is None:
        return 0
    if boundary.replace(day=1)<=registry.transfer_last_review_on:
        return 0
    previous=registry.transfer_last_review_on
    world._active_journal.undo_callbacks.setdefault(
        ('transfer-clock',id(registry)),lambda: setattr(registry,'transfer_last_review_on',previous))
    created=0
    month=registry.transfer_last_review_on
    while month<boundary.replace(day=1):
        _settle_earned_bonuses(world,boundary)
        y=month.year+(month.month//12)
        m=month.month%12+1
        month=date(y,m,1)
        for deal_id,record in tuple(registry.transfer_offers.items()):
            if record.status in ('manager_turn','agreed') and record.expires_on < month:
                world._put(registry.transfer_offers,deal_id,replace(record,status='expired',
                           reason='Club agreement or offer expired without completion'))
        # TS-24.5: retire the random quarterly manager bids. All new AI
        # offers must originate from position-sensitive squad planning.
        from football_manager.services.ai_transfer_market import process_ai_market
        created += len(process_ai_market(world,month))
        from football_manager.services.loan_market import process_ai_loans
        process_ai_loans(world,month)
        registry.transfer_last_review_on=month
    return created


def transfer_read_model(session) -> dict:
    """Read-only, predictable payload. No lazy mutation from GET."""
    registry=session._world_squads
    now=session.current_date
    manager=_manager_club(session)
    offers=[]
    for item in sorted(registry.transfer_offers.values(),key=lambda d:d.deal_id,reverse=True)[:80]:
        if manager not in (item.seller_id,item.buyer_id):
            continue
        try:
            # Historical completed deals remain visible after subsequent re-sales.
            owning=item.buyer_id if item.status=='completed' else item.seller_id
            player,_=_player(registry,item.player_id,owning)
        except ValueError:
            if item.status!='completed':
                continue
            present_contract=registry.contracts.get(item.player_id)
            current_owner=present_contract.club_id if present_contract else None
            if current_owner not in registry.clubs:
                continue
            try:
                player,_=_player(registry,item.player_id,current_owner)
            except ValueError:
                continue
        terms=item.terms
        evaluation=assess_terms(registry,player,item.buyer_id,terms,now)
        inactive=item.expires_on<now and item.status in ('manager_turn','agreed')
        personal=None
        if item.status=='agreed':
            from football_manager.services.transfer_personal import agent_demand
            personal=agent_demand(registry,player,item.seller_id,item.buyer_id,now)
        offers.append({'id':item.deal_id,'direction':'outgoing' if item.buyer_id==manager else 'incoming',
            'player_id':item.player_id,'player':player.full_name,'seller_id':item.seller_id,
            'buyer_id':item.buyer_id,'seller':registry.clubs[item.seller_id].name,
            'buyer':registry.clubs[item.buyer_id].name,'status':'expired' if inactive else item.status,
            'reason':item.reason,'fixed_gbp':terms.fixed_gbp,'terms':terms_as_json(terms),
            'valuation':evaluation,'market_value_gbp':_quote(registry,player).value_gbp,
            'expires_on':item.expires_on.isoformat(),'updated_on':item.events[-1].on_date.isoformat(),
            'events':len(item.events),'personal_status':item.personal_status,
            'personal_terms':({'weekly_wage_gbp':item.personal_terms.weekly_wage_gbp,
                'years':item.personal_terms.years,'role':item.personal_terms.role,
                'signing_bonus_gbp':item.personal_terms.signing_bonus_gbp}
                if item.personal_terms else None),
            'personal_quote':personal,'sell_on_paid_gbp':item.sell_on_paid_gbp,
            'bonus_paid':list(item.bonus_paid),
            'personal_history':[{'on_date':ev.on_date.isoformat(),'actor':ev.actor,
                'note':ev.note,'terms':{'weekly_wage_gbp':ev.terms.weekly_wage_gbp,
                 'years':ev.terms.years,'role':ev.terms.role,
                 'signing_bonus_gbp':ev.terms.signing_bonus_gbp}}
                for ev in item.personal_events],
            # Chronological events already persist in the save graph. Expose only
            # the terms shared between the two parties, not hidden AI thresholds.
            'history':[{'on_date':event.on_date.isoformat(),
                        'by_club_id':event.by_club_id,
                        'by_club':registry.clubs[event.by_club_id].name,
                        'by_manager':event.by_club_id==manager,
                        'note':event.note, 'terms':terms_as_json(event.terms)}
                       for event in item.events],
            'may_answer':not inactive and item.status=='manager_turn' and item.proposed_by!=manager,
            'proposed_by':item.proposed_by})
    # Browse only professional rivals with a contract; no uncontrolled PA fields.
    targets=[]
    for cid in sorted(registry.clubs):
        if cid==manager:continue
        club=registry.clubs[cid]
        for p in club.squad.players:
            if p.id not in registry.contracts or registry.contracts[p.id].kind!='professional':continue
            q=_quote(registry,p)
            targets.append({'id':p.id,'name':p.full_name,'club_id':cid,'club':club.name,
                            'position':p.primary_position.value,'ovr':round(p.overall_rating,1),
                            'age':p.age_on(now),'value_gbp':q.value_gbp,
                            'contract_until':registry.contracts[p.id].expires_on.isoformat()})
    targets.sort(key=lambda x:(x['club'],x['name']))
    from football_manager.services.ai_transfer_market import window_open
    world_deals=[d for d in registry.transfer_offers.values()
                 if d.status=='completed' and manager not in (d.seller_id,d.buyer_id)]
    world_deals.sort(key=lambda d:(d.started_on,d.deal_id),reverse=True)
    player_names={p.id:p.full_name for club in registry.clubs.values() for p in club.squad.players}
    for retired in registry.retired_players.values():
        player_names[retired.player.id]=retired.player.full_name
    transfer_news=[{'id':d.deal_id,'date':d.started_on.isoformat(),
                    'player_id':d.player_id,'player':player_names.get(d.player_id,d.player_id),
                    'from_club':registry.clubs[d.seller_id].name,
                    'to_club':registry.clubs[d.buyer_id].name,
                    'fee_gbp':d.terms.fixed_gbp}
                   for d in world_deals[:45]]
    return {'schema_version':1,'source':'ts24-5-autonomous-club-negotiation','date':now.isoformat(),
            'window_open': window_open(now), 'world_transfers':transfer_news,
            'club_id':manager,'club':registry.clubs[manager].name,
            'available_transfer_budget_gbp':_availability(registry,manager,now),
            'transfer_budget_gbp':registry.club_finances[manager].transfer_budget_gbp,
            'offers':offers,'targets':targets,
            'note':'Club offers reserve fees; player consent completes registration and guaranteed payments. Future bonuses remain recorded obligations.',
            'accepted_note':'A club agreement is provisional until the player and agent approve a contract and the transfer is settled.'}


def terms_as_json(terms: TransferTerms) -> dict:
    return {'fixed_gbp':terms.fixed_gbp,'bonuses':[{'kind':b.kind,'threshold':b.threshold,'amount_gbp':b.amount_gbp}
            for b in terms.bonuses], 'sell_on_type':terms.sell_on_type,
            'sell_on_percent':terms.sell_on_percent,'buyback_gbp':terms.buyback_gbp,
            'buyback_until':terms.buyback_until.isoformat() if terms.buyback_until else None}
