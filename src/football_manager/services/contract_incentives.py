"""TS-FIX-03: once-only, money-backed player contract milestone settlements."""
from __future__ import annotations

from dataclasses import replace
from football_manager.domain.contract_negotiation import PlayerBonusLedger
from football_manager.services.transfer_personal import career_player_totals


def career_clean_sheets(registry, player_id):
    """Count only genuinely recorded goalkeeper/defender clean sheets.

    Legacy games without event coverage do not manufacture historic totals.
    Each competition/season total is disjoint and match verified.
    """
    return sum(stats.clean_sheets
               for competitions in registry.statistics.seasons.values()
               for rows in competitions.values()
               for pid, stats in rows.items() if pid == player_id)



def record_contract_bonuses(registry, player_id: str, club_id: str, now, bonuses):
    """Replace any former agreement; old triggers cannot be earned twice."""
    if not bonuses:
        registry.contract_bonuses.pop(player_id,None)
        return
    row=PlayerBonusLedger(player_id,club_id,now,(*career_player_totals(registry,player_id),career_clean_sheets(registry,player_id)),
                          registry.identities[club_id].tier,tuple(bonuses))
    row.validate()
    registry.contract_bonuses[player_id]=row


def due_contract_bonuses(world, current) -> dict[str,int]:
    """Pay earned contractual milestones when month closes, journaled atomically.

    Bonuses only remain payable while the recorded employment contract matches
    the exact registration. An old club must not pay a new club's milestones.
    """
    registry=world.football_world
    due={}
    for pid,row in tuple(registry.contract_bonuses.items()):
        contract=registry.contracts.get(pid)
        if (contract is None or contract.club_id!=row.club_id or contract.signed_on!=row.signed_on
                or current<row.signed_on):
            # Retain archived ledger (no payment) for transaction-safe history.
            continue
        if current > contract.expires_on:
            continue
        counts=(*career_player_totals(registry,pid),career_clean_sheets(registry,pid))
        values={'appearances':counts[0]-row.baseline[0],
                'goals':counts[1]-row.baseline[1],
                'assists':counts[2]-row.baseline[2],
                'clean_sheets':counts[3]-row.baseline[3],
                'promotion':int(registry.identities[row.club_id].tier<row.starting_tier)}
        earned=[b for b in row.bonuses if b.kind not in row.paid and values[b.kind]>=b.threshold]
        if earned:
            amount=sum(b.amount_gbp for b in earned)
            due[row.club_id]=due.get(row.club_id,0)+amount
            world._put(registry.contract_bonuses,pid,replace(row,paid=(*row.paid,*(b.kind for b in earned))))
    return due
