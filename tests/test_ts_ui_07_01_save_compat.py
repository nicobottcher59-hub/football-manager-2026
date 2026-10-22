"""Isolated SQLite save compatibility regression for the Youth Academy patch."""
from __future__ import annotations
from copy import deepcopy
import pytest
from football_manager.dev_ui.session import DevelopmentSession
from football_manager.services import youth_academy as ya

def test_scout_contract_survives_sqlite_save_and_existing_v22_section_markers(tmp_path):
    """New saves load; the old section-22 / graph-24 discrepancy is recoverable."""
    from dataclasses import replace
    from football_manager.persistence import SQLiteSaveRepository
    from football_manager.persistence.manager_career import (
        MANAGER_STATE_VERSION, manager_career_document, load_manager_career,
    )
    from football_manager.persistence.session_codec import GRAPH_VERSION
    s=DevelopmentSession()
    offer=ya.scout_market(s._world_squads.youth)[0]
    reply=ya.youth_command(s,{
        'action':'offer_scout','offer_id':offer['id'],'scout_id':None,
        'monthly_wage':offer['monthly_wage']*2,'years':3,'signing_fee':offer['signing_fee']})
    assert reply['accepted']
    assert MANAGER_STATE_VERSION == GRAPH_VERSION == 24
    repo=SQLiteSaveRepository(tmp_path/'academy-contracts.sqlite3')
    document=manager_career_document(s)
    repo.save('new','New',document,expected_revision=0)
    loaded=load_manager_career(repo,'new').session
    scout=loaded._world_squads.youth.scouts[reply['scout_id']]
    assert scout.monthly_wage == offer['monthly_wage']*2
    assert scout.contract_until.isoformat() == reply['until']
    assert loaded._world_squads.youth.recruitment_funds==s._world_squads.youth.recruitment_funds

    # Affected older builds accidentally tagged the v24 graph as section v22.
    original=document.sections[0]
    assert original.name=='manager_state'
    legacy_section=replace(original,version=22)
    legacy_document=replace(document,sections=(legacy_section,*document.sections[1:]))
    repo.save('legacy-marker','Prior build',legacy_document,expected_revision=0)
    recovered=load_manager_career(repo,'legacy-marker').session
    assert recovered._world_squads.youth.scouts[reply['scout_id']].monthly_wage==scout.monthly_wage
    assert recovered._world_squads.youth.recruitment_funds==loaded._world_squads.youth.recruitment_funds
