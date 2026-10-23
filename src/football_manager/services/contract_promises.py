"""Real playing-time commitments from signed manager/agent contract roles.

Leverage the existing manager-inbox promise assessment and its match-verified
appearance ledger. Do not invent starts, appearances or morale events.
"""
from __future__ import annotations

from datetime import timedelta
from football_manager.domain.manager_inbox import ManagerPromise


def record_contract_role_promise(session,player_id,role):
    if role not in ('star','important','regular','rotation'):
        return
    inbox=getattr(session,'manager_inbox',None)
    if inbox is None:
        return
    kind='starter_role' if role in ('star','important','regular') else 'playing_time'
    # Fresh contract role supersedes unresolved expectations from prior talks.
    for promise in inbox.promises:
        if promise.player_id==player_id and promise.status=='active' and promise.kind in ('starter_role','playing_time'):
            promise.status='void'
            promise.assessed_on=session.current_date
    promise=ManagerPromise(inbox.next_promise_id,player_id,session.current_date,
                           session.current_date+timedelta(days=84),kind)
    inbox.next_promise_id+=1
    inbox.promises.append(promise)
